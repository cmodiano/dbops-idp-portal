"""
Tests for executions/utils.py — helper functions extracted from views.py (Story 22.7).

Covers:
- get_env_config_case_insensitive
- validate_environment_against_inventory
- parse_int, parse_date
- detect_request_source
- apply_scope_filter
- parse_iso_datetime
- calculate_next_execution_date

Story 26.8: _is_dba_or_dbops tests moved to core/tests/test_permissions.py (TestIsDBAOrDBOPS).
Story 26.10: Renamed all _ prefixed public functions to remove underscore prefix.
"""
import pytest
from datetime import datetime, date, timedelta, timezone as dt_timezone
from unittest.mock import patch, MagicMock

from django.test import TestCase

from core.exceptions import BadRequestError

from executions.utils import (
    get_env_config_case_insensitive,
    validate_environment_against_inventory,
    parse_int,
    parse_date,
    detect_request_source,
    apply_scope_filter,
    parse_iso_datetime,
    calculate_next_execution_date,
)


# ============================================================================
# get_env_config_case_insensitive
# ============================================================================

class TestGetEnvConfigCaseInsensitive(TestCase):
    def test_returns_config_for_matching_env(self):
        config = {"DEV": {"key": "value"}, "PROD": {"key": "prod"}}
        result = get_env_config_case_insensitive(config, "DEV")
        assert result == {"key": "value"}

    def test_case_insensitive_lookup(self):
        config = {"DEV": {"key": "value"}, "PROD": {"key": "prod"}}
        assert get_env_config_case_insensitive(config, "dev") == {"key": "value"}
        assert get_env_config_case_insensitive(config, "Dev") == {"key": "value"}
        assert get_env_config_case_insensitive(config, "DeV") == {"key": "value"}

    def test_returns_empty_dict_for_missing_env(self):
        config = {"DEV": {"key": "value"}}
        assert get_env_config_case_insensitive(config, "staging") == {}

    def test_returns_empty_dict_for_empty_config(self):
        assert get_env_config_case_insensitive({}, "dev") == {}

    def test_returns_empty_dict_for_none_config(self):
        assert get_env_config_case_insensitive(None, "dev") == {}

    def test_returns_empty_dict_for_empty_env(self):
        config = {"DEV": {"key": "value"}}
        assert get_env_config_case_insensitive(config, "") == {}

    def test_returns_empty_dict_for_none_env(self):
        config = {"DEV": {"key": "value"}}
        assert get_env_config_case_insensitive(config, None) == {}

    def test_returns_empty_dict_for_non_dict_value(self):
        """HIGH-5 FIX: Non-dict values should return empty dict."""
        config = {"DEV": "not_a_dict"}
        assert get_env_config_case_insensitive(config, "dev") == {}

    def test_strips_whitespace_from_env(self):
        config = {"DEV": {"key": "value"}}
        assert get_env_config_case_insensitive(config, " dev ") == {"key": "value"}


# ============================================================================
# validate_environment_against_inventory
# ============================================================================

@pytest.mark.django_db
class TestValidateEnvironmentAgainstInventory(TestCase):

    @patch('executions.utils.InventoryService')
    def test_valid_environment_passes(self, MockInventoryService):
        mock_instance = MagicMock()
        mock_instance.list_environments.return_value = ['dev', 'staging', 'prod']
        MockInventoryService.return_value = mock_instance

        # Should not raise
        validate_environment_against_inventory('dev')

    @patch('executions.utils.InventoryService')
    def test_case_insensitive_validation(self, MockInventoryService):
        mock_instance = MagicMock()
        mock_instance.list_environments.return_value = ['DEV', 'staging', 'PROD']
        MockInventoryService.return_value = mock_instance

        # Case-insensitive, should not raise
        validate_environment_against_inventory('dev')
        validate_environment_against_inventory('Dev')
        validate_environment_against_inventory('DEV')

    @patch('executions.utils.InventoryService')
    @patch('executions.utils.AuditService')
    def test_invalid_environment_raises_bad_request(self, MockAudit, MockInventoryService):
        mock_instance = MagicMock()
        mock_instance.list_environments.return_value = ['dev', 'staging', 'prod']
        MockInventoryService.return_value = mock_instance

        with pytest.raises(BadRequestError) as exc_info:
            validate_environment_against_inventory('invalid_env', user_id=123)

        assert exc_info.value.code == 'INVALID_ENVIRONMENT'

    def test_empty_environment_passes(self):
        # Should not raise for empty/None environment
        validate_environment_against_inventory('')
        validate_environment_against_inventory(None)

    @patch('executions.utils.InventoryService')
    def test_inventory_unavailable_raises_bad_request(self, MockInventoryService):
        from inventory.services import InventoryServiceError
        mock_instance = MagicMock()
        mock_instance.list_environments.side_effect = InventoryServiceError("Connection failed")
        MockInventoryService.return_value = mock_instance

        with pytest.raises(BadRequestError) as exc_info:
            validate_environment_against_inventory('dev')

        assert exc_info.value.code == 'INVENTORY_UNAVAILABLE'


