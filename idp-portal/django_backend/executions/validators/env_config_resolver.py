"""Résolution de la configuration d'environnement pour les exécutions."""
from __future__ import annotations

from typing import Any

from executions.utils import get_env_config_case_insensitive

import structlog

logger = structlog.get_logger(__name__)


class EnvironmentConfigResolver:
    """Résout la configuration d'environnement (impact_rules, env_config)."""

    @staticmethod
    def resolve(action: Any, environment: str | None, correlation_id: str) -> dict:
        """
        Resolve environment-specific config from action.

        Returns:
            Dict with: change_required, change_model_code, impact_level,
            requires_maintenance_window, requires_approval, env_str.
        """
        env_str: str = str(environment) if environment else ""

        # Impact level (from impact_rules)
        impact_rules = action.impact_rules or {}
        env_impact_config = get_env_config_case_insensitive(impact_rules, env_str)
        impact_level = (
            env_impact_config.get("impact_level")
            or env_impact_config.get("level")
            or action.default_impact_level
        )

        logger.info(
            "execution_environment_config",
            action_id=action.id,
            environment=environment,
            impact_level=impact_level,
            correlation_id=correlation_id,
        )

        return {
            'change_required': False,       # ADR-007: handled by service_call steps
            'change_model_code': None,      # ADR-007: handled by service_call steps
            'impact_level': impact_level,
            'requires_maintenance_window': False,  # ADR-007: handled by gate steps
            'requires_approval': False,     # ADR-007: handled by gate steps
            'env_str': env_str,
        }
