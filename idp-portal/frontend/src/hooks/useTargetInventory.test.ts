import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useTargetInventory } from './useTargetInventory';
import { fetchInventoryItems } from '../services/execution_service';

vi.mock('../services/execution_service', () => ({
  submitExecution: vi.fn(),
  fetchInventoryItems: vi.fn().mockResolvedValue([]),
  fetchInventoryTargets: vi.fn().mockResolvedValue([]),
}));

describe('useTargetInventory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchInventoryItems).mockResolvedValue([
      { id: 'dev', name: 'Developpement', environment: null },
      { id: 'staging', name: 'Staging', environment: null },
      { id: 'prod', name: 'Production', environment: null },
    ]);
  });

  it('loads environments on mount when open', async () => {
    const { result } = renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 0,
        parameterFields: [],
        environment: null,
      })
    );

    await waitFor(() => {
      expect(result.current.environmentsCache).not.toBeNull();
    });

    expect(result.current.environmentsCache).toHaveLength(3);
    expect(fetchInventoryItems).toHaveBeenCalledWith('environments');
  });

  it('does not load when closed', () => {
    renderHook(() =>
      useTargetInventory({
        open: false,
        currentStep: 0,
        parameterFields: [],
        environment: null,
      })
    );

    expect(fetchInventoryItems).not.toHaveBeenCalled();
  });

  it('handles inventory unavailable with cache fallback', async () => {
    const cachedItems = [{ id: 'dev', name: 'Dev', environment: null }];
    const error = new Error('Unavailable') as Error & {
      code: string;
      useCache: boolean;
      cachedItems: typeof cachedItems;
    };
    error.code = 'INVENTORY_UNAVAILABLE';
    error.useCache = true;
    error.cachedItems = cachedItems;

    vi.mocked(fetchInventoryItems).mockRejectedValue(error);

    const { result } = renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 0,
        parameterFields: [],
        environment: null,
      })
    );

    await waitFor(() => {
      expect(result.current.environmentsCache).toEqual(cachedItems);
      expect(result.current.inventoryWarnings.environments).toBe(true);
    });
  });

  it('starts with empty inventory data and no warnings', () => {
    const { result } = renderHook(() =>
      useTargetInventory({
        open: false,
        currentStep: 0,
        parameterFields: [],
        environment: null,
      })
    );

    expect(result.current.inventoryData).toEqual({});
    expect(result.current.inventoryWarnings).toEqual({});
    expect(result.current.loadingInventory).toBe(false);
  });

  it('does not expose pattern resolution (moved to usePatternResolver)', () => {
    const { result } = renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 0,
        parameterFields: [],
        environment: null,
      })
    );

    // Verify no pattern-related properties exist (Story 20.4: extracted)
    const returnValue = result.current;
    expect(returnValue).not.toHaveProperty('resolvedPatternTargets');
    expect(returnValue).not.toHaveProperty('patternResolving');
    expect(returnValue).not.toHaveProperty('resolvePattern');
  });
});
