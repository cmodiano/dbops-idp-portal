/**
 * useScheduledExecutions - Hook for scheduled executions data (Story 38.6, SOLID-FE-4).
 *
 * Wraps listScheduledExecutions + toggleRecurringPattern to remove direct service imports
 * from CalendarPage.tsx.
 */
import { useState, useCallback, useRef } from 'react';
import { listScheduledExecutions, toggleRecurringPattern } from '../services/scheduled_execution_service';
import type { ScheduledExecutionListItem, ScheduledExecutionFilters } from '../types/api';
import logger from '../services/logger';

export function useScheduledExecutions() {
  const [executions, setExecutions] = useState<ScheduledExecutionListItem[]>([]);
  const [availableActions, setAvailableActions] = useState<{ action_id: number; action_name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingPatternId, setTogglingPatternId] = useState<number | null>(null);
  const initialLoadDone = useRef(false);

  const fetchExecutions = useCallback(async (apiFilters: ScheduledExecutionFilters) => {
    if (!initialLoadDone.current) {
      setLoading(true);
    }
    setError(null);
    try {
      const response = await listScheduledExecutions(apiFilters, 100, 0);
      setExecutions(response.data);
      if (response.available_actions) {
        setAvailableActions(response.available_actions);
      }
    } catch (err) {
      setError('Erreur lors du chargement des exécutions planifiées');
      if (import.meta.env.DEV) {
        logger.error('Failed to fetch scheduled executions', { error: err instanceof Error ? err.message : String(err) });
      }
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, []);

  const toggleRecurrence = useCallback(async (id: number, newState: boolean) => {
    setTogglingPatternId(id);
    try {
      await toggleRecurringPattern(id, newState);
      return { success: true as const };
    } catch (err: unknown) {
      return { success: false as const, error: err instanceof Error ? err.message : 'Une erreur est survenue' };
    } finally {
      setTogglingPatternId(null);
    }
  }, []);

  return { executions, availableActions, loading, error, togglingPatternId, fetchExecutions, toggleRecurrence };
}
