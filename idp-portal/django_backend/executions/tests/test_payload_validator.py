import pytest
from unittest.mock import patch

from django.test import RequestFactory

from core.exceptions import BadRequestError
from executions.validators.payload_validator import ExecutionPayloadValidator


@pytest.mark.django_db
class TestExecutionPayloadValidator:
    def test_parameters_must_be_dict(self):
        request = RequestFactory().post("/api/v1/executions/")

        payload = {
            "action_id": 1,
            "environment": "dev",
            "parameters": ["not", "a", "dict"],
        }

        with patch.object(ExecutionPayloadValidator, "validate_action") as mock_validate_action:
            mock_action = type("MockAction", (), {"requires_target": False})()
            mock_validate_action.return_value = mock_action

            with pytest.raises(BadRequestError) as exc_info:
                ExecutionPayloadValidator.validate(payload, request)

        assert exc_info.value.code == "BAD_REQUEST"
        assert "parameters" in exc_info.value.message

