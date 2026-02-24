/**
 * Tests for useExecutionView hook (Story 39.7 — coverage).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useExecutionView } from './useExecutionView';
import * as executionService from '../services/execution_service';
import * as catalogService from '../services/catalog_service';
import type { ExecutionResponse } from '../types/api';

vi.mock('../services/execution_service');
vi.mock('../services/catalog_service');
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

const mockExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy App',
  user_id: 5,
  environment: 'prod',
  parameters: null,
  status: 'COMPLETED',
  servicenow_change_id: null,
  started_at: '2025-01-01T10:00:00Z',
  completed_at: '2025-01-01T10:05:00Z',
  created_at: '2025-01-01T09:59:00Z',
  item_type: 'action',
};

const mockWorkflowExecution: ExecutionResponse = {
  ...mockExecution,
  id: 2,
  item_type: 'workflow',
  action_id: 20,
};

describe('useExecutionView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts with loading state when executionId provided', () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    expect(result.current.loading).toBe(true);
  });

  it('returns null execution when executionId is null', async () => {
    const { result } = renderHook(() => useExecutionView(null));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.execution).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('fetches and returns execution data', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.execution).toEqual(mockExecution);
    expect(result.current.error).toBeNull();
  });

  it('sets error on fetch failure', async () => {
    vi.mocked(executionService.getExecution).mockRejectedValue(new Error('Not found'));
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('Not found');
  });

  it('loads workflow details for workflow execution', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockWorkflowExecution);
    vi.mocked(catalogService.fetchCatalogActionById).mockResolvedValue({
      data: { id: 20, name: 'Workflow', item_type: 'workflow', workflow_steps: [] } as never,
      can_execute: true,
      allowed_environments: [],
    });
    const { result } = renderHook(() => useExecutionView(2));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(catalogService.fetchCatalogActionById).toHaveBeenCalledWith(20);
    expect(result.current.actionDetail).not.toBeNull();
  });

  it('handles workflow detail fetch failure gracefully', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockWorkflowExecution);
    vi.mocked(catalogService.fetchCatalogActionById).mockRejectedValue(new Error('Detail not found'));
    const { result } = renderHook(() => useExecutionView(2));
    await waitFor(() => expect(result.current.loading).toBe(false));
    // Should not set error — just log warning
    expect(result.current.execution).toEqual(mockWorkflowExecution);
    expect(result.current.actionDetail).toBeNull();
  });

  it('does not load workflow details for action type', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(catalogService.fetchCatalogActionById).not.toHaveBeenCalled();
    expect(result.current.actionDetail).toBeNull();
  });

  it('refresh refetches execution data', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const updatedExecution = { ...mockExecution, status: 'RUNNING' as const };
    vi.mocked(executionService.getExecution).mockResolvedValue(updatedExecution);

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.execution?.status).toBe('RUNNING');
  });

  it('refresh does nothing when executionId is null', async () => {
    const { result } = renderHook(() => useExecutionView(null));
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.refresh();
    });
    expect(executionService.getExecution).not.toHaveBeenCalled();
  });

  it('handleExecutionUpdate updates execution status', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const updated: ExecutionResponse = { ...mockExecution, status: 'RUNNING' };
    act(() => {
      result.current.handleExecutionUpdate(updated);
    });

    expect(result.current.execution?.status).toBe('RUNNING');
  });

  it('handleExecutionUpdate ignores update when no status change', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const sameStatus: ExecutionResponse = { ...mockExecution };
    act(() => {
      result.current.handleExecutionUpdate(sameStatus);
    });

    // Should remain the same object (no update)
    expect(result.current.execution?.status).toBe('COMPLETED');
  });

  it('refresh sets error on failure', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    const { result } = renderHook(() => useExecutionView(1));
    await waitFor(() => expect(result.current.loading).toBe(false));

    vi.mocked(executionService.getExecution).mockRejectedValue(new Error('Refresh failed'));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.error?.message).toBe('Refresh failed');
  });
});
