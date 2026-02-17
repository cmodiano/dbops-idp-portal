"""
Unit tests for AAPOutputInterpreter.
Story 28.3 — AC5: Tests unitaires AAPOutputInterpreter.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from executions.interpreters.aap_output_interpreter import AAPOutputInterpreter
from executions.policy_evaluator import PolicyEvaluationError


CORR_PATCH = "executions.interpreters.aap_output_interpreter.get_correlation_id"


class TestAAPOutputInterpreter:
    """AC5: AAPOutputInterpreter tests."""

    @patch(CORR_PATCH, return_value="test")
    def test_aap_interpreter_successful_job(self, _m: MagicMock) -> None:
        """job_status=successful, failed_tasks=0."""
        interpreter = AAPOutputInterpreter()
        output = {
            "job_id": 100,
            "status": "successful",
            "failed": False,
            "failed_tasks": [],
            "changed": 3,
            "changed_hosts": ["server1", "server2", "server3"],
        }

        artifact = interpreter.interpret("aap", output)

        assert artifact.changes == []
        assert artifact.metadata["job_id"] == 100
        assert artifact.metadata["job_status"] == "successful"
        assert artifact.metadata["changed_hosts"] == ["server1", "server2", "server3"]

    @patch(CORR_PATCH, return_value="test")
    def test_aap_interpreter_failed_tasks(self, _m: MagicMock) -> None:
        """job_status=failed, failed_tasks > 0."""
        interpreter = AAPOutputInterpreter()
        output = {
            "job_id": 200,
            "status": "failed",
            "failed": True,
            "failed_tasks": [
                {"name": "Install package", "host": "server1"},
                {"name": "Configure service", "host": "server2"},
            ],
            "changed": 1,
            "changed_hosts": ["server3"],
        }

        artifact = interpreter.interpret("aap", output)

        assert len(artifact.changes) == 2
        assert artifact.changes[0]["task_name"] == "Install package"
        assert artifact.changes[0]["host"] == "server1"
        assert artifact.changes[0]["status"] == "failed"
        assert artifact.changes[1]["task_name"] == "Configure service"
        assert artifact.metadata["job_status"] == "failed"

    @patch(CORR_PATCH, return_value="test")
    def test_aap_interpreter_changed_hosts(self, _m: MagicMock) -> None:
        """changed_hosts extracted correctly."""
        interpreter = AAPOutputInterpreter()
        output = {
            "job_id": 300,
            "status": "successful",
            "failed_tasks": [],
            "changed_hosts": ["web1", "web2", "db1"],
        }

        artifact = interpreter.interpret("aap", output)

        assert artifact.metadata["changed_hosts"] == ["web1", "web2", "db1"]
        assert len(artifact.metadata["changed_hosts"]) == 3

    @patch(CORR_PATCH, return_value="test")
    def test_aap_interpreter_invalid_output(self, _m: MagicMock) -> None:
        """output corrompu → PolicyEvaluationError."""
        interpreter = AAPOutputInterpreter()

        with pytest.raises(PolicyEvaluationError, match="Invalid AAP job output"):
            interpreter.interpret("aap", 12345)  # type: ignore[arg-type]

    @patch(CORR_PATCH, return_value="test")
    def test_aap_interpreter_json_string(self, _m: MagicMock) -> None:
        """JSON string input → parsed correctly."""
        interpreter = AAPOutputInterpreter()
        output = json.dumps({
            "job_id": 400,
            "status": "successful",
            "failed_tasks": [],
            "changed_hosts": [],
        })

        artifact = interpreter.interpret("aap", output)

        assert artifact.metadata["job_id"] == 400
        assert artifact.changes == []

    @patch(CORR_PATCH, return_value="test")
    def test_aap_interpreter_invalid_json_string(self, _m: MagicMock) -> None:
        """Invalid JSON string → PolicyEvaluationError."""
        interpreter = AAPOutputInterpreter()

        with pytest.raises(PolicyEvaluationError, match="cannot parse JSON"):
            interpreter.interpret("aap", "{ invalid json }")
