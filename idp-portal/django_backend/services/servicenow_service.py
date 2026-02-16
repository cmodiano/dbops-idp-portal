"""
ServiceNowService — ServiceNow ITSM integration service (placeholder).

Story 27.9: ServiceNow is classified as a Service (consumed by the portal for
change management), not a Platform adapter (does not execute jobs).

Future implementation will provide:
- create_change(): Create a ServiceNow change request
- update_change(): Update a change request status
- get_change_status(): Query change request status
- close_change(): Close a completed change request
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class ServiceNowService:
    """ServiceNow ITSM service client — placeholder, NOT yet implemented.

    ServiceNow is a consumed service for change management (opening, updating,
    closing change requests during execution flows). It does NOT execute jobs
    and therefore does NOT implement BaseAdapter.

    **Status:** Placeholder only. Not used in production code paths.
    Only instantiated via ``get_service_client('servicenow')`` in test factories.

    **Future implementation** (backlog):
    - ``create_change()`` — Create a ServiceNow change request
    - ``update_change()`` — Update a change request status
    - ``get_change_status()`` — Query change request status
    - ``close_change()`` — Close a completed change request

    Configuration will come from Integration model (type='servicenow'):
    - base_url: ServiceNow instance URL
    - credential_ref: Vault reference for authentication
    - config: Additional configuration (instance, table, etc.)
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        **kwargs: object,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        logger.info("servicenow_service_initialized", base_url=self.base_url)

    def create_change(self, **kwargs: object) -> None:
        """Create a ServiceNow change request (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.create_change() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )

    def update_change(self, change_id: str, **kwargs: object) -> None:
        """Update a ServiceNow change request (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.update_change() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )

    def get_change_status(self, change_id: str) -> None:
        """Query ServiceNow change request status (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.get_change_status() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )

    def close_change(self, change_id: str, **kwargs: object) -> None:
        """Close a ServiceNow change request (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.close_change() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )
