"""Tests for base adapter and factory (Story 4.3, Task 6.5).

Tests BaseAdapter and get_platform_adapter factory:
- BaseAdapter abstract methods
- MockAdapter implementation
- Factory function platform selection
"""

import pytest
from abc import ABC

from app.adapters import get_platform_adapter, register_adapter, BaseAdapter, MockAdapter


class TestBaseAdapter:
    """Tests for BaseAdapter abstract class (Task 5.1)."""

    def test_base_adapter_is_abstract(self):
        """BaseAdapter cannot be instantiated directly."""
        assert issubclass(BaseAdapter, ABC)

    def test_base_adapter_requires_trigger_implementation(self):
        """Subclass must implement trigger method."""
        class IncompleteAdapter(BaseAdapter):
            async def get_status(self, platform_job_id: str):
                return {}

            async def parse_callback(self, callback_data: dict):
                return {}

        with pytest.raises(TypeError, match="trigger"):
            IncompleteAdapter("test", "http://test")

    def test_base_adapter_requires_get_status_implementation(self):
        """Subclass must implement get_status method."""
        class IncompleteAdapter(BaseAdapter):
            async def trigger(self, parameters, credentials, correlation_id):
                return "job-1"

            async def parse_callback(self, callback_data: dict):
                return {}

        with pytest.raises(TypeError, match="get_status"):
            IncompleteAdapter("test", "http://test")

    def test_base_adapter_requires_parse_callback_implementation(self):
        """Subclass must implement parse_callback method."""
        class IncompleteAdapter(BaseAdapter):
            async def trigger(self, parameters, credentials, correlation_id):
                return "job-1"

            async def get_status(self, platform_job_id: str):
                return {}

        with pytest.raises(TypeError, match="parse_callback"):
            IncompleteAdapter("test", "http://test")


class TestMockAdapter:
    """Tests for MockAdapter (Task 5.4)."""

    def test_mock_adapter_initializes(self):
        """MockAdapter can be instantiated."""
        adapter = MockAdapter()
        assert adapter.platform_type == "mock"
        assert adapter.base_url == "http://mock"

    @pytest.mark.asyncio
    async def test_mock_adapter_trigger_returns_job_id(self):
        """MockAdapter.trigger returns incrementing job IDs."""
        adapter = MockAdapter()

        job1 = await adapter.trigger({}, {}, "correlation-1")
        job2 = await adapter.trigger({}, {}, "correlation-2")

        assert job1 == "mock-job-1"
        assert job2 == "mock-job-2"

    @pytest.mark.asyncio
    async def test_mock_adapter_get_status_returns_completed(self):
        """MockAdapter.get_status returns completed status."""
        adapter = MockAdapter()

        status = await adapter.get_status("mock-job-1")

        assert status["status"] == "completed"
        assert "output" in status
        assert status["error_message"] is None

    @pytest.mark.asyncio
    async def test_mock_adapter_parse_callback_extracts_fields(self):
        """MockAdapter.parse_callback parses webhook data."""
        adapter = MockAdapter()
        callback_data = {
            "job_id": "mock-job-1",
            "status": "completed",
            "output": {"result": "success"},
            "error": None,
        }

        result = await adapter.parse_callback(callback_data)

        assert result["platform_job_id"] == "mock-job-1"
        assert result["status"] == "completed"
        assert result["output"] == {"result": "success"}
        assert result["error_message"] is None


class TestGetPlatformAdapter:
    """Tests for get_platform_adapter factory (Task 5.3)."""

    def test_get_platform_adapter_returns_mock_adapter(self):
        """Factory returns MockAdapter for 'mock' platform."""
        adapter = get_platform_adapter("mock", "http://mock")

        assert isinstance(adapter, MockAdapter)
        assert adapter.platform_type == "mock"
        assert adapter.base_url == "http://mock"

    def test_get_platform_adapter_case_insensitive(self):
        """Factory is case-insensitive for platform type."""
        adapter1 = get_platform_adapter("MOCK", "http://mock")
        adapter2 = get_platform_adapter("Mock", "http://mock")
        adapter3 = get_platform_adapter("mock", "http://mock")

        assert isinstance(adapter1, MockAdapter)
        assert isinstance(adapter2, MockAdapter)
        assert isinstance(adapter3, MockAdapter)

    def test_get_platform_adapter_raises_for_unsupported(self):
        """Factory raises ValueError for unsupported platform."""
        with pytest.raises(ValueError) as exc_info:
            get_platform_adapter("unsupported_platform", "http://test")

        assert "Plateforme non supportée" in str(exc_info.value)
        assert "unsupported_platform" in str(exc_info.value)
        assert "mock" in str(exc_info.value)  # Lists available platforms

    def test_get_platform_adapter_sets_base_url(self):
        """Factory passes base_url to adapter."""
        adapter = get_platform_adapter("mock", "http://custom-url:8080")

        assert adapter.base_url == "http://custom-url:8080"


class TestRegisterAdapter:
    """Tests for register_adapter extensibility."""

    def test_register_adapter_adds_new_platform(self):
        """register_adapter allows adding new platform types."""
        class CustomAdapter(BaseAdapter):
            async def trigger(self, parameters, credentials, correlation_id):
                return "custom-job"

            async def get_status(self, platform_job_id):
                return {"status": "completed"}

            async def parse_callback(self, callback_data):
                return {}

        register_adapter("custom", CustomAdapter)

        adapter = get_platform_adapter("custom", "http://custom")
        assert isinstance(adapter, CustomAdapter)

    def test_register_adapter_overwrites_existing(self):
        """register_adapter can override existing platform type."""
        class NewMockAdapter(BaseAdapter):
            async def trigger(self, parameters, credentials, correlation_id):
                return "new-mock-job"

            async def get_status(self, platform_job_id):
                return {"status": "completed"}

            async def parse_callback(self, callback_data):
                return {}

        original_adapter = get_platform_adapter("mock", "http://mock")
        register_adapter("mock", NewMockAdapter)
        new_adapter = get_platform_adapter("mock", "http://mock")

        assert isinstance(original_adapter, MockAdapter)
        assert isinstance(new_adapter, NewMockAdapter)

        # Reset to original
        register_adapter("mock", MockAdapter)
