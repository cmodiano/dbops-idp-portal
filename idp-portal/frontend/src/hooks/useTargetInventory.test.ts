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

describe('useTargetInventory - Story 23.6', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchInventoryItems).mockImplementation(
      (type: string, _environment?: string, _options?: { server_names?: string[] }) => {
        if (type === 'environments') {
          return Promise.resolve([
            { id: 'dev', name: 'Developpement', environment: null },
            { id: 'staging', name: 'Staging', environment: null },
            { id: 'prod', name: 'Production', environment: null },
          ]);
        }
        // instances, servers, databases
        return Promise.resolve([
          { id: 'item-1', name: 'Item 1', environment: 'dev' },
          { id: 'item-2', name: 'Item 2', environment: 'dev' },
        ]);
      }
    );
  });

  it('passe selectedServerNames à fetchInventoryItems pour instances', async () => {
    renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 1,
        parameterFields: [{ inventorySource: 'instances' }],
        environment: 'dev',
        selectedServerNames: ['srv01', 'srv02'],
      })
    );

    await waitFor(() => {
      expect(fetchInventoryItems).toHaveBeenCalledWith(
        'instances',
        'dev',
        { server_names: ['srv01', 'srv02'] }
      );
    });
  });

  it('recharge inventaire quand selectedServerNames change', async () => {
    const { rerender } = renderHook(
      (props) =>
        useTargetInventory({
          open: true,
          currentStep: 1,
          parameterFields: [{ inventorySource: 'instances' }],
          environment: 'dev',
          selectedServerNames: props.selectedServerNames,
        }),
      { initialProps: { selectedServerNames: ['srv01'] } }
    );

    // Wait for the first inventory fetch (environments + instances)
    await waitFor(() => {
      expect(fetchInventoryItems).toHaveBeenCalledWith(
        'instances',
        'dev',
        { server_names: ['srv01'] }
      );
    });

    // Rerender with different server names
    rerender({ selectedServerNames: ['srv02', 'srv03'] });

    await waitFor(() => {
      expect(fetchInventoryItems).toHaveBeenCalledWith(
        'instances',
        'dev',
        { server_names: ['srv02', 'srv03'] }
      );
    });

    // Verify instances was called at least twice (initial + after server names change)
    const instancesCalls = vi.mocked(fetchInventoryItems).mock.calls.filter(
      (call) => call[0] === 'instances'
    );
    expect(instancesCalls.length).toBeGreaterThanOrEqual(2);
    // The last call should have the updated server names
    expect(instancesCalls[instancesCalls.length - 1]).toEqual([
      'instances',
      'dev',
      { server_names: ['srv02', 'srv03'] },
    ]);
  });

  it('ne passe pas server_names pour inventorySource servers', async () => {
    renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 1,
        parameterFields: [{ inventorySource: 'servers' }],
        environment: 'dev',
        selectedServerNames: ['srv01'],
      })
    );

    await waitFor(() => {
      expect(fetchInventoryItems).toHaveBeenCalledWith('servers', 'dev', undefined);
    });
  });

  it('selectedServerNames vide ne passe pas server_names', async () => {
    renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 1,
        parameterFields: [{ inventorySource: 'instances' }],
        environment: 'dev',
        selectedServerNames: [],
      })
    );

    await waitFor(() => {
      expect(fetchInventoryItems).toHaveBeenCalledWith(
        'instances',
        'dev',
        { server_names: [] }
      );
    });
  });

  it('pas de rechargement si selectedServerNames inchangé', async () => {
    // Use a separate spy to track calls precisely
    const spy = vi.fn();
    vi.mocked(fetchInventoryItems).mockImplementation(
      (type: string, _environment?: string, _options?: { server_names?: string[] }) => {
        spy(type, _environment, _options);
        if (type === 'environments') {
          return Promise.resolve([
            { id: 'dev', name: 'Developpement', environment: null },
          ]);
        }
        return Promise.resolve([
          { id: 'item-1', name: 'Item 1', environment: 'dev' },
        ]);
      }
    );

    const { rerender } = renderHook(
      (props) =>
        useTargetInventory({
          open: true,
          currentStep: 1,
          parameterFields: [{ inventorySource: 'instances' }],
          environment: 'dev',
          selectedServerNames: props.selectedServerNames,
        }),
      { initialProps: { selectedServerNames: ['srv01'] } }
    );

    // Wait for the initial inventory fetch to complete
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith(
        'instances',
        'dev',
        { server_names: ['srv01'] }
      );
    });

    // Record the number of instances calls after initial load stabilizes
    const instancesCallsBefore = spy.mock.calls.filter(
      (call) => call[0] === 'instances'
    ).length;

    // Rerender with the same selectedServerNames and same environment
    rerender({ selectedServerNames: ['srv01'] });

    // Wait a tick for any potential re-fetch to settle
    await new Promise((r) => setTimeout(r, 100));

    const instancesCallsAfter = spy.mock.calls.filter(
      (call) => call[0] === 'instances'
    ).length;

    // Should not have fetched instances again since selectedServerNames is unchanged
    expect(instancesCallsAfter).toBe(instancesCallsBefore);
  });
});
