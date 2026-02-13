"""
AAP (Ansible Automation Platform) adapter for remote execution management.
"""

import structlog

logger = structlog.get_logger(__name__)


class AAPAdapter:
    """Adapter for interacting with Ansible Automation Platform."""

    def cancel_execution(self, platform_job_id: str) -> None:
        """
        Attempt to cancel a running job on AAP.

        Args:
            platform_job_id: The job ID on the AAP platform.

        Raises:
            NotImplementedError: Remote cancellation not yet implemented.
        """
        raise NotImplementedError(
            "AAP remote cancellation not yet implemented"
        )
