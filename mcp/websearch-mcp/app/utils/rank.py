from __future__ import annotations

from typing import List, Dict, Tuple
from ..providers.base import SearchItem
from ..config import settings
from .normalize import normalize_url


def deduplicate(items: List[SearchItem]) -> List[SearchItem]:
    seen = set()
    deduped: List[SearchItem] = []
    for it in items:
        key = normalize_url(it.get("url", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped


def _channel_order(channel: str) -> int:
    try:
        return settings.CHANNEL_PRIORITY.index(channel)
    except ValueError:
        return len(settings.CHANNEL_PRIORITY)


def score_item(it: SearchItem) -> float:
    base = settings.PROVIDER_WEIGHTS.get(it.get("provider", ""), 0.5)
    # 최신 항목 가산: published_at 존재만으로 미세 가중치
    freshness = 0.1 if it.get("published_at") else 0.0
    channel_bias = 1.0 - 0.05 * _channel_order(it.get("channel", "web"))
    return max(0.0, base * channel_bias + freshness)


def sort_items(items: List[SearchItem]) -> List[SearchItem]:
    return sorted(
        items,
        key=lambda it: (
            _channel_order(it.get("channel", "web")),
            -(1 if it.get("published_at") else 0),
            -score_item(it),
        ),
    )


