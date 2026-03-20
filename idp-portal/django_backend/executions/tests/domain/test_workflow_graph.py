"""
Tests unitaires pour executions/domain/workflow_graph.py.

Fonctions pures — pas de @pytest.mark.django_db requis.
Story 85.1 — AC7.
"""
from executions.domain.workflow_graph import (
    apply_join_policy,
    find_step_config,
    get_linear_next_step_ids,
    get_next_step_ids,
)
from executions.models import ExecutionStatus

STEPS = [
    {"step_id": "s1", "order": 1, "on_success_step_ids": ["s2"], "on_error_step_ids": ["s3"]},
    {"step_id": "s2", "order": 2},
    {"step_id": "s3", "order": 3},
]


# ---------------------------------------------------------------------------
# get_next_step_ids
# ---------------------------------------------------------------------------

def test_get_next_step_ids_success_explicit():
    result = get_next_step_ids(STEPS[0], ExecutionStatus.COMPLETED, STEPS)
    assert result == ["s2"]


def test_get_next_step_ids_success_linear_fallback():
    """Pas de on_success_step_ids → fallback linéaire."""
    step = {"step_id": "s1", "order": 1}
    steps = [step, {"step_id": "s2", "order": 2}]
    result = get_next_step_ids(step, ExecutionStatus.COMPLETED, steps)
    assert result == ["s2"]


def test_get_next_step_ids_error_explicit():
    result = get_next_step_ids(STEPS[0], ExecutionStatus.FAILED, STEPS)
    assert result == ["s3"]


def test_get_next_step_ids_error_empty_when_no_routing():
    """Pas de on_error_step_ids → liste vide."""
    step = {"step_id": "s2", "order": 2}
    result = get_next_step_ids(step, ExecutionStatus.FAILED, STEPS)
    assert result == []


def test_get_next_step_ids_success_empty_list_no_linear_fallback():
    """on_success_step_ids présent mais vide → pas de fallback linéaire (clé présente = routing explicite)."""
    step = {"step_id": "s1", "order": 1, "on_success_step_ids": []}
    steps = [step, {"step_id": "s2", "order": 2}]
    result = get_next_step_ids(step, ExecutionStatus.COMPLETED, steps)
    assert result == []  # Clé présente → pas de fallback, retourne liste vide


# ---------------------------------------------------------------------------
# get_linear_next_step_ids
# ---------------------------------------------------------------------------

def test_get_linear_next_step_ids_returns_next_by_order():
    steps = [
        {"step_id": "s1", "order": 1},
        {"step_id": "s2", "order": 2},
        {"step_id": "s3", "order": 3},
    ]
    result = get_linear_next_step_ids(steps[0], steps)
    assert result == ["s2"]


def test_get_linear_next_step_ids_returns_empty_at_end():
    steps = [
        {"step_id": "s1", "order": 1},
        {"step_id": "s2", "order": 2},
    ]
    result = get_linear_next_step_ids(steps[1], steps)
    assert result == []


# ---------------------------------------------------------------------------
# apply_join_policy
# ---------------------------------------------------------------------------

def _make_results(*pairs):
    """Helper: [(step_id, status, next_ids), ...]"""
    return {sid: (status, nids) for sid, status, nids in pairs}


def test_apply_join_policy_single_predecessor_always_included():
    """1 seul prédécesseur → toujours inclus quelle que soit la policy."""
    wave = [{"step_id": "s1", "order": 1, "on_success_step_ids": ["s2"]}]
    results = _make_results(("s1", ExecutionStatus.COMPLETED, ["s2"]))
    step_lookup = {"s2": {"step_id": "s2", "join_policy": "all_success"}}
    assert apply_join_policy(wave, results, step_lookup) == ["s2"]


def test_apply_join_policy_all_success():
    wave = [
        {"step_id": "s1", "on_success_step_ids": ["s3"]},
        {"step_id": "s2", "on_success_step_ids": ["s3"]},
    ]
    results = _make_results(
        ("s1", ExecutionStatus.COMPLETED, ["s3"]),
        ("s2", ExecutionStatus.COMPLETED, ["s3"]),
    )
    step_lookup = {"s3": {"step_id": "s3", "join_policy": "all_success"}}
    assert apply_join_policy(wave, results, step_lookup) == ["s3"]


def test_apply_join_policy_all_success_fails_if_one_failed():
    wave = [
        {"step_id": "s1", "on_success_step_ids": ["s3"]},
        {"step_id": "s2", "on_error_step_ids": ["s3"]},
    ]
    results = _make_results(
        ("s1", ExecutionStatus.COMPLETED, ["s3"]),
        ("s2", ExecutionStatus.FAILED, ["s3"]),
    )
    step_lookup = {"s3": {"step_id": "s3", "join_policy": "all_success"}}
    assert apply_join_policy(wave, results, step_lookup) == []


def test_apply_join_policy_one_success():
    wave = [
        {"step_id": "s1", "on_success_step_ids": ["s3"]},
        {"step_id": "s2", "on_error_step_ids": ["s3"]},
    ]
    results = _make_results(
        ("s1", ExecutionStatus.COMPLETED, ["s3"]),
        ("s2", ExecutionStatus.FAILED, ["s3"]),
    )
    step_lookup = {"s3": {"step_id": "s3", "join_policy": "one_success"}}
    assert apply_join_policy(wave, results, step_lookup) == ["s3"]


def test_apply_join_policy_all_done():
    wave = [
        {"step_id": "s1", "on_success_step_ids": ["s3"]},
        {"step_id": "s2", "on_error_step_ids": ["s3"]},
    ]
    results = _make_results(
        ("s1", ExecutionStatus.COMPLETED, ["s3"]),
        ("s2", ExecutionStatus.FAILED, ["s3"]),
    )
    step_lookup = {"s3": {"step_id": "s3", "join_policy": "all_done"}}
    assert apply_join_policy(wave, results, step_lookup) == ["s3"]


def test_apply_join_policy_all_failed():
    wave = [
        {"step_id": "s1", "on_error_step_ids": ["s3"]},
        {"step_id": "s2", "on_error_step_ids": ["s3"]},
    ]
    results = _make_results(
        ("s1", ExecutionStatus.FAILED, ["s3"]),
        ("s2", ExecutionStatus.FAILED, ["s3"]),
    )
    step_lookup = {"s3": {"step_id": "s3", "join_policy": "all_failed"}}
    assert apply_join_policy(wave, results, step_lookup) == ["s3"]


def test_apply_join_policy_one_failed():
    wave = [
        {"step_id": "s1", "on_success_step_ids": ["s3"]},
        {"step_id": "s2", "on_error_step_ids": ["s3"]},
    ]
    results = _make_results(
        ("s1", ExecutionStatus.COMPLETED, ["s3"]),
        ("s2", ExecutionStatus.FAILED, ["s3"]),
    )
    step_lookup = {"s3": {"step_id": "s3", "join_policy": "one_failed"}}
    assert apply_join_policy(wave, results, step_lookup) == ["s3"]


# ---------------------------------------------------------------------------
# find_step_config
# ---------------------------------------------------------------------------

def test_find_step_config_found_and_not_found():
    steps = [{"step_id": "s1"}, {"step_id": "s2"}]
    assert find_step_config(steps, "s1") == {"step_id": "s1"}
    assert find_step_config(steps, "missing") is None
    assert find_step_config(steps, None) is None
