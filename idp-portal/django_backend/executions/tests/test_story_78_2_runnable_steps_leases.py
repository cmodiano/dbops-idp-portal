"""
Tests Story 78.2 — Renforcement RUNNABLE_STEPS avec leases et reclaim

AC1 : model round-trip avec les 4 nouveaux champs (claimed_until, attempt_no, last_error, max_attempts)
AC2 : claim_batch() respecte les leases (actif, expiré, eligible_at) et incrémente attempt_no
AC3 : reclaim_expired_leases() remet à zéro claim mais préserve attempt_no
AC4 : crash recovery end-to-end (enqueue → claim → expire → reclaim → second claim)
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from executions.models import RunnableStep
from executions.services.runnable_steps import RunnableStepService, LEASE_DURATION_SECONDS
from tests.factories import ExecutionFactory, ExecutionStepFactory


def _make_runnable_step(execution=None, step=None, **kwargs):
    """Helper pour créer un RunnableStep en base.

    Note: eligible_at a auto_now_add=True — Django ignore le kwarg au create().
    Ce helper applique eligible_at via .update() après création si fourni.
    """
    if execution is None:
        execution = ExecutionFactory()
    if step is None:
        step = ExecutionStepFactory(execution=execution)
    eligible_at = kwargs.pop("eligible_at", None)
    defaults = {
        "execution_step": step,
        "execution": execution,
        "step_order": step.step_order,
        "step_type": step.step_type,
        "priority": kwargs.pop("priority", 0),
    }
    defaults.update(kwargs)
    rs = RunnableStep.objects.create(**defaults)
    if eligible_at is not None:
        RunnableStep.objects.filter(pk=rs.pk).update(eligible_at=eligible_at)
        rs.refresh_from_db()
    return rs


@pytest.mark.django_db
class TestAC1ModelFields:
    """AC1 : Les 4 nouveaux champs sont persistés et ont les bons défauts."""

    def test_new_fields_defaults(self):
        """Les champs lease ont les valeurs par défaut correctes."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        rs = RunnableStep.objects.create(
            execution_step=step,
            execution=execution,
            step_order=step.step_order,
            step_type=step.step_type,
            priority=0,
        )
        rs.refresh_from_db()
        assert rs.claimed_until is None
        assert rs.attempt_no == 0
        assert rs.last_error is None
        assert rs.max_attempts == 3

    def test_round_trip_all_fields(self):
        """Écriture et relecture des 4 champs."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        now = timezone.now()
        rs = RunnableStep.objects.create(
            execution_step=step,
            execution=execution,
            step_order=step.step_order,
            step_type=step.step_type,
            priority=0,
            claimed_until=now + timedelta(minutes=5),
            attempt_no=2,
            last_error="timeout connecting to platform",
            max_attempts=5,
        )
        rs.refresh_from_db()
        assert rs.claimed_until is not None
        assert rs.attempt_no == 2
        assert rs.last_error == "timeout connecting to platform"
        assert rs.max_attempts == 5

    def test_is_claimed_property(self):
        """is_claimed est True uniquement si le lease est dans le futur."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        rs = RunnableStep(
            execution_step=step,
            execution=execution,
            step_order=1,
            step_type="platform",
        )
        assert rs.is_claimed is False

        rs.claimed_until = timezone.now() + timedelta(minutes=5)
        assert rs.is_claimed is True

        rs.claimed_until = timezone.now() - timedelta(minutes=1)
        assert rs.is_claimed is False

    def test_is_lease_expired_property(self):
        """is_lease_expired est True si claimed_at existe et claimed_until est dans le passé."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        rs = RunnableStep(
            execution_step=step,
            execution=execution,
            step_order=1,
            step_type="platform",
        )
        assert rs.is_lease_expired is False

        rs.claimed_at = timezone.now()
        rs.claimed_until = timezone.now() + timedelta(minutes=5)
        assert rs.is_lease_expired is False

        rs.claimed_until = timezone.now() - timedelta(minutes=1)
        assert rs.is_lease_expired is True

    def test_has_exceeded_max_attempts_property(self):
        """has_exceeded_max_attempts est True si attempt_no >= max_attempts."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)
        rs = RunnableStep(
            execution_step=step,
            execution=execution,
            step_order=1,
            step_type="platform",
            attempt_no=2,
            max_attempts=3,
        )
        assert rs.has_exceeded_max_attempts is False
        rs.attempt_no = 3
        assert rs.has_exceeded_max_attempts is True


