"""Tests for centralized status mappers (adapters/status_mappers.py).

Story 54.11 (MAINT-BE-7): Verify centralized status mappings are correct
and that AAP/Tower share the same dict instance.
"""
from __future__ import annotations

import pytest

from adapters.status_mappers import (
    AAP_STATUS_MAP,
    AZURE_DEVOPS_STATUS_MAP,
    AZURE_DEVOPS_TERMINAL_RESULTS,
    GITHUB_ACTIONS_STATUS_MAP,
    GITHUB_ACTIONS_TERMINAL_CONCLUSIONS,
    TERRAFORM_CLOUD_STATUS_MAP,
    TERRAFORM_CLOUD_TERMINAL_STATUSES,
    TOWER_STATUS_MAP,
    map_azure_devops_status,
    map_github_actions_status,
    map_terraform_cloud_status,
)


class TestAAPTowerSharedDict:
    def test_aap_and_tower_share_same_dict(self) -> None:
        """AAP and Tower point to the same dict instance (identical protocol)."""
        assert AAP_STATUS_MAP is TOWER_STATUS_MAP

    def test_aap_map_has_expected_entries(self) -> None:
        valid = {"SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        for k, v in AAP_STATUS_MAP.items():
            assert v in valid, f"AAP {k!r} → {v!r} invalid"


class TestAAPStatusMapper:
    @pytest.mark.parametrize("aap_status,expected", [
        ("pending", "SUBMITTED"),
        ("waiting", "SUBMITTED"),
        ("running", "RUNNING"),
        ("successful", "COMPLETED"),
        ("failed", "FAILED"),
        ("error", "FAILED"),
        ("canceled", "CANCELLED"),
    ])
    def test_status_map(self, aap_status: str, expected: str) -> None:
        assert AAP_STATUS_MAP[aap_status] == expected

    def test_unknown_status_defaults_to_submitted(self) -> None:
        assert AAP_STATUS_MAP.get("new_status", "SUBMITTED") == "SUBMITTED"


class TestTowerStatusMapper:
    @pytest.mark.parametrize("tower_status,expected", [
        ("pending", "SUBMITTED"),
        ("waiting", "SUBMITTED"),
        ("running", "RUNNING"),
        ("successful", "COMPLETED"),
        ("failed", "FAILED"),
        ("error", "FAILED"),
        ("canceled", "CANCELLED"),
    ])
    def test_status_map(self, tower_status: str, expected: str) -> None:
        assert TOWER_STATUS_MAP[tower_status] == expected

    def test_unknown_status_defaults_to_submitted(self) -> None:
        assert TOWER_STATUS_MAP.get("new_status", "SUBMITTED") == "SUBMITTED"


class TestGitHubActionsStatusMapper:
    def test_queued(self) -> None:
        assert map_github_actions_status("queued", None) == "SUBMITTED"

    def test_in_progress(self) -> None:
        assert map_github_actions_status("in_progress", None) == "RUNNING"

    def test_completed_success(self) -> None:
        assert map_github_actions_status("completed", "success") == "COMPLETED"

    def test_completed_failure(self) -> None:
        assert map_github_actions_status("completed", "failure") == "FAILED"

    def test_completed_cancelled(self) -> None:
        assert map_github_actions_status("completed", "cancelled") == "CANCELLED"

    def test_completed_timed_out(self) -> None:
        assert map_github_actions_status("completed", "timed_out") == "FAILED"

    def test_completed_action_required(self) -> None:
        assert map_github_actions_status("completed", "action_required") == "SUBMITTED"

    def test_completed_skipped(self) -> None:
        assert map_github_actions_status("completed", "skipped") == "CANCELLED"

    def test_unknown_state(self) -> None:
        assert map_github_actions_status("unknown", None) == "SUBMITTED"

    def test_completed_unknown_conclusion(self) -> None:
        assert map_github_actions_status("completed", "unknown") == "FAILED"

    def test_terminal_conclusions_in_map(self) -> None:
        for conclusion in GITHUB_ACTIONS_TERMINAL_CONCLUSIONS:
            key = f"completed:{conclusion}"
            assert key in GITHUB_ACTIONS_STATUS_MAP, f"{key!r} missing from map"


class TestTerraformCloudStatusMapper:
    def test_all_entries_valid(self) -> None:
        valid = {"SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        for k, v in TERRAFORM_CLOUD_STATUS_MAP.items():
            assert v in valid, f"TFC {k!r} → {v!r} invalid"

    @pytest.mark.parametrize("tc_status,expected", [
        ("pending", "SUBMITTED"),
        ("planning", "RUNNING"),
        ("applied", "COMPLETED"),
        ("planned_and_finished", "COMPLETED"),
        ("errored", "FAILED"),
        ("canceled", "CANCELLED"),
        ("force_canceled", "CANCELLED"),
        ("discarded", "CANCELLED"),
    ])
    def test_map_function(self, tc_status: str, expected: str) -> None:
        assert map_terraform_cloud_status(tc_status) == expected

    def test_unknown_status(self) -> None:
        assert map_terraform_cloud_status("new_tfc_status") == "SUBMITTED"

    def test_terminal_statuses_are_subset_of_map(self) -> None:
        for status in TERRAFORM_CLOUD_TERMINAL_STATUSES:
            assert status in TERRAFORM_CLOUD_STATUS_MAP


class TestAzureDevOpsStatusMapper:
    def test_in_progress(self) -> None:
        assert map_azure_devops_status("inProgress", None) == "RUNNING"

    def test_canceling(self) -> None:
        assert map_azure_devops_status("canceling", None) == "RUNNING"

    def test_completed_succeeded(self) -> None:
        assert map_azure_devops_status("completed", "succeeded") == "COMPLETED"

    def test_completed_failed(self) -> None:
        assert map_azure_devops_status("completed", "failed") == "FAILED"

    def test_completed_canceled(self) -> None:
        assert map_azure_devops_status("completed", "canceled") == "CANCELLED"

    def test_unknown_state(self) -> None:
        assert map_azure_devops_status("unknown", None) == "SUBMITTED"

    def test_completed_unknown_result(self) -> None:
        assert map_azure_devops_status("completed", "unknown") == "FAILED"

    def test_terminal_results_in_map(self) -> None:
        for result in AZURE_DEVOPS_TERMINAL_RESULTS:
            key = f"completed:{result}"
            assert key in AZURE_DEVOPS_STATUS_MAP, f"{key!r} missing from map"
