/**
 * Tests for useExecutionWizardState hook — Part 7 (Story 55-7).
 * Covers handleSubmitScheduled branches: one-time/cron validation errors,
 * unpublished action guard, and daily/weekly/cron recurring patterns.
 * All tests use open=false to avoid antd Form worker hangs.
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
  useSchedulingValidation: () => ({
    validateSchedule: vi.fn(),
    validateCronDebounced: vi.fn(),
    handleCronPresetChange: vi.fn(),
  }),
}));

const mockScheduling = {
  schedulingType: 'immediate' as string,
  scheduledAt: null as null | { isBefore: (d: unknown) => boolean; format: (f: string) => string; utc: () => { toISOString: () => string } },
  cronExpression: '',
  cronIsValid: false,
  dailyHour: 9,
  dailyMinute: 30,
  weeklyDayOfWeek: 2,
  weeklyHour: 10,
  weeklyMinute: 15,
};

const mockSetSchedulingError = vi.fn();
const mockSubmitScheduled = vi.fn().mockResolvedValue(1);

vi.mock('./useExecutionSubmit', () => ({
  useExecutionSubmit: () => ({
    submitImmediate: vi.fn().mockResolvedValue(1),
    submitScheduled: mockSubmitScheduled,
    isSubmitting: false,
    submitError: null,
    setSubmitError: vi.fn(),
    schedulingError: null,
    setSchedulingError: mockSetSchedulingError,
    resetScheduling: vi.fn(),
    get scheduling() { return mockScheduling; },
  }),
}));
vi.mock('./useTargetInventory', () => ({
  useTargetInventory: () => ({
    environmentsCache: {},
    inventoryData: [],
    inventoryWarnings: [],
    loadingInventory: false,
  }),
}));
vi.mock('./useWorkflowStepActions', () => ({
  useWorkflowStepActions: () => ({
    workflowStepActions: {},
    loadingWorkflowStepActions: false,
    workflowStepActionsError: null,
  }),
}));
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

const mockNotification = {
  error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn(),
};

const publishedAction: CatalogActionDetail = {
  id: 1,
  name: 'Published Action',
  engine: 'AAP',
  platform: 'AAP',
  status: 'published',
  created_at: '2025-01-01T00:00:00Z',
  item_type: 'action',
  requires_target: false,
  allowed_environments: ['DEV', 'PROD'],
  default_impact_level: null,
  impact_rules: null,
  parameters_schema: null,
} as unknown as CatalogActionDetail;

const draftAction: CatalogActionDetail = {
  ...publishedAction,
  status: 'draft',
} as unknown as CatalogActionDetail;

const onCancel = vi.fn();
const onSuccess = vi.fn();

let useAppSpy: ReturnType<typeof vi.spyOn>;

beforeEach(async () => {
  vi.clearAllMocks();
  useAppSpy = vi.spyOn(App, 'useApp').mockReturnValue({
    notification: mockNotification as never,
    message: {} as never,
    modal: {} as never,
  });
  mockScheduling.schedulingType = 'immediate';
  mockScheduling.scheduledAt = null;
  mockScheduling.cronExpression = '';
  mockScheduling.cronIsValid = false;
  mockSubmitScheduled.mockResolvedValue(1);
});

afterEach(() => {
  useAppSpy?.mockRestore();
  cleanup();
});

/** Helper: renders hook with publishedAction and sets selectedEnvironment to 'DEV' */
async function renderWithEnv(action: CatalogActionDetail = publishedAction) {
  const { result, unmount } = renderHook(() =>
    useExecutionWizardState({
      open: false,
      action,
      allowedEnvironments: ['DEV', 'PROD'],
      onCancel,
      onSuccess,
    })
  );
  await act(async () => {
    result.current.setSelectedEnvironment('DEV' as never);
  });
  return { result, unmount };
}

