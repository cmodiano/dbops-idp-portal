"""Centralized status mapping for all platform adapters.

Story 54.11 (MAINT-BE-7): Eliminate duplicated STATUS_MAP dicts across adapters.
Single source of truth for platform status → IDP Portal status conversions.

IDP Portal target status vocabulary:
  SUBMITTED  — job accepted, waiting to start
  RUNNING    — job actively executing
  COMPLETED  — job finished successfully
  FAILED     — job finished with an error
  CANCELLED  — job was cancelled before or during execution
"""
from __future__ import annotations

__all__ = [
    "AAP_STATUS_MAP",
    "TOWER_STATUS_MAP",
    "AAP_TOWER_TERMINAL_STATUSES",
    "GITHUB_ACTIONS_STATUS_MAP",
    "GITHUB_ACTIONS_TERMINAL_CONCLUSIONS",
    "map_github_actions_status",
    "TERRAFORM_CLOUD_STATUS_MAP",
    "TERRAFORM_CLOUD_TERMINAL_STATUSES",
    "map_terraform_cloud_status",
    "AZURE_DEVOPS_STATUS_MAP",
    "AZURE_DEVOPS_TERMINAL_RESULTS",
    "map_azure_devops_status",
]

# ---------------------------------------------------------------------------
# AAP / Tower (Ansible Automation Platform + Tower/AWX)
# Both platforms use the same API v2 status vocabulary.
# ---------------------------------------------------------------------------

_AAP_TOWER_STATUS_MAP: dict[str, str] = {
    "pending": "SUBMITTED",
    "waiting": "SUBMITTED",
    "running": "RUNNING",
    "successful": "COMPLETED",
    "failed": "FAILED",
    "error": "FAILED",
    "canceled": "CANCELLED",
}

# Both names point to the same dict — Tower/AWX API is identical to AAP API v2
AAP_STATUS_MAP: dict[str, str] = _AAP_TOWER_STATUS_MAP
TOWER_STATUS_MAP: dict[str, str] = _AAP_TOWER_STATUS_MAP  # alias — identical to AAP

# Terminal statuses for AAP/Tower log-completeness checks
AAP_TOWER_TERMINAL_STATUSES: frozenset[str] = frozenset({
    "successful",
    "failed",
    "error",
    "canceled",
})

# ---------------------------------------------------------------------------
# GitHub Actions
# ---------------------------------------------------------------------------

GITHUB_ACTIONS_STATUS_MAP: dict[str, str] = {
    "queued": "SUBMITTED",
    "in_progress": "RUNNING",
    "completed:success": "COMPLETED",
    "completed:failure": "FAILED",
    "completed:cancelled": "CANCELLED",
    "completed:timed_out": "FAILED",
    "completed:action_required": "SUBMITTED",
    "completed:skipped": "CANCELLED",
}

GITHUB_ACTIONS_TERMINAL_CONCLUSIONS: set[str] = {
    "success",
    "failure",
    "cancelled",
    "timed_out",
    "skipped",
}


def map_github_actions_status(status: str, conclusion: str | None) -> str:
    """Map GitHub Actions status+conclusion to IDP Portal status."""
    if status == "completed" and conclusion:
        mapped = GITHUB_ACTIONS_STATUS_MAP.get(f"completed:{conclusion}")
        return mapped if mapped is not None else "FAILED"
    mapped = GITHUB_ACTIONS_STATUS_MAP.get(status)
    return mapped if mapped is not None else "SUBMITTED"


# ---------------------------------------------------------------------------
# Terraform Cloud
# ---------------------------------------------------------------------------

TERRAFORM_CLOUD_STATUS_MAP: dict[str, str] = {
    "pending": "SUBMITTED",
    "fetching": "SUBMITTED",
    "plan_queued": "SUBMITTED",
    "planning": "RUNNING",
    "planned": "SUBMITTED",
    "cost_estimating": "RUNNING",
    "cost_estimated": "SUBMITTED",
    "policy_checking": "RUNNING",
    "policy_override": "SUBMITTED",
    "policy_soft_failed": "SUBMITTED",
    "policy_checked": "SUBMITTED",
    "confirmed": "SUBMITTED",
    "apply_queued": "SUBMITTED",
    "applying": "RUNNING",
    "applied": "COMPLETED",
    "planned_and_finished": "COMPLETED",
    "errored": "FAILED",
    "canceled": "CANCELLED",
    "force_canceled": "CANCELLED",
    "discarded": "CANCELLED",
}

TERRAFORM_CLOUD_TERMINAL_STATUSES: set[str] = {
    "applied",
    "planned_and_finished",
    "errored",
    "canceled",
    "force_canceled",
    "discarded",
}


def map_terraform_cloud_status(tc_status: str) -> str:
    """Map Terraform Cloud run status to IDP Portal status."""
    mapped = TERRAFORM_CLOUD_STATUS_MAP.get(tc_status)
    return mapped if mapped is not None else "SUBMITTED"


# ---------------------------------------------------------------------------
# Azure DevOps
# ---------------------------------------------------------------------------

AZURE_DEVOPS_STATUS_MAP: dict[str, str] = {
    "inProgress": "RUNNING",
    "canceling": "RUNNING",
    "completed:succeeded": "COMPLETED",
    "completed:failed": "FAILED",
    "completed:canceled": "CANCELLED",
}

AZURE_DEVOPS_TERMINAL_RESULTS: set[str] = {"succeeded", "failed", "canceled"}


def map_azure_devops_status(state: str, result: str | None) -> str:
    """Map Azure DevOps state+result to IDP Portal status."""
    if state == "completed" and result:
        mapped = AZURE_DEVOPS_STATUS_MAP.get(f"completed:{result}")
        return mapped if mapped is not None else "FAILED"
    mapped = AZURE_DEVOPS_STATUS_MAP.get(state)
    return mapped if mapped is not None else "SUBMITTED"
