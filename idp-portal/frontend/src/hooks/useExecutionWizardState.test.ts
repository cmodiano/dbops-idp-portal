/**
 * Tests for useExecutionWizardState hook (Story 39.7 — coverage).
 */
import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { renderHook, act, cleanup } from '@testing-library/react';
import React from 'react';
import { App } from 'antd';
import { useExecutionWizardState } from './useExecutionWizardState';
import type { CatalogActionDetail } from '../services/catalog_service';

vi.mock('./usePatternResolver', () => ({
  usePatternResolver: () => ({ resolvedTargets: [], isResolving: false }),
}));
vi.mock('./useSchedulingValidation', () => ({
  useSchedulingValidation: () => ({
    validateSchedule: vi.fn(), validateCronDebounced: vi.fn(), handleCronPresetChange: vi.fn(),
  }),
}));
const mockScheduling = {
  schedulingType: 'immediate',
  scheduledAt: null, cronExpression: '', cronIsValid: false,
  dailyHour: 9, dailyMinute: 0,
  weeklyDayOfWeek: 1, weeklyHour: 9, weeklyMinute: 0,
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
  useTargetInventory: () => ({
    environmentsCache: {}, inventoryData: [], inventoryWarnings: [], loadingInventory: false,
  }),
}));
vi.mock('./useWorkflowStepActions', () => ({
  useWorkflowStepActions: () => ({
    workflowStepActions: {}, loadingWorkflowStepActions: false, workflowStepActionsError: null,
  }),
}));
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(App, null, children);

const mockAction: CatalogActionDetail = {
  id: 1, name: 'Deploy App', engine: 'AAP', platform: 'AAP', status: 'published',
  created_at: '2025-01-01T00:00:00Z', item_type: 'action', workflow_steps: null,
  requires_target: true, allowed_environments: ['DEV', 'PROD'],
  default_impact_level: null, impact_rules: null,
} as unknown as CatalogActionDetail;

const mockWorkflowAction: CatalogActionDetail = {
  ...mockAction, id: 2, item_type: 'workflow',
  workflow_steps: [
    { order: 2, name: 'Step 2', referenced_action_id: 20 },
    { order: 1, name: 'Step 1', referenced_action_id: 10 },
  ],
} as unknown as CatalogActionDetail;

const onCancel = vi.fn();
const onSuccess = vi.fn();

