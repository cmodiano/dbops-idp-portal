/**
 * useRemediationCatalogActions — Encapsulation DIP de fetchCatalogActions (catalog_service).
 * Story 48.8 (SOLID-FE-4, AC4): Supprime l'import direct de catalog_service dans RemediationRulesEditor.tsx.
 */

import { useState, useEffect } from 'react';
import { fetchCatalogActions } from '../services/catalog_service';
import type { CatalogAction } from '../services/catalog_service';
import logger from '../services/logger';

export interface UseRemediationCatalogActionsReturn {
  catalogActions: CatalogAction[];
  loadingCatalog: boolean;
  catalogError: string | null;
}

export function useRemediationCatalogActions(): UseRemediationCatalogActionsReturn {
  const [catalogActions, setCatalogActions] = useState<CatalogAction[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingCatalog(true);
    setCatalogError(null);
    fetchCatalogActions()
      .then((actions) => {
        if (!cancelled) setCatalogActions(Array.isArray(actions) ? actions : []);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur chargement catalogue';
        logger.error('useRemediationCatalogActions failed', { error: msg });
        setCatalogError(msg);
        setCatalogActions([]);
      })
      .finally(() => { if (!cancelled) setLoadingCatalog(false); });
    return () => { cancelled = true; };
  }, []);

  return { catalogActions, loadingCatalog, catalogError };
}
