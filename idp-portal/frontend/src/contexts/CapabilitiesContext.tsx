/**
 * CapabilitiesContext — PERF-FE-01 (Story 88-7).
 *
 * Fournit les capabilities (plateformes, services, steps) à tous les composants
 * React Flow enfants sans multiplier les useState/useEffect par nœud.
 *
 * Usage :
 *   Parent canvas : <CapabilitiesContext.Provider value={capabilities}>
 *   Composant nœud : const capabilities = useCapabilitiesContext();
 */
import { createContext, useContext } from 'react';
import type { CapabilitiesState } from '../hooks/useCapabilities';

export const CapabilitiesContext = createContext<CapabilitiesState | null>(null);

/**
 * Hook de consommation du contexte capabilities.
 * Retourne null si utilisé hors d'un CapabilitiesContext.Provider.
 * Le comportement null est identique à celui de useCapabilities() pendant le chargement.
 */
export function useCapabilitiesContext(): CapabilitiesState | null {
  return useContext(CapabilitiesContext);
}
