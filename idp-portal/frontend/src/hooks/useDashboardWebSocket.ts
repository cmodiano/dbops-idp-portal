/**
 * useDashboardWebSocket - Real-time dashboard updates via WebSocket (Story 5.2, Task 2.1-2.3).
 *
 * Connects to /ws/dashboard, receives execution_update messages.
 * Updates the recent executions list in real-time without full refetch.
 *
 * Story 22.13: Token sent in first message after connection (not in URL query string).
 * Sequence: connect → send {type:"auth", token} → receive {type:"auth_success"} → business messages.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import type { DashboardRecentExecution, ExecutionStatusType } from '../types/api';
import logger from '../services/logger';

const RECONNECT_DELAY_MS = 3000;
const WS_PROTOCOL = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE = typeof window !== 'undefined' ? `${WS_PROTOCOL}//${window.location.host}` : 'ws://localhost';

/** WebSocket close codes for authentication/authorization failure — do not reconnect. */
const WS_AUTH_FAILED_CODE = 4001;
const WS_AUTHZ_FAILED_CODE = 4003;

export interface ExecutionUpdateMessage {
  type: 'execution_update';
  execution_id: number;
  status: ExecutionStatusType;
  action_name?: string;
  step_summary?: string;
}

export interface UseDashboardWebSocketResult {
  /** Whether WebSocket is currently connected. */
  connected: boolean;
  /** Last received message (for debugging/testing). */
  lastMessage: ExecutionUpdateMessage | null;
  /** Connection error if any. */
  error: string | null;
  /** Whether WebSocket has been authenticated (Story 22.13). */
  isAuthenticated: boolean;
}

export interface UseDashboardWebSocketOptions {
  /** Current list of recent executions to update. */
  recentExecutions: DashboardRecentExecution[];
  /** Callback when executions list is updated. */
  onExecutionsUpdate: (executions: DashboardRecentExecution[]) => void;
  /** Callback when a new error execution is detected (for badge). */
  onNewError?: (executionId: number) => void;
}

/**
 * Hook for real-time dashboard updates (Story 5.2, Task 2.1).
 *
 * Connects to /ws/dashboard and updates the recent executions list
 * when execution_update messages are received.
 */
export function useDashboardWebSocket(
  options: UseDashboardWebSocketOptions
): UseDashboardWebSocketResult {
  const { accessToken } = useAuth();
  const { recentExecutions, onExecutionsUpdate, onNewError } = options;

  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<ExecutionUpdateMessage | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  // Keep recentExecutions in a ref to avoid reconnecting on every update
  const recentExecutionsRef = useRef(recentExecutions);
  useEffect(() => {
    recentExecutionsRef.current = recentExecutions;
  }, [recentExecutions]);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data) as { type: string; user_id?: string; execution_id?: number; status?: ExecutionStatusType; action_name?: string; step_summary?: string };

        // Story 22.13 (AC4): Handle auth_success confirmation
        if (msg.type === 'auth_success') {
          logger.info('Dashboard WebSocket authentication successful');
          if (isMountedRef.current) {
            setIsAuthenticated(true);
          }
          return;
        }

        if (msg.type === 'connection_ack') {
          // Connection acknowledged
          return;
        }

        if (msg.type === 'execution_update' && msg.execution_id && msg.status) {
          const updateMsg: ExecutionUpdateMessage = {
            type: 'execution_update',
            execution_id: msg.execution_id,
            status: msg.status,
            action_name: msg.action_name,
            step_summary: msg.step_summary,
          };

          if (isMountedRef.current) {
            setLastMessage(updateMsg);
          }

          // Update recent executions list (Task 2.2 — insert or replace, code-review)
          const currentList = recentExecutionsRef.current;
          const existingIndex = currentList.findIndex((e) => e.id === updateMsg.execution_id);

          if (existingIndex >= 0) {
            const updated = [...currentList];
            updated[existingIndex] = {
              ...updated[existingIndex],
              status: updateMsg.status,
            };
            onExecutionsUpdate(updated);
          } else {
            // Insert new execution (Story 5.2 Task 2.2: "remplacer ou insérer ligne")
            const newRow: DashboardRecentExecution = {
              id: updateMsg.execution_id,
              action_name: updateMsg.action_name ?? null,
              user_display_name: '—',
              environment: 'dev',
              status: updateMsg.status,
              created_at: new Date().toISOString(),
            };
            const merged = [newRow, ...currentList]
              .sort((a, b) => {
                const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
                const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
                return tb - ta;
              })
              .slice(0, 10);
            onExecutionsUpdate(merged);
          }

          // Notify if new error (Task 3.1 - badge support)
          if (updateMsg.status === 'FAILED' && onNewError) {
            onNewError(updateMsg.execution_id);
          }
        }
      } catch {
        // Parse error: ignore invalid messages (no console in prod — code-review)
        if (import.meta.env.DEV) {
          logger.warn('useDashboardWebSocket: Failed to parse message');
        }
      }
    },
    [onExecutionsUpdate, onNewError]
  );

  useEffect(() => {
    isMountedRef.current = true;

    let closed = false;

    const connect = () => {
      const token = accessToken;
      // Story 22.13 (AC1): No token in URL — auth sent via first message after connection
      const url = `${WS_BASE}/ws/dashboard`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isMountedRef.current) {
          setConnected(true);
          setError(null);
        }
        // Story 22.13 (AC2): Send auth message immediately on connection
        if (token) {
          logger.info('Dashboard WebSocket connection established, sending auth...');
          ws.send(JSON.stringify({ type: 'auth', token }));
        }
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        wsRef.current = null;
        if (isMountedRef.current) {
          setConnected(false);
          setIsAuthenticated(false);
        }
        // Do NOT reconnect on authentication/authorization failures.
        if (event.code === WS_AUTH_FAILED_CODE || event.code === WS_AUTHZ_FAILED_CODE) {
          logger.error('Dashboard WebSocket authentication/authorization failed', { code: event.code, reason: event.reason });
          if (isMountedRef.current) {
            setError(event.code === WS_AUTHZ_FAILED_CODE
              ? 'Accès non autorisé au flux WebSocket'
              : 'Échec d\'authentification WebSocket');
          }
          return;
        }
        if (closed) return;
        // Reconnect after delay
        reconnectTimeoutRef.current = setTimeout(() => {
          if (!closed) connect();
        }, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        if (isMountedRef.current) {
          setError('Erreur de connexion WebSocket dashboard');
        }
      };
    };

    connect();

    return () => {
      closed = true;
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [accessToken, handleMessage]);

  return { connected, lastMessage, error, isAuthenticated };
}
