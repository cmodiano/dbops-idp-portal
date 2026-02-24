/**
 * Tests for useWebSocket hook (Story 39.7 — coverage).
 * Tests WebSocket connection, auth flow, message handling, reconnection.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';
import * as executionService from '../../services/execution_service';
import type { ExecutionResponse, ExecutionStepResponse } from '../../types/api';

vi.mock('../../services/execution_service');
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token-123' }),
}));
vi.mock('../../services/logger', () => ({
  default: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = MockWebSocket.OPEN;
  url: string;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  static instances: MockWebSocket[] = [];

  static reset() {
    MockWebSocket.instances = [];
  }

  simulateOpen() {
    this.onopen?.({} as Event);
  }

  simulateMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  simulateClose(code = 1000, reason = '') {
    this.onclose?.({ code, reason } as CloseEvent);
  }

  simulateError() {
    this.onerror?.({} as Event);
  }
}

const mockExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy',
  user_id: 5,
  environment: 'prod',
  parameters: null,
  status: 'RUNNING',
  servicenow_change_id: null,
  started_at: '2025-01-01T10:00:00Z',
  completed_at: null,
  created_at: '2025-01-01T09:59:00Z',
  item_type: 'action',
};

const mockStep: ExecutionStepResponse = {
  id: 1,
  execution_id: 1,
  step_order: 1,
  step_name: 'Step 1',
  step_type: 'platform',
  status: 'RUNNING',
  started_at: '2025-01-01T10:00:00Z',
  completed_at: null,
  output: null,
  platform_job_id: null,
  error_message: null,
};

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.reset();
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue([mockStep]);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('returns initial state when executionId is null', async () => {
    const { result } = renderHook(() => useWebSocket(null));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.steps).toEqual([]);
    expect(result.current.execution).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('does not create WebSocket when executionId is null', async () => {
    renderHook(() => useWebSocket(null));

    await act(async () => {
      await Promise.resolve();
    });

    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('creates WebSocket with correct URL when executionId provided', async () => {
    renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain('/ws/executions/1');
  });

  it('sends auth message on WebSocket open', async () => {
    renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
    });

    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'auth', token: 'test-token-123' }),
    );
  });

  it('sets isAuthenticated=true on auth_success message', async () => {
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: 'auth_success' });
    });

    expect(result.current.isAuthenticated).toBe(true);
  });

  it('updates steps on step_update message', async () => {
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({
        type: 'step_update',
        data: { step_order: 1, step_name: 'Step 1', status: 'COMPLETED' },
      });
    });

    expect(result.current.steps.some((s) => s.step_order === 1)).toBe(true);
  });

  it('sets error on WebSocket error', async () => {
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateError();
    });

    expect(result.current.error).toBe('Erreur de connexion WebSocket');
  });

  it('does not reconnect on auth failure (code 4001)', async () => {
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateClose(4001, 'Auth failed');
    });

    expect(result.current.error).toBe("Échec d'authentification WebSocket");
    expect(result.current.isAuthenticated).toBe(false);

    // Advance time — should NOT reconnect
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });

    // Still only one WebSocket instance
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('reconnects after normal close', async () => {
    renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateClose(1000);
    });

    await act(async () => {
      vi.advanceTimersByTime(2001);
    });

    // Should have created a second WebSocket
    expect(MockWebSocket.instances.length).toBeGreaterThan(1);
  });

  it('handles execution_complete message', async () => {
    vi.mocked(executionService.getExecution).mockResolvedValue({ ...mockExecution, status: 'COMPLETED' });
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateMessage({ type: 'execution_complete' });
    });

    expect(result.current.execution?.status).toBe('COMPLETED');
    expect(ws.close).toHaveBeenCalled();
  });

  it('handles execution_failed message', async () => {
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateMessage({ type: 'execution_failed', error_message: 'Runtime error' });
    });

    expect(result.current.error).toBe('Runtime error');
    expect(ws.close).toHaveBeenCalled();
  });

  it('closes WebSocket on unmount', async () => {
    const { unmount } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    unmount();

    expect(ws.close).toHaveBeenCalled();
  });

  it('reSyncState fetches execution and steps', async () => {
    renderHook(() => useWebSocket(1));

    // Flush microtasks and promises
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // reSyncState is called on connect — verify services were called
    expect(executionService.getExecution).toHaveBeenCalledWith(1);
    expect(executionService.getExecutionSteps).toHaveBeenCalledWith(1);
  });

  it('handles parse error in message', async () => {
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    // Simulate invalid JSON
    act(() => {
      ws.onmessage?.({ data: 'invalid json{{{' } as MessageEvent);
    });

    // Should not crash - error is just logged
    expect(result.current.steps).toBeDefined();
  });

  it('adds new step when not found in existing steps', async () => {
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue([]);
    const { result } = renderHook(() => useWebSocket(1));

    await act(async () => {
      await Promise.resolve();
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateMessage({
        type: 'step_update',
        data: { step_order: 2, step_name: 'New Step', status: 'RUNNING' },
      });
    });

    expect(result.current.steps.some((s) => s.step_order === 2)).toBe(true);
  });
});
