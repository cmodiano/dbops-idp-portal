/**
 * Tests for executionHelpers (Story 17.15).
 *
 * AC3: prepareWizardParamsFromExecution extracts correct parameters.
 */

import { describe, it, expect } from 'vitest';
import { prepareWizardParamsFromExecution, getApprovalInfoFromSteps } from './executionHelpers';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

function makeExecution(overrides?: Partial<ExecutionResponse>): ExecutionResponse {
  return {
    id: 1,
    action_id: 10,
    action_name: 'Create PDB',
    user_id: 1,
    environment: 'dev',
    parameters: null,
    status: 'COMPLETED',
    servicenow_change_id: null,
    started_at: '2026-01-28T10:00:00Z',
    completed_at: '2026-01-28T10:05:00Z',
    created_at: '2026-01-28T09:59:00Z',
    ...overrides,
  };
}

describe('prepareWizardParamsFromExecution', () => {
  it('extracts action_id and environment', () => {
    const result = prepareWizardParamsFromExecution(makeExecution());
    expect(result).not.toBeNull();
    expect(result!.actionId).toBe(10);
    expect(result!.environment).toBe('dev');
  });

  it('extracts target_names from parameters._targets', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({
        parameters: {
          _targets: ['srv-dev-01', 'srv-dev-02'],
          db_name: 'mydb',
        },
      })
    );
    expect(result).not.toBeNull();
    expect(result!.targetNames).toEqual(['srv-dev-01', 'srv-dev-02']);
  });

  it('removes _targets from clean parameters', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({
        parameters: {
          _targets: ['srv-dev-01'],
          db_name: 'mydb',
          batch_size: 100,
        },
      })
    );
    expect(result).not.toBeNull();
    expect(result!.parameters).toEqual({ db_name: 'mydb', batch_size: 100 });
    expect(result!.parameters).not.toHaveProperty('_targets');
  });

  it('returns undefined parameters when only _targets present', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({
        parameters: { _targets: ['srv-dev-01'] },
      })
    );
    expect(result).not.toBeNull();
    expect(result!.parameters).toBeUndefined();
  });

  it('returns undefined targetNames when no _targets', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({ parameters: { db_name: 'mydb' } })
    );
    expect(result).not.toBeNull();
    expect(result!.targetNames).toBeUndefined();
  });

  it('returns null when action_id is 0', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({ action_id: 0 })
    );
    expect(result).toBeNull();
  });

  it('handles null parameters', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({ parameters: null })
    );
    expect(result).not.toBeNull();
    expect(result!.parameters).toBeUndefined();
    expect(result!.targetNames).toBeUndefined();
  });

  it('handles non-array _targets gracefully', () => {
    const result = prepareWizardParamsFromExecution(
      makeExecution({
        parameters: { _targets: 'not-an-array', db_name: 'mydb' },
      })
    );
    expect(result).not.toBeNull();
    expect(result!.targetNames).toBeUndefined();
    expect(result!.parameters).toEqual({ db_name: 'mydb' });
  });
});

// --- Tests for getApprovalInfoFromSteps (Story 71.2, AC2/AC7) ---

function makeStep(overrides?: Partial<ExecutionStepResponse>): ExecutionStepResponse {
  return {
    id: 1,
    execution_id: 100,
    step_order: 1,
    step_name: 'vault',
    step_type: 'vault',
    status: 'COMPLETED',
    started_at: '2026-01-28T10:00:00Z',
    completed_at: '2026-01-28T10:01:00Z',
    output: null,
    platform_job_id: null,
    error_message: null,
    ...overrides,
  };
}

describe('getApprovalInfoFromSteps', () => {
  it('returns nulls when no step has approval info', () => {
    const steps = [makeStep(), makeStep({ id: 2, step_order: 2 })];
    const result = getApprovalInfoFromSteps(steps);
    expect(result).toEqual({ approvedById: null, approvedAt: null, approvalComment: null });
  });

  it('returns nulls for empty steps array', () => {
    const result = getApprovalInfoFromSteps([]);
    expect(result).toEqual({ approvedById: null, approvedAt: null, approvalComment: null });
  });

  it('extracts approval info from a COMPLETED approval step', () => {
    const steps = [
      makeStep({ id: 1, step_order: 1 }),
      makeStep({
        id: 2,
        step_order: 2,
        status: 'COMPLETED',
        approved_by_id: 42,
        approved_at: '2026-01-28T10:02:00Z',
        approval_comment: 'Looks good',
      }),
    ];
    const result = getApprovalInfoFromSteps(steps);
    expect(result).toEqual({
      approvedById: 42,
      approvedAt: '2026-01-28T10:02:00Z',
      approvalComment: 'Looks good',
    });
  });

  it('extracts approval info from a REJECTED step (approval_comment as rejection reason)', () => {
    const steps = [
      makeStep({
        id: 1,
        step_order: 1,
        status: 'FAILED',
        approved_by_id: 7,
        approved_at: '2026-01-28T10:03:00Z',
        approval_comment: 'Not ready for prod',
      }),
    ];
    const result = getApprovalInfoFromSteps(steps);
    expect(result).toEqual({
      approvedById: 7,
      approvedAt: '2026-01-28T10:03:00Z',
      approvalComment: 'Not ready for prod',
    });
  });

  it('returns first step with approval when multiple steps have approval info', () => {
    const steps = [
      makeStep({
        id: 1,
        step_order: 1,
        approved_by_id: 10,
        approved_at: '2026-01-28T10:00:00Z',
        approval_comment: 'First',
      }),
      makeStep({
        id: 2,
        step_order: 2,
        approved_by_id: 20,
        approved_at: '2026-01-28T11:00:00Z',
        approval_comment: 'Second',
      }),
    ];
    const result = getApprovalInfoFromSteps(steps);
    expect(result.approvedById).toBe(10);
    expect(result.approvalComment).toBe('First');
  });

  it('handles step with approved_by_id but no comment', () => {
    const steps = [
      makeStep({
        id: 1,
        approved_by_id: 5,
        approved_at: '2026-01-28T10:00:00Z',
      }),
    ];
    const result = getApprovalInfoFromSteps(steps);
    expect(result).toEqual({
      approvedById: 5,
      approvedAt: '2026-01-28T10:00:00Z',
      approvalComment: null,
    });
  });
});
