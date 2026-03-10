/**
 * useWebSocket - Real-time execution timeline via WebSocket (Story 4.6, Task 2.1-2.3).
 *
 * Connects to /ws/executions/{id}, receives step_update, execution_complete, execution_failed.
 * On reconnect: re-syncs via GET /api/v1/executions/{id} (AC3).
 *
 * Story 22.13: Token sent in first message after connection (not in URL query string).
 * Sequence: connect → send {type:"auth", token} → receive {type:"auth_success"} → business messages.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getExecution, getExecutionSteps } from '../services/execution_service';
import type { ExecutionResponse } from '../types/api';
import type { ExecutionStepResponse } from '../types/api';
import logger from '../services/logger';

const RECONNECT_DELAY_MS = 2000;
const WS_PROTOCOL = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE = typeof window !== 'undefined' ? `${WS_PROTOCOL}//${window.location.host}` : 'ws://localhost';

/** WebSocket close code for authentication failure — do not reconnect. */
const WS_AUTH_FAILED_CODE = 4001;

export interface UseWebSocketResult {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  loading: boolean;
  error: string | null;
  lastMessage: { type: string; execution_id?: number; data?: unknown } | null;
  isAuthenticated: boolean;
}

export function useWebSocket(executionId: number | null): UseWebSocketResult {
  const { accessToken } = useAuth();
  const [steps, setSteps] = useState<ExecutionStepResponse[]>([]);
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<UseWebSocketResult['lastMessage']>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // MEDIUM-2 FIX: Use ref to track mounted state and prevent setState after unmount
  const isMountedRef = useRef(true);

  const reSyncState = useCallback(async (id: number) => {
    try {
      const [execData, stepsData] = await Promise.all([
        getExecution(id),
        getExecutionSteps(id),
      ]);
      // MEDIUM-2 FIX: Check mounted before setState to prevent memory leak
      if (isMountedRef.current) {
        setExecution(execData);
        setSteps(stepsData);
      }
    } catch (e) {
      if (isMountedRef.current) {
        setError(e instanceof Error ? e.message : 'Erreur de synchronisation');
      }
    }
  }, []);

  useEffect(() => {
    // MEDIUM-2 FIX: Reset mounted state on effect run
    isMountedRef.current = true;

    if (executionId == null) {
      queueMicrotask(() => {
        setLoading(false);
        setSteps([]);
        setExecution(null);
        setError(null);
        setIsAuthenticated(false);
      });
      return;
    }

    let closed = false;

    const connect = () => {
      const token = accessToken;
      // Story 22.13 (AC1): No token in URL — auth sent via first message after connection
      const url = `${WS_BASE}/ws/executions/${executionId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setError(null);
        // Story 22.13 (AC2): Send auth message immediately on connection
        if (token) {
          logger.info('WebSocket connection established, sending auth...');
          ws.send(JSON.stringify({ type: 'auth', token }));
        }
        // Re-sync full state on connect (AC3: reconnect → GET /executions/{id})
        reSyncState(executionId);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as {
            type: string;
            execution_id?: number;
            user_id?: string;
            data?: { step_order?: number; step_name?: string; status?: string; step_type?: string; started_at?: string | null; completed_at?: string | null }; // Story 58.3: step_type ajouté
            status?: string;
            error_message?: string;
          };

          // Story 22.13 (AC4): Handle auth_success confirmation
          if (msg.type === 'auth_success') {
            logger.info('WebSocket authentication successful');
            if (isMountedRef.current) {
              setIsAuthenticated(true);
            }
            // Story 58.3 AC#3: re-sync sur auth_success — couvre les steps créés entre onopen et auth
            reSyncState(executionId);
            return;
          }

          setLastMessage(msg);

          if (msg.type === 'step_update' && msg.data) {
            const d = msg.data;
            setSteps((prev) => {
              const idx = prev.findIndex((s) => s.step_order === d.step_order);
              const base = idx >= 0 ? prev[idx] : null;
              const updated: ExecutionStepResponse = {
                id: base?.id ?? 0,
                execution_id: executionId!,
                step_order: d.step_order ?? base?.step_order ?? 0,
                step_name: d.step_name ?? base?.step_name ?? '',
                step_type: (d.step_type as ExecutionStepResponse['step_type']) ?? base?.step_type ?? 'platform', // Story 58.3: lire step_type depuis le message WS en priorité
                status: (d.status as ExecutionStepResponse['status']) ?? base?.status ?? 'PENDING',
                started_at: d.started_at ?? base?.started_at ?? null,
                completed_at: d.completed_at ?? base?.completed_at ?? null,
                output: base?.output ?? null,
                platform_job_id: base?.platform_job_id ?? null,
                error_message: base?.error_message ?? null,
              };
              if (idx >= 0) {
                const next = [...prev];
                next[idx] = updated;
                return next;
              }
              const next = [...prev, updated];
              next.sort((a, b) => a.step_order - b.step_order);
              return next;
            });
          } else if (msg.type === 'execution_complete') {
            setExecution((e) => (e ? { ...e, status: 'COMPLETED' } : null));
            ws.close();
          } else if (msg.type === 'execution_failed') {
            setExecution((e) => (e ? { ...e, status: 'FAILED' } : null));
            setError(msg.error_message ?? 'Exécution en échec');
            ws.close();
          }
        } catch (parseError) {
          // HIGH-3 FIX: Log parse errors instead of silently ignoring
          logger.warn('useWebSocket: Failed to parse message', { error: parseError instanceof Error ? parseError.message : String(parseError) });
        }
      };

      ws.onclose = (event) => {
        wsRef.current = null;
        if (isMountedRef.current) {
          setIsAuthenticated(false);
        }
        // Story 22.13 (AC5): Do NOT reconnect on auth failure (code 4001)
        if (event.code === WS_AUTH_FAILED_CODE) {
          logger.error('WebSocket authentication failed - invalid token', { code: event.code, reason: event.reason });
          if (isMountedRef.current) {
            setError('Échec d\'authentification WebSocket');
          }
          return;
        }
        if (closed) return;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        if (isMountedRef.current) {
          setError('Erreur de connexion WebSocket');
        }
      };
    };

    queueMicrotask(() => {
      setLoading(true);
      reSyncState(executionId).finally(() => {
        if (isMountedRef.current) setLoading(false);
      });
      connect();
    });

    return () => {
      closed = true;
      isMountedRef.current = false; // MEDIUM-2 FIX: Mark as unmounted
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [executionId, accessToken, reSyncState]);

  return { steps, execution, loading, error, lastMessage, isAuthenticated };
}