# ============================================================================
# parse_int
# ============================================================================

class TestParseInt(TestCase):
    def test_valid_int_string(self):
        assert parse_int("42", 0, name="limit") == 42

    def test_none_returns_default(self):
        assert parse_int(None, 50, name="limit") == 50

    def test_empty_string_returns_default(self):
        assert parse_int("", 50, name="limit") == 50

    def test_negative_int(self):
        assert parse_int("-5", 0, name="offset") == -5

    def test_invalid_string_raises_bad_request(self):
        with pytest.raises(BadRequestError):
            parse_int("abc", 0, name="limit")

    def test_float_string_raises_bad_request(self):
        with pytest.raises(BadRequestError):
            parse_int("3.14", 0, name="limit")


# ============================================================================
# parse_date
# ============================================================================

class TestParseDate(TestCase):
    def test_valid_iso_date(self):
        result = parse_date("2026-02-09", name="start_date")
        assert result == date(2026, 2, 9)

    def test_none_returns_none(self):
        assert parse_date(None, name="start_date") is None

    def test_empty_string_returns_none(self):
        assert parse_date("", name="start_date") is None

    def test_invalid_format_raises_bad_request(self):
        with pytest.raises(BadRequestError):
            parse_date("09/02/2026", name="start_date")

    def test_invalid_value_raises_bad_request(self):
        with pytest.raises(BadRequestError):
            parse_date("not-a-date", name="start_date")


# ============================================================================
# detect_request_source
# ============================================================================

class TestDetectRequestSource(TestCase):
    def test_bearer_token_returns_api(self):
        request = MagicMock()
        request.META = {'HTTP_AUTHORIZATION': 'Bearer eyJhbG...'}
        assert detect_request_source(request) == 'api'

    def test_xmlhttprequest_returns_ui(self):
        request = MagicMock()
        request.META = {
            'HTTP_AUTHORIZATION': '',
            'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest',
            'HTTP_REFERER': '',
            'HTTP_ORIGIN': '',
        }
        assert detect_request_source(request) == 'ui'

    def test_referer_returns_ui(self):
        request = MagicMock()
        request.META = {
            'HTTP_AUTHORIZATION': '',
            'HTTP_X_REQUESTED_WITH': '',
            'HTTP_REFERER': 'http://localhost:3000',
            'HTTP_ORIGIN': '',
        }
        assert detect_request_source(request) == 'ui'

    def test_origin_returns_ui(self):
        request = MagicMock()
        request.META = {
            'HTTP_AUTHORIZATION': '',
            'HTTP_X_REQUESTED_WITH': '',
            'HTTP_REFERER': '',
            'HTTP_ORIGIN': 'http://localhost:3000',
        }
        assert detect_request_source(request) == 'ui'

    def test_no_headers_returns_api(self):
        request = MagicMock()
        request.META = {
            'HTTP_AUTHORIZATION': '',
            'HTTP_X_REQUESTED_WITH': '',
            'HTTP_REFERER': '',
            'HTTP_ORIGIN': '',
        }
        assert detect_request_source(request) == 'api'

    def test_missing_headers_returns_api(self):
        request = MagicMock()
        request.META = {}
        assert detect_request_source(request) == 'api'


# ============================================================================
# apply_scope_filter
# ============================================================================

