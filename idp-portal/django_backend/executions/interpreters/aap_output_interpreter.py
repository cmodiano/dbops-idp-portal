"""
AAPOutputInterpreter — Parses AAP (Ansible Automation Platform) job output.

Extracts job_status, failed_tasks, changed_hosts from AAP job JSON output
and produces a NormalizedArtifact.
"""
from __future__ import annotations

import json

import structlog

from core.middleware import get_correlation_id
from executions.interpreters.base import NormalizedArtifact, OutputInterpreter
from executions.policy_evaluator import PolicyEvaluationError

logger = structlog.get_logger(__name__)


class AAPOutputInterpreter(OutputInterpreter):
    """Interprets AAP job output (JSON)."""

    def interpret(self, step_type: str, step_output: dict | str) -> NormalizedArtifact:
        """
        Parse AAP job output and extract job_status, failed_tasks, changed_hosts.

        Input format (AAP job summary JSON):
        {
          "job_id": 12345,
          "status": "failed",
          "failed": true,
          "failed_tasks": [
            {"name": "Install package", "host": "server1"}
          ],
          "changed": 2,
          "changed_hosts": ["server2", "server3"]
        }
        """
        correlation_id = get_correlation_id()

        if isinstance(step_output, str):
            try:
                step_output = json.loads(step_output)
            except (ValueError, TypeError) as exc:
                raise PolicyEvaluationError(
                    message=f"Invalid AAP job output: cannot parse JSON: {exc}",
                ) from exc

        if not isinstance(step_output, dict):
            raise PolicyEvaluationError(
                message=f"Invalid AAP job output: expected dict or JSON str, got {type(step_output).__name__}",
            )

        failed_tasks = step_output.get("failed_tasks", [])
        if not isinstance(failed_tasks, list):
            raise PolicyEvaluationError(
                message="Invalid AAP job output: 'failed_tasks' must be a list",
            )

        changes: list[dict] = [
            {
                "task_name": task.get("name", "unknown"),
                "host": task.get("host", "unknown"),
                "status": "failed",
            }
            for task in failed_tasks
            if isinstance(task, dict)
        ]

        metadata = {
            "job_id": step_output.get("job_id"),
            "job_status": step_output.get("status"),
            "changed_hosts": step_output.get("changed_hosts", []),
        }

        logger.info(
            "aap_job_output_parsed",
            job_id=metadata["job_id"],
            job_status=metadata["job_status"],
            num_failed_tasks=len(changes),
            num_changed_hosts=len(metadata["changed_hosts"]),
            correlation_id=correlation_id,
        )

        return NormalizedArtifact(changes=changes, metadata=metadata)
