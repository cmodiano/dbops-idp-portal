/**
 * useVaultIntegrations — Fetch active Vault integrations for secret service selection.
 * Story 27.11: Used in IntegrationForm to populate the "Service de secrets" dropdown.
 */

import { useEffect, useState } from 'react';
import { getIntegrations } from '../services/integrations_service';
import type { IntegrationResponse } from '../types/api';

export interface UseVaultIntegrationsReturn {
  vaultIntegrations: IntegrationResponse[];
  loading: boolean;
  error: string | null;
}

export function useVaultIntegrations(): UseVaultIntegrationsReturn {
  const [vaultIntegrations, setVaultIntegrations] = useState<IntegrationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getIntegrations()
      .then((integrations) => {
        if (cancelled) return;
        const vaults = integrations.filter(
          (i) => i.type === 'vault' && i.status !== 'invalid',
        );
        setVaultIntegrations(vaults);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur inconnue';
        setError(msg);
        setVaultIntegrations([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { vaultIntegrations, loading, error };
}
