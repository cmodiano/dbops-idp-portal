/**
 * useInventorySchema — Fetch inventory column schema per entity type.
 * Story 62.5: Loads available columns from GET /api/v1/inventory/schema/ with sessionStorage cache.
 */

import { useEffect, useState } from 'react';
import { fetchInventorySchema } from '../services/execution_service';
import type { InventorySchema } from '../types/api';

const CACHE_KEY = 'inventory_schema_cache';
const CACHE_DURATION_MS = 5 * 60 * 1000; // 5 minutes

export interface UseInventorySchemaReturn {
  schema: InventorySchema | null;
  loading: boolean;
  error: string | null;
}

export function useInventorySchema(): UseInventorySchemaReturn {
  const [schema, setSchema] = useState<InventorySchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Check sessionStorage cache first
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached) as {
          data: InventorySchema;
          timestamp: number;
        };
        if (Date.now() - timestamp < CACHE_DURATION_MS && data !== null && typeof data === 'object') {
          setSchema(data);
          setLoading(false);
          return;
        }
      }
    } catch {
      /* ignore invalid cache */
    }

    async function load() {
      try {
        const result = await fetchInventorySchema();
        if (!cancelled) {
          setSchema(result);
          setError(null);
          sessionStorage.setItem(
            CACHE_KEY,
            JSON.stringify({ data: result, timestamp: Date.now() }),
          );
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur chargement schéma inventaire');
          setSchema(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { schema, loading, error };
}
