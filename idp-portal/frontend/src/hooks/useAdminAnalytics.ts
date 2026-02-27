/**
 * useAdminAnalytics — Encapsulation DIP de fetchAdminAnalytics (admin_service).
 * Story 48.8 (SOLID-FE-4, AC2): Supprime l'import direct d'admin_service dans AdminAnalyticsDashboard.tsx.
 * Code review: cancelled flag dans le scope useEffect pour éviter setState sur composant démonté.
 */

import { useState, useEffect } from 'react';
import { fetchAdminAnalytics } from '../services/admin_service';
import type { AdminAnalytics } from '../types/api';
import logger from '../services/logger';

export interface UseAdminAnalyticsReturn {
  data: AdminAnalytics | null;
  loading: boolean;
  error: string | null;
}

export function useAdminAnalytics(days: number): UseAdminAnalyticsReturn {
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAdminAnalytics(days)
      .then((analytics) => {
        if (!cancelled) setData(analytics);
      })
      .catch((err) => {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : 'Erreur de chargement des métriques';
          setError(msg);
          logger.error('useAdminAnalytics fetch failed', { days, error: msg });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  return { data, loading, error };
}
