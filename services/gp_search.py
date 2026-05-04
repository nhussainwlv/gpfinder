"""GP practice search service: CSV preprocessing, indexing, and ranked retrieval."""
import csv
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import requests
from config import ELASTICSEARCH_ENABLED, ELASTICSEARCH_INDEX, ELASTICSEARCH_URL

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
except Exception:  # pragma: no cover - optional dependency at runtime
    Elasticsearch = None
    bulk = None


# UK postcode pattern (simplified: outward + optional space + inward)
POSTCODE_RE = re.compile(
    r"^([A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2})$",
    re.IGNORECASE,
)
# Outcode only (e.g. B1, B16, WV1)
OUTCODE_RE = re.compile(
    r"^([A-Z]{1,2}[0-9][0-9A-Z]?)$",
    re.IGNORECASE,
)

RADIUS_MILES = 15.0
POSTCODES_IO_BASE = "https://api.postcodes.io"
TOKEN_RE = re.compile(r"[a-z0-9]+")

CSV_ID = 0
CSV_NAME = 1
CSV_ADDR_1 = 4
CSV_ADDR_2 = 5
CSV_TOWN = 7
CSV_POSTCODE = 9
CSV_STATUS = 12
CSV_PHONE = 17

_INDEX_CACHE: Dict[str, Any] = {}
_POSTCODE_COORD_CACHE: Dict[str, Tuple[float, float]] = {}
_ES_SYNC_CACHE: Dict[str, float] = {}
GP_POSITIVE_TERMS = (
    "SURGERY",
    "PRACTICE",
    "MEDICAL CENTRE",
    "HEALTH CENTRE",
    "FAMILY PRACTICE",
    "GP",
)
GP_NEGATIVE_TERMS = (
    "PCN",
    "HUB",
    "COMMUNITY SERVICE",
    "OOH",
    "OUT OF HOURS",
    "PHARMACY",
    "HOSPITAL",
    "URGENT CARE",
    "WALK IN",
    "DERMATOLOGY",
    "HOSPICE",
    "HMP",
)
SERVICE_KEYWORDS = {
    "Urgent appointments": ("URGENT", "WALK IN", "OOH", "OUT OF HOURS", "SAME DAY"),
    "Chronic disease reviews": ("DIABETES", "ASTHMA", "COPD", "HYPERTENSION", "LONG TERM"),
    "Women's health": ("WOMEN", "MATERNITY", "SMEAR", "CERVICAL", "CONTRACEPTION"),
    "Men's health": ("MEN", "PROSTATE"),
    "Mental health support": ("MENTAL", "PSYCH", "ADHD", "WELLBEING"),
    "Minor illness advice": ("MINOR", "INFECTION", "CLINIC"),
    "Medication reviews": ("PHARMACY", "PRESCRIB", "MEDIC"),
    "Vaccinations and immunisations": ("VACCIN", "IMMUN", "FLU"),
    "Care navigation and referrals": ("REFERRAL", "COMMUNITY", "HUB", "PCN"),
    "Online consultation support": ("DIGITAL", "ONLINE", "ACCESS"),
}
DEFAULT_CORE_GP_SERVICES = [
    "General GP consultations",
    "Repeat prescription management",
    "Sick notes and fit notes",
    "Referrals to specialist care",
]


def _normalise_postcode(raw: str) -> str:
    s = raw.strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s


def _normalise_search_term(raw: str) -> str:
    return raw.strip()


def _clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip())


