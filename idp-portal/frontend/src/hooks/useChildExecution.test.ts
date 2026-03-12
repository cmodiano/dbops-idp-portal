/**
 * Tests for useChildExecution hook (Story 71.11, AC #4).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChildExecution } from './useChildExecution';
import * as executionService from '../services/execution_service';

vi.mock('../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(),
}));

describe('useChildExecution', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('état initial : childExecution=null, childSteps=[], loading=false, error=null', () => {
    const { result } = renderHook(() => useChildExecution(null, false));

    expect(result.current.childExecution).toBeNull();
    expect(result.current.childSteps).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('enabled=false — pas d\'appel API, état initial maintenu', () => {
    const { result } = renderHook(() => useChildExecution(5, false));

    expect(executionService.getExecution).not.toHaveBeenCalled();
    expect(result.current.childExecution).toBeNull();
  });

  it('childExecutionId=null — pas d\'appel API', () => {
    renderHook(() => useChildExecution(null, true));

    expect(executionService.getExecution).not.toHaveBeenCalled();
  });

  it('chargement réussi — childExecution et childSteps populés, loading=false', async () => {
    const mockExec = { id: 5, status: 'SUCCESS' } as any;
    const mockSteps = [{ id: 1, step_id: 'step-a' }] as any;
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExec);
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue(mockSteps);

    const { result } = renderHook(() => useChildExecution(5, true));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.childExecution).toEqual(mockExec);
    expect(result.current.childSteps).toEqual(mockSteps);
    expect(result.current.error).toBeNull();
  });

  it('erreur — error non-null, childExecution=null, childSteps=[]', async () => {
    vi.mocked(executionService.getExecution).mockRejectedValue(new Error('Not found'));
    vi.mocked(executionService.getExecutionSteps).mockRejectedValue(new Error('Not found'));

    const { result } = renderHook(() => useChildExecution(5, true));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Not found');
    expect(result.current.childExecution).toBeNull();
    expect(result.current.childSteps).toEqual([]);
  });

  it('cleanup (unmount pendant chargement) — pas de mise à jour d\'état après unmount', async () => {
    let resolveExec!: (v: any) => void;
    let resolveSteps!: (v: any) => void;
    vi.mocked(executionService.getExecution).mockReturnValue(new Promise(r => { resolveExec = r; }));
    vi.mocked(executionService.getExecutionSteps).mockReturnValue(new Promise(r => { resolveSteps = r; }));

    const { result, unmount } = renderHook(() => useChildExecution(5, true));

    // Unmount while loading
    unmount();

    // Resolve promises after unmount — should not cause state updates (no crash)
    await act(async () => {
      resolveExec({ id: 5, status: 'SUCCESS' });
      resolveSteps([]);
    });

    // State should remain at initial (null) because cancelled flag was set
    expect(result.current.childExecution).toBeNull();
  });
});
