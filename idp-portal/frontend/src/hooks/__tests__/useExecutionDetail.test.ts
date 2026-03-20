/**
 * Tests for useExecutionDetail hook (Story 26.4 - AC2).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { createElement } from 'react';
import { MemoryRouter } from 'react-router';
import type { ExecutionResponse, ExecutionStepResponse } from '../../types/api';
import type { CatalogActionDetail } from '../../services/catalog_service';

// --- Mocks ---

vi.mock('../../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(),
}));

vi.mock('../../services/catalog_service', () => ({
  fetchCatalogActionById: vi.fn(),
}));

import { getExecution, getExecutionSteps } from '../../services/execution_service';
import { fetchCatalogActionById } from '../../services/catalog_service';
import { useExecutionDetail } from '../useExecutionDetail';

const mockedGetExecution = vi.mocked(getExecution);
const mockedGetExecutionSteps = vi.mocked(getExecutionSteps);
const mockedFetchCatalogActionById = vi.mocked(fetchCatalogActionById);

// --- Helpers ---

function makeExecution(overrides: Partial<ExecutionResponse> = {}): ExecutionResponse {
  return {
    id: 42,
    action_id: 10,
    action_name: 'Test Action',
    user_id: 1,
    environment: 'DEV',
    parameters: null,
    status: 'COMPLETED',
    servicenow_change_id: null,
    started_at: '2025-01-01T00:00:00Z',
    completed_at: '2025-01-01T00:01:00Z',
    created_at: '2025-01-01T00:00:00Z',
    item_type: 'action',
    ...overrides,
  };
}

function makeStep(overrides: Partial<ExecutionStepResponse> = {}): ExecutionStepResponse {
  return {
    id: 1,
    execution_id: 42,
    step_order: 1,
    step_name: 'Step 1',
    step_type: 'platform',
    status: 'COMPLETED',
    started_at: '2025-01-01T00:00:00Z',
    completed_at: '2025-01-01T00:00:30Z',
    output: null,
    platform_job_id: null,
    error_message: null,
    ...overrides,
  };
}

/**
 * Wrapper providing MemoryRouter with optional initial entries.
 */
function createWrapper(initialEntries: string[] = ['/executions']) {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(MemoryRouter, { initialEntries }, children);
}

// --- Tests ---

