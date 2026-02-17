/**
 * useExecutionDetail - Hook for managing execution detail drawer state
 *
 * Story 26.4 - AC2: Extracted from ExecutionsPage.tsx to encapsulate drawer logic.
 * Handles loading execution details, steps, and action metadata for the drawer.
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router';
import type {
  ExecutionResponse,
  ExecutionStepResponse,
} from '../types/api';
import type { CatalogActionDetail } from '../services/catalog_service';
import {
  getExecution,
  getExecutionSteps,
} from '../services/execution_service';
import { fetchCatalogActionById } from '../services/catalog_service';

export interface UseExecutionDetailReturn {
  drawerOpen: boolean;
  selectedExecution: ExecutionResponse | null;
  selectedSteps: ExecutionStepResponse[];
  selectedActionDetail: CatalogActionDetail | null;
  loading: boolean;
  error: string | null;
  openExecution: (record: ExecutionResponse) => Promise<void>;
  closeDrawer: () => void;
}

export const useExecutionDetail = (): UseExecutionDetailReturn => {
  const params = useParams<{ id?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<ExecutionStepResponse[]>([]);
  const [selectedActionDetail, setSelectedActionDetail] = useState<CatalogActionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadExecutionDetail = useCallback(async (id: number) => {
    setDrawerOpen(true);
    setLoading(true);
    setError(null);
    setSelectedExecution(null);
    setSelectedSteps([]);
    setSelectedActionDetail(null);

    try {
      const [execution, steps] = await Promise.all([
        getExecution(id),
        getExecutionSteps(id),
      ]);
      setSelectedExecution(execution);
      setSelectedSteps(steps);
      if (execution.item_type === 'workflow' && execution.action_id) {
        try {
          const { data } = await fetchCatalogActionById(execution.action_id);
          setSelectedActionDetail(data);
        } catch {
          // Fallback: show timeline if action detail fails
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erreur de chargement du détail';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const openExecution = async (record: ExecutionResponse) => {
    await loadExecutionDetail(record.id);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setError(null);
    if (params.id) {
      navigate('/executions', { replace: true });
    } else if (searchParams.has('open')) {
      searchParams.delete('open');
      setSearchParams(searchParams, { replace: true });
    }
  };

  // Open drawer from URL: /executions/:id or /executions?open=79
  const openExecutionId = params.id || searchParams.get('open');
  useEffect(() => {
    if (!openExecutionId) return;
    const id = parseInt(openExecutionId, 10);
    if (isNaN(id)) return;
    loadExecutionDetail(id);
  }, [openExecutionId, loadExecutionDetail]);

  return {
    drawerOpen,
    selectedExecution,
    selectedSteps,
    selectedActionDetail,
    loading,
    error,
    openExecution,
    closeDrawer,
  };
};
