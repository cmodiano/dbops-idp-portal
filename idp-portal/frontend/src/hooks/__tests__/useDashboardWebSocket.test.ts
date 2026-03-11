/**
 * Tests for useDashboardWebSocket hook (Story 71.11, AC #6).
 * Mock WebSocket manuel pour contrôler les événements WS.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// --- Mock WebSocket global ---
let lastWsInstance: MockWebSocket | null = null;

class MockWebSocket {
  url: string;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(url: string) {
    this.url = url;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    lastWsInstance = this;
  }
}

vi.stubGlobal('WebSocket', MockWebSocket);

// --- Autres mocks ---

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  default: {
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

import { useDashboardWebSocket } from '../useDashboardWebSocket';
import { useAuth } from '../../contexts/AuthContext';

const mockUseAuth = vi.mocked(useAuth);

describe('useDashboardWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastWsInstance = null;
    mockUseAuth.mockReturnValue({ accessToken: 'test-token' } as any);
  });

  it('connexion initiale — WebSocket instancié avec URL /ws/dashboard, connected=false initialement', () => {
    const onExecutionsUpdate = vi.fn();
    const onNewError = vi.fn();
    const options = { recentExecutions: [], onExecutionsUpdate, onNewError };

    const { result } = renderHook(() => useDashboardWebSocket(options));

    expect(lastWsInstance).not.toBeNull();
    expect(lastWsInstance!.url).toContain('/ws/dashboard');
    expect(result.current.connected).toBe(false);
  });

  it('onopen — connected=true, message auth envoyé via ws.send()', async () => {
    const onExecutionsUpdate = vi.fn();
    const onNewError = vi.fn();
    // Stable references to avoid useEffect re-run on every render
    const options = { recentExecutions: [], onExecutionsUpdate, onNewError };

    const { result } = renderHook(() => useDashboardWebSocket(options));

    // Capture WS instance set during mount
    const ws = lastWsInstance;
    expect(ws).not.toBeNull();

    await act(async () => {
      ws!.onopen?.(new Event('open'));
    });

    expect(result.current.connected).toBe(true);
    expect(ws!.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'auth', token: 'test-token' }),
    );
  });

  it('message auth_success — isAuthenticated=true', async () => {
    const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError: vi.fn() };
    const { result } = renderHook(() => useDashboardWebSocket(options));

    const ws = lastWsInstance!;

    await act(async () => {
      ws.onopen?.(new Event('open'));
    });

    await act(async () => {
      ws.onmessage?.(
        new MessageEvent('message', { data: JSON.stringify({ type: 'auth_success' }) }),
      );
    });

    expect(result.current.isAuthenticated).toBe(true);
  });

  it('message execution_update existing — onExecutionsUpdate appelé avec liste mise à jour', async () => {
    const existingExec = {
      id: 1,
      action_name: 'Deploy',
      user_display_name: 'user',
      environment: 'dev',
      status: 'RUNNING' as const,
      created_at: new Date().toISOString(),
    } as any;
    const onExecutionsUpdate = vi.fn();
    const options = {
      recentExecutions: [existingExec],
      onExecutionsUpdate,
      onNewError: vi.fn(),
    };

    renderHook(() => useDashboardWebSocket(options));
    const ws = lastWsInstance!;

    await act(async () => {
      ws.onopen?.(new Event('open'));
    });

    await act(async () => {
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'execution_update', execution_id: 1, status: 'SUCCESS' }),
      }));
    });

    expect(onExecutionsUpdate).toHaveBeenCalled();
    const updatedList = onExecutionsUpdate.mock.calls[0][0];
    expect(updatedList[0].status).toBe('SUCCESS');
  });

  it('message execution_update nouveau id — insertion dans la liste', async () => {
    const onExecutionsUpdate = vi.fn();
    const options = { recentExecutions: [], onExecutionsUpdate, onNewError: vi.fn() };

    renderHook(() => useDashboardWebSocket(options));
    const ws = lastWsInstance!;

    await act(async () => {
      ws.onopen?.(new Event('open'));
    });

    await act(async () => {
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({
          type: 'execution_update',
          execution_id: 99,
          status: 'RUNNING',
          action_name: 'New Action',
        }),
      }));
    });

    expect(onExecutionsUpdate).toHaveBeenCalled();
    const updatedList = onExecutionsUpdate.mock.calls[0][0];
    expect(updatedList.some((e: any) => e.id === 99)).toBe(true);
  });

  it('message execution_update — limite à 10 éléments max après insertion', async () => {
    // 10 existing executions — inserting a new one should still cap at 10
    const makeExec = (id: number, created_at: string) => ({
      id,
      action_name: `Action ${id}`,
      user_display_name: 'user',
      environment: 'dev',
      status: 'COMPLETED' as const,
      created_at,
    });
    const existingExecs = Array.from({ length: 10 }, (_, i) =>
      makeExec(i + 1, new Date(2024, 0, i + 1).toISOString()),
    );

    const onExecutionsUpdate = vi.fn();
    const options = { recentExecutions: existingExecs, onExecutionsUpdate, onNewError: vi.fn() };

    renderHook(() => useDashboardWebSocket(options));
    const ws = lastWsInstance!;

    await act(async () => {
      ws.onopen?.(new Event('open'));
    });

    await act(async () => {
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({
          type: 'execution_update',
          execution_id: 999,
          status: 'RUNNING',
          action_name: 'New Action',
        }),
      }));
    });

    expect(onExecutionsUpdate).toHaveBeenCalled();
    const updatedList = onExecutionsUpdate.mock.calls[0][0];
    expect(updatedList.length).toBeLessThanOrEqual(10);
  });

  it('message execution_update status FAILED — onNewError appelé avec execution_id', async () => {
    const onNewError = vi.fn();
    const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError };

    renderHook(() => useDashboardWebSocket(options));
    const ws = lastWsInstance!;

    await act(async () => {
      ws.onopen?.(new Event('open'));
    });

    await act(async () => {
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'execution_update', execution_id: 42, status: 'FAILED' }),
      }));
    });

    expect(onNewError).toHaveBeenCalledWith(42);
  });

  it('message JSON malformé — pas de crash', async () => {
    const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError: vi.fn() };
    renderHook(() => useDashboardWebSocket(options));
    const ws = lastWsInstance!;

    await act(async () => {
      ws.onopen?.(new Event('open'));
    });

    expect(() => {
      act(() => {
        ws.onmessage?.(new MessageEvent('message', { data: 'NOT_JSON{{{' }));
      });
    }).not.toThrow();
  });

  describe('tests avec timers (vi.useFakeTimers)', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('onclose code normal — reconnexion après RECONNECT_DELAY_MS', () => {
      const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError: vi.fn() };
      renderHook(() => useDashboardWebSocket(options));

      const firstWs = lastWsInstance;

      act(() => {
        lastWsInstance!.onclose?.(new CloseEvent('close', { code: 1000 }));
      });

      // Before delay — no reconnection yet
      expect(lastWsInstance).toBe(firstWs);

      // After delay — new WebSocket created
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      expect(lastWsInstance).not.toBe(firstWs);
    });

    it('onclose code 4001 — PAS de reconnexion, error set "Échec d\'authentification"', async () => {
      const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError: vi.fn() };
      const { result } = renderHook(() => useDashboardWebSocket(options));

      const firstWs = lastWsInstance;

      await act(async () => {
        firstWs!.onclose?.(new CloseEvent('close', { code: 4001 }));
      });

      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Still the same ws instance (no reconnection)
      expect(lastWsInstance).toBe(firstWs);
      expect(result.current.error).toContain('Échec');
    });

    it('onclose code 4003 — PAS de reconnexion, error set "Accès non autorisé"', async () => {
      const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError: vi.fn() };
      const { result } = renderHook(() => useDashboardWebSocket(options));

      const firstWs = lastWsInstance;

      await act(async () => {
        firstWs!.onclose?.(new CloseEvent('close', { code: 4003 }));
      });

      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Still the same ws instance (no reconnection)
      expect(lastWsInstance).toBe(firstWs);
      expect(result.current.error).toContain('autorisé');
    });
  });

  it('cleanup à l\'unmount — ws.close() appelé', () => {
    const options = { recentExecutions: [], onExecutionsUpdate: vi.fn(), onNewError: vi.fn() };
    const { unmount } = renderHook(() => useDashboardWebSocket(options));

    const ws = lastWsInstance;
    expect(ws).not.toBeNull();

    unmount();

    expect(ws!.close).toHaveBeenCalled();
  });
});
