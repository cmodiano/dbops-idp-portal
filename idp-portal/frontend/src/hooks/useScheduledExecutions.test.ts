/**
 * Tests for useScheduledExecutions hook (Story 39.7 — coverage).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useScheduledExecutions } from './useScheduledExecutions';
import * as scheduledService from '../services/scheduled_execution_service';
import type { ScheduledExecutionListItem } from '../types/api';

vi.mock('../services/scheduled_execution_service');
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

const mockExecution: ScheduledExecutionListItem = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy',
  environment: 'prod',
  targets: [],
  parameters: null,
  scheduled_at: '2025-06-01T10:00:00Z',
  recurring_pattern: null,
  status: 'PENDING',
  created_at: '2025-01-01T00:00:00Z',
};

const mockApiResponse = {
  data: [mockExecution],
  available_actions: [{ action_id: 10, action_name: 'Deploy' }],
  total: 1,
  page: 1,
  page_size: 100,
};

describe('useScheduledExecutions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts with initial state', () => {
    const { result } = renderHook(() => useScheduledExecutions());
    expect(result.current.executions).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.togglingPatternId).toBeNull();
  });

  it('fetchExecutions sets loading and fetches data', async () => {
    vi.mocked(scheduledService.listScheduledExecutions).mockResolvedValue(mockApiResponse);
    const { result } = renderHook(() => useScheduledExecutions());

    await act(async () => {
      await result.current.fetchExecutions({});
    });

    expect(result.current.executions).toHaveLength(1);
    expect(result.current.executions[0].id).toBe(1);
    expect(result.current.availableActions).toHaveLength(1);
    expect(result.current.loading).toBe(false);
  });

  it('sets error on fetchExecutions failure', async () => {
    vi.mocked(scheduledService.listScheduledExecutions).mockRejectedValue(new Error('Network'));
    const { result } = renderHook(() => useScheduledExecutions());

    await act(async () => {
      await result.current.fetchExecutions({});
    });

    expect(result.current.error).toBe('Erreur lors du chargement des exécutions planifiées');
    expect(result.current.loading).toBe(false);
  });

  it('sets loading on first fetch', async () => {
    let resolve: (v: typeof mockApiResponse) => void;
    const promise = new Promise<typeof mockApiResponse>((r) => { resolve = r; });
    vi.mocked(scheduledService.listScheduledExecutions).mockReturnValue(promise);

    const { result } = renderHook(() => useScheduledExecutions());

    act(() => {
      void result.current.fetchExecutions({});
    });

    expect(result.current.loading).toBe(true);

    await act(async () => {
      resolve!(mockApiResponse);
      await promise;
    });

    expect(result.current.loading).toBe(false);
  });

  it('toggleRecurrence returns success on success', async () => {
    vi.mocked(scheduledService.toggleRecurringPattern).mockResolvedValue(undefined);
    const { result } = renderHook(() => useScheduledExecutions());

    let toggleResult: { success: boolean };
    await act(async () => {
      toggleResult = await result.current.toggleRecurrence(1, true);
    });

    expect(toggleResult!.success).toBe(true);
    expect(result.current.togglingPatternId).toBeNull();
  });

  it('toggleRecurrence returns error on failure', async () => {
    vi.mocked(scheduledService.toggleRecurringPattern).mockRejectedValue(new Error('Toggle failed'));
    const { result } = renderHook(() => useScheduledExecutions());

    let toggleResult: { success: boolean; error?: string };
    await act(async () => {
      toggleResult = await result.current.toggleRecurrence(1, false);
    });

    expect(toggleResult!.success).toBe(false);
    expect(toggleResult!.error).toBe('Toggle failed');
    expect(result.current.togglingPatternId).toBeNull();
  });

  it('toggleRecurrence returns generic error for non-Error failures', async () => {
    vi.mocked(scheduledService.toggleRecurringPattern).mockRejectedValue('unknown');
    const { result } = renderHook(() => useScheduledExecutions());

    let toggleResult: { success: boolean; error?: string };
    await act(async () => {
      toggleResult = await result.current.toggleRecurrence(1, false);
    });

    expect(toggleResult!.success).toBe(false);
    expect(toggleResult!.error).toBe('Une erreur est survenue');
  });

  it('handles response without available_actions', async () => {
    vi.mocked(scheduledService.listScheduledExecutions).mockResolvedValue({
      data: [mockExecution],
      total: 1,
      page: 1,
      page_size: 100,
    });
    const { result } = renderHook(() => useScheduledExecutions());

    await act(async () => {
      await result.current.fetchExecutions({});
    });

    expect(result.current.executions).toHaveLength(1);
    expect(result.current.availableActions).toHaveLength(0); // not updated
  });
});
