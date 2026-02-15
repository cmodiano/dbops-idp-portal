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
    """ServiceNow ITSM service client (placeholder for future implementation).

    ServiceNow is a consumed service for change management (opening, updating,
    closing change requests during execution flows). It does NOT execute jobs
    and therefore does NOT implement BaseAdapter.

    Configuration will come from Integration model (type='servicenow'):
    - base_url: ServiceNow instance URL
    - credential_ref: Vault reference for authentication
    - config: Additional configuration (instance, table, etc.)

    TODO: Implement create_change(), update_change(), get_change_status() methods
    as per integration-type-catalogue.md specification (Story 27.9 placeholder).
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
