"""Tests de couverture complémentaires pour executions/views/remediation_views.py.

Couvre les branches manquantes :
- regex invalide dans error_pattern (compilation)
- target_action_id absent dans la règle
- Action.DoesNotExist pour le target_action
- child.action is None (completed_at / action_name None)
- Execution.DoesNotExist (404) dans les deux vues
- remediation_rules vide
- error_message vide
- environment filter ne matchant pas
"""
import json
import pytest
from rest_framework.test import APIClient

from executions.models import ExecutionStatus
from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory


@pytest.mark.django_db
class TestRemediationSuggestionsNotFound:
    """Tests 404 pour ExecutionRemediationSuggestionsView."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile="DBA", username="test_user_404_sug")
        self.client.force_authenticate(user=self.user)

    def test_execution_not_found_suggestions(self):
        """Execution non trouvée → 404 dans ExecutionRemediationSuggestionsView."""
        response = self.client.get("/api/v1/executions/999999/remediation")
        assert response.status_code == 404

    def test_no_remediation_rules(self):
        """Action sans remediation_rules → réponse vide."""
        integration = IntegrationFactory.create(type="aap", name="AAP 404 test")
        action = ActionFactory.create(
            status="published",
            integration=integration,
            remediation_rules=None,
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            error_message="some error",
        )
        response = self.client.get(f"/api/v1/executions/{execution.id}/remediation")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_no_error_message(self):
        """Execution sans error_message → réponse vide."""
        integration = IntegrationFactory.create(type="aap", name="AAP no-err test")
        action = ActionFactory.create(
            status="published",
            integration=integration,
            remediation_rules=json.dumps([{"error_pattern": "ORA-01555", "target_action_id": 1}]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            error_message="",
        )
        response = self.client.get(f"/api/v1/executions/{execution.id}/remediation")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_environment_filter_no_match(self):
        """Règle avec environments non correspondants → règle ignorée."""
        integration = IntegrationFactory.create(type="aap", name="AAP env test")
        target_action = ActionFactory.create(
            status="published", integration=integration, name="Fix Action Env"
        )
        action = ActionFactory.create(
            status="published",
            integration=integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-01555",
                    "target_action_id": target_action.id,
                    "environments": ["prod"],  # execution is in "dev" → no match
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
        response = self.client.get(f"/api/v1/executions/{execution.id}/remediation")
        assert response.status_code == 200
        assert response.json()["data"] == []


@pytest.mark.django_db
class TestRemediationSuggestionsCoverageEdgeCases:
    """Branches manquantes de ExecutionRemediationSuggestionsView."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile="DBA", username="test_user_cov_rem")
        self.integration = IntegrationFactory.create(type="aap", name="Test AAP Cov")
        self.client.force_authenticate(user=self.user)

    def _url(self, execution_id: int) -> str:
        return f"/api/v1/executions/{execution_id}/remediation"

    def test_invalid_regex_pattern_skips_rule(self):
        """Regex invalide dans error_pattern → règle ignorée, liste vide."""
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
                    "error_pattern": "[invalid regex(",  # Invalid regex
                    "target_action_id": target_action.id,
                    "environments": [],
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
            error_message="some error message",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_missing_target_action_id_skips_rule(self):
        """Règle sans target_action_id → règle ignorée."""
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-01555",
                    # No target_action_id key
                    "environments": [],
                    "auto_trigger": False,
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
        assert response.json()["data"] == []

    def test_target_action_not_found_skips_rule(self):
        """target_action inexistant → règle ignorée, liste vide."""
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    "error_pattern": "ORA-01555",
                    "target_action_id": 999999,  # Non-existent action
                    "environments": [],
                    "auto_trigger": False,
                    "risk_level": "medium",
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
        assert response.json()["data"] == []

    def test_multiple_rules_some_matching_some_not(self):
        """Plusieurs règles : certaines matchent, d'autres non (y compris sans target_action_id)."""
        target_action = ActionFactory.create(
            name="Fix Action Matching",
            status="published",
            integration=self.integration,
        )
        action = ActionFactory.create(
            status="published",
            integration=self.integration,
            remediation_rules=json.dumps([
                {
                    # Valid matching rule
                    "error_pattern": "ORA-01555",
                    "target_action_id": target_action.id,
                    "environments": [],
                    "auto_trigger": False,
                    "risk_level": "low",
                },
                {
                    # No target_action_id → skipped
                    "error_pattern": "ORA-01555",
                    "environments": [],
                },
                {
                    # Invalid regex → skipped
                    "error_pattern": "[bad(",
                    "target_action_id": target_action.id,
                    "environments": [],
                },
                {
                    # Non-matching regex
                    "error_pattern": "DIFFERENT-ERROR",
                    "target_action_id": target_action.id,
                    "environments": [],
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="prod",
            error_message="ORA-01555: snapshot too old",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        data = response.json()["data"]
        # Only first rule matches
        assert len(data) == 1
        assert data[0]["action_id"] == target_action.id

    def test_rule_without_environments_key_matches_any_env(self):
        """Règle sans clé 'environments' → rule_envs=[], toujours active."""
        target_action = ActionFactory.create(
            name="Fix No Env Rule",
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
                    # No 'environments' key
                    "auto_trigger": True,
                    "risk_level": "high",
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="production",
            error_message="ORA-01555: snapshot too old",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["matching_rule"]["auto_trigger"] is True
        assert data[0]["matching_rule"]["risk_level"] == "high"

    def test_empty_error_pattern_in_rule_skips_rule(self):
        """Règle avec error_pattern vide → règle ignorée."""
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
                    "error_pattern": "",  # Empty pattern
                    "target_action_id": target_action.id,
                    "environments": [],
                },
            ]),
        )
        execution = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
            error_message="some error",
        )

        response = self.client.get(self._url(execution.id))

        assert response.status_code == 200
        assert response.json()["data"] == []


