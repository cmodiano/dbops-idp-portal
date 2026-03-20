"""
Tests for ISP split of BaseAdapter (Story 34.15).

Validates:
- ITriggerableAdapter alone → non-cancellable
- BaseAdapter (full) → cancellable
- _attempt_remote_cancellation() skips remote cancel for non-cancellable adapters
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from adapters.base_adapter import BaseAdapter, ICancellableAdapter, ITriggerableAdapter


# ---------------------------------------------------------------------------
# Concrete test adapters
# ---------------------------------------------------------------------------


class MinimalAdapter(ITriggerableAdapter):
    """Adapter sans annulation — futur use case (ex. Splunk, read-only)."""

    async def trigger(self, **kwargs) -> dict:
        return {}

    async def get_status(self, platform_job_id: str, **kwargs) -> dict:
        return {}

    async def get_job_logs(self, platform_job_id: str, **kwargs) -> dict:
        return {}


class FullAdapter(BaseAdapter):
    """Adapter complet avec annulation — comme tous les adapters existants."""

    async def trigger(self, **kwargs) -> dict:
        return {}

    async def get_status(self, platform_job_id: str, **kwargs) -> dict:
        return {}

    async def get_job_logs(self, platform_job_id: str, **kwargs) -> dict:
        return {}

    async def cancel_execution(self, platform_job_id: str, **kwargs) -> None:
        pass


# ---------------------------------------------------------------------------
# AC #5.1 — MinimalAdapter is ITriggerableAdapter but NOT ICancellableAdapter
# ---------------------------------------------------------------------------


def test_minimal_adapter_is_triggerable():
    adapter = MinimalAdapter()
    assert isinstance(adapter, ITriggerableAdapter)


def test_minimal_adapter_not_cancellable():
    adapter = MinimalAdapter()
    assert not isinstance(adapter, ICancellableAdapter)


# ---------------------------------------------------------------------------
# AC #5.2 — FullAdapter (BaseAdapter) is both ITriggerableAdapter and ICancellableAdapter
# ---------------------------------------------------------------------------


def test_full_adapter_is_triggerable():
    adapter = FullAdapter()
    assert isinstance(adapter, ITriggerableAdapter)


def test_full_adapter_is_cancellable():
    adapter = FullAdapter()
    assert isinstance(adapter, ICancellableAdapter)


def test_base_adapter_combines_both_interfaces():
    """BaseAdapter is a subclass of both ITriggerableAdapter and ICancellableAdapter."""
    assert issubclass(BaseAdapter, ITriggerableAdapter)
    assert issubclass(BaseAdapter, ICancellableAdapter)


# ---------------------------------------------------------------------------
# L1 FIX — Vérification régression : les 5 adapters réels héritent de BaseAdapter
# ---------------------------------------------------------------------------


def test_existing_adapters_inherit_base_adapter():
    """Régression guard : les 5 adapters existants héritent de BaseAdapter (cancellable)."""
    from adapters.aap_adapter import AAPAdapter
    from adapters.tower_adapter import TowerAdapter
    from adapters.azure_devops_adapter import AzureDevOpsAdapter
    from adapters.github_actions_adapter import GitHubActionsAdapter
    from adapters.terraform_cloud_adapter import TerraformCloudAdapter

    for adapter_cls in (AAPAdapter, TowerAdapter, AzureDevOpsAdapter, GitHubActionsAdapter, TerraformCloudAdapter):
        assert issubclass(adapter_cls, BaseAdapter), f"{adapter_cls.__name__} must inherit from BaseAdapter"
        assert issubclass(adapter_cls, ICancellableAdapter), f"{adapter_cls.__name__} must be ICancellableAdapter"


# ---------------------------------------------------------------------------
# AC #5.3 — _attempt_remote_cancellation() skips non-cancellable adapter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAttemptRemoteCancellationISP:
    """_attempt_remote_cancellation() respects ISP — skips if adapter is not ICancellableAdapter."""

    def setup_method(self):
        from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory
        from executions.models import ExecutionStatus

        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create(type='aap', base_url='http://aap.example.com', name='AAP Test')
        self.action = ActionFactory.create(status='published', integration=self.integration)
        self.execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        self.execution.set_parameters({'platform_job_id': 'job-non-cancellable'})
        self.execution.save()

    def test_non_cancellable_adapter_skips_remote_cancel_and_logs_warning(self):
        """If adapter does not implement ICancellableAdapter, cancel is skipped and warning is logged."""
        from executions.views.execution_views import ExecutionCancelView

        view = ExecutionCancelView()

        # MinimalAdapter does not implement ICancellableAdapter
        minimal_adapter = MinimalAdapter()

        with patch('executions.views.execution_views.get_platform_adapter', return_value=minimal_adapter), \
             patch('adapters.utils.build_auth_headers', return_value={'Authorization': 'Bearer token'}), \
             patch('executions.views.execution_views.exec_logger') as mock_logger:
            view._attempt_remote_cancellation(self.execution)

        # M1 FIX: Warning logged with cancel_not_supported event and correct context kwargs
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == 'cancel_not_supported'
        assert call_args[1].get('platform_type') == 'aap'
        assert call_args[1].get('execution_id') == str(self.execution.id)

    def test_cancellable_adapter_calls_cancel_execution(self):
        """If adapter implements ICancellableAdapter, cancel_execution is called with correct args."""
        from executions.views.execution_views import ExecutionCancelView
        from unittest.mock import AsyncMock

        view = ExecutionCancelView()

        full_adapter = FullAdapter()
        full_adapter.cancel_execution = AsyncMock(return_value=None)  # type: ignore[method-assign]

        with patch('executions.views.execution_views.get_platform_adapter', return_value=full_adapter), \
             patch('adapters.utils.build_auth_headers', return_value={'Authorization': 'Bearer token'}):
            view._attempt_remote_cancellation(self.execution)

        # M2 FIX: Vérifier que cancel_execution est appelé avec le bon platform_job_id
        full_adapter.cancel_execution.assert_called_once()
        call_args = full_adapter.cancel_execution.call_args
        assert call_args[0][0] == 'job-non-cancellable'


# ---------------------------------------------------------------------------
# Story 86.1: AdapterTimeoutError class tests
# ---------------------------------------------------------------------------

class TestAdapterTimeoutError:
    """Story 86.1 — 5.1: Validate AdapterTimeoutError class."""

    def test_is_subclass_of_service_unavailable_error(self) -> None:
        """AdapterTimeoutError is subclass of ServiceUnavailableError."""
        from core.exceptions import AdapterTimeoutError, ServiceUnavailableError
        assert issubclass(AdapterTimeoutError, ServiceUnavailableError)

    def test_code_is_adapter_timeout(self) -> None:
        """code == 'ADAPTER_TIMEOUT'."""
        from core.exceptions import AdapterTimeoutError
        exc = AdapterTimeoutError(adapter_type="aap")
        assert exc.code == "ADAPTER_TIMEOUT"

    def test_details_contains_adapter_type(self) -> None:
        """details dict contains adapter_type."""
        from core.exceptions import AdapterTimeoutError
        exc = AdapterTimeoutError(adapter_type="aap")
        assert exc.details.get("adapter_type") == "aap"

    def test_with_platform_job_id(self) -> None:
        """platform_job_id is included in details when provided."""
        from core.exceptions import AdapterTimeoutError
        exc = AdapterTimeoutError(adapter_type="tower", platform_job_id="job-123")
        assert exc.details.get("platform_job_id") == "job-123"
        assert exc.details.get("adapter_type") == "tower"

    def test_default_message(self) -> None:
        """Default message is 'Adapter call timed out'."""
        from core.exceptions import AdapterTimeoutError
        exc = AdapterTimeoutError(adapter_type="github_actions")
        assert exc.message == "Adapter call timed out"

    def test_custom_message(self) -> None:
        """Custom message overrides default."""
        from core.exceptions import AdapterTimeoutError
        exc = AdapterTimeoutError(adapter_type="azure_devops", message="Custom timeout msg")
        assert exc.message == "Custom timeout msg"

    def test_extra_details_merged(self) -> None:
        """Additional details dict is merged."""
        from core.exceptions import AdapterTimeoutError
        exc = AdapterTimeoutError(adapter_type="terraform_cloud", details={"url": "https://example.com"})
        assert exc.details.get("url") == "https://example.com"
        assert exc.details.get("adapter_type") == "terraform_cloud"
