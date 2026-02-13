/**
 * Story 17.12: Feature Flag API service.
 *
 * Provides typed functions for interacting with the feature flag API endpoints.
 */

import { apiFetch, apiFetchRaw } from './api_client';

/** Flag status map: flag_key -> enabled boolean. */
export type FeatureFlagsStatus = Record<string, boolean>;

export interface FeatureFlagDetail {
  flag_key: string;
  enabled: boolean;
  rollout_percent: number;
  description: string;
  updated_at: string | null;
  updated_by: string;
}

export interface FeatureFlagListResponse {
  data: FeatureFlagDetail[];
  source: string;
}

/**
 * GET /api/v1/feature-flags/status/
 * Returns current user's feature flag status (authenticated).
 */
export async function fetchFeatureFlagsStatus(): Promise<FeatureFlagsStatus> {
  return apiFetch<FeatureFlagsStatus>('/feature-flags/status');
}

/**
 * GET /api/v1/feature-flags/
 * Returns all feature flags (admin only).
 */
export async function fetchFeatureFlags(): Promise<FeatureFlagListResponse> {
  return apiFetchRaw<FeatureFlagListResponse>('/feature-flags');
}

/**
 * PATCH /api/v1/feature-flags/{flagKey}/
 * Update a feature flag (admin only).
 */
export async function updateFeatureFlag(
  flagKey: string,
  data: { enabled?: boolean; rollout_percent?: number },
): Promise<FeatureFlagDetail> {
  return apiFetch<FeatureFlagDetail>(`/feature-flags/${flagKey}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}
