"""Vues remediation pour les exécutions.

Story 30.2: Endpoints remediation suggestions et context.
"""
from __future__ import annotations

import re

import structlog
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Action
from core.exceptions import NotFoundError
from core.middleware import get_correlation_id
from executions.models import Execution, ExecutionStatus
from executions.serializers import (
    RemediationSuggestionSerializer,
    RemediationContextSerializer,
)

logger = structlog.get_logger(__name__)


class ExecutionRemediationSuggestionsView(APIView):
    """GET /executions/{id}/remediation — Suggestions de remédiation basées sur l'erreur."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["executions"],
        summary="Suggestions de remédiation pour une exécution",
        responses={200: RemediationSuggestionSerializer(many=True)},
    )
    def get(self, request: Request, execution_id: int) -> Response:
        correlation_id = get_correlation_id()

        try:
            execution = Execution.objects.select_related("action").get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(
                code="EXECUTION_NOT_FOUND",
                message="Exécution non trouvée",
                details={"execution_id": execution_id},
            )

        remediation_rules = execution.action.remediation_rules
        if not remediation_rules:
            return Response({"data": []})

        error_message = execution.error_message
        if not error_message:
            return Response({"data": []})

        suggestions: list[dict] = []
        # Compile regex once to avoid hot path recompilation (HIGH-3 fix)
        compiled_patterns: dict[str, re.Pattern] = {}

        for rule in remediation_rules:
            # Filter by environment
            rule_envs = rule.get("environments") or []
            if rule_envs and execution.environment not in rule_envs:
                continue

            # Match error_pattern regex against error_message
            error_pattern = rule.get("error_pattern", "")
            if not error_pattern:
                continue

            # Cache compiled regex to avoid recompilation (HIGH-3 fix)
            if error_pattern not in compiled_patterns:
                try:
                    compiled_patterns[error_pattern] = re.compile(error_pattern)
                except re.error:
                    logger.warning(
                        "invalid_remediation_regex",
                        error_pattern=error_pattern,
                        action_id=execution.action_id,
                        correlation_id=correlation_id,
                    )
                    continue

            compiled = compiled_patterns[error_pattern]
            try:
                if not compiled.search(error_message):
                    continue
            except re.error:
                logger.warning(
                    "invalid_remediation_regex",
                    error_pattern=error_pattern,
                    action_id=execution.action_id,
                    correlation_id=correlation_id,
                )
                continue

            # Load target action
            target_action_id = rule.get("target_action_id")
            if not target_action_id:
                continue

            try:
                target_action = Action.objects.get(id=target_action_id)
            except Action.DoesNotExist:
                logger.warning(
                    "remediation_target_action_not_found",
                    target_action_id=target_action_id,
                    action_id=execution.action_id,
                    correlation_id=correlation_id,
                )
                continue

            suggestions.append(
                {
                    "action_id": target_action.id,
                    "action_name": target_action.name,
                    "action_description": target_action.description or "",
                    "matching_rule": {
                        "error_pattern": error_pattern,
                        "environments": rule_envs,
                        "risk_level": rule.get("risk_level", ""),
                        "auto_trigger": rule.get("auto_trigger", False),
                    },
                }
            )

        logger.info(
            "remediation_suggestions_fetched",
            execution_id=execution_id,
            suggestion_count=len(suggestions),
            correlation_id=correlation_id,
        )

        return Response({"data": suggestions})


class ExecutionRemediationContextView(APIView):
    """GET /executions/{id}/remediation-context — Contexte de remédiation d'une exécution."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["executions"],
        summary="Contexte de remédiation d'une exécution",
        responses={200: RemediationContextSerializer},
    )
    def get(self, request: Request, execution_id: int) -> Response:
        correlation_id = get_correlation_id()

        try:
            execution = Execution.objects.get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(
                code="EXECUTION_NOT_FOUND",
                message="Exécution non trouvée",
                details={"execution_id": execution_id},
            )

        # Child executions that are remediation type
        # Since there's no parent_item_type DB field, we filter by parent_execution
        # and check if the child was created as a remediation (all children of a failed exec)
        child_executions = Execution.objects.select_related("action").filter(
            parent_execution_id=execution.id,
        ).order_by("-created_at")

        has_remediation = child_executions.exists()
        successful_remediation = child_executions.filter(
            status=ExecutionStatus.COMPLETED,
        ).exists()

        remediation_actions = []
        for child in child_executions:
            remediation_actions.append(
                {
                    "id": child.id,
                    "action_id": child.action_id,
                    "action_name": child.action.name if child.action else None,
                    "status": child.status,
                    "created_at": child.created_at.isoformat() if child.created_at else None,
                    "completed_at": child.completed_at.isoformat() if child.completed_at else None,
                    "error_message": child.error_message,
                }
            )

        logger.info(
            "remediation_context_fetched",
            execution_id=execution_id,
            has_remediation=has_remediation,
            remediation_count=len(remediation_actions),
            correlation_id=correlation_id,
        )

        return Response(
            {
                "data": {
                    "has_remediation": has_remediation,
                    "successful_remediation": successful_remediation,
                    "remediation_actions": remediation_actions,
                }
            }
        )
