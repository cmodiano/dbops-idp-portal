/**
 * useTargetInventory - Inventory fetching hook.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.3).
 * Refactored in Story 20.4: pattern resolution extracted to usePatternResolver.
 *
 * Manages inventory data loading, environment caching. Single responsibility: fetch only.
 */

import { useEffect, useRef, useState } from 'react';
import { fetchInventoryItems, fetchTargetsPaginated } from '../services/execution_service';
import type { InventoryItem } from '../types/api';
import logger from '../services/logger';

export type { Target } from '../components/catalog/TargetSelector';
export type { InventoryTarget } from '../services/execution_service';

export interface UseTargetInventoryOptions {
  open: boolean;
  actionId?: number;
  currentStep: number;
  parameterFields: Array<{ inventorySource?: 'databases' | 'servers' | 'instances' }>;
  environment: string | null;
  /** Names of servers selected at step 1, used to filter instances/databases (Story 23.6). */
  selectedServerNames?: string[];
  /** Story 37.3 - Engine type of the action to filter inventory by technology. */
  engineType?: string | null;
}

export interface UseTargetInventoryReturn {
  environmentsCache: InventoryItem[] | null;
  inventoryData: Record<string, InventoryItem[]>;
  inventoryWarnings: Record<string, boolean>;
  loadingInventory: boolean;
}

