"""
Tests Story 78.1 — Table WORKFLOW_EVENT_COUNTER et allocation séquence atomique

AC1 : Table WORKFLOW_EVENT_COUNTER créée (migration Flyway V122).
AC2 : WorkflowEventService utilise exclusivement l'allocation atomique via select_for_update().
AC3 : Classification critique (exception propagée) vs best-effort (silencieuse).
AC4 : Tests de concurrence — N émetteurs simultanés → séquence strictement croissante,
      sans doublons, sans trous (DB réelle, @pytest.mark.django_db(transaction=True)).

Note : les tests de threading concurrent (AC4) requièrent Oracle (row-level locking).
SQLite utilise un verrou de table complet qui provoque des "table is locked" sous
concurrence — ce comportement est normal et attendu sur SQLite.
Les tests de concurrence réelle sont donc skippés sur SQLite et s'exécutent sur Oracle.
"""
from __future__ import annotations

import concurrent.futures
import threading

import pytest
from unittest.mock import patch

from django.db import connection, transaction

from executions.models import (
    WorkflowEvent,
    WorkflowEventCounter,
    WorkflowEventType,
    WorkflowEventEntityType,
)
from executions.services.workflow_events import (
    WorkflowEventService,
    CRITICAL_EVENT_TYPES,
    BEST_EFFORT_EVENT_TYPES,
)
from tests.factories import ExecutionFactory, ExecutionStepFactory


def is_oracle():
    """Vérifie si la base de données de test est Oracle."""
    return connection.vendor == 'oracle'


requires_oracle = pytest.mark.skipif(
    not is_oracle(),
    reason="Test de concurrence row-level lock — nécessite Oracle. SQLite utilise un verrou de table qui provoque 'table is locked' sous concurrence.",
)


# ---------------------------------------------------------------------------
# AC2 — Allocation atomique : WorkflowEventCounter remplace MAX()+1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAtomicSequenceAllocation:
    """WorkflowEventService._next_sequence_num() utilise WorkflowEventCounter."""

    def test_first_allocation_returns_one(self):
        """Premier appel → séquence = 1, compteur créé."""
        execution = ExecutionFactory()
        with transaction.atomic():
            seq = WorkflowEventService._next_sequence_num(execution.id)
        assert seq == 1
        counter = WorkflowEventCounter.objects.get(execution_id=execution.id)
        assert counter.last_sequence_num == 1

    def test_subsequent_allocations_are_strictly_increasing(self):
        """Appels successifs → séquences strictement croissantes."""
        execution = ExecutionFactory()
        seqs = []
        for _ in range(5):
            with transaction.atomic():
                seqs.append(WorkflowEventService._next_sequence_num(execution.id))
        assert seqs == list(range(1, 6))

    def test_counter_isolated_between_executions(self):
        """Chaque execution_id a son propre compteur indépendant."""
        exec1 = ExecutionFactory()
        exec2 = ExecutionFactory()
        with transaction.atomic():
            seq1a = WorkflowEventService._next_sequence_num(exec1.id)
        with transaction.atomic():
            seq2a = WorkflowEventService._next_sequence_num(exec2.id)
        with transaction.atomic():
            seq1b = WorkflowEventService._next_sequence_num(exec1.id)

        assert seq1a == 1
        assert seq2a == 1
        assert seq1b == 2

    def test_no_legacy_max_query_used(self):
        """_next_sequence_num n'utilise plus MAX(sequence_num) sur WORKFLOW_EVENTS."""
        execution = ExecutionFactory()
        # Initialiser le compteur à une valeur élevée pour simuler une execution avancée.
        # Insérer ensuite un event avec un sequence_num très différent directement en DB.
        # Si MAX() était utilisé, le prochain numéro serait basé sur l'event max, pas le counter.
        WorkflowEventCounter.objects.create(
            execution_id=execution.id,
            last_sequence_num=5,
        )
        WorkflowEvent.objects.create(
            execution_id=execution.id,
            event_type=WorkflowEventType.STEP_STARTED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=1,
            sequence_num=100,  # Écart intentionnel avec le counter (last_seq=5)
        )
        with transaction.atomic():
            seq = WorkflowEventService._next_sequence_num(execution.id)
        # Avec l'allocation atomique via counter, seq = 5+1 = 6, pas 100+1 = 101
        assert seq == 6, (
            "L'ancienne méthode MAX()+1 aurait retourné 101. "
            f"Si seq==6, c'est bien WorkflowEventCounter (last_seq=5) qui est utilisé, obtenu: {seq}"
        )


