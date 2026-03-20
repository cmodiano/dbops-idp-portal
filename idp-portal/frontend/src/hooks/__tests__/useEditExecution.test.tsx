/**
 * Tests for useEditExecution hook — Story 26.6 AC9
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

import { useEditExecution } from '../useEditExecution';
import { updateScheduledExecution } from '../../services/scheduled_execution_service';
import { ApiError } from '../../services/api_client';
import type { ScheduledExecutionListItem } from '../../types/api';

vi.mock('../../services/scheduled_execution_service', () => ({
  updateScheduledExecution: vi.fn(),
}));

const mockValidateFields = vi.fn();
const mockSetFieldsValue = vi.fn();
const mockSetFields = vi.fn();
const mockResetFields = vi.fn();
const mockForm = {
  validateFields: mockValidateFields,
  setFieldsValue: mockSetFieldsValue,
  setFields: mockSetFields,
  resetFields: mockResetFields,
  getFieldValue: vi.fn(),
  getFieldsValue: vi.fn(),
  getFieldError: vi.fn(),
  getFieldsError: vi.fn(),
  isFieldsTouched: vi.fn(),
  isFieldTouched: vi.fn(),
  isFieldValidating: vi.fn(),
  scrollToField: vi.fn(),
  submit: vi.fn(),
  getFieldInstance: vi.fn(),
};

const mockNotification = { success: vi.fn(), error: vi.fn() };
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    App: {
      ...actual.App,
      useApp: () => ({ notification: mockNotification, message: { success: vi.fn(), error: vi.fn() }, modal: {} }),
    },
    Form: {
      ...actual.Form,
      useForm: () => [mockForm],
    },
  };
});

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, profile: 'DBOPS' } }),
}));

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
    parameters: { _targets: ['server1'], key: 'value' },
    ...overrides,
  };
}

describe('useEditExecution', () => {
  const onSuccess = vi.fn();
  const onClosePopover = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(updateScheduledExecution).mockResolvedValue({} as never);
    mockValidateFields.mockResolvedValue({
      scheduled_at: { utc: () => ({ format: () => '2026-03-15T10:00:00Z' }) },
      target_names: ['server1'],
    });
  });

  function renderEditHook() {
    return renderHook(() => useEditExecution(onSuccess, onClosePopover));
  }

  it('should initialize with default values', () => {
    const { result } = renderEditHook();
    expect(result.current.executionToEdit).toBeNull();
    expect(result.current.editModalVisible).toBe(false);
    expect(result.current.editLoading).toBe(false);
    expect(result.current.editLoading).toBe(false);
  });

  it('openEditModal should set execution, show modal and initialize form', () => {
    const { result } = renderEditHook();
    const exec = makeExec();

    act(() => {
      result.current.openEditModal(exec);
    });

    expect(result.current.executionToEdit).toBe(exec);
    expect(result.current.editModalVisible).toBe(true);
    expect(mockSetFieldsValue).toHaveBeenCalled();
  });

  it('openEditModal should populate form with recurring pattern config', () => {
    const { result } = renderEditHook();
    const exec = makeExec({
      recurring_pattern: {
        pattern_type: 'weekly',
        pattern_config: { hour: 14, minute: 30, day_of_week: 3 },
        is_active: true,
        next_execution_date: '2026-03-17T14:30:00Z',
      },
    });

    act(() => {
      result.current.openEditModal(exec);
    });

    // Story 11.11: only the next_execution_date is editable for recurring executions
    expect(mockSetFieldsValue).toHaveBeenCalledWith(
      expect.objectContaining({
        next_execution_date: expect.anything(),
      })
    );
  });

  it('closeEditModal should reset state', () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.openEditModal(makeExec());
    });
    act(() => {
      result.current.closeEditModal();
    });

    expect(result.current.executionToEdit).toBeNull();
    expect(result.current.editModalVisible).toBe(false);
  });

  it('should show modal when opening edit', () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.openEditModal(makeExec());
    });

    expect(result.current.editModalVisible).toBe(true);
  });

  it('submitEdit should call API and onSuccess on success', async () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.openEditModal(makeExec());
    });

    await act(async () => {
      await result.current.submitEdit();
    });

    expect(updateScheduledExecution).toHaveBeenCalledWith(42, expect.any(Object));
    expect(mockNotification.success).toHaveBeenCalled();
    expect(onClosePopover).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it('submitEdit should handle 403 error', async () => {
    vi.mocked(updateScheduledExecution).mockRejectedValue(new ApiError('Forbidden', 403));
    const { result } = renderEditHook();

    act(() => {
      result.current.openEditModal(makeExec());
    });

    // Don't await the promise directly — let it settle and check notification
    act(() => {
      result.current.submitEdit();
    });

    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Permission refusée' })
      );
    });
  });

  it('submitEdit should handle 404 error', async () => {
    vi.mocked(updateScheduledExecution).mockRejectedValue(new ApiError('Not found', 404));
    const { result } = renderEditHook();

    act(() => {
      result.current.openEditModal(makeExec());
    });

    act(() => {
      result.current.submitEdit();
    });

    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Exécution planifiée introuvable' })
      );
    });
  });

  it('submitEdit should handle 400 error with field details', async () => {
    vi.mocked(updateScheduledExecution).mockRejectedValue(
      new ApiError('Validation failed', 400, {
        error: { code: 'VALIDATION', message: 'Invalid', details: { scheduled_at: 'Date invalide' } },
      })
    );
    const { result } = renderEditHook();

    act(() => {
      result.current.openEditModal(makeExec());
    });

    act(() => {
      result.current.submitEdit();
    });

    // Hook shows a notification for 400 errors (no per-field setFields)
    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Erreur de validation' })
      );
    });
  });

  it('submitEdit should do nothing if no execution selected', async () => {
    const { result } = renderEditHook();

    await act(async () => {
      await result.current.submitEdit();
    });

    expect(updateScheduledExecution).not.toHaveBeenCalled();
  });

  it('submitEdit sets scheduled_at when no target_names', async () => {
    mockValidateFields.mockResolvedValue({
      scheduled_at: { utc: () => ({ format: () => '2026-03-15T10:00:00Z' }) },
      target_names: null,
      environment: 'PROD',
    });
    const { result } = renderEditHook();
    act(() => { result.current.openEditModal(makeExec()); });
    await act(async () => { await result.current.submitEdit(); });
    // Story 11.11: only scheduled_at is sent for one-time executions
    expect(updateScheduledExecution).toHaveBeenCalledWith(
      42, expect.objectContaining({ scheduled_at: '2026-03-15T10:00:00Z' }),
    );
  });

  it('submitEdit sends next_execution_date for cron recurring execution', async () => {
    mockValidateFields.mockResolvedValue({
      next_execution_date: { utc: () => ({ format: () => '2026-03-20T09:00:00Z' }) },
    });
    const { result } = renderEditHook();
    act(() => {
      result.current.openEditModal(makeExec({
        recurring_pattern: { pattern_type: 'cron', pattern_config: { cron_expression: '0 9 * * *' }, is_active: true, next_execution_date: null },
      }));
    });
    await act(async () => { await result.current.submitEdit(); });
    expect(updateScheduledExecution).toHaveBeenCalledWith(
      42, expect.objectContaining({ next_execution_date: '2026-03-20T09:00:00Z' }),
    );
  });

  it('submitEdit sends next_execution_date for daily recurring execution', async () => {
    mockValidateFields.mockResolvedValue({
      next_execution_date: { utc: () => ({ format: () => '2026-03-21T09:30:00Z' }) },
    });
    const { result } = renderEditHook();
    act(() => {
      result.current.openEditModal(makeExec({
        recurring_pattern: { pattern_type: 'daily', pattern_config: { hour: 9, minute: 0 }, is_active: true, next_execution_date: null },
      }));
    });
    await act(async () => { await result.current.submitEdit(); });
    expect(updateScheduledExecution).toHaveBeenCalledWith(
      42, expect.objectContaining({ next_execution_date: '2026-03-21T09:30:00Z' }),
    );
  });

  it('submitEdit sends next_execution_date for weekly recurring execution', async () => {
    mockValidateFields.mockResolvedValue({
      next_execution_date: { utc: () => ({ format: () => '2026-03-25T10:00:00Z' }) },
    });
    const { result } = renderEditHook();
    act(() => {
      result.current.openEditModal(makeExec({
        recurring_pattern: { pattern_type: 'weekly', pattern_config: { hour: 10, minute: 0, day_of_week: 2 }, is_active: true, next_execution_date: null },
      }));
    });
    await act(async () => { await result.current.submitEdit(); });
    expect(updateScheduledExecution).toHaveBeenCalledWith(
      42, expect.objectContaining({ next_execution_date: '2026-03-25T10:00:00Z' }),
    );
  });

  it('submitEdit handles generic error', async () => {
    vi.mocked(updateScheduledExecution).mockRejectedValue(new Error('Server error'));
    const { result } = renderEditHook();
    act(() => { result.current.openEditModal(makeExec()); });
    act(() => { result.current.submitEdit(); });
    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Erreur' }),
      );
    });
  });
});
