/**
 * useActorExecutionSync - Real-time status updates for the current user's active executions.
 *
 * Story 36.2: Opens a WebSocket per active execution ID.
 * On execution_complete / execution_failed → calls onStatusUpdate() and closes the WS.
 * On WS error (non-4001) → activates a fallback polling every 2000 ms.
 * Auth sent in first message (not in URL — Story 22.13).
 */

import { useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getExecution } from '../services/execution_service';
import type { ExecutionResponse } from '../types/api';

const TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'];
const FALLBACK_POLL_INTERVAL_MS = 2000;
const WS_AUTH_FAILED_CODE = 4001;

function buildWsUrl(path: string): string {
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost';
  return `${protocol}//${host}${path}`;
}

/**
 * Subscribes to WebSocket updates for the given execution IDs.
 * Calls onStatusUpdate when execution_complete or execution_failed is received.
 * Falls back to polling on WS error (except auth failure code 4001).
 */
export function useActorExecutionSync(
  executionIds: number[],
  onStatusUpdate: (id: number, status: string, data?: Partial<ExecutionResponse>) => void,
): void {
  const { accessToken } = useAuth();
  const wsMap = useRef<Map<number, WebSocket>>(new Map());
  const pollMap = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map());
  const isMountedRef = useRef(true);

  const startFallbackPolling = useCallback((id: number) => {
    if (pollMap.current.has(id)) return;
    const intervalId = setInterval(async () => {
      if (!isMountedRef.current) return;
      try {
        const execution = await getExecution(id);
        if (!isMountedRef.current) return;
        onStatusUpdate(id, execution.status, execution);
        if (TERMINAL_STATUSES.includes(execution.status)) {
          clearInterval(intervalId);
          pollMap.current.delete(id);
        }
      } catch {
        // silencieux — retry au prochain tick
      }
    }, FALLBACK_POLL_INTERVAL_MS);
    pollMap.current.set(id, intervalId);
  }, [onStatusUpdate]);

  const openWs = useCallback((id: number) => {
    const ws = new WebSocket(buildWsUrl(`/ws/executions/${id}`));
    wsMap.current.set(id, ws);

    ws.onopen = () => {
      const token = accessToken;
      if (token) ws.send(JSON.stringify({ type: 'auth', token }));
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const msg = JSON.parse(event.data as string) as {
          type: string;
          status?: string;
          error_message?: string;
          [key: string]: unknown;
        };
        if (msg.type === 'execution_complete') {
          // Delete from map BEFORE close so onclose knows this is an intentional terminal close
          wsMap.current.delete(id);
          onStatusUpdate(id, msg.status ?? 'COMPLETED', msg as Partial<ExecutionResponse>);
          ws.close();
        } else if (msg.type === 'execution_failed') {
          // Delete from map BEFORE close so onclose knows this is an intentional terminal close
          wsMap.current.delete(id);
          onStatusUpdate(id, 'FAILED', { status: 'FAILED', error_message: msg.error_message } as Partial<ExecutionResponse>);
          ws.close();
        }
      } catch {
        // JSON invalide ignoré
      }
    };

    ws.onclose = (event) => {
      // Check BEFORE deleting: if id was already removed from wsMap (intentional terminal close
      // from onmessage or explicit cleanup), skip fallback polling to avoid spurious API calls.
      const wasTracked = wsMap.current.has(id);
      wsMap.current.delete(id);
      // 4001 = auth failure → ne pas poller
      if (event.code === WS_AUTH_FAILED_CODE) return;
      // Intentional close (terminal status or explicit cleanup) → no fallback needed
      if (!wasTracked) return;
      if (isMountedRef.current) startFallbackPolling(id);
    };

    ws.onerror = () => {
      // onclose gérera le fallback
      ws.close();
    };
  }, [accessToken, onStatusUpdate, startFallbackPolling]);

  // Synchronise les connexions WS avec executionIds
  useEffect(() => {
    // Ouvrir WS pour les nouveaux IDs
    for (const id of executionIds) {
      if (!wsMap.current.has(id) && !pollMap.current.has(id)) {
        openWs(id);
      }
    }

    // Fermer WS/polling pour les IDs disparus
    for (const [id, ws] of wsMap.current) {
      if (!executionIds.includes(id)) {
        // Delete BEFORE close so onclose skips fallback polling for this intentional cleanup
        wsMap.current.delete(id);
        ws.close();
      }
    }
    for (const [id, intervalId] of pollMap.current) {
      if (!executionIds.includes(id)) {
        clearInterval(intervalId);
        pollMap.current.delete(id);
      }
    }
  }, [executionIds, openWs]);

  // Cleanup total au démontage
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      wsMap.current.forEach((ws) => ws.close());
      wsMap.current.clear();
      pollMap.current.forEach((intervalId) => clearInterval(intervalId));
      pollMap.current.clear();
    };
  }, []);
}
