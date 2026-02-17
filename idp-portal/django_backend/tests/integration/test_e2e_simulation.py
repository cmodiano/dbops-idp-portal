"""
End-to-end tests for execution simulation mode (Story 19.0).

Validates the complete flow:
  POST /executions → steps created → progression → GET /steps → final status.

Uses synchronous simulation (no threads) for SQLite compatibility.
"""

from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Action
from executions.models import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
)
from executions.simulation_service import SimulationService
from idp_auth.models import User


def _sync_start_simulation(execution):
    """Replacement for start_simulation that runs synchronously (no thread)."""
    from django.conf import settings

    if not getattr(settings, "SIMULATE_EXECUTION_DEV", False):
        return
    from django.utils import timezone

    execution.status = ExecutionStatus.RUNNING
    execution.started_at = timezone.now()
    execution.save(update_fields=["status", "started_at"])
    SimulationService._run_simulation(execution.id)


@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_FAILURE_RATE=0.0,
    SIMULATE_EXECUTION_STEP_DURATION=0,
)
@pytest.mark.django_db
@pytest.mark.integration
class TestE2ESimulationFlow(TestCase):
    """AC11: End-to-end simulation flow via API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="e2e_sim_user", profile="DBA")
        self.client.force_authenticate(user=self.user)
        self.action = Action.objects.create(
            name="E2E Sim Action",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status="published",
            requires_target=False,
        )

    @patch("executions.simulation_service.time.sleep")
    @patch.object(
        SimulationService, "start_simulation", side_effect=_sync_start_simulation
    )
    def test_full_simulation_flow_success(self, mock_start, mock_sleep):
        """E2E: POST /executions → GET /executions/{id} → GET /steps → all COMPLETED."""
        # 1. Create execution
        response = self.client.post(
            "/api/v1/executions/",
            {"action_id": self.action.id, "environment": "dev"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        execution_id = response.data["data"]["execution_id"]

        # 2. Verify execution detail shows COMPLETED
        detail = self.client.get(f"/api/v1/executions/{execution_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["data"]["status"], "COMPLETED")
        self.assertIsNotNone(detail.data["data"]["completed_at"])

        # 3. Verify all steps via API
        steps_resp = self.client.get(f"/api/v1/executions/{execution_id}/steps/")
        self.assertEqual(steps_resp.status_code, 200)
        steps_data = steps_resp.data["data"]
        self.assertEqual(len(steps_data), 5)

        for step in steps_data:
            self.assertEqual(step["status"], "COMPLETED")
            self.assertIsNotNone(step["started_at"])
            self.assertIsNotNone(step["completed_at"])

        # 4. Verify step names match specification
        names = [s["step_name"] for s in steps_data]
        self.assertEqual(
            names,
            [
                "Préparation",
                "Récupération secrets Vault",
                "Déclenchement plateforme",
                "Exécution distante",
                "Vérification résultat",
            ],
        )

    @override_settings(SIMULATE_EXECUTION_FAILURE_RATE=1.0)
    @patch("executions.simulation_service.time.sleep")
    @patch.object(
        SimulationService, "start_simulation", side_effect=_sync_start_simulation
    )
    def test_full_simulation_flow_failure(self, mock_start, mock_sleep):
        """E2E: With 100% failure rate, execution ends FAILED with error logs."""
        response = self.client.post(
            "/api/v1/executions/",
            {"action_id": self.action.id, "environment": "dev"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        execution_id = response.data["data"]["execution_id"]

        # Execution should be FAILED
        detail = self.client.get(f"/api/v1/executions/{execution_id}/")
        self.assertEqual(detail.data["data"]["status"], "FAILED")

        # Last step should be FAILED, earlier steps COMPLETED
        steps_resp = self.client.get(f"/api/v1/executions/{execution_id}/steps/")
        steps_data = steps_resp.data["data"]

        for step in steps_data[:-1]:
            self.assertEqual(step["status"], "COMPLETED")
        self.assertEqual(steps_data[-1]["status"], "FAILED")

    @patch("executions.simulation_service.time.sleep")
    @patch.object(
        SimulationService, "start_simulation", side_effect=_sync_start_simulation
    )
    def test_steps_contain_realistic_logs(self, mock_start, mock_sleep):
        """E2E AC4: Logs are realistic per step type."""
        response = self.client.post(
            "/api/v1/executions/",
            {"action_id": self.action.id, "environment": "dev"},
            format="json",
        )
        execution_id = response.data["data"]["execution_id"]

        steps = ExecutionStep.objects.filter(execution_id=execution_id).order_by(
            "step_order"
        )

        # Vault step mentions secrets
        vault_step = steps.get(step_name="Récupération secrets Vault")
        self.assertIn("Vault", vault_step.output)
        self.assertIn("secrets", vault_step.output)

        # Platform step includes job ID
        platform_step = steps.get(step_name="Déclenchement plateforme")
        self.assertIn(f"job-sim-{execution_id}", platform_step.output)

        # Verification step includes success
        verif_step = steps.get(step_name="Vérification résultat")
        self.assertIn("[SUCCESS]", verif_step.output)

    @override_settings(SIMULATE_EXECUTION_DEV=False)
    def test_simulation_disabled_normal_flow(self):
        """E2E: When simulation disabled, no steps are auto-created."""
        response = self.client.post(
            "/api/v1/executions/",
            {"action_id": self.action.id, "environment": "dev"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        execution_id = response.data["data"]["execution_id"]

        steps = ExecutionStep.objects.filter(execution_id=execution_id)
        self.assertEqual(steps.count(), 0)

        execution = Execution.objects.get(id=execution_id)
        self.assertEqual(execution.status, ExecutionStatus.SUBMITTED)
