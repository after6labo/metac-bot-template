"""Read-only official results collection. Never generates or changes forecasts."""
import json
import os
import sys
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "https://www.metaculus.com/api/"
TARGETS = ("fall-futureeval-2026", "minibench")
SCHEMA_VERSION = 2
ENTRY_FIELDS = ("score", "rank", "coverage", "contribution_count", "calculated_on",
                "excluded", "exclusion_status", "prize", "ci_lower", "ci_upper")
BOARD_FIELDS = ("id", "project_id", "project_name", "project_slug", "name", "score_type",
                "is_primary_leaderboard", "finalized", "start_time", "end_time",
                "max_coverage", "prize_pool", "bot_exclusion_status")
CONTRIBUTION_FIELDS = ("question_id", "post_id", "question_title", "question_type",
                       "question_resolution", "score", "coverage", "question_weight")


def select(data, fields):
    return {key: data.get(key) for key in fields}


class ApiError(Exception):
    """Contains only a safe error category, never response bodies or credentials."""


class Client:
    def __init__(self, token, get=None, interval_seconds=3.2, sleep=time.sleep):
        self.token = token
        if get is None:
            import requests
            get = requests.get
        self.get = get
        self.calls = 0
        self.interval_seconds = interval_seconds
        self.sleep = sleep
        self.paused = False
        self.retry_not_before_utc = None

    def read(self, path, params=None):
        if self.paused:
            raise ApiError("http_429_paused")
        if self.calls:
            self.sleep(self.interval_seconds)
        self.calls += 1
        try:
            response = self.get(BASE + path, params=params,
                                headers={"Authorization": f"Token {self.token}"},
                                timeout=15)
            if response.status_code != 200:
                if response.status_code == 429:
                    self.paused = True
                    # Stop this collection; do not retry or continue through other endpoints.
                    retry = getattr(response, "headers", {}).get("Retry-After")
                    now = datetime.now(timezone.utc)
                    try:
                        resume = now + timedelta(seconds=max(0, float(retry)))
                    except (TypeError, ValueError):
                        try:
                            resume = parsedate_to_datetime(retry)
                        except (TypeError, ValueError):
                            resume = now + timedelta(minutes=5)
                    self.retry_not_before_utc = resume.isoformat()
                raise ApiError(f"http_{response.status_code}")
            return response.json()
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(type(exc).__name__) from None


def resolved_contributions(rows):
    return [select(row, CONTRIBUTION_FIELDS) for row in rows
            if row.get("question_resolution") not in (None, "", "annulled", "ambiguous")]


def board_summary(board, user_id):
    summary = select(board, BOARD_FIELDS)
    entries = board.get("entries", [])
    entry = next((e for e in entries if (e.get("user") or {}).get("id") == user_id), None)
    own = board.get("userEntry")
    if isinstance(own, dict) and (own.get("user") or {}).get("id") == user_id:
        entry = own
    summary["entry_status"] = "found" if entry else "not_listed"
    summary["own_entry"] = select(entry, ENTRY_FIELDS) if entry else None
    summary["listed_entry_count"] = len(entries)
    summary["ranked_entry_count"] = sum(e.get("rank") is not None for e in entries)
    summary["prize_payment_confirmed"] = None
    return summary


def resolved_question(post, question_id):
    questions = []
    if isinstance(post.get("question"), dict):
        questions.append(post["question"])
    questions += (post.get("group_of_questions") or {}).get("questions", [])
    questions += [v for v in (post.get("conditional") or {}).values()
                  if isinstance(v, dict) and "id" in v]
    q = next((q for q in questions if q.get("id") == question_id), None)
    if not q or q.get("status") != "resolved":
        return {"question_id": question_id, "status": "not_resolved_or_not_found"}
    result = select(q, ("id", "type", "resolution", "actual_resolve_time", "open_time",
                        "actual_close_time", "spot_scoring_time", "default_score_type", "scaling", "options"))
    forecasts = q.get("my_forecasts") or {}
    result["score_data"] = forecasts.get("score_data")
    # Only export the resolved question's own forecast; never live predictions.
    latest = forecasts.get("latest")
    result["last_forecast"] = select(latest, ("start_time", "end_time", "forecast_values",
                                              "interval_lower_bounds", "centers", "interval_upper_bounds")) if latest else None
    history = forecasts.get("history")
    result["forecast_count"] = len(history) if isinstance(history, list) else None
    return result


