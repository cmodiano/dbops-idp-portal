/**
 * Categories service (Story 2.30).
 * CRUD operations for REF_CATEGORIES reference data.
 */

import { apiFetch } from './api_client';
import type { RefCategory } from '../types/api';

/**
 * Fetch categories from REF_CATEGORIES table.
 * @param activeOnly - If true (default), return only active categories.
 */
export async function getCategories(activeOnly = true): Promise<RefCategory[]> {
  return apiFetch<RefCategory[]>(`/reference/categories?active_only=${activeOnly}`);
}

/**
 * Create a new category (DBOPS admin only).
 */
export async function createCategory(data: {
  code: string;
  label: string;
  display_order: number;
  is_active: number;
}): Promise<RefCategory> {
  return apiFetch<RefCategory>('/admin/categories/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing category (DBOPS admin only).
 */
export async function updateCategory(
  id: number,
  data: Partial<{ code: string; label: string; display_order: number; is_active: number }>
): Promise<RefCategory> {
  return apiFetch<RefCategory>(`/admin/categories/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Soft-delete a category (set is_active=0). DBOPS admin only.
 */
export async function deleteCategory(id: number): Promise<void> {
  await apiFetch<void>(`/admin/categories/${id}/delete/`, { method: 'DELETE' });
}
