import hmac
import logging
import os
from typing import Any, Dict

from flask import Blueprint, jsonify, make_response, request

from app.services import slack
from app.tools.pr_review import format_for_slack, review

logger = logging.getLogger(__name__)

tasks_bp = Blueprint("tasks", __name__)


def dev_channel() -> str:
    return os.getenv("SLACK_DEV_CHANNEL", "byabosayee_devs").strip().lstrip("#")


def _authorized() -> bool:
    """Same admin token as the detailed health view. Fails closed when unset."""
    token = os.getenv("HEALTH_TOKEN", "").strip()
    if not token:
        return False
    provided = request.headers.get("X-Health-Token", "") or request.args.get("token", "")
    return bool(provided) and hmac.compare_digest(provided, token)


@tasks_bp.post("/tasks/pr-review")
def pr_review():
    """Review one pull request and post the result to the dev channel.

    The diff arrives in the request body rather than being fetched here, so this
    service never needs a GitHub token.
    """
    if not _authorized():
        return make_response("forbidden", 403)

    pr = request.get_json(silent=True) or {}
    if not pr.get("number"):
        return jsonify({"error": "missing PR number"}), 400

    result = review(pr)
    text = format_for_slack(pr, result)

    payload: Dict[str, Any] = {
        "pr": pr.get("number"),
        "reviewed": result.get("ok", False),
        "model": result.get("model"),
    }
    if not result.get("ok"):
        payload["review_error"] = result.get("error")

    if request.args.get("dry") == "1":
        payload["posted"] = False
        payload["preview"] = text
        return jsonify(payload), 200

    posted = slack.post_message(dev_channel(), text)
    payload["posted"] = bool(posted.get("ok"))
    if not posted.get("ok"):
        payload["slack_error"] = posted.get("error")
        logger.error("PR review could not be posted to #%s | error=%s",
                     dev_channel(), posted.get("error"))
    return jsonify(payload), 200
