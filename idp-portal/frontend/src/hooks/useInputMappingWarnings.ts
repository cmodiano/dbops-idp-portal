/**
 * useInputMappingWarnings — Hook partagé pour calculer les warnings de validation
 * des références de steps dans les input_mapping (Story 57.20).
 *
 * Extrait via useMemo les step_id invalides référencés dans les valeurs de l'input_mapping.
 */

import { useMemo } from 'react';
import { validateStepReferences } from '../utils/validateStepReferences';

export function useInputMappingWarnings(
  inputMapping: Record<string, string> | null | undefined,
  availableStepOptions: { value: string; label: string }[] | undefined,
): string[] {
  return useMemo(() => {
    if (!inputMapping || !availableStepOptions) return [];
    const stepIds = availableStepOptions.map((s) => s.value);
    const warnings: string[] = [];
    for (const value of Object.values(inputMapping)) {
      const invalid = validateStepReferences(value, stepIds);
      for (const id of invalid) {
        const msg = `Référence inconnue : step_id '${id}' n'existe pas dans ce workflow`;
        if (!warnings.includes(msg)) warnings.push(msg);
      }
    }
    return warnings;
  }, [inputMapping, availableStepOptions]);
}
