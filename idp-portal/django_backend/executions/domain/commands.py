"""
Domain commands — types et constantes de commandes workflow.
Aucune dépendance ORM. Pur Python stdlib.
Story 85.1.
"""
from __future__ import annotations
from enum import Enum


class CommandType(str, Enum):
    """Types de commandes workflow persistées dans WORKFLOW_COMMANDS."""
    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"
    TIMEOUT_SIGNAL = "timeout_signal"
    RESUME_SIGNAL = "resume_signal"


# Ensemble des valeurs valides — rétrocompatibilité avec les appelants existants
VALID_COMMAND_TYPES: frozenset[str] = frozenset(ct.value for ct in CommandType)
