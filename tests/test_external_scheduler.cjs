const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('operations/github_scheduler.gs', 'utf8');
const now = Date.parse('2026-09-25T03:00:00Z');
const live = '.github/workflows/run_bot_on_tournament.yaml';
const smoke = '.github/workflows/test_bot.yaml';
function run(age, status = 'completed', path = live) {
  return { path, head_branch: 'main', status, created_at: new Date(now-age*60000).toISOString() };
}
function harness(runs = [], overrides = {}) {
  const calls = [], props = { GITHUB_ACTIONS_TOKEN: 'test-placeholder', ...overrides.props };
  let unlocked = false;
  const context = vm.createContext({
    Date: class extends Date { static now() { return now; } },
    console: { log() {} },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: k => props[k] || null, setProperty: (k,v) => { props[k] = v; },
    }) },
    LockService: { getScriptLock: () => ({
      tryLock: () => overrides.lock !== false, releaseLock: () => { unlocked = true; },
    }) },
    UrlFetchApp: { fetch: (url, options) => {
      calls.push({ url, options });
      if (overrides.throwFetch) throw Error('do not expose request internals');
      const method = options.method || 'get';
      const code = method === 'post' ? (overrides.postCode || 204) : (overrides.getCode || 200);
      return { getResponseCode: () => code, getContentText: () => JSON.stringify(
        overrides.body || { total_count: runs.length, workflow_runs: runs }
      ) };
    } },
  });
  vm.runInContext(source, context);
  return { context, calls, props, unlocked: () => unlocked,
    tick: () => context.metaculusSchedulerTick(), check: () => context.checkMetaculusScheduler() };
}
test('three-hour schedule gap dispatches main exactly once and persists cooldown', () => {
  const h = harness([run(183)]);
  assert.equal(h.tick().status, 'dispatched');
  const post = h.calls.find(c => c.options.method === 'post');
  assert.match(post.url, /run_bot_on_tournament.yaml\/dispatches$/);
  assert.deepEqual(JSON.parse(post.options.payload), { ref: 'main' });
  assert.equal(h.props.METACULUS_LAST_DISPATCH_MS, String(now));
  assert.equal(h.tick().status, 'dispatch_cooldown');
  assert.equal(h.calls.filter(c => c.options.method === 'post').length, 1);
  assert.ok(h.unlocked());
});
test('recent production launch needs no additional launch', () => {
  const h = harness([run(19)]);
  assert.equal(h.tick().status, 'recent_run');
  assert.equal(h.calls.length, 1);
});
test('exactly twenty minutes allows a launch', () => {
  assert.equal(harness([run(20)]).tick().status, 'dispatched');
});
test('current API 200 dispatch response is accepted alongside legacy 204', () => {
  assert.equal(harness([run(183)], {postCode:200}).tick().status, 'dispatched');
});
test('active production or smoke test blocks duplicate launch', () => {
  for (const path of [live, smoke]) for (const status of ['queued', 'in_progress', 'pending', 'waiting', 'requested']) {
    const h = harness([run(183), run(2, status, path)]);
    assert.equal(h.tick().status, 'active_run');
    assert.equal(h.calls.length, 1);
  }
});
test('active non-main runs still hold the shared concurrency lock', () => {
  for (const path of [live, smoke]) {
    const otherBranch = {...run(1, 'in_progress', path), head_branch: 'maintenance'};
    const h = harness([otherBranch, run(183)]);
    assert.equal(h.tick().status, 'active_run');
    assert.doesNotMatch(h.calls[0].url, /branch=main/);
    assert.equal(h.calls.length, 1);
  }
});
test('unrelated workflow or completed smoke test does not hide production gap', () => {
  const h = harness([run(1, 'completed', smoke), run(1, 'in_progress', 'other.yaml'), run(183)]);
  assert.equal(h.tick().status, 'dispatched');
});
test('read-only setup check never dispatches', () => {
  const h = harness([run(183)]);
  assert.equal(h.check().status, 'would_dispatch');
  assert.equal(h.calls.length, 1);
  assert.equal(h.props.METACULUS_LAST_DISPATCH_MS, undefined);
});
test('missing token and overlap fail safely before network', () => {
  const missing = harness([], { props: { GITHUB_ACTIONS_TOKEN: '' } });
  assert.throws(() => missing.tick(), /GITHUB_ACTIONS_TOKEN/);
  assert.equal(missing.calls.length, 0);
  const locked = harness([], { lock: false });
  assert.equal(locked.tick().status, 'lock_busy');
  assert.equal(locked.calls.length, 0);
});
test('API denial or transport failure never dispatches and exposes no body', () => {
  for (const options of [{getCode:401}, {getCode:429}, {throwFetch:true}]) {
    const h = harness([run(183)], options);
    assert.throws(() => h.tick(), /GitHub/);
    assert.equal(h.calls.length, 1);
    assert.ok(h.unlocked());
  }
});
test('dispatch error preserves cooldown against ambiguous retry storms', () => {
  const h = harness([run(183)], {postCode:500});
  assert.throws(() => h.tick(), /GitHub/);
  assert.equal(h.tick().status, 'dispatch_cooldown');
  assert.equal(h.calls.filter(c => c.options.method === 'post').length, 1);
});
test('empty repository can bootstrap; malformed timestamps/data fail closed', () => {
  assert.equal(harness([]).tick().status, 'dispatched');
  for (const body of [{}, {workflow_runs: [{}]}, {workflow_runs: [{...run(50), created_at:'invalid'}]}]) {
    const h = harness([], {body});
    assert.throws(() => h.tick(), /Invalid/);
    assert.equal(h.calls.length, 1);
  }
});
