/**
 * useIntegrationTypes — Fetch integration type catalogue from backend (Story 24.2 AC1).
 * SessionStorage cache with 1h TTL to reduce network calls.
 * Falls back to FALLBACK_INTEGRATION_TYPES if API fails.
 */

import { useEffect, useState } from 'react';
import { getIntegrationTypes } from '../services/integrations_service';
import type { IntegrationTypeCatalogue } from '../types/api';
import { FALLBACK_INTEGRATION_TYPES } from '../types/api';

const CACHE_KEY = 'integration_types_cache';
const CACHE_TTL = 3600000; // 1 hour

interface CachedData {
  data: IntegrationTypeCatalogue[];
  timestamp: number;
}

function getCachedTypes(): IntegrationTypeCatalogue[] | null {
  try {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (!cached) return null;

    const parsed: CachedData = JSON.parse(cached);
    if (!parsed.data || !Array.isArray(parsed.data) || typeof parsed.timestamp !== 'number') {
      sessionStorage.removeItem(CACHE_KEY);
      return null;
    }

    if (Date.now() - parsed.timestamp > CACHE_TTL) {
      sessionStorage.removeItem(CACHE_KEY);
      return null;
    }

    return parsed.data;
  } catch {
    sessionStorage.removeItem(CACHE_KEY);
    return null;
  }
}

function setCachedTypes(data: IntegrationTypeCatalogue[]): void {
  try {
    sessionStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ data, timestamp: Date.now() } satisfies CachedData),
    );
  } catch {
    // Ignore storage errors (quota exceeded, etc.)
  }
}

export interface UseIntegrationTypesReturn {
  types: IntegrationTypeCatalogue[];
  loading: boolean;
  error: string | null;
  isFallback: boolean;
}

export function useIntegrationTypes(): UseIntegrationTypesReturn {
  const [types, setTypes] = useState<IntegrationTypeCatalogue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFallback, setIsFallback] = useState(false);

  useEffect(() => {
    const cached = getCachedTypes();
    if (cached) {
      setTypes(cached);
      setLoading(false);
      return;
    }

    let cancelled = false;

    // LOW-3 fix: Simple retry with Promise chain (1 retry only for stability)
    const fetchWithRetry = getIntegrationTypes()
      .catch(() => {
        // Retry once after 1s
        return new Promise<IntegrationTypeCatalogue[]>((resolve, reject) => {
          setTimeout(() => {
            getIntegrationTypes().then(resolve).catch(reject);
          }, 1000);
        });
      });

    fetchWithRetry
      .then((data) => {
        if (cancelled) return;
        setTypes(data);
        setCachedTypes(data);
        setError(null);
        setIsFallback(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur inconnue';
        setError(msg);
        setTypes(FALLBACK_INTEGRATION_TYPES);
        setIsFallback(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { types, loading, error, isFallback };
}
