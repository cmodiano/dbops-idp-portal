/**
 * Tests for useWorkflowStepActions hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useWorkflowStepActions } from './useWorkflowStepActions';

vi.mock('../services/catalog_service', () => ({
  fetchCatalogActionById: vi.fn(),
}));

import { fetchCatalogActionById } from '../services/catalog_service';
const mockFetch = vi.mocked(fetchCatalogActionById);

const mockActionDetail = { id: 10, name: 'Deploy', engine: 'AAP', status: 'published' };

describe('useWorkflowStepActions — coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({ data: mockActionDetail, can_execute: true, allowed_environments: ['DEV'] } as never);
  });

  it('initial state: empty map, loading=false', () => {
    const { result } = renderHook(() =>
      useWorkflowStepActions({ open: false, isWorkflow: false, currentStep: 0, workflowSteps: [] })
    );
    expect(result.current.workflowStepActions).toEqual({});
    expect(result.current.loadingWorkflowStepActions).toBe(false);
    expect(result.current.workflowStepActionsError).toBeNull();
  });

  it('does not fetch when open=false', () => {
    renderHook(() =>
      useWorkflowStepActions({ open: false, isWorkflow: true, currentStep: 1, workflowSteps: [{ order: 1, name: 'Step', referenced_action_id: 10 }] })
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('fetches actions when open=true, isWorkflow=true, currentStep=1', async () => {
    const { result } = renderHook(() =>
      useWorkflowStepActions({
        open: true, isWorkflow: true, currentStep: 1,
        workflowSteps: [{ order: 1, name: 'Step', referenced_action_id: 10 }],
      })
    );
    await waitFor(() => expect(result.current.loadingWorkflowStepActions).toBe(false));
    expect(result.current.workflowStepActions[10]).toBeDefined();
  });

  it('sets error when fetch fails', async () => {
    mockFetch.mockRejectedValue(new Error('Not found'));
    const { result } = renderHook(() =>
      useWorkflowStepActions({
        open: true, isWorkflow: true, currentStep: 1,
        workflowSteps: [{ order: 1, name: 'Step', referenced_action_id: 10 }],
      })
    );
    await waitFor(() => expect(result.current.loadingWorkflowStepActions).toBe(false));
    expect(result.current.workflowStepActionsError).toBe('Not found');
  });
});
