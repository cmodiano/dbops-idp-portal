/**
 * Hook to load approver profiles from the API (Story 58.4, AC2, AC4).
 * Fetches GET /admin/profiles?is_approver=true and returns options for Select components.
 *
 * @param enabled - Si false, aucun appel API n'est effectué (optimisation pour les gates non-approval).
 */

import { useState, useEffect } from 'react';
import { apiFetch } from '../services/api_client';
import type { ProfileListItem } from '../types/api';

interface ApproverProfile {
  id: number;
  name: string;
}

interface UseApproverProfilesResult {
  profiles: ApproverProfile[];
  loading: boolean;
  approverProfileOptions: { value: number; label: string }[];
}

export function useApproverProfiles(enabled = true): UseApproverProfilesResult {
  const [profiles, setProfiles] = useState<ApproverProfile[]>([]);
  const [loading, setLoading] = useState(enabled);

  useEffect(() => {
    if (!enabled) {
      setProfiles([]);
      setLoading(false);
      return;
    }

    let cancelled = false;

    setLoading(true);
    apiFetch<ProfileListItem[]>('/admin/profiles/?is_approver=true')
      .then((data) => {
        if (!cancelled) {
          const items = (data ?? []).map((p) => ({ id: p.id, name: p.name }));
          setProfiles(items);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          void err; // silently ignore fetch errors
          setProfiles([]);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const approverProfileOptions = profiles.map((p) => ({
    value: p.id,
    label: p.name,
  }));

  return { profiles, loading, approverProfileOptions };
}
