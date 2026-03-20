/**
 * Tests for execution_core (Story 4.1, 7.4, 9.1, 9.2).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as executionCore from './execution_core';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

describe('execution_core', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('buildFilterParams', () => {
    it('returns empty string when no filters', () => {
      expect(executionCore.buildFilterParams()).toBe('');
      expect(executionCore.buildFilterParams(undefined)).toBe('');
    });

    it('builds params from all filter fields', () => {
      const params = executionCore.buildFilterParams({
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        action_id: 5,
        engine: 'Oracle',
        tags: ['rac', 'dataguard'],
        status: 'COMPLETED',
        environment: 'PROD',
      });
      expect(params).toContain('start_date=2024-01-01');
      expect(params).toContain('end_date=2024-12-31');
      expect(params).toContain('action_id=5');
      expect(params).toContain('engine=Oracle');
      expect(params).toContain('tags=rac%2Cdataguard');
      expect(params).toContain('status=COMPLETED');
      expect(params).toContain('environment=PROD');
    });

    it('skips tags when empty array', () => {
      const params = executionCore.buildFilterParams({ tags: [] });
      expect(params).not.toContain('tags=');
    });
  });

  describe('submitExecution', () => {
    it('POSTs to /executions with request body', async () => {
      const mock = { execution_id: 1, status: 'SUBMITTED' };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.submitExecution({
        action_id: 1,
        environment: 'dev',
        parameters: {},
      });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions', {
        method: 'POST',
        body: JSON.stringify({ action_id: 1, environment: 'dev', parameters: {} }),
      });
      expect(result).toEqual(mock);
    });
  });

  describe('getExecution', () => {
    it('fetches execution by ID', async () => {
      const mock = { id: 1, status: 'RUNNING' };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.getExecution(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1');
      expect(result).toEqual(mock);
    });
  });

  describe('getExecutionSteps', () => {
    it('fetches steps for execution', async () => {
      const mock = [{ id: 1, status: 'COMPLETED' }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.getExecutionSteps(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/steps');
      expect(result).toEqual(mock);
    });
  });

  describe('getStepLogs', () => {
    it('fetches logs for step', async () => {
      const mock = { logs: ['log1', 'log2'] };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.getStepLogs(1, 2);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/steps/2/logs');
      expect(result).toEqual(mock);
    });
  });

  describe('listExecutions', () => {
    it('fetches executions with default params', async () => {
      const mock = { data: [], pagination: { page: 1, total: 0 } };
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mock as any);

      await executionCore.listExecutions();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith(
        expect.stringContaining('limit=50&offset=0&scope=mine')
      );
    });

    it('includes filter params when provided', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ data: [], pagination: {} } as any);

      await executionCore.listExecutions(10, 5, 'all', { status: 'COMPLETED' });

      const url = vi.mocked(apiClient.apiFetchRaw).mock.calls[0][0] as string;
      expect(url).toContain('limit=10');
      expect(url).toContain('offset=5');
      expect(url).toContain('scope=all');
      expect(url).toContain('status=COMPLETED');
    });
  });

  describe('listPendingApprovals', () => {
    it('fetches pending approvals', async () => {
      const mock = { data: [], pagination: { total: 0 } };
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mock as any);

      const result = await executionCore.listPendingApprovals(20, 10);

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith(
        '/executions/pending-approvals?limit=20&offset=10'
      );
      expect(result).toEqual(mock);
    });
  });

  describe('getPendingApprovalsCount', () => {
    it('returns count from API', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ count: 5 } as any);

      const result = await executionCore.getPendingApprovalsCount();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith(
        '/executions/pending-approvals?count_only=true'
      );
      expect(result).toBe(5);
    });
  });

  describe('approveExecution', () => {
    it('POSTs approve with optional comment', async () => {
      const mock = { execution_id: 1, status: 'RUNNING' };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      await executionCore.approveExecution(1, 'Approved');

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/approve', {
        method: 'POST',
        body: JSON.stringify({ comment: 'Approved' }),
      });
    });

    it('POSTs approve without comment', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await executionCore.approveExecution(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/approve', {
        method: 'POST',
        body: JSON.stringify({}),
      });
    });
  });

  describe('rejectExecution', () => {
    it('POSTs reject with optional comment', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await executionCore.rejectExecution(1, 'Rejected');

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/reject', {
        method: 'POST',
        body: JSON.stringify({ comment: 'Rejected' }),
      });
    });
  });

  describe('cancelExecution', () => {
    it('PATCHes cancel', async () => {
      const mock = { id: 1, status: 'CANCELLED' };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.cancelExecution(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/cancel', {
        method: 'PATCH',
      });
      expect(result).toEqual(mock);
    });
  });

  describe('fetchRemediationSuggestions', () => {
    it('fetches remediation suggestions', async () => {
      const mock = [{ id: 1, suggestion: 'Restart' }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.fetchRemediationSuggestions(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/remediation');
      expect(result).toEqual(mock);
    });
  });

  describe('fetchRemediationContext', () => {
    it('fetches remediation context', async () => {
      const mock = { execution_id: 1, step_output: {} };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionCore.fetchRemediationContext(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/1/remediation-context');
      expect(result).toEqual(mock);
    });
  });
});
