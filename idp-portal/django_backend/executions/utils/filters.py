"""
Module executions.utils.filters — Filtres, scope, parseurs date/int/datetime.

Responsabilité unique : parser les paramètres de requête et appliquer les filtres
avancés (scope, dates, action, moteur, tags, statut, environnement).
"""
from __future__ import annotations

from datetime import datetime, timedelta, date
from datetime import timezone as dt_timezone
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.request import Request

from catalog.models import Action
from core.exceptions import BadRequestError
from core.permissions import is_admin_user
from executions.utils.rbac_helpers import get_allowed_action_ids_for_user

# Fixed-offset UTC — Oracle Thin Mode ne supporte pas les named timezones (DPY-3022)
UTC = dt_timezone(timedelta(0))


def parse_int(value: str | None, default: int, *, name: str) -> int:
    """
    Parse integer query parameter with default value.
    Story 26.10: Renamed from _parse_int to respect Python convention (PEP 8).
    """
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide", details={name: value})


def parse_date(value: str | None, *, name: str) -> date | None:
    """
    Parse date string in YYYY-MM-DD format.
    Story 26.10: Renamed from _parse_date to respect Python convention (PEP 8).
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide (YYYY-MM-DD)", details={name: value})


def parse_iso_datetime(value: str | None, *, name: str) -> datetime | None:
    """
    Parse ISO 8601 datetime string with timezone handling.
    Story 26.10: Renamed from _parse_iso_datetime to respect Python convention (PEP 8).
    """
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        raise BadRequestError(
            code="BAD_REQUEST",
            message=f"{name} invalide (ISO 8601)",
            details={name: value},
        )
    if timezone.is_naive(dt):
        # Assume UTC if no timezone info
        dt = timezone.make_aware(dt, timezone=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def detect_request_source(request: Any) -> str:
    """
    Detect if request comes from UI (frontend) or API (standalone).
    Story 13.5, Subtask 3.2: Distinguish UI vs API requests for audit.
    Story 26.10: Renamed from _detect_request_source to respect Python convention (PEP 8).

    Heuristics:
    - If Authorization: Bearer is present → "api" (API clients always send it)
    - Else if X-Requested-With: XMLHttpRequest → "ui"
    - Else if Referer or Origin present → "ui" (browser navigation)
    - Otherwise → "api"
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.strip().upper().startswith('BEARER '):
        return 'api'

    x_requested_with = request.META.get('HTTP_X_REQUESTED_WITH', '')
    if x_requested_with.lower() == 'xmlhttprequest':
        return 'ui'

    referer = request.META.get('HTTP_REFERER', '')
    origin = request.META.get('HTTP_ORIGIN', '')
    if referer or origin:
        return 'ui'

    return 'api'


def apply_scope_filter(qs: QuerySet, *, user: Any, scope: str) -> tuple[QuerySet, str]:
    """
    Return (qs, effective_scope) applying RBAC-based scope filtering.

    - scope=mine → filter by user_id (inchangé)
    - scope=all + admin (DBA/DBOPS) → accès complet, pas de filtre
    - scope=all + non-admin → filtrer par les action IDs autorisés via RBAC
      - get_allowed_action_ids_for_user() retourne None → accès complet (actions_type='all')
      - retourne set() vide → liste vide (aucune permission)
      - retourne set d'IDs → filter(action_id__in=allowed_ids)
    - Pas de fallback silencieux scope=all → scope=mine (Story 36.1 AC6)

    Story 26.10: Renamed from _apply_scope_filter to respect Python convention (PEP 8).
    Story 36.1: RBAC-based filtering for non-admin users (AC2, AC3, AC6, AC7).
    """
    scope = (scope or "mine").lower()
    if scope not in ("mine", "all"):
        raise BadRequestError(code="BAD_REQUEST", message="scope invalide", details={"scope": scope})

    if scope == "mine":
        qs = qs.filter(user_id=user.id)
        return qs, "mine"

    # scope == "all" — use central permission helper so DBA/DBOPS via profile, profiles, or AD groups are recognized
    if is_admin_user(user):
        # Admins (DBA/DBOPS) voient tout — comportement actuel inchangé (AC3)
        return qs, "all"

    # Utilisateurs non-admin : filtrer par leurs action IDs autorisés via RBAC (AC2, AC6)
    allowed_ids = get_allowed_action_ids_for_user(user)
    if allowed_ids is None:
        # actions_type='all' dans les permissions → accès complet
        return qs, "all"
    # Set vide → aucune exécution visible (AC7)
    qs = qs.filter(action_id__in=allowed_ids)
    return qs, "all"


def apply_execution_filters(qs: QuerySet, *, request: Request) -> tuple[QuerySet, date | None, date | None]:
    """
    Apply advanced filters (Story 9.10) used by the frontend:
    start_date, end_date, action_id, engine, tags (AND), status, environment.
    Story 26.10: Renamed from _apply_execution_filters to respect Python convention (PEP 8).
    """
    start_date_s = request.query_params.get("start_date")
    end_date_s = request.query_params.get("end_date")
    start_d = parse_date(start_date_s, name="start_date")
    end_d = parse_date(end_date_s, name="end_date")

    if start_d:
        start_dt = timezone.make_aware(datetime.combine(start_d, datetime.min.time()))
        qs = qs.filter(created_at__gte=start_dt)
    if end_d:
        # inclusive end_date
        end_exclusive = timezone.make_aware(datetime.combine(end_d + timedelta(days=1), datetime.min.time()))
        qs = qs.filter(created_at__lt=end_exclusive)

    action_id = request.query_params.get("action_id")
    if action_id:
        qs = qs.filter(action_id=parse_int(action_id, 0, name="action_id"))

    engine = request.query_params.get("engine")
    if engine:
        qs = qs.filter(action__engine=engine)

    tags = request.query_params.get("tags")
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t and t.strip()]
        if tag_list:
            action_ids = Action.objects.search_by_tags(tag_list).values("id")
            qs = qs.filter(action_id__in=action_ids)

    status = request.query_params.get("status")
    if status:
        qs = qs.filter(status=status)

    environment = request.query_params.get("environment")
    if environment:
        qs = qs.filter(environment=environment)

    return qs, start_d, end_d
