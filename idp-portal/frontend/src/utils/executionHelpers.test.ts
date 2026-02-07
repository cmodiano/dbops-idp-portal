/**
 * Tests for executionHelpers (Story 17.15).
 *
 * AC3: prepareWizardParamsFromExecution extracts correct parameters.
 */

import { describe, it, expect } from 'vitest';
import { prepareWizardParamsFromExecution } from './executionHelpers';
import type { ExecutionResponse } from '../types/api';

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
