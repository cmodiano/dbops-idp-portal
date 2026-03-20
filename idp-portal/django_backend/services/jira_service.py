"""
JiraService — Jira REST API service for issue management.

Story 27.10: Jira integration as a consumed service (not a platform adapter).
Supports Jira Cloud (REST API v3) and Server/Data Center (REST API v2).
"""
from __future__ import annotations

import asyncio
import random

import httpx
import structlog

from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)

# Jira API version (Cloud v3, Server v2 — caller chooses via base_url)
JIRA_API_VERSION = "3"

# Retry config for transient errors (500, 503, timeout)
MAX_RETRIES = 3
_TRANSIENT_STATUS_CODES = frozenset({500, 503})

# Error code mapping for non-retryable HTTP errors
_ERROR_CODES: dict[int, str] = {
    401: "JIRA_AUTH_FAILED",
    403: "JIRA_PERMISSION_DENIED",
    404: "JIRA_RESOURCE_NOT_FOUND",
    409: "JIRA_CONFLICT",
    429: "JIRA_RATE_LIMITED",
}


class JiraService(IHealthCheckable):
    """Jira integration service client.

    Jira is a consumed service (issue tracking), not a platform that executes
    jobs. It does NOT implement BaseAdapter.

    Requires base_url (Jira instance) and auth_headers with Basic Auth or PAT.
    Typically instantiated via the service factory get_service_client('jira').
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = timeout

    async def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """Create a Jira issue.

        Args:
            project_key: Project key (e.g. 'PROJ').
            issue_type: Issue type name (Bug, Task, Story, Epic).
            summary: Issue title.
            description: Optional description text.
            assignee: Optional assignee username.
            labels: Optional list of labels.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'issue_key', 'issue_id', 'url'.

        Raises:
            ServiceUnavailableError: On Jira API errors.
        """
        url = f"{self.base_url}/rest/api/{JIRA_API_VERSION}/issue"
        payload: dict = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
            }
        }
        if description:
            payload["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        if assignee:
            payload["fields"]["assignee"] = {"name": assignee}
        if labels:
            payload["fields"]["labels"] = labels

        logger.info(
            "jira_create_issue_request",
            project_key=project_key,
            issue_type=issue_type,
            correlation_id=correlation_id,
        )

        data = await self._request_with_retry(
            "POST", url, json_payload=payload, correlation_id=correlation_id
        )

        result = {
            "issue_key": data.get("key"),
            "issue_id": data.get("id"),
            "url": data.get("self"),
        }

        logger.info(
            "jira_issue_created",
            issue_key=result["issue_key"],
            issue_id=result["issue_id"],
            correlation_id=correlation_id,
        )

        return result

    async def update_issue(
        self,
        issue_key: str,
        correlation_id: str | None = None,
        **updates: object,
    ) -> dict:
        """Update a Jira issue.

        Args:
            issue_key: Issue key (e.g. 'PROJ-123').
            correlation_id: Tracing correlation ID.
            **updates: Fields to update (status, assignee, labels, etc.).

        Returns:
            Dict with 'issue_key', 'status' = 'updated'.

        Raises:
            ServiceUnavailableError: On Jira API errors.
        """
        url = f"{self.base_url}/rest/api/{JIRA_API_VERSION}/issue/{issue_key}"
        payload: dict = {"fields": {}}

        if "status" in updates:
            payload["fields"]["status"] = {"name": updates["status"]}
        if "assignee" in updates:
            payload["fields"]["assignee"] = {"name": updates["assignee"]}
        if "labels" in updates:
            payload["fields"]["labels"] = updates["labels"]
        if "summary" in updates:
            payload["fields"]["summary"] = updates["summary"]

        logger.info(
            "jira_update_issue_request",
            issue_key=issue_key,
            fields=list(payload["fields"].keys()),
            correlation_id=correlation_id,
        )

        await self._request_with_retry(
            "PUT",
            url,
            json_payload=payload,
            correlation_id=correlation_id,
            expect_no_content=True,
        )

        logger.info(
            "jira_issue_updated",
            issue_key=issue_key,
            correlation_id=correlation_id,
        )

        return {"issue_key": issue_key, "status": "updated"}

    async def get_issue(
        self,
        issue_key: str,
        correlation_id: str | None = None,
    ) -> dict:
        """Retrieve a Jira issue.

        Args:
            issue_key: Issue key (e.g. 'PROJ-123').
            correlation_id: Tracing correlation ID.

        Returns:
            Full Jira issue data dict.

        Raises:
            ServiceUnavailableError: On Jira API errors.
        """
        url = f"{self.base_url}/rest/api/{JIRA_API_VERSION}/issue/{issue_key}"

        logger.info(
            "jira_get_issue_request",
            issue_key=issue_key,
            correlation_id=correlation_id,
        )

        data = await self._request_with_retry(
            "GET", url, correlation_id=correlation_id
        )

        logger.info(
            "jira_issue_retrieved",
            issue_key=issue_key,
            correlation_id=correlation_id,
        )

        return data

    async def add_comment(
        self,
        issue_key: str,
        comment: str,
        correlation_id: str | None = None,
    ) -> dict:
        """Add a comment to a Jira issue.

        Args:
            issue_key: Issue key (e.g. 'PROJ-123').
            comment: Comment text.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'comment_id', 'issue_key', 'url'.

        Raises:
            ServiceUnavailableError: On Jira API errors.
        """
        url = f"{self.base_url}/rest/api/{JIRA_API_VERSION}/issue/{issue_key}/comment"
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }

        logger.info(
            "jira_add_comment_request",
            issue_key=issue_key,
            correlation_id=correlation_id,
        )

        data = await self._request_with_retry(
            "POST", url, json_payload=payload, correlation_id=correlation_id
        )

        result = {
            "comment_id": data.get("id"),
            "issue_key": issue_key,
            "url": data.get("self"),
        }

        logger.info(
            "jira_comment_added",
            issue_key=issue_key,
            comment_id=result["comment_id"],
            correlation_id=correlation_id,
        )

        return result

    # ------------------------------------------------------------------
    # Internal retry helper
    # ------------------------------------------------------------------

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict | None = None,
        correlation_id: str | None = None,
        expect_no_content: bool = False,
    ) -> dict:
        """Execute HTTP request with exponential backoff retry on transient errors."""
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    headers=self.auth_headers,
                    timeout=self.timeout,
                ) as client:
                    if method == "GET":
                        response = await client.get(url)
                    elif method == "POST":
                        response = await client.post(url, json=json_payload)
                    elif method == "PUT":
                        response = await client.put(url, json=json_payload)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    status_code = response.status_code

                    # Success
                    if status_code in (200, 201, 204):
                        if expect_no_content or status_code == 204:
                            return {}
                        return response.json()  # type: ignore[no-any-return]

                    # Transient errors — retry
                    if status_code in _TRANSIENT_STATUS_CODES:
                        last_exc = ServiceUnavailableError(
                            code="JIRA_SERVER_ERROR",
                            message=f"Jira server error {status_code}",
                            details={"status_code": status_code},
                        )
                        if attempt < MAX_RETRIES - 1:
                            delay = random.uniform(0, 2 ** (attempt + 1))
                            logger.warning(
                                "jira_transient_error_retry",
                                status_code=status_code,
                                attempt=attempt + 1,
                                delay=delay,
                                correlation_id=correlation_id,
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise last_exc

                    # Non-retryable client errors
                    error_code = _ERROR_CODES.get(status_code, f"JIRA_ERROR_{status_code}")
                    try:
                        error_body = response.text
                    except Exception as _:  # noqa: BLE001 — graceful-degradation: httpx may raise StreamClosed, DecodeError, etc.
                        error_body = ""

                    logger.error(
                        "jira_api_error",
                        status_code=status_code,
                        error_code=error_code,
                        url=url,
                        correlation_id=correlation_id,
                    )
                    raise ServiceUnavailableError(
                        code=error_code,
                        message=f"Jira API error: {error_body}",
                        details={"status_code": status_code},
                    )

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    delay = random.uniform(0, 2 ** (attempt + 1))
                    logger.warning(
                        "jira_timeout_retry",
                        attempt=attempt + 1,
                        delay=delay,
                        correlation_id=correlation_id,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "jira_timeout",
                    url=url,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                raise ServiceUnavailableError(
                    code="JIRA_TIMEOUT",
                    message="Jira did not respond in time",
                    details={"url": url},
                ) from exc

            except ServiceUnavailableError:
                raise

            except Exception as exc:  # noqa: BLE001 — logged-and-wrapped: unexpected error converted to ServiceUnavailableError with logging
                logger.error(
                    "jira_unexpected_error",
                    url=url,
                    correlation_id=correlation_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise ServiceUnavailableError(
                    code="JIRA_UNKNOWN_ERROR",
                    message="Unexpected error calling Jira",
                    details={"error": str(exc)},
                ) from exc

        # Safety net — should not reach here
        raise ServiceUnavailableError(
            code="JIRA_MAX_RETRIES",
            message=f"Jira max retries ({MAX_RETRIES}) exceeded",
            details={"url": url},
        ) from last_exc

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Ping Jira via GET /rest/api/2/serverInfo et valide l'authentification."""
        from datetime import datetime, timezone as tz
        url = f"{self.base_url}/rest/api/2/serverInfo"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("jira_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("jira_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz.utc),
                error_message=str(exc),
            )
