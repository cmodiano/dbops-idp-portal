"""
Tests unitaires pour executions/domain/commands.py.
Story 85.1 — AC7.
"""
from executions.domain.commands import CommandType, VALID_COMMAND_TYPES


def test_command_type_has_all_expected_values():
    expected = {"approve", "reject", "cancel", "timeout_signal", "resume_signal"}
    actual = {ct.value for ct in CommandType}
    assert actual == expected


def test_valid_command_types_matches_command_type_values():
    assert VALID_COMMAND_TYPES == frozenset(ct.value for ct in CommandType)
    assert isinstance(VALID_COMMAND_TYPES, frozenset)
