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

### Verified run and submission-window correction
- Commit b72179d triggered Actions run 35998719942 automatically. Dependency installation, all 16 tests, live execution, artifact saving and repository logging succeeded.
- API returned MiniBench 0 and Fall 1 open question. One forecast plus explanation was successfully submitted for question ID 45707 with zero report errors and estimated cost $0.00000.
- This precedes the official Sep28 season opening, so treat it as a Fall-area submission/practice pending confirmation of score eligibility; do not count it as a scored competitive result. Score and rank are still unknown.
- Official resources (edited Sep23) say batches open at random hours for only 1.5 hours. The inherited daily schedule would miss many. Change polling to every 20 minutes with a shared persistent 40-request UTC-day limit, 3.2-second minimum spacing, no SDK retries, and a stop for the day on provider 402/429. This is a submission-coverage correction, not a claim about forecast accuracy.
- Request reservations are written before each call and committed in the workflow's always-run finalizer, including failures. Token counts cover successful responses observed after instrumentation. Unknown routed model and credit balance stay null.
- Checkout main after acquiring shared concurrency so queued runs see the newest quota. A hard runner kill or repository-write failure can prevent quota persistence; provider free-tier enforcement remains in force and such workflow failures require investigation before retrying.
- A conservative four-request carry-forward reserve covers the earlier uninstrumented one-question run on Sep24; it is a safety reserve, not a measured call count. The instrumented per-run count starts separately.
- Daily ChatGPT operations/score check has also been scheduled, with notifications only for meaningful changes or required owner action.


## 2026-09-25 — daily operations check (02:24–02:28 UTC)

