/**
 * Engines admin service (Story 31.10).
 * Fetch and update REF_ENGINES reference data for admin UI.
 */

import { apiFetch } from './api_client';
import type { RefEngine } from './reference_service';

/**
 * Fetch engines for admin (all, including inactive).
 * @param activeOnly - If false (default for admin), return all engines.
 */
export async function fetchEnginesForAdmin(activeOnly = false): Promise<RefEngine[]> {
  return apiFetch<RefEngine[]>(`/reference/engines?active_only=${activeOnly}`);
}

/**
 * Update an existing engine (DBOPS admin only).
 */
export async function updateEngine(
  id: number,
  payload: Partial<{ icon_url: string | null; label: string; display_order: number; is_active: number }>
): Promise<RefEngine> {
  return apiFetch<RefEngine>(`/admin/engines/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
