"""
Tests for executions/utils/workflow_parsing.py.
Story 39.4 — Tâche 5.

Couvre les 4 fonctions :
- extract_workflow_referenced_action_ids
- extract_workflow_step_map
- validate_workflow_step_parameters
- validate_workflow_referenced_actions
"""
import pytest
from unittest.mock import MagicMock
from django.test import TestCase

from core.exceptions import BadRequestError, NotFoundError
from executions.utils.workflow_parsing import (
    extract_workflow_referenced_action_ids,
    extract_workflow_step_map,
    validate_workflow_step_parameters,
    validate_workflow_referenced_actions,
)
from tests.factories import UserFactory, ActionFactory
from core.models import AuditLog


# ============================================================================
# Helpers
# ============================================================================

def _make_action_mock(execution_steps):
    """Create a lightweight MagicMock Action with execution_steps set."""
    action = MagicMock()
    action.execution_steps = execution_steps
    action.id = 1
    action.name = 'Workflow Action'
    return action


# ============================================================================
# extract_workflow_referenced_action_ids
# ============================================================================

class TestExtractWorkflowReferencedActionIds(TestCase):

    # Tâche 5.1 — execution_steps non-liste → []
    def test_non_list_execution_steps_returns_empty(self):
        """5.1: execution_steps is not a list → []."""
        action = _make_action_mock(execution_steps="not a list")
        result = extract_workflow_referenced_action_ids(action)
        self.assertEqual(result, [])

    def test_none_execution_steps_returns_empty(self):
        """5.1b: execution_steps=None → []."""
        action = _make_action_mock(execution_steps=None)
        result = extract_workflow_referenced_action_ids(action)
        self.assertEqual(result, [])

    # Tâche 5.2 — step non-dict → ignoré
    def test_non_dict_step_is_skipped(self):
        """5.2: Step that is not a dict → skipped."""
        action = _make_action_mock(execution_steps=["string_step", 42, None])
        result = extract_workflow_referenced_action_ids(action)
        self.assertEqual(result, [])

    # Tâche 5.3 — step sans referenced_action_id → ignoré
    def test_step_without_referenced_action_id_is_skipped(self):
        """5.3: Step without referenced_action_id key → skipped."""
        action = _make_action_mock(execution_steps=[
            {"order": 1, "name": "Step 1"},  # no referenced_action_id
        ])
        result = extract_workflow_referenced_action_ids(action)
        self.assertEqual(result, [])

    # Tâche 5.4 — referenced_action_id non-convertible en int → log warning + skip
    def test_non_convertible_referenced_action_id_is_skipped(self):
        """5.4: Non-int-convertible referenced_action_id → warning logged + skipped."""
        action = _make_action_mock(execution_steps=[
            {"order": 1, "referenced_action_id": "not_an_int"},
            {"order": 2, "referenced_action_id": 5},
        ])
        result = extract_workflow_referenced_action_ids(action)
        self.assertEqual(result, [5])

    # Tâche 5.5 — avec clé order → tri respecté
    def test_order_key_respects_sorting(self):
        """5.5: Steps with 'order' key → sorted in ascending order."""
        action = _make_action_mock(execution_steps=[
            {"order": 3, "referenced_action_id": 30},
            {"order": 1, "referenced_action_id": 10},
            {"order": 2, "referenced_action_id": 20},
        ])
        result = extract_workflow_referenced_action_ids(action)
        self.assertEqual(result, [10, 20, 30])


# ============================================================================
# extract_workflow_step_map
# ============================================================================

