/**
 * Hook for fetching AAP templates (job or workflow) from an integration.
 * Story 31.5: Provides template list, loading state, fallback mode, and error.
 * Cache in sessionStorage for 2 minutes per (integrationId, resourceType) — only when no search.
 *
 * H2 fix: cleanup flag prevents stale fetch responses from overwriting new data.
 * H3 fix: optional `search` param triggers server-side search via backend.
 */

import { useState, useEffect } from 'react';
import { getAAPTemplates } from '../services/integrations_service';
import type { AAPTemplate } from '../types/api';

const CACHE_DURATION_MS = 2 * 60 * 1000; // 2 minutes

interface CacheEntry {
  templates: AAPTemplate[];
  timestamp: number;
}

function getCacheKey(integrationId: number, resourceType: string): string {
  return `aap_templates_${integrationId}_${resourceType}`;
}

export function useAAPTemplates(
  integrationId: number | null | undefined,
  resourceType: 'job_template' | 'workflow_job',
  search?: string,
) {
  const [templates, setTemplates] = useState<AAPTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [fallback, setFallback] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // H2 fix: cancel flag prevents stale responses from overwriting current state
    let cancelled = false;

    if (!integrationId) {
      setFallback(true);
      setTemplates([]);
      setError(null);
      return;
    }

    // Check sessionStorage cache (only when no search active)
    if (!search) {
      const cacheKey = getCacheKey(integrationId, resourceType);
      try {
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
          const entry: CacheEntry = JSON.parse(cached);
          if (Date.now() - entry.timestamp < CACHE_DURATION_MS) {
            setTemplates(entry.templates);
            setFallback(false);
            setError(null);
            return;
          }
        }
      } catch {
        /* ignore invalid cache */
      }
    }

    setLoading(true);
    setError(null);

    // H3 fix: pass search param to service (server-side filtering)
    getAAPTemplates(integrationId, resourceType, search || undefined)
      .then(({ templates: t, fallback: fb }) => {
        if (cancelled) return;
        setTemplates(t);
        setFallback(fb);
        // Cache only unsearched results
        if (!fb && !search) {
          const cacheKey = getCacheKey(integrationId, resourceType);
          const entry: CacheEntry = { templates: t, timestamp: Date.now() };
          try {
            sessionStorage.setItem(cacheKey, JSON.stringify(entry));
          } catch {
            /* storage full — ignore */
          }
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Erreur chargement templates');
        setFallback(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    // H2 fix: cleanup cancels in-flight requests
    return () => {
      cancelled = true;
    };
  }, [integrationId, resourceType, search]);

  return { templates, loading, fallback, error };
}
