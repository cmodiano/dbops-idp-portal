/**
 * Tests for useCancelExecution hook — Story 26.6 AC9
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { App } from 'antd';
import type { ReactNode } from 'react';

import { useCancelExecution } from '../useCancelExecution';
import { cancelScheduledExecution } from '../../services/scheduled_execution_service';
import { ApiError } from '../../services/api_client';
import type { ScheduledExecutionListItem } from '../../types/api';

vi.mock('../../services/scheduled_execution_service', () => ({
  cancelScheduledExecution: vi.fn(),
}));

const mockNotification = { success: vi.fn(), error: vi.fn() };
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    App: {
      ...actual.App,
      useApp: () => ({ notification: mockNotification, message: { success: vi.fn(), error: vi.fn() }, modal: {} }),
    },
  };
});

function makeExec(overrides: Partial<ScheduledExecutionListItem> = {}): ScheduledExecutionListItem {
  return {
    scheduled_execution_id: 42,
    action_id: 10,
    action_name: 'Deploy DB',
    user_id: 1,
    user_name: 'admin',
    environment: 'dev',
    scheduled_at: '2026-03-15T10:00:00Z',
    status: 'pending',
    created_at: '2026-03-10T08:00:00Z',
    parameters: null,
    ...overrides,
  };
}

describe('useCancelExecution', () => {
  const onSuccess = vi.fn();
  const onClosePopover = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cancelScheduledExecution).mockResolvedValue({} as never);
  });

  function renderCancelHook() {
    return renderHook(() => useCancelExecution(onSuccess, onClosePopover));
  }

  it('should initialize with default values', () => {
    const { result } = renderCancelHook();
    expect(result.current.executionToCancel).toBeNull();
    expect(result.current.cancelModalVisible).toBe(false);
    expect(result.current.cancelLoading).toBe(false);
  });

  it('openCancelModal should set execution and show modal', () => {
    const { result } = renderCancelHook();
    const exec = makeExec();

    act(() => {
      result.current.openCancelModal(exec);
    });

    expect(result.current.executionToCancel).toBe(exec);
    expect(result.current.cancelModalVisible).toBe(true);
  });

  it('closeCancelModal should reset state', () => {
    const { result } = renderCancelHook();

    act(() => {
      result.current.openCancelModal(makeExec());
    });
    act(() => {
      result.current.closeCancelModal();
    });

    expect(result.current.executionToCancel).toBeNull();
    expect(result.current.cancelModalVisible).toBe(false);
  });

  it('confirmCancel should call API and onSuccess on success', async () => {
    const { result } = renderCancelHook();
    const exec = makeExec();

    act(() => {
      result.current.openCancelModal(exec);
    });

    await act(async () => {
      await result.current.confirmCancel();
    });

    expect(cancelScheduledExecution).toHaveBeenCalledWith(42);
    expect(mockNotification.success).toHaveBeenCalled();
    expect(onClosePopover).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
    expect(result.current.cancelModalVisible).toBe(false);
  });

  it('confirmCancel should handle 403 error', async () => {
    vi.mocked(cancelScheduledExecution).mockRejectedValue(new ApiError('Permission denied', 403));
    const { result } = renderCancelHook();

    act(() => {
      result.current.openCancelModal(makeExec());
    });

    await act(async () => {
      await result.current.confirmCancel();
    });

    expect(mockNotification.error).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Permission refusée' })
    );
  });

  it('confirmCancel should handle 400 error', async () => {
    vi.mocked(cancelScheduledExecution).mockRejectedValue(new ApiError('Invalid status', 400));
    const { result } = renderCancelHook();

    act(() => {
      result.current.openCancelModal(makeExec());
    });

    await act(async () => {
      await result.current.confirmCancel();
    });

    expect(mockNotification.error).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Cette exécution ne peut plus être annulée' })
    );
  });

  it('confirmCancel should handle generic error', async () => {
    vi.mocked(cancelScheduledExecution).mockRejectedValue(new Error('Network error'));
    const { result } = renderCancelHook();

    act(() => {
      result.current.openCancelModal(makeExec());
    });

    await act(async () => {
      await result.current.confirmCancel();
    });

    expect(mockNotification.error).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Network error' })
    );
  });

  it('confirmCancel should do nothing if no execution selected', async () => {
    const { result } = renderCancelHook();

    await act(async () => {
      await result.current.confirmCancel();
    });

    expect(cancelScheduledExecution).not.toHaveBeenCalled();
  });
});
