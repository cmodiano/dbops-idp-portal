"""
Tests for Story 18.6: Integration error status (INTEGRATION_ERROR).

AC7: ExecutionStatus.INTEGRATION_ERROR can be persisted and serialized.
AC8: POST execution handles integration errors (placeholder).
AC4: error_message field is included in serializer output.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution, ExecutionStatus
from executions.serializers import ExecutionSerializer
from executions.services import ExecutionService
from core.models import AuditLog, AuditActionType


@pytest.mark.django_db
class TestExecutionStatusIntegrationError(TestCase):
    """AC7: ExecutionStatus.INTEGRATION_ERROR status tests."""

    def setUp(self):
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published',
        )

    def test_integration_error_status_value(self):
        """INTEGRATION_ERROR is a valid ExecutionStatus member."""
        assert ExecutionStatus.INTEGRATION_ERROR == 'INTEGRATION_ERROR'
        assert ExecutionStatus.INTEGRATION_ERROR.label == 'Integration Error'

    def test_create_execution_with_integration_error_status(self):
        """Story 18.6 AC7: INTEGRATION_ERROR status can be persisted."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.INTEGRATION_ERROR,
            error_message='AAP unreachable: Connection timeout after 30s',
        )

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.INTEGRATION_ERROR
        assert execution.error_message == 'AAP unreachable: Connection timeout after 30s'

    def test_serializer_includes_error_message(self):
        """Story 18.6 AC4: ExecutionSerializer includes error_message field."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.INTEGRATION_ERROR,
            error_message='ServiceNow API returned 500',
        )

        serializer = ExecutionSerializer(execution)
        data = serializer.data

        assert data['status'] == 'INTEGRATION_ERROR'
        assert data['error_message'] == 'ServiceNow API returned 500'

    def test_serializer_error_message_null_when_not_set(self):
        """error_message is null when execution has normal status."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        serializer = ExecutionSerializer(execution)
        data = serializer.data

        assert data['status'] == 'SUBMITTED'
        assert data['error_message'] is None

    def test_integration_error_is_terminal_state(self):
        """INTEGRATION_ERROR is a terminal state — no valid transitions out."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.INTEGRATION_ERROR,
        )

        service = ExecutionService()
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))

    def test_submitted_can_transition_to_integration_error(self):
        """SUBMITTED -> INTEGRATION_ERROR is a valid transition."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        service = ExecutionService()
        updated = service.update_status(execution.id, ExecutionStatus.INTEGRATION_ERROR, str(self.user.id))

        assert updated is not None
        assert updated.status == ExecutionStatus.INTEGRATION_ERROR


@pytest.mark.django_db
class TestExecutionIntegrationErrorAudit(TestCase):
    """AC4: AuditActionType.EXECUTION_INTEGRATION_ERROR audit tests."""

    def test_audit_type_exists(self):
        """EXECUTION_INTEGRATION_ERROR is a valid AuditActionType."""
        assert AuditActionType.EXECUTION_INTEGRATION_ERROR == 'EXECUTION_INTEGRATION_ERROR'

    def test_status_transition_creates_audit_entry(self):
        """Transitioning to INTEGRATION_ERROR creates audit trail."""
        user = User.objects.create(username='audituser', profile='DBA')
        action = Action.objects.create(
            name='Audit Test Action',
            engine='Oracle',
            platform='AAP',
            status='published',
        )
        execution = Execution.objects.create(
            action=action,
            user=user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        service = ExecutionService()
        service.update_status(execution.id, ExecutionStatus.INTEGRATION_ERROR, str(user.id))

        audit = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution.id,
            action_type=AuditActionType.EXECUTION_INTEGRATION_ERROR,
        ).first()
        assert audit is not None
