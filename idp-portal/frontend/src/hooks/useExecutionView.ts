/**
 * useExecutionView - Hook for ExecutionView component data fetching (Story 38.6, SOLID-FE-4).
 *
 * Wraps getExecution + fetchCatalogActionById to remove direct service imports
 * from ExecutionView.tsx. Handles initial load, workflow detail loading, manual refresh,
 * and real-time execution updates from child components.
 */
import { useState, useEffect, useCallback } from 'react';
import { getExecution } from '../services/execution_service';
import { fetchCatalogActionById } from '../services/catalog_service';
import type { ExecutionResponse } from '../types/api';
import type { CatalogActionDetail } from '../services/catalog_service';
import logger from '../services/logger';

export function useExecutionView(executionId: number | null) {
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [actionDetail, setActionDetail] = useState<CatalogActionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Initial load + workflow details
  useEffect(() => {
    if (executionId == null) {
      setExecution(null);
      setActionDetail(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    getExecution(executionId)
      .then(async (data) => {
        if (cancelled) return;
        setExecution(data);
        setError(null);
        // Load workflow definition if this is a workflow execution
        if (data.item_type === 'workflow' && data.action_id) {
          try {
            const { data: actionDetailData } = await fetchCatalogActionById(data.action_id);
            if (!cancelled) setActionDetail(actionDetailData);
          } catch (err) {
            logger.warn('useExecutionView: Failed to load workflow details', {
              action_id: data.action_id,
              error: err instanceof Error ? err.message : String(err),
            });
          }
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [executionId]);

  // Manual refresh
  const refresh = useCallback(async () => {
    if (executionId == null) return;
    try {
      const data = await getExecution(executionId);
      setExecution(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }, [executionId]);

  // Sync execution status from child components (polling/WS updates)
  const handleExecutionUpdate = useCallback((updated: ExecutionResponse) => {
    setExecution((prev) => {
      if (!prev) return updated;
      if (prev.status !== updated.status || prev.completed_at !== updated.completed_at) {
        return { ...prev, status: updated.status, completed_at: updated.completed_at, started_at: updated.started_at ?? prev.started_at };
      }
      return prev;
    });
  }, []);

  return { execution, actionDetail, loading, error, refresh, handleExecutionUpdate };
}