@pytest.mark.django_db
class TestAC2ClaimBatch:
    """AC2 : claim_batch() respecte les leases et incrémente attempt_no."""

    def test_claim_does_not_offer_active_lease(self):
        """Un step avec claimed_until dans le futur n'est pas offert."""
        now = timezone.now()
        _make_runnable_step(
            claimed_at=now,
            claimed_by="worker-A",
            claimed_until=now + timedelta(minutes=5),
            attempt_no=1,
            eligible_at=now - timedelta(seconds=10),
        )
        batch = RunnableStepService.claim_batch("worker-B")
        assert len(batch) == 0

    def test_claim_does_not_offer_future_eligible(self):
        """Un step avec eligible_at dans le futur n'est pas offert."""
        rs = _make_runnable_step()
        # auto_now_add ignores kwargs, so force eligible_at via update()
        RunnableStep.objects.filter(pk=rs.pk).update(
            eligible_at=timezone.now() + timedelta(hours=1),
        )
        batch = RunnableStepService.claim_batch("worker-A")
        assert len(batch) == 0

    def test_claim_offers_expired_lease(self):
        """Un step avec claimed_until dans le passé (lease expiré) est offert."""
        now = timezone.now()
        _make_runnable_step(
            claimed_at=now - timedelta(minutes=10),
            claimed_by="worker-A",
            claimed_until=now - timedelta(minutes=5),
            attempt_no=1,
            eligible_at=now - timedelta(minutes=15),
        )
        batch = RunnableStepService.claim_batch("worker-B")
        assert len(batch) == 1
        assert batch[0].claimed_by == "worker-B"

    def test_attempt_no_incremented_on_claim(self):
        """attempt_no est incrémenté à chaque claim successif."""
        now = timezone.now()
        rs = _make_runnable_step(
            eligible_at=now - timedelta(seconds=10),
        )
        assert rs.attempt_no == 0

        # Premier claim
        batch1 = RunnableStepService.claim_batch("worker-A")
        assert len(batch1) == 1
        rs.refresh_from_db()
        assert rs.attempt_no == 1

        # Simuler expiration du lease
        RunnableStep.objects.filter(pk=rs.pk).update(
            claimed_until=now - timedelta(minutes=1),
        )

        # Deuxième claim
        batch2 = RunnableStepService.claim_batch("worker-B")
        assert len(batch2) == 1
        rs.refresh_from_db()
        assert rs.attempt_no == 2
        assert rs.claimed_by == "worker-B"

    def test_claim_sets_claimed_until(self):
        """claimed_until est fixé à now + LEASE_DURATION lors du claim."""
        now = timezone.now()
        _make_runnable_step(
            eligible_at=now - timedelta(seconds=10),
        )
        batch = RunnableStepService.claim_batch("worker-A")
        assert len(batch) == 1
        step = RunnableStep.objects.get(pk=batch[0].pk)
        # claimed_until doit être environ LEASE_DURATION_SECONDS après now
        assert step.claimed_until is not None
        delta = (step.claimed_until - now).total_seconds()
        assert abs(delta - LEASE_DURATION_SECONDS) < 2  # tolérance 2s

    def test_claim_offers_unclaimed_step(self):
        """Un step sans claim (claimed_until IS NULL) et eligible est offert."""
        now = timezone.now()
        _make_runnable_step(
            eligible_at=now - timedelta(seconds=10),
        )
        batch = RunnableStepService.claim_batch("worker-A")
        assert len(batch) == 1

    def test_claim_skips_step_exceeding_max_attempts(self):
        """Un step qui a atteint max_attempts n'est pas offert (plus de retries)."""
        now = timezone.now()
        _make_runnable_step(
            eligible_at=now - timedelta(seconds=10),
            attempt_no=3,
            max_attempts=3,
        )
        batch = RunnableStepService.claim_batch("worker-A")
        assert len(batch) == 0


