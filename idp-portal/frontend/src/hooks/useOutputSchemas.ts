/**
 * useOutputSchemas — Hook React pour charger les variables disponibles d'un workflow (Story 63.3).
 * useOutputSchemasList — Hook pour charger les OutputSchema par type (Story 71.1, AC1).
 * Pattern identique à useIntegrations.
 */
import { useState, useEffect } from 'react';
import { fetchAvailableVariables, fetchOutputSchemasList } from '../services/output_schema_service';
import type { AvailableVariablesStep, OutputSchemaListItem } from '../services/output_schema_service';
import logger from '../services/logger';

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

/**
 * Story 71.1, AC1: Charge la liste des OutputSchema filtrés par schemaType.
 * Encapsule fetchOutputSchemasList() pour supprimer l'import direct dans OutputSchemaPanel.
 */
export function useOutputSchemasList(schemaType?: string, enabled = true) {
  const [schemas, setSchemas] = useState<OutputSchemaListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchOutputSchemasList(schemaType)
      .then((data) => { if (!cancelled) setSchemas(data); })
      .catch((err: unknown) => {
        if (!cancelled) {
          logger.error('output_schemas_list_load_error', { error: String(err) });
          setError('Impossible de charger les schémas d\'output.');
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [schemaType, enabled]);

  return { schemas, loading, error };
}
