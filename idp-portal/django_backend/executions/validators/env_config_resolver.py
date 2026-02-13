"""Résolution de la configuration d'environnement pour les exécutions."""
from __future__ import annotations

from core.exceptions import BadRequestError
from executions.utils import _get_env_config_case_insensitive

import structlog

logger = structlog.get_logger(__name__)


class EnvironmentConfigResolver:
    """Résout la configuration d'environnement (change_type_config, impact_rules, env_config)."""

    @staticmethod
    def resolve(action, environment: str | None, correlation_id: str) -> dict:
        """
        Resolve environment-specific config from action.

        Returns:
            Dict with: change_required, change_model_code, impact_level,
            requires_maintenance_window, requires_approval, env_str.

        Raises:
            BadRequestError: If execution is not allowed for the environment.
        """
        change_type_config_raw = action.change_type_config
        if change_type_config_raw is None:
            change_type_config = {}
        elif not isinstance(change_type_config_raw, dict):
            logger.warning(
                "invalid_change_type_config_type_ignored",
                action_id=action.id,
                value_type=type(change_type_config_raw).__name__,
                correlation_id=correlation_id,
            )
            change_type_config = {}
        else:
            change_type_config = change_type_config_raw

        env_str: str = str(environment) if environment else ""
        env_change_config = _get_env_config_case_insensitive(change_type_config, env_str)
        change_required = env_change_config.get("required", False)
        change_model_code = env_change_config.get("change_model_code")

        # Story 25.4: allowed=false -> reject submission for this environment
        allowed = env_change_config.get("allowed", True)
        if allowed is False:
            raise BadRequestError(
                code="EXECUTION_NOT_ALLOWED_FOR_ENVIRONMENT",
                message=f"L'exécution de cette action n'est pas autorisée pour l'environnement {env_str}.",
                details={"environment": env_str, "action_id": action.id},
            )

        requires_maintenance_window = env_change_config.get("requires_maintenance_window", False)
        requires_approval = env_change_config.get("requires_approval", False)

        # Impact level
        impact_rules = action.impact_rules or {}
        env_impact_config = _get_env_config_case_insensitive(impact_rules, env_str)
        impact_level = env_impact_config.get("impact_level") or env_impact_config.get("level") or action.default_impact_level

        logger.info(
            "execution_environment_config",
            action_id=action.id,
            environment=environment,
            change_required=change_required,
            change_model_code=change_model_code,
            impact_level=impact_level,
            requires_maintenance_window=requires_maintenance_window,
            requires_approval=requires_approval,
            correlation_id=correlation_id,
        )

        return {
            'change_required': change_required,
            'change_model_code': change_model_code,
            'impact_level': impact_level,
            'requires_maintenance_window': requires_maintenance_window,
            'requires_approval': requires_approval,
            'env_str': env_str,
        }
