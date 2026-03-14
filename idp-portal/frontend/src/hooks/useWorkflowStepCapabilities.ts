/**
 * useWorkflowStepCapabilities — Story 82.6, AC3.
 *
 * Retourne les variants du step "gate" depuis les capacités backend.
 * Fallback vers GATE_TYPE_OPTIONS local si l'API échoue (résilience).
 */
import { useCapabilities } from './useCapabilities';
import type { GateVariant } from '../services/capabilities_service';

// Fallback local si API indisponible — comportement identique à l'existant
const GATE_TYPE_OPTIONS_FALLBACK: GateVariant[] = [
  { code: 'maintenance_window', label: 'Fenêtre de maintenance', config_schema: {} },
  { code: 'approval', label: 'Approbation manuelle', config_schema: {} },
];

export function useWorkflowStepCapabilities(): {
  gateVariants: GateVariant[];
  loading: boolean;
  error: string | null;
} {
  const { capabilities, loading, error } = useCapabilities();

  let gateVariants: GateVariant[];

  if (error) {
    // Fallback si erreur API
    gateVariants = GATE_TYPE_OPTIONS_FALLBACK;
  } else if (capabilities) {
    // Capacités chargées : rechercher le step gate (fallback si absent ou sans variants)
    const gateStep = capabilities.stepTypes.find((s) => s.code === 'gate');
    gateVariants = gateStep?.variants ?? GATE_TYPE_OPTIONS_FALLBACK;
  } else {
    // Chargement en cours (capabilities null, pas d'erreur)
    gateVariants = [];
  }

  return { gateVariants, loading, error };
}
