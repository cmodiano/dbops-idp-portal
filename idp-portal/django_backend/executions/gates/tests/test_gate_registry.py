"""Tests unitaires du GateRegistry — Story 82.5, Story 83.4."""
import pytest

from executions.gates.definitions import GateDefinition, GateDefinitionRegistry, GateResolutionStrategy
from executions.gates.registry import gate_registry


class TestGateDefinitionRegistry:
    """Tests isolés sur GateDefinitionRegistry (instance fraîche, pas le singleton)."""

    def test_register_and_get(self):
        registry = GateDefinitionRegistry()
        defn = GateDefinition(
            gate_type='test_gate',
            condition_type='test_condition',
            display_name='Test Gate',
            category='test',
        )
        registry.register(defn)
        assert registry.get('test_gate') is defn

    def test_get_unknown_raises_key_error(self):
        registry = GateDefinitionRegistry()
        with pytest.raises(KeyError):
            registry.get('unknown')

    def test_get_for_condition_type(self):
        registry = GateDefinitionRegistry()
        defn = GateDefinition(
            gate_type='approval',
            condition_type='approval_granted',
            display_name='Approval',
            category='approval',
            requires_manual_resolution=True,
        )
        registry.register(defn)
        assert registry.get_for_condition_type('approval_granted') is defn

    def test_get_for_condition_type_unknown_raises(self):
        registry = GateDefinitionRegistry()
        with pytest.raises(KeyError):
            registry.get_for_condition_type('not_registered')

    def test_list_types_order(self):
        registry = GateDefinitionRegistry()
        for gate_type, cond_type in [('a', 'ca'), ('b', 'cb'), ('c', 'cc')]:
            registry.register(GateDefinition(gate_type=gate_type, condition_type=cond_type,
                                              display_name=gate_type, category='x'))
        assert registry.list_types() == ['a', 'b', 'c']

    def test_get_valid_condition_types(self):
        registry = GateDefinitionRegistry()
        registry.register(GateDefinition(gate_type='approval', condition_type='approval_granted',
                                          display_name='A', category='x'))
        registry.register(GateDefinition(gate_type='mw', condition_type='maintenance_window',
                                          display_name='B', category='y'))
        assert registry.get_valid_condition_types() == frozenset({'approval_granted', 'maintenance_window'})

    def test_is_registered(self):
        registry = GateDefinitionRegistry()
        registry.register(GateDefinition(gate_type='g1', condition_type='c1', display_name='G1', category='x'))
        assert registry.is_registered('g1') is True
        assert registry.is_registered('unknown') is False

    def test_reregister_replaces(self):
        registry = GateDefinitionRegistry()
        defn1 = GateDefinition(gate_type='g', condition_type='c', display_name='V1', category='x')
        defn2 = GateDefinition(gate_type='g', condition_type='c', display_name='V2', category='x')
        registry.register(defn1)
        registry.register(defn2)
        assert registry.get('g').display_name == 'V2'


class TestIsManualConditionType:
    """Tests unitaires de GateDefinitionRegistry.is_manual_condition_type() — Story 84.2 AC9."""

    def test_known_manual_type_returns_true(self):
        """approval_granted est enregistré avec requires_manual_resolution=True."""
        assert gate_registry.is_manual_condition_type('approval_granted') is True

    def test_known_auto_type_returns_false(self):
        """maintenance_window est enregistré avec requires_manual_resolution=False."""
        assert gate_registry.is_manual_condition_type('maintenance_window') is False

    def test_unknown_type_returns_false_no_exception(self):
        """Type inconnu → False, pas de KeyError."""
        assert gate_registry.is_manual_condition_type('unknown_type') is False

    def test_empty_string_returns_false(self):
        """Chaîne vide → False, pas d'exception."""
        assert gate_registry.is_manual_condition_type('') is False

    def test_isolated_registry_manual_type(self):
        """Instance fraîche : type manual enregistré → True."""
        registry = GateDefinitionRegistry()
        registry.register(GateDefinition(
            gate_type='review',
            condition_type='review_required',
            display_name='Revue',
            category='review',
            requires_manual_resolution=True,
        ))
        assert registry.is_manual_condition_type('review_required') is True

    def test_isolated_registry_auto_type(self):
        """Instance fraîche : type auto enregistré → False."""
        registry = GateDefinitionRegistry()
        registry.register(GateDefinition(
            gate_type='check',
            condition_type='check_passed',
            display_name='Check',
            category='check',
            requires_manual_resolution=False,
        ))
        assert registry.is_manual_condition_type('check_passed') is False

    def test_isolated_registry_unknown_returns_false(self):
        """Instance fraîche vide : type inconnu → False."""
        registry = GateDefinitionRegistry()
        assert registry.is_manual_condition_type('anything') is False


