/**
 * Tests for useExecutionWizardState hook — Part 3 (Story 55-7).
 * Covers: immediate scheduling success (onCancel+onSuccess), targets-based env derivation,
 * and open=true effect with unpublished action.
 * NOTE: daily/weekly/cron/unpublished-scheduling scenarios are covered in extra6.test.ts.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { renderHook, act, cleanup } from '@testing-library/react';
import { App } from 'antd';
import { useExecutionWizardState } from './useExecutionWizardState';
import type { CatalogActionDetail } from '../services/catalog_service';

vi.mock('./usePatternResolver', () => ({ usePatternResolver: () => ({ resolvedTargets: [], isResolving: false }) }));
vi.mock('./useSchedulingValidation', () => ({
  useSchedulingValidation: () => ({ validateSchedule: vi.fn(), validateCronDebounced: vi.fn(), handleCronPresetChange: vi.fn() }),
}));

const mockScheduling = {
  schedulingType: 'immediate' as string,
  scheduledAt: null as null | { isBefore: (d: unknown) => boolean; utc: () => { toISOString: () => string } },
  cronExpression: '', cronIsValid: false,
  dailyHour: 9, dailyMinute: 0, weeklyDayOfWeek: 1, weeklyHour: 9, weeklyMinute: 0,
};

const mockSubmitScheduled = vi.fn().mockResolvedValue(1);

vi.mock('./useExecutionSubmit', () => ({
  useExecutionSubmit: () => ({
    submitImmediate: vi.fn().mockResolvedValue(1), submitScheduled: mockSubmitScheduled,
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
const mockAction: CatalogActionDetail = {
  id: 1, name: 'Deploy App', engine: 'AAP', platform: 'AAP', status: 'published',
  created_at: '2025-01-01T00:00:00Z', item_type: 'action', workflow_steps: null,
  requires_target: true, allowed_environments: ['DEV', 'PROD'],
  default_impact_level: null, impact_rules: null,
} as unknown as CatalogActionDetail;

const onSuccess = vi.fn();

let useAppSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  useAppSpy = vi.spyOn(App, 'useApp').mockReturnValue({ notification: mockNotification as never, message: {} as never, modal: {} as never });
});
afterEach(() => {
  useAppSpy.mockRestore(); cleanup(); vi.clearAllMocks();
  mockScheduling.schedulingType = 'immediate'; mockScheduling.scheduledAt = null;
  mockScheduling.cronExpression = ''; mockScheduling.cronIsValid = false;
});

describe('useExecutionWizardState — Part 3', () => {
  it('immediate scheduled: triggers onCancel+onSuccess', async () => {
    const localOnCancel = vi.fn();
    const localOnSuccess = vi.fn();
    mockSubmitScheduled.mockResolvedValueOnce(5);
    const { result, unmount } = renderHook(() => useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV'], onCancel: localOnCancel, onSuccess: localOnSuccess }));
    await act(async () => { result.current.setSelectedEnvironment('DEV' as never); });
    await act(async () => { await result.current.handleSubmitScheduled(); });
    expect(localOnCancel).toHaveBeenCalled();
    expect(localOnSuccess).toHaveBeenCalledWith(5, { isScheduled: true });
    unmount();
  });

  it('targets-based: handleSubmitScheduled derives env from selectedTargets', async () => {
    const localOnCancel = vi.fn();
    mockSubmitScheduled.mockResolvedValueOnce(20);
    const { result, unmount } = renderHook(() => useExecutionWizardState({ open: false, action: mockAction, allowedEnvironments: ['DEV'], onCancel: localOnCancel, onSuccess }));
    await act(async () => {
      result.current.setSelectedTargets([{ name: 'srv1', environment: 'DEV', target_type: 'server', metadata: null }]);
    });
    await act(async () => { await result.current.handleSubmitScheduled(); });
    expect(localOnCancel).toHaveBeenCalled();
    unmount();
  });

  it('open=true with unpublished action: calls onCancel (covers useEffect 1 open branch)', async () => {
    const unpublished = { ...mockAction, status: 'draft' } as CatalogActionDetail;
    const localOnCancel = vi.fn();
    const { unmount } = renderHook(() => useExecutionWizardState({ open: true, action: unpublished, allowedEnvironments: ['DEV'], onCancel: localOnCancel, onSuccess }));
    await act(async () => { /* wait for effect */ });
    expect(localOnCancel).toHaveBeenCalled();
    unmount();
  });
});
