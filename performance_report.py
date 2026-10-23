"""Read-only official results collection. Never generates or changes forecasts."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "https://www.metaculus.com/api/"
TARGETS = ("fall-futureeval-2026", "minibench")
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
    def __init__(self, token, get=None):
        self.token = token
        if get is None:
            import requests
            get = requests.get
        self.get = get
        self.calls = 0

    def read(self, path, params=None):
        self.calls += 1
        try:
            response = self.get(BASE + path, params=params,
                                headers={"Authorization": f"Token {self.token}"},
                                timeout=15)
            if response.status_code != 200:
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
                        "actual_close_time", "spot_scoring_time", "default_score_type"))
    forecasts = q.get("my_forecasts") or {}
    result["score_data"] = forecasts.get("score_data")
    # Only export the resolved question's own forecast; never live predictions.
    latest = forecasts.get("latest")
    result["last_forecast"] = select(latest, ("start_time", "end_time", "probability_yes",
                                              "probability_yes_per_category", "quartiles")) if latest else None
    history = forecasts.get("history")
    result["forecast_count"] = len(history) if isinstance(history, list) else None
    return result


def collect(token, get=None):
    client = Client(token, get)
    report = {"schema_version": 1, "started_at_utc": datetime.now(timezone.utc).isoformat(),
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
    for slug in TARGETS:
        project = {"requested_slug": slug, "status": "completed", "leaderboards": [],
                   "resolved_questions": [], "errors": []}
        report["projects"].append(project)
        try:
            info = client.read(f"projects/tournaments/{slug}/")
            project.update(select(info, ("id", "name", "slug", "start_date", "close_date")))
            if not isinstance(project["id"], int):
                raise ApiError("missing_project_id")
            boards = client.read(f"leaderboards/project/{project['id']}/")
            if not isinstance(boards, list):
                raise ApiError("invalid_leaderboard_schema")
            project["leaderboards"] = [board_summary(b, user_id) for b in boards]
            post_cache = {}
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
                        if qid and pid:
                            questions[qid] = pid
                except ApiError as exc:
                    board["contributions_status"] = "failed"
                    project["errors"].append({"stage": "contributions", "board_id": board["id"], "error": str(exc)})
            for qid, pid in questions.items():
                try:
                    if pid not in post_cache:
                        post_cache[pid] = client.read(f"posts/{pid}/")
                    question = resolved_question(post_cache[pid], qid)
                    question["post_id"] = pid
                    project["resolved_questions"].append(question)
                except ApiError as exc:
                    project["errors"].append({"stage": "resolved_question", "question_id": qid, "error": str(exc)})
        except ApiError as exc:
            project["errors"].append({"stage": "project_or_leaderboard", "error": str(exc)})
        if project["errors"]:
            project["status"] = "partial_or_failed"
            report["status"] = "partial_or_failed"
    report["api_get_calls"] = client.calls
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
            print("Official performance report is current for this day/resolution set.")
            return
    report = collect(os.environ["METACULUS_TOKEN"])
    report["resolution_signature"] = signature
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if report["run_id"]:
        history = path.parent / "history"
        history.mkdir(exist_ok=True)
        (history / f"{report['run_id']}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}.json").write_text(path.read_text())
    print("PERFORMANCE_RESULT=" + json.dumps(report, ensure_ascii=False))


def is_due(previous, signature, now):
    try:
        previous_time = datetime.fromisoformat(previous["started_at_utc"])
        jst = timezone(timedelta(hours=9))
        new_day = previous_time.astimezone(jst).date() != now.astimezone(jst).date()
        new_resolutions = previous.get("resolution_signature") != signature
        return new_day or (previous.get("status") == "completed" and new_resolutions)
    except (KeyError, TypeError, ValueError):
        return True


if __name__ == "__main__":
    main()
