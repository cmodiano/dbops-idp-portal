import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from catalog.models import Action, ActionStatus
from core.models import AuditLog
from idp_auth.models import User


def _get_error_message(body):
    """Extract error message from DRF/custom exception response (handles multiple formats)."""
    err = body.get("error") or {}
    msg = err.get("message")
    if msg:
        return msg
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return "; ".join(str(d) for d in detail)
    return ""


@pytest.mark.django_db
class TestStory411WorkflowDelegation(TestCase):
    """
    Story 4.11: Delegation d'autorisation pour exécution de workflows (actions référencées).
    Validates:
      - referenced actions existence + published status only
      - no per-action RBAC checks
      - explicit audit entries with delegated=true (success + failure)
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="workflow_exec_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

        # Referenced actions (published by default)
        self.ref1 = Action.objects.create(
            name="Ref Action 1",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            requires_target=False,
        )
        self.ref2 = Action.objects.create(
            name="Ref Action 2",
            category="Provisioning",
            engine="SQL Server",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            requires_target=False,
        )

        # Workflow action referencing ref1/ref2
        self.workflow = Action.objects.create(
            name="Delegated Workflow",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type="workflow",
            requires_target=False,
        )
        self.workflow.execution_steps = (
            [
                {"order": 1, "name": "Step 1", "referenced_action_id": self.ref1.id},
                {"order": 2, "name": "Step 2", "referenced_action_id": self.ref2.id},
            ]
        )
        self.workflow.save(update_fields=["execution_steps"])

    def test_workflow_delegation_success(self):
        """
        AC1/AC2: user executes workflow; referenced actions exist + published -> 201.
        AC5: audit entry created with delegated=true and referenced_action_ids.
        """
        before = AuditLog.objects.count()
        resp = self.client.post(
            "/api/v1/executions",
            {"action_id": self.workflow.id, "environment": "dev", "parameters": {}},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

        # There should be at least one new audit entry with delegated=true
        after = AuditLog.objects.count()
        assert after > before
        delegated_entries = [
            a for a in AuditLog.objects.all()
            if (a.get_details() or {}).get("delegated") is True
        ]
        assert delegated_entries, "Expected at least one audit entry with delegated=true"
        details = delegated_entries[0].get_details() or {}
        assert details.get("workflow_action_id") == self.workflow.id
        assert details.get("referenced_action_ids") == [self.ref1.id, self.ref2.id]
        assert details.get("validation_result") == "success"

    def test_workflow_referenced_action_deleted_returns_404_and_audit(self):
        """
        AC4: missing referenced action -> 404 with stable message.
        AC5: audit created with delegated=true + validation_result=failed.
        """
        missing_id = self.ref2.id
        self.ref2.delete()

        before = AuditLog.objects.count()
        resp = self.client.post(
            "/api/v1/executions",
            {"action_id": self.workflow.id, "environment": "dev"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        message = _get_error_message(body)
        assert message == f"L'action référencée '{missing_id}' n'existe plus ou n'est plus disponible"

        assert AuditLog.objects.count() > before
        delegated_failed = [
            a for a in AuditLog.objects.all()
            if (a.get_details() or {}).get("delegated") is True
            and (a.get_details() or {}).get("validation_result") == "failed"
        ]
        assert delegated_failed, "Expected failed delegation audit entry"
        details = delegated_failed[0].get_details() or {}
        assert details.get("missing_referenced_action_ids") == [missing_id]

    def test_workflow_referenced_action_not_published_returns_400_and_audit(self):
        """
        AC4: referenced action not published -> 400 with stable message.
        AC5: audit created with delegated=true + validation_result=failed.
        """
        self.ref1.status = ActionStatus.DISABLED
        self.ref1.save(update_fields=["status"])

        before = AuditLog.objects.count()
        resp = self.client.post(
            "/api/v1/executions",
            {"action_id": self.workflow.id, "environment": "dev"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        message = _get_error_message(body)
        assert message == f"L'action référencée '{self.ref1.name}' n'est plus publiée (statut: {self.ref1.status})"

        assert AuditLog.objects.count() > before
        delegated_failed = [
            a for a in AuditLog.objects.all()
            if (a.get_details() or {}).get("delegated") is True
            and (a.get_details() or {}).get("validation_result") == "failed"
        ]
        assert delegated_failed, "Expected failed delegation audit entry"
        details = delegated_failed[0].get_details() or {}
        assert any(
            p.get("action_name") == self.ref1.name and p.get("status") == self.ref1.status
            for p in details.get("not_published", [])
        )

    def test_workflow_multiple_missing_actions_returns_404_with_all_listed(self):
        """AC4: multiple missing referenced actions -> 404 with all IDs in message."""
        id1, id2 = self.ref1.id, self.ref2.id
        self.ref1.delete()
        self.ref2.delete()

        resp = self.client.post(
            "/api/v1/executions",
            {"action_id": self.workflow.id, "environment": "dev"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        message = _get_error_message(resp.json())
        assert "n'existent plus" in message
        assert str(id1) in message
        assert str(id2) in message

    def test_workflow_multiple_not_published_returns_400_with_all_listed(self):
        """AC4: multiple not-published referenced actions -> 400 with all in message."""
        self.ref1.status = ActionStatus.DISABLED
        self.ref1.save(update_fields=["status"])
        self.ref2.status = ActionStatus.DRAFT
        self.ref2.save(update_fields=["status"])

        resp = self.client.post(
            "/api/v1/executions",
            {"action_id": self.workflow.id, "environment": "dev"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        message = _get_error_message(resp.json())
        assert "ne sont plus publiées" in message
        assert self.ref1.name in message
        assert self.ref2.name in message
        assert "disabled" in message
        assert "draft" in message

    def test_workflow_empty_referenced_actions_returns_400(self):
        """Workflow with no referenced actions -> 400."""
        self.workflow.execution_steps = ([])
        self.workflow.save(update_fields=["execution_steps"])

        resp = self.client.post(
            "/api/v1/executions",
            {"action_id": self.workflow.id, "environment": "dev"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        assert (body.get("error") or {}).get("code") == "WORKFLOW_EMPTY"

