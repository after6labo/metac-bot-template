# Metaculus AI Forecasting Experiment Log

## 2026-09-23

### Objective
Enter Metaculus FutureEval / MiniBench as an AI forecasting bot under a strict zero-new-cost constraint and measure real tournament performance, ranking, and any prize earnings.

### Current setup
- Repository: `after6labo/metac-bot-template`
- Base: official Metaculus bot template
- Metaculus bot account: created
- API forecasting access: enabled
- LLM route for zero-cost baseline: `openrouter/openrouter/free`
- External research in zero-cost baseline: disabled
- Forecast samples per question: 1
- Parser validation samples: 1
- New spending: $0
- OpenRouter/Metaculus granted-credit application: submitted, pending

### Verification history
1. Test run #1: failed. Metaculus proxy did not allow `gpt-4o-search-preview`.
2. Test run #2: failed for the same unavailable search-model allowance.
3. Test run #3: research bypass worked, but fallback Metaculus proxy / rate-limit issues remained.
4. Test run #4: forecast generation succeeded through OpenRouter free routing, but Metaculus rejected submission because API forecasting access was not enabled.
5. Test run #5: succeeded end-to-end. One forecast was generated and submitted to the Bot Testing Area with zero reported LLM cost and no errors.

### Competition run
- First live workflow run: 2026-09-23
- Workflow conclusion: success
- MiniBench open questions returned by the official API alias `minibench`: 0
- Seasonal open questions returned by the official client: 0. Correction on 2026-09-24: this actually queried Summer project 33022, despite the Fall banner.
- Competitive forecasts submitted in this run: 0
- Reported LLM cost: $0.00000
- Fall 2026 FutureEval official start: 2026-09-28

### Automation
The live workflow is scheduled daily at 00:17 UTC (09:17 JST). It prioritizes MiniBench, then Fall FutureEval, while using a limited zero-cost batch until granted credits become available.

### User actions performed
- Created Metaculus bot account and token
- Forked the official template repository
- Created OpenRouter account/API key
- Submitted the free LLM-credit application
- Added required GitHub repository secrets
- Enabled Metaculus API forecasting
- Manually launched initial test/live workflows

### User work time
Not measured.

### Current measured results
- Bot Testing Area forecasts successfully submitted: 1
- Competitive forecasts: 0
- Competitive score/rank: not yet available
- Prize earnings: $0
- New monetary cost: $0

### Next trigger
Wait for MiniBench or Fall FutureEval questions to become open. The scheduled workflow will attempt participation automatically without requiring manual action.


## 2026-09-24 — autonomous operations audit

### Evidence and correction
- Inspected default branch `a7c560ba17f84865141dcdbdc9a4b44336b5dda4`, Actions run `35841074249`, and its job `107115990452`.
- The 2026-09-23 live job queried `minibench` and **33022 (Summer)**, not Fall. Both returned zero. The earlier Fall-specific claim was wrong.
- Official Fall target: **33121 / `fall-futureeval-2026`**, opens 2026-09-28, closes 2027-01-06; prize pool $50,000.
- MiniBench canonical alias `minibench` currently displays 2026-09-21 to 2026-10-09, 60 total questions, $1,000 pool. A displayed total is not an API open count.
- Locked SDK is forecasting-tools 0.2.92. Its seasonal constant is stale; target the verified slug explicitly. Its convenience retrieval only gets the first page, so use the existing async paginated API without a dependency upgrade.
- Only manual Actions runs were visible at audit time. The production workflow was not labelled Disabled; the Cup and review workflows were Disabled. Daily cron configuration is not proof of a scheduled execution.
- Participation and free-credit application use the same official form. The handoff reports that application submitted; credit approval and prize eligibility have not been independently verified.

### Bounded changes
- Keep free router, no external research, one prediction and one parser attempt; no paid fallback. Require both existing credential names, never print their values.
- Reject Cup mode and remove its automatic schedule. Share the free quota concurrency group across test/live runs.
- Use explicit Fall slug and current MiniBench alias, skip already-forecasted IDs, deduplicate, conservatively exclude election-related questions, and cap each live batch at 12.
- Add general base-rate/evidence/incentive/counter-scenario guidance. No live question's forecast was inspected or individually tuned.
- Record submission-complete versus failure/unconfirmed separately. SDK posts prediction before comment; an exception must not be represented as a confirmed submission or blindly retried by hand.
- Persist sanitized per-run JSON to `run-results/`, with unknown metrics as null, and return nonzero on a failed fetch or forecast.
- Run offline regression tests before live runs. Allow code changes on main to trigger the same bounded live workflow, in addition to the existing daily 09:17 JST schedule.

### Validation and current result
- 16 offline regression tests passed; syntax compilation and workflow YAML parsing passed. Runtime integration remains subject to the next Actions result.
- Historical confirmed test submissions: 1. Historical confirmed competitive submissions: 0. Official score/rank: unavailable at audit.
- New spending to date: $0. Prize receipts to date: $0. User work in this audit: no additional operation; time not measured.
- API counts, token usage, actual routed model identities, and credit balance are not yet instrumented and are explicitly null. Free router route name is not a fixed underlying model.
- External research remains disabled, a material forecasting weakness. No accuracy improvement is claimed before resolved-question evidence exists.

### Official references checked
- https://www.metaculus.com/tournament/fall-futureeval-2026/
- https://www.metaculus.com/tournament/summer-futureeval-2026/
- https://www.metaculus.com/tournament/minibench/
- https://www.metaculus.com/notebooks/45615/announcement-of-futureeval-fall-2026/
- https://www.metaculus.com/notebooks/38928/futureeval-resources-page/
- https://www.metaculus.com/futureeval/participate/
- https://github.com/Metaculus/metac-bot-template
- https://github.com/Metaculus/forecasting-tools
- https://openrouter.ai/openrouter/free
- https://openrouter.ai/docs/api/reference/limits

- Review found missing elected/legislative-seat outcome wording; added a failing regression case, fixed the filter, and re-ran all 16 tests successfully. Reviewer completed SDK API checks but its final pass ended at the available usage limit.
