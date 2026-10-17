import hmac
import logging
import os
from typing import Any, Dict

import requests
from flask import Blueprint, jsonify, request

from app.agent.prompt import build_prompt
from app.db.session import db_status
from app.services.models import (
    AllModelsUnavailable,
    complete,
    get_model_chain,
    is_free,
)

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)


def _authorized() -> bool:
    """Detailed diagnostics require HEALTH_TOKEN."""
    token = os.getenv("HEALTH_TOKEN", "").strip()
    if not token:
        return False
    provided = request.headers.get("X-Health-Token", "") or request.args.get("token", "")
    return bool(provided) and hmac.compare_digest(provided, token)


def _check_openrouter(detailed: bool) -> Dict[str, Any]:
    """Validate the API key without making a model request."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return {
            "configured": False,
            "reachable": False,
            "error": "OPENROUTER_API_KEY is not set",
        }

    base_url = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1").rstrip("/")
    try:
        response = requests.get(
            f"{base_url}/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
    except requests.RequestException as error:
        return {"configured": True, "reachable": False, "error": str(error)[:200]}

    if response.status_code == 401:
        return {
            "configured": True,
            "reachable": True,
            "key_valid": False,
            "error": "key rejected (401)",
        }

    if not response.ok:
        return {
            "configured": True,
            "reachable": True,
            "key_valid": False,
            "error": f"status {response.status_code}",
        }

    result: Dict[str, Any] = {
        "configured": True,
        "reachable": True,
        "key_valid": True,
    }
    if detailed:
        data = response.json().get("data", {})
        free_requests = data.get("free_model_daily_requests") or {}
        result["key_label"] = data.get("label")
        result["credit_limit"] = data.get("limit")
        result["credit_used"] = data.get("usage")
        result["expires_at"] = data.get("expires_at")
        result["free_requests_today"] = {
            "used": free_requests.get("used"),
            "limit": free_requests.get("limit"),
            "remaining": free_requests.get("remaining"),
        }
        if data.get("limit") is None:
            result["warning"] = "this key has no spending cap"

    return result


def _check_database(detailed: bool) -> Dict[str, Any]:
    status = db_status()
    if detailed:
        return status
    return {"backend": status["backend"], "connected": status.get("connected", False)}


@health_bp.get("/health")
def health():
    """Report service, OpenRouter, and database health."""
    detailed = _authorized()
    openrouter = _check_openrouter(detailed)

    chain = get_model_chain()
    models: Dict[str, Any] = {
        "chain_length": len(chain),
        "all_free": all(is_free(model) for model in chain),
    }
    if detailed:
        models["chain"] = chain
        models["paid_models"] = [model for model in chain if not is_free(model)]

    database = _check_database(detailed)
    payload: Dict[str, Any] = {
        "status": "ok",
        "service": "tri-buddy-agent",
        "openrouter": openrouter,
        "models": models,
        "database": database,
        "detail": "full" if detailed else "public",
    }

    if detailed and request.args.get("probe") == "model":
        try:
            result = complete(build_prompt(), "Reply with exactly: OK")
            payload["probe"] = {
                "ok": True,
                "answered_by": result["model"],
                "reply": result["content"][:80],
            }
        except AllModelsUnavailable as error:
            payload["probe"] = {
                "ok": False,
                "rate_limited": error.rate_limited,
                "failures": error.failures,
            }

    healthy = (
        openrouter.get("reachable")
        and openrouter.get("key_valid")
        and database.get("connected")
    )
    if not healthy:
        payload["status"] = "degraded"
    if request.args.get("strict") == "1" and not healthy:
        return jsonify(payload), 503

    return jsonify(payload), 200