class TestExtractWorkflowStepMap(TestCase):

    # Tâche 5.6 — execution_steps non-liste → {}
    def test_non_list_execution_steps_returns_empty_dict(self):
        """5.6: execution_steps not a list → {}."""
        action = _make_action_mock(execution_steps={"key": "value"})
        result = extract_workflow_step_map(action)
        self.assertEqual(result, {})

    # Tâche 5.7 — step non-dict ou clés manquantes → ignoré
    def test_non_dict_step_ignored(self):
        """5.7a: Non-dict step → ignored."""
        action = _make_action_mock(execution_steps=["string_step"])
        result = extract_workflow_step_map(action)
        self.assertEqual(result, {})

    def test_step_missing_referenced_action_id_ignored(self):
        """5.7b: Step without 'referenced_action_id' → KeyError caught, ignored."""
        action = _make_action_mock(execution_steps=[
            {"order": 1, "name": "step without ref_id"},
        ])
        result = extract_workflow_step_map(action)
        self.assertEqual(result, {})

    # Tâche 5.8 — steps valides → dict {order: ref_id}
    def test_valid_steps_returns_order_to_ref_id_map(self):
        """5.8: Valid steps → {order: referenced_action_id} dict."""
        action = _make_action_mock(execution_steps=[
            {"order": 1, "referenced_action_id": 10},
            {"order": 2, "referenced_action_id": 20},
        ])
        result = extract_workflow_step_map(action)
        self.assertEqual(result, {1: 10, 2: 20})


# ============================================================================
# validate_workflow_step_parameters
# ============================================================================

@pytest.mark.django_db
class TestValidateWorkflowStepParameters(TestCase):

    def setUp(self):
        self.user = UserFactory(username='wsp_tester')
        # Create a workflow action with 2 steps
        self.ref_action1 = ActionFactory(
            status='published',
            parameters_schema={
                "type": "object",
                "properties": {"db_name": {"type": "string"}},
                "required": ["db_name"],
            }
        )
        self.ref_action2 = ActionFactory(status='published', parameters_schema={})

        self.workflow_action = ActionFactory(
            status='published',
            execution_steps=[
                {"order": 1, "referenced_action_id": self.ref_action1.id},
                {"order": 2, "referenced_action_id": self.ref_action2.id},
            ]
        )

    # Tâche 5.9 — None → {}
    def test_none_parameters_returns_empty_dict(self):
        """5.9: None → {}."""
        result = validate_workflow_step_parameters(
            workflow_action=self.workflow_action,
            workflow_step_parameters=None,
        )
        self.assertEqual(result, {})

    # Tâche 5.10 — non-dict → BadRequestError(INVALID_WORKFLOW_STEP_PARAMETERS)
    def test_non_dict_raises_bad_request(self):
        """5.10: Non-dict → BadRequestError(INVALID_WORKFLOW_STEP_PARAMETERS)."""
        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=self.workflow_action,
                workflow_step_parameters="invalid",
            )
        self.assertEqual(ctx.exception.code, 'INVALID_WORKFLOW_STEP_PARAMETERS')

    # Tâche 5.11 — clé non-convertible en int → BadRequestError(INVALID_WORKFLOW_STEP_ORDER)
    def test_non_int_key_raises_invalid_step_order(self):
        """5.11: Key not convertible to int → BadRequestError(INVALID_WORKFLOW_STEP_ORDER)."""
        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=self.workflow_action,
                workflow_step_parameters={"not_an_int": {"parameters": {}}},
            )
        self.assertEqual(ctx.exception.code, 'INVALID_WORKFLOW_STEP_ORDER')

    # Tâche 5.12 — step_order inconnu → BadRequestError(INVALID_WORKFLOW_STEP_ORDER)
    def test_unknown_step_order_raises_invalid_step_order(self):
        """5.12: Unknown step_order → BadRequestError(INVALID_WORKFLOW_STEP_ORDER)."""
        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=self.workflow_action,
                workflow_step_parameters={"99": {"parameters": {}}},
            )
        self.assertEqual(ctx.exception.code, 'INVALID_WORKFLOW_STEP_ORDER')

    # Tâche 5.13 — action référencée introuvable → NotFoundError(REFERENCED_ACTION_NOT_FOUND)
    def test_missing_referenced_action_raises_not_found(self):
        """5.13: Referenced action not found → NotFoundError(REFERENCED_ACTION_NOT_FOUND)."""
        # Create workflow with a ref to non-existent action
        workflow = ActionFactory(
            status='published',
            execution_steps=[
                {"order": 1, "referenced_action_id": 99999999},
            ]
        )
        with self.assertRaises(NotFoundError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=workflow,
                workflow_step_parameters={"1": {"parameters": {}}},
            )
        self.assertEqual(ctx.exception.code, 'REFERENCED_ACTION_NOT_FOUND')

    # Tâche 5.13b — step value avec "parameters": None → traité comme {} (couverture ligne 139)
    def test_step_parameters_key_is_none_treated_as_empty(self):
        """5.13b: Step value with parameters=None → treated as {} (no error)."""
        # ref_action2 has no schema, so empty params are accepted
        result = validate_workflow_step_parameters(
            workflow_action=self.workflow_action,
            workflow_step_parameters={"2": {"parameters": None}},
        )
        self.assertEqual(result, {"2": {"name": "Étape 2", "parameters": {}}})

    # Tâche 5.13c — step value avec "parameters": valeur non-dict (ex: string) → BadRequestError
    def test_step_parameters_non_dict_raises_invalid_parameters(self):
        """5.13c: Step value with parameters=non-dict (not None) → BadRequestError(INVALID_PARAMETERS)."""
        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=self.workflow_action,
                workflow_step_parameters={"2": {"parameters": "invalid_string"}},
            )
        self.assertEqual(ctx.exception.code, 'INVALID_PARAMETERS')

    # Tâche 5.14 — pas de schema, params vides → accepté
    def test_no_schema_empty_params_accepted(self):
        """5.14: No schema, empty params → accepted (normalized empty dict)."""
        # ref_action2 has no schema (parameters_schema={})
        result = validate_workflow_step_parameters(
            workflow_action=self.workflow_action,
            workflow_step_parameters={"2": {"parameters": {}}},
        )
        self.assertEqual(result, {"2": {"name": "Étape 2", "parameters": {}}})

    # Tâche 5.15 — pas de schema, params non-vides → BadRequestError(INVALID_PARAMETERS)
    def test_no_schema_non_empty_params_raises_bad_request(self):
        """5.15: No schema, non-empty params → BadRequestError(INVALID_PARAMETERS)."""
        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=self.workflow_action,
                workflow_step_parameters={"2": {"parameters": {"extra_key": "val"}}},
            )
        self.assertEqual(ctx.exception.code, 'INVALID_PARAMETERS')

    # Tâche 5.16 — schema valide, params conformes → normalisé
    def test_valid_schema_valid_params_normalized(self):
        """5.16: Valid schema, conforming params → normalized dict returned."""
        result = validate_workflow_step_parameters(
            workflow_action=self.workflow_action,
            workflow_step_parameters={"1": {"parameters": {"db_name": "TESTDB"}}},
        )
        self.assertIn("1", result)
        self.assertEqual(result["1"]["parameters"]["db_name"], "TESTDB")

    # Tâche 5.17 — schema valide, params invalides → BadRequestError(INVALID_PARAMETERS)
    def test_valid_schema_invalid_params_raises_bad_request(self):
        """5.17: Valid schema, invalid params → BadRequestError(INVALID_PARAMETERS)."""
        # ref_action1 requires db_name (string), send integer
        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_step_parameters(
                workflow_action=self.workflow_action,
                workflow_step_parameters={"1": {"parameters": {"db_name": 12345}}},
            )
        self.assertEqual(ctx.exception.code, 'INVALID_PARAMETERS')


