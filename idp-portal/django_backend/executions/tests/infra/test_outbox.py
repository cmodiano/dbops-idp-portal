"""Tests pour executions.infra.outbox — Story 85.2."""
import uuid

import pytest

from executions.infra.outbox import (
    APPROVAL_GRANTED,
    APPROVAL_NOTIFICATION,
    APPROVAL_REJECTED,
    EXECUTION_NOTIFICATION,
    STEP_BROADCAST,
    OutboxService,
)
from tests.factories import ExecutionFactory


def test_import_from_infra_outbox():
    """Vérifier que l'import depuis infra.outbox fonctionne."""
    assert OutboxService is not None
    assert APPROVAL_GRANTED == "approval_granted"
    assert APPROVAL_REJECTED == "approval_rejected"
    assert STEP_BROADCAST == "step_broadcast"
    assert EXECUTION_NOTIFICATION == "execution_notification"
    assert APPROVAL_NOTIFICATION == "approval_notification"


@pytest.mark.django_db
def test_write_entry_creates_outbox_row():
    """OutboxService.write_entry() crée un ExecutionOutbox."""
    execution = ExecutionFactory()
    key = OutboxService.build_idempotency_key(execution.id, APPROVAL_GRANTED, uuid.uuid4().hex)
    entry, created = OutboxService.write_entry(
        execution_id=execution.id,
        event_type=APPROVAL_GRANTED,
        payload={"execution_step_id": 1},
        idempotency_key=key,
    )
    assert created is True
    assert entry.event_type == APPROVAL_GRANTED
    assert entry.execution_id == execution.id


@pytest.mark.django_db
def test_write_entry_idempotent():
    """Double appel avec même clé idempotency → un seul enregistrement."""
    execution = ExecutionFactory()
    key = OutboxService.build_idempotency_key(execution.id, APPROVAL_GRANTED, uuid.uuid4().hex)
    entry1, created1 = OutboxService.write_entry(execution.id, APPROVAL_GRANTED, {}, key)
    entry2, created2 = OutboxService.write_entry(execution.id, APPROVAL_GRANTED, {}, key)
    assert created1 is True
    assert created2 is False
    assert entry1.id == entry2.id


def test_build_idempotency_key_format():
    """Vérifier le format {exec_id}:{event_type}:{discriminator}."""
    key = OutboxService.build_idempotency_key(42, "approval_granted", "step_15")
    assert key == "42:approval_granted:step_15"
