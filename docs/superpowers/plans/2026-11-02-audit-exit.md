# Audit attention exit status implementation plan

> For agentic workers: use superpowers:executing-plans inline; keep this repair narrowly scoped.

**Goal:** Do not report successful process completion when the independent inventory audit requires attention.

**Architecture:** Keep forecasting, eligibility, independent inventory and result persistence unchanged. Include the runner's needs_attention flag in the final should_fail_run predicate, which main calls only after forecasting and saving results.

**Tech Stack:** Existing Python unittest and GitHub Actions.

**Spec:** Owner's current autonomous-operation request and AGENTS.md, Overnight participation monitoring. Routine repairs and production deployment are already authorized without further approval.

## Global constraints

- Zero new spending; existing free-only route; no extra provider retry or paid fallback.
- No changes to live probabilities, prompts, question eligibility or provider stopping conditions.
- Failed audits remain actionable even if pending is empty. Healthy targets must still forecast.

## Review focus

- Audit-only attention must fail; healthy empty and submitted runs must not.
- Partial publication plus audit attention must fail only after existing publication/persistence.
- Existing pending, fetch and publication failures must retain failure behavior.
- Regression tests must exercise the real predicate, not a default stub.
- Actions must run the whole suite before the bot and preserve results even on failure.

## Task 1: Restore audit failure propagation

- [x] Read bot_runtime.py, main.py final call, bot_helpers.py and production workflow. Root cause: should_fail_run explicitly omitted audit-only needs_attention.
- [x] Change tests/test_bot_helpers.py to require failure for audit-only attention and partial publication with attention; verify healthy cases remain successful.
- [x] Run unittest: two expected AssertionError failures before implementation.
- [x] Add needs_attention to bot_helpers.should_fail_run and update its docstring; no other production change.
- [x] Run full available suite: 98 tests, 23 SDK-dependent skips because SDK is not installed locally; Node scheduler tests 12/12. Do not treat skipped tests as passed.
- [ ] Independent read-only review, then atomic commit of helper, tests and this record to existing main.
- [ ] Inspect triggered production Actions: all 98 Python and 12 Node tests, actual audit/pending/outcomes, prediction retention and persistence. Record results in EXPERIMENT_LOG.md.

## Execution rulings

- Use an isolated snapshot from the configured GitHub connector; no repository credentials are present or copied locally. Source blobs are checked again before atomic tree/ref update.
- Owner explicitly requests continued execution without waiting for further design approval. This is a minimal restoration of the documented failure contract, not a new feature.
- Local SDK skips require verification in the existing Actions environment, before claiming full validation.
