/**
 * usePatternResolver - Pattern resolution hook for target matching.
 * Extracted from useTargetInventory and ExecutionWizard (Story 20.4, Task 1).
 *
 * Resolves targets by glob/simple pattern matching with debounce.
 * Single responsibility: pattern input state + resolution logic.
 */

import { useEffect, useState } from 'react';
import { fetchInventoryTargets } from '../services/execution_service';
import { useDebounce } from './useDebounce';
import { matchGlob } from '../utils/globMatch';

export interface ResolvedTarget {
  name: string;
  environment: string;
}

export interface UsePatternResolverOptions {
  /** Whether the hook is active (e.g. modal open). */
  enabled: boolean;
  /** Current target input mode — resolution only runs when 'pattern'. */
  inputMode: string;
  /** Raw pattern string from user input. */
  pattern: string;
  /** Debounce delay in ms (default 400). */
  debounceMs?: number;
}

export interface UsePatternResolverReturn {
  resolvedTargets: ResolvedTarget[];
  isResolving: boolean;
}

export function usePatternResolver({
  enabled,
  inputMode,
  pattern,
  debounceMs = 400,
}: UsePatternResolverOptions): UsePatternResolverReturn {
  const [resolvedTargets, setResolvedTargets] = useState<ResolvedTarget[]>([]);
  const [isResolving, setIsResolving] = useState(false);

  const debouncedPattern = useDebounce(pattern.trim(), debounceMs);

  useEffect(() => {
    if (!enabled || inputMode !== 'pattern' || !debouncedPattern) {
      setResolvedTargets([]);
      return;
    }

    let cancelled = false;
    setIsResolving(true);

    fetchInventoryTargets()
      .then((targets) => {
        if (cancelled) return;
        const matched = targets.filter((t) => matchGlob(debouncedPattern, t.name));
        setResolvedTargets(matched as ResolvedTarget[]);
      })
      .catch(() => {
        if (!cancelled) setResolvedTargets([]);
      })
      .finally(() => {
        if (!cancelled) setIsResolving(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, inputMode, debouncedPattern]);

  return { resolvedTargets, isResolving };
}
