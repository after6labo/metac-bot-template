/* External wake-up only. Forecasting and both API secrets remain in Actions.
 * Configure GITHUB_ACTIONS_TOKEN in Script Properties, never in this file.
 * See operations/EXTERNAL_SCHEDULER.md before installing the trigger.
 */
const METACULUS_REPO = 'after6labo/metac-bot-template';
const METACULUS_WORKFLOW = '.github/workflows/run_bot_on_tournament.yaml';
const METACULUS_TEST_WORKFLOW = '.github/workflows/test_bot.yaml';
const METACULUS_INTERVAL_MS = 20 * 60 * 1000;

function metaculusSchedulerTick() {
  return metaculusSchedulerCheck_(false);
}

function checkMetaculusScheduler() {
  return metaculusSchedulerCheck_(true);
}

function metaculusSchedulerCheck_(dryRun) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return { status: 'lock_busy' };
  try {
    const properties = PropertiesService.getScriptProperties();
    const token = properties.getProperty('GITHUB_ACTIONS_TOKEN');
    if (!token) throw new Error('Set GITHUB_ACTIONS_TOKEN in Script Properties. Never paste it in chat or code.');
    const now = Date.now();
    const last = Number(properties.getProperty('METACULUS_LAST_DISPATCH_MS') || 0);
    if (!Number.isFinite(last) || last < 0) throw new Error('Invalid dispatch cooldown');
    if (!dryRun && now - last < METACULUS_INTERVAL_MS) {
      return metaculusSchedulerStatus_('dispatch_cooldown', now);
    }
    const response = metaculusGithub_(token, 'get', '/actions/runs?per_page=100');
    let data;
    try { data = JSON.parse(response); }
    catch (_) { throw new Error('Invalid GitHub run collection'); }
    if (!Array.isArray(data.workflow_runs)) throw new Error('Invalid GitHub run collection');
    let latestProduction = 0;
    for (const run of data.workflow_runs) {
      if (!run || typeof run.path !== 'string' || typeof run.status !== 'string') {
        throw new Error('Invalid GitHub run metadata');
      }
      if (![METACULUS_WORKFLOW, METACULUS_TEST_WORKFLOW].includes(run.path)) continue;
      if (run.status !== 'completed') return metaculusSchedulerStatus_('active_run', now);
      if (run.path === METACULUS_WORKFLOW && run.head_branch === 'main') {
        const created = Date.parse(run.created_at);
        if (!Number.isFinite(created)) throw new Error('Invalid GitHub run timestamp');
        latestProduction = Math.max(latestProduction, created);
      }
    }
    if (now - latestProduction < METACULUS_INTERVAL_MS) {
      return metaculusSchedulerStatus_('recent_run', now);
    }
    if (dryRun) return metaculusSchedulerStatus_('would_dispatch', now);
    // Reserve before POST: a transport failure may still have launched a run.
    properties.setProperty('METACULUS_LAST_DISPATCH_MS', String(now));
    metaculusGithub_(token, 'post', '/actions/workflows/run_bot_on_tournament.yaml/dispatches', {ref: 'main'});
    return metaculusSchedulerStatus_('dispatched', now);
  } finally {
    lock.releaseLock();
  }
}

function metaculusGithub_(token, method, path, body) {
  const options = {
    method: method,
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2026-03-10',
    },
    muteHttpExceptions: true,
    followRedirects: false,
  };
  if (body) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(body);
  }
  let response;
  try {
    response = UrlFetchApp.fetch('https://api.github.com/repos/' + METACULUS_REPO + path, options);
  } catch (_) {
    // Do not print request options, provider bodies or credentials.
    throw new Error('GitHub transport failure; no automatic immediate retry');
  }
  const status = response.getResponseCode();
  // API 2026-03-10 returns 200; also accept legacy 204 without a body.
  if (!(method === 'post' ? [200, 204].includes(status) : status === 200)) {
    throw new Error('GitHub ' + method.toUpperCase() + ' failed (HTTP ' + status + ')');
  }
  return method === 'post' ? '' : response.getContentText();
}

function metaculusSchedulerStatus_(status, now) {
  const result = { status: status, checked_at_utc: new Date(now).toISOString() };
  PropertiesService.getScriptProperties().setProperty('METACULUS_SCHEDULER_STATUS', JSON.stringify(result));
  console.log(JSON.stringify(result));
  return result;
}

function installMetaculusScheduler() {
  // Validate access without submitting a forecast or requesting a launch.
  checkMetaculusScheduler();
  removeMetaculusScheduler();
  ScriptApp.newTrigger('metaculusSchedulerTick').timeBased().everyMinutes(10).create();
  console.log('Installed one 10-minute trigger. First launch remains subject to checks.');
}

function removeMetaculusScheduler() {
  for (const trigger of ScriptApp.getProjectTriggers()) {
    if (trigger.getHandlerFunction() === 'metaculusSchedulerTick') ScriptApp.deleteTrigger(trigger);
  }
}
