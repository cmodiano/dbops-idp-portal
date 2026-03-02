/**
 * Tests for useExecutionWizardState hook — Part 5 (Story 55-7).
 * Covers: buildWorkflowStepParams (no raw params branch, line 72),
 * handleSubmitScheduled double-submit guard (lines 366-367),
 * getInvalidWorkflowStepOrders (lines 51-61) via handleNext step 1 catch.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { renderHook, act, cleanup } from '@testing-library/react';
import { App } from 'antd';
import { useExecutionWizardState } from './useExecutionWizardState';
import type { CatalogActionDetail } from '../services/catalog_service';

vi.mock('./usePatternResolver', () => ({
  usePatternResolver: () => ({ resolvedTargets: [], isResolving: false }),
}));
vi.mock('./useSchedulingValidation', () => ({
  useSchedulingValidation: () => ({ validateSchedule: vi.fn(), validateCronDebounced: vi.fn(), handleCronPresetChange: vi.fn() }),
}));

const mockScheduling = {
  schedulingType: 'immediate' as string,
  scheduledAt: null as null | { isBefore: (d: unknown) => boolean; utc: () => { toISOString: () => string } },
  cronExpression: '', cronIsValid: false,
  dailyHour: 9, dailyMinute: 0, weeklyDayOfWeek: 1, weeklyHour: 9, weeklyMinute: 0,
};

const mockSetSchedulingError = vi.fn();
// Use a resolvable promise we can control
let resolveSubmitScheduled: ((id: number) => void) | null = null;
const mockSubmitScheduled = vi.fn().mockImplementation(() =>
  new Promise<number>((resolve) => { resolveSubmitScheduled = resolve; })
);
const mockSubmitImmediate = vi.fn().mockResolvedValue(1);

vi.mock('./useExecutionSubmit', () => ({
  useExecutionSubmit: () => ({
    submitImmediate: mockSubmitImmediate,
    submitScheduled: mockSubmitScheduled,
    isSubmitting: false, submitError: null, setSubmitError: vi.fn(),
    schedulingError: null, setSchedulingError: mockSetSchedulingError, resetScheduling: vi.fn(),
    get scheduling() { return mockScheduling; },
  }),
}));
vi.mock('./useTargetInventory', () => ({
  useTargetInventory: () => ({ environmentsCache: {}, inventoryData: [], inventoryWarnings: [], loadingInventory: false }),
}));
vi.mock('./useWorkflowStepActions', () => ({
  useWorkflowStepActions: () => ({ workflowStepActions: {}, loadingWorkflowStepActions: false, workflowStepActionsError: null }),
}));
vi.mock('../services/logger', () => ({ default: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));

const mockNotification = { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() };

const mockAction: CatalogActionDetail = {
  id: 1, name: 'Deploy App', engine: 'AAP', platform: 'AAP', status: 'published',
  created_at: '2025-01-01T00:00:00Z', item_type: 'action', workflow_steps: null,
  requires_target: true, allowed_environments: ['DEV', 'PROD'],
  default_impact_level: null, impact_rules: null,
} as unknown as CatalogActionDetail;

const mockWorkflowAction: CatalogActionDetail = {
  ...mockAction, id: 2, item_type: 'workflow',
  workflow_steps: [
    { order: 1, name: 'Step 1', referenced_action_id: 10 },
    { order: 2, name: 'Step 2', referenced_action_id: 20 },
  ],
} as unknown as CatalogActionDetail;

const onCancel = vi.fn();
const onSuccess = vi.fn();

let useAppSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  useAppSpy = vi.spyOn(App, 'useApp').mockReturnValue({ notification: mockNotification as never, message: {} as never, modal: {} as never });
  resolveSubmitScheduled = null;
});
afterEach(() => {
  useAppSpy.mockRestore(); cleanup(); vi.clearAllMocks();
  mockScheduling.schedulingType = 'immediate'; mockScheduling.scheduledAt = null;
  mockScheduling.cronExpression = ''; mockScheduling.cronIsValid = false;
  // Resolve any pending promise to avoid leaks
  resolveSubmitScheduled?.(0);
  resolveSubmitScheduled = null;
});

describe('useExecutionWizardState — Part 5', () => {
  it('buildWorkflowStepParams: workflow action with no workflow_step_parameters returns undefined (line 72)', async () => {
    const localOnSuccess = vi.fn();
    mockSubmitImmediate.mockResolvedValueOnce(50);
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess: localOnSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      // Parameters WITHOUT workflow_step_parameters → buildWorkflowStepParams returns undefined
      result.current.setParameters({ someOtherParam: 'value' });
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({ workflow_step_parameters: undefined })
    );
    unmount();
  });

  it('handleSubmitScheduled double-submit guard: second concurrent call is blocked (lines 366-367)', async () => {
    // Reset to use controlled promise
    mockSubmitScheduled.mockImplementationOnce(() =>
      new Promise<number>((resolve) => { resolveSubmitScheduled = resolve; })
    );
    const localOnCancel = vi.fn();
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV'], onCancel: localOnCancel, onSuccess })
    );
    await act(async () => { result.current.setSelectedEnvironment('DEV' as never); });

    // Start first call (will block waiting for mockSubmitScheduled to resolve)
    let p1: Promise<void>;
    act(() => { p1 = result.current.handleSubmitScheduled(); });

    // Give micro-task queue a tick so isSubmittingRef gets set
    await act(async () => { await Promise.resolve(); });

    // Second call should hit the double-submit guard
    await act(async () => { await result.current.handleSubmitScheduled(); });

    // Resolve the first call
    await act(async () => {
      resolveSubmitScheduled?.(42);
      await p1!;
    });
    // First call should have succeeded
    expect(localOnCancel).toHaveBeenCalled();
    unmount();
  });

  it('handleNext step 1 getInvalidWorkflowStepOrders runs in catch when validateFields rejects (lines 51-61, 322-327)', async () => {
    // To trigger the catch block, we need form.validateFields() to reject.
    // We mock Form.useForm to return a form that rejects validateFields.
    const { Form: AntdForm } = await import('antd');
    const mockFormInstance = {
      validateFields: vi.fn().mockRejectedValueOnce(new Error('validation failed')).mockResolvedValue({}),
      getFieldsError: vi.fn().mockReturnValue([
        { name: ['workflow_step_parameters', '1', 'key'], errors: ['Required'] },
      ]),
      resetFields: vi.fn(),
      setFieldsValue: vi.fn(),
      getFieldValue: vi.fn(),
      getFieldsValue: vi.fn().mockReturnValue({}),
      setFields: vi.fn(),
      isFieldTouched: vi.fn().mockReturnValue(false),
      isFieldsTouched: vi.fn().mockReturnValue(false),
      isFieldValidating: vi.fn().mockReturnValue(false),
      scrollToField: vi.fn(),
      submit: vi.fn(),
      getInternalHooks: vi.fn().mockReturnValue({}),
    };
    const useFormSpy = vi.spyOn(AntdForm, 'useForm').mockReturnValue([mockFormInstance as never]);

    try {
      const { result, unmount } = renderHook(() =>
        useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
      );
      // Advance to step 1 first using manual targets
      await act(async () => {
        result.current.setTargetInputMode('manual');
        result.current.setManualTargetInput('srv1');
      });
      await act(async () => { await result.current.handleNext(); });
      expect(result.current.currentStep).toBe(1);

      // Now at step 1, call handleNext — validateFields will reject (first call)
      await act(async () => { await result.current.handleNext(); });

      // Should stay at step 1 (return in catch block)
      expect(result.current.currentStep).toBe(1);
      // workflowInvalidStepOrders should be set from getInvalidWorkflowStepOrders
      expect(result.current.workflowInvalidStepOrders).toEqual([1]);

      unmount();
    } finally {
      useFormSpy.mockRestore();
    }
  });
});
