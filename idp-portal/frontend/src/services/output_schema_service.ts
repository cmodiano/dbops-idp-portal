/**
 * Output Schema Service (Story 63.3).
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
