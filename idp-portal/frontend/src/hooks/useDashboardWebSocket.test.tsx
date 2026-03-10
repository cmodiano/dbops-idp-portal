/**
 * Tests for useDashboardWebSocket hook (Story 5.2, Task 5.2 + Story 22.13 auth tests).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useDashboardWebSocket } from './useDashboardWebSocket';
import type { DashboardRecentExecution } from '../types/api';

// Mock useAuth
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

// Mock logger
vi.mock('../services/logger', () => ({
  default: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock WebSocket with support for CloseEvent code
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.onclose?.({ code: 1000, reason: '' });
  }

  // Helper to simulate server messages
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  // Helper to simulate connection open
  simulateOpen() {
    this.onopen?.();
  }

  // Helper to simulate close with specific code (Story 22.13)
  simulateClose(code: number, reason = '') {
    this.onclose?.({ code, reason });
  }
}

describe('useDashboardWebSocket', () => {
  const mockExecutions: DashboardRecentExecution[] = [
    {
      id: 1,
      action_name: 'Action A',
      user_display_name: 'User 1',
      environment: 'dev',
      status: 'RUNNING',
      created_at: '2026-01-30T10:00:00',
    },
    {
      id: 2,
      action_name: 'Action B',
      user_display_name: 'User 2',
      environment: 'prod',
      status: 'COMPLETED',
      created_at: '2026-01-30T09:00:00',
    },
  ];

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // Story 22.13 (AC1): URL does NOT contain token query parameter
  it('connects to /ws/dashboard WITHOUT token in URL (Story 22.13 AC1)', async () => {
    const onExecutionsUpdate = vi.fn();

    renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    expect(MockWebSocket.instances[0].url).toContain('/ws/dashboard');
    // Story 22.13: Token must NOT be in URL
    expect(MockWebSocket.instances[0].url).not.toContain('token=');
    expect(MockWebSocket.instances[0].url).not.toContain('?');
  });

  // Story 22.13 (AC2): Auth message sent on connection open
  it('sends auth message on connection open (Story 22.13 AC2)', async () => {
    const onExecutionsUpdate = vi.fn();

    renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(MockWebSocket.instances[0].send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'auth', token: 'test-token' })
    );
  });

  // Story 22.13 (AC4): Handle auth_success message
  it('handles auth_success message and sets isAuthenticated (Story 22.13 AC4)', async () => {
    const onExecutionsUpdate = vi.fn();

    const { result } = renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'auth_success',
        user_id: 'user123',
      });
    });

    expect(result.current.isAuthenticated).toBe(true);
    // auth_success should NOT be stored as lastMessage
    expect(result.current.lastMessage).toBeNull();
    expect(onExecutionsUpdate).not.toHaveBeenCalled();
  });

  // Story 22.13 (AC5): No reconnect on code 4001
  it('does not reconnect on authentication failure code 4001 (Story 22.13 AC5)', async () => {
    const onExecutionsUpdate = vi.fn();

    const { result } = renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].simulateClose(4001, 'Invalid token');
    });

    // Should NOT have created a new WebSocket instance (no reconnect)
    // Wait a bit to ensure no reconnect is scheduled
    await new Promise((r) => setTimeout(r, 100));
    expect(MockWebSocket.instances.length).toBe(1);
    expect(result.current.error).toBe('Échec d\'authentification WebSocket');
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('does not reconnect on authorization failure code 4003', async () => {
    const onExecutionsUpdate = vi.fn();

    const { result } = renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose(4003, 'Forbidden');
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(MockWebSocket.instances.length).toBe(1);
    expect(result.current.error).toBe('Accès non autorisé au flux WebSocket');
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('sets connected=true on WebSocket open', async () => {
    const onExecutionsUpdate = vi.fn();

    const { result } = renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(result.current.connected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('updates execution status on execution_update message (Task 2.2)', async () => {
    const onExecutionsUpdate = vi.fn();

    renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // Simulate execution_update message
    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'execution_update',
        execution_id: 1,
        status: 'COMPLETED',
        action_name: 'Action A',
      });
    });

    // Should call onExecutionsUpdate with updated list
    expect(onExecutionsUpdate).toHaveBeenCalled();
    const updatedList = onExecutionsUpdate.mock.calls[0][0];
    expect(updatedList[0].status).toBe('COMPLETED');
  });

  it('calls onNewError when execution fails (Task 3.1 support)', async () => {
    const onExecutionsUpdate = vi.fn();
    const onNewError = vi.fn();

    renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
        onNewError,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // Simulate execution_update with FAILED status
    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'execution_update',
        execution_id: 1,
        status: 'FAILED',
      });
    });

    expect(onNewError).toHaveBeenCalledWith(1);
  });

  it('stores lastMessage for debugging', async () => {
    const onExecutionsUpdate = vi.fn();

    const { result } = renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'execution_update',
        execution_id: 42,
        status: 'RUNNING',
        step_summary: 'Vault (1/3)',
      });
    });

    expect(result.current.lastMessage).toEqual({
      type: 'execution_update',
      execution_id: 42,
      status: 'RUNNING',
      action_name: undefined,
      step_summary: 'Vault (1/3)',
    });
  });

  it('ignores connection_ack messages', async () => {
    const onExecutionsUpdate = vi.fn();

    const { result } = renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'connection_ack',
      });
    });

    expect(result.current.lastMessage).toBeNull();
    expect(onExecutionsUpdate).not.toHaveBeenCalled();
  });

  it('inserts new executions not in current list', async () => {
    const onExecutionsUpdate = vi.fn();

    renderHook(() =>
      useDashboardWebSocket({
        recentExecutions: mockExecutions,
        onExecutionsUpdate,
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // Simulate update for execution not in list (Story 5.2 Task 2.2: insert new row — code-review)
    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'execution_update',
        execution_id: 999, // Not in mockExecutions
        status: 'COMPLETED',
      });
    });

    // Should call onExecutionsUpdate with merged list (new execution inserted, sorted by date, max 10)
    expect(onExecutionsUpdate).toHaveBeenCalledTimes(1);
    const updated = onExecutionsUpdate.mock.calls[0][0] as DashboardRecentExecution[];
    expect(updated).toHaveLength(3);
    expect(updated[0].id).toBe(999);
    expect(updated[0].status).toBe('COMPLETED');
    expect(updated[0].action_name).toBeNull();
    expect(updated[0].user_display_name).toBe('—');
    expect(updated[0].environment).toBe('dev');
    expect(updated[1].id).toBe(1);
    expect(updated[2].id).toBe(2);
  });
});