describe('useExecutionWizardState — Part 7 (handleSubmitScheduled branches)', () => {
  it('one-time without scheduledAt: calls setSchedulingError (covers line 375)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'one-time';
    mockScheduling.scheduledAt = null;

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSetSchedulingError).toHaveBeenCalledWith('Veuillez sélectionner une date et heure');
    unmount();
  });

  it('one-time with past scheduledAt: calls setSchedulingError (covers line 376)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'one-time';
    // isBefore(dayjs()) → true means the date is in the past
    mockScheduling.scheduledAt = {
      isBefore: () => true,
      format: () => '01/01/2025 à 09:00',
      utc: () => ({ toISOString: () => '2025-01-01T09:00:00.000Z' }),
    };

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSetSchedulingError).toHaveBeenCalledWith('La date planifiée doit être dans le futur');
    unmount();
  });

  it('cron with empty cronExpression: calls setSchedulingError (covers lines 377-379)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'cron';
    mockScheduling.cronExpression = '';
    mockScheduling.cronIsValid = false;

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSetSchedulingError).toHaveBeenCalledWith('Veuillez saisir une expression cron valide');
    unmount();
  });

  it('unpublished action: calls setSchedulingError and notification.error (covers lines 381-385)', async () => {
    const { result, unmount } = await renderWithEnv(draftAction);
    // Use 'immediate' so we skip the scheduling validation
    mockScheduling.schedulingType = 'immediate';

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSetSchedulingError).toHaveBeenCalledWith(
      expect.stringContaining("n'est plus publiée")
    );
    expect(mockNotification.error).toHaveBeenCalled();
    unmount();
  });

  it('daily scheduling: sends recurringPattern and shows daily success notification (covers lines 390-392, 412-413)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'daily';
    mockScheduling.dailyHour = 9;
    mockScheduling.dailyMinute = 30;

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSubmitScheduled).toHaveBeenCalledWith(
      expect.objectContaining({
        recurring_pattern: expect.objectContaining({ pattern_type: 'daily' }),
      })
    );
    expect(mockNotification.success).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exécution récurrente créée' })
    );
    unmount();
  });

  it('weekly scheduling: sends recurringPattern and shows weekly success notification (covers lines 393-395, 414)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'weekly';
    mockScheduling.weeklyDayOfWeek = 2; // mardis
    mockScheduling.weeklyHour = 10;
    mockScheduling.weeklyMinute = 15;

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSubmitScheduled).toHaveBeenCalledWith(
      expect.objectContaining({
        recurring_pattern: expect.objectContaining({ pattern_type: 'weekly' }),
      })
    );
    expect(mockNotification.success).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exécution récurrente créée' })
    );
    unmount();
  });

  it('cron valid: sends recurringPattern and shows cron success notification (covers lines 396-397, 415)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'cron';
    mockScheduling.cronExpression = '0 9 * * 1';
    mockScheduling.cronIsValid = true;

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSubmitScheduled).toHaveBeenCalledWith(
      expect.objectContaining({
        recurring_pattern: expect.objectContaining({
          pattern_type: 'cron',
          pattern_config: expect.objectContaining({ cron_expression: '0 9 * * 1' }),
        }),
      })
    );
    expect(mockNotification.success).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exécution récurrente créée' })
    );
    unmount();
  });

  it('selectedTargets.length > 0: passes target_names in submitScheduled (covers line 406)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'daily';
    await act(async () => {
      result.current.setSelectedTargets([
        { name: 'srv-dev-01', environment: 'DEV', target_type: 'server', metadata: null },
      ]);
    });

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSubmitScheduled).toHaveBeenCalledWith(
      expect.objectContaining({
        target_names: ['srv-dev-01'],
      })
    );
    unmount();
  });

  it('one-time with future scheduledAt: submits and shows planifiée notification (covers line 418)', async () => {
    const { result, unmount } = await renderWithEnv();
    mockScheduling.schedulingType = 'one-time';
    mockScheduling.scheduledAt = {
      isBefore: () => false,
      format: () => '15/06/2027 à 14:00',
      utc: () => ({ toISOString: () => '2027-06-15T12:00:00.000Z' }),
    };

    await act(async () => { await result.current.handleSubmitScheduled(); });

    expect(mockSubmitScheduled).toHaveBeenCalledWith(
      expect.objectContaining({
        scheduled_at: '2027-06-15T12:00:00.000Z',
      })
    );
    expect(mockNotification.success).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exécution planifiée' })
    );
    unmount();
  });
});
