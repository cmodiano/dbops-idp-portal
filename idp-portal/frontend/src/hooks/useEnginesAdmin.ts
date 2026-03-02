/**
 * useEnginesAdmin — Encapsulation DIP de fetchEnginesForAdmin/updateEngine (engines_service).
 * Story 54.15 (SOLID-FE-4, AC3/AC4): Supprime les imports directs depuis engines_service
 * dans EnginesAdminTable.tsx et EngineForm.tsx.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchEnginesForAdmin, updateEngine } from '../services/engines_service';
import type { RefEngine } from '../services/reference_service';
import logger from '../services/logger';

export interface UseEnginesAdminReturn {
  engines: RefEngine[];
  loading: boolean;
  error: string | null;
  handleUpdate: (id: number, data: Partial<RefEngine>) => Promise<RefEngine>;
  refresh: () => void;
}

export function useEnginesAdmin(): UseEnginesAdminReturn {
  const [engines, setEngines] = useState<RefEngine[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchEnginesForAdmin(false)
      .then((data) => { if (!cancelled) setEngines(Array.isArray(data) ? data : []); })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur chargement moteurs';
        logger.error('useEnginesAdmin fetch failed', { error: msg });
        setError(msg);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tick]);

  const refresh = useCallback(() => {
    setTick((t) => t + 1);
  }, []);

  const handleUpdate = useCallback(async (id: number, data: Partial<RefEngine>): Promise<RefEngine> => {
    return updateEngine(id, data);
  }, []);

  return { engines, loading, error, handleUpdate, refresh };
}
