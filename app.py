"""
GPFinder - Flask application.
by Naeem Hussain | 2365963
Search for GP practices in England by postcode or town.
"""
import json
import os
import re
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import (
    CACHE_DEFAULT_TIMEOUT,
    CACHE_TYPE,
    DATA_GP_CSV,
    DATA_FEEDBACK_JSONL,
    NHS_ORD_API_BASE,
    NHS_ORD_API_KEY,
    RATELIMIT_DEFAULT,
    RATELIMIT_STORAGE_URI,
)
from services.gp_search import search_practices

app = Flask(__name__)
app.config.from_object("config")

cache = Cache(app, config={
    "CACHE_TYPE": CACHE_TYPE,
    "CACHE_DEFAULT_TIMEOUT": CACHE_DEFAULT_TIMEOUT,
})

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[RATELIMIT_DEFAULT],
    storage_uri=RATELIMIT_STORAGE_URI,
)

# Input validation: allow letters, numbers, spaces, hyphens; max length 50
SEARCH_PATTERN = re.compile(r"^[A-Za-z0-9\s\-]{1,50}$")


def validate_search_query(q: str) -> tuple[bool, str]:
    """Validate search input. Returns (ok, sanitised_or_error_message)."""
    if not q or not isinstance(q, str):
        return False, "Please enter a postcode or town name."
    q = q.strip()
    if len(q) < 2:
        return False, "Please enter at least 2 characters."
    if len(q) > 50:
        return False, "Search term is too long."
    if not SEARCH_PATTERN.match(q):
        return False, "Invalid characters. Use only letters, numbers, spaces and hyphens."
    return True, q


@app.route("/")
def index():
    """Serve the main search page."""
    return render_template("index.html")


def _parse_radius(radius_param: str) -> float:
    """Parse and validate radius (miles). Allowed 5–50, default 15."""
    try:
        r = float(radius_param)
        if 5 <= r <= 50:
            return r
    except (TypeError, ValueError):
        pass
    return 15.0


def _do_search(sanitised_query: str, radius_miles: float = 15.0) -> list:
    """Perform search (cached per query + radius)."""
    use_nhs = bool(NHS_ORD_API_KEY)
    return search_practices(
        DATA_GP_CSV,
        sanitised_query,
        use_nhs_api=use_nhs,
        nhs_api_base=NHS_ORD_API_BASE,
        nhs_api_key=NHS_ORD_API_KEY,
        radius_miles=radius_miles,
        strict_gp_only=True,
    )


@app.route("/api/search")
@limiter.limit("30 per minute")
def api_search():
    """
    Search GP practices by postcode or town.
    Query params: q (required), radius (optional, 5–50 miles, default 15)
    """
    q = request.args.get("q", "")
    ok, value = validate_search_query(q)
    if not ok:
        return jsonify({"error": value, "results": []}), 400

    radius = _parse_radius(request.args.get("radius", "15"))
    scope = request.args.get("scope", "core").strip().lower()
    strict_gp_only = scope != "all"
    cache_key = f"search:{value.strip().lower()}:{radius}:{scope}"
    results = cache.get(cache_key)
    if results is None:
        use_nhs = bool(NHS_ORD_API_KEY)
        results = search_practices(
            DATA_GP_CSV,
            value,
            use_nhs_api=use_nhs,
            nhs_api_base=NHS_ORD_API_BASE,
            nhs_api_key=NHS_ORD_API_KEY,
            radius_miles=radius,
            strict_gp_only=strict_gp_only,
        )
        cache.set(cache_key, results, timeout=CACHE_DEFAULT_TIMEOUT)
    return jsonify({"results": results, "query": value, "scope": scope})


@app.errorhandler(429)
def ratelimit_handler(e):
    """Return JSON for rate limit exceeded."""
    return jsonify({"error": "Too many requests. Please try again later.", "results": []}), 429


@app.route("/api/feedback", methods=["POST"])
@limiter.limit("40 per minute")
def api_feedback():
    """Capture lightweight user feedback for search quality improvements."""
    payload = request.get_json(silent=True) or {}
    feedback_type = (payload.get("type") or "").strip().lower()
    if feedback_type not in {"useful", "incorrect", "rating"}:
        return jsonify({"ok": False, "error": "Invalid feedback type."}), 400

    rating = payload.get("rating")
    if feedback_type == "rating":
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Rating must be an integer between 1 and 5."}), 400
        if rating < 1 or rating > 5:
            return jsonify({"ok": False, "error": "Rating must be between 1 and 5."}), 400

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "query": (payload.get("query") or "").strip()[:80],
        "practice_id": (payload.get("practice_id") or "").strip()[:40],
        "practice_name": (payload.get("practice_name") or "").strip()[:160],
        "type": feedback_type,
        "rating": rating if feedback_type == "rating" else None,
        "message": (payload.get("message") or "").strip()[:500],
        "language": (payload.get("language") or "en").strip()[:10],
        "scope": (payload.get("scope") or "core").strip()[:10],
    }

    try:
        DATA_FEEDBACK_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_FEEDBACK_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return jsonify({"ok": False, "error": "Could not save feedback."}), 500

    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", app.config.get("PORT", 5001)))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