// One shared hook instance for all basic state tests to reduce memory pressure
describe('useExecutionWizardState', () => {
  let result: ReturnType<typeof renderHook<ReturnType<typeof useExecutionWizardState>, unknown>>['result'];
  let unmount: () => void;

  beforeAll(() => {
    const rendered = renderHook(
      () => useExecutionWizardState({
        open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'], onCancel, onSuccess,
      }),
      { wrapper },
    );
    result = rendered.result;
    unmount = rendered.unmount;
  });

  afterAll(() => { unmount(); cleanup(); });

  it('initial state: step=0, list mode, empty params, form and ctxValue defined', () => {
    expect(result.current.currentStep).toBe(0);
    expect(result.current.targetInputMode).toBe('list');
    expect(result.current.parameters).toEqual({});
    expect(result.current.pageMeEnabled).toBe(false);
    expect(result.current.selectedEnvironment).toBeNull();
    expect(result.current.form).toBeDefined();
    expect(result.current.wizardCtxValue).toBeDefined();
  });

  it('isWorkflow=false for action type; workflowSteps empty', () => {
    expect(result.current.isWorkflow).toBe(false);
    expect(result.current.workflowSteps).toEqual([]);
    expect(result.current.requiresTarget).toBe(true);
  });

  it('handlePrev stays at step 0; handleKeyDown Escape calls onCancel', () => {
    act(() => result.current.handlePrev());
    expect(result.current.currentStep).toBe(0);

    act(() => {
      result.current.handleKeyDown({
        key: 'Escape', shiftKey: false,
        target: document.createElement('input'), preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    expect(onCancel).toHaveBeenCalled();
  });

  it('execSubmit and schedulingValidation are returned', () => {
    expect(result.current.execSubmit).toBeDefined();
    expect(result.current.schedulingValidation).toBeDefined();
  });

  it('isWorkflowStep2Valid true when no invalid workflow steps', () => {
    // non-workflow, so steps are empty: valid
    expect(result.current.isWorkflowStep2Valid).toBe(true);
  });

  it('handleNext returns early when requiresTarget=true and no targets selected', async () => {
    // requiresTarget=true, effectiveTargetNames=[] → notification.warning + return
    await act(async () => {
      await result.current.handleNext();
    });
    // Step remains at 0 (no advance due to missing targets)
    expect(result.current.currentStep).toBe(0);
  });

  it('handleSubmit returns early when derivedEnvironment is null', async () => {
    // action is set but derivedEnvironment=null and no effectiveTargetNames → early return
    await act(async () => {
      await result.current.handleSubmit();
    });
    expect(result.current.currentStep).toBe(0); // no side-effects
  });

  it('handleSubmitScheduled returns early when derivedEnvironment is null', async () => {
    // action is set but derivedEnvironment=null → early return
    await act(async () => {
      await result.current.handleSubmitScheduled();
    });
    expect(result.current.currentStep).toBe(0); // no side-effects
  });

  it('handleKeyDown Enter on non-TEXTAREA calls handleNext', async () => {
    const div = document.createElement('div');
    await act(async () => {
      result.current.handleKeyDown({
        key: 'Enter', shiftKey: false,
        target: div, preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    // handleNext called but returns early (no targets) — step stays at 0
    expect(result.current.currentStep).toBe(0);
  });
});

describe('useExecutionWizardState — workflow action', () => {
  let result: ReturnType<typeof renderHook<ReturnType<typeof useExecutionWizardState>, unknown>>['result'];
  let unmount: () => void;

  beforeAll(() => {
    const rendered = renderHook(
      () => useExecutionWizardState({
        open: false, action: mockWorkflowAction,
        allowedEnvironments: ['DEV'], onCancel, onSuccess,
      }),
      { wrapper },
    );
    result = rendered.result;
    unmount = rendered.unmount;
  });

  afterAll(() => { unmount(); cleanup(); });

  it('isWorkflow=true, workflowSteps sorted, isWorkflowStep2Valid=true', () => {
    expect(result.current.isWorkflow).toBe(true);
    expect(result.current.workflowSteps.map((s) => s.order)).toEqual([1, 2]);
    expect(result.current.isWorkflowStep2Valid).toBe(true);
  });

  it('workflowStepActions and loadingWorkflowStepActions returned', () => {
    expect(result.current.workflowStepActions).toBeDefined();
    expect(result.current.loadingWorkflowStepActions).toBe(false);
    expect(result.current.workflowStepActionsError).toBeNull();
  });
});

describe('useExecutionWizardState — handleSubmit/Scheduled success', () => {
  let result: ReturnType<typeof renderHook<ReturnType<typeof useExecutionWizardState>, unknown>>['result'];
  let unmount: () => void;
  const onCancelLocal = vi.fn();
  const onSuccessLocal = vi.fn();

  beforeAll(async () => {
    const rendered = renderHook(
      () => useExecutionWizardState({
        open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'],
        onCancel: onCancelLocal, onSuccess: onSuccessLocal,
      }),
      { wrapper },
    );
    result = rendered.result;
    unmount = rendered.unmount;
    // Set environment so derivedEnvironment becomes 'DEV'
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
    });
  });

  afterAll(() => { unmount(); cleanup(); });

  it('handleSubmit calls submitImmediate when action and derivedEnvironment are set', async () => {
    await act(async () => {
      await result.current.handleSubmit();
    });
    expect(onSuccessLocal).toHaveBeenCalledWith(1);
  });

  it('handleSubmitScheduled calls submitScheduled and triggers onCancel+onSuccess', async () => {
    onCancelLocal.mockClear();
    onSuccessLocal.mockClear();
    await act(async () => {
      await result.current.handleSubmitScheduled();
    });
    expect(onCancelLocal).toHaveBeenCalled();
    expect(onSuccessLocal).toHaveBeenCalledWith(1);
  });
});

describe('useExecutionWizardState — setters', () => {
  it('state setters work correctly', async () => {
    const { result, unmount } = renderHook(
      () => useExecutionWizardState({
        open: false, action: null, allowedEnvironments: ['DEV'], onCancel, onSuccess,
      }),
      { wrapper },
    );

    await act(async () => {
      result.current.setTargetInputMode('pattern');
      result.current.setTargetPattern('srv-*');
    });
    expect(result.current.targetInputMode).toBe('pattern');
    expect(result.current.targetPattern).toBe('srv-*');

    await act(async () => {
      result.current.setManualTargetInput('h1, h2');
    });
    expect(result.current.manualTargetInput).toBe('h1, h2');

    unmount();
    cleanup();
  });

  it('requiresTarget=false, effectiveTargetNames in list mode', async () => {
    const a = { ...mockAction, requires_target: false } as CatalogActionDetail;
    const { result, unmount } = renderHook(
      () => useExecutionWizardState({
        open: false, action: a, allowedEnvironments: ['DEV'], onCancel, onSuccess,
      }),
      { wrapper },
    );

    expect(result.current.requiresTarget).toBe(false);

    await act(async () => {
      result.current.setSelectedTargets([{ name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null }]);
    });
    expect(result.current.effectiveTargetNames).toEqual(['srv1']);

    unmount();
    cleanup();
  });

  it('handleSubmitScheduled with daily scheduling covers recurringPattern notification branch', async () => {
    mockScheduling.schedulingType = 'daily';
    const onCancelDa = vi.fn();
    const { result, unmount } = renderHook(
      () => useExecutionWizardState({
        open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'],
        onCancel: onCancelDa, onSuccess: vi.fn(),
      }),
      { wrapper },
    );
    // Use setSelectedTargets to cover the targets-based derivedEnvironment branch (lines 197-198)
    // and the target_names truthy branch (line 406)
    await act(async () => {
      result.current.setSelectedTargets([{ name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null }]);
    });
    await act(async () => {
      await result.current.handleSubmitScheduled();
    });
    expect(onCancelDa).toHaveBeenCalled();
    unmount();
    cleanup();
    mockScheduling.schedulingType = 'immediate';
  });

  it('handleSubmitScheduled with cron scheduling covers cron recurringPattern branch', async () => {
    mockScheduling.schedulingType = 'cron';
    mockScheduling.cronExpression = '0 9 * * *';
    mockScheduling.cronIsValid = true;
    const onCancelCron = vi.fn();
    const { result, unmount } = renderHook(
      () => useExecutionWizardState({
        open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'],
        onCancel: onCancelCron, onSuccess: vi.fn(),
      }),
      { wrapper },
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
    });
    await act(async () => {
      await result.current.handleSubmitScheduled();
    });
    expect(onCancelCron).toHaveBeenCalled();
    unmount();
    cleanup();
    mockScheduling.schedulingType = 'immediate';
    mockScheduling.cronExpression = '';
    mockScheduling.cronIsValid = false;
  });
});
