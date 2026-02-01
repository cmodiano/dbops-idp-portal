/**
 * Tests for useDashboardWebSocket hook (Story 5.2, Task 5.2).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useDashboardWebSocket } from './useDashboardWebSocket';
import type { DashboardRecentExecution } from '../types/api';

// Mock useAuth
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.onclose?.();
  }

  send() {}

  // Helper to simulate server messages
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  // Helper to simulate connection open
  simulateOpen() {
    this.onopen?.();
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

  it('connects to /ws/dashboard with token (Task 2.1)', async () => {
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
    expect(MockWebSocket.instances[0].url).toContain('token=test-token');
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

  it('ignores executions not in current list', async () => {
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
