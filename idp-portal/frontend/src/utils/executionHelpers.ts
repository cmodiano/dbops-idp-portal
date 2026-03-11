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

/** Rejection info extracted from execution steps (ADR-007, V118). */
export interface RejectionInfo {
  rejectedById: number | null;
  rejectedAt: string | null;
  rejectionReason: string | null;
}

/**
 * Extract approval info from execution steps.
 * Picks the latest decided gate by approved_at (source of truth per ADR-007).
 */
export function getApprovalInfoFromSteps(steps: ExecutionStepResponse[]): ApprovalInfo {
  const withApproval = steps.filter((s): s is ExecutionStepResponse & { approved_at: string } =>
    s.approved_at != null
  );
  if (withApproval.length === 0) {
    return { approvedById: null, approvedAt: null, approvalComment: null };
  }
  const latest = withApproval.reduce((a, b) =>
    (a.approved_at ?? '') >= (b.approved_at ?? '') ? a : b
  );
  return {
    approvedById: latest.approved_by_id ?? null,
    approvedAt: latest.approved_at ?? null,
    approvalComment: latest.approval_comment ?? null,
  };
}

/**
 * Extract rejection info from execution steps (ADR-007, V118).
 * Picks the latest decided gate by rejected_at (gate rejection).
 */
export function getRejectionInfoFromSteps(steps: ExecutionStepResponse[]): RejectionInfo {
  const withRejection = steps.filter((s): s is ExecutionStepResponse & { rejected_at: string } =>
    s.rejected_at != null
  );
  if (withRejection.length === 0) {
    return { rejectedById: null, rejectedAt: null, rejectionReason: null };
  }
  const latest = withRejection.reduce((a, b) =>
    (a.rejected_at ?? '') >= (b.rejected_at ?? '') ? a : b
  );
  return {
    rejectedById: latest.rejected_by_id ?? null,
    rejectedAt: latest.rejected_at ?? null,
    rejectionReason: latest.approval_comment ?? null,
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
