"""
StepConditionEvaluator — ADR-007 §6

Évalue si un step doit être exécuté ou SKIPPED selon les conditions déclarées.
Aucun accès DB : l'objet execution est passé en paramètre.
"""

from executions.models import Execution


class StepConditionEvaluator:
    """Évalue si un step doit être exécuté ou SKIPPED (ADR-007 §6)."""

    def should_execute(self, step_config: dict, execution: Execution) -> bool:
        """
        Retourne True si le step doit être exécuté.
        Retourne False si le step doit être SKIPPED.

        Args:
            step_config: dict du step (depuis action.execution_steps)
            execution:   instance Execution avec .environment (str)
        """
        condition = step_config.get('condition')
        if not condition or not isinstance(condition, dict):
            return True

        env_list = condition.get('environment_in')
        if env_list is not None:
            if isinstance(env_list, str):
                env_list = [env_list]
            elif not isinstance(env_list, (list, tuple, set)):
                return True  # Invalid type → treat as no-op, execute step
            if env_list and execution.environment not in env_list:
                return False

        # Préparation pour `when:` (futur) — ignorer silencieusement
        return True
