"""
StepConditionEvaluator — ADR-007 §6

Évalue si un step doit être exécuté ou SKIPPED selon les conditions déclarées.
Aucun accès DB : l'objet execution est passé en paramètre.
"""


class StepConditionEvaluator:
    """Évalue si un step doit être exécuté ou SKIPPED (ADR-007 §6)."""

    def should_execute(self, step_config: dict, execution) -> bool:
        """
        Retourne True si le step doit être exécuté.
        Retourne False si le step doit être SKIPPED.

        Args:
            step_config: dict du step (depuis action.execution_steps)
            execution:   instance Execution avec .environment (str)
        """
        condition = step_config.get('condition')
        if not condition:
            return True

        env_list = condition.get('environment_in')
        if env_list is not None:
            if env_list and execution.environment not in env_list:
                return False

        # Préparation pour `when:` (futur) — ignorer silencieusement
        return True
