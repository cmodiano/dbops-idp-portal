"""
Story 82.5: gate_registry — singleton + enregistrement des gates existants.

Ce module est importé par GateHandler, GateEvaluator et catalog/validators.
Il ne doit pas importer de modules Django pour rester importable avant l'ORM.
"""
from __future__ import annotations

from executions.gates.definitions import GateDefinition, GateDefinitionRegistry

gate_registry = GateDefinitionRegistry()

# ─────────────────────────────────────────────────────────────
# Enregistrement des 2 gates implémentés — source de vérité centralisée (Story 82.5)
# Source: docs/backend/epic-82-extensibilite-gates-services-platforms.md
# ─────────────────────────────────────────────────────────────

gate_registry.register(GateDefinition(
    gate_type='maintenance_window',
    condition_type='maintenance_window',   # Identique à gate_type (cas le plus simple)
    display_name='Fenêtre de maintenance',
    category='maintenance',
    config_schema={},
    supports_timeout=True,
    requires_manual_resolution=False,      # Auto-évalué par GateEvaluator._check_maintenance_window
))

gate_registry.register(GateDefinition(
    gate_type='approval',
    condition_type='approval_granted',     # Différent du gate_type — mapping clé
    display_name='Approbation manuelle',
    category='approval',
    config_schema={},
    supports_timeout=True,
    requires_manual_resolution=True,       # Satisfait uniquement via POST /approve/
))