@pytest.mark.django_db
class TestRemediationContextCoverageEdgeCases:
    """Branches manquantes de ExecutionRemediationContextView."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile="DBA", username="test_user_ctx_cov")
        self.integration = IntegrationFactory.create(type="aap", name="Test AAP CtxCov")
        self.client.force_authenticate(user=self.user)

    def _url(self, execution_id: int) -> str:
        return f"/api/v1/executions/{execution_id}/remediation-context"

    def test_child_with_null_completed_at(self):
        """Child execution sans completed_at → completed_at=None dans la réponse."""
        action = ActionFactory.create(status="published", integration=self.integration)
        parent = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )
        child = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
            parent_execution=parent,
        )
        # Ensure completed_at is None
        child.completed_at = None
        child.save(update_fields=["completed_at"])

        response = self.client.get(self._url(parent.id))

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_remediation"] is True
        ra = data["remediation_actions"][0]
        assert ra["completed_at"] is None

    def test_child_with_completed_at_set(self):
        """Child execution avec completed_at → completed_at non None dans la réponse."""
        from django.utils import timezone
        action = ActionFactory.create(status="published", integration=self.integration)
        parent = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment="dev",
        )
        child = ExecutionFactory.create(
            action=action,
            user=self.user,
            status=ExecutionStatus.COMPLETED,
            environment="dev",
            parent_execution=parent,
        )
        # Explicitly set completed_at as it may not be auto-set by factory
        child.completed_at = timezone.now()
        child.save(update_fields=["completed_at"])

        response = self.client.get(self._url(parent.id))

        assert response.status_code == 200
        data = response.json()["data"]
        ra = data["remediation_actions"][0]
        # completed_at should be a non-null ISO string
        assert ra["completed_at"] is not None
        assert "T" in ra["completed_at"]

    def test_execution_not_found_context(self):
        """Execution non trouvée → 404 dans ExecutionRemediationContextView."""
        response = self.client.get(self._url(999999))
        assert response.status_code == 404
