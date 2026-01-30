/**
 * Catalog service (Story 3.1).
 *
 * Provides functions to fetch catalog actions, favorites, and recent actions.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type { ActionPreviewData } from '../types/api';

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

/** Filters for catalog query (Story 3.3, AC9; Story 2.23: category removed). */
export interface CatalogFilters {
  tags?: string[];
  /** Text search on name, description, tags (debounce 300 ms recommended). */
  q?: string;
  engine?: string;
  environment?: string;
  impact?: string;
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
 * Optional filters: tags, q, engine, environment, impact (Story 3.3; Story 2.23: category removed).
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
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<CatalogAction[]>(`/catalog/actions${query}`);
}

/**
 * Fetch tags with action counts for catalog (Story 3.3, AC3, AC10).
 * Returns list of { name, action_count } for published actions (RBAC applied).
 */
export async function fetchCatalogTags(): Promise<CatalogTagWithCount[]> {
  return apiFetch<CatalogTagWithCount[]>('/catalog/tags');
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
