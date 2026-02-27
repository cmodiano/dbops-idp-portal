"""
Story 51.1: Interface IHealthCheckable et dataclass HealthCheckResult.

Définit le contrat commun pour les adapters et services supportant le health check.
Pattern ISP : IHealthCheckable est une interface optionnelle (comme ICancellableAdapter).
Le code appelant vérifie isinstance(adapter, IHealthCheckable) avant d'appeler health_check().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class HealthCheckStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    status: HealthCheckStatus
    checked_at: datetime
    error_message: str | None = None


class IHealthCheckable(ABC):
    """Interface optionnelle — adaptateurs et services supportant le health check.

    Les adapters/services qui ne supportent pas le health check n'héritent PAS de cette
    classe. Le code appelant vérifie isinstance(obj, IHealthCheckable) avant d'appeler
    health_check().
    """

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Effectue un ping minimal + validation credentials.

        Returns:
            HealthCheckResult avec status ok/error/unknown, timestamp, message d'erreur.

        Note:
            Ne doit PAS lever d'exception non catchée — capturer et retourner
            HealthCheckResult(status=HealthCheckStatus.ERROR, error_message=str(exc)).
        """
        ...
