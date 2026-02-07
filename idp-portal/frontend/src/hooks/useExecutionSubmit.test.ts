import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { App } from 'antd';
import React from 'react';
import { useExecutionSubmit } from './useExecutionSubmit';
import { submitExecution } from '../services/execution_service';
import { createScheduledExecution } from '../services/scheduled_execution_service';

vi.mock('../services/execution_service', () => ({
  submitExecution: vi.fn(),
}));

vi.mock('../services/scheduled_execution_service', () => ({
  createScheduledExecution: vi.fn(),
  validateCronExpression: vi.fn(),
  getCronNextExecutions: vi.fn(),
}));

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(App, null, children);

describe('useExecutionSubmit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('submitImmediate', () => {
    it('returns execution_id on success', async () => {
      vi.mocked(submitExecution).mockResolvedValue({ execution_id: 42 } as any);

      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });

      let executionId: number | null = null;
      await act(async () => {
        executionId = await result.current.submitImmediate({
          action_id: 1,
          environment: 'dev',
          parameters: { pdb: 'test' },
        });
      });

      expect(executionId).toBe(42);
      expect(result.current.isSubmitting).toBe(false);
      expect(result.current.submitError).toBeNull();
    });

    it('sets error on failure', async () => {
      vi.mocked(submitExecution).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });

      let executionId: number | null = null;
      await act(async () => {
        executionId = await result.current.submitImmediate({
          action_id: 1,
          environment: 'dev',
          parameters: null,
        });
      });

      expect(executionId).toBeNull();
      expect(result.current.submitError).toBe('Network error');
    });

    it('handles INVALID_PARENT_STATUS error', async () => {
      const error = new Error('FAILED') as Error & { code: string };
      error.code = 'INVALID_PARENT_STATUS';
      vi.mocked(submitExecution).mockRejectedValue(error);

      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });

      await act(async () => {
        await result.current.submitImmediate({
          action_id: 1,
          environment: 'dev',
          parameters: null,
        });
      });

      expect(result.current.submitError).toBe('L\'exécution parente n\'est pas en échec');
    });

    it('passes target_names and workflow_step_parameters', async () => {
      vi.mocked(submitExecution).mockResolvedValue({ execution_id: 99 } as any);

      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });

      await act(async () => {
        await result.current.submitImmediate({
          action_id: 1,
          target_names: ['srv-01', 'srv-02'],
          parameters: null,
          workflow_step_parameters: { '1': { parameters: { foo: 'bar' } } },
        });
      });

      expect(submitExecution).toHaveBeenCalledWith(
        expect.objectContaining({
          target_names: ['srv-01', 'srv-02'],
          workflow_step_parameters: { '1': { parameters: { foo: 'bar' } } },
        })
      );
    });
  });

  describe('submitScheduled', () => {
    it('returns scheduled_execution_id on success', async () => {
      vi.mocked(createScheduledExecution).mockResolvedValue({ scheduled_execution_id: 10 } as any);

      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });

      let schedId: number | null = null;
      await act(async () => {
        schedId = await result.current.submitScheduled({
          action_id: 1,
          environment: 'dev',
          parameters: null,
          scheduled_at: '2026-03-01T10:00:00Z',
        });
      });

      expect(schedId).toBe(10);
    });

    it('sets schedulingError on failure', async () => {
      vi.mocked(createScheduledExecution).mockRejectedValue(new Error('Server error'));

      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });

      await act(async () => {
        await result.current.submitScheduled({
          action_id: 1,
          environment: 'dev',
          parameters: null,
        });
      });

      expect(result.current.schedulingError).toBe('Server error');
    });
  });

  describe('scheduling state', () => {
    it('has initial scheduling state', () => {
      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });
      expect(result.current.scheduling.isScheduling).toBe(false);
      expect(result.current.scheduling.schedulingType).toBe('one-time');
      expect(result.current.scheduling.cronExpression).toBe('');
    });

    it('updates scheduling state partially', () => {
      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });
      act(() => result.current.updateScheduling({ isScheduling: true, schedulingType: 'daily' }));
      expect(result.current.scheduling.isScheduling).toBe(true);
      expect(result.current.scheduling.schedulingType).toBe('daily');
      expect(result.current.scheduling.dailyHour).toBe(2); // unchanged
    });

    it('resetScheduling returns to initial state', () => {
      const { result } = renderHook(() => useExecutionSubmit(), { wrapper });
      act(() => result.current.updateScheduling({ isScheduling: true, cronExpression: '0 2 * * *' }));
      act(() => result.current.resetScheduling());
      expect(result.current.scheduling.isScheduling).toBe(false);
      expect(result.current.scheduling.cronExpression).toBe('');
      expect(result.current.schedulingError).toBeNull();
    });
  });
});
