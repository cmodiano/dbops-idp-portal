/**
 * useTargetInventory - Inventory and target fetching hook.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.3).
 *
 * Manages inventory data loading, environment caching, and RBAC-filtered targets.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchInventoryItems, fetchInventoryTargets } from '../services/execution_service';
import type { InventoryItem } from '../types/api';
import { useDebounce } from './useDebounce';
import { matchGlob } from '../utils/globMatch';

export type { Target } from '../components/catalog/TargetSelector';

export interface UseTargetInventoryOptions {
  open: boolean;
  actionId?: number;
  currentStep: number;
  parameterFields: Array<{ inventorySource?: 'databases' | 'servers' }>;
  environment: string | null;
}

export interface UseTargetInventoryReturn {
  environmentsCache: InventoryItem[] | null;
  inventoryData: Record<string, InventoryItem[]>;
  inventoryWarnings: Record<string, boolean>;
  loadingInventory: boolean;
  resolvedPatternTargets: Array<{ name: string; environment: string }>;
  patternResolving: boolean;
  resolvePattern: (pattern: string, inputMode: string) => void;
}

export function useTargetInventory({
  open,
  currentStep,
  parameterFields,
  environment,
}: UseTargetInventoryOptions): UseTargetInventoryReturn {
  const [environmentsCache, setEnvironmentsCache] = useState<InventoryItem[] | null>(null);
  const [inventoryData, setInventoryData] = useState<Record<string, InventoryItem[]>>({});
  const [inventoryWarnings, setInventoryWarnings] = useState<Record<string, boolean>>({});
  const [loadingInventory, setLoadingInventory] = useState(false);
  const [resolvedPatternTargets, setResolvedPatternTargets] = useState<Array<{ name: string; environment: string }>>([]);
  const [patternResolving, setPatternResolving] = useState(false);
  const [patternInput, setPatternInput] = useState('');
  const [patternMode, setPatternMode] = useState('');
  const lastInventoryEnvRef = useRef<string | null>(null);

  const debouncedPattern = useDebounce(patternInput, 400);

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

    const sourcesToLoad = new Set<'databases' | 'servers'>();
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

    const toFetch: Array<'databases' | 'servers'> = [];
    const cached: Record<string, InventoryItem[]> = {};

    sourcesToLoad.forEach((source) => {
      if (!envChanged && inventoryData[source] && inventoryData[source].length > 0) {
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
          const items = await fetchInventoryItems(source, environment);
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
  }, [open, currentStep, parameterFields, environment, inventoryData]);

  // Resolve pattern targets (debounced)
  useEffect(() => {
    if (!open || patternMode !== 'pattern' || !debouncedPattern) {
      setResolvedPatternTargets([]);
      return;
    }
    let cancelled = false;
    setPatternResolving(true);
    fetchInventoryTargets()
      .then((targets) => {
        if (cancelled) return;
        const matched = targets.filter((t) => matchGlob(debouncedPattern, t.name));
        setResolvedPatternTargets(matched as Array<{ name: string; environment: string }>);
      })
      .catch(() => {
        if (!cancelled) setResolvedPatternTargets([]);
      })
      .finally(() => {
        if (!cancelled) setPatternResolving(false);
      });
    return () => { cancelled = true; };
  }, [open, patternMode, debouncedPattern]);

  const resolvePattern = useCallback((pattern: string, inputMode: string) => {
    setPatternInput(pattern.trim());
    setPatternMode(inputMode);
  }, []);

  return {
    environmentsCache,
    inventoryData,
    inventoryWarnings,
    loadingInventory,
    resolvedPatternTargets,
    patternResolving,
    resolvePattern,
  };
}
