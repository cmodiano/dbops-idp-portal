/**
 * Tests for useCancelRunningExecution hook (Story 71.11, AC #4).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCancelRunningExecution } from './useCancelRunningExecution';
import * as executionService from '../services/execution_service';

vi.mock('../services/execution_service', () => ({
  cancelExecution: vi.fn(),
}));

describe('useCancelRunningExecution', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('cancelRunningExecution(id) appelle cancelExecution(id)', async () => {
    vi.mocked(executionService.cancelExecution).mockResolvedValue(undefined as any);

    const { result } = renderHook(() => useCancelRunningExecution());

    await act(async () => {
      await result.current.cancelRunningExecution(42);
    });

    expect(executionService.cancelExecution).toHaveBeenCalledWith(42);
  });

  it('la fonction cancelRunningExecution est stable entre re-renders (useCallback)', () => {
    const { result, rerender } = renderHook(() => useCancelRunningExecution());

    const firstRef = result.current.cancelRunningExecution;
    rerender();
    const secondRef = result.current.cancelRunningExecution;

    expect(firstRef).toBe(secondRef);
  });
});
