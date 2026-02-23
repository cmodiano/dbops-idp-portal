"""
Base adapter interfaces for platform integrations.

Defines the contracts that platform adapters must implement.

Story 27.1-27.3: Strategy Pattern for platform-agnostic execution.
Story 34.15: ISP — Split BaseAdapter into ITriggerableAdapter (core) and
  ICancellableAdapter (optional). New adapters that do not support remote
  cancellation inherit from ITriggerableAdapter only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ITriggerableAdapter(ABC):
    """Interface core — toute plateforme doit supporter trigger/status/logs."""

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


class ICancellableAdapter(ABC):
    """Interface optionnelle ISP — plateformes supportant l'annulation distante.

    Les adapters qui ne supportent pas l'annulation n'héritent PAS de cette classe.
    Le code appelant vérifie isinstance(adapter, ICancellableAdapter) avant d'appeler
    cancel_execution().
    """

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


class BaseAdapter(ITriggerableAdapter, ICancellableAdapter):
    """Combinaison des deux interfaces — compatibilité ascendante (Story 27.1-27.3).

    Les adapters existants (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud)
    héritent de BaseAdapter sans modification.

    Pour les nouveaux adapters ne supportant pas l'annulation distante (ex. Splunk,
    adapters read-only), hériter de ITriggerableAdapter uniquement — NE PAS hériter
    de BaseAdapter. Le code appelant vérifie isinstance(adapter, ICancellableAdapter)
    avant d'appeler cancel_execution() (Story 34.15 — ISP).
    """


__all__ = ["ITriggerableAdapter", "ICancellableAdapter", "BaseAdapter"]
