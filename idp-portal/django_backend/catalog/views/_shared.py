"""
Utilitaires partagés entre les ViewSets du catalogue.

Responsabilité unique : fournir le cache TTL (per-worker) et les helpers
d'annotation/clé utilisés par ActionViewSet, CatalogActionViewSet et TagViewSet.
"""
from __future__ import annotations

from typing import Any

from cachetools import TTLCache
from django.db.models import Count, OuterRef, Subquery, IntegerField, Value, QuerySet
from django.db.models.functions import Coalesce

from catalog.models import Action
from executions.models import Execution


# Story 3.1 AC10: in-memory cache for catalog, TTL 5 min (300s)
# Story 30.6: Cache stores complete response dict {"data": [...], "pagination": {...}}
# Story 30.7 (RACE-3): Per-worker cache (not shared between Gunicorn workers).
# See docs/architecture/caching-strategy.md for rationale and limitations.
_catalog_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1000, ttl=300)

# Story 17.17: in-memory cache for catalog tags, TTL 5 min (300s)
# Story 30.7 (RACE-3): Per-worker cache — see docs/architecture/caching-strategy.md
_tags_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=200, ttl=300)


def _annotate_execution_count(queryset: QuerySet[Action]) -> QuerySet[Action]:
    """
    Annotate actions with execution_count without GROUP BY on CLOB columns (Oracle limitation).
    Uses a correlated subquery instead of Count() over a join.
    """
    subq = (
        Execution.objects.filter(action_id=OuterRef('pk'))
        .values('action_id')
        .annotate(c=Count('*'))
        .values('c')
    )
    return queryset.annotate(
        execution_count=Coalesce(Subquery(subq, output_field=IntegerField()), Value(0))
    )


def _get_cache_key(
    user_id: int | None,
    tags_filter: list[str] | None,
    q: str | None = None,
    engine: str | None = None,
    environment: str | None = None,
    impact: str | None = None,
    category: str | None = None,
    page: str | None = None,
    page_size: str | None = None,
) -> str:
    """Generate cache key for catalog query."""
    user_part = f"user_{user_id}" if user_id else "anon"
    tags_part = ",".join(sorted(tags_filter)) if tags_filter else "all"
    q_part = q.strip() if q and q.strip() else ""
    engine_part = engine or ""
    env_part = environment or ""
    impact_part = impact or ""
    category_part = category or ""
    page_part = page or "1"
    limit_part = page_size or "20"
    return f"{user_part}_{tags_part}_q{q_part}_e{engine_part}_env{env_part}_i{impact_part}_cat{category_part}:page_{page_part}:limit_{limit_part}"
