"""Base adapter interface for platform integrations (Story 4.3, Task 5.1).

Defines the Strategy Pattern interface for platform adapters (AAP, Terraform, etc.).
Each platform adapter must implement this interface for the execution engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Abstract base class for platform adapters (Strategy Pattern).

    All platform adapters (AAP, Terraform, GitHub Actions, Azure DevOps, etc.)
    must implement this interface to be used by the execution engine.

    The adapter is responsible for:
    - Triggering executions on the external platform
    - Polling/receiving status updates
    - Parsing callback data from webhooks

    Attributes:
        platform_type: Type of platform (e.g., "aap", "terraform")
        base_url: Base URL of the platform API
    """

    def __init__(self, platform_type: str, base_url: str) -> None:
        """Initialize adapter with platform configuration.

        Args:
            platform_type: Type of platform
            base_url: Base URL for platform API
        """
        self.platform_type = platform_type
        self.base_url = base_url

    @abstractmethod
    async def trigger(
        self,
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        correlation_id: str,
        *,
        integration: dict[str, Any] | None = None,
    ) -> str:
        """Trigger execution on the platform (Story 4.3, Task 5.1, 5.3).

        Args:
            parameters: Execution parameters (action-specific)
            credentials: Credentials from Vault (e.g., {"username": ..., "password": ...})
            correlation_id: Request correlation ID for tracing
            integration: Optional integration dict with token_url, config (flow steps) for config-driven auth (Story 5.3)

        Returns:
            platform_job_id: External job ID from the platform (e.g., AAP job ID)

        Raises:
            PlatformError: If trigger fails (connection, auth, validation)
        """
        ...

    @abstractmethod
    async def get_status(self, platform_job_id: str) -> dict[str, Any]:
        """Get current status of a platform job (Story 4.3, Task 5.1).

        Args:
            platform_job_id: External job ID from trigger()

        Returns:
            Dict with status information:
            {
                "status": "running" | "completed" | "failed" | "cancelled",
                "output": {...},  # Job output/results
                "error_message": "..." | None,  # Error if failed
            }

        Raises:
            PlatformError: If status check fails
        """
        ...

    @abstractmethod
    async def parse_callback(self, callback_data: dict[str, Any]) -> dict[str, Any]:
        """Parse webhook callback data from platform (Story 4.3, Task 5.1).

        Called when the platform sends a webhook notification about job completion.

        Args:
            callback_data: Raw webhook payload from platform

        Returns:
            Dict with parsed information:
            {
                "platform_job_id": "...",
                "status": "completed" | "failed",
                "output": {...},
                "error_message": "..." | None,
            }

        Raises:
            PlatformError: If callback data is invalid
        """
        ...


class MockAdapter(BaseAdapter):
    """Mock adapter for testing (Story 4.3, Task 5.4).

    Used in development and tests when no real platform is available.
    Returns predictable responses for testing the execution engine.
    """

    def __init__(self, platform_type: str = "mock", base_url: str = "http://mock") -> None:
        """Initialize mock adapter."""
        super().__init__(platform_type, base_url)
        self._job_counter = 0

    async def trigger(
        self,
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        correlation_id: str,
        *,
        integration: dict[str, Any] | None = None,
    ) -> str:
        """Return mock job ID."""
        self._job_counter += 1
        return f"mock-job-{self._job_counter}"

    async def get_status(self, platform_job_id: str) -> dict[str, Any]:
        """Return mock completed status."""
        return {
            "status": "completed",
            "output": {"message": f"Mock job {platform_job_id} completed"},
            "error_message": None,
        }

    async def parse_callback(self, callback_data: dict[str, Any]) -> dict[str, Any]:
        """Parse mock callback data."""
        return {
            "platform_job_id": callback_data.get("job_id", "unknown"),
            "status": callback_data.get("status", "completed"),
            "output": callback_data.get("output", {}),
            "error_message": callback_data.get("error"),
        }
