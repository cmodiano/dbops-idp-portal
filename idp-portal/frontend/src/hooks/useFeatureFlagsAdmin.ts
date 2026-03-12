/**
 * useFeatureFlagsAdmin — Encapsulation DIP de fetchFeatureFlags et updateFeatureFlag.
 * Story 71.1, AC2: Supprime l'import direct depuis feature_flag_service dans FeatureFlagsPanel.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchFeatureFlags, updateFeatureFlag } from '../services/feature_flag_service';
import type { FeatureFlagDetail } from '../services/feature_flag_service';
import logger from '../services/logger';

export type { FeatureFlagDetail } from '../services/feature_flag_service';

export function useFeatureFlagsAdmin() {
  const [flags, setFlags] = useState<FeatureFlagDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFlags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchFeatureFlags();
      setFlags(response.data);
    } catch (err) {
      logger.error('feature_flags_admin_load_error', { error: String(err) });
      setError('Erreur lors du chargement des feature flags');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  const handleToggle = useCallback(async (flagKey: string, enabled: boolean) => {
    try {
      await updateFeatureFlag(flagKey, { enabled });
      setFlags((prev) =>
        prev.map((f) => (f.flag_key === flagKey ? { ...f, enabled } : f)),
      );
      setError(null);
    } catch (err) {
      logger.error('feature_flags_toggle_error', { flagKey, error: String(err) });
      setError('Erreur lors de la mise à jour du flag');
      throw err;
    }
  }, []);

  const handleRolloutChange = useCallback(async (flagKey: string, rolloutPercent: number) => {
    try {
      await updateFeatureFlag(flagKey, { rollout_percent: rolloutPercent });
      setFlags((prev) =>
        prev.map((f) =>
          f.flag_key === flagKey ? { ...f, rollout_percent: rolloutPercent } : f,
        ),
      );
      setError(null);
    } catch (err) {
      logger.error('feature_flags_rollout_error', { flagKey, error: String(err) });
      setError('Erreur lors de la mise à jour du rollout');
      throw err;
    }
  }, []);

  return { flags, loading, error, handleToggle, handleRolloutChange, refresh: loadFlags };
}
