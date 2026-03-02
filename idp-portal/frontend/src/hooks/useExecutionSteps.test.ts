/**
 * Tests for useExecutionSteps hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useExecutionSteps } from './useExecutionSteps';

vi.mock('../services/execution_service', () => ({
  getExecutionSteps: vi.fn(),
}));
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

import { getExecutionSteps } from '../services/execution_service';
const mockGetSteps = vi.mocked(getExecutionSteps);

describe('useExecutionSteps — coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty steps when enabled=false', () => {
    const { result } = renderHook(() => useExecutionSteps(1, false));
    expect(result.current.steps).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('returns empty steps when executionId=null', () => {
    const { result } = renderHook(() => useExecutionSteps(null, true));
    expect(result.current.steps).toEqual([]);
  });

  it('fetches steps when enabled=true and executionId set', async () => {
    const steps = [{ id: 1, name: 'Step 1' }];
    mockGetSteps.mockResolvedValue(steps as never);
    const { result } = renderHook(() => useExecutionSteps(42, true));
    await waitFor(() => expect(result.current.steps).toHaveLength(1));
    expect(mockGetSteps).toHaveBeenCalledWith(42);
  });

  it('sets error on fetch failure', async () => {
    mockGetSteps.mockRejectedValue(new Error('Steps error'));
    const { result } = renderHook(() => useExecutionSteps(42, true));
    await waitFor(() => expect(result.current.error).toBe('Steps error'));
  });
});