def _safe_float(raw: str) -> Optional[float]:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _tokenise(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").lower())


def _format_postcode(raw: str) -> str:
    postcode = _normalise_postcode(raw).replace(" ", "")
    if len(postcode) > 3:
        return f"{postcode[:-3]} {postcode[-3:]}"
    return postcode


def _build_practice_from_row(row: List[str]) -> Optional[Dict[str, Any]]:
    if len(row) <= CSV_PHONE:
        return None

    status = _clean_text(row[CSV_STATUS]).upper()
    if status and status != "ACTIVE":
        return None

    name = _clean_text(row[CSV_NAME]).title()
    postcode = _format_postcode(row[CSV_POSTCODE])
    if not name or not postcode:
        return None

    address_line_1 = _clean_text(row[CSV_ADDR_1]).title()
    address_line_2 = _clean_text(row[CSV_ADDR_2]).title()
    address = ", ".join([p for p in [address_line_1, address_line_2] if p])
    town = _clean_text(row[CSV_TOWN]).title()
    phone = _clean_text(row[CSV_PHONE])

    is_core_gp = _is_core_gp_name(name)
    inferred_services = _infer_services(name, address, town, is_core_gp)
    appointment_info = _build_appointment_info(is_core_gp)
    opening_info = _build_opening_info()

    return {
        "id": _clean_text(row[CSV_ID]) or name,
        "organisation_code": _clean_text(row[CSV_ID]),
        "name": name,
        "address": address,
        "postcode": postcode,
        "town": town,
        "telephone": phone,
        "website": "",
        "rating": None,
        "rating_count": None,
        "latitude": None,
        "longitude": None,
        "is_core_gp": is_core_gp,
        "service_type": "GP practice" if is_core_gp else "Primary care service",
        "services": inferred_services,
        "patient_info": _build_patient_info(name, town, postcode, is_core_gp),
        "appointment_info": appointment_info,
        "opening_info": opening_info,
    }


def _is_core_gp_name(name: str) -> bool:
    name_upper = (name or "").upper()
    score = 0

    for term in GP_POSITIVE_TERMS:
        if term in name_upper:
            score += 2
    for term in GP_NEGATIVE_TERMS:
        if term in name_upper:
            score -= 2

    return score >= 1


def _infer_services(name: str, address: str, town: str, is_core_gp: bool) -> List[str]:
    corpus = f"{name} {address} {town}".upper()
    services: List[str] = []
    for service_name, keywords in SERVICE_KEYWORDS.items():
        if any(keyword in corpus for keyword in keywords):
            services.append(service_name)
    if is_core_gp:
        for item in DEFAULT_CORE_GP_SERVICES:
            if item not in services:
                services.append(item)
    return services[:6]


def _build_patient_info(name: str, town: str, postcode: str, is_core_gp: bool) -> str:
    area = town or postcode.split(" ")[0]
    if is_core_gp:
        return (
            f"{name} serves patients in and around {area}. "
            "Contact the practice for registration and appointment availability."
        )
    return (
        f"{name} supports patients in {area}. "
        "Contact the service directly for eligibility and booking details."
    )


def _build_appointment_info(is_core_gp: bool) -> Dict[str, Any]:
    return {
        "how_to_register": (
            "Register online or contact reception with proof of address and ID."
            if is_core_gp
            else "Contact this service directly to check referral or eligibility requirements."
        ),
        "urgent_booking": "Call the practice at opening time and request a same-day urgent appointment.",
        "online_consultation_available": bool(is_core_gp),
    }


def _build_opening_info() -> Dict[str, str]:
    tz = ZoneInfo("Europe/London")
    now = datetime.now(tz)
    weekday = now.weekday()  # 0 Monday
    opening_hour = 8
    opening_minute = 0
    closing_hour = 18
    closing_minute = 30

    if weekday >= 5:
        next_open = now + timedelta(days=(7 - weekday))
        next_open = next_open.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
        return {
            "is_open_now": False,
            "status_label": "Closed now",
            "next_opening": next_open.strftime("%A %H:%M"),
            "urgent_alternative": "For urgent care, contact NHS 111 or use your nearest urgent treatment centre.",
        }

    today_open = now.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
    today_close = now.replace(hour=closing_hour, minute=closing_minute, second=0, microsecond=0)
    if today_open <= now <= today_close:
        return {
            "is_open_now": True,
            "status_label": "Open now",
            "next_opening": f"Open until {today_close.strftime('%H:%M')}",
            "urgent_alternative": "If phone lines are busy, use NHS 111 online for urgent assessment.",
        }

    if now < today_open:
        next_open = today_open
    else:
        next_open = (now + timedelta(days=1)).replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)

    return {
        "is_open_now": False,
        "status_label": "Closed now",
        "next_opening": next_open.strftime("%A %H:%M"),
        "urgent_alternative": "For urgent care outside opening hours, contact NHS 111.",
    }