def resolved_posts(client, project_id, needed_post_ids):
    """Batch closed/resolved post details; stop once all contributed posts are found."""
    posts, offset, seen = {}, 0, set()
    while needed_post_ids - posts.keys():
        data = client.read("posts/", {"tournaments": project_id, "statuses": ["closed", "resolved"],
                                      "limit": 100, "offset": offset, "order_by": "-published_at"})
        rows = data.get("results") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise ApiError("invalid_posts_schema")
        ids = {p.get("id") for p in rows}
        if ids & seen or len(ids) != len(rows):
            raise ApiError("duplicate_posts_page")
        seen.update(ids)
        posts.update({p["id"]: p for p in rows if p.get("id") in needed_post_ids})
        offset += len(rows)
        if len(rows) < 100:
            break
    if needed_post_ids - posts.keys():
        raise ApiError("resolved_contribution_posts_missing")
    return posts


def collect(token, get=None, sleep=time.sleep):
    client = Client(token, get, sleep=sleep)
    report = {"schema_version": SCHEMA_VERSION, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "run_id": os.getenv("GITHUB_RUN_ID"), "status": "completed", "errors": [],
              "projects": [], "llm_calls": 0, "prize_payment_confirmed": None}
    try:
        me = client.read("users/me/")
        if not isinstance(me.get("id"), int):
            raise ApiError("missing_user_id")
        user_id = me["id"]
        report["bot"] = select(me, ("id", "username"))
    except ApiError as exc:
        report["errors"].append({"stage": "identity", "error": str(exc)})
        report["status"] = "failed"
        report["api_get_calls"] = client.calls
        return report
    targets = list(TARGETS)
    try:
        rounds = client.read("projects/minibenches/")
        if not isinstance(rounds, list):
            raise ApiError("invalid_minibenches_schema")
        # Include earlier rounds overlapping this experiment, not just the rolling alias.
        report["minibench_rounds"] = [select(p, ("id", "slug", "name", "start_date", "close_date"))
                                      for p in rounds if (p.get("close_date") or "") >= "2026-09-24"
                                      and (p.get("start_date") or "9999") <= report["started_at_utc"]]
        targets += [p["slug"] for p in report["minibench_rounds"] if p.get("slug") and p["slug"] not in targets]
    except ApiError as exc:
        report["errors"].append({"stage": "minibench_rounds", "error": str(exc)})
        report["status"] = "partial_or_failed"
    seen_projects = set()
    for slug in targets:
        project = {"requested_slug": slug, "status": "completed", "leaderboards": [],
                   "resolved_questions": [], "errors": []}
        report["projects"].append(project)
        try:
            info = client.read(f"projects/tournaments/{slug}/")
            project.update(select(info, ("id", "name", "slug", "start_date", "close_date")))
            if not isinstance(project["id"], int):
                raise ApiError("missing_project_id")
            if project["id"] in seen_projects:
                report["projects"].remove(project)
                continue
            seen_projects.add(project["id"])
            boards = client.read(f"leaderboards/project/{project['id']}/")
            if not isinstance(boards, list):
                raise ApiError("invalid_leaderboard_schema")
            project["leaderboards"] = [board_summary(b, user_id) for b in boards]
            questions = {}
            for board in project["leaderboards"]:
                params = {"for_user": user_id, "project": project["id"]}
                for key in ("score_type", "name", "start_time", "end_time"):
                    if board.get(key):
                        params[key] = board[key]
                try:
                    data = client.read("medals/contributions/", params)
                    if data.get("leaderboard", {}).get("id") != board["id"]:
                        raise ApiError("contribution_leaderboard_mismatch")
                    contributions = data.get("contributions")
                    if not isinstance(contributions, list):
                        raise ApiError("invalid_contributions_schema")
                    board["resolved_contributions"] = resolved_contributions(contributions)
                    board["unresolved_contribution_count"] = sum(
                        x.get("question_resolution") in (None, "") for x in contributions)
                    board["contributions_status"] = "completed"
                    for row in board["resolved_contributions"]:
                        qid, pid = row.get("question_id"), row.get("post_id")
                        if qid and pid and board["entry_status"] == "found" and row.get("coverage") != 0:
                            questions[qid] = pid
                except ApiError as exc:
                    board["contributions_status"] = "failed"
                    project["errors"].append({"stage": "contributions", "board_id": board["id"], "error": str(exc)})
            if questions:
                try:
                    post_cache = resolved_posts(client, project["id"], set(questions.values()))
                    for qid, pid in questions.items():
                        question = resolved_question(post_cache[pid], qid)
                        question["post_id"] = pid
                        project["resolved_questions"].append(question)
                except ApiError as exc:
                    project["errors"].append({"stage": "resolved_questions", "error": str(exc)})
        except ApiError as exc:
            project["errors"].append({"stage": "project_or_leaderboard", "error": str(exc)})
        if project["errors"]:
            project["status"] = "partial_or_failed"
            report["status"] = "partial_or_failed"
    report["api_get_calls"] = client.calls
    report["retry_not_before_utc"] = client.retry_not_before_utc
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    path = Path("run-results/performance/latest.json")
    forecast_path = Path("run-results/latest.json")
    signature = []
    if forecast_path.exists():
        data = json.loads(forecast_path.read_text())
        for audit in data.get("retrieval_audit", []):
            if isinstance(audit, dict):
                for question in audit.get("questions", []):
                    if question.get("status") == "resolved":
                        signature.append(question.get("question_id"))
    signature = sorted(x for x in set(signature) if isinstance(x, int))
    if "--if-due" in sys.argv and path.exists():
        previous = json.loads(path.read_text())
        now = datetime.now(timezone.utc)
        if not is_due(previous, signature, now):
            print("Performance collection not due or cooling down; consult stored status and timestamp.")
            return
    report = collect(os.environ["METACULUS_TOKEN"])
    report["resolution_signature"] = signature
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (path.parent / "README.md").write_text(render_markdown(report))
    if report["run_id"]:
        history = path.parent / "history"
        history.mkdir(exist_ok=True)
        (history / f"{report['run_id']}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}.json").write_text(path.read_text())
    print("PERFORMANCE_RESULT=" + json.dumps(report, ensure_ascii=False))


