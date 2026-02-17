"""
Inventory models and data structures.
Story 13.1 - Target data structures (no DB table - data comes from external sources).
"""

from dataclasses import dataclass
from typing import Any


class TargetEnvironment:
    """Environment choices for targets."""
    DEV = 'dev'
    STAGING = 'staging'
    PROD = 'prod'

    CHOICES = [
        (DEV, 'Développement'),
        (STAGING, 'Certification'),
        (PROD, 'Production'),
    ]

    VALUES = [DEV, STAGING, PROD]


class TargetType:
    """Target type choices."""
    SERVER = 'server'
    DATABASE = 'database'
    GROUP = 'group'
    CLUSTER = 'cluster'
    OTHER = 'other'

    CHOICES = [
        (SERVER, 'Serveur'),
        (DATABASE, 'Base de données'),
        (GROUP, 'Groupe'),
        (CLUSTER, 'Cluster'),
        (OTHER, 'Autre'),
    ]

    VALUES = [SERVER, DATABASE, GROUP, CLUSTER, OTHER]


@dataclass
class Target:
    """
    Target data structure.
    Represents an inventory item from external source (API or DBOPS_INVENTORY).
    No DB persistence - data comes from inventory integration or fallback.
    """
    name: str
    environment: str
    target_type: str = TargetType.SERVER
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'name': self.name,
            'environment': self.environment,
            'target_type': self.target_type,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Target':
        """Create Target from dictionary."""
        return cls(
            name=data.get('name', ''),
            environment=data.get('environment', TargetEnvironment.DEV),
            target_type=data.get('target_type', TargetType.SERVER),
            metadata=data.get('metadata'),
        )
