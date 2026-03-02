/**
 * Tests for useExecutionWizardState hook — Part 4 (Story 55-7).
 * Covers: evaluateImpact, buildWorkflowStepParams, getInvalidWorkflowStepOrders,
 * effectiveTargetNames (pattern/empty), derivedEnvironment (pattern), hasMixedEnvironments,
 * handleNext at step 1, handleSubmitScheduled (missing env guard).
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { renderHook, act, cleanup } from '@testing-library/react';
import { App } from 'antd';
import { useExecutionWizardState } from './useExecutionWizardState';
import type { CatalogActionDetail } from '../services/catalog_service';

// Default mock: resolvedTargets = []
let mockResolvedTargets: Array<{ name: string; environment: string; target_type: string; metadata: null }> = [];

vi.mock('./usePatternResolver', () => ({
  usePatternResolver: () => ({ resolvedTargets: mockResolvedTargets, isResolving: false }),
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
const mockSubmitImmediate = vi.fn().mockResolvedValue(1);
const mockSubmitScheduled = vi.fn().mockResolvedValue(1);

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
  mockResolvedTargets = [];
});
afterEach(() => {
  useAppSpy.mockRestore(); cleanup(); vi.clearAllMocks();
  mockScheduling.schedulingType = 'immediate'; mockScheduling.scheduledAt = null;
  mockScheduling.cronExpression = ''; mockScheduling.cronIsValid = false;
  mockResolvedTargets = [];
});

describe('useExecutionWizardState — Part 4', () => {
  it('hasMixedEnvironments=true when 2 targets have different environments (line 209)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedTargets([
        { name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null },
        { name: 'srv2', environment: 'PROD', target_type: 'server', metadata: null },
      ]);
    });
    // Advance to step 1: hasMixedEnvironments=true triggers warning but still advances
    await act(async () => { await result.current.handleNext(); });
    expect(mockNotification.warning).toHaveBeenCalled();
    // Step advances despite mixed envs warning
    expect(result.current.currentStep).toBe(1);
    unmount();
  });

  it('handleSubmitScheduled with no env and no targets calls notification.warning (lines 370-371)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    // Do NOT set environment or targets — derivedEnvironment will be null
    await act(async () => { await result.current.handleSubmitScheduled(); });
    expect(mockNotification.warning).toHaveBeenCalled();
    unmount();
  });

  it('evaluateImpact body runs when action has impact_rules and derivedEnvironment set (lines 43-47)', async () => {
    const actionWithImpact = {
      ...mockAction,
      impact_rules: { DEV: { level: 'high' as const }, PROD: { level: 'critical' as const } },
      default_impact_level: 'low' as const,
    } as unknown as CatalogActionDetail;
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: actionWithImpact, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedTargets([{ name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null }]);
    });
    // currentImpact should be 'high' (matching DEV rule)
    expect(result.current.wizardCtxValue.currentImpact).toBe('high');
    unmount();
  });

  it('evaluateImpact returns defaultImpact when no rule matches env (lines 43-47)', async () => {
    const actionWithImpact = {
      ...mockAction,
      impact_rules: { PROD: { level: 'critical' as const } },
      default_impact_level: 'low' as const,
    } as unknown as CatalogActionDetail;
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: actionWithImpact, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedTargets([{ name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null }]);
    });
    // DEV not in impact_rules → returns defaultImpact='low'
    expect(result.current.wizardCtxValue.currentImpact).toBe('low');
    unmount();
  });

  it('buildWorkflowStepParams runs for workflow action with parameters set in handleSubmit (lines 69-80)', async () => {
    const localOnSuccess = vi.fn();
    mockSubmitImmediate.mockResolvedValueOnce(99);
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess: localOnSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({ workflow_step_parameters: { '1': { parameters: { key: 'val' } } } });
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({ workflow_step_parameters: { '1': { parameters: { key: 'val' } } } })
    );
    unmount();
  });

  it('handleNext at step 1: calls form.validateFields, advances to step 2 (lines 319-320)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    // First advance to step 1 using manual targets
    await act(async () => {
      result.current.setTargetInputMode('manual');
      result.current.setManualTargetInput('srv1');
    });
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(1);
    // Now call handleNext again from step 1 — validateFields resolves with {} (no fields registered)
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(2);
    unmount();
  });

  it('effectiveTargetNames in pattern mode returns resolvedPatternTargets names (line 188)', async () => {
    mockResolvedTargets = [{ name: 'ptn-srv1', environment: 'DEV', target_type: 'server', metadata: null }];
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setTargetInputMode('pattern');
      result.current.setTargetPattern('ptn-*');
    });
    expect(result.current.effectiveTargetNames).toEqual(['ptn-srv1']);
    unmount();
  });

  it('derivedEnvironment in pattern mode returns first resolvedPatternTarget env (line 199)', async () => {
    mockResolvedTargets = [{ name: 'ptn-srv1', environment: 'PROD', target_type: 'server', metadata: null }];
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setTargetInputMode('pattern');
      result.current.setTargetPattern('ptn-*');
    });
    expect(result.current.wizardCtxValue.derivedEnvironment).toBe('PROD');
    unmount();
  });
});