describe('useExecutionDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns correct initial state', () => {
    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    expect(result.current.drawerOpen).toBe(false);
    expect(result.current.selectedExecution).toBeNull();
    expect(result.current.selectedSteps).toEqual([]);
    expect(result.current.selectedActionDetail).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.openExecution).toBe('function');
    expect(typeof result.current.closeDrawer).toBe('function');
  });

  it('openExecution loads execution + steps for a standard action', async () => {
    const execution = makeExecution({ item_type: 'action' });
    const steps = [makeStep()];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    expect(mockedGetExecution).toHaveBeenCalledWith(42);
    expect(mockedGetExecutionSteps).toHaveBeenCalledWith(42);
    expect(result.current.drawerOpen).toBe(true);
    expect(result.current.selectedExecution).toEqual(execution);
    expect(result.current.selectedSteps).toEqual(steps);
    expect(result.current.selectedActionDetail).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('openExecution loads action detail for workflow executions', async () => {
    const execution = makeExecution({ item_type: 'workflow', action_id: 10 });
    const steps = [makeStep()];
    const actionDetail = { id: 10, name: 'Workflow Action' } as unknown as CatalogActionDetail;

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);
    mockedFetchCatalogActionById.mockResolvedValue({
      data: actionDetail,
      can_execute: true,
      allowed_environments: ['DEV'],
    });

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    expect(mockedFetchCatalogActionById).toHaveBeenCalledWith(10);
    expect(result.current.selectedActionDetail).toEqual(actionDetail);
    expect(result.current.drawerOpen).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it('handles errors gracefully when loading fails', async () => {
    const execution = makeExecution();
    mockedGetExecution.mockRejectedValue(new Error('Network error'));
    mockedGetExecutionSteps.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    expect(result.current.drawerOpen).toBe(true);
    expect(result.current.error).toBe('Network error');
    expect(result.current.loading).toBe(false);
    expect(result.current.selectedExecution).toBeNull();
    expect(result.current.selectedSteps).toEqual([]);
  });

  it('handles non-Error throws with fallback message', async () => {
    const execution = makeExecution();
    mockedGetExecution.mockRejectedValue('string error');
    mockedGetExecutionSteps.mockRejectedValue('string error');

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    expect(result.current.error).toBe('Erreur de chargement du détail');
  });

  it('closeDrawer resets all state', async () => {
    const execution = makeExecution();
    const steps = [makeStep()];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    // Open first
    await act(async () => {
      await result.current.openExecution(execution);
    });
    expect(result.current.drawerOpen).toBe(true);

    // Close
    act(() => {
      result.current.closeDrawer();
    });

    expect(result.current.drawerOpen).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('opens drawer automatically when ?open=79 search param is present', async () => {
    const execution = makeExecution({ id: 79 });
    const steps = [makeStep({ execution_id: 79 })];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(['/executions?open=79']),
    });

    await waitFor(() => {
      expect(mockedGetExecution).toHaveBeenCalledWith(79);
    });

    await waitFor(() => {
      expect(result.current.drawerOpen).toBe(true);
      expect(result.current.selectedExecution).toEqual(execution);
    });
  });

  it('closeDrawer removes open search param when present', async () => {
    const execution = makeExecution({ id: 79 });
    const steps = [makeStep({ execution_id: 79 })];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(['/executions?open=79']),
    });

    await waitFor(() => {
      expect(result.current.drawerOpen).toBe(true);
    });

    act(() => {
      result.current.closeDrawer();
    });

    expect(result.current.drawerOpen).toBe(false);
  });

  it('silently continues when fetchCatalogActionById fails for workflow', async () => {
    const execution = makeExecution({ item_type: 'workflow', action_id: 10 });
    const steps = [makeStep()];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);
    mockedFetchCatalogActionById.mockRejectedValue(new Error('Not found'));

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    // Should still succeed, just without action detail
    expect(result.current.drawerOpen).toBe(true);
    expect(result.current.selectedExecution).toEqual(execution);
    expect(result.current.selectedActionDetail).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  // --- BUG-FE-02 tests ---

  it('sets actionDetailUnavailable=true when fetchCatalogActionById fails', async () => {
    const execution = makeExecution({ item_type: 'workflow', action_id: 10 });
    const steps = [makeStep()];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);
    mockedFetchCatalogActionById.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    expect(result.current.actionDetailUnavailable).toBe(true);
  });

  it('still returns selectedExecution and selectedSteps when action detail fetch fails', async () => {
    const execution = makeExecution({ item_type: 'workflow', action_id: 10 });
    const steps = [makeStep(), makeStep({ id: 2, step_order: 2 })];

    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);
    mockedFetchCatalogActionById.mockRejectedValue(new Error('Forbidden'));

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });

    expect(result.current.selectedExecution).toEqual(execution);
    expect(result.current.selectedSteps).toEqual(steps);
    expect(result.current.actionDetailUnavailable).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('actionDetailUnavailable is false on initial state and resets on new load', async () => {
    const execution = makeExecution({ item_type: 'workflow', action_id: 10 });
    const steps = [makeStep()];
    const actionDetail = { id: 10, name: 'Workflow Action' } as unknown as CatalogActionDetail;

    const { result } = renderHook(() => useExecutionDetail(), {
      wrapper: createWrapper(),
    });

    // Initial state: false
    expect(result.current.actionDetailUnavailable).toBe(false);

    // First call: fails
    mockedGetExecution.mockResolvedValue(execution);
    mockedGetExecutionSteps.mockResolvedValue(steps);
    mockedFetchCatalogActionById.mockRejectedValue(new Error('err'));

    await act(async () => {
      await result.current.openExecution(execution);
    });
    expect(result.current.actionDetailUnavailable).toBe(true);

    // Second call: succeeds — should reset to false
    mockedFetchCatalogActionById.mockResolvedValue({
      data: actionDetail,
      can_execute: true,
      allowed_environments: ['DEV'],
    });

    await act(async () => {
      await result.current.openExecution(execution);
    });
    expect(result.current.actionDetailUnavailable).toBe(false);
  });
});
