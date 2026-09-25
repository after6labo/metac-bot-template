# 定期起動の補助スケジュール

## 現在の状態

2026-09-25 13:23:50 JST: 本人操作で10分トリガーを設置（実行ログで報告済み）。
13:24:36 JSTのGAS手動起動からGitHub run 36094321091が起動し、13:25:49 JSTに正常終了。
初回の接続・起動・Bot実行・結果保存は確認済みです。
2026-09-25 17:29:18 JSTまでの4時間04分40秒を検証済みです。
手動初回を除く後続workflow_dispatch 8件と既存cron 1件は、すべて正常終了・結果保存を確認。
問題取得フェーズの開始間隔はおおむね30分、最大30分14.324秒でした。
直近開始17:17:11.584 JSTから確認時点までの空白12分06.416秒も最大間隔の計算に含めています。
60分超・90分以上の空白はなく、初期検証条件を満たしました。厳密な20分間隔や将来の完全捕捉は保証しません。
GASの管理画面・時間トリガーの実行ログは直接確認していません。本人の設置報告とGitHub側の反復実行が根拠です。
新規提出・失敗・LLM呼び出しはいずれも0、記録上の追加費用は0です（請求明細の確認ではありません）。
詳細な時刻・run ID・公式情報の確認結果は [EXPERIMENT_LOG.md](../EXPERIMENT_LOG.md) に記録しました。
初回設定のやり直しや追加の本人操作は不要です。

補助起動導入前に確認したGitHubの全11回の履歴では、定期実行の間隔は193分30秒・183分17秒でした。
当時の最新ジョブは作成2秒後に起動し約67秒で終了しており、Botの長時間処理ではありません。
cronは `7,27,47 * * * *` で正しく、既に毎時00分を避けています。
定期イベントの生成以前の遅延・欠落に整合しますが、GitHub内部の理由は確認できません。

## 対策

既存GoogleアカウントのApps Scriptから10分ごとにGitHubの起動状況を確認し、
本番Workflowの直近作成から20分以上経過した場合に `workflow_dispatch` で起動します。
本番・テストが実行中／待機中なら起動しません。POST前に20分の抑制期間を記録し、
通信結果が不明でも即時再送しません。既存cronも予備として残します。

- トークンは専用Script Propertiesにのみ保存。チャット、ソース、シートに貼りません。
- Metaculus/OpenRouterのキーは移さず、従来のGitHub Secretsを使用します。
- 1日40回のLLM上限、無料ルーター、二重提出除外、共有concurrencyは維持します。
- Google側の通常のチェックは1 GET、必要時だけ1 POST。最大目安216 HTTP呼び出し/日です。
- 公開リポジトリの標準ubuntu Runnerを使用。非公開化時は本番ジョブを停止する条件を追加しました。
- GASとGitHub Runnerの遅延は残ります。20分厳守・90分窓の完全捕捉を保証するものではありません。

## 本人が行う初回設定

1. GitHubの [Fine-grained personal access tokens](https://github.com/settings/personal-access-tokens/new) を開きます。
   - 名前: `metaculus-gas-scheduler`
   - Resource owner: `after6labo`
   - Expiration: 30 days（期限到来後は更新が必要）
   - Repository access: **Only select repositories** → `metac-bot-template` のみ
   - Repository permissions: **Actions: Read and write**。Metadataの自動Read以外は追加不要。
   - 発行した値は、下記Script Propertiesへ直接入力します。ボクには送らないでください。
2. [Google Apps Script](https://script.google.com/home/start) で専用プロジェクトを作り、
   名前を `Metaculus_起動補助` とします。既存のX投稿用スクリプトには混ぜません。
3. [github_scheduler.gs](github_scheduler.gs) の全文を `コード.gs`（または `Code.gs`）に貼り付け、保存します。
   Webアプリとしてのデプロイ・一般公開は不要です。
4. 左の歯車「プロジェクトの設定」→「スクリプト プロパティ」に次を追加します。
   - プロパティ: `GITHUB_ACTIONS_TOKEN`
   - 値: 手順1のトークン
5. エディタで `checkMetaculusScheduler` を選び実行し、本人のGoogleアカウントで初回認可します。
   これは履歴確認のみで、Botを起動しません。`would_dispatch` / `recent_run` / `active_run` が正常です。
   401/403の場合はトークン期限・対象リポジトリ・Actions権限を確認し、値は共有しないでください。
6. `installMetaculusScheduler` を1回実行します。10分トリガーを1つ作ります。
   もう一度実行しても、この専用関数のトリガーだけを置き換えます。
7. `metaculusSchedulerTick` を1回実行します。
   `dispatched` ならGitHubの [Actions](https://github.com/after6labo/metac-bot-template/actions/workflows/run_bot_on_tournament.yaml)
   に `workflow_dispatch` の実行が現れることを確認します。
   `recent_run` / `active_run` / `dispatch_cooldown` なら重複防止で起動を見送っています。

## 有効化後の検証と停止

設定終了を伝えてもらった後、AIがActionsとrun-results/historyを確認します。
初回手動実行を除く少なくとも3回の補助起動と、4時間分の実際の問題取得フェーズ開始時刻を計測します。
Actions履歴は対象期間を全件確認し、必要ならページングします。最大間隔には直近開始から確認時点までの空白も含めます。
run-results/history の started_at_utc は取得処理直前の時刻であり、GitHubでのrun作成時刻と区別します。
`workflow_dispatch` のHTTP成功だけでは「Botが正常終了した」と判定しません。
90分以上の問題確認間隔が残る場合は未解決として記録し、60分超は要調査とします。
問題がなければLLM呼び出し0のままであることも確認します。

停止はApps Scriptで `removeMetaculusScheduler` を実行。GitHub側の既存cronは残ります。
トークン失効・権限エラー時は自動更新せず停止し、GASの実行履歴で確認します。
他のGASプロジェクトのトリガー・既存APIキーには触れません。

## 公式根拠（2026-09-25確認）

- [GitHub scheduleの遅延・欠落](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [workflow_dispatch / Actions write権限 / 2026-03-10 API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
- [標準Runnerと公開リポジトリの料金](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Apps Scriptの10分トリガー](https://developers.google.com/apps-script/reference/script/clock-trigger-builder)
- [Apps Script無料アカウントの割り当て](https://developers.google.com/apps-script/guides/services/quotas)
- [GitHub Actions利用条件](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions)

単にcronの分を変更しても根本対策の根拠がありません。
Runnerを数時間sleepさせて常時占有する案、自己連鎖でジョブを増やす案、有料サービス追加は採用していません。
