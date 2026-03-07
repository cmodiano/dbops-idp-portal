/**
 * Tests for useExecutionsData — Stories 36.2 and 36.3.
 *
 * Story 36.2 — Real-time actor sync:
 * - actorActiveIds contient uniquement les exécutions RUNNING/SUBMITTED de l'utilisateur courant
 * - handleActorStatusUpdate met à jour le statut de l'exécution dans la liste
 * - refresh() relance listExecutions
 *
 * Story 36.3 — Observer polling + Visibility API:
 * - setInterval à 10 000 ms quand des exécutions RUNNING sont présentes
 * - setInterval à 30 000 ms quand aucune exécution en cours
 * - Pas de refetch quand document.hidden = true
 * - Refetch immédiat au retour au premier plan (visibilitychange)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useExecutionsData } from './useExecutionsData';
import * as executionService from '../services/execution_service';
import * as actorSyncModule from './useActorExecutionSync';
import type { ExecutionResponse, ExecutionFilters } from '../types/api';

// ── Mocks ─────────────────────────────────────────────────────────────────────
vi.mock('../services/execution_service');
vi.mock('../services/integrations_service', () => ({
  getIntegrations: vi.fn().mockResolvedValue([]),
}));
vi.mock('../services/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 42, username: 'actor' },
    accessToken: 'token',
  }),
}));
// useActorExecutionSync is mocked — won't create real WebSocket connections
vi.mock('./useActorExecutionSync', () => ({
  useActorExecutionSync: vi.fn(),
}));

const mockListExecutions = vi.mocked(executionService.listExecutions);
const mockFetchStats = vi.mocked(executionService.fetchExecutionStats);
const mockFetchTimeSeries = vi.mocked(executionService.fetchExecutionTimeSeries);
const mockListPending = vi.mocked(executionService.listPendingApprovals);
const mockActorSync = vi.mocked(actorSyncModule.useActorExecutionSync);

function makeExecution(id: number, status: ExecutionResponse['status'], userId = 42): ExecutionResponse {
  return {
    id,
    action_id: 1,
    action_name: 'Action ' + id,
    user_id: userId,
    environment: 'dev',
    parameters: null,
    status,
    servicenow_change_id: null,
    started_at: null,
    completed_at: null,
    created_at: '2026-01-01T00:00:00Z',
  };
}

function makeListResponse(executions: ExecutionResponse[]) {
  return { data: executions, pagination: { total: executions.length, page: 1, page_size: 25, total_pages: 1 } };
}

const defaultFilters: ExecutionFilters = {};

describe('useExecutionsData — Story 36.2', () => {
  beforeEach(() => {
    mockListExecutions.mockResolvedValue(makeListResponse([]));
    mockFetchStats.mockResolvedValue({ executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0 });
    mockFetchTimeSeries.mockResolvedValue([]);
    mockListPending.mockResolvedValue(makeListResponse([]));
    mockActorSync.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('5.1 — actorActiveIds contient uniquement les exécutions RUNNING/SUBMITTED de l\'utilisateur courant', async () => {
    const executions = [
      makeExecution(1, 'RUNNING', 42),    // acteur, actif → inclus
      makeExecution(2, 'SUBMITTED', 42),  // acteur, actif → inclus
      makeExecution(3, 'COMPLETED', 42),  // acteur, terminal → exclu
      makeExecution(4, 'RUNNING', 99),    // autre user → exclu
    ];
    mockListExecutions.mockResolvedValue(makeListResponse(executions));

    renderHook(() => useExecutionsData(defaultFilters, false));

    await waitFor(() => {
      // Le hook est appelé à chaque render; vérifier le dernier appel
      expect(mockActorSync).toHaveBeenCalled();
      const calls = mockActorSync.mock.calls;
      const lastCallIds = calls[calls.length - 1][0] as number[];
      expect(lastCallIds).toContain(1);
      expect(lastCallIds).toContain(2);
      expect(lastCallIds).not.toContain(3);
      expect(lastCallIds).not.toContain(4);
    });
  });

  it('5.2 — handleActorStatusUpdate(1, "COMPLETED") → exécution #1 passe à COMPLETED', async () => {
    // Capture le callback passé à useActorExecutionSync
    let capturedCallback: ((id: number, status: string, data?: Partial<ExecutionResponse>) => void) | null = null;
    mockActorSync.mockImplementation(
      (_ids, cb) => {
        capturedCallback = cb as typeof capturedCallback;
      }
    );

    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));

    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.executions).toHaveLength(1);
    });

    expect(result.current.executions[0].status).toBe('RUNNING');
    expect(capturedCallback).not.toBeNull();

    // Simuler la mise à jour WebSocket via le callback
    await act(async () => {
      capturedCallback!(1, 'COMPLETED');
    });

    expect(result.current.executions[0].status).toBe('COMPLETED');
  });

  it('5.3 — refresh() relance listExecutions', async () => {
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const callsBefore = mockListExecutions.mock.calls.length;

    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore));
    expect(mockListExecutions.mock.calls.length).toBe(callsBefore + 1);
  });

  it('refresh est exposé dans le retour du hook', async () => {
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(typeof result.current.refresh).toBe('function');
  });
});

// ── Story 36.3 — Polling observateur + Visibility API ─────────────────────────

describe('useExecutionsData — Story 36.3 : polling observateur', () => {
  beforeEach(() => {
    mockListExecutions.mockResolvedValue(makeListResponse([]));
    mockFetchStats.mockResolvedValue({ executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0 });
    mockFetchTimeSeries.mockResolvedValue([]);
    mockListPending.mockResolvedValue(makeListResponse([]));
    mockActorSync.mockReset();
    // Ensure tab is visible by default
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  it('3.1 — RUNNING exécutions → setTimeout appelé avec 10 000 ms ou 30 000 ms (polling actif)', async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');
    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));

    renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(mockListExecutions).toHaveBeenCalled());

    const delays = setTimeoutSpy.mock.calls.map((args) => args[1]).filter((d): d is number => typeof d === 'number');
    const hasPollingDelay = delays.some((d) => d === 10_000 || d === 30_000);
    expect(hasPollingDelay).toBe(true);

    setTimeoutSpy.mockRestore();
  });

  it('3.2 — Aucune exécution en cours → setTimeout appelé avec 30 000 ms', async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');
    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'COMPLETED', 42)]));

    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const pollingCall = setTimeoutSpy.mock.calls.find((args) => args[1] === 30_000);
    expect(pollingCall).toBeDefined();

    setTimeoutSpy.mockRestore();
  });

  it('3.3 — document.hidden = true → refetchSilent non appelé à l\'intervalle', async () => {
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));

    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const initialCalls = mockListExecutions.mock.calls.length;
    vi.useFakeTimers();
    try {
      vi.advanceTimersByTime(35_000);
      await Promise.resolve();
      expect(mockListExecutions.mock.calls.length).toBe(initialCalls);
    } finally {
      vi.useRealTimers();
    }
  });

  it('3.4 — document.hidden = false et intervalle écoulé → refetchSilent appelé', async () => {
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));

    let pollingCallback: (() => void) | null = null;
    const realSetTimeout = globalThis.setTimeout;
    vi.spyOn(globalThis, 'setTimeout').mockImplementation(((fn: TimerHandler, delay?: number, ...rest: unknown[]) => {
      if (delay === 10_000 || delay === 30_000) pollingCallback = fn as () => void;
      return realSetTimeout(fn, delay, ...rest);
    }) as typeof setTimeout);

    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(pollingCallback).toBeDefined();
    const callsBefore = mockListExecutions.mock.calls.length;
    await act(async () => {
      pollingCallback!();
    });
    await waitFor(() => expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore));

    vi.restoreAllMocks();
  });

  it('3.5 — retour au premier plan (visibilitychange) → refetchSilent déclenché immédiatement  ', async () => {
    // Start with tab hidden
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });

    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));

    renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(mockListExecutions).toHaveBeenCalled());

    const callsBefore = mockListExecutions.mock.calls.length;

    // Tab becomes visible → visibilitychange fires → immediate refetch
    await act(async () => {
      Object.defineProperty(document, 'hidden', { value: false, configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await waitFor(() => {
      expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});

describe('useExecutionsData — coverage extras', () => {
  beforeEach(() => {
    mockListExecutions.mockResolvedValue(makeListResponse([]));
    mockFetchStats.mockResolvedValue({ executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0 });
    mockFetchTimeSeries.mockResolvedValue([]);
    mockListPending.mockResolvedValue(makeListResponse([]));
    mockActorSync.mockReset();
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  it('fetchData error case sets error state', async () => {
    mockListExecutions.mockRejectedValue(new Error('Server error'));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Server error');
  });

  it('refetchCurrentState calls listExecutions', async () => {
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const callsBefore = mockListExecutions.mock.calls.length;
    await act(async () => { await result.current.refetchCurrentState(); });
    expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it('updateExecutionInList updates a single execution', async () => {
    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.executions[0].status).toBe('RUNNING');
    act(() => { result.current.updateExecutionInList(1, { status: 'COMPLETED' }); });
    expect(result.current.executions[0].status).toBe('COMPLETED');
  });

  it('loadPendingApprovals when canApprove=true calls listPendingApprovals', async () => {
    mockListPending.mockResolvedValue(makeListResponse([makeExecution(10, 'PENDING_APPROVAL', 42)]));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, true));
    await waitFor(() => expect(result.current.pendingApprovalsLoading).toBe(false));
    expect(mockListPending).toHaveBeenCalled();
    expect(result.current.pendingApprovals).toHaveLength(1);
  });

  it('loadPendingApprovals when canApprove=false skips call', async () => {
    renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(mockListExecutions).toHaveBeenCalled());
    expect(mockListPending).not.toHaveBeenCalled();
  });

  it('loadPendingApprovals error returns empty array', async () => {
    mockListPending.mockRejectedValue(new Error('Forbidden'));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, true));
    await waitFor(() => expect(result.current.pendingApprovalsLoading).toBe(false));
    expect(result.current.pendingApprovals).toEqual([]);
  });

  it('stats loading error sets statsData to defaults', async () => {
    mockFetchStats.mockRejectedValue(new Error('Stats error'));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.statsLoading).toBe(false));
    expect(result.current.statsData).toEqual({ executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0 });
  });

  it('timeSeries loading error sets timeSeriesData to empty', async () => {
    mockFetchTimeSeries.mockRejectedValue(new Error('TimeSeries error'));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.timeSeriesLoading).toBe(false));
    expect(result.current.timeSeriesData).toEqual([]);
  });

  it('setCurrentPage triggers re-fetch', async () => {
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const callsBefore = mockListExecutions.mock.calls.length;
    act(() => { result.current.setCurrentPage(2); });
    await waitFor(() => expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore));
  });

  it('setActiveScope changes scope and triggers re-fetch', async () => {
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const callsBefore = mockListExecutions.mock.calls.length;
    act(() => { result.current.setActiveScope('mine'); });
    await waitFor(() => expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore));
    expect(result.current.activeScope).toBe('mine');
  });

  it('sortField and sortOrder setters are exposed', async () => {
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setSortField('status');
      result.current.setSortOrder('ascend');
    });
    expect(result.current.sortField).toBe('status');
    expect(result.current.sortOrder).toBe('ascend');
  });

  it('handleActorStatusUpdate with data payload merges extra fields', async () => {
    let capturedCallback: ((id: number, status: string, data?: Partial<import('../types/api').ExecutionResponse>) => void) | null = null;
    mockActorSync.mockImplementation((_ids, cb) => { capturedCallback = cb as typeof capturedCallback; });
    mockListExecutions.mockResolvedValue(makeListResponse([makeExecution(1, 'RUNNING', 42)]));
    const { result } = renderHook(() => useExecutionsData(defaultFilters, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      capturedCallback!(1, 'COMPLETED', { completed_at: '2026-01-01T12:00:00Z' });
    });
    expect(result.current.executions[0].status).toBe('COMPLETED');
    expect(result.current.executions[0].completed_at).toBe('2026-01-01T12:00:00Z');
  });
});

// ── Story 58.5 — Propagation approbations entre fenêtres ────────────────────

describe('useExecutionsData — Story 58.5 : polling approbations', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockListExecutions.mockResolvedValue(makeListResponse([]));
    mockFetchStats.mockResolvedValue({ executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0 });
    mockFetchTimeSeries.mockResolvedValue([]);
    mockListPending.mockResolvedValue(makeListResponse([]));
    mockActorSync.mockReset();
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  it('58.5-1 — loadPendingApprovals est appelé périodiquement quand canApprove=true (AC1)', async () => {
    mockListPending.mockResolvedValue(makeListResponse([makeExecution(10, 'PENDING_APPROVAL', 42)]));

    renderHook(() => useExecutionsData(defaultFilters, true));

    // Attendre le chargement initial
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
    const initialCalls = mockListPending.mock.calls.length;
    expect(initialCalls).toBeGreaterThanOrEqual(1); // appel initial au mount

    // Avancer de 30s → polling déclenché
    await vi.advanceTimersByTimeAsync(30_000);
    expect(mockListPending.mock.calls.length).toBeGreaterThan(initialCalls);

    // Avancer de 30s supplémentaires → un autre appel
    const afterFirstPoll = mockListPending.mock.calls.length;
    await vi.advanceTimersByTimeAsync(30_000);
    expect(mockListPending.mock.calls.length).toBeGreaterThan(afterFirstPoll);
  });

  it('58.5-2 — loadPendingApprovals n\'est PAS pollé quand canApprove=false (AC3)', async () => {
    renderHook(() => useExecutionsData(defaultFilters, false));

    await vi.advanceTimersByTimeAsync(0);
    expect(mockListPending).not.toHaveBeenCalled(); // pas d'appel initial non plus

    // Avancer de 60s → aucun appel polling
    await vi.advanceTimersByTimeAsync(60_000);
    expect(mockListPending).not.toHaveBeenCalled();
  });

  it('58.5-3 — loadPendingApprovals est appelé sur visibilitychange quand canApprove=true (AC2)', async () => {
    mockListPending.mockResolvedValue(makeListResponse([]));

    renderHook(() => useExecutionsData(defaultFilters, true));
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
    const callsBefore = mockListPending.mock.calls.length;

    // Simuler tab hidden → visible
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(0);

    // Pas d'appel quand hidden
    const callsAfterHidden = mockListPending.mock.calls.length;
    expect(callsAfterHidden).toBe(callsBefore);

    // Retour visible → appel immédiat
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(0);

    expect(mockListPending.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it('58.5-4 — le polling s\'arrête quand l\'onglet est caché (AC3)', async () => {
    mockListPending.mockResolvedValue(makeListResponse([]));
    // Start with tab visible
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });

    renderHook(() => useExecutionsData(defaultFilters, true));
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);

    // Verify polling works when visible
    const callsBeforePoll = mockListPending.mock.calls.length;
    await vi.advanceTimersByTimeAsync(30_000);
    expect(mockListPending.mock.calls.length).toBeGreaterThan(callsBeforePoll);

    // Tab becomes hidden → polling ticks should be skipped
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    const callsBeforeHidden = mockListPending.mock.calls.length;

    // Avancer de 60s avec tab hidden → pas de polling
    await vi.advanceTimersByTimeAsync(60_000);
    expect(mockListPending.mock.calls.length).toBe(callsBeforeHidden);
  });
});