export function useTargetInventory({
  open,
  currentStep,
  parameterFields,
  environment,
  selectedServerNames = [],
  engineType = null,  // Story 37.3
}: UseTargetInventoryOptions): UseTargetInventoryReturn {
  const [environmentsCache, setEnvironmentsCache] = useState<InventoryItem[] | null>(null);
  const [inventoryData, setInventoryData] = useState<Record<string, InventoryItem[]>>({});
  const [inventoryWarnings, setInventoryWarnings] = useState<Record<string, boolean>>({});
  const [loadingInventory, setLoadingInventory] = useState(false);
  const lastInventoryEnvRef = useRef<string | null>(null);
  // Story 23.6 - Track previous selectedServerNames for cache invalidation
  const lastServerNamesRef = useRef<string[] | null>(null);
  // Story 37.3 - Track previous engineType for cache invalidation
  const lastEngineTypeRef = useRef<string | null>(null);
  // Story 30.4 - Ref to avoid inventoryData in useEffect deps (prevents infinite loop)
  const inventoryDataRef = useRef(inventoryData);
  inventoryDataRef.current = inventoryData;

  // Load environments (cached, loaded once)
  useEffect(() => {
    if (!open || environmentsCache !== null) return;

    fetchInventoryItems('environments')
      .then((items) => {
        setEnvironmentsCache(items);
        setInventoryWarnings((prev) => ({ ...prev, environments: false }));
      })
      .catch((err: Error & { code?: string; useCache?: boolean; cachedItems?: InventoryItem[] }) => {
        if (err.code === 'INVENTORY_UNAVAILABLE' && err.useCache && err.cachedItems) {
          setEnvironmentsCache(err.cachedItems);
          setInventoryWarnings((prev) => ({ ...prev, environments: true }));
        } else {
          setEnvironmentsCache(null);
        }
      });
  }, [open, environmentsCache]);

  // Load inventory data for fields that need it (only on step 2 with environment selected)
  useEffect(() => {
    if (!open || currentStep !== 1 || !environment) return;

    const sourcesToLoad = new Set<'databases' | 'servers' | 'instances'>();
    parameterFields.forEach((field) => {
      if (field.inventorySource) {
        sourcesToLoad.add(field.inventorySource);
      }
    });

    if (sourcesToLoad.size === 0) return;

    const envChanged = lastInventoryEnvRef.current !== environment;
    if (envChanged) {
      lastInventoryEnvRef.current = environment;
    }

    // Story 23.6 - Invalidate cache if selected servers change
    const serverNamesChanged = JSON.stringify(lastServerNamesRef.current) !== JSON.stringify(selectedServerNames);
    if (serverNamesChanged) {
      const previousServerNames = lastServerNamesRef.current;
      lastServerNamesRef.current = selectedServerNames;
      // Story 23.6 - Log cache invalidation for debugging (HIGH-3 fix)
      if (import.meta.env.DEV) {
        const prevNames = JSON.stringify(previousServerNames || []);
        const newNames = JSON.stringify(selectedServerNames);
        // Use logger for DEV mode debugging
        logger.debug('[useTargetInventory] Cache invalidation: server_names changed', {
          previous: prevNames,
          current: newNames,
          environment,
        });
      }
    }

    // Story 37.3 - Invalidate cache if engine_type changes
    const engineTypeChanged = lastEngineTypeRef.current !== engineType;
    if (engineTypeChanged) {
      const previousEngineType = lastEngineTypeRef.current;
      lastEngineTypeRef.current = engineType;
      if (import.meta.env.DEV) {
        logger.debug('[useTargetInventory] Cache invalidation: engine_type changed', {
          previous: previousEngineType,
          current: engineType,
          environment,
        });
      }
    }

    const toFetch: Array<'databases' | 'servers' | 'instances'> = [];
    const cached: Record<string, InventoryItem[]> = {};

    sourcesToLoad.forEach((source) => {
      // Story 23.6 - For instances/databases, also invalidate on server_names change
      // Story 37.3 - engine_type change invalidates all inventory types (servers too)
      const needsRefetch = envChanged || serverNamesChanged || engineTypeChanged;
      const currentData = inventoryDataRef.current;
      if (!needsRefetch && currentData[source] && currentData[source].length > 0) {
        cached[source] = currentData[source];
      } else {
        toFetch.push(source);
      }
    });

    if (toFetch.length === 0) return;

    setLoadingInventory(true);
    Promise.all(
      toFetch.map(async (source) => {
        try {
          // Story 23.6 - Pass server_names for instances/databases
          // MEDIUM-1 fix: Validate selectedServerNames format before API call
          const validServerNames = selectedServerNames.filter(name => typeof name === 'string' && name.trim().length > 0);
          // Story 37.3 - Pass engine_type for all inventory types
          const engineTypeOption = engineType ? { engine_type: engineType } : {};
          const options = (source === 'instances' || source === 'databases')
            ? { server_names: validServerNames, ...engineTypeOption }
            : (Object.keys(engineTypeOption).length > 0 ? engineTypeOption : undefined);
          const items = await fetchInventoryItems(source, environment, options);
          setInventoryWarnings((prev) => ({ ...prev, [source]: false }));
          return [source, items] as const;
        } catch (err: unknown) {
          const error = err as Error & { code?: string; useCache?: boolean; cachedItems?: InventoryItem[] };
          if (error.code === 'INVENTORY_UNAVAILABLE' && error.useCache && error.cachedItems) {
            setInventoryWarnings((prev) => ({ ...prev, [source]: true }));
            return [source, error.cachedItems] as const;
          }
          return [source, [] as InventoryItem[]] as const;
        }
      })
    )
      .then((results) => {
        const data: Record<string, InventoryItem[]> = { ...cached };
        results.forEach(([source, items]) => {
          data[source] = items;
        });
        setInventoryData(data);
      })
      .finally(() => setLoadingInventory(false));
  }, [open, currentStep, parameterFields, environment, selectedServerNames, engineType]);

  return {
    environmentsCache,
    inventoryData,
    inventoryWarnings,
    loadingInventory,
  };
}

/**
 * Story 71.1, AC5: Hook DIP léger pour TargetSelector.
 * Encapsule fetchTargetsPaginated() pour supprimer l'import direct de execution_service.
 */
export function useTargetsPaginated(search?: string) {
  const [targets, setTargets] = useState<import('../services/execution_service').InventoryTarget[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTargetsPaginated(search || undefined)
      .then((response) => {
        if (!cancelled) setTargets(response?.items ?? []);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur lors du chargement des cibles');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [search]);

  return { targets, loading, error };
}
