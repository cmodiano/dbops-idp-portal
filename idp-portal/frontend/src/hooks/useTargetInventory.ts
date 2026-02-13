/**
 * useTargetInventory - Inventory fetching hook.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.3).
 * Refactored in Story 20.4: pattern resolution extracted to usePatternResolver.
 *
 * Manages inventory data loading, environment caching. Single responsibility: fetch only.
 */

import { useEffect, useRef, useState } from 'react';
import { fetchInventoryItems } from '../services/execution_service';
import type { InventoryItem } from '../types/api';

export type { Target } from '../components/catalog/TargetSelector';

export interface UseTargetInventoryOptions {
  open: boolean;
  actionId?: number;
  currentStep: number;
  parameterFields: Array<{ inventorySource?: 'databases' | 'servers' | 'instances' }>;
  environment: string | null;
  /** Names of servers selected at step 1, used to filter instances/databases (Story 23.6). */
  selectedServerNames?: string[];
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
}: UseTargetInventoryOptions): UseTargetInventoryReturn {
  const [environmentsCache, setEnvironmentsCache] = useState<InventoryItem[] | null>(null);
  const [inventoryData, setInventoryData] = useState<Record<string, InventoryItem[]>>({});
  const [inventoryWarnings, setInventoryWarnings] = useState<Record<string, boolean>>({});
  const [loadingInventory, setLoadingInventory] = useState(false);
  const lastInventoryEnvRef = useRef<string | null>(null);
  // Story 23.6 - Track previous selectedServerNames for cache invalidation
  const lastServerNamesRef = useRef<string[] | null>(null);

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
      lastServerNamesRef.current = selectedServerNames;
      // Story 23.6 - Log cache invalidation for debugging (HIGH-3 fix)
      if (import.meta.env.DEV) {
        const prevNames = JSON.stringify(lastServerNamesRef.current || []);
        const newNames = JSON.stringify(selectedServerNames);
        // Use console for DEV mode (logger not available in hooks without correlation_id context)
        console.debug('[useTargetInventory] Cache invalidation: server_names changed', {
          previous: prevNames,
          current: newNames,
          environment,
        });
      }
    }

    const toFetch: Array<'databases' | 'servers' | 'instances'> = [];
    const cached: Record<string, InventoryItem[]> = {};

    sourcesToLoad.forEach((source) => {
      // Story 23.6 - For instances/databases, also invalidate on server_names change
      const needsRefetch = source === 'instances' || source === 'databases'
        ? envChanged || serverNamesChanged
        : envChanged;
      if (!needsRefetch && inventoryData[source] && inventoryData[source].length > 0) {
        cached[source] = inventoryData[source];
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
          const options = (source === 'instances' || source === 'databases')
            ? { server_names: validServerNames }
            : undefined;
          const items = await fetchInventoryItems(source, environment, options);
          setInventoryWarnings((prev) => ({ ...prev, [source]: false }));
          return [source, items] as const;
        } catch (err: unknown) {
          const error = err as Error & { code?: string; useCache?: boolean; cachedItems?: InventoryItem[] };
          if (error.code === 'INVENTORY_UNAVAILABLE' && error.useCache && error.cachedItems) {
            setInventoryWarnings((prev) => ({ ...prev, [source]: true }));
            return [source, error.cachedItems] as const;
          }
          return [source, []] as const;
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
  }, [open, currentStep, parameterFields, environment, inventoryData, selectedServerNames]);

  return {
    environmentsCache,
    inventoryData,
    inventoryWarnings,
    loadingInventory,
  };
}
