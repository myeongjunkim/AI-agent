from __future__ import annotations

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import Optional
from datetime import timezone
from dateutil import parser as dateparser


_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k not in _TRACKING_PARAMS]
        normalized = parsed._replace(query=urlencode(query_pairs, doseq=True))
        # Normalize scheme/host casing
        netloc = normalized.netloc.lower()
        scheme = (normalized.scheme or "https").lower()
        normalized = normalized._replace(netloc=netloc, scheme=scheme)
        return urlunparse(normalized)
    except Exception:
        return url


def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def parse_date_to_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = dateparser.parse(value)
        if not dt:
            return None
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


