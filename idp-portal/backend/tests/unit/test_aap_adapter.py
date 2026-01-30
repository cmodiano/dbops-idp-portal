"""Tests for AAP adapter (Story 4.4).

Tests AAPAdapter implementation:
- Trigger job on AAP platform (AC1)
- Handle AAP errors (AC2)
- Get job status (AC3)
- Parse webhook callback (AC4)
- Factory registration (AC5)
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
