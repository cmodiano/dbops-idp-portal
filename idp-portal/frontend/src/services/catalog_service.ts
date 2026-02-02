/**
 * Catalog service (Story 3.1).
 *
 * Provides functions to fetch catalog actions, favorites, and recent actions.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type { ActionPreviewData, ActionStats } from '../types/api';

/** Action with execution_count for catalog display. */
export interface CatalogAction extends ActionPreviewData {
  id: number;
  status: string;
  created_at: string;
  execution_count: number;
}

/** Favorite entry from API. */
export interface FavoriteEntry {
  action_id: number;
  created_at: string;
}

/** Recent action entry from API. */
export interface RecentAction {
  action_id: number;
  name: string;
  last_executed_at: string;
}

/** Filters for catalog query (Story 3.3, AC9; Story 8.7: category added back). */
export interface CatalogFilters {
  tags?: string[];
  /** Text search on name, description, tags (debounce 300 ms recommended). */
  q?: string;
  engine?: string;
  environment?: string;
  impact?: string;
  /** Category filter (maps to tag on backend): provisioning, patching, etc. Story 8.7. */
  category?: string;
}

/** Tag with action count from GET /catalog/tags (Story 3.3, AC10). */
export interface CatalogTagWithCount {
  name: string;
  action_count: number;
}

/** Full action detail from GET /catalog/actions/{id} (Story 3.2). */
export interface CatalogActionDetail extends CatalogAction {
  execution_steps?: unknown[];
  change_type_config?: Record<string, unknown>;
}

/** Response from GET /catalog/actions/{id} (Story 3.2, AC3). */
export interface CatalogActionDetailResponse {
  data: CatalogActionDetail;
  can_execute: boolean;
  allowed_environments: string[];
}

/**
 * Fetch catalog actions (AC1, AC3, AC6, AC9, AC10, AC11).
 * Optional filters: tags, q, engine, environment, impact, category (Story 3.3; Story 8.7: category added).
 */
export async function fetchCatalogActions(filters?: CatalogFilters): Promise<CatalogAction[]> {
  const params = new URLSearchParams();
  if (filters?.tags && filters.tags.length > 0) {
    params.set('tags', filters.tags.join(','));
  }
  if (filters?.q?.trim()) {
    params.set('q', filters.q.trim());
  }
  if (filters?.engine) {
    params.set('engine', filters.engine);
  }
  if (filters?.environment) {
    params.set('environment', filters.environment);
  }
  if (filters?.impact) {
    params.set('impact', filters.impact);
  }
  // Story 8.7: Add category filter (skip "tout" and "mes-actions" as they are UI-only)
  if (filters?.category && filters.category !== 'tout' && filters.category !== 'mes-actions') {
    params.set('category', filters.category);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<CatalogAction[]>(`/catalog/actions${query}`);
}

/**
 * Fetch tags with action counts for catalog (Story 3.3, AC3, AC10; Story 8.7: category filter).
 * Returns list of { name, action_count } for published actions (RBAC applied).
 * Story 8.7 AC3: When category is provided, returns only tags from actions in that category.
 */
export async function fetchCatalogTags(category?: string): Promise<CatalogTagWithCount[]> {
  const params = new URLSearchParams();
  // Story 8.7: Filter tags by category (skip "tout" and "mes-actions")
  if (category && category !== 'tout' && category !== 'mes-actions') {
    params.set('category', category);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<CatalogTagWithCount[]>(`/catalog/tags${query}`);
}

/**
 * Fetch user favorites (AC4, AC12).
 */
export async function fetchFavorites(): Promise<FavoriteEntry[]> {
  return apiFetch<FavoriteEntry[]>('/users/me/favorites');
}

/**
 * Add action to favorites (AC13). Idempotent.
 */
export async function addFavorite(actionId: number): Promise<void> {
  await apiFetch(`/users/me/favorites/${actionId}`, { method: 'POST' });
}

/**
 * Remove action from favorites (AC13). Idempotent.
 */
export async function removeFavorite(actionId: number): Promise<void> {
  await apiFetch(`/users/me/favorites/${actionId}`, { method: 'DELETE' });
}

/**
 * Fetch recent actions (AC5).
 * @deprecated Story 9.6: No longer used in CatalogPage "Mes actions" tab (favorites only).
 * Recent actions are now available in "Mes exécutions" tab on ExecutionsPage (Story 8.9).
 * This function can be removed if not used elsewhere.
 */
export async function fetchRecentActions(limit = 10): Promise<RecentAction[]> {
  return apiFetch<RecentAction[]>(`/users/me/recent-actions?limit=${limit}`);
}

/**
 * Fetch single action detail by ID (Story 3.2, AC1, AC3, AC6).
 * Returns full action detail with can_execute and allowed_environments.
 * Throws if action not found or user lacks permission.
 *
 * Uses apiFetchRaw to include auth headers while preserving full response structure
 * (can_execute and allowed_environments alongside data).
 */
export async function fetchCatalogActionById(
  id: number
): Promise<CatalogActionDetailResponse> {
  const response = await apiFetchRaw<{
    data: CatalogActionDetail;
    can_execute: boolean;
    allowed_environments: string[];
  }>(`/catalog/actions/${id}`);
  return {
    data: response.data,
    can_execute: response.can_execute ?? false,
    allowed_environments: response.allowed_environments ?? [],
  };
}

/**
 * Fetch action stats for scorecard display (Story 8.1, AC4, AC5).
 * Returns aggregated metrics over the last 30 days.
 * Returns null if no executions exist (AC3).
 *
 * @param actionId - The action ID to fetch stats for
 * @returns ActionStats or null if no data
 */
export async function fetchActionStats(actionId: number): Promise<ActionStats | null> {
  const response = await apiFetchRaw<{ data: ActionStats | null }>(`/catalog/actions/${actionId}/stats`);
  return response.data;
}