# ============================================================================
# validate_workflow_referenced_actions
# ============================================================================

@pytest.mark.django_db
class TestValidateWorkflowReferencedActions(TestCase):

    def setUp(self):
        self.user = UserFactory(username='wra_tester')

    # Tâche 5.18 — aucun step référencé → BadRequestError(WORKFLOW_EMPTY)
    def test_empty_workflow_raises_bad_request(self):
        """5.18: No referenced steps → BadRequestError(WORKFLOW_EMPTY)."""
        workflow = ActionFactory(status='published', execution_steps=[])

        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_referenced_actions(
                workflow_action=workflow,
                correlation_id=None,
                user_id=self.user.id,
                ip_address=None,
            )
        self.assertEqual(ctx.exception.code, 'WORKFLOW_EMPTY')

    # Tâche 5.19 — action manquante (1 seule) → NotFoundError(REFERENCED_ACTION_NOT_FOUND) + audit
    def test_single_missing_referenced_action_raises_not_found_with_audit(self):
        """5.19: 1 missing referenced action → NotFoundError + audit entry."""
        workflow = ActionFactory(
            status='published',
            execution_steps=[{"order": 1, "referenced_action_id": 99999999}]
        )

        with self.assertRaises(NotFoundError) as ctx:
            validate_workflow_referenced_actions(
                workflow_action=workflow,
                correlation_id='test-corr-1',
                user_id=self.user.id,
                ip_address='127.0.0.1',
            )
        self.assertEqual(ctx.exception.code, 'REFERENCED_ACTION_NOT_FOUND')

        # Audit should be created
        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=0,
        ).first()
        self.assertIsNotNone(audit)

    # Tâche 5.20 — plusieurs actions manquantes → message pluriel + audit
    def test_multiple_missing_referenced_actions_plural_message(self):
        """5.20: Multiple missing → plural message + audit."""
        workflow = ActionFactory(
            status='published',
            execution_steps=[
                {"order": 1, "referenced_action_id": 99999991},
                {"order": 2, "referenced_action_id": 99999992},
            ]
        )

        with self.assertRaises(NotFoundError) as ctx:
            validate_workflow_referenced_actions(
                workflow_action=workflow,
                correlation_id='test-corr-2',
                user_id=self.user.id,
                ip_address='127.0.0.1',
            )
        self.assertEqual(ctx.exception.code, 'REFERENCED_ACTION_NOT_FOUND')
        # Plural message contains "suivantes"
        self.assertIn("suivantes", ctx.exception.message)

    # Tâche 5.21 — action non publiée (1 seule) → BadRequestError(REFERENCED_ACTION_NOT_PUBLISHED) + audit
    def test_single_not_published_action_raises_bad_request_with_audit(self):
        """5.21: 1 not-published referenced action → BadRequestError + audit."""
        draft_action = ActionFactory(status='draft')
        workflow = ActionFactory(
            status='published',
            execution_steps=[{"order": 1, "referenced_action_id": draft_action.id}]
        )

        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_referenced_actions(
                workflow_action=workflow,
                correlation_id='test-corr-3',
                user_id=self.user.id,
                ip_address='127.0.0.1',
            )
        self.assertEqual(ctx.exception.code, 'REFERENCED_ACTION_NOT_PUBLISHED')

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=0,
        ).first()
        self.assertIsNotNone(audit)

    # Tâche 5.22 — plusieurs non publiées → message pluriel + audit
    def test_multiple_not_published_actions_plural_message(self):
        """5.22: Multiple not-published → plural message + audit."""
        draft1 = ActionFactory(status='draft', name='Draft Action A')
        draft2 = ActionFactory(status='draft', name='Draft Action B')
        workflow = ActionFactory(
            status='published',
            execution_steps=[
                {"order": 1, "referenced_action_id": draft1.id},
                {"order": 2, "referenced_action_id": draft2.id},
            ]
        )

        with self.assertRaises(BadRequestError) as ctx:
            validate_workflow_referenced_actions(
                workflow_action=workflow,
                correlation_id='test-corr-4',
                user_id=self.user.id,
                ip_address='127.0.0.1',
            )
        self.assertEqual(ctx.exception.code, 'REFERENCED_ACTION_NOT_PUBLISHED')
        # Plural form should mention "suivantes"
        self.assertIn("suivantes", ctx.exception.message)

    # Tâche 5.23 — toutes publiées → retourne liste d'IDs
    def test_all_published_returns_list_of_ids(self):
        """5.23: All referenced actions published → returns ordered list of IDs."""
        action_a = ActionFactory(status='published')
        action_b = ActionFactory(status='published')
        workflow = ActionFactory(
            status='published',
            execution_steps=[
                {"order": 1, "referenced_action_id": action_a.id},
                {"order": 2, "referenced_action_id": action_b.id},
            ]
        )

        result = validate_workflow_referenced_actions(
            workflow_action=workflow,
            correlation_id=None,
            user_id=self.user.id,
            ip_address=None,
        )
        self.assertIsInstance(result, list)
        self.assertIn(action_a.id, result)
        self.assertIn(action_b.id, result)
