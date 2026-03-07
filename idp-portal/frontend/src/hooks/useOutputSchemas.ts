/**
 * useOutputSchemas — Hook React pour charger les variables disponibles d'un workflow (Story 63.3).
 * Pattern identique à useIntegrations.
 */
import { useState, useEffect } from 'react';
import { fetchAvailableVariables } from '../services/output_schema_service';
import type { AvailableVariablesStep } from '../services/output_schema_service';

export function useOutputSchemas(workflowId: number | undefined) {
  const [availableVariables, setAvailableVariables] = useState<AvailableVariablesStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!workflowId) { setAvailableVariables([]); setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAvailableVariables(workflowId)
      .then((data) => { if (!cancelled) setAvailableVariables(data); })
      .catch((err) => {
        if (!cancelled) {
          setAvailableVariables([]);
          setError(err instanceof Error ? err.message : 'Erreur de chargement');
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [workflowId]);

  return { availableVariables, loading, error };
}
