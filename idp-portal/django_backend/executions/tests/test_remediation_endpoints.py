"""Tests for remediation endpoints (Story 30.2, AC5).

Tests for:
- GET /executions/{id}/remediation — suggestions de remédiation
- GET /executions/{id}/remediation-context — contexte de remédiation
"""
import json
import pytest
from rest_framework.test import APIClient

from executions.models import ExecutionStatus
from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory


@pytest.mark.django_db
class TestRemediationSuggestions:
    """GET /executions/{id}/remediation — AC1, AC5."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile="DBA", username="test_user_rem")
        self.integration = IntegrationFactory.create(type="aap", name="Test AAP Rem")
        self.client.force_authenticate(user=self.user)

    def _url(self, execution_id: int) -> str:
        return f"/api/v1/executions/{execution_id}/remediation"

    def test_matching_rule_returns_suggestion(self):
        """Exécution avec règle matchante → suggestion retournée."""
        target_action = ActionFactory.create(
            name="Fix ORA-01555",
            description="Action corrective pour ORA-01555",
            status="published",
            integration=self.integration,
        )
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-01555",
                    "target_action_id": target_action.id,
                    "environments": ["dev", "staging", "prod"],
                    "auto_trigger": False,
                    "risk_level": "low",
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            error_message="ORA-01555: snapshot too old",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["action_id"] == target_action.id
        assert data[0]["action_name"] == "Fix ORA-01555"
        assert data[0]["action_description"] == "Action corrective pour ORA-01555"
        assert data[0]["matching_rule"]["error_pattern"] == "ORA-01555"

    def test_non_matching_regex_returns_empty(self):
        """Règle non matchante (regex ne matche pas) → {"data": []}."""
        target_action = ActionFactory.create(
            name="Fix Action",
            status="published",
            integration=self.integration,
        )
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-00001",
                    "target_action_id": target_action.id,
                    "environments": ["dev"],
                    "auto_trigger": False,
                    "risk_level": "low",
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            error_message="ORA-01555: completely different error",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_environment_mismatch_filters_rule(self):
        """Environnement non inclus dans rule.environments → pas de suggestion."""
        target_action = ActionFactory.create(
            name="Fix Action",
            status="published",
            integration=self.integration,
        )
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-01555",
                    "target_action_id": target_action.id,
                    "environments": ["prod"],  # Only prod
                    "auto_trigger": False,
                    "risk_level": "low",
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",  # dev != prod
            error_message="ORA-01555: snapshot too old",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_null_error_message_returns_empty(self):
        """error_message=None → {"data": []}."""
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-01555",
                    "target_action_id": 1,
                    "environments": ["dev"],
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            error_message=None,
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_null_remediation_rules_returns_empty(self):
        """remediation_rules=None → {"data": []}."""
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=None,
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            error_message="ORA-01555: some error",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_nonexistent_execution_returns_404(self):
        """Exécution inexistante → HTTP 404."""
        response = self.client.get(self._url(999999))

        assert response.status_code == 404

    def test_unauthenticated_returns_401(self):
        """Utilisateur non authentifié → HTTP 401."""
        self.client.force_authenticate(user=None)

        response = self.client.get(self._url(1))

        assert response.status_code == 401


@pytest.mark.django_db
class TestRemediationContext:
    """GET /executions/{id}/remediation-context — AC2, AC5."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile="DBA", username="test_user_ctx")
        self.integration = IntegrationFactory.create(type="aap", name="Test AAP Ctx")
        self.client.force_authenticate(user=self.user)

    def _url(self, execution_id: int) -> str:
        return f"/api/v1/executions/{execution_id}/remediation-context"

    def test_with_child_executions_returns_has_remediation_true(self):
        """Exécution avec 2 child executions → has_remediation=true, 2 éléments."""
        action = ActionFactory.create(status="published", integration=self.integration)
        parent = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )
        ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
            parent_execution=parent,
        )
        ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            parent_execution=parent,
        )

        response = self.client.get(self._url(parent.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_remediation"] is True
        assert len(data["remediation_actions"]) == 2

    def test_child_execution_completed_returns_successful_true(self):
        """Child execution COMPLETED → successful_remediation=true."""
        action = ActionFactory.create(status="published", integration=self.integration)
        parent = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )
        ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.COMPLETED,
            environment="dev",
            parent_execution=parent,
        )

        response = self.client.get(self._url(parent.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_remediation"] is True
        assert data["successful_remediation"] is True

    def test_child_execution_failed_returns_successful_false(self):
        """Child execution FAILED → successful_remediation=false."""
        action = ActionFactory.create(status="published", integration=self.integration)
        parent = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )
        ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            parent_execution=parent,
        )

        response = self.client.get(self._url(parent.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_remediation"] is True
        assert data["successful_remediation"] is False

    def test_no_child_executions_returns_has_remediation_false(self):
        """Aucun child execution → has_remediation=false."""
        action = ActionFactory.create(status="published", integration=self.integration)
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_remediation"] is False
        assert data["successful_remediation"] is False
        assert data["remediation_actions"] == []

    def test_nonexistent_execution_returns_404(self):
        """Exécution inexistante → HTTP 404."""
        response = self.client.get(self._url(999999))

        assert response.status_code == 404

    def test_unauthenticated_returns_401(self):
        """Utilisateur non authentifié → HTTP 401."""
        self.client.force_authenticate(user=None)

        response = self.client.get(self._url(1))

        assert response.status_code == 401

    def test_remediation_action_fields(self):
        """Vérifier que chaque remediation_action contient tous les champs requis."""
        action = ActionFactory.create(
            name="Test Action Fields",
            status="published",
            integration=self.integration,
        )
        parent = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )
        ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.COMPLETED,
            environment="dev",
            parent_execution=parent,
            error_message="Some error",
        )

        response = self.client.get(self._url(parent.id))

        assert response.status_code == 200
        ra = response.json()["data"]["remediation_actions"][0]
        assert "id" in ra
        assert "action_id" in ra
        assert "action_name" in ra
        assert "status" in ra
        assert "created_at" in ra
        assert "completed_at" in ra
        assert "error_message" in ra
        assert ra["action_name"] == "Test Action Fields"
