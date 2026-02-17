/**
 * Tests for useRemediationSuggestions hook (Story 9.1, Task 16).
 *
 * Verifies:
 * - AC1: Fetches suggestions only when execution status is 'FAILED'
 * - AC5: Uses fetchRemediationSuggestions service function
 * - Resets suggestions when status changes from FAILED
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useRemediationSuggestions } from './useRemediationSuggestions';
import * as executionService from '../services/execution_service';
import type { RemediationSuggestion } from '../types/api';

vi.mock('../services/execution_service', () => ({
  fetchRemediationSuggestions: vi.fn(),
}));

const mockFetchRemediationSuggestions = executionService.fetchRemediationSuggestions as ReturnType<typeof vi.fn>;

describe('useRemediationSuggestions', () => {
  const mockSuggestions: RemediationSuggestion[] = [
    {
      action_id: 42,
      action_name: 'Fix Database Issue',
      action_description: 'Restarts the database listener',
      matching_rule: {
        error_pattern: 'ORA-\\d+',
        target_action_id: 42,
        environments: ['prod'],
        auto_trigger: false,
        risk_level: 'medium',
      },
    },
    {
      action_id: 10,
      action_name: 'Retry Connection',
      action_description: null,
      matching_rule: {
        error_pattern: 'timeout',
        target_action_id: 10,
        environments: ['dev', 'prod'],
        auto_trigger: true,
        risk_level: 'low',
      },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRemediationSuggestions.mockResolvedValue(mockSuggestions);
  });

  it('does not fetch when executionId is null', async () => {
    const { result } = renderHook(() =>
      useRemediationSuggestions(null, 'FAILED')
    );

    expect(result.current.suggestions).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockFetchRemediationSuggestions).not.toHaveBeenCalled();
  });

  it('does not fetch when status is not FAILED', async () => {
    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'COMPLETED')
    );

    expect(result.current.suggestions).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(mockFetchRemediationSuggestions).not.toHaveBeenCalled();
  });

  it('does not fetch when status is RUNNING', async () => {
    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'RUNNING')
    );

    expect(result.current.suggestions).toBeNull();
    expect(mockFetchRemediationSuggestions).not.toHaveBeenCalled();
  });

  it('fetches suggestions when executionId is present and status is FAILED (AC1)', async () => {
    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'FAILED')
    );

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockFetchRemediationSuggestions).toHaveBeenCalledWith(123);
    expect(result.current.suggestions).toEqual(mockSuggestions);
    expect(result.current.error).toBeNull();
  });

  it('handles fetch error gracefully', async () => {
    const testError = new Error('Network error');
    mockFetchRemediationSuggestions.mockRejectedValue(testError);

    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.suggestions).toBeNull();
    expect(result.current.error).toEqual(testError);
  });

  it('resets suggestions when status changes from FAILED to COMPLETED', async () => {
    const { result, rerender } = renderHook(
      ({ executionId, status }) => useRemediationSuggestions(executionId, status),
      { initialProps: { executionId: 123, status: 'FAILED' as const } }
    );

    await waitFor(() => {
      expect(result.current.suggestions).toEqual(mockSuggestions);
    });

    // Change status to COMPLETED
    rerender({ executionId: 123, status: 'COMPLETED' as const });

    expect(result.current.suggestions).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('refetches when executionId changes', async () => {
    const { result, rerender } = renderHook(
      ({ executionId, status }) => useRemediationSuggestions(executionId, status),
      { initialProps: { executionId: 123, status: 'FAILED' as const } }
    );

    await waitFor(() => {
      expect(result.current.suggestions).toEqual(mockSuggestions);
    });

    expect(mockFetchRemediationSuggestions).toHaveBeenCalledTimes(1);

    // Change executionId
    rerender({ executionId: 456, status: 'FAILED' as const });

    await waitFor(() => {
      expect(mockFetchRemediationSuggestions).toHaveBeenCalledTimes(2);
    });

    expect(mockFetchRemediationSuggestions).toHaveBeenLastCalledWith(456);
  });

  it('provides refetch function that re-fetches suggestions', async () => {
    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.suggestions).toEqual(mockSuggestions);
    });

    expect(mockFetchRemediationSuggestions).toHaveBeenCalledTimes(1);

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    expect(mockFetchRemediationSuggestions).toHaveBeenCalledTimes(2);
  });

  it('handles non-Error exceptions', async () => {
    mockFetchRemediationSuggestions.mockRejectedValue('string error');

    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('Unknown error');
  });

  it('returns empty array when API returns empty suggestions', async () => {
    mockFetchRemediationSuggestions.mockResolvedValue([]);

    const { result } = renderHook(() =>
      useRemediationSuggestions(123, 'FAILED')
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.suggestions).toEqual([]);
    expect(result.current.error).toBeNull();
  });
});
