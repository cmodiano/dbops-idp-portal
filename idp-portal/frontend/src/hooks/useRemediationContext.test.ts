/**
 * Tests for useRemediationContext hook (Story 9.2, Task 25).
 *
 * Verifies:
 * - AC2: Fetches context only when execution status is 'FAILED'
 * - AC3: Uses fetchRemediationContext service function
 * - Resets context when status changes from FAILED
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useRemediationContext } from './useRemediationContext';
import * as executionService from '../services/execution_service';
import type { RemediationContext } from '../types/api';

vi.mock('../services/execution_service', () => ({
  fetchRemediationContext: vi.fn(),
}));

const mockFetchRemediationContext = executionService.fetchRemediationContext as ReturnType<typeof vi.fn>;

describe('useRemediationContext', () => {
  const mockContextWithSuccess: RemediationContext = {
    has_remediation: true,
    successful_remediation: true,
    remediation_actions: [
      {
        execution_id: 2,
        action_name: 'Fix Database',
        status: 'COMPLETED',
        created_at: '2026-02-02T10:00:00Z',
        completed_at: '2026-02-02T10:05:00Z',
      },
    ],
  };

  const mockContextNoRemediation: RemediationContext = {
    has_remediation: false,
    successful_remediation: false,
    remediation_actions: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRemediationContext.mockResolvedValue(mockContextWithSuccess);
  });

  it('does not fetch when executionId is null', async () => {
    const { result } = renderHook(() =>
      useRemediationContext(null, 'FAILED')
    );

    expect(result.current.context).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockFetchRemediationContext).not.toHaveBeenCalled();
  });

  it('does not fetch when status is not FAILED', async () => {
    const { result } = renderHook(() =>
      useRemediationContext(123, 'COMPLETED')
    );

    expect(result.current.context).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(mockFetchRemediationContext).not.toHaveBeenCalled();
  });

  it('does not fetch when status is RUNNING', async () => {
    const { result } = renderHook(() =>
      useRemediationContext(123, 'RUNNING')
    );

    expect(result.current.context).toBeNull();
    expect(mockFetchRemediationContext).not.toHaveBeenCalled();
  });

  it('fetches context when executionId is present and status is FAILED (AC2)', async () => {
    const { result } = renderHook(() =>
      useRemediationContext(123, 'FAILED')
    );

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockFetchRemediationContext).toHaveBeenCalledWith(123);
    expect(result.current.context).toEqual(mockContextWithSuccess);
    expect(result.current.error).toBeNull();
  });

  it('handles fetch error gracefully', async () => {
    const testError = new Error('Network error');
    mockFetchRemediationContext.mockRejectedValue(testError);

    const { result } = renderHook(() =>
      useRemediationContext(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.context).toBeNull();
    expect(result.current.error).toEqual(testError);
  });

  it('resets context when status changes from FAILED to COMPLETED', async () => {
    const { result, rerender } = renderHook(
      ({ executionId, status }) => useRemediationContext(executionId, status),
      { initialProps: { executionId: 123, status: 'FAILED' as const } }
    );

    await waitFor(() => {
      expect(result.current.context).toEqual(mockContextWithSuccess);
    });

    // Change status to COMPLETED
    rerender({ executionId: 123, status: 'COMPLETED' as const });

    expect(result.current.context).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('refetches when executionId changes', async () => {
    const { result, rerender } = renderHook(
      ({ executionId, status }) => useRemediationContext(executionId, status),
      { initialProps: { executionId: 123, status: 'FAILED' as const } }
    );

    await waitFor(() => {
      expect(result.current.context).toEqual(mockContextWithSuccess);
    });

    expect(mockFetchRemediationContext).toHaveBeenCalledTimes(1);

    // Change executionId
    rerender({ executionId: 456, status: 'FAILED' as const });

    await waitFor(() => {
      expect(mockFetchRemediationContext).toHaveBeenCalledTimes(2);
    });

    expect(mockFetchRemediationContext).toHaveBeenLastCalledWith(456);
  });

  it('provides refetch function that re-fetches context', async () => {
    const { result } = renderHook(() =>
      useRemediationContext(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.context).toEqual(mockContextWithSuccess);
    });

    expect(mockFetchRemediationContext).toHaveBeenCalledTimes(1);

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    expect(mockFetchRemediationContext).toHaveBeenCalledTimes(2);
  });

  it('handles non-Error exceptions', async () => {
    mockFetchRemediationContext.mockRejectedValue('string error');

    const { result } = renderHook(() =>
      useRemediationContext(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('Unknown error');
  });

  it('returns context with no remediation when API returns empty', async () => {
    mockFetchRemediationContext.mockResolvedValue(mockContextNoRemediation);

    const { result } = renderHook(() =>
      useRemediationContext(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.context).toEqual(mockContextNoRemediation);
    expect(result.current.context?.has_remediation).toBe(false);
    expect(result.current.context?.successful_remediation).toBe(false);
    expect(result.current.context?.remediation_actions).toEqual([]);
    expect(result.current.error).toBeNull();
  });
});
