/**
 * useServiceNowIntegrations — Fetch active ServiceNow integrations for gate configuration.
 * Story 31.6: Loads integrations of type 'servicenow' from admin API, with sessionStorage cache.
 */

import { useEffect, useState } from 'react';
import { getIntegrationsByType } from '../services/integrations_service';
import type { IntegrationResponse } from '../types/api';

const CACHE_KEY = 'sn_integrations';
const CACHE_DURATION_MS = 5 * 60 * 1000; // 5 minutes

export interface UseServiceNowIntegrationsReturn {
  integrations: IntegrationResponse[];
  integrationOptions: { value: number; label: string }[];
  loading: boolean;
  error: string | null;
}

export function useServiceNowIntegrations(): UseServiceNowIntegrationsReturn {
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Check cache first
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached) as {
          data: IntegrationResponse[];
          timestamp: number;
        };
        if (Date.now() - timestamp < CACHE_DURATION_MS && Array.isArray(data)) {
          setIntegrations(data);
          setLoading(false);
          return;
        }
      }
    } catch {
      /* ignore invalid cache */
    }

    async function load() {
      try {
        const all = await getIntegrationsByType('servicenow');
        if (!cancelled) {
          const snIntegrations = all.filter(
            (i) => i.status !== 'invalid',
          );
          setIntegrations(snIntegrations);
          setError(null);
          sessionStorage.setItem(
            CACHE_KEY,
            JSON.stringify({ data: snIntegrations, timestamp: Date.now() }),
          );
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur');
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
    label: `${i.name} (${i.type})`,
  }));

  return { integrations, integrationOptions, loading, error };
}
