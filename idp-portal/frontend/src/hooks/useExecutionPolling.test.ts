/**
 * Tests for useExecutionPolling hook (Story 19.0, AC8-10, AC12).
 *
 * Verifies:
 * - Polling starts when enabled=true
 * - Polling calls getExecution + getExecutionSteps at configured interval
 * - Polling stops on terminal statuses (COMPLETED, FAILED, CANCELLED)
 * - Cleanup on unmount (no memory leaks)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useExecutionPolling } from './useExecutionPolling';
import * as executionService from '../services/execution_service';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

vi.mock('../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(),
}));

vi.mock('../services/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));

const mockGetExecution = executionService.getExecution as ReturnType<typeof vi.fn>;
const mockGetExecutionSteps = executionService.getExecutionSteps as ReturnType<typeof vi.fn>;

const mockExecutionRunning: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Test Action',
  user_id: 1,
  environment: 'dev',
  parameters: null,
  status: 'RUNNING',
  servicenow_change_id: null,
  started_at: '2026-02-08T10:00:00Z',
  completed_at: null,
  created_at: '2026-02-08T10:00:00Z',
};

const mockExecutionCompleted: ExecutionResponse = {
  ...mockExecutionRunning,
  status: 'COMPLETED',
  completed_at: '2026-02-08T10:01:00Z',
};

const mockSteps: ExecutionStepResponse[] = [
  {
    id: 1,
    execution_id: 1,
    step_order: 1,
    step_name: 'Préparation',
    step_type: 'prerequisite',
    status: 'RUNNING',
    started_at: '2026-02-08T10:00:01Z',
    completed_at: null,
    output: null,
    platform_job_id: null,
    error_message: null,
  },
];

/** Helper: advance fake timers AND flush React updates */
async function advanceAndFlush(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('useExecutionPolling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not poll when enabled=false', async () => {
    renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: false }),
    );

    await advanceAndFlush(0);

    expect(mockGetExecution).not.toHaveBeenCalled();
    expect(mockGetExecutionSteps).not.toHaveBeenCalled();
  });

  it('does not poll when executionId is null', async () => {
    renderHook(() =>
      useExecutionPolling({ executionId: null, enabled: true }),
    );

    await advanceAndFlush(0);

    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it('fetches immediately when enabled', async () => {
    mockGetExecution.mockResolvedValue(mockExecutionRunning);
    mockGetExecutionSteps.mockResolvedValue(mockSteps);

    const { result } = renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: true }),
    );

    await advanceAndFlush(0);

    expect(mockGetExecution).toHaveBeenCalledWith(1);
    expect(mockGetExecutionSteps).toHaveBeenCalledWith(1);
    expect(result.current.execution).toEqual(mockExecutionRunning);
    expect(result.current.steps).toEqual(mockSteps);
    expect(result.current.isPolling).toBe(true);
  });

  it('polls at the configured interval (2500ms)', async () => {
    mockGetExecution.mockResolvedValue(mockExecutionRunning);
    mockGetExecutionSteps.mockResolvedValue(mockSteps);

    renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: true, interval: 2500 }),
    );

    // Flush initial fetch
    await advanceAndFlush(0);
    expect(mockGetExecution).toHaveBeenCalledTimes(1);

    // Advance to first interval
    await advanceAndFlush(2500);
    expect(mockGetExecution).toHaveBeenCalledTimes(2);

    // Advance to second interval
    await advanceAndFlush(2500);
    expect(mockGetExecution).toHaveBeenCalledTimes(3);
  });

  it('stops polling when execution status becomes COMPLETED', async () => {
    mockGetExecution
      .mockResolvedValueOnce(mockExecutionRunning)
      .mockResolvedValueOnce(mockExecutionCompleted);
    mockGetExecutionSteps.mockResolvedValue(mockSteps);

    const { result } = renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: true, interval: 2500 }),
    );

    // Initial fetch → RUNNING
    await advanceAndFlush(0);
    expect(result.current.execution?.status).toBe('RUNNING');

    // Next poll → COMPLETED
    await advanceAndFlush(2500);
    expect(result.current.execution?.status).toBe('COMPLETED');
    expect(result.current.isPolling).toBe(false);

    // No more fetches after stop
    await advanceAndFlush(5000);
    expect(mockGetExecution).toHaveBeenCalledTimes(2);
  });

  it('stops polling when execution status becomes FAILED', async () => {
    const mockFailed: ExecutionResponse = {
      ...mockExecutionRunning,
      status: 'FAILED',
    };
    mockGetExecution
      .mockResolvedValueOnce(mockExecutionRunning)
      .mockResolvedValueOnce(mockFailed);
    mockGetExecutionSteps.mockResolvedValue([]);

    const { result } = renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: true, interval: 2500 }),
    );

    await advanceAndFlush(0);
    expect(result.current.execution?.status).toBe('RUNNING');

    await advanceAndFlush(2500);
    expect(result.current.execution?.status).toBe('FAILED');
    expect(result.current.isPolling).toBe(false);
  });

  it('handles fetch errors gracefully', async () => {
    mockGetExecution.mockRejectedValue(new Error('Network error'));
    mockGetExecutionSteps.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: true }),
    );

    await advanceAndFlush(0);

    expect(result.current.error).toBeTruthy();
    expect(result.current.error?.message).toBe('Network error');
  });

  it('cleans up interval on unmount', async () => {
    mockGetExecution.mockResolvedValue(mockExecutionRunning);
    mockGetExecutionSteps.mockResolvedValue(mockSteps);

    const { unmount } = renderHook(() =>
      useExecutionPolling({ executionId: 1, enabled: true, interval: 2500 }),
    );

    await advanceAndFlush(0);
    expect(mockGetExecution).toHaveBeenCalledTimes(1);

    unmount();

    // Advance timers after unmount - should NOT trigger more fetches
    await advanceAndFlush(5000);
    expect(mockGetExecution).toHaveBeenCalledTimes(1);
  });
});