# ---------------------------------------------------------------------------
# AC3 — Classification critique vs best-effort
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEmitClassification:
    """emit() propage les exceptions pour les events critiques, les avale pour best-effort."""

    def test_critical_event_types_set_is_correct(self):
        """CRITICAL_EVENT_TYPES contient exactement les types définis dans AC3 + STEP_STATUS_CHANGED."""
        expected = {
            WorkflowEventType.EXECUTION_STATUS_CHANGED,
            WorkflowEventType.EXECUTION_COMPLETED,
            WorkflowEventType.EXECUTION_FAILED,
            WorkflowEventType.STEP_STATUS_CHANGED,
            WorkflowEventType.STEP_STARTED,
            WorkflowEventType.STEP_COMPLETED,
            WorkflowEventType.STEP_FAILED,
            WorkflowEventType.APPROVAL_REQUESTED,
            WorkflowEventType.APPROVAL_GRANTED,
            WorkflowEventType.APPROVAL_REJECTED,
        }
        assert CRITICAL_EVENT_TYPES == expected, (
            f"Différence : {CRITICAL_EVENT_TYPES.symmetric_difference(expected)}"
        )

    def test_best_effort_event_types_set_is_correct(self):
        """BEST_EFFORT_EVENT_TYPES contient STEP_OUTPUT_UPDATED et TARGET_ADDED."""
        assert WorkflowEventType.STEP_OUTPUT_UPDATED in BEST_EFFORT_EVENT_TYPES
        assert WorkflowEventType.TARGET_ADDED in BEST_EFFORT_EVENT_TYPES

    def test_critical_event_propagates_exception(self):
        """Un événement critique lève une exception si l'emit échoue."""
        execution = ExecutionFactory()
        with patch.object(WorkflowEventService, '_emit_inner', side_effect=RuntimeError("DB down")):
            with pytest.raises(RuntimeError, match="DB down"):
                WorkflowEventService.emit(
                    execution_id=execution.id,
                    event_type=WorkflowEventType.STEP_STARTED,  # critique
                    entity_type=WorkflowEventEntityType.EXECUTION_STEP,
                    entity_id=1,
                )

    def test_best_effort_event_swallows_exception(self):
        """Un événement best-effort retourne None sans lever si l'emit échoue."""
        execution = ExecutionFactory()
        with patch.object(WorkflowEventService, '_emit_inner', side_effect=RuntimeError("DB down")):
            result = WorkflowEventService.emit(
                execution_id=execution.id,
                event_type=WorkflowEventType.STEP_OUTPUT_UPDATED,  # best-effort
                entity_type=WorkflowEventEntityType.EXECUTION_STEP,
                entity_id=1,
            )
        assert result is None

    def test_best_effort_event_logs_warning_on_failure(self):
        """Un événement best-effort loggue un warning si l'emit échoue."""
        execution = ExecutionFactory()
        with patch.object(WorkflowEventService, '_emit_inner', side_effect=RuntimeError("DB down")):
            with patch('executions.services.workflow_events.logger') as mock_logger:
                WorkflowEventService.emit(
                    execution_id=execution.id,
                    event_type=WorkflowEventType.TARGET_ADDED,  # best-effort
                    entity_type=WorkflowEventEntityType.EXECUTION_TARGET,
                    entity_id=1,
                )
                mock_logger.warning.assert_called_once()

    def test_critical_event_emits_successfully(self):
        """Un événement critique réussi retourne un WorkflowEvent."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        result = WorkflowEventService.emit(
            execution_id=execution.id,
            event_type=WorkflowEventType.STEP_STARTED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
        )
        assert result is not None
        assert isinstance(result, WorkflowEvent)
        assert result.event_type == WorkflowEventType.STEP_STARTED
        assert result.sequence_num == 1

    def test_best_effort_event_emits_successfully(self):
        """Un événement best-effort réussi retourne un WorkflowEvent."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        result = WorkflowEventService.emit(
            execution_id=execution.id,
            event_type=WorkflowEventType.STEP_OUTPUT_UPDATED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
        )
        assert result is not None
        assert result.event_type == WorkflowEventType.STEP_OUTPUT_UPDATED

    def test_emit_target_added_is_best_effort(self):
        """emit_target_added() retourne un WorkflowEvent et est best-effort (TARGET_ADDED)."""
        execution = ExecutionFactory()
        result = WorkflowEventService.emit_target_added(
            execution_id=execution.id,
            target_id=42,
            target_name="server-01",
        )
        assert result is not None
        assert result.event_type == WorkflowEventType.TARGET_ADDED
        assert result.entity_type == WorkflowEventEntityType.EXECUTION_TARGET
        assert result.entity_id == 42

    def test_get_latest_sequence_reads_from_counter(self):
        """get_latest_sequence() lit depuis WORKFLOW_EVENT_COUNTER, pas MAX(WORKFLOW_EVENTS)."""
        execution = ExecutionFactory()
        # Émettre 3 events pour initialiser le counter à 3
        for i in range(3):
            WorkflowEventService.emit(
                execution_id=execution.id,
                event_type=WorkflowEventType.STEP_STARTED,
                entity_type=WorkflowEventEntityType.EXECUTION_STEP,
                entity_id=i + 1,
            )
        assert WorkflowEventService.get_latest_sequence(execution.id) == 3

    def test_get_latest_sequence_returns_zero_if_no_counter(self):
        """get_latest_sequence() retourne 0 si aucun counter n'existe pour l'execution."""
        execution = ExecutionFactory()
        assert WorkflowEventService.get_latest_sequence(execution.id) == 0


