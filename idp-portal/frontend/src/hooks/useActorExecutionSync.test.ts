/**
 * Tests for useActorExecutionSync (Story 36.2).
 *
 * Verifies:
 * - WS connection created per executionId
 * - execution_complete → onStatusUpdate called + WS closed
 * - execution_failed → onStatusUpdate called + WS closed
 * - WS error (non-4001) → fallback polling activated at 2000 ms
 * - WS error code 4001 → no reconnect, no polling
 * - ID removed from executionIds → WS closed
 * - unmount → all WS closed, all intervals cleared
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useActorExecutionSync } from './useActorExecutionSync';
import * as executionService from '../services/execution_service';
import type { ExecutionResponse } from '../types/api';

// ── Mock AuthContext ──────────────────────────────────────────────────────────
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    accessToken: 'test-token',
    user: { id: 1 },
  }),
}));

// ── Mock execution_service ────────────────────────────────────────────────────
vi.mock('../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(),
  listExecutions: vi.fn(),
}));

const mockGetExecution = executionService.getExecution as ReturnType<typeof vi.fn>;

// ── Mock WebSocket ────────────────────────────────────────────────────────────
class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closedWith: number | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();

  close(code?: number) {
    this.closedWith = code ?? 1000;
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: this.closedWith }));
    }
  }

  // Helper: simulate server message
  simulateMessage(data: object) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  // Helper: simulate open
  simulateOpen() {
    this.readyState = WebSocket.OPEN;
    if (this.onopen) this.onopen(new Event('open'));
  }

  // Helper: simulate error
  simulateError(closeCode = 1006) {
    if (this.onerror) this.onerror(new Event('error'));
    this.close(closeCode);
  }
}

const mockExecution = (id: number, status: ExecutionResponse['status']): ExecutionResponse => ({
  id,
  action_id: 10,
  action_name: 'Test Action',
  user_id: 1,
  environment: 'dev',
  parameters: null,
  status,
  servicenow_change_id: null,
  started_at: null,
  completed_at: null,
  created_at: '2026-01-01T00:00:00Z',
});

describe('useActorExecutionSync', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('4.2 — crée une connexion WS pour chaque executionId fourni', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1, 2], onStatusUpdate));
    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[0].url).toContain('/ws/executions/1');
    expect(MockWebSocket.instances[1].url).toContain('/ws/executions/2');
  });

  it('4.2 — envoie le token en premier message après ouverture (pas dans l\'URL)', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();
    expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'auth', token: 'test-token' }));
    expect(ws.url).not.toContain('token=');
  });

  it('4.3 — execution_complete → onStatusUpdate(id, COMPLETED) appelé et WS fermée', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({ type: 'execution_complete', status: 'COMPLETED' });
    expect(onStatusUpdate).toHaveBeenCalledWith(1, 'COMPLETED', expect.objectContaining({ type: 'execution_complete' }));
    expect(ws.closedWith).not.toBeNull();
  });

  it('4.3 — execution_complete utilise "COMPLETED" par défaut si status absent', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({ type: 'execution_complete' });
    expect(onStatusUpdate).toHaveBeenCalledWith(1, 'COMPLETED', expect.any(Object));
  });

  it('4.4 — execution_failed → onStatusUpdate(id, FAILED, {error_message}) appelé et WS fermée', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({ type: 'execution_failed', error_message: 'Timeout' });
    expect(onStatusUpdate).toHaveBeenCalledWith(1, 'FAILED', { status: 'FAILED', error_message: 'Timeout' });
    expect(ws.closedWith).not.toBeNull();
  });

  it('4.3b — execution_complete → aucun fallback polling ne démarre après fermeture WS', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({ type: 'execution_complete', status: 'COMPLETED' });

    // Verify no fallback polling started (regression guard: ws.close() after terminal message
    // must NOT trigger startFallbackPolling)
    vi.advanceTimersByTime(10000);
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it('4.4b — execution_failed → aucun fallback polling ne démarre après fermeture WS', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({ type: 'execution_failed', error_message: 'Timeout' });

    vi.advanceTimersByTime(10000);
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it('4.5 — WS erreur (code ≠ 4001) → fallback polling 2000 ms activé', () => {
    const onStatusUpdate = vi.fn();
    const execution = mockExecution(1, 'RUNNING');
    mockGetExecution.mockResolvedValue(execution);

    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateError(1006);

    // Avancer le timer de 2000 ms
    vi.advanceTimersByTime(2000);
    expect(mockGetExecution).toHaveBeenCalledWith(1);
  });

  it('4.5 — polling s\'arrête quand l\'exécution atteint un statut terminal', async () => {
    const onStatusUpdate = vi.fn();
    const completedExecution = mockExecution(1, 'COMPLETED');
    mockGetExecution.mockResolvedValue(completedExecution);

    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateError(1006);

    // Premier tick
    await vi.runAllTimersAsync();
    expect(onStatusUpdate).toHaveBeenCalledWith(1, 'COMPLETED', completedExecution);

    // Pas de nouvel appel après statut terminal
    vi.clearAllMocks();
    await vi.runAllTimersAsync();
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it('4.6 — fermeture serveur code 4001 (auth failure) → aucun reconnect, aucun polling', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    // Le serveur ferme directement avec 4001 (auth failure) — pas via onerror
    ws.close(4001);

    vi.advanceTimersByTime(10000);
    expect(mockGetExecution).not.toHaveBeenCalled();
    // Pas de nouvelle WS créée
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('4.6b — fermeture serveur code 4003 (authz failure) → aucun reconnect, aucun polling', () => {
    const onStatusUpdate = vi.fn();
    renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.close(4003);

    vi.advanceTimersByTime(10000);
    expect(mockGetExecution).not.toHaveBeenCalled();
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('4.7 — quand un ID quitte executionIds, sa WS est fermée et aucun fallback polling ne démarre', () => {
    const onStatusUpdate = vi.fn();
    mockGetExecution.mockResolvedValue(mockExecution(1, 'RUNNING'));
    const { rerender } = renderHook(
      ({ ids }: { ids: number[] }) => useActorExecutionSync(ids, onStatusUpdate),
      { initialProps: { ids: [1, 2] } },
    );
    expect(MockWebSocket.instances).toHaveLength(2);
    const ws1 = MockWebSocket.instances[0];

    rerender({ ids: [2] });
    expect(ws1.closedWith).not.toBeNull();

    // Verify no fallback polling started for the removed ID (regression guard for the bug
    // where ws.close() triggered onclose → startFallbackPolling on an intentionally removed WS)
    vi.advanceTimersByTime(10000);
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it('4.8 — unmount → toutes les WS fermées, tous les intervalles annulés', () => {
    const onStatusUpdate = vi.fn();
    const { unmount } = renderHook(() => useActorExecutionSync([1, 2], onStatusUpdate));

    const [ws1, ws2] = MockWebSocket.instances;
    unmount();

    expect(ws1.readyState).toBe(WebSocket.CLOSED);
    expect(ws2.readyState).toBe(WebSocket.CLOSED);
  });

  it('4.8 — unmount après fallback polling → intervals annulés, pas d\'appels après démontage', async () => {
    const onStatusUpdate = vi.fn();
    const runningExecution = mockExecution(1, 'RUNNING');
    mockGetExecution.mockResolvedValue(runningExecution);

    const { unmount } = renderHook(() => useActorExecutionSync([1], onStatusUpdate));
    const ws = MockWebSocket.instances[0];
    ws.simulateError(1006);

    unmount();
    vi.clearAllMocks();
    await vi.runAllTimersAsync();
    expect(onStatusUpdate).not.toHaveBeenCalled();
  });
});
