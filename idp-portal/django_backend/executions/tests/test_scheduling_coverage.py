"""
Tests de couverture pour executions/utils/scheduling.py (Story 55).
Couvre les lignes manquantes :
  - 27  : reference naive → make_aware
  - 37-38 : BadRequestError daily (ValueError hour/minute)
  - 53-54 : BadRequestError weekly (ValueError day_of_week)
  - 65  : candidate weekly <= reference → +7 days
  - 79  : cron result naive → make_aware
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from core.exceptions import BadRequestError


class TestCalculateNextExecutionDateScheduling:
    """Tests pour executions.utils.scheduling.calculate_next_execution_date."""

    # Référence UTC aware
    REF_AWARE = datetime(2024, 6, 10, 14, 30, 0, tzinfo=timezone.utc)  # Lundi (isoweekday=1)
    # Référence naive
    REF_NAIVE = datetime(2024, 6, 10, 14, 30, 0)  # Sans tzinfo

    # ── Ligne 27 : reference naive ────────────────────────────────────────────

    def test_daily_naive_reference_is_made_aware(self):
        """Ligne 27 : reference sans tzinfo → make_aware appliqué."""
        from executions.utils.scheduling import calculate_next_execution_date

        result = calculate_next_execution_date(
            "daily",
            {"hour": 8, "minute": 0},
            self.REF_NAIVE,
        )
        # Le résultat doit être aware
        assert result.tzinfo is not None

    # ── Lignes 37-38 : BadRequestError daily ─────────────────────────────────

    def test_daily_invalid_hour_raises_bad_request(self):
        """Lignes 37-38 : hour non-entier → BadRequestError INVALID_PATTERN_CONFIG."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "daily",
                {"hour": "invalid_hour", "minute": 0},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "INVALID_PATTERN_CONFIG"

    def test_daily_invalid_minute_raises_bad_request(self):
        """Lignes 37-38 : minute non-entier → BadRequestError INVALID_PATTERN_CONFIG."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "daily",
                {"hour": 8, "minute": "not_an_int"},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "INVALID_PATTERN_CONFIG"

    def test_daily_none_hour_raises_bad_request(self):
        """Variante : hour=None → TypeError → BadRequestError."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "daily",
                {"hour": None, "minute": 0},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "INVALID_PATTERN_CONFIG"

    # ── Lignes 53-54 : BadRequestError weekly ────────────────────────────────

    def test_weekly_invalid_day_of_week_raises_bad_request(self):
        """Lignes 53-54 : day_of_week non-entier → BadRequestError INVALID_PATTERN_CONFIG."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "weekly",
                {"day_of_week": "monday", "hour": 9, "minute": 0},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "INVALID_PATTERN_CONFIG"

    def test_weekly_none_day_of_week_raises_bad_request(self):
        """Lignes 53-54 : day_of_week=None → TypeError → BadRequestError."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "weekly",
                {"day_of_week": None, "hour": 9, "minute": 0},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "INVALID_PATTERN_CONFIG"

    # ── Ligne 65 : candidate <= reference → +7 days ──────────────────────────

    def test_weekly_same_day_always_schedules_next_week(self):
        """Ligne 65 : même jour de la semaine → days_ahead devient 7 (via `or 7`)."""
        from executions.utils.scheduling import calculate_next_execution_date

        # REF_AWARE est un Lundi (isoweekday=1), day_of_week=1 → days_ahead = 0 or 7 = 7
        result = calculate_next_execution_date(
            "weekly",
            {"day_of_week": 1, "hour": 14, "minute": 0},
            self.REF_AWARE,
        )
        # Résultat doit être au moins 7 jours plus tard
        assert result > self.REF_AWARE
        diff = result - self.REF_AWARE
        assert diff.days >= 6  # au moins 6 jours (peut être 7)

    def test_weekly_candidate_still_before_reference_adds_7_days(self):
        """Ligne 65 : candidate <= reference (heure passée même jour) → +7 days."""
        from executions.utils.scheduling import calculate_next_execution_date

        # Même jour (lundi=1), même heure → candidate exactement égal à reference → +7 days
        result = calculate_next_execution_date(
            "weekly",
            {"day_of_week": 1, "hour": 12, "minute": 0},
            self.REF_AWARE,  # 14h30 le lundi
        )
        # 12h00 lundi suivant
        diff = result - self.REF_AWARE
        assert diff.days >= 6

    # ── Ligne 79 : cron result naive → make_aware ────────────────────────────

    def test_cron_naive_result_is_made_aware(self):
        """Ligne 79 : croniter retourne un datetime naive → make_aware appliqué."""
        from executions.utils.scheduling import calculate_next_execution_date
        from croniter import croniter

        # Patch croniter pour retourner un datetime naïf
        naive_next = datetime(2024, 6, 11, 0, 0, 0)  # Sans tzinfo

        with patch.object(croniter, 'get_next', return_value=naive_next):
            result = calculate_next_execution_date(
                "cron",
                {"cron_expression": "0 0 * * *"},
                self.REF_AWARE,
            )
        assert result.tzinfo is not None

    def test_cron_aware_result_converted_to_utc(self):
        """Ligne 81 : croniter retourne un aware → astimezone(UTC)."""
        from executions.utils.scheduling import calculate_next_execution_date

        result = calculate_next_execution_date(
            "cron",
            {"cron_expression": "0 8 * * *"},
            self.REF_AWARE,
        )
        assert result.tzinfo is not None

    def test_cron_invalid_expression_raises_bad_request(self):
        """Lignes 70-75 : expression cron invalide → BadRequestError."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "cron",
                {"cron_expression": "invalid_cron"},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "INVALID_CRON_EXPRESSION"

    def test_daily_candidate_in_future_no_extra_day(self):
        """Ligne 44->46 : candidate > reference → pas de +1 day (branche else non prise)."""
        from executions.utils.scheduling import calculate_next_execution_date

        # REF à 14h30, target 20h00 → candidate 20h00 > 14h30 → résultat = aujourd'hui 20h00
        result = calculate_next_execution_date(
            "daily",
            {"hour": 20, "minute": 0},
            self.REF_AWARE,
        )
        assert result.hour == 20
        assert result.minute == 0
        # Même date (pas de +1 day)
        assert result.date() == self.REF_AWARE.date()

    def test_weekly_candidate_lte_reference_adds_7_days(self):
        """Ligne 65 : candidate <= reference (bascule de sécurité weekly) — simulé via mock."""
        import executions.utils.scheduling as sched_mod
        from datetime import timedelta as real_timedelta

        ref_val = datetime(2024, 6, 10, 14, 30, 0, tzinfo=timezone.utc)
        _expected_result = ref_val + real_timedelta(days=7)

        # Candidat dans le passé pour déclencher la branche ligne 65
        _past_candidate = ref_val - real_timedelta(days=1)

        call_count = [0]
        original_timedelta = sched_mod.timedelta

        class FakeTimedelta:
            """Retourne un candidat dans le passé au premier appel (weekly days_ahead)."""
            def __new__(cls, days=0, **kwargs):
                if days > 0 and call_count[0] == 0:
                    call_count[0] += 1
                    # Retourner un vrai timedelta négatif pour forcer candidate <= reference
                    return original_timedelta(days=-2)
                return original_timedelta(days=days, **kwargs)

        with patch.object(sched_mod, 'timedelta', FakeTimedelta):
            result = sched_mod.calculate_next_execution_date(
                "weekly",
                {"day_of_week": 2, "hour": 9, "minute": 0},
                ref_val,
            )
        # Le résultat doit être > reference (après application du +7 days)
        assert result > ref_val

    def test_unknown_pattern_type_raises_bad_request(self):
        """Ligne 84 : pattern_type inconnu → BadRequestError BAD_REQUEST."""
        from executions.utils.scheduling import calculate_next_execution_date

        with pytest.raises(BadRequestError) as exc_info:
            calculate_next_execution_date(
                "monthly",
                {},
                self.REF_AWARE,
            )
        assert exc_info.value.code == "BAD_REQUEST"
