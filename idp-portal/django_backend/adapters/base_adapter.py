"""
Base adapter interface for platform integrations.

Defines the contract that all platform adapters (AAP, Tower, Azure DevOps,
GitHub Actions, Terraform Cloud, etc.) must implement.

Story 27.1-27.3: Strategy Pattern for platform-agnostic execution.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """Abstract base class for platform integration adapters.

    All platform adapters must implement:
    - trigger(): Launch a job/workflow/pipeline run
    - get_status(): Get current execution status
    - get_job_logs(): Retrieve execution logs
    - cancel_execution(): Cancel a running execution
    """

    @abstractmethod
    async def trigger(
        self,
        **kwargs,
    ) -> dict:
        """Launch an execution on the target platform.

        Args:
            **kwargs: Platform-specific parameters (job_template_id,
                     pipeline_id, extra_vars, template_parameters, etc.)

        Returns:
            dict with at minimum:
            - platform_job_id: str - Remote job/run ID
            - status: str - Initial IDP Portal status
            - url: str (optional) - Platform URL to view execution

        Raises:
            ServiceUnavailableError: If platform is unreachable or returns error
        """
        ...

    @abstractmethod
    async def get_status(
        self,
        platform_job_id: str,
        **kwargs,
    ) -> dict:
        """Get current status of a platform execution.

        Args:
            platform_job_id: Remote job/run ID
            **kwargs: Platform-specific parameters (resource_type, pipeline_id, etc.)

        Returns:
            dict with at minimum:
            - status: str - IDP Portal status (RUNNING, COMPLETED, FAILED, etc.)
            - Platform-specific fields (aap_status, azure_devops_state, etc.)

        Raises:
            ServiceUnavailableError: If platform is unreachable
        """
        ...

    @abstractmethod
    async def get_job_logs(
        self,
        platform_job_id: str,
        **kwargs,
    ) -> dict:
        """Retrieve logs for a platform execution.

        Args:
            platform_job_id: Remote job/run ID
            **kwargs: Platform-specific parameters (resource_type, pipeline_id, etc.)

        Returns:
            dict with:
            - content: str - Log text (concatenated if multiple parts)
            - format: str - Log format (text/plain, application/json, etc.)
            - timestamp: str - ISO timestamp of retrieval
            - complete: bool - True if execution is in terminal state
            - job_status: str - Platform job status at retrieval time

        Raises:
            ServiceUnavailableError: If platform is unreachable or logs unavailable
        """
        ...

    @abstractmethod
    async def cancel_execution(
        self,
        platform_job_id: str,
        **kwargs,
    ) -> None:
        """Cancel a running execution on the platform.

        Args:
            platform_job_id: Remote job/run ID
            **kwargs: Platform-specific parameters (resource_type, pipeline_id, etc.)

        Raises:
            ServiceUnavailableError: If platform is unreachable or cancel fails
        """
        ...
