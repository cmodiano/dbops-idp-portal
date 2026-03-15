"""
Tests unitaires — Story 83-2: GateEvaluationStrategy et dispatch dans GateEvaluator.

Tests couverts :
- MaintenanceWindowEvaluationStrategy.evaluate() avec requires_maintenance_window=False → court-circuit
- MaintenanceWindowEvaluationStrategy.evaluate() avec target en fenêtre → satisfied=True
- MaintenanceWindowEvaluationStrategy.evaluate() avec target hors fenêtre → satisfied=False
- GateEvaluator avec gate ayant evaluation_strategy=None et requires_manual_resolution=False
  → satisfied=False, reason='No evaluator implemented for: ...'
- GateEvaluator avec gate ayant requires_manual_resolution=True
  → satisfied=False, reason="En attente d'approbation explicite"
- GateEvaluator dispatch vers strategy (mock) via evaluation_strategy
"""
from unittest.mock import MagicMock, patch

from executions.gate_evaluator import GateEvaluator
from executions.gates.definitions import (
    GateDefinition,
    GateEvaluationContext,
    GateEvaluationStrategy,
)
from executions.gates.strategies import MaintenanceWindowEvaluationStrategy
from inventory.services import InventoryService, InventoryServiceError


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_ctx(requires_maintenance_window=True, targets=None):
    """Construit un GateEvaluationContext avec un step mocké."""
    mock_step = MagicMock()
    mock_step.id = 42

    if targets is None:
        targets = []
    mock_targets_qs = MagicMock()
    mock_targets_qs.exists.return_value = bool(targets)
    mock_targets_qs.__iter__ = lambda self: iter(targets)
    mock_step.execution.targets.all.return_value = mock_targets_qs

    mock_inventory = MagicMock(spec=InventoryService)

    return GateEvaluationContext(
        step=mock_step,
        condition={'type': 'maintenance_window'},
        inventory_service=mock_inventory,
        requires_maintenance_window=requires_maintenance_window,
    )


def _make_target(target_id='SERVER1', target_name='server1.example.com'):
    target = MagicMock()
    target.target_id = target_id
    target.target_name = target_name
    return target


# ─────────────────────────────────────────────────────────────
# Tests : MaintenanceWindowEvaluationStrategy
# ─────────────────────────────────────────────────────────────

class TestMaintenanceWindowEvaluationStrategy:
    """Tests purs (sans DB) de la stratégie."""

    def test_court_circuit_fenetre_non_requise(self):
        """requires_maintenance_window=False → satisfied=True sans appel inventaire."""
        strategy = MaintenanceWindowEvaluationStrategy()
        ctx = _make_ctx(requires_maintenance_window=False)

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is True
        assert 'non requise' in context['reason']
        ctx.inventory_service.get_next_maintenance_window.assert_not_called()

    def test_no_targets_satisfied(self):
        """Aucun target configuré → satisfied=True par défaut."""
        strategy = MaintenanceWindowEvaluationStrategy()
        ctx = _make_ctx(requires_maintenance_window=True, targets=[])

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is True
        assert 'No targets' in context['reason']

    def test_target_dans_fenetre(self):
        """Target dans sa fenêtre → satisfied=True."""
        strategy = MaintenanceWindowEvaluationStrategy()
        target = _make_target('SRV1')
        ctx = _make_ctx(requires_maintenance_window=True, targets=[target])
        ctx.inventory_service.get_next_maintenance_window.return_value = {
            'is_active': True,
            'start': None,
            'end': None,
        }

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is True
        assert context['reason'] == 'All targets in maintenance window'
        assert context['details'][0]['is_active'] is True

    def test_target_hors_fenetre(self):
        """Target hors fenêtre → satisfied=False."""
        from datetime import datetime, timezone as tz
        strategy = MaintenanceWindowEvaluationStrategy()
        target = _make_target('SRV1')
        ctx = _make_ctx(requires_maintenance_window=True, targets=[target])
        next_start = datetime(2026, 3, 20, 2, 0, 0, tzinfo=tz.utc)
        ctx.inventory_service.get_next_maintenance_window.return_value = {
            'is_active': False,
            'start': next_start,
        }

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is False
        assert 'outside' in context['reason'].lower() or 'One or more' in context['reason']
        assert 'next_possible_at' in context
        assert context['details'][0]['is_active'] is False

    def test_fenetre_non_configuree_bloque(self):
        """Pas de fenêtre configurée → satisfied=False (fail-safe)."""
        strategy = MaintenanceWindowEvaluationStrategy()
        target = _make_target('SRV1')
        ctx = _make_ctx(requires_maintenance_window=True, targets=[target])
        ctx.inventory_service.get_next_maintenance_window.return_value = None

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is False
        detail = context['details'][0]
        assert detail['is_active'] is False
        assert 'blocked by default' in detail['reason']

    def test_inventory_error_bloque(self):
        """Erreur d'inventaire → satisfied=False (safe default)."""
        strategy = MaintenanceWindowEvaluationStrategy()
        target = _make_target('SRV1')
        ctx = _make_ctx(requires_maintenance_window=True, targets=[target])
        ctx.inventory_service.get_next_maintenance_window.side_effect = InventoryServiceError(
            "Connection refused"
        )

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is False
        detail = context['details'][0]
        assert 'Inventory service error' in detail['reason']

    def test_implements_protocol(self):
        """MaintenanceWindowEvaluationStrategy respecte le Protocol GateEvaluationStrategy."""
        strategy = MaintenanceWindowEvaluationStrategy()
        assert isinstance(strategy, GateEvaluationStrategy)

    def test_targets_mixtes_un_hors_fenetre(self):
        """Deux targets : l'un en fenêtre, l'autre hors → satisfied=False (all_in_window)."""
        from datetime import datetime, timezone as tz
        strategy = MaintenanceWindowEvaluationStrategy()
        target_in = _make_target('SRV_IN', 'in.example.com')
        target_out = _make_target('SRV_OUT', 'out.example.com')
        ctx = _make_ctx(requires_maintenance_window=True, targets=[target_in, target_out])
        next_start = datetime(2026, 3, 21, 2, 0, 0, tzinfo=tz.utc)

        def fake_get_window(target_id):
            if target_id == 'SRV_IN':
                return {'is_active': True, 'start': None}
            return {'is_active': False, 'start': next_start}

        ctx.inventory_service.get_next_maintenance_window.side_effect = fake_get_window

        satisfied, context = strategy.evaluate(ctx)

        assert satisfied is False
        assert 'One or more targets outside maintenance window' in context['reason']
        assert len(context['details']) == 2
        in_detail = next(d for d in context['details'] if d['target_id'] == 'SRV_IN')
        out_detail = next(d for d in context['details'] if d['target_id'] == 'SRV_OUT')
        assert in_detail['is_active'] is True
        assert out_detail['is_active'] is False
        assert 'next_possible_at' in context


