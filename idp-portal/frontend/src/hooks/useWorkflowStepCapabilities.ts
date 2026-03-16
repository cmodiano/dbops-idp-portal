/**
 * useWorkflowStepCapabilities — Story 83-12.
 *
 * Retourne les variants du step "gate" depuis les capacités backend.
 * Résilience technique uniquement : liste vide si API indisponible ou données absentes.
 * Aucune vérité métier locale — le backend reste source de vérité unique.
 */
import { useCapabilities } from './useCapabilities';
import type { GateVariant } from '../services/capabilities_service';

export function useWorkflowStepCapabilities(): {
  gateVariants: GateVariant[];
  loading: boolean;
  error: string | null;
} {
  const { capabilities, loading, error } = useCapabilities();

  let gateVariants: GateVariant[];

  if (error) {
    // Résilience technique : erreur API → liste vide (pas de fallback métier)
    gateVariants = [];
  } else if (capabilities) {
    // Capacités chargées : rechercher le step gate
    const gateStep = capabilities.stepTypes.find((s) => s.code === 'gate');
    gateVariants = gateStep?.variants ?? [];
  } else {
    // Chargement en cours (capabilities null, pas d'erreur)
    gateVariants = [];
  }

  return { gateVariants, loading, error };
}