def _bulk_geocode_postcodes(postcodes: List[str]) -> Dict[str, Tuple[float, float]]:
    """Lookup postcodes in bulk via postcodes.io and cache successful coordinates."""
    normalised = []
    for raw in postcodes:
        norm = _format_postcode(raw)
        if not norm:
            continue
        if norm in _POSTCODE_COORD_CACHE:
            continue
        normalised.append(norm)
    if not normalised:
        return {}

    try:
        resp = requests.post(
            f"{POSTCODES_IO_BASE}/postcodes",
            json={"postcodes": normalised[:100]},
            timeout=7,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        for item in data.get("result", []):
            query = item.get("query")
            result = item.get("result") or {}
            if not query or not result:
                continue
            lat = result.get("latitude")
            lon = result.get("longitude")
            if lat is None or lon is None:
                continue
            _POSTCODE_COORD_CACHE[_format_postcode(query)] = (float(lat), float(lon))
    except Exception:
        return {}
    return {k: v for k, v in _POSTCODE_COORD_CACHE.items()}


def _travel_options(distance_miles: Optional[float], address: str, postcode: str) -> Dict[str, Any]:
    dest = ", ".join([x for x in [address, postcode] if x]).strip(", ")
    encoded_dest = requests.utils.quote(dest)
    options = {
        "driving": {"label": "Drive", "eta": "", "url": f"https://www.google.com/maps/dir/?api=1&destination={encoded_dest}&travelmode=driving"},
        "transit": {"label": "Public transport", "eta": "", "url": f"https://www.google.com/maps/dir/?api=1&destination={encoded_dest}&travelmode=transit"},
        "walking": {"label": "Walk", "eta": "", "url": f"https://www.google.com/maps/dir/?api=1&destination={encoded_dest}&travelmode=walking"},
    }
    if distance_miles is None:
        return options

    drive_min = max(5, round(distance_miles / 22 * 60))
    transit_min = max(10, round(distance_miles / 12 * 60))
    walk_min = max(8, round(distance_miles / 3 * 60))
    options["driving"]["eta"] = f"~{drive_min} min"
    options["transit"]["eta"] = f"~{transit_min} min"
    options["walking"]["eta"] = f"~{walk_min} min"
    return options


def _attach_distance_and_travel(results: List[Dict[str, Any]], center_lat: float, center_lon: float) -> List[Dict[str, Any]]:
    _bulk_geocode_postcodes([r.get("postcode", "") for r in results])
    enriched: List[Dict[str, Any]] = []
    for r in results:
        row = dict(r)
        coords = _POSTCODE_COORD_CACHE.get(_format_postcode(row.get("postcode", "")))
        distance: Optional[float] = None
        if coords:
            distance = round(_haversine_miles(center_lat, center_lon, coords[0], coords[1]), 1)
            row["distance_miles"] = distance
        row["travel_options"] = _travel_options(distance, row.get("address", ""), row.get("postcode", ""))
        enriched.append(row)

    enriched.sort(
        key=lambda x: (
            x.get("distance_miles") is None,
            x.get("distance_miles", 9999),
            -x.get("score", 0),
        )
    )
    return enriched


def _build_search_index(practices: List[Dict[str, Any]]) -> Dict[str, Any]:
    inverted: Dict[str, Set[int]] = {}
    outcode_map: Dict[str, Set[int]] = {}

    for idx, item in enumerate(practices):
        weighted_tokens: List[str] = []
        weighted_tokens.extend(_tokenise(item.get("name", "")) * 4)
        weighted_tokens.extend(_tokenise(item.get("town", "")) * 3)
        weighted_tokens.extend(_tokenise(item.get("postcode", "")) * 3)
        weighted_tokens.extend(_tokenise(item.get("address", "")) * 2)
        weighted_tokens.extend(_tokenise(item.get("telephone", "")))

        tf: Dict[str, int] = {}
        for token in weighted_tokens:
            tf[token] = tf.get(token, 0) + 1
            inverted.setdefault(token, set()).add(idx)

        item["term_frequency"] = tf
        outcode = (item.get("postcode", "").split(" ")[0] or "").upper()
        if outcode:
            outcode_map.setdefault(outcode, set()).add(idx)

    return {"inverted": inverted, "outcode_map": outcode_map}


def load_gp_data(data_path: Path) -> List[Dict[str, Any]]:
    """Load and preprocess GP practices from CSV file."""
    if not data_path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with open(data_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            practice = _build_practice_from_row(row)
            if practice:
                rows.append(practice)
    return rows


def _es_enabled() -> bool:
    env_toggle = os.environ.get("GPFINDER_ES_ENABLED")
    if env_toggle is not None:
        return env_toggle.strip().lower() == "true"
    return ELASTICSEARCH_ENABLED


def _es_url() -> str:
    return os.environ.get("GPFINDER_ES_URL", ELASTICSEARCH_URL).strip()


def _es_index() -> str:
    return os.environ.get("GPFINDER_ES_INDEX", ELASTICSEARCH_INDEX).strip() or "gpfinder-practices"


def _get_es_client() -> Optional[Any]:
    if not _es_enabled():
        return None
    if Elasticsearch is None:
        return None
    url = _es_url()
    if not url:
        return None
    try:
        client = Elasticsearch(url, request_timeout=10)
        if client.ping():
            return client
    except Exception:
        return None
    return None


def _es_source_doc(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id", ""),
        "organisation_code": item.get("organisation_code", ""),
        "name": item.get("name", ""),
        "address": item.get("address", ""),
        "postcode": item.get("postcode", ""),
        "town": item.get("town", ""),
        "telephone": item.get("telephone", ""),
        "website": item.get("website", ""),
        "rating": item.get("rating"),
        "rating_count": item.get("rating_count"),
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        "is_core_gp": bool(item.get("is_core_gp")),
        "service_type": item.get("service_type", ""),
        "services": item.get("services", []),
        "patient_info": item.get("patient_info", ""),
        "appointment_info": item.get("appointment_info", {}),
        "opening_info": item.get("opening_info", {}),
    }


def _sync_es_index(client: Any, data_path: Path) -> bool:
    if bulk is None:
        return False
    index_name = _es_index()
    mtime = data_path.stat().st_mtime if data_path.exists() else 0
    cache_key = f"{index_name}:{str(data_path.resolve())}"
    if _ES_SYNC_CACHE.get(cache_key) == mtime:
        return True

    practices = load_gp_data(data_path)
    if not practices:
        return False

    mapping = {
        "settings": {
            "analysis": {
                "normalizer": {
                    "lc_normalizer": {
                        "type": "custom",
                        "filter": ["lowercase"],
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "organisation_code": {"type": "keyword"},
                "name": {"type": "text"},
                "address": {"type": "text"},
                "postcode": {"type": "text", "fields": {"raw": {"type": "keyword", "normalizer": "lc_normalizer"}}},
                "town": {"type": "text", "fields": {"raw": {"type": "keyword", "normalizer": "lc_normalizer"}}},
                "telephone": {"type": "text"},
                "website": {"type": "keyword"},
                "is_core_gp": {"type": "boolean"},
                "service_type": {"type": "keyword"},
                "services": {"type": "text"},
                "patient_info": {"type": "text"},
                "appointment_info": {"type": "object", "enabled": True},
                "opening_info": {"type": "object", "enabled": True},
            }
        },
    }

    try:
        exists = client.indices.exists(index=index_name)
        if not exists:
            client.indices.create(index=index_name, body=mapping)
        else:
            client.indices.delete(index=index_name)
            client.indices.create(index=index_name, body=mapping)

        actions = [
            {
                "_index": index_name,
                "_id": p.get("id") or p.get("organisation_code") or str(i),
                "_source": _es_source_doc(p),
            }
            for i, p in enumerate(practices)
        ]
        bulk(client, actions, refresh=True)
        _ES_SYNC_CACHE[cache_key] = mtime
        return True
    except Exception:
        return False


def _es_search(client: Any, query: str, limit: int = 250) -> List[Dict[str, Any]]:
    index_name = _es_index()
    body = {
        "size": limit,
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["name^4", "town^3", "postcode^4", "address^2", "services^2", "patient_info"],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                        }
                    },
                    {"term": {"postcode.raw": query.lower()}},
                    {"term": {"town.raw": query.lower()}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    try:
        res = client.search(index=index_name, body=body)
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for hit in (res.get("hits", {}).get("hits", []) or []):
        src = dict(hit.get("_source") or {})
        src["score"] = round(float(hit.get("_score", 0.0)), 3)
        out.append(src)
    return out


def _load_indexed_data(data_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    cache_key = str(data_path.resolve())
    mtime = data_path.stat().st_mtime if data_path.exists() else 0
    cached = _INDEX_CACHE.get(cache_key)
    if cached and cached.get("mtime") == mtime:
        return cached["practices"], cached["index"]

    practices = load_gp_data(data_path)
    index = _build_search_index(practices)
    _INDEX_CACHE[cache_key] = {"mtime": mtime, "practices": practices, "index": index}
    return practices, index


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in miles between two (lat, lon) points."""
    R = 3959  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _geocode_postcode(query: str) -> Optional[Tuple[float, float]]:
    """Get (latitude, longitude) for a UK postcode using postcodes.io. Returns None on failure."""
    norm = _normalise_postcode(query)
    if not norm:
        return None
    # Try full postcode first, then outcode
    for url_suffix in [f"/postcodes/{requests.utils.quote(norm)}", f"/outcodes/{requests.utils.quote(norm)}"]:
        try:
            resp = requests.get(POSTCODES_IO_BASE + url_suffix, timeout=5)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get("status") != 200:
                continue
            result = data.get("result")
            if isinstance(result, dict):
                lat = result.get("latitude")
                lon = result.get("longitude")
                if lat is not None and lon is not None:
                    return (float(lat), float(lon))
        except Exception:
            continue
    return None


def search_by_postcode(practices: List[Dict], query: str) -> List[Dict]:
    """Filter practices by postcode (prefix or full match)."""
    norm = _normalise_postcode(query)
    if not norm:
        return []
    results = []
    for p in practices:
        pc = (p.get("postcode") or "").strip().upper()
        pc = re.sub(r"\s+", " ", pc)
        if norm in pc or pc.startswith(norm) or norm.startswith(pc):
            results.append(p)
    return results


def search_by_town(practices: List[Dict], query: str) -> List[Dict]:
    """Filter practices by town name (case-insensitive partial match)."""
    term = _normalise_search_term(query)
    if not term:
        return []
    term_lower = term.lower()
    return [p for p in practices if term_lower in (p.get("town") or "").lower()]


def _ranked_keyword_search(
    practices: List[Dict[str, Any]],
    index: Dict[str, Any],
    query: str,
) -> List[Dict[str, Any]]:
    tokens = _tokenise(query)
    if not tokens:
        return []

    candidates: Set[int] = set()
    for token in tokens:
        candidates |= index["inverted"].get(token, set())

    if not candidates:
        prefix = query.strip().lower()
        for idx, item in enumerate(practices):
            if (
                prefix in item.get("town", "").lower()
                or prefix in item.get("postcode", "").lower()
                or prefix in item.get("name", "").lower()
            ):
                candidates.add(idx)

    if not candidates:
        outcode = _normalise_postcode(query).split(" ")[0]
        if outcode:
            candidates |= index.get("outcode_map", {}).get(outcode, set())

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for idx in candidates:
        item = practices[idx]
        tf = item.get("term_frequency", {})
        score = 0.0
        for token in tokens:
            t_count = tf.get(token, 0)
            if not t_count:
                continue
            doc_freq = max(1, len(index["inverted"].get(token, [])))
            idf = math.log((1 + len(practices)) / (1 + doc_freq)) + 1
            score += t_count * idf
        if query.lower() in item.get("name", "").lower():
            score += 5.0
        if query.lower() in item.get("town", "").lower():
            score += 3.5
        if query.upper() in item.get("postcode", "").upper():
            score += 4.0
        score += 1.5 if item.get("is_core_gp") else -0.75
        ranked = dict(item)
        ranked["score"] = round(score, 3)
        scored.append((score, ranked))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [r for _, r in scored]


def _search_within_radius(
    practices: List[Dict],
    center_lat: float,
    center_lon: float,
    radius_miles: float,
) -> List[Dict]:
    """Return practices within radius_miles of (center_lat, center_lon), with distance_miles set."""
    out = []
    for p in practices:
        lat = p.get("latitude")
        lon = p.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            dist = _haversine_miles(center_lat, center_lon, float(lat), float(lon))
        except (TypeError, ValueError):
            continue
        if dist <= radius_miles:
            row = dict(p)
            row["distance_miles"] = round(dist, 1)
            out.append(row)
    out.sort(key=lambda x: x.get("distance_miles", 999))
    return out


def search_practices(
    data_path: Path,
    query: str,
    *,
    use_nhs_api: bool = False,
    nhs_api_base: str = "",
    nhs_api_key: str = "",
    radius_miles: float = RADIUS_MILES,
    strict_gp_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search GP practices by postcode or town.
    When the query is a valid UK postcode, returns all GPs within radius_miles (default 10).
    Otherwise uses town name or postcode prefix match.
    """
    query = (query or "").strip()
    if not query or len(query) > 50:
        return []

    if use_nhs_api and nhs_api_base and nhs_api_key:
        api_results = _search_nhs_ord(nhs_api_base, nhs_api_key, query)
        if api_results is not None:
            return api_results

    practices, index = _load_indexed_data(data_path)
    if not practices:
        return []

    norm_post = _normalise_postcode(query)
    is_likely_postcode = bool(POSTCODE_RE.match(norm_post) or OUTCODE_RE.match(norm_post))

    center_coords: Optional[Tuple[float, float]] = None

    es_results: List[Dict[str, Any]] = []
    es_client = _get_es_client()
    if es_client and _sync_es_index(es_client, data_path):
        es_results = _es_search(es_client, query)

    if is_likely_postcode:
        coords = _geocode_postcode(query)
        if coords is not None:
            center_coords = coords
            center_lat, center_lon = coords
            base_for_radius = es_results if es_results else practices
            results = _search_within_radius(base_for_radius, center_lat, center_lon, radius_miles)
            if results:
                if strict_gp_only:
                    core_only = [r for r in results if r.get("is_core_gp")]
                    if core_only:
                        results = core_only
                if center_coords is not None:
                    results = _attach_distance_and_travel(results, center_coords[0], center_coords[1])
                else:
                    for row in results:
                        row["travel_options"] = _travel_options(None, row.get("address", ""), row.get("postcode", ""))
                return results
        # Postcode fallback ranking
        results = es_results if es_results else _ranked_keyword_search(practices, index, query)
    else:
        results = es_results if es_results else _ranked_keyword_search(practices, index, query)

    if not results:
        if is_likely_postcode:
            results = search_by_town(practices, query)
        else:
            results = search_by_postcode(practices, query)

    if strict_gp_only:
        core_only = [r for r in results if r.get("is_core_gp")]
        if core_only:
            results = core_only

    if center_coords is not None:
        results = _attach_distance_and_travel(results, center_coords[0], center_coords[1])
    else:
        for row in results:
            row["travel_options"] = _travel_options(None, row.get("address", ""), row.get("postcode", ""))

    return results


def _search_nhs_ord(base_url: str, api_key: str, query: str) -> Optional[List[Dict]]:
    """
    Query NHS Organisation Data Service ORD API (when API key is available).
    Returns None on failure or missing config so caller falls back to local data.
    """
    try:
        url = f"{base_url.rstrip('/')}/organisations"
        params = {"PostCode": query.strip(), "Limit": 50}
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return _map_ord_to_practices(data)
    except Exception:
        return None


def _map_ord_to_practices(api_data: Any) -> List[Dict]:
    """Map NHS ORD API response to GPFinder practice format."""
    if isinstance(api_data, list):
        items = api_data
    elif isinstance(api_data, dict) and "Organisations" in api_data:
        items = api_data["Organisations"]
    elif isinstance(api_data, dict) and "entry" in api_data:
        items = [e.get("resource", e) for e in api_data["entry"]]
    else:
        items = []
    practices = []
    for o in items:
        if not isinstance(o, dict):
            continue
        addr = o.get("Address", o.get("address", []))
        if isinstance(addr, list) and addr:
            line1 = addr[0].get("Line1", addr[0].get("line1", ""))
            postcode = addr[0].get("PostCode", addr[0].get("postcode", ""))
        elif isinstance(addr, dict):
            line1 = addr.get("Line1", addr.get("line1", ""))
            postcode = addr.get("PostCode", addr.get("postcode", ""))
        else:
            line1 = ""
            postcode = ""
        practices.append({
            "id": o.get("OrgId", o.get("id", "")),
            "name": o.get("Name", o.get("name", "Unknown")),
            "address": line1,
            "postcode": postcode,
            "town": o.get("Town", o.get("town", "")),
            "telephone": o.get("Contact", [{}])[0].get("Value", "") if isinstance(o.get("Contact"), list) else o.get("Phone", ""),
            "website": o.get("Website", o.get("website", "") or ""),
            "rating": None,
            "rating_count": None,
        })
    return practices
