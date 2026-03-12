/**
 * Utility functions for approval context formatting (Story 58.6).
 * Extracted to a separate file to satisfy react-refresh/only-export-components.
 */

/** Replace underscores with spaces, trim, and capitalize first letter. */
export function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').trim().replace(/^./, c => c.toUpperCase());
}

/** Format a parameter value for display. Booleans → Oui/Non, null → —, objects → JSON indenté (Story 72.4). */
export function formatParamValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Oui' : 'Non';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** Env config label mapping. */
export const ENV_CONFIG_LABELS: Record<string, string> = {
  impact_level: "Niveau d'impact",
  change_required: 'Changement requis',
  requires_maintenance_window: 'Fenêtre de maintenance',
  requires_approval: 'Approbation requise',
  change_model_code: 'Code modèle de changement',
};

/** Impact level label mapping. */
export const IMPACT_LEVEL_LABELS: Record<string, string> = {
  low: 'Faible',
  medium: 'Moyen',
  high: 'Élevé',
  critical: 'Critique',
};

/** Internal keys to separate from business parameters. */
const INTERNAL_KEYS = ['_targets', '_env_config', 'workflow_step_parameters'];

/** Separate internal fields from business parameters. */
export function partitionParameters(parameters: Record<string, unknown> | null) {
  const empty = {
    targets: [] as string[],
    envConfig: null as Record<string, unknown> | null,
    stepParams: null as Record<string, unknown> | null,
    businessParams: {} as Record<string, unknown>,
  };
  if (!parameters) return empty;

  const targets = Array.isArray(parameters._targets) ? (parameters._targets as string[]) : [];
  const envConfig = (parameters._env_config && typeof parameters._env_config === 'object' && !Array.isArray(parameters._env_config))
    ? (parameters._env_config as Record<string, unknown>)
    : null;
  const stepParams = (parameters.workflow_step_parameters && typeof parameters.workflow_step_parameters === 'object' && !Array.isArray(parameters.workflow_step_parameters))
    ? (parameters.workflow_step_parameters as Record<string, unknown>)
    : null;

  const businessParams: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(parameters)) {
    if (!INTERNAL_KEYS.includes(k)) {
      businessParams[k] = v;
    }
  }

  return { targets, envConfig, stepParams, businessParams };
}