def is_due(previous, signature, now):
    if previous.get("retry_not_before_utc"):
        try:
            if now < datetime.fromisoformat(previous["retry_not_before_utc"]):
                return False
        except (TypeError, ValueError):
            return False
    # Older reports did not persist Retry-After. Wait at least five minutes after
    # a recorded 429 when upgrading them, rather than using schema change as a retry.
    if not previous.get("retry_not_before_utc"):
        errors = previous.get("errors", []) + [e for p in previous.get("projects", []) for e in p.get("errors", [])]
        if any(e.get("error", "").startswith("http_429") for e in errors):
            try:
                if now < datetime.fromisoformat(previous["started_at_utc"]) + timedelta(minutes=5):
                    return False
            except (KeyError, TypeError, ValueError):
                return False
    if previous.get("schema_version") != SCHEMA_VERSION:
        return True
    try:
        previous_time = datetime.fromisoformat(previous["started_at_utc"])
        jst = timezone(timedelta(hours=9))
        new_day = previous_time.astimezone(jst).date() != now.astimezone(jst).date()
        new_resolutions = previous.get("resolution_signature") != signature
        return new_day or (previous.get("status") == "completed" and new_resolutions)
    except (KeyError, TypeError, ValueError):
        return True


def render_markdown(report):
    def value(x):
        if x is None:
            return "未確認"
        return f"{x:.2f}" if isinstance(x, float) else str(x)
    lines = ["# 公式成績", "", f"取得開始（UTC）: {report['started_at_utc']}",
             f"取得状態: {report['status']}。順位・スコアは公式APIの値。暫定賞金は入金実績ではありません。", "",
             "| 大会 | 順位 | スコア | 採点寄与数 | 公式計算日時（UTC） |",
             "|---|---:|---:|---:|---|"]
    for project in report["projects"]:
        for board in project["leaderboards"]:
            entry = board.get("own_entry") or {}
            lines.append("| " + " | ".join([project.get("name") or project["requested_slug"],
                value(entry.get("rank")), value(entry.get("score")), value(entry.get("contribution_count")),
                value(entry.get("calculated_on"))]) + " |")
        if not project["leaderboards"]:
            lines.append(f"| {project['requested_slug']}（{project['status']}） | 未確認 | 未確認 | 未確認 | 未確認 |")
    lines += ["", "## 確定済み問題の公式採点", "", "| 大会 | 問題 | 結果 | 公式得点 |", "|---|---|---|---:|"]
    for project in report["projects"]:
        for board in project["leaderboards"]:
            for row in board.get("resolved_contributions", []):
                lines.append(f"| {project['requested_slug']} | [q{row['question_id']}](https://www.metaculus.com/questions/{row['post_id']}/) | {row['question_resolution']} | {value(row['score'])} |")
    lines += ["", "## 改善レビュー", "", "- 各問の公式得点・予測値・確定結果を照合し、失点の大きい問題から原因を調べる。",
              "- 少数の結果だけで予測値やプロンプトを最適化しない。改善案は解決済みの評価用データと別の検証用データで比較する。",
              "- 投稿漏れ・形式変換失敗は予測精度と分けて改善する。ライブ問題への手動調整はしない。",
              "- 新規モデル・有料検索は使用しない。この成績取得のLLM呼び出しは0回。", "",
              "詳細な取得障害・確定状況・賞金表示は [latest.json](latest.json)、過去の推移は [history](history) を参照。", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
