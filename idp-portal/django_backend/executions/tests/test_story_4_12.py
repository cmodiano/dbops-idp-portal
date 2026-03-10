import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from catalog.models import Action, ActionStatus
from idp_auth.models import User
from executions.models import Execution


@pytest.mark.django_db
class TestStory412WorkflowStepParameters(TestCase):
    """
    Story 4.12:
      - AC3/AC4: workflow_step_parameters payload validation
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="workflow_step_params_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

        self.ref = Action.objects.create(
            name="Ref With Schema",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            requires_target=False,
        )
        self.ref.parameters_schema = {
            "type": "object",
            "properties": {"foo": {"type": "string"}},
            "required": ["foo"],
        }
        self.ref.save(update_fields=["parameters_schema"])

        self.workflow = Action.objects.create(
            name="Workflow With Steps",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type="workflow",
            requires_target=False,
        )
        self.workflow.execution_steps = (
            [{"order": 1, "name": "Step 1", "referenced_action_id": self.ref.id}]
        )
        self.workflow.save(update_fields=["execution_steps"])

        self.simple_action = Action.objects.create(
            name="Simple Action",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type="action",
            requires_target=False,
        )

    def test_rejects_workflow_step_parameters_for_non_workflow(self):
        resp = self.client.post(
            "/api/v1/executions/",
            {
                "action_id": self.simple_action.id,
                "environment": "dev",
                "workflow_step_parameters": {"1": {"parameters": {"foo": "bar"}}},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        assert (body.get("error") or {}).get("code") == "INVALID_WORKFLOW_STEP_PARAMETERS"

    def test_rejects_unknown_step_order(self):
        resp = self.client.post(
            "/api/v1/executions/",
            {
                "action_id": self.workflow.id,
                "environment": "dev",
                "workflow_step_parameters": {"999": {"parameters": {"foo": "bar"}}},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        assert (body.get("error") or {}).get("code") == "INVALID_WORKFLOW_STEP_ORDER"
        details = (body.get("error") or {}).get("details") or {}
        assert "999" in (details.get("invalid_step_orders") or [])

    def test_rejects_invalid_parameters_for_step(self):
        # Missing required foo
        resp = self.client.post(
            "/api/v1/executions/",
            {
                "action_id": self.workflow.id,
                "environment": "dev",
                "workflow_step_parameters": {"1": {"parameters": {}}},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        assert (body.get("error") or {}).get("code") == "INVALID_PARAMETERS"
        details = (body.get("error") or {}).get("details") or {}
        assert details.get("step_order") == 1

    def test_accepts_valid_workflow_step_parameters_and_stores_them(self):
        resp = self.client.post(
            "/api/v1/executions/",
            {
                "action_id": self.workflow.id,
                "environment": "dev",
                "workflow_step_parameters": {"1": {"parameters": {"foo": "bar"}}},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        created = Execution.objects.order_by("-id").first()
        assert created is not None
        params = created.get_parameters() or {}
        wsp = (params.get("workflow_step_parameters") or {}).get("1") or {}
        assert wsp.get("parameters") == {"foo": "bar"}
        assert "step_id" in wsp
        assert "step_name" in wsp

