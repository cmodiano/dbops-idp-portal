/**
 * useBusinessRulePoliciesAdmin — Encapsulation DIP des 5 opérations CRUD business_rules_service.
 * Story 71.1, AC3/AC4: Supprime les imports directs dans BusinessRulesPolicyPanel et EvaluationStepConfig.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getBusinessRulePolicies,
  getBusinessRulePolicy,
  createBusinessRulePolicy,
  updateBusinessRulePolicy,
  deleteBusinessRulePolicy,
} from '../services/business_rules_service';
import type {
  BusinessRulePolicyListItem,
  BusinessRulePolicyDetail,
  BusinessRulePolicyPayload,
  BusinessRulePolicyFilters,
} from '../types/api';
import logger from '../services/logger';

export function useBusinessRulePoliciesAdmin(filters?: BusinessRulePolicyFilters) {
  const [policies, setPolicies] = useState<BusinessRulePolicyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const filtersKey = JSON.stringify(filters);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getBusinessRulePolicies(filtersRef.current);
      setPolicies(response.data ?? []);
    } catch (err) {
      logger.error('business_rule_policies_load_error', { error: String(err) });
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  const getOne = useCallback(async (id: number): Promise<BusinessRulePolicyDetail> => {
    return getBusinessRulePolicy(id);
  }, []);

  const create = useCallback(async (payload: BusinessRulePolicyPayload): Promise<BusinessRulePolicyDetail> => {
    const result = await createBusinessRulePolicy(payload);
    await fetchPolicies();
    return result;
  }, [fetchPolicies]);

  const update = useCallback(async (id: number, payload: Partial<BusinessRulePolicyPayload>): Promise<BusinessRulePolicyDetail> => {
    const result = await updateBusinessRulePolicy(id, payload);
    await fetchPolicies();
    return result;
  }, [fetchPolicies]);

  const remove = useCallback(async (id: number): Promise<void> => {
    await deleteBusinessRulePolicy(id);
    await fetchPolicies();
  }, [fetchPolicies]);

  return {
    policies,
    loading,
    error,
    fetchPolicies,
    getOne,
    create,
    update,
    remove,
  };
}

/**
 * Lightweight hook for EvaluationStepConfig: load active policies only.
 * Replaces direct import of getBusinessRulePolicies in EvaluationStepConfig.tsx.
 */
export function useBusinessRulePoliciesActive() {
  const [policies, setPolicies] = useState<BusinessRulePolicyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getBusinessRulePolicies({ is_active: true })
      .then((response) => {
        if (!cancelled) setPolicies(response.data ?? []);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur chargement politiques';
        logger.error('useBusinessRulePoliciesActive fetch failed', { error: msg });
        setError(msg);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return { policies, loading, error };
}
