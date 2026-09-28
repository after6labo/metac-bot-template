# Metaculus zero-new-cost experiment

The operator may autonomously maintain this existing public repository, run tests,
commit routine fixes and sanitized experiment logs, and operate the existing bot.
The goal is measured official tournament performance and prize receipts, not a demo.

## Non-negotiable boundaries
- New monetary spending is zero. Never enable paid API models, search, cloud, or
  automatic paid fallback. Unavailable free service means stop that run.
- Never print, commit, request in chat, or copy secrets. Existing credentials stay
  in GitHub Actions Secrets; names are METACULUS_TOKEN and OPENROUTER_API_KEY.
- Account creation, new service registration, login, new keys, identity checks,
  terms acceptance, new repositories and payments require the account owner's action.
- Do not use company confidential information or personal private information.
- Do not send email/Discord/other messages without explicit authorization.
- Do not ask the owner to set or correct individual tournament probabilities.
  Never tune an answer after inspecting a live/upcoming question's bot output.
  Use resolved results and aggregate error patterns for accuracy improvements.

## Resume procedure
1. Recheck the current Metaculus official rules, competition IDs/slugs, dates,
   participation/prize conditions, human-in-the-loop rules, and free-credit policy.
2. Read EXPERIMENT_LOG.md, run-results/latest.json and recent GitHub Actions runs.
   A configured schedule is not evidence of an execution. A green empty run is
   not a submission. Unknown score, balance or usage is null, not zero.
3. Diagnose concrete failures before editing. Apply a small reversible change,
   run offline tests and inspect its actual Actions result. No force pushes.
4. Keep this baseline until a resolved benchmark supports a measured improvement.
   Do not add a large agent framework or spend quota on no-new-question runs.

## Current implementation
- Production: .github/workflows/run_bot_on_tournament.yaml; every 20 minutes (UTC minutes 7, 27, 47),
  manual runs, and relevant main code changes. Shared concurrency with smoke test.
- Explicit Fall 2026 slug: fall-futureeval-2026 (33121); MiniBench alias: minibench.
  Review after the season; do not blindly trust the locked SDK seasonal constant.
- OpenRouter free router only; no live search; <=12 questions/run; one reasoning
  sample and one parser attempt. Shared UTC-day quota is 40 reserved outbound calls,
  stored in run-results/budget.json; failed calls consume it too. A provider 402/429
  blocks further calls that day. Underlying routed model may change.
- The owner explicitly removed topic-based exclusions on 2026-09-29 JST.
  Election-related questions are eligible under the same rules as other topics.
  Do not reintroduce topic filters without an explicit owner request. The earlier
  statement describing election exclusion as a user scope constraint was incorrect.
  Retain duplicate/already-forecasted guards and all zero-cost/quota controls.
- Basic stance: base rates -> verified evidence -> incentives and observed social
  factors -> counter-scenario -> probability. Avoid ethnic/national stereotypes;
  distinguish should from will, and missing research from current evidence.
- Complete reports indicate prediction and explanation publication returned.
  Exceptions may follow a successful prediction but failed comment. Investigate
  before retrying; already_forecasted alone does not prove comment success.
- Cup mode is disabled; its default configuration is outside the free experiment.
- Tests: python -m unittest discover -s tests -v
- Scheduler regression tests: node --test tests/test_external_scheduler.cjs
- The configured 20-minute cron has observed 183–193 minute gaps. External
  Apps Script wake-up is prepared in operations/github_scheduler.gs and documented
  in operations/EXTERNAL_SCHEDULER.md. Owner installed the 10-minute GAS trigger
  on 2026-09-25 04:23:50 UTC; first manual GAS dispatch 36094321091 succeeded.
  Post-activation audit through 2026-09-25 08:29:18 UTC verified 8 later dispatches
  plus 1 native schedule run over 4h04m40s, all successful. Fetch-phase starts
  were generally ~30 minutes apart; max 30m14.324s including the current tail
  (12m06.416s). Initial cadence acceptance is met, not a guarantee of 20 minutes
  or future coverage. GAS timer logs were not directly inspected. See the log.
  Investigate gaps >60 minutes; >=90 minutes remains a coverage failure.

## Measurements and next work
Preserve start date, route/model history, calls/tokens/balance when observable,
submission/failure/skip counts, official score/rank, calibration, reasons for
changes, before/after outcomes, owner actions/time, new spend and prize receipts.
Do not invent unobserved values. Runtime JSON is not a billing or payout receipt.
Observe upcoming first actual competitive submission, then resolved outcomes.
The owner supplied the season's LLM-credit rejection notice (recorded Sep28).
Treat Fall 2026 as no donated credits; continue only the existing free router.
The email's sender/header was not independently authenticated. No reply or
resubmission is required by that notice. Runtime credit_approval=unverified is
not the authoritative application status; this operator record supersedes it.
Any future grant requires explicit verification and paid-overrun prevention.
Fall participant-form and free-credit application use the same official form;
the owner reports it submitted. Seasonal survey remains required for prizes.

## Open participation incident — 2026-09-28
- MiniBench has zero confirmed submissions since startup on Sep23, despite a Sep21 round start. Treat competition participation as not achieved, not healthy merely because Actions succeeds.
- The Sep28 06:27 UTC result returned 0 MiniBench and 0 Fall open questions. This is a filtered retrieval count, not evidence that no competition questions exist or that none were missed.
- Root cause is unresolved: historical opening/closing metadata has not been reconciled with polling times. Do not assert either a broken filter or a legitimately closed round without evidence.
- The operator's cloud browser cannot view the official list because of a persistent site security check. Do not bypass that restriction. Existing logs lack question-window metadata; an owner-supplied screenshot/export can supply the missing evidence.
- Next priority is to establish actual MiniBench question availability during bot operation, then fix a demonstrated retrieval/coverage fault or identify the next verified submission opportunity. Do not tune individual live forecasts.
- Report Bot execution, accepted competitive submissions, and official score separately. No 'wait, all is well' assurance while this incident is unresolved. The owner should not have to interpret English pages or diagnose the bot.

### Confirmed missed window — question 45980 / post 45795
Owner-provided official question_data.csv (exported Sep28 06:58:36 UTC) identifies MiniBench project 33125 and an exact open window Sep23 21:10:51–Sep24 00:10:51 UTC (Sep24 06:10:51–09:10:51 JST). No production workflow started during this window: preceding run 35841074249 started Sep23 09:07:25 UTC; next run 35998719942 started Sep24 12:23:12 UTC. This establishes at least one missed submission opportunity due to absent polling, before GAS activation on Sep25. Do not generalize this single-question cause to all 60 items or claim that query correctness is fully verified. The supplied ZIP contains aggregate forecasts, not individual bot participation proof. No individual prediction was tuned. Latest audited 24h through Sep28 06:46:56 UTC: 52 successful production runs, maximum creation-time gap 30m04s; fetch timing must be reported separately. Keep the installed scheduler; accepted competitive submission remains the next unverified milestone.
