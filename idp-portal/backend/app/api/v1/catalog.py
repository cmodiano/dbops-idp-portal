"""Catalog routes: public catalog access (Story 2.14, Story 3.1).

Provides read-only access to published actions.
Story 2.6, AC4: optional tag filter for catalogue.
Story 2.14: RBAC by action removed — access control now via profile permissions.
Story 3.1: RBAC filtering via cumulative_permissions, category filter, execution_count, cache.
"""

from __future__ import annotations

import re

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_optional_user
from app.models.auth import UserProfile
from app.models.catalog import ActionDetail, ActionStatus, ImpactLevel, normalize_tag_name
from app.repositories import catalog_repository

# Story 3.3: Validation pattern for environment parameter (alphanumeric + underscore only)
_ENVIRONMENT_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

router = APIRouter(prefix="/catalog", tags=["catalog"])

# Story 3.1 AC10: in-memory cache for catalog, TTL 5 min (300s)
# Story 3.3 AC9: cache key includes q, tags, category, engine, environment, impact (NFR4)
_catalog_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=1000, ttl=300)


def _get_cache_key(
    user_id: int | None,
    tags_filter: list[str] | None,
    q: str | None = None,
    engine: str | None = None,
    environment: str | None = None,
    impact: str | None = None,
) -> str:
    """Generate cache key for catalog query (Story 3.3: all params included)."""
    user_part = f"user_{user_id}" if user_id else "anon"
    tags_part = ",".join(sorted(tags_filter)) if tags_filter else "all"
    q_part = q.strip() if q and q.strip() else ""
    engine_part = engine or ""
    env_part = environment or ""
    impact_part = impact or ""
    return f"{user_part}_{tags_part}_q{q_part}_e{engine_part}_env{env_part}_i{impact_part}"


def _filter_by_rbac(
    actions: list[dict],
    cumulative_permissions: any,
) -> list[dict]:
    """Filter actions by user's RBAC permissions (Story 3.1 AC11)."""
    if cumulative_permissions is None:
        return actions

    actions_type = getattr(cumulative_permissions, "actions_type", "all")
    if actions_type == "all":
        return actions

    action_ids = set(getattr(cumulative_permissions, "action_ids", []) or [])
    tag_patterns = set(getattr(cumulative_permissions, "tag_patterns", []) or [])

    result = []
    for action in actions:
        # Check if action_id is in allowed list
        if action["id"] in action_ids:
            result.append(action)
            continue
        # Check if any tag matches pattern
        action_tags = set(action.get("tags", []))
        if action_tags & tag_patterns:
            result.append(action)
    return result


@router.get("/actions")
async def list_catalog_actions(
    tags: str | None = Query(None, description="Comma-separated tag names to filter by (AC4, NFR4)"),
    category: str | None = Query(None, description="Category filter (maps to tag: provisioning, patching, administration, monitoring)"),
    q: str | None = Query(None, description="Text search on name, description, tags (Story 3.3, AC9)"),
    engine: str | None = Query(None, description="Filter by engine (e.g. Oracle, SQL Server)"),
    environment: str | None = Query(None, description="Filter by environment (key in impact_rules, e.g. PROD, DEV)"),
    impact: str | None = Query(None, description="Filter by default impact level (low, medium, high)"),
    user: UserProfile | None = Depends(get_optional_user),
) -> dict:
    """List published actions in the catalog (Story 3.1, 3.3, AC1, AC3, AC6, AC9, AC10, AC11).

    - category: filter by category (maps to tag name, e.g. ?category=provisioning)
    - tags: filter by tags (e.g. ?tags=rac,dataguard)
    - q: text search on name, description, tags (debounce 300 ms recommended)
    - engine, environment, impact: additional filters (Story 3.3, AC9)
    - RBAC: if authenticated, filters by user's cumulative_permissions

    Returns:
        { "data": list[ActionWithExecutionCount] }
    """
    # Story 3.3: Validate environment parameter (security: prevent JSON path injection)
    if environment and not _ENVIRONMENT_PATTERN.match(environment):
        raise HTTPException(status_code=400, detail="Invalid environment parameter: alphanumeric and underscore only")

    # Story 3.3: Validate impact parameter against allowed values
    if impact:
        try:
            ImpactLevel(impact)
        except ValueError:
            valid_values = [level.value for level in ImpactLevel]
            raise HTTPException(status_code=400, detail=f"Invalid impact parameter: must be one of {valid_values}") from None

    # Combine category and tags filters
    tags_filter: list[str] | None = None
    if category:
        tags_filter = [normalize_tag_name(category)]
    if tags:
        extra_tags = [n for s in tags.split(",") if (n := normalize_tag_name(s.strip()))]
        if tags_filter:
            tags_filter.extend(extra_tags)
        else:
            tags_filter = extra_tags
    tags_filter = tags_filter or None

    # Check cache (Story 3.3: key includes all params)
    user_id = user.id if user else None
    cache_key = _get_cache_key(user_id, tags_filter, q=q, engine=engine, environment=environment, impact=impact)
    if cache_key in _catalog_cache:
        return {"data": _catalog_cache[cache_key]}

    # Fetch from repository
    actions = await catalog_repository.list_catalog(
        status=ActionStatus.PUBLISHED,
        tags_filter=tags_filter,
        q=q,
        engine=engine,
        environment=environment,
        impact=impact,
    )

    # Apply RBAC filtering if user is authenticated
    if user and user.cumulative_permissions:
        actions = _filter_by_rbac(actions, user.cumulative_permissions)

    # Cache result
    _catalog_cache[cache_key] = actions

    return {"data": actions}