class TestApplyScopeFilter(TestCase):
    def test_mine_scope_filters_by_user(self):
        user = MagicMock()
        user.id = 42
        user.profile = "business"
        qs = MagicMock()

        result_qs, effective = apply_scope_filter(qs, user=user, scope="mine")
        assert effective == "mine"
        qs.filter.assert_called_once_with(user_id=42)

    def test_all_scope_for_dba(self):
        user = MagicMock()
        user.id = 1
        user.profile = "DBA"
        qs = MagicMock()

        result_qs, effective = apply_scope_filter(qs, user=user, scope="all")
        assert effective == "all"
        qs.filter.assert_not_called()

    def test_all_scope_for_dbops(self):
        """Story 36.1 AC3: DBOPS (admin) voit tout sans filtre, comme DBA."""
        user = MagicMock()
        user.id = 2
        user.profile = "DBOPS"
        qs = MagicMock()

        result_qs, effective = apply_scope_filter(qs, user=user, scope="all")
        assert effective == "all"
        qs.filter.assert_not_called()

    def test_all_scope_for_non_dba_with_specific_action_permissions(self):
        """Story 36.1 — subtask 2.2: non-admin filtre par action IDs autorisés (AC2, AC6)."""
        user = MagicMock()
        user.id = 42
        user.profile = "business"
        qs = MagicMock()

        with patch(
            'executions.utils.filters.get_allowed_action_ids_for_user',
            return_value={1, 2, 3}
        ):
            result_qs, effective = apply_scope_filter(qs, user=user, scope="all")

        assert effective == "all"
        qs.filter.assert_called_once_with(action_id__in={1, 2, 3})

    def test_all_scope_for_non_dba_with_all_access_permission(self):
        """Story 36.1 — subtask 2.3: None retourné → accès complet, aucun filtre (AC2)."""
        user = MagicMock()
        user.id = 42
        user.profile = "business"
        qs = MagicMock()

        with patch(
            'executions.utils.filters.get_allowed_action_ids_for_user',
            return_value=None
        ):
            result_qs, effective = apply_scope_filter(qs, user=user, scope="all")

        assert effective == "all"
        qs.filter.assert_not_called()

    def test_all_scope_for_non_dba_with_empty_permissions(self):
        """Story 36.1 — subtask 2.4: set() vide → filter appelé, résultat vide (AC7)."""
        user = MagicMock()
        user.id = 42
        user.profile = "business"
        qs = MagicMock()

        with patch(
            'executions.utils.filters.get_allowed_action_ids_for_user',
            return_value=set()
        ):
            result_qs, effective = apply_scope_filter(qs, user=user, scope="all")

        assert effective == "all"
        qs.filter.assert_called_once_with(action_id__in=set())

    def test_all_scope_returns_all_as_effective_scope_for_any_user(self):
        """Story 36.1 — subtask 2.5: effective_scope == 'all' même pour non-admin (AC6)."""
        user = MagicMock()
        user.id = 42
        user.profile = "business"
        qs = MagicMock()

        with patch(
            'executions.utils.filters.get_allowed_action_ids_for_user',
            return_value={10, 20}
        ):
            result_qs, effective = apply_scope_filter(qs, user=user, scope="all")

        assert effective == "all"  # Pas de fallback silencieux vers 'mine'

    def test_invalid_scope_raises_bad_request(self):
        user = MagicMock()
        user.profile = "DBA"
        qs = MagicMock()

        with pytest.raises(BadRequestError):
            apply_scope_filter(qs, user=user, scope="invalid")

    def test_none_scope_defaults_to_mine(self):
        user = MagicMock()
        user.id = 10
        user.profile = "business"
        qs = MagicMock()

        with patch('executions.utils.filters.get_allowed_action_ids_for_user', return_value=set()):
            result_qs, effective = apply_scope_filter(qs, user=user, scope=None)
        assert effective == "mine"


# ============================================================================
# parse_iso_datetime
# ============================================================================

class TestParseIsoDatetime(TestCase):
    def test_valid_iso_datetime_with_tz(self):
        result = parse_iso_datetime("2026-02-09T14:30:00+00:00", name="scheduled_at")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.hour == 14

    def test_valid_iso_datetime_without_tz_assumes_utc(self):
        result = parse_iso_datetime("2026-02-09T14:30:00", name="scheduled_at")
        assert result is not None

    def test_none_returns_none(self):
        assert parse_iso_datetime(None, name="scheduled_at") is None

    def test_empty_returns_none(self):
        assert parse_iso_datetime("", name="scheduled_at") is None

    def test_invalid_format_raises_bad_request(self):
        with pytest.raises(BadRequestError):
            parse_iso_datetime("not-a-date", name="scheduled_at")


# ============================================================================
# calculate_next_execution_date
# ============================================================================

class TestCalculateNextExecutionDate(TestCase):
    def test_daily_pattern_future(self):
        UTC = dt_timezone(timedelta(0))
        reference = datetime(2026, 2, 9, 6, 0, 0, tzinfo=UTC)
        result = calculate_next_execution_date("daily", {"hour": 10, "minute": 30}, reference)
        assert result.hour == 10
        assert result.minute == 30
        assert result.day == 9  # Same day (10:30 is after 06:00)

    def test_daily_pattern_past_time(self):
        UTC = dt_timezone(timedelta(0))
        reference = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        result = calculate_next_execution_date("daily", {"hour": 10, "minute": 0}, reference)
        assert result.day == 10  # Next day

    def test_weekly_pattern(self):
        UTC = dt_timezone(timedelta(0))
        # Monday = isoweekday() 1
        reference = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)  # This is a Monday
        result = calculate_next_execution_date("weekly", {"day_of_week": 3, "hour": 10, "minute": 0}, reference)
        assert result.isoweekday() == 3  # Wednesday

    def test_cron_pattern(self):
        UTC = dt_timezone(timedelta(0))
        reference = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        result = calculate_next_execution_date("cron", {"cron_expression": "0 14 * * *"}, reference)
        assert result.hour == 14
        assert result.minute == 0

    def test_invalid_cron_raises_bad_request(self):
        UTC = dt_timezone(timedelta(0))
        reference = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(BadRequestError):
            calculate_next_execution_date("cron", {"cron_expression": "invalid"}, reference)

    def test_invalid_pattern_type_raises_bad_request(self):
        UTC = dt_timezone(timedelta(0))
        reference = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(BadRequestError):
            calculate_next_execution_date("invalid", {}, reference)

    def test_case_insensitive_pattern_type(self):
        UTC = dt_timezone(timedelta(0))
        reference = datetime(2026, 2, 9, 6, 0, 0, tzinfo=UTC)
        result = calculate_next_execution_date("DAILY", {"hour": 10, "minute": 0}, reference)
        assert result.hour == 10