class TestGateRegistrySingleton:
    """Tests sur le singleton gate_registry (état réel)."""

    def test_list_types_contains_two_gates(self):
        types = gate_registry.list_types()
        # Vérifie l'ordre d'insertion (maintenance_window enregistré en premier dans registry.py)
        assert types == ['maintenance_window', 'approval']

    def test_maintenance_window_condition_type(self):
        defn = gate_registry.get('maintenance_window')
        assert defn.condition_type == 'maintenance_window'
        assert defn.requires_manual_resolution is False
        assert defn.supports_timeout is True

    def test_approval_condition_type(self):
        defn = gate_registry.get('approval')
        assert defn.condition_type == 'approval_granted'
        assert defn.requires_manual_resolution is True

    def test_valid_condition_types(self):
        assert gate_registry.get_valid_condition_types() == frozenset({
            'maintenance_window',
            'approval_granted',
        })

    def test_get_for_condition_type_approval_granted(self):
        defn = gate_registry.get_for_condition_type('approval_granted')
        assert defn.gate_type == 'approval'

    def test_display_names(self):
        assert gate_registry.get('maintenance_window').display_name == 'Fenêtre de maintenance'
        assert gate_registry.get('approval').display_name == 'Approbation manuelle'

    def test_maintenance_window_resolution_strategy_is_none(self):
        """maintenance_window est auto-évalué → resolution_strategy=None."""
        defn = gate_registry.get('maintenance_window')
        assert defn.resolution_strategy is None

    def test_approval_resolution_strategy_is_none(self):
        """approval utilise endpoint /approve/ → resolution_strategy=None (non encore implémentée)."""
        defn = gate_registry.get('approval')
        assert defn.resolution_strategy is None


class TestGateResolutionStrategy:
    """Tests du Protocol GateResolutionStrategy (Story 83.4)."""

    def test_gate_definition_has_resolution_strategy_field(self):
        """GateDefinition a un champ resolution_strategy avec défaut None."""
        defn = GateDefinition(
            gate_type='test',
            condition_type='test_condition',
            display_name='Test',
            category='test',
        )
        assert defn.resolution_strategy is None

    def test_gate_resolution_strategy_is_runtime_checkable(self):
        """GateResolutionStrategy est un Protocol runtime_checkable."""
        class MockResolution:
            def resolve(self, ctx):
                return True, {}

        assert isinstance(MockResolution(), GateResolutionStrategy)

    def test_gate_definition_resolution_strategy_excluded_from_equality(self):
        """resolution_strategy est compare=False → n'affecte pas l'égalité."""
        class MockResolution:
            def resolve(self, ctx):
                return True, {}

        defn1 = GateDefinition(
            gate_type='test',
            condition_type='test_condition',
            display_name='Test',
            category='test',
        )
        defn2 = GateDefinition(
            gate_type='test',
            condition_type='test_condition',
            display_name='Test',
            category='test',
            resolution_strategy=MockResolution(),
        )
        assert defn1 == defn2
