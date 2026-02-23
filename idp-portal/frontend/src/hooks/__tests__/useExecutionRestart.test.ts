/**
 * Tests for useExecutionRestart hook (Story 26.4 - AC3).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { createElement } from 'react';
import { App } from 'antd';
import type { ExecutionResponse } from '../../types/api';
import type { CatalogActionDetail } from '../../services/catalog_service';

// --- Mocks ---

const mockNotificationError = vi.fn();

vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>();
  // Preserve App as a real React component but override useApp
  const MockedApp = Object.assign(actual.App, {
    useApp: () => ({
      notification: { error: mockNotificationError },
      message: {},
      modal: {},
    }),
  });
  return {
    ...actual,
    App: MockedApp,
  };
});

vi.mock('../../services/catalog_service', () => ({
  fetchCatalogActionById: vi.fn(),
}));

vi.mock('../../utils/executionHelpers', () => ({
  prepareWizardParamsFromExecution: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  default: {
    debug: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
  },
}));

import { fetchCatalogActionById } from '../../services/catalog_service';
import { prepareWizardParamsFromExecution } from '../../utils/executionHelpers';
import logger from '../../services/logger';
import { useExecutionRestart } from '../useExecutionRestart';

const mockedFetchCatalogActionById = vi.mocked(fetchCatalogActionById);
const mockedPrepareWizardParams = vi.mocked(prepareWizardParamsFromExecution);

// --- Helpers ---

function makeExecution(overrides: Partial<ExecutionResponse> = {}): ExecutionResponse {
  return {
    id: 42,
    action_id: 10,
    action_name: 'Test Action',
    user_id: 1,
    environment: 'DEV',
    parameters: { key: 'value' },
    status: 'COMPLETED',
    servicenow_change_id: null,
    started_at: '2025-01-01T00:00:00Z',
    completed_at: '2025-01-01T00:01:00Z',
    created_at: '2025-01-01T00:00:00Z',
    item_type: 'action',
    ...overrides,
  };
}

function createWrapper() {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(App, null, children);
}

function createDefaultArgs() {
  const refetchCurrentState = vi.fn().mockResolvedValue(undefined);
  const isRefreshingRef = { current: false };
  return { refetchCurrentState, isRefreshingRef };
}

// --- Tests ---

describe('useExecutionRestart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns correct initial state', () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    expect(result.current.restartWizardOpen).toBe(false);
    expect(result.current.restartAction).toBeNull();
    expect(result.current.restartAllowedEnvs).toEqual([]);
    expect(result.current.restartInitialParams).toBeUndefined();
    expect(result.current.restartLoadingId).toBeNull();
    expect(typeof result.current.handleRestartExecution).toBe('function');
    expect(typeof result.current.handleRestartWizardClose).toBe('function');
    expect(typeof result.current.handleRestartSuccess).toBe('function');
  });

  it('handleRestartExecution loads action and opens wizard', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    const execution = makeExecution({ action_id: 10 });
    const actionDetail = { id: 10, name: 'Action' } as unknown as CatalogActionDetail;
    const wizardParams = { actionId: 10, environment: 'DEV', parameters: { key: 'value' } };

    mockedFetchCatalogActionById.mockResolvedValue({
      data: actionDetail,
      can_execute: true,
      allowed_environments: ['DEV', 'PROD'],
    });
    mockedPrepareWizardParams.mockReturnValue(wizardParams);

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.handleRestartExecution(execution);
    });

    expect(mockedFetchCatalogActionById).toHaveBeenCalledWith(10);
    expect(mockedPrepareWizardParams).toHaveBeenCalledWith(execution);
    expect(result.current.restartWizardOpen).toBe(true);
    expect(result.current.restartAction).toEqual(actionDetail);
    expect(result.current.restartAllowedEnvs).toEqual(['DEV', 'PROD']);
    expect(result.current.restartInitialParams).toEqual(wizardParams);
    expect(result.current.restartLoadingId).toBeNull();
  });

  it('handleRestartExecution shows error when no action_id', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    const execution = makeExecution({ action_id: undefined as unknown as number });

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.handleRestartExecution(execution);
    });

    expect(mockNotificationError).toHaveBeenCalledWith({
      title: 'Erreur de relance',
      description: 'Action non disponible — impossible de relancer cette exécution',
    });
    expect(vi.mocked(logger.error)).toHaveBeenCalled();
    expect(mockedFetchCatalogActionById).not.toHaveBeenCalled();
    expect(result.current.restartWizardOpen).toBe(false);
  });

  it('handleRestartExecution shows error when prepareWizardParams returns null', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    const execution = makeExecution({ action_id: 10 });
    const actionDetail = { id: 10, name: 'Action' } as unknown as CatalogActionDetail;

    mockedFetchCatalogActionById.mockResolvedValue({
      data: actionDetail,
      can_execute: true,
      allowed_environments: ['DEV'],
    });
    mockedPrepareWizardParams.mockReturnValue(null);

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.handleRestartExecution(execution);
    });

    expect(mockNotificationError).toHaveBeenCalledWith({
      title: 'Erreur de relance',
      description: 'Action non disponible — impossible de relancer cette exécution',
    });
    expect(result.current.restartWizardOpen).toBe(false);
  });

  it('handleRestartExecution handles fetch errors', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    const execution = makeExecution({ action_id: 10 });

    mockedFetchCatalogActionById.mockRejectedValue(new Error('Network failure'));

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.handleRestartExecution(execution);
    });

    expect(mockNotificationError).toHaveBeenCalledWith({
      title: 'Erreur de relance',
      description: 'Network failure',
    });
    expect(result.current.restartWizardOpen).toBe(false);
    expect(result.current.restartLoadingId).toBeNull();
  });

  it('handleRestartWizardClose resets all state', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    const execution = makeExecution({ action_id: 10 });
    const actionDetail = { id: 10, name: 'Action' } as unknown as CatalogActionDetail;
    const wizardParams = { actionId: 10, environment: 'DEV' };

    mockedFetchCatalogActionById.mockResolvedValue({
      data: actionDetail,
      can_execute: true,
      allowed_environments: ['DEV'],
    });
    mockedPrepareWizardParams.mockReturnValue(wizardParams);

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    // Open wizard first
    await act(async () => {
      await result.current.handleRestartExecution(execution);
    });
    expect(result.current.restartWizardOpen).toBe(true);

    // Close wizard
    act(() => {
      result.current.handleRestartWizardClose();
    });

    expect(result.current.restartWizardOpen).toBe(false);
    expect(result.current.restartAction).toBeNull();
    expect(result.current.restartAllowedEnvs).toEqual([]);
    expect(result.current.restartInitialParams).toBeUndefined();
  });

  it('handleRestartSuccess closes wizard and calls refetchCurrentState', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    const execution = makeExecution({ action_id: 10 });
    const actionDetail = { id: 10, name: 'Action' } as unknown as CatalogActionDetail;
    const wizardParams = { actionId: 10, environment: 'DEV' };

    mockedFetchCatalogActionById.mockResolvedValue({
      data: actionDetail,
      can_execute: true,
      allowed_environments: ['DEV'],
    });
    mockedPrepareWizardParams.mockReturnValue(wizardParams);

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    // Open wizard first
    await act(async () => {
      await result.current.handleRestartExecution(execution);
    });
    expect(result.current.restartWizardOpen).toBe(true);

    // Trigger restart success
    act(() => {
      result.current.handleRestartSuccess(999);
    });

    expect(result.current.restartWizardOpen).toBe(false);
    expect(result.current.restartAction).toBeNull();
    expect(refetchCurrentState).toHaveBeenCalled();
    expect(isRefreshingRef.current).toBe(true); // set before promise resolves
    expect(vi.mocked(logger.debug)).toHaveBeenCalledWith('Restart execution created', { executionId: 999 });
  });

  it('handleRestartSuccess does not call refetchCurrentState when already refreshing', async () => {
    const { refetchCurrentState, isRefreshingRef } = createDefaultArgs();
    isRefreshingRef.current = true; // Already refreshing

    const { result } = renderHook(
      () => useExecutionRestart(refetchCurrentState, isRefreshingRef),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.handleRestartSuccess(999);
    });

    expect(refetchCurrentState).not.toHaveBeenCalled();
    expect(result.current.restartWizardOpen).toBe(false);
  });
});
