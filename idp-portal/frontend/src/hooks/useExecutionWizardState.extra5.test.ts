/**
 * Tests for useExecutionWizardState hook — Part 6 (Story 55-7).
 * Covers getInvalidWorkflowStepOrders branches: empty errors, non-matching names (lines 54, 56, 61).
 * Note: open=true tests omitted — form.resetFields() in effects causes worker hangs.
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

vi.mock('./useExecutionSubmit', () => ({
  useExecutionSubmit: () => ({
    submitImmediate: vi.fn().mockResolvedValue(1),
    submitScheduled: vi.fn().mockResolvedValue(1),
    isSubmitting: false, submitError: null, setSubmitError: vi.fn(),
    schedulingError: null, setSchedulingError: vi.fn(), resetScheduling: vi.fn(),
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

const onCancel = vi.fn();
const onSuccess = vi.fn();

let useAppSpy: ReturnType<typeof vi.spyOn>;
let useFormSpy: ReturnType<typeof vi.spyOn> | null = null;

beforeEach(() => {
  useAppSpy = vi.spyOn(App, 'useApp').mockReturnValue({ notification: mockNotification as never, message: {} as never, modal: {} as never });
});
afterEach(() => {
  useAppSpy.mockRestore();
  useFormSpy?.mockRestore();
  useFormSpy = null;
  cleanup();
  vi.clearAllMocks();
  mockScheduling.schedulingType = 'immediate';
  mockScheduling.scheduledAt = null;
});

describe('useExecutionWizardState — Part 6', () => {
  it('getInvalidWorkflowStepOrders: covers empty-errors branch (line 54), non-matching-name branch (line 56), and return (line 61)', async () => {
    const { Form: AntdForm } = await import('antd');
    useFormSpy = vi.spyOn(AntdForm, 'useForm').mockReturnValue([{
      validateFields: vi.fn().mockRejectedValueOnce(new Error('validation error')).mockResolvedValue({}),
      getFieldsError: vi.fn().mockReturnValue([
        // Line 54: errors is empty → hit the `continue` branch
        { name: ['workflow_step_parameters', '1'], errors: [] },
        // Line 56: name[0] !== 'workflow_step_parameters' → hit the `continue` branch
        { name: ['other_field', '1'], errors: ['Required'] },
        // Valid: counted as invalid order 2
        { name: ['workflow_step_parameters', '2', 'param'], errors: ['Required'] },
        // Second valid match: order 3 — forces sort comparator (a - b) to execute (line 61)
        { name: ['workflow_step_parameters', '3', 'key'], errors: ['Required'] },
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
    } as never]);

    const workflowAction: CatalogActionDetail = {
      id: 2, name: 'Workflow', engine: 'AAP', platform: 'AAP', status: 'published',
      created_at: '2025-01-01T00:00:00Z', item_type: 'workflow',
      workflow_steps: [
        { order: 1, name: 'S1', referenced_action_id: 10 },
        { order: 2, name: 'S2', referenced_action_id: 20 },
      ],
      requires_target: true, allowed_environments: ['DEV'],
      default_impact_level: null, impact_rules: null,
    } as unknown as CatalogActionDetail;

    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: workflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    // Advance to step 1
    await act(async () => {
      result.current.setTargetInputMode('manual');
      result.current.setManualTargetInput('srv1');
    });
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(1);

    // Call handleNext at step 1 → validateFields rejects → getInvalidWorkflowStepOrders runs
    await act(async () => { await result.current.handleNext(); });

    expect(result.current.currentStep).toBe(1);
    // Only order 2 should be invalid (order 1 had empty errors, 'other_field' skipped)
    // Orders 2 and 3 should be invalid (sorted ascending); order 1 had empty errors, 'other_field' skipped
    expect(result.current.workflowInvalidStepOrders).toEqual([2, 3]);
    unmount();
  });
});
