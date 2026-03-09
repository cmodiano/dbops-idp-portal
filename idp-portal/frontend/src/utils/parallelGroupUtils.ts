/**
 * parallelGroupUtils — Story 65.6
 *
 * Utilities for parallel_group step matching and aggregated status computation.
 * The backend does NOT create an ExecutionStep for the parallel_group itself —
 * only sub-steps are persisted. These helpers derive group state from sub-step statuses.
 */

import type { WorkflowStep } from '../types/api/catalog';
import type { ExecutionStepResponse, ExecutionStepStatus } from '../types/api/executions';

/**
 * Finds the ExecutionSteps corresponding to the sub-steps of a parallel_group.
 * Prefers config_step_id matching; falls back to step_name for legacy data.
 */
export function findExecutionStepsForParallelGroup(
  parallelGroupStep: WorkflowStep,
  workflowSteps: WorkflowStep[],
  executionSteps: ExecutionStepResponse[],
): ExecutionStepResponse[] {
  if (!parallelGroupStep.parallel_steps?.length) return [];

  return parallelGroupStep.parallel_steps.flatMap((stepId) => {
    const byConfig = executionSteps.find((es) => es.config_step_id === stepId);
    if (byConfig) return [byConfig];
    const wf = workflowSteps.find((s) => s.step_id === stepId);
    const byName = wf?.name ? executionSteps.find((es) => es.step_name === wf.name) : undefined;
    return byName ? [byName] : [];
  });
}

/**
 * Computes the aggregated status of a parallel_group from its sub-step statuses.
 * Rules (aligned with backend fail-fast behaviour):
 * - FAILED  if ≥1 sub-step is FAILED
 * - RUNNING if ≥1 sub-step is RUNNING (and no FAILED)
 * - COMPLETED if all sub-steps are COMPLETED
 * - SKIPPED   if all sub-steps are SKIPPED
 * - PENDING   otherwise (including 0 sub-steps)
 */
export function computeParallelGroupStatus(
  subSteps: ExecutionStepResponse[],
): ExecutionStepStatus {
  if (subSteps.length === 0) return 'PENDING';
  const statuses = subSteps.map((s) => s.status);
  if (statuses.some((s) => s === 'FAILED')) return 'FAILED';
  if (statuses.some((s) => s === 'RUNNING')) return 'RUNNING';
  if (statuses.every((s) => s === 'COMPLETED')) return 'COMPLETED';
  if (statuses.every((s) => s === 'SKIPPED')) return 'SKIPPED';
  return 'PENDING';
}

/**
 * Builds a map indexed by step_id of parallel_groups with their resolved sub-steps.
 * Used by WorkflowExecutionGraph and TimelineList.
 */
export function buildParallelGroupMap(
  workflowSteps: WorkflowStep[],
  executionSteps: ExecutionStepResponse[],
): Map<string, { groupStep: WorkflowStep; subSteps: ExecutionStepResponse[] }> {
  const result = new Map<string, { groupStep: WorkflowStep; subSteps: ExecutionStepResponse[] }>();
  for (const step of workflowSteps) {
    if (step.step_type === 'parallel_group' && step.step_id) {
      result.set(step.step_id, {
        groupStep: step,
        subSteps: findExecutionStepsForParallelGroup(step, workflowSteps, executionSteps),
      });
    }
  }
  return result;
}

/**
 * Returns the set of step_ids and step_names belonging to any parallel_group.
 * Callers should prefer config_step_id when matching; use step_name for legacy.
 * Only includes step_ids that resolve to a workflow step (ignores orphans).
 * Used by TimelineList to know if a step should be skipped (rendered inside its group section).
 */
export function getStepNamesInParallelGroups(
  workflowSteps: WorkflowStep[],
): Set<string> {
  const ids = new Set<string>();
  for (const step of workflowSteps) {
    if (step.step_type === 'parallel_group' && step.parallel_steps) {
      for (const subStepId of step.parallel_steps) {
        const subStep = workflowSteps.find((s) => s.step_id === subStepId);
        if (subStep) {
          ids.add(subStepId);
          if (subStep.name) ids.add(subStep.name);
        }
      }
    }
  }
  return ids;
}
