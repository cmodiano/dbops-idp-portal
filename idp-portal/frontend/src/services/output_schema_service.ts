/**
 * Output Schema Service (Story 63.3, Story 63.9).
 * Fonctions pour récupérer les variables disponibles des schemas de sortie.
 */

import { apiFetch } from './api_client';

export interface OutputField {
  name: string;
  path: string;
  type: string;
  description: string;
}

export interface AvailableVariablesStep {
  step_id: string;
  step_name: string;
  step_type: string;
  variables: OutputField[];
}

export async function fetchAvailableVariables(workflowId: number): Promise<AvailableVariablesStep[]> {
  return apiFetch<AvailableVariablesStep[]>(
    `/output-schemas/workflows/${workflowId}/available-variables/`,
  );
}

/** Story 63.9: OutputSchema list item (pour le selector admin). */
export interface OutputSchemaListItem {
  id: number;
  name: string;
  schema_type: string;
  schema_json: { output_fields?: { name: string; type: string; description?: string }[] } | null;
}

/** Story 63.9: Charger les OutputSchema filtrés par schema_type. */
export async function fetchOutputSchemasList(schemaType?: string): Promise<OutputSchemaListItem[]> {
  const params = schemaType ? `?schema_type=${encodeURIComponent(schemaType)}` : '';
  return apiFetch<OutputSchemaListItem[]>(`/output-schemas/${params}`);
}
