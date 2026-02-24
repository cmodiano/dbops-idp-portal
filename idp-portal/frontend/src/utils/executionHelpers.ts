/**
 * Execution helpers (Story 17.15).
 */

import type { ExecutionResponse } from '../types/api';
import type { WizardInitialParams } from '../types/wizard';

/**
 * Extract wizard pre-fill parameters from a past execution.
 * Returns null if the execution has no action (action deleted).
 *
 * Target names are extracted from `parameters._targets` (stored by backend
 * when target_names are provided at execution creation).
 */
export function prepareWizardParamsFromExecution(
  execution: ExecutionResponse,
): WizardInitialParams | null {
  if (!execution.action_id) return null;

  // Extract target_names from parameters._targets (backend stores them there)
  const params = execution.parameters as Record<string, unknown> | null;
  const targets = params?._targets;
  const targetNames = Array.isArray(targets) ? targets as string[] : undefined;

  // Build clean parameters without internal _targets field
  let cleanParameters: Record<string, unknown> | undefined;
  if (params) {
    const { _targets: _, ...rest } = params;
    if (Object.keys(rest).length > 0) {
      cleanParameters = rest;
    }
  }

  return {
    actionId: execution.action_id,
    targetNames,
    environment: execution.environment ?? undefined,
    parameters: cleanParameters,
  };
}