# ---------------------------------------------------------------------------
# AC4 — Tests de concurrence
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestConcurrentSequenceAllocation:
    """N émetteurs concurrents → séquence strictement croissante, sans doublons, sans trous.

    Les tests de threading réel (@requires_oracle) nécessitent Oracle car SQLite utilise
    un verrou de table entier (pas row-level) qui empêche toute écriture concurrente.
    Les tests de mécanisme (select_for_update appelé, séquences séquentielles) s'exécutent
    sur tous les backends.
    """

    def test_counter_row_created_on_first_emit(self):
        """La ligne WORKFLOW_EVENT_COUNTER est créée à la première émission."""
        execution = ExecutionFactory()
        assert not WorkflowEventCounter.objects.filter(execution_id=execution.id).exists()

        WorkflowEventService.emit(
            execution_id=execution.id,
            event_type=WorkflowEventType.STEP_STARTED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=1,
        )

        counter = WorkflowEventCounter.objects.get(execution_id=execution.id)
        assert counter.last_sequence_num == 1

    def test_sequential_emits_produce_no_duplicates(self):
        """N émissions séquentielles → N séquences uniques sans trou (tous backends)."""
        n = 8
        execution = ExecutionFactory()
        seqs = []
        for i in range(n):
            event = WorkflowEventService.emit(
                execution_id=execution.id,
                event_type=WorkflowEventType.STEP_STARTED,
                entity_type=WorkflowEventEntityType.EXECUTION_STEP,
                entity_id=i + 1,
            )
            assert event is not None
            seqs.append(event.sequence_num)

        assert seqs == list(range(1, n + 1)), f"Séquences attendues 1..{n}, obtenues : {seqs}"

    def test_select_for_update_is_used_in_sequence_allocation(self):
        """_next_sequence_num() appelle select_for_update() sur WorkflowEventCounter."""
        execution = ExecutionFactory()
        # On patche select_for_update pour vérifier qu'il est appelé
        called = []

        original_select_for_update = WorkflowEventCounter.objects.__class__.select_for_update

        def spy_select_for_update(self, *args, **kwargs):
            called.append(True)
            return original_select_for_update(self, *args, **kwargs)

        with patch.object(
            WorkflowEventCounter.objects.__class__,
            'select_for_update',
            spy_select_for_update,
        ):
            with transaction.atomic():
                WorkflowEventService._next_sequence_num(execution.id)

        assert called, "select_for_update() doit être appelé dans _next_sequence_num()"

    @requires_oracle
    def test_concurrent_emitters_no_duplicates(self):
        """10 threads émettent simultanément → 10 séquences uniques sans collision (Oracle)."""
        n_threads = 10
        execution = ExecutionFactory()
        results = []
        errors = []
        lock = threading.Lock()

        def emit_and_collect(entity_id):
            try:
                event = WorkflowEventService.emit(
                    execution_id=execution.id,
                    event_type=WorkflowEventType.STEP_STARTED,
                    entity_type=WorkflowEventEntityType.EXECUTION_STEP,
                    entity_id=entity_id,
                )
                if event is not None:
                    with lock:
                        results.append(event.sequence_num)
            except Exception as e:  # noqa: BLE001
                with lock:
                    errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(emit_and_collect, i + 1) for i in range(n_threads)]
            concurrent.futures.wait(futures)

        assert not errors, f"Des erreurs sont survenues : {errors}"
        assert len(results) == n_threads, f"Attendu {n_threads} résultats, obtenu {len(results)}"
        assert len(set(results)) == n_threads, (
            f"Doublons détectés dans les séquences : {sorted(results)}"
        )
        assert sorted(results) == list(range(1, n_threads + 1)), (
            f"Séquences attendues : {list(range(1, n_threads + 1))}, obtenues : {sorted(results)}"
        )

    @requires_oracle
    def test_concurrent_emitters_strictly_monotonic(self):
        """5 threads émettent 3 événements chacun → 15 séquences strictement croissantes (Oracle)."""
        n_threads = 5
        events_per_thread = 3
        total = n_threads * events_per_thread
        execution = ExecutionFactory()
        all_sequences = []
        lock = threading.Lock()

        def emit_multiple(entity_id):
            local_seqs = []
            for _ in range(events_per_thread):
                event = WorkflowEventService.emit(
                    execution_id=execution.id,
                    event_type=WorkflowEventType.STEP_COMPLETED,
                    entity_type=WorkflowEventEntityType.EXECUTION_STEP,
                    entity_id=entity_id,
                )
                if event:
                    local_seqs.append(event.sequence_num)
            with lock:
                all_sequences.extend(local_seqs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(emit_multiple, i + 1) for i in range(n_threads)]
            concurrent.futures.wait(futures)

        assert len(all_sequences) == total
        sorted_seqs = sorted(all_sequences)
        assert sorted_seqs == list(range(1, total + 1)), (
            f"Attendu 1..{total}, obtenu : {sorted_seqs}"
        )
