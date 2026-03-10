/**
 * Execution helpers (Story 17.15).
 */

import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';
import type { WizardInitialParams } from '../types/wizard';

/** Approval info extracted from execution steps (ADR-007, Story 71.2). */
export interface ApprovalInfo {
  approvedById: number | null;
  approvedAt: string | null;
  approvalComment: string | null;
}

/**
 * Extract approval info from execution steps.
 * Finds the first step with `approved_by_id` set (source of truth per ADR-007).
 */
export function getApprovalInfoFromSteps(steps: ExecutionStepResponse[]): ApprovalInfo {
  const approvalStep = steps.find(s => s.approved_by_id != null);
  if (!approvalStep) {
    return { approvedById: null, approvedAt: null, approvalComment: null };
  }
  return {
    approvedById: approvalStep.approved_by_id ?? null,
    approvedAt: approvalStep.approved_at ?? null,
    approvalComment: approvalStep.approval_comment ?? null,
  };
}

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
