"""
Tests unitaires pour StepConditionEvaluator — Story 57.3

AC#1 : step SKIPPED si condition environment_in non remplie
AC#5 : step sans condition → should_execute() retourne True
AC#6 : step avec condition remplie → should_execute() retourne True
AC#7 : step SKIPPED sans step_id → pas d'entrée dans _step_outputs

Pas d'accès DB (StepConditionEvaluator est pur Python).
"""

from unittest.mock import MagicMock

from executions.step_handlers.condition_evaluator import StepConditionEvaluator


class TestStepConditionEvaluator:
    def setup_method(self):
        self.evaluator = StepConditionEvaluator()

    def _make_execution(self, environment: str):
        """Mock minimal d'un objet Execution avec .environment."""
        exec_mock = MagicMock()
        exec_mock.environment = environment
        return exec_mock

    # --- AC#5 : pas de condition → True ---

    def test_no_condition_returns_true(self):
        """AC#5 : step sans condition → should_execute() retourne True."""
        assert self.evaluator.should_execute({}, self._make_execution("lab")) is True

    def test_none_condition_returns_true(self):
        """Condition explicitement None → True."""
        step = {"condition": None}
        assert self.evaluator.should_execute(step, self._make_execution("lab")) is True

    def test_empty_condition_returns_true(self):
        """Condition vide {} → aucune règle → True."""
        assert self.evaluator.should_execute({"condition": {}}, self._make_execution("lab")) is True

    # --- AC#6 : condition remplie → True ---

    def test_environment_in_matching(self):
        """AC#6 : environment dans la liste → should_execute() retourne True."""
        step = {"condition": {"environment_in": ["production", "pre-production"]}}
        assert self.evaluator.should_execute(step, self._make_execution("production")) is True

    def test_environment_in_matching_second_element(self):
        """AC#6 : environment est le deuxième élément de la liste → True."""
        step = {"condition": {"environment_in": ["production", "pre-production"]}}
        assert self.evaluator.should_execute(step, self._make_execution("pre-production")) is True

    # --- AC#1 : condition non remplie → False (SKIP) ---

    def test_environment_in_not_matching(self):
        """AC#1 : environment non dans la liste → should_execute() retourne False."""
        step = {"condition": {"environment_in": ["production", "pre-production"]}}
        assert self.evaluator.should_execute(step, self._make_execution("lab")) is False

    def test_environment_in_single_value_not_matching(self):
        """Un seul environnement dans la liste, non correspondant → False."""
        step = {"condition": {"environment_in": ["production"]}}
        assert self.evaluator.should_execute(step, self._make_execution("dev")) is False

    # --- Liste vide : cas limite ---

    def test_environment_in_empty_list_returns_true(self):
        """Liste vide → condition non applicable → True (falsy guard)."""
        step = {"condition": {"environment_in": []}}
        assert self.evaluator.should_execute(step, self._make_execution("lab")) is True

    # --- Clés inconnues ignorées silencieusement ---

    def test_unknown_condition_key_ignored(self):
        """Clé inconnue ('when') → ignorée silencieusement → True."""
        step = {"condition": {"when": "some_expression"}}
        assert self.evaluator.should_execute(step, self._make_execution("lab")) is True

    def test_mixed_known_and_unknown_keys_not_matching(self):
        """Clé connue non remplie + clé inconnue → False (condition connue non remplie)."""
        step = {"condition": {"environment_in": ["production"], "when": "some_expression"}}
        assert self.evaluator.should_execute(step, self._make_execution("lab")) is False

    def test_mixed_known_and_unknown_keys_matching(self):
        """Clé connue remplie + clé inconnue → True."""
        step = {"condition": {"environment_in": ["production"], "when": "some_expression"}}
        assert self.evaluator.should_execute(step, self._make_execution("production")) is True
