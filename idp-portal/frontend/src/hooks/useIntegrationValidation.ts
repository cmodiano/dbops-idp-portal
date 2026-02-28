/**
 * useIntegrationValidation — Encapsulation DIP de validateIntegration/validateAllIntegrations (integrations_service).
 * Story 54.15 (SOLID-FE-4, AC5): Supprime les imports directs depuis integrations_service dans IntegrationsTable.tsx.
 * Note: pas de chargement au mount — les fonctions sont déclenchées sur action utilisateur.
 */

import { useState, useCallback } from 'react';
import { validateIntegration, validateAllIntegrations } from '../services/integrations_service';
import type { IntegrationValidationResponse, IntegrationValidateAllResponse } from '../types/api';

export interface UseIntegrationValidationReturn {
  validateOne: (id: number) => Promise<IntegrationValidationResponse>;
  validateAll: () => Promise<IntegrationValidateAllResponse>;
  validatingId: number | null;
  validatingAll: boolean;
}

export function useIntegrationValidation(): UseIntegrationValidationReturn {
  const [validatingId, setValidatingId] = useState<number | null>(null);
  const [validatingAll, setValidatingAll] = useState(false);

  const validateOne = useCallback(async (id: number): Promise<IntegrationValidationResponse> => {
    setValidatingId(id);
    try {
      return await validateIntegration(id);
    } finally {
      setValidatingId(null);
    }
  }, []);

  const validateAll = useCallback(async (): Promise<IntegrationValidateAllResponse> => {
    setValidatingAll(true);
    try {
      return await validateAllIntegrations();
    } finally {
      setValidatingAll(false);
    }
  }, []);

  return { validateOne, validateAll, validatingId, validatingAll };
}