# ─────────────────────────────────────────────────────────────
# Tests : Dispatch dans GateEvaluator
# ─────────────────────────────────────────────────────────────

class TestGateEvaluatorDispatch:
    """Tests du dispatch vers evaluation_strategy dans GateEvaluator (sans DB)."""

    def _make_step(self, gate_conditions, requires_maintenance_window=False):
        """Step mocké avec gate_conditions et _env_config."""
        step = MagicMock()
        step.id = 99
        step.get_output.return_value = {'gate_conditions': gate_conditions}
        step.execution.get_parameters.return_value = {
            '_env_config': {'requires_maintenance_window': requires_maintenance_window}
        }
        return step

    def test_evaluation_strategy_none_et_non_manuel_retourne_no_evaluator(self):
        """Gate enregistré, evaluation_strategy=None, requires_manual_resolution=False
        → satisfied=False, reason='No evaluator implemented for: ...'"""
        condition_type = 'test_no_strategy'
        mock_def = GateDefinition(
            gate_type=condition_type,
            condition_type=condition_type,
            display_name='Test',
            category='test',
            requires_manual_resolution=False,
            evaluation_strategy=None,
        )

        step = self._make_step([{'type': condition_type}])
        mock_inventory = MagicMock(spec=InventoryService)
        evaluator = GateEvaluator(inventory_service=mock_inventory)

        with patch(
            'executions.gate_evaluator.gate_registry.get_for_condition_type',
            return_value=mock_def,
        ):
            satisfied, status = evaluator.evaluate(step)

        assert satisfied is False
        gate = status['gates'][0]
        assert gate['satisfied'] is False
        assert f'No evaluator implemented for: {condition_type}' in gate['reason']

    def test_requires_manual_resolution_retourne_approbation_explicite(self):
        """Gate requires_manual_resolution=True → satisfied=False, raison approbation."""
        condition_type = 'approval_granted'
        mock_def = GateDefinition(
            gate_type='approval',
            condition_type=condition_type,
            display_name='Approbation',
            category='approval',
            requires_manual_resolution=True,
        )

        step = self._make_step([{'type': condition_type}])
        mock_inventory = MagicMock(spec=InventoryService)
        evaluator = GateEvaluator(inventory_service=mock_inventory)

        with patch(
            'executions.gate_evaluator.gate_registry.get_for_condition_type',
            return_value=mock_def,
        ):
            satisfied, status = evaluator.evaluate(step)

        assert satisfied is False
        gate = status['gates'][0]
        assert gate['satisfied'] is False
        assert "approbation explicite" in gate['reason'].lower()

    def test_evaluation_strategy_appelee_et_resultat_retourne(self):
        """Gate avec evaluation_strategy → strategy.evaluate() est appelée et résultat propagé."""
        condition_type = 'mock_gate'
        mock_strategy = MagicMock()
        mock_strategy.evaluate.return_value = (True, {'reason': 'Mock OK'})

        mock_def = GateDefinition(
            gate_type=condition_type,
            condition_type=condition_type,
            display_name='Mock',
            category='test',
            requires_manual_resolution=False,
            evaluation_strategy=mock_strategy,
        )

        step = self._make_step([{'type': condition_type}])
        mock_inventory = MagicMock(spec=InventoryService)
        evaluator = GateEvaluator(inventory_service=mock_inventory)

        with patch(
            'executions.gate_evaluator.gate_registry.get_for_condition_type',
            return_value=mock_def,
        ):
            satisfied, status = evaluator.evaluate(step)

        assert satisfied is True
        assert mock_strategy.evaluate.called
        ctx_arg = mock_strategy.evaluate.call_args.args[0]
        assert isinstance(ctx_arg, GateEvaluationContext)
        assert ctx_arg.step is step
        gate = status['gates'][0]
        assert gate['reason'] == 'Mock OK'
