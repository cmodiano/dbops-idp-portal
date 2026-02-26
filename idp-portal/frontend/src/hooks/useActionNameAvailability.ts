/**
 * useActionNameAvailability — Encapsulation DIP de checkActionNameAvailable (admin_service).
 * Story 48.8 (SOLID-FE-4, AC3): Supprime l'import direct d'admin_service dans WizardStep1General.tsx.
 */

import { useCallback } from 'react';
import { checkActionNameAvailable } from '../services/admin_service';

export interface UseActionNameAvailabilityReturn {
  checkName: (name: string, excludeId?: number) => Promise<boolean>;
}

export function useActionNameAvailability(): UseActionNameAvailabilityReturn {
  const checkName = useCallback(
    (name: string, excludeId?: number) => checkActionNameAvailable(name, excludeId),
    []
  );
  return { checkName };
}
