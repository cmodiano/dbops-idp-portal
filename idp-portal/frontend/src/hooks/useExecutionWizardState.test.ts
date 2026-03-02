/**
 * Tests for useExecutionWizardState hook — Part 1 (Story 55-7).
 *
 * Covers: initial state, workflow action, keyboard navigation, handleNext, handleSubmit.
 * Uses vi.spyOn(App, 'useApp') to avoid antd portal memory leaks in JSDOM.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
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
  schedulingType: 'immediate' as string,
  scheduledAt: null as null | { isBefore: (d: unknown) => boolean; utc: () => { toISOString: () => string } },
  cronExpression: '', cronIsValid: false,
  dailyHour: 9, dailyMinute: 0,
  weeklyDayOfWeek: 1, weeklyHour: 9, weeklyMinute: 0,
};

const mockSetSubmitError = vi.fn();
const mockSetSchedulingError = vi.fn();
const mockResetScheduling = vi.fn();
const mockSubmitImmediate = vi.fn().mockResolvedValue(1);
const mockSubmitScheduled = vi.fn().mockResolvedValue(1);

vi.mock('./useExecutionSubmit', () => ({
  useExecutionSubmit: () => ({
    submitImmediate: mockSubmitImmediate,
    submitScheduled: mockSubmitScheduled,
    isSubmitting: false,
    submitError: null,
    setSubmitError: mockSetSubmitError,
    schedulingError: null,
    setSchedulingError: mockSetSchedulingError,
    resetScheduling: mockResetScheduling,
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

const mockNotification = { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() };
// No App wrapper needed — App.useApp is spied on directly
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(React.Fragment, null, children);

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

let useAppSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  useAppSpy = vi.spyOn(App, 'useApp').mockReturnValue({
    notification: mockNotification as never,
    message: {} as never,
    modal: {} as never,
  });
});
afterEach(() => {
  useAppSpy.mockRestore();
  cleanup();
  vi.clearAllMocks();
  mockScheduling.schedulingType = 'immediate';
  mockScheduling.scheduledAt = null;
});

function makeHook(overrides: Partial<Parameters<typeof useExecutionWizardState>[0]> = {}) {
  return renderHook(
    () => useExecutionWizardState({
      open: false, action: mockAction, allowedEnvironments: ['DEV', 'PROD'], onCancel, onSuccess, ...overrides,
    }),
    { wrapper },
  );
}

// ─── Initial state ───────────────────────────────────────────────────────────

describe('useExecutionWizardState — initial state', () => {
  it('step=0, list mode, empty params, form and ctxValue defined', () => {
    const { result, unmount } = makeHook();
    expect(result.current.currentStep).toBe(0);
    expect(result.current.targetInputMode).toBe('list');
    expect(result.current.parameters).toEqual({});
    expect(result.current.pageMeEnabled).toBe(false);
    expect(result.current.selectedEnvironment).toBeNull();
    expect(result.current.form).toBeDefined();
    expect(result.current.wizardCtxValue).toBeDefined();
    unmount();
  });

  it('isWorkflow=false; workflowSteps=[]; requiresTarget=true', () => {
    const { result, unmount } = makeHook();
    expect(result.current.isWorkflow).toBe(false);
    expect(result.current.workflowSteps).toEqual([]);
    expect(result.current.requiresTarget).toBe(true);
    unmount();
  });

  it('execSubmit and schedulingValidation are defined', () => {
    const { result, unmount } = makeHook();
    expect(result.current.execSubmit).toBeDefined();
    expect(result.current.schedulingValidation).toBeDefined();
    unmount();
  });

  it('isWorkflowStep2Valid=true for non-workflow', () => {
    const { result, unmount } = makeHook();
    expect(result.current.isWorkflowStep2Valid).toBe(true);
    unmount();
  });
});

// ─── Workflow action ─────────────────────────────────────────────────────────

describe('useExecutionWizardState — workflow action', () => {
  it('isWorkflow=true, workflowSteps sorted ascending', () => {
    const { result, unmount } = makeHook({ action: mockWorkflowAction, allowedEnvironments: ['DEV'] });
    expect(result.current.isWorkflow).toBe(true);
    expect(result.current.workflowSteps.map((s) => s.order)).toEqual([1, 2]);
    unmount();
  });

  it('workflowStepActions defined, loadingWorkflowStepActions=false', () => {
    const { result, unmount } = makeHook({ action: mockWorkflowAction, allowedEnvironments: ['DEV'] });
    expect(result.current.workflowStepActions).toBeDefined();
    expect(result.current.loadingWorkflowStepActions).toBe(false);
    unmount();
  });
});

// ─── Keyboard / navigation ───────────────────────────────────────────────────

describe('useExecutionWizardState — keyboard and navigation', () => {
  it('handlePrev stays at step 0', () => {
    const { result, unmount } = makeHook();
    act(() => result.current.handlePrev());
    expect(result.current.currentStep).toBe(0);
    unmount();
  });

  it('handleKeyDown Escape calls onCancel', () => {
    const localOnCancel = vi.fn();
    const { result, unmount } = makeHook({ onCancel: localOnCancel });
    act(() => result.current.handleKeyDown({
      key: 'Escape', shiftKey: false,
      target: document.createElement('input'), preventDefault: vi.fn(),
    } as unknown as React.KeyboardEvent));
    expect(localOnCancel).toHaveBeenCalled();
    unmount();
  });

  it('handleKeyDown Enter on DIV calls handleNext (stays at 0 — no targets)', async () => {
    const { result, unmount } = makeHook();
    await act(async () => result.current.handleKeyDown({
      key: 'Enter', shiftKey: false,
      target: document.createElement('div'), preventDefault: vi.fn(),
    } as unknown as React.KeyboardEvent));
    expect(result.current.currentStep).toBe(0);
    unmount();
  });

  it('handleKeyDown Enter on TEXTAREA does nothing', async () => {
    const { result, unmount } = makeHook();
    await act(async () => result.current.handleKeyDown({
      key: 'Enter', shiftKey: false,
      target: document.createElement('textarea'), preventDefault: vi.fn(),
    } as unknown as React.KeyboardEvent));
    expect(result.current.currentStep).toBe(0);
    unmount();
  });
});

// ─── handleNext ──────────────────────────────────────────────────────────────

describe('useExecutionWizardState — handleNext', () => {
  it('returns early when requiresTarget=true and no targets', async () => {
    const { result, unmount } = makeHook();
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(0);
    unmount();
  });

  it('returns early when requiresTarget=false and no environment', async () => {
    const a = { ...mockAction, requires_target: false } as CatalogActionDetail;
    const { result, unmount } = makeHook({ action: a, allowedEnvironments: ['DEV', 'PROD'] });
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(0);
    unmount();
  });

  it('advances to step 1 when manual targets are present', async () => {
    const { result, unmount } = makeHook();
    await act(async () => {
      result.current.setTargetInputMode('manual');
      result.current.setManualTargetInput('h1');
    });
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(1);
    unmount();
  });

  it('stays at step 0 in pattern mode with empty resolved targets', async () => {
    const { result, unmount } = makeHook();
    await act(async () => {
      result.current.setTargetInputMode('pattern');
      result.current.setTargetPattern('srv-*');
    });
    await act(async () => { await result.current.handleNext(); });
    expect(result.current.currentStep).toBe(0);
    unmount();
  });
});

// ─── handleSubmit ─────────────────────────────────────────────────────────────

describe('useExecutionWizardState — handleSubmit', () => {
  it('returns early when no environment and no targets', async () => {
    const { result, unmount } = makeHook();
    await act(async () => { await result.current.handleSubmit(); });
    expect(result.current.currentStep).toBe(0);
    unmount();
  });

  it('calls submitImmediate and triggers onSuccess when environment is set', async () => {
    const localOnSuccess = vi.fn();
    mockSubmitImmediate.mockResolvedValueOnce(42);
    const { result, unmount } = makeHook({ onSuccess: localOnSuccess });
    await act(async () => { result.current.setSelectedEnvironment('DEV' as never); });
    await act(async () => { await result.current.handleSubmit(); });
    expect(localOnSuccess).toHaveBeenCalledWith(42);
    unmount();
  });

  it('calls submitImmediate when targets are set (derives env from targets)', async () => {
    const localOnSuccess = vi.fn();
    mockSubmitImmediate.mockResolvedValueOnce(7);
    const { result, unmount } = makeHook({ onSuccess: localOnSuccess });
    await act(async () => {
      result.current.setSelectedTargets([{ name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null }]);
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(localOnSuccess).toHaveBeenCalledWith(7);
    unmount();
  });

  it('sets submitError when action is not published', async () => {
    const unpublished = { ...mockAction, status: 'draft' } as CatalogActionDetail;
    const { result, unmount } = makeHook({ action: unpublished });
    await act(async () => { result.current.setSelectedEnvironment('DEV' as never); });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSetSubmitError).toHaveBeenCalled();
    unmount();
  });

  it('double-submit guard: second concurrent call is blocked', async () => {
    const { result, unmount } = makeHook();
    await act(async () => { result.current.setSelectedEnvironment('DEV' as never); });
    await act(async () => {
      await Promise.all([result.current.handleSubmit(), result.current.handleSubmit()]);
    });
    expect(result.current.currentStep).toBe(0);
    unmount();
  });
});
