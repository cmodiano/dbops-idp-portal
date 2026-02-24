/**
 * useIntegrations - Hook for loading all integrations (Story 38.6, SOLID-FE-4).
 *
 * Wraps getIntegrations to remove direct service imports from CalendarFiltersPanel.tsx.
 */
import { useState, useEffect } from 'react';
import { getIntegrations } from '../services/integrations_service';
import type { IntegrationResponse } from '../types/api';

export function useIntegrations() {
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getIntegrations()
      .then((data) => { if (!cancelled) setIntegrations(data); })
      .catch((err) => { if (!cancelled) { setIntegrations([]); setError(err instanceof Error ? err.message : 'Erreur de chargement des intégrations'); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return { integrations, loading, error };
}
