/**
 * Tests for useExecutionWizardState hook — Part 8 (Story 62-2).
 * Covers buildWorkflowStepParams with workflowSteps:
 *   3.1 Cas nominal : shared_parameters injectés dans toutes les étapes
 *   3.2 Cas override : paramètre spécifique écrase le commun, autres étapes gardent la valeur commune
 *   3.3 Cas sans paramètres communs : comportement identique à l'ancien (AC4)
 *   3.4 Cas shared_parameters vides {} : équivalent à aucun paramètre commun (AC5)
 *   3.5 Cas workflowSteps vide [] : fallback sur comportement existant (rétrocompatibilité)
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

const mockSubmitImmediate = vi.fn().mockResolvedValue(1);

vi.mock('./useExecutionSubmit', () => ({
  useExecutionSubmit: () => ({
    submitImmediate: mockSubmitImmediate,
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

/** Workflow action avec 2 étapes */
const mockWorkflowAction: CatalogActionDetail = {
  id: 2, name: 'Deploy Workflow', engine: 'AAP', platform: 'AAP', status: 'published',
  created_at: '2025-01-01T00:00:00Z', item_type: 'workflow',
  workflow_steps: [
    { order: 1, name: 'Step 1', referenced_action_id: 10 },
    { order: 2, name: 'Step 2', referenced_action_id: 20 },
  ],
  requires_target: false, allowed_environments: ['DEV', 'PROD'],
  default_impact_level: null, impact_rules: null,
} as unknown as CatalogActionDetail;

/** Workflow action avec workflow_steps vide (pour fallback) */
const mockWorkflowActionNoSteps: CatalogActionDetail = {
  ...mockWorkflowAction,
  workflow_steps: [],
} as unknown as CatalogActionDetail;

const onCancel = vi.fn();
const onSuccess = vi.fn();

let useAppSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  useAppSpy = vi.spyOn(App, 'useApp').mockReturnValue({ notification: mockNotification as never, message: {} as never, modal: {} as never });
});
afterEach(() => {
  useAppSpy.mockRestore(); cleanup(); vi.clearAllMocks();
  mockScheduling.schedulingType = 'immediate'; mockScheduling.scheduledAt = null;
});

describe('useExecutionWizardState — Part 8 — buildWorkflowStepParams avec workflowSteps (Story 62-2)', () => {
  it('3.1 nominal : shared_parameters injectés dans les deux étapes (AC1)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({
        shared_parameters: { server_id: 'srv01' },
        workflow_step_parameters: {
          '1': { parameters: {} },
          '2': { parameters: {} },
        },
      });
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_step_parameters: {
          '1': { parameters: { server_id: 'srv01' } },
          '2': { parameters: { server_id: 'srv01' } },
        },
      })
    );
    unmount();
  });

  it('3.2 override : paramètre step-specific écrase le commun pour étape 1, étape 2 garde la valeur commune (AC2)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({
        shared_parameters: { server_id: 'srv01' },
        workflow_step_parameters: {
          '1': { parameters: { server_id: 'srv-override' } },
          '2': { parameters: {} },
        },
      });
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_step_parameters: {
          '1': { parameters: { server_id: 'srv-override' } },
          '2': { parameters: { server_id: 'srv01' } },
        },
      })
    );
    unmount();
  });

  it('3.3 sans paramètres communs : workflow_step_parameters construit uniquement depuis per-step (AC4)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({
        workflow_step_parameters: {
          '1': { parameters: { specific: 'val1' } },
          '2': { parameters: {} },
        },
      });
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_step_parameters: {
          '1': { parameters: { specific: 'val1' } },
        },
      })
    );
    unmount();
  });

  it('3.4 shared_parameters vides {} : pas d\'injection, équivalent à aucun paramètre commun (AC5)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({
        shared_parameters: {},
        workflow_step_parameters: {
          '1': { parameters: { specific: 'val1' } },
          '2': { parameters: {} },
        },
      });
    });
    await act(async () => { await result.current.handleSubmit(); });
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_step_parameters: {
          '1': { parameters: { specific: 'val1' } },
        },
      })
    );
    unmount();
  });

  it('3.5b step présent dans workflowSteps mais absent de workflow_step_parameters : shared injectés quand même (cas bord)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowAction, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({
        shared_parameters: { server_id: 'srv01' },
        // step 2 is intentionally absent from workflow_step_parameters
        workflow_step_parameters: {
          '1': { parameters: { specific: 'val1' } },
        },
      });
    });
    await act(async () => { await result.current.handleSubmit(); });
    // Step 2 has no per-step entry but should still receive shared params
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_step_parameters: {
          '1': { parameters: { server_id: 'srv01', specific: 'val1' } },
          '2': { parameters: { server_id: 'srv01' } },
        },
      })
    );
    unmount();
  });

  it('3.5 workflowSteps vide [] : fallback sur comportement existant (rétrocompatibilité)', async () => {
    const { result, unmount } = renderHook(() =>
      useExecutionWizardState({ open: false, action: mockWorkflowActionNoSteps, allowedEnvironments: ['DEV'], onCancel, onSuccess })
    );
    await act(async () => {
      result.current.setSelectedEnvironment('DEV' as never);
      result.current.setParameters({
        shared_parameters: { server_id: 'srv01' },
        workflow_step_parameters: {
          '1': { parameters: { key: 'val' } },
        },
      });
    });
    await act(async () => { await result.current.handleSubmit(); });
    // Fallback : lit workflow_step_parameters directement (ignore shared_parameters)
    expect(mockSubmitImmediate).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_step_parameters: {
          '1': { parameters: { key: 'val' } },
        },
      })
    );
    unmount();
  });
});
