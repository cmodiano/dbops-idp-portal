/**
 * useIntegrationTypesByRole — Filter integration types by role (Story 29.1).
 * Wraps useIntegrationTypes and filters locally by integration_role.
 */

import { useMemo } from 'react';
import { useIntegrationTypes } from './useIntegrationTypes';
import type { IntegrationTypeCatalogue, IntegrationRoleType } from '../types/api';

export interface UseIntegrationTypesByRoleReturn {
  types: IntegrationTypeCatalogue[];
  loading: boolean;
  error: string | null;
  isFallback: boolean;
}

export function useIntegrationTypesByRole(
  role?: IntegrationRoleType,
): UseIntegrationTypesByRoleReturn {
  const { types, loading, error, isFallback } = useIntegrationTypes();

  const filtered = useMemo(() => {
    if (!role) return types;
    // Guard against null/undefined integration_role (defensive coding)
    return types.filter((t) => t.integration_role && t.integration_role === role);
  }, [types, role]);

  return { types: filtered, loading, error, isFallback };
}