@pytest.mark.django_db
class TestAC3ReclaimExpiredLeases:
    """AC3 : reclaim_expired_leases() remet à zéro claim mais préserve attempt_no."""

    def test_reclaim_resets_claim_preserves_attempt_no(self):
        """reclaim remet claimed_at/claimed_by/claimed_until à None, garde attempt_no."""
        now = timezone.now()
        rs = _make_runnable_step(
            claimed_at=now - timedelta(minutes=10),
            claimed_by="worker-A",
            claimed_until=now - timedelta(minutes=5),
            attempt_no=2,
            eligible_at=now - timedelta(minutes=15),
        )
        reclaimed = RunnableStepService.reclaim_expired_leases()
        assert reclaimed == 1

        rs.refresh_from_db()
        assert rs.claimed_at is None
        assert rs.claimed_by is None
        assert rs.claimed_until is None
        assert rs.attempt_no == 2  # Préservé

    def test_reclaim_does_not_touch_active_leases(self):
        """reclaim ne touche pas les steps avec un lease actif."""
        now = timezone.now()
        _make_runnable_step(
            claimed_at=now,
            claimed_by="worker-A",
            claimed_until=now + timedelta(minutes=5),
            attempt_no=1,
            eligible_at=now - timedelta(minutes=10),
        )
        reclaimed = RunnableStepService.reclaim_expired_leases()
        assert reclaimed == 0

    def test_reclaim_returns_zero_when_nothing_to_reclaim(self):
        """reclaim retourne 0 si aucun lease expiré."""
        _make_runnable_step(
            eligible_at=timezone.now() - timedelta(seconds=10),
        )
        reclaimed = RunnableStepService.reclaim_expired_leases()
        assert reclaimed == 0


@pytest.mark.django_db
class TestAC4CrashRecovery:
    """AC4 : Scénario complet crash recovery."""

    def test_crash_recovery_full_scenario(self):
        """
        enqueue → claim (lease non renouvelé = crash simulé) → reclaim → second claim.
        Vérifie attempt_no=2 et absence de double exécution.
        """
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)

        now = timezone.now()

        # Enqueue le step
        rs = RunnableStepService.enqueue(step)
        assert rs is not None
        # Forcer eligible_at dans le passé (auto_now_add le met à now)
        RunnableStep.objects.filter(pk=rs.pk).update(
            eligible_at=now - timedelta(seconds=10),
        )

        # Worker A claim
        claimed = RunnableStepService.claim_batch("worker-A")
        assert len(claimed) == 1
        rs.refresh_from_db()
        assert rs.attempt_no == 1
        # Ne pas delete() → simule le crash

        # Simuler expiration du lease (avancer claimed_until dans le passé)
        RunnableStep.objects.filter(pk=rs.pk).update(
            claimed_until=now - timedelta(minutes=1),
        )

        # Reclaim des leases expirés
        reclaimed = RunnableStepService.reclaim_expired_leases()
        assert reclaimed == 1

        # Vérifier que le step est disponible pour un second worker
        claimed2 = RunnableStepService.claim_batch("worker-B")
        assert len(claimed2) == 1
        step_db = RunnableStep.objects.get(pk=claimed2[0].pk)
        assert step_db.attempt_no == 2
        assert step_db.claimed_by == "worker-B"

        # Vérifier qu'il n'y a qu'un seul RunnableStep (pas de duplication)
        assert RunnableStep.objects.filter(
            execution_step=step
        ).count() == 1

    def test_pending_count_includes_expired_leases(self):
        """pending_count() compte les steps disponibles (unclaimed + lease expiré)."""
        execution = ExecutionFactory()
        now = timezone.now()

        # Step 1 : unclaimed (available)
        _make_runnable_step(
            execution=execution,
            eligible_at=now - timedelta(seconds=10),
        )
        # Step 2 : lease actif (not available)
        _make_runnable_step(
            execution=execution,
            claimed_at=now,
            claimed_by="worker-A",
            claimed_until=now + timedelta(minutes=5),
            attempt_no=1,
            eligible_at=now - timedelta(seconds=10),
        )
        # Step 3 : lease expiré (available)
        _make_runnable_step(
            execution=execution,
            claimed_at=now - timedelta(minutes=10),
            claimed_by="worker-B",
            claimed_until=now - timedelta(minutes=5),
            attempt_no=1,
            eligible_at=now - timedelta(seconds=10),
        )

        count = RunnableStepService.pending_count(execution_id=execution.id)
        assert count == 2  # unclaimed + expired, pas le lease actif
