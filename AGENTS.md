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
- Production: .github/workflows/run_bot_on_tournament.yaml; daily 00:17 UTC,
  manual runs, and relevant main code changes. Shared concurrency with smoke test.
- Explicit Fall 2026 slug: fall-futureeval-2026 (33121); MiniBench alias: minibench.
  Review after the season; do not blindly trust the locked SDK seasonal constant.
- OpenRouter free router only; no live search; <=12 questions/run; one reasoning
  sample and one parser attempt. Underlying routed model may change.
- Election-related forecasts are conservatively filtered per project policy;
  this is a user scope constraint, not a claim about all AI product restrictions.
- Basic stance: base rates -> verified evidence -> incentives and observed social
  factors -> counter-scenario -> probability. Avoid ethnic/national stereotypes;
  distinguish should from will, and missing research from current evidence.
- Complete reports indicate prediction and explanation publication returned.
  Exceptions may follow a successful prediction but failed comment. Investigate
  before retrying; already_forecasted alone does not prove comment success.
- Cup mode is disabled; its default configuration is outside the free experiment.
- Tests: python -m unittest discover -s tests -v

## Measurements and next work
Preserve start date, route/model history, calls/tokens/balance when observable,
submission/failure/skip counts, official score/rank, calibration, reasons for
changes, before/after outcomes, owner actions/time, new spend and prize receipts.
Do not invent unobserved values. Runtime JSON is not a billing or payout receipt.
Observe upcoming first actual competitive submission, then resolved outcomes.
Credit approval can improve research/model options only after checking grant
limits and paid-overrun prevention. Free-credit approval is not yet verified.
Fall participant-form and free-credit application use the same official form;
the owner reports it submitted. Seasonal survey remains required for prizes.
