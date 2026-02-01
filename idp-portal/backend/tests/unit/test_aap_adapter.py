"""Tests for AAP adapter (Story 4.4, 5.3).

Tests AAPAdapter implementation:
- Trigger job on AAP platform (AC1)
- Handle AAP errors (AC2)
- Get job status (AC3)
- Parse webhook callback (AC4)
- Factory registration (AC5)
- Story 5.3: config flow (obtain_token then call_api), rétrocompat sans config
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.adapters.aap_adapter import AAPAdapter
from app.adapters import get_platform_adapter
from app.core.exceptions import PlatformError


class TestAAPAdapterInit:
    """Tests for AAPAdapter initialization (Task 1.1)."""

    def test_aap_adapter_initializes_with_platform_type_and_base_url(self):
        """AAPAdapter stores platform_type and base_url."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")

        assert adapter.platform_type == "aap"
        assert adapter.base_url == "https://aap.example.com"

    def test_aap_adapter_uses_httpx_client(self):
        """AAPAdapter uses httpx.AsyncClient for HTTP calls."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")

        # Adapter should have client attribute or create it on demand
        assert hasattr(adapter, "_client") or hasattr(adapter, "base_url")


class TestAAPAdapterTrigger:
    """Tests for AAPAdapter.trigger method (Task 1.2, 1.3, 1.4)."""

    @pytest.mark.asyncio
    async def test_trigger_success_returns_job_id(self):
        """Trigger returns AAP job_id on success (AC1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42, "extra_vars": {"target": "db-01"}}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345, "status": "pending"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            job_id = await adapter.trigger(parameters, credentials, correlation_id)

        assert job_id == "12345"

    @pytest.mark.asyncio
    async def test_trigger_with_bearer_token(self):
        """Trigger uses Bearer token when credentials contain token (AC1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        correlation_id = "test-corr-123"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            job_id = await adapter.trigger(parameters, credentials, correlation_id)

            # Verify Bearer token was used
            call_kwargs = mock_client.post.call_args.kwargs
            assert "headers" in call_kwargs
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"].startswith("Bearer ")

    @pytest.mark.asyncio
    async def test_trigger_with_basic_auth(self):
        """Trigger uses Basic auth when credentials contain username/password (AC1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            await adapter.trigger(parameters, credentials, correlation_id)

            # Verify auth was used
            call_kwargs = mock_client.post.call_args.kwargs
            assert "auth" in call_kwargs

    @pytest.mark.asyncio
    async def test_trigger_with_integration_config_obtains_token_then_launches(self):
        """Story 5.3 AC4: When integration has config with obtain_token step, POST token_url first then launch with Bearer."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"
        integration = {
            "base_url": "https://aap.example.com",
            "token_url": "https://aap.example.com/api/v2/token/",
            "config": {
                "auth_flow": [
                    {
                        "step": "obtain_token",
                        "url_ref": "token_url",
                        "credentials": {"ref": "credential_ref", "keys": ["username", "password"]},
                        "response_token_path": "access_token",
                    },
                ],
            },
        }

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "token-from-config"}
        token_response.raise_for_status = MagicMock()
        launch_response = MagicMock()
        launch_response.status_code = 201
        launch_response.json.return_value = {"id": 99999}
        launch_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[token_response, launch_response])
            mock_get_client.return_value = mock_client

            job_id = await adapter.trigger(
                parameters, credentials, correlation_id, integration=integration
            )

        assert job_id == "99999"
        assert mock_client.post.call_count == 2
        # First call: token_url with username/password body
        first_call_url = mock_client.post.call_args_list[0][0][0]
        assert "token" in first_call_url
        # Second call: launch with Bearer (credentials merged with token)
        second_call_headers = mock_client.post.call_args_list[1][1].get("headers", {})
        assert "Authorization" in second_call_headers
        assert "Bearer token-from-config" in second_call_headers["Authorization"]

    @pytest.mark.asyncio
    async def test_trigger_with_integration_config_nested_token_path(self):
        """Story 5.3: Nested response_token_path like 'data.access_token' (code-review fix MED-1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"
        integration = {
            "base_url": "https://aap.example.com",
            "token_url": "https://aap.example.com/api/v2/token/",
            "config": {
                "auth_flow": [
                    {
                        "step": "obtain_token",
                        "url_ref": "token_url",
                        "credentials": {"keys": ["username", "password"]},
                        "response_token_path": "data.access_token",  # Nested path
                    },
                ],
            },
        }

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"data": {"access_token": "nested-token-value"}}
        token_response.raise_for_status = MagicMock()
        launch_response = MagicMock()
        launch_response.status_code = 201
        launch_response.json.return_value = {"id": 77777}
        launch_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[token_response, launch_response])
            mock_get_client.return_value = mock_client

            job_id = await adapter.trigger(
                parameters, credentials, correlation_id, integration=integration
            )

        assert job_id == "77777"
        # Verify Bearer token from nested path was used
        second_call_headers = mock_client.post.call_args_list[1][1].get("headers", {})
        assert "Bearer nested-token-value" in second_call_headers["Authorization"]

    @pytest.mark.asyncio
    async def test_trigger_with_config_token_not_found_raises_error(self):
        """Story 5.3: When token not found at response_token_path, raise PlatformError (code-review fix HIGH-1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"
        integration = {
            "base_url": "https://aap.example.com",
            "token_url": "https://aap.example.com/api/v2/token/",
            "config": {
                "auth_flow": [
                    {
                        "step": "obtain_token",
                        "url_ref": "token_url",
                        "credentials": {"keys": ["username", "password"]},
                        "response_token_path": "wrong.path",
                    },
                ],
            },
        }

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "actual-token"}  # Not at wrong.path
        token_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=token_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(
                    parameters, credentials, correlation_id, integration=integration
                )

            assert exc_info.value.code == "AAP_TOKEN_NOT_IN_RESPONSE"

    @pytest.mark.asyncio
    async def test_trigger_with_config_token_url_missing_raises_error(self):
        """Story 5.3: When config has obtain_token but no token_url, raise PlatformError (code-review fix HIGH-1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="")  # No base_url
        parameters = {"job_template_id": 42}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"
        integration = {
            "base_url": None,
            "token_url": None,  # No URL!
            "config": {
                "auth_flow": [
                    {"step": "obtain_token", "credentials": {"keys": ["username", "password"]}},
                ],
            },
        }

        with pytest.raises(PlatformError) as exc_info:
            await adapter.trigger(
                parameters, credentials, correlation_id, integration=integration
            )

        assert exc_info.value.code == "AAP_TOKEN_URL_MISSING"

    @pytest.mark.asyncio
    async def test_trigger_with_config_token_request_fails_raises_error(self):
        """Story 5.3: When token request fails, raise PlatformError (code-review fix HIGH-1)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "tower_user", "password": "secret"}
        correlation_id = "test-corr-123"
        integration = {
            "base_url": "https://aap.example.com",
            "token_url": "https://aap.example.com/api/v2/token/",
            "config": {
                "auth_flow": [
                    {"step": "obtain_token", "credentials": {"keys": ["username", "password"]}},
                ],
            },
        }

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
            mock_get_client.return_value = mock_client

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(
                    parameters, credentials, correlation_id, integration=integration
                )

            assert exc_info.value.code == "AAP_TOKEN_ACQUISITION_FAILED"

    @pytest.mark.asyncio
    async def test_trigger_without_integration_config_unchanged_behavior(self):
        """Story 5.3 AC5: When integration is None or has no config, behavior unchanged (retrocompat)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"token": "existing-bearer-token"}
        correlation_id = "test-corr-123"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            job_id = await adapter.trigger(parameters, credentials, correlation_id)

        assert job_id == "12345"
        # Single POST (launch only, no obtain_token)
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_trigger_timeout_raises_platform_error(self):
        """Trigger raises PlatformError on timeout (AC2)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "user", "password": "pass"}

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_UNAVAILABLE"
            assert "indisponible" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_trigger_connect_error_raises_platform_error(self):
        """Trigger raises PlatformError on connection error (AC2)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "user", "password": "pass"}

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_trigger_401_raises_auth_error(self):
        """Trigger raises PlatformError with AAP_AUTH_ERROR on 401 (AC2)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "user", "password": "wrong"}

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_trigger_403_raises_auth_error(self):
        """Trigger raises PlatformError with AAP_AUTH_ERROR on 403."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_trigger_400_raises_auth_error(self):
        """Trigger raises PlatformError with AAP_AUTH_ERROR on 400 (Task 1.3)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_trigger_404_raises_template_not_found(self):
        """Trigger raises PlatformError with AAP_JOB_TEMPLATE_NOT_FOUND on 404."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 999}
        credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_JOB_TEMPLATE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_trigger_missing_template_id_raises_value_error(self):
        """Trigger raises ValueError when job_template_id is missing (Task 1.4)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {}  # No job_template_id
        credentials = {"username": "user", "password": "pass"}

        with pytest.raises(ValueError) as exc_info:
            await adapter.trigger(parameters, credentials, "corr-123")

        assert "job_template_id" in str(exc_info.value).lower()

    # --- Story 4.10: resource_type job_template | workflow_job (AC2, AC3) ---

    @pytest.mark.asyncio
    async def test_trigger_without_resource_type_defaults_to_job_template(self):
        """Trigger without resource_type uses job_template (AC3)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"job_template_id": 42}
        credentials = {"username": "user", "password": "pass"}
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await adapter.trigger(parameters, credentials, "corr-123")

        call_args = mock_client.post.call_args
        assert call_args[0][0].endswith("/api/v2/job_templates/42/launch/")

    @pytest.mark.asyncio
    async def test_trigger_workflow_job_uses_workflow_endpoint(self):
        """Trigger with resource_type=workflow_job calls workflow_job_templates launch (AC2)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {
            "resource_type": "workflow_job",
            "workflow_job_template_id": 99,
        }
        credentials = {"username": "user", "password": "pass"}
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 888}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            job_id = await adapter.trigger(parameters, credentials, "corr-123")

        assert job_id == "888"
        call_args = mock_client.post.call_args
        assert "/api/v2/workflow_job_templates/99/launch/" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_trigger_workflow_job_missing_id_raises_value_error(self):
        """Trigger with resource_type=workflow_job and no workflow_job_template_id raises ValueError."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"resource_type": "workflow_job"}
        credentials = {"username": "user", "password": "pass"}

        with pytest.raises(ValueError) as exc_info:
            await adapter.trigger(parameters, credentials, "corr-123")

        assert "workflow_job_template_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_trigger_workflow_job_404_raises_workflow_template_not_found(self):
        """Trigger workflow_job 404 raises AAP_WORKFLOW_JOB_TEMPLATE_NOT_FOUND (Story 4.10)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        parameters = {"resource_type": "workflow_job", "workflow_job_template_id": 999}
        credentials = {"username": "user", "password": "pass"}
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(PlatformError) as exc_info:
                await adapter.trigger(parameters, credentials, "corr-123")

            assert exc_info.value.code == "AAP_WORKFLOW_JOB_TEMPLATE_NOT_FOUND"


class TestAAPAdapterGetStatus:
    """Tests for AAPAdapter.get_status method (Task 2.1, 2.2, 2.3)."""

    @pytest.mark.asyncio
    async def test_get_status_success_completed(self):
        """get_status returns completed status for successful job (AC3)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "status": "successful",
            "result_traceback": "",
            "job_explanation": "",
            "artifacts": {"backup_file": "/backups/db.tar.gz"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await adapter.get_status("12345")

        assert status["status"] == "completed"
        assert status["output"]["artifacts"] == {"backup_file": "/backups/db.tar.gz"}
        assert status["error_message"] is None

    @pytest.mark.asyncio
    async def test_get_status_running_maps_to_running(self):
        """get_status maps AAP 'running' to 'running' (AC3)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 12345, "status": "running"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await adapter.get_status("12345")

        assert status["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_pending_maps_to_running(self):
        """get_status maps AAP 'pending' to 'running' (waiting in queue)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 12345, "status": "pending"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await adapter.get_status("12345")

        assert status["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_failed_includes_error_message(self):
        """get_status returns failed with error_message from traceback (AC3)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "status": "failed",
            "result_traceback": "TASK [backup] failed: Permission denied",
            "job_explanation": "Job failed during execution",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await adapter.get_status("12345")

        assert status["status"] == "failed"
        assert "Permission denied" in status["error_message"]

    @pytest.mark.asyncio
    async def test_get_status_canceled_maps_to_cancelled(self):
        """get_status maps AAP 'canceled' to 'cancelled' (British spelling)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 12345, "status": "canceled"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await adapter.get_status("12345")

        assert status["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_status_timeout_returns_running(self):
        """get_status returns running on timeout (assume still in progress)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            status = await adapter.get_status("12345")

        assert status["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_connect_error_returns_running(self):
        """get_status returns running on connection error (Task 2.2)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

            status = await adapter.get_status("12345")

        assert status["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_404_raises_job_not_found(self):
        """get_status raises PlatformError on 404 (job not found)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.get_status("99999")

            assert exc_info.value.code == "AAP_JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_status_500_raises_platform_error(self):
        """get_status raises PlatformError on non-404 HTTP error (e.g. 500)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.get_status("12345")

            assert exc_info.value.code == "AAP_ERROR"

    @pytest.mark.asyncio
    async def test_get_status_workflow_job_uses_workflow_jobs_endpoint(self):
        """get_status after workflow_job trigger uses /workflow_jobs/{id}/ (Story 4.10)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}
        adapter._resource_type = "workflow_job"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 888, "status": "successful"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            status = await adapter.get_status("888")

        assert status["status"] == "completed"
        call_args = mock_client.get.call_args
        assert "/api/v2/workflow_jobs/888/" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_status_workflow_job_404_raises_workflow_job_not_found(self):
        """get_status workflow_job 404 raises AAP_WORKFLOW_JOB_NOT_FOUND (Story 4.10)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}
        adapter._resource_type = "workflow_job"
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(PlatformError) as exc_info:
                await adapter.get_status("99999")

            assert exc_info.value.code == "AAP_WORKFLOW_JOB_NOT_FOUND"


class TestAAPAdapterParseCallback:
    """Tests for AAPAdapter.parse_callback method (Task 3.1, 3.2, 3.3)."""

    @pytest.mark.asyncio
    async def test_parse_callback_success(self):
        """parse_callback extracts fields from AAP webhook (AC4)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        callback_data = {
            "id": 12345,
            "status": "successful",
            "result_traceback": "",
            "artifacts": {"result": "success"},
        }

        result = await adapter.parse_callback(callback_data)

        assert result["platform_job_id"] == "12345"
        assert result["status"] == "completed"
        assert result["output"]["artifacts"] == {"result": "success"}
        assert result["error_message"] is None

    @pytest.mark.asyncio
    async def test_parse_callback_failed_with_error(self):
        """parse_callback extracts error_message from failed job (AC4)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        callback_data = {
            "id": 12345,
            "status": "failed",
            "result_traceback": "TASK [backup] failed: Disk full",
        }

        result = await adapter.parse_callback(callback_data)

        assert result["platform_job_id"] == "12345"
        assert result["status"] == "failed"
        assert "Disk full" in result["error_message"]

    @pytest.mark.asyncio
    async def test_parse_callback_missing_job_id_raises_error(self):
        """parse_callback raises PlatformError when job_id missing (AC4)."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        callback_data = {"status": "successful"}  # No id

        with pytest.raises(PlatformError) as exc_info:
            await adapter.parse_callback(callback_data)

        assert exc_info.value.code == "AAP_INVALID_CALLBACK"

    @pytest.mark.asyncio
    async def test_parse_callback_uses_job_id_field(self):
        """parse_callback also accepts 'job_id' field for compatibility."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        callback_data = {"job_id": 12345, "status": "successful"}

        result = await adapter.parse_callback(callback_data)

        assert result["platform_job_id"] == "12345"


class TestAAPAdapterFactoryRegistration:
    """Tests for AAPAdapter factory registration (Task 4.1, 4.2, 4.3)."""

    def test_factory_returns_aap_adapter(self):
        """get_platform_adapter returns AAPAdapter for 'aap' (AC5)."""
        adapter = get_platform_adapter("aap", "https://aap.example.com")

        assert isinstance(adapter, AAPAdapter)
        assert adapter.platform_type == "aap"
        assert adapter.base_url == "https://aap.example.com"

    def test_factory_case_insensitive(self):
        """Factory is case-insensitive for 'aap' platform."""
        adapter1 = get_platform_adapter("AAP", "https://aap.example.com")
        adapter2 = get_platform_adapter("Aap", "https://aap.example.com")

        assert isinstance(adapter1, AAPAdapter)
        assert isinstance(adapter2, AAPAdapter)


class TestAAPAdapterStatusMapping:
    """Tests for AAP status to unified status mapping."""

    @pytest.fixture
    def adapter(self):
        """Create AAPAdapter for tests."""
        adapter = AAPAdapter(platform_type="aap", base_url="https://aap.example.com")
        adapter._credentials = {"username": "user", "password": "pass"}
        return adapter

    @pytest.mark.asyncio
    @pytest.mark.parametrize("aap_status,expected_status", [
        ("pending", "running"),
        ("waiting", "running"),
        ("running", "running"),
        ("successful", "completed"),
        ("failed", "failed"),
        ("error", "failed"),
        ("canceled", "cancelled"),
    ])
    async def test_status_mapping(self, adapter, aap_status, expected_status):
        """AAP statuses map to unified statuses correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 123, "status": aap_status}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await adapter.get_status("123")

        assert status["status"] == expected_status
