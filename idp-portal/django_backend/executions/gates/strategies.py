"""
Story 83-2: Stratégies d'évaluation des gates — logique déplacée depuis GateEvaluator.

Chaque stratégie encapsule la logique d'évaluation d'un type de gate auto-évalué.
GateEvaluator devient un simple orchestrateur qui délègue à ces stratégies.
"""
import structlog

from core.middleware import get_correlation_id
from executions.gates.definitions import GateEvaluationContext
from inventory.services import InventoryServiceError

logger = structlog.get_logger(__name__)


class MaintenanceWindowEvaluationStrategy:
    """Évalue si tous les targets d'exécution sont dans leur fenêtre de maintenance.

    Logique extraite de GateEvaluator._check_maintenance_window() (Story 83-2).
    """

    def evaluate(self, ctx: GateEvaluationContext) -> tuple[bool, dict]:
        """Évalue la condition maintenance_window.

        Args:
            ctx: Contexte d'évaluation portant step, condition, inventory_service,
                 requires_maintenance_window.

        Returns:
            tuple[bool, dict]: (satisfied, context avec reason/next_possible_at/details)
        """
        # Court-circuit : fenêtre non requise pour cet environnement
        if not ctx.requires_maintenance_window:
            return True, {'reason': "Plage de maintenance non requise pour cet environnement"}

        correlation_id = get_correlation_id()
        targets = ctx.step.execution.targets.all()

        if not targets.exists():
            logger.info(
                "gate_evaluator_no_targets",
                step_id=ctx.step.id,
                correlation_id=correlation_id,
            )
            return True, {'reason': 'No targets configured — condition satisfied by default'}

        all_in_window = True
        next_starts = []
        target_details = []

        for target in targets:
            try:
                window = ctx.inventory_service.get_next_maintenance_window(target.target_id)

                if window is None:
                    # Pas de fenêtre configurée → BLOQUE par défaut (fail-safe).
                    # Rationale : les gates maintenance_window protègent les changements PROD.
                    # Si l'inventaire ne définit pas de fenêtre, bloquer est plus sûr qu'autoriser.
                    all_in_window = False
                    target_details.append({
                        'target_id': target.target_id,
                        'target_name': target.target_name,
                        'is_active': False,
                        'reason': 'No maintenance window configured in inventory (blocked by default)',
                    })
                    continue

                if window.get('is_active'):
                    target_details.append({
                        'target_id': target.target_id,
                        'target_name': target.target_name,
                        'is_active': True,
                        'reason': 'Within maintenance window',
                    })
                else:
                    all_in_window = False
                    next_start = window.get('start')
                    if next_start:
                        next_starts.append(next_start)
                    target_details.append({
                        'target_id': target.target_id,
                        'target_name': target.target_name,
                        'is_active': False,
                        'reason': 'Outside maintenance window',
                        'next_start': next_start.isoformat() if next_start else None,
                    })

            except InventoryServiceError as e:
                logger.error(
                    "gate_evaluator_inventory_error",
                    step_id=ctx.step.id,
                    target_id=target.target_id,
                    error=str(e),
                    correlation_id=correlation_id,
                )
                # Erreur inventaire → condition NON satisfaite (safe default)
                all_in_window = False
                target_details.append({
                    'target_id': target.target_id,
                    'target_name': target.target_name,
                    'is_active': False,
                    'reason': f'Inventory service error: {str(e)}',
                })

        context = {
            'reason': 'All targets in maintenance window' if all_in_window
                      else 'One or more targets outside maintenance window',
            'details': target_details,
        }

        if next_starts:
            context['next_possible_at'] = max(next_starts).isoformat()

        return all_in_window, context
