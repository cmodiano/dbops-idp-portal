"""
Story 61.6 — Verification EXECUTION_SUBMITTED contexte
Verifie que les champs action_id, action_name, environment sont toujours presents
dans l'audit EXECUTION_SUBMITTED pour les 3 chemins de creation d'execution.
"""
import json

from django.test import TestCase

from core.models import AuditLog
from executions.dtos import ExecutionRequest
from executions.services import ExecutionService
from tests.factories import UserFactory, ActionFactory, ExecutionFactory


class TestExecutionSubmittedContext(TestCase):
    """AC1-5 : Verification du contexte EXECUTION_SUBMITTED pour les 3 chemins."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(status='published')
        self.service = ExecutionService()

    # ----------------------------------------------------------------
    # AC1 — Chemin API/UI minimal
    # ----------------------------------------------------------------
    def test_api_path_always_has_action_name_and_id(self):
        """AC1 : EXECUTION_SUBMITTED contient action_id, action_name, environment."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            source='api',
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertEqual(details['action_id'], self.action.id)
        self.assertEqual(details['action_name'], self.action.name)
        self.assertEqual(details['environment'], 'dev')
        self.assertEqual(details.get('source'), 'api')

    # ----------------------------------------------------------------
    # AC2 — Chemin Scheduled (simule source='celery_beat')
    # ----------------------------------------------------------------
    def test_scheduled_path_has_action_name_and_celery_source(self):
        """AC2 : source='celery_beat' -> action_id, action_name presents, pas de targets."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='prod',
            source='celery_beat',
            # pas de targets ni ip_address — comme scheduled.py
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertEqual(details['action_id'], self.action.id)
        self.assertEqual(details['action_name'], self.action.name)
        self.assertEqual(details['environment'], 'prod')
        self.assertEqual(details.get('source'), 'celery_beat')
        # targets absent pour les scheduled executions — comportement attendu
        self.assertNotIn('targets', details)

    # ----------------------------------------------------------------
    # AC3 — Chemin Container workflow child (sans source ni targets)
    # ----------------------------------------------------------------
    def test_child_execution_path_has_action_name_without_source_or_targets(self):
        """AC3 : child execution sans source ni targets -> action_id, action_name presents."""
        parent_execution = ExecutionFactory(user=self.user)
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            parent_execution_id=parent_execution.id,
            # pas de source, pas de targets, pas d'ip_address
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertEqual(details['action_id'], self.action.id)
        self.assertEqual(details['action_name'], self.action.name)
        self.assertEqual(details['environment'], 'dev')
        self.assertNotIn('targets', details)
        self.assertNotIn('source', details)

    # ----------------------------------------------------------------
    # AC4 — targets : conditionnel
    # ----------------------------------------------------------------
    def test_targets_present_when_provided(self):
        """AC4a : targets fournis -> cle 'targets' presente dans details."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            targets=['server-01', 'server-02'],
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertEqual(details['action_id'], self.action.id)
        self.assertEqual(details['action_name'], self.action.name)
        self.assertEqual(details['environment'], 'dev')
        self.assertIn('targets', details)
        self.assertEqual(details['targets'], ['server-01', 'server-02'])

    def test_targets_absent_when_not_provided(self):
        """AC4b : targets non fournis -> cle 'targets' absente de details."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertNotIn('targets', details)

    # ----------------------------------------------------------------
    # AC5 — parameters : conditionnel
    # ----------------------------------------------------------------
    def test_parameters_present_when_provided(self):
        """AC5 : parameters non vides fournis -> 'parameters' present dans details."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            parameters={'db_name': 'testdb', 'env': 'dev'},
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertIn('parameters', details)
        self.assertEqual(details['parameters']['db_name'], 'testdb')

    def test_parameters_absent_when_not_provided(self):
        """AC5b : parameters non fournis -> cle 'parameters' absente de details."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertNotIn('parameters', details)

    def test_parameters_sanitization_excludes_sensitive_keys(self):
        """AC5 'apres sanitisation' : cles sensibles exclues, cles valides presentes."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            parameters={'db_name': 'testdb', 'password': 'secret123', 'token': 'abc'},
        )
        execution = self.service.create_execution(req)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details) if isinstance(audit.details, str) else audit.details
        self.assertIn('parameters', details)
        self.assertEqual(details['parameters']['db_name'], 'testdb')
        self.assertNotIn('password', details['parameters'])
        self.assertNotIn('token', details['parameters'])
