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
- Fall 2026 FutureEval open questions returned by the official client: 0
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
