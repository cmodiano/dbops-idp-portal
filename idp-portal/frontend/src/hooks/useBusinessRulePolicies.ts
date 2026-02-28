/**
 * useBusinessRulePolicies — Encapsulation DIP de getBusinessRulePolicies (business_rules_service).
 * Story 54.15 (SOLID-FE-4, AC6): Supprime l'import direct depuis business_rules_service dans BusinessRulePolicySelector.tsx.
 * Pattern: cancelled flag (Story 48.8).
 */

import { useState, useEffect } from 'react';
import { getBusinessRulePolicies } from '../services/business_rules_service';
import type { BusinessRulePolicyListItem } from '../types/api';
import logger from '../services/logger';

export interface UseBusinessRulePoliciesReturn {
  policies: BusinessRulePolicyListItem[];
  loading: boolean;
  error: string | null;
}

/**
 * Charge les politiques de règles métier filtrées par stepType.
 * Si stepType est vide ou null, retourne une liste vide sans appel API.
 */
export function useBusinessRulePolicies(stepType?: string | null): UseBusinessRulePoliciesReturn {
  const [policies, setPolicies] = useState<BusinessRulePolicyListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stepType?.trim()) {
      setPolicies([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    getBusinessRulePolicies({ is_active: true, step_type: stepType.trim() })
      .then((response) => {
        if (!cancelled) setPolicies(response.data ?? []);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur chargement politiques métier';
        logger.error('useBusinessRulePolicies fetch failed', { error: msg });
        setError(msg);
        setPolicies([]);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [stepType]);

  return { policies, loading, error };
}
