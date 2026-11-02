# Numeric generation retry implementation plan

> For agentic workers: use superpowers:executing-plans, TDD and verification-before-completion.

Goal: recover transient numeric generation failures without a human rerunning jobs.
Architecture: match the existing multiple-choice bounded generation loop in main.py, before numeric parsing. No prompt, probabilities, parser, routing, question eligibility or cooldown changes.
Spec: owner's standing autonomous-repair instruction; production 41393032499 HTTP 500 and 41395951698 empty-response failures both at numeric initial invoke. Maximum three invocations (SDK two provider attempts each); ProviderPaused and cancellation propagate immediately; success is never regenerated for conversion failures.

Approaches: raising token/time limits would not address HTTP 500 and would delay other questions; manual job reruns recover but depend on operator checks. Chosen by operator: existing bounded retry pattern, without tuning live outputs.

Global constraints: zero new spending; existing free router only; no paid fallback; no provider limit bypass; no live output/prompt changes. Existing 180-second/8192-token/3.2-second serial settings and 25-minute job timeout unchanged.

Review focus: pause on first/later attempt, exhausted retries, successful generation followed by bad parsing, cancellation, sanitized diagnostics.

## Task 1: numeric generation recovery

- [x] Add tests/test_numeric_generation_retry.py exercising the real method. Transient AssertionError and TimeoutError then success must preserve one reasoning and prediction; three failures must raise without parsing; ProviderPaused first/after a transient error must stop; bad conversion must not regenerate; cancellation propagates; log exception type only.
- [x] Run unittest discovery on the new test; observed four missing-retry failures before production edit.
- [x] Add the bounded loop only around initial numeric invoke. Update AGENTS.md implementation description.
- [x] Run full Python and Node suites; review minimal diff. SDK-unavailable local tests use AST isolation of the real numeric method, not a rewritten implementation. Actions must additionally run actual SDK tests.
- [x] Commit atomically through configured GitHub connector, verify exact files and deployed workflow result, reconcile all pending IDs and publication timestamps before report.

## Progress / rulings

- Native implementation; separate scratch snapshot repository because prior scratch copy is stale, no usable remote git checkout. No external credential extraction or network workaround.
- User explicitly authorized routine fixes without approval pauses; no new design approval requested. Local baseline: 98 tests, 23 SDK skips; Node12 pass. Environment-status tool/policy snapshot unavailable; no shell network attempted.
- Final local suite: 104 tests, 23 SDK skips; Node12 pass; diff check clean. Independent review found no Critical/Important/Minor issues. Actual SDK and deployment results remain a required post-deploy gate; live provider reliability/forecast quality are not established by offline tests. Preserve pending incidents until publication evidence exists.

- Deployment f636384d1237fd70a85fbd753068e11a1d7104da verified byte-for-byte. Actions41399202158:104 SDK-inclusive tests, Node12 pass, q46617 prediction and explanation posted, both inventories matched, no pending or fetch errors; all persistence steps passed. Bounded retry branch did not fire live; its coverage is offline. Forecast quality and long-term provider reliability remain unproven. See EXPERIMENT_LOG.md 2026-11-02 15:28 JST for all run/publication evidence and remaining incidents.
