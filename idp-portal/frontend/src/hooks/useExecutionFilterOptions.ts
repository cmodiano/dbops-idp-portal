/**
 * useExecutionFilterOptions - Hook for loading filter option data (Story 38.6, SOLID-FE-4).
 *
 * Wraps fetchExecutionTags + fetchCatalogActions to remove direct service imports
 * from ExecutionsFiltersPanel.tsx.
 */
import { useState, useEffect } from 'react';
import { fetchExecutionTags } from '../services/execution_service';
import { fetchCatalogActions } from '../services/catalog_service';
import type { CatalogAction } from '../services/catalog_service';

export function useExecutionFilterOptions() {
  const [tags, setTags] = useState<string[]>([]);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [actions, setActions] = useState<CatalogAction[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);

  // Load tags and actions on mount
  useEffect(() => {
    let cancelled = false;
    setTagsLoading(true);
    setActionsLoading(true);
    Promise.all([
      fetchExecutionTags().catch(() => [] as string[]),
      fetchCatalogActions().catch(() => [] as CatalogAction[]),
    ]).then(([tagsData, actionsData]) => {
      if (!cancelled) {
        setTags(tagsData);
        setActions(actionsData);
      }
    }).finally(() => {
      if (!cancelled) {
        setTagsLoading(false);
        setActionsLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  return { tags, tagsLoading, actions, actionsLoading };
}
