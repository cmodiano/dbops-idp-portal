"""
Story 82.5: gate_registry — singleton + enregistrement des gates existants.
Story 83.2: Ajout evaluation_strategy sur maintenance_window.

Ce module est importé par GateHandler, GateEvaluator et catalog/validators.
Requiert Django initialisé (via strategies.py → inventory.services → ORM).
Note: definitions.py reste sans imports Django (importable avant ORM).
"""
from __future__ import annotations

from executions.gates.definitions import GateDefinition, GateDefinitionRegistry
from executions.gates.strategies import MaintenanceWindowEvaluationStrategy

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
    requires_manual_resolution=False,      # Auto-évalué via evaluation_strategy (Story 83.2)
    evaluation_strategy=MaintenanceWindowEvaluationStrategy(),
))

gate_registry.register(GateDefinition(
    gate_type='approval',
    condition_type='approval_granted',     # Différent du gate_type — mapping clé
    display_name='Approbation manuelle',
    category='approval',
    config_schema={},
    supports_timeout=True,
    requires_manual_resolution=True,       # Satisfait uniquement via POST /approve/
    # evaluation_strategy=None (défaut) — résolution manuelle, pas d'auto-évaluation
))