@router.get("/tags")
async def list_catalog_tags(
    user: UserProfile | None = Depends(get_optional_user),
) -> dict:
    """List tags with action counts for published actions (Story 3.3, AC3, AC10).

    Returns tags that appear on published actions, with count per tag.
    RBAC: if authenticated, only tags from actions the user can see (same scope as list_catalog).

    Returns:
        { "data": list[{ "name": string, "action_count": number }] }
    """
    action_ids_filter: list[int] | None = None
    if user and user.cumulative_permissions:
        actions_type = getattr(user.cumulative_permissions, "actions_type", "all")
        if actions_type != "all":
            actions = await catalog_repository.list_catalog(status=ActionStatus.PUBLISHED)
            actions = _filter_by_rbac(actions, user.cumulative_permissions)
            action_ids_filter = [a["id"] for a in actions]

    tags = await catalog_repository.list_tags_with_counts(action_ids_filter=action_ids_filter)
    return {"data": tags}


def _check_rbac_for_action(action: ActionDetail, cumulative_permissions: any) -> bool:
    """Check if user has RBAC permission for a specific action (Story 3.2, AC6).

    Returns True if user has access, False otherwise.
    actions_type: "all" = access all, "list" = check action_ids, "pattern" = check tag_patterns.
    """
    if cumulative_permissions is None:
        return True

    actions_type = getattr(cumulative_permissions, "actions_type", "all")
    if actions_type == "all":
        return True

    action_ids = set(getattr(cumulative_permissions, "action_ids", []) or [])
    tag_patterns = set(getattr(cumulative_permissions, "tag_patterns", []) or [])

    # Check if action_id is in allowed list (for "list" type or combined)
    if action.id in action_ids:
        return True

    # Check if any tag matches pattern (for "pattern" type or combined)
    action_tags = set(action.tags or [])
    if action_tags & tag_patterns:
        return True

    return False


@router.get("/actions/{action_id}")
async def get_catalog_action_by_id(
    action_id: int,
    user: UserProfile | None = Depends(get_optional_user),
) -> dict:
    """Get a single published action by ID (Story 3.2, AC1, AC3, AC6).

    - Returns full ActionDetail for published actions only
    - RBAC: if authenticated, checks user's cumulative_permissions
    - Returns 404 if action not found, not published, or user lacks permission
    - Returns can_execute and allowed_environments for execution permission (AC3)

    Args:
        action_id: The action ID to fetch

    Returns:
        { "data": ActionDetail, "can_execute": bool, "allowed_environments": list[str] }
    """
    action = await catalog_repository.get_by_id(action_id)

    # 404 if not found or not published
    if action is None or action.status != ActionStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Action non trouvée")

    # RBAC check if user is authenticated
    if user and user.cumulative_permissions:
        if not _check_rbac_for_action(action, user.cumulative_permissions):
            raise HTTPException(status_code=404, detail="Action non trouvée")

    # Execution permission info (Story 3.2, AC3)
    allowed_environments: list[str] = []
    can_execute = False
    if user and user.cumulative_permissions:
        allowed_environments = getattr(user.cumulative_permissions, "environments", []) or []
        can_execute = len(allowed_environments) > 0

    return {
        "data": action,
        "can_execute": can_execute,
        "allowed_environments": allowed_environments,
    }