### Measured activity since the previous verified push run
- Re-read main AGENTS.md, this log, latest.json, all five persisted run-result files, repository metadata, and the complete Actions run collection (11 runs returned, not a truncated page).
- Three scheduled production runs are now confirmed: [36035254375](https://github.com/after6labo/metac-bot-template/actions/runs/36035254375) at Sep24 17:34:28 UTC; [36057295051](https://github.com/after6labo/metac-bot-template/actions/runs/36057295051) at 20:47:58 UTC; [36074778580](https://github.com/after6labo/metac-bot-template/actions/runs/36074778580) at 23:51:15 UTC. All completed successfully, including result persistence. Latest job 107883428189 reports 21 passing offline tests.
- Across those three scheduled runs: new complete submissions **0**, failed/unconfirmed submissions **0**, reserved outbound LLM attempts **0**, observed LLM tokens **0**, estimated LLM cost **$0**. Each found MiniBench 0 / Fall 1 open and skipped question 45707 as already_forecasted: **3 skip events, 1 unique question**. These are observations at polling times, not proof there were no questions between polls.
- Confirmed historical submissions remain Bot Testing Area **1**, Fall-area forecast plus explanation **1**; scored eligibility of the pre-season Fall submission remains unverified. No new submission was made by this audit.
- Official score, rank, calibration, current credit balance/approval and actual routed model remain **unknown**, not zero. The current production results do not query official scores or provider key balances. No authenticated credit or payout receipt was available in this audit. Historical recorded receipts are $0; current independently verified payout total is unknown. Cumulative API usage is also unknown because the earlier one-question run predates instrumentation.
- The budget file still contains the Sep24 safety reservation of 4, not 4 measured calls. It is not a provider credit balance. Recorded new spending remains $0 under the unchanged free-only route; provider billing was not independently retrieved. No new paid service, paid fallback, key or account was enabled; no owner action/time was required or measured.

### Operational issue: configured interval is not achieved
- main still contains cron `7,27,47 * * * *`; main is the actual default branch, the repository is public and not archived, and the schedule demonstrably triggers.
- Consecutive observed schedule starts are **193m30s** and **183m17s** apart. Latest run was created/started at 23:51:15 and completed at 23:52:26 (71 seconds). Thus long bot execution is not the explanation for these gaps; no queued/in-progress run was returned.
- This can miss the official **90-minute** submission windows. Actual missed eligible questions are **unknown**, not estimated from the gaps.
- GitHub documents that scheduled events can be delayed or dropped under load: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule . Scheduler delay/drop is consistent with the evidence but its specific cause for this repository is **unconfirmed**.
- No speculative code fix, schedule churn, long-lived polling runner, duplicate launch or retry loop was introduced. A manual launch would not repair schedule reliability. Retain the bounded free-only workflow and check whether gaps persist on the next audit; escalate sustained coverage loss rather than claiming 20-minute execution is guaranteed. The daily monitor remains enabled because safe operations are not fully blocked.

### Official rules and dates rechecked
- Fall page still shows `fall-futureeval-2026`, Sep28 2026–Jan06 2027, $50,000; MiniBench `minibench` shows Sep21–Oct09 2026, 60 total displayed questions, $1,000. Total displayed questions do not mean open questions. Keep explicit Fall target; do not use SDK 0.2.92's stale 33022.
- Resources page (edited Sep23) was read in the browser: one forecast per question with a private explanation comment; random batches and 1.5-hour windows; spot peer scoring; one prize-eligible primary bot per participant/team; no question-specific human preview/tuning or reruns; description/code inspection requirements. Autonomous bot operation remains allowed. No forecast content was inspected for tuning.
- Free donated credits use a separately issued OpenRouter key. Approval is not implied by the personal free-router key or a successful run. No model/search change before grant and overrun safety are verified. Seasonal surveys and any eventual identity/payment steps remain owner actions, not silently completed.
- Browser could read the rules body but the Fall tournament subsequently showed a Cloudflare security-verification page. No challenge was attempted or bypassed. Search could confirm public dates, but live leaderboard verification was unavailable; no claim of score/rank zero or of no resolved questions is made.
- Sources: https://www.metaculus.com/notebooks/38928/futureeval-resources-page/ ; https://www.metaculus.com/tournament/fall-futureeval-2026/ ; https://www.metaculus.com/tournament/minibench/ .


## 2026-09-25 — schedule investigation and external wake-up preparation

### Evidence and diagnosis
- Rechecked all 11 Actions runs. Only three are schedule-triggered; their creation gaps are 193m30s and 183m17s. No hidden queued or cancelled production runs account for the gaps.
- Latest run 36074778580: created 23:51:15 UTC, job created 23:51:16, started 23:51:18, completed 23:52:25. The job duration is 67 seconds; runner allocation takes 2 seconds. Thus the observed gaps originate before run creation, not in forecasting, dependency setup, runner queueing or the concurrency lock.
- Main's cron is correctly configured as 7,27,47 * * * * and already avoids the start of the hour. GitHub's documented scheduled-event delay/drop is consistent with this. GitHub's internal repository-specific cause remains unconfirmed. Missed questions are unknown.
- Rechecked current official Fall dates ($50k, Sep28-Jan06) and MiniBench listing ($1k). Resource-page body was not returned by search; the earlier same-day official rule audit above remains the latest complete rule read. No forecasting model, tournament or question-specific decision changed.

### Bounded remediation
- Prepare a standalone Google Apps Script watchdog: check every 10 minutes, dispatch existing main production workflow if its last creation is at least 20 minutes old, do not dispatch while production/test is active. Shared script lock and a pre-POST 20-minute cooldown prevent immediate duplicate/ambiguous retries.
- No Metaculus/OpenRouter secret is copied. Owner must create a repository-scoped Actions-write GitHub token and store it directly in Script Properties, then authorize/install the Google trigger. These owner-only steps are NOT performed by this change. External wake-up remains INACTIVE.
- Preserve native cron, existing 40-call UTC-day limit, free-only routing, duplicate forecast exclusion and shared Actions concurrency. Add offline scheduler tests to production CI and stop the production job if the repository becomes private.
- Do not keep an Actions runner alive with hours of idle sleep, endlessly self-chain runs, create paid services or claim a cron-minute change repairs GitHub scheduling. Existing short-lived benchmark runs remain the execution unit.
- Setup and rollback: operations/EXTERNAL_SCHEDULER.md. Verify at least 3 external launches and 4 hours of actual polling after owner activation; any 90-minute gap remains a coverage failure. Dispatch success alone is not forecast success.
- Local baseline: 20 Python tests passed, 1 SDK test skipped because SDK is only installed in Actions. Scheduler tests include the observed 183-minute gap, cooldown, concurrent runs, read-only setup, missing token, 401/429/transport errors, failed dispatch and malformed metadata. Current API 200 dispatch response and legacy 204 are both handled.
- New spending introduced: $0. Forecast accuracy/score/prize changes: none claimed. No new account, credential, paid option or external trigger was created. Owner work so far: no new operation; future one-time setup required.

- Independent code review found non-main manual runs were initially omitted from the active-run check despite shared concurrency. Added a failing regression, fixed the cross-branch active-run check, and all 12 scheduler tests now pass.
