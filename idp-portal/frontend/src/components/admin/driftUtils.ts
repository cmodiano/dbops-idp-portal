/**
 * Utility types and functions for IaC drift status (Story 64.13).
 */

export type DriftStatus = 'synced' | 'diverged' | 'ui-only';

export function getDriftStatus(
  last_synced_at: string | null | undefined,
  updated_at: string | null | undefined,
): DriftStatus {
  if (!last_synced_at) return 'ui-only';
  if (!updated_at) return 'synced';
  return new Date(updated_at) > new Date(last_synced_at) ? 'diverged' : 'synced';
}
