/**
 * Tests for useExecutionsData — Story 36.2 additions.
 *
 * Verifies:
 * - actorActiveIds contient uniquement les exécutions RUNNING/SUBMITTED de l'utilisateur courant
 * - handleActorStatusUpdate met à jour le statut de l'exécution dans la liste
 * - refresh() relance listExecutions
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
  return { data: executions, pagination: { total: executions.length, page: 1, page_size: 25 } };
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
