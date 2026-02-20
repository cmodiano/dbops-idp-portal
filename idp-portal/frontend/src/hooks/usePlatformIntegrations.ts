/**
 * usePlatformIntegrations — Fetch active platform integrations for action forms.
 * Story 31.1: Replaces usePlatforms in ActionForm/ActionWizard. Loads integrations
 * with integration_role='platform' from the IntegrationTypeCatalogue.
 */

import { useCallback, useEffect, useState } from 'react';
import { getIntegrations, getIntegrationTypes } from '../services/integrations_service';
import type { IntegrationResponse } from '../types/api';

export interface UsePlatformIntegrationsReturn {
  integrations: IntegrationResponse[];
  integrationOptions: { value: number; label: string }[];
  loading: boolean;
  error: string | null;
  getIntegrationById: (id: number) => IntegrationResponse | undefined;
}

export function usePlatformIntegrations(): UsePlatformIntegrationsReturn {
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const types = await getIntegrationTypes('platform');
        const platformCodes = new Set(types.map((t) => t.code));
        const all = await getIntegrations();
        if (!cancelled) {
          const platformIntegrations = all.filter(
            (i) => platformCodes.has(i.type) && i.status !== 'invalid',
          );
          setIntegrations(platformIntegrations);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur inconnue');
          setIntegrations([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const integrationOptions = integrations.map((i) => ({
    value: i.id,
    label: `${i.name} — ${i.type}`,
  }));

  const getIntegrationById = useCallback(
    (id: number): IntegrationResponse | undefined =>
      integrations.find((i) => i.id === id),
    [integrations],
  );

  return { integrations, integrationOptions, loading, error, getIntegrationById };
}
