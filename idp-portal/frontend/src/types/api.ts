/**
 * Barrel re-export for API types.
 *
 * This file re-exports all types from domain-specific files under 'types/api/'.
 * It is intentionally kept as the primary import path for convenience.
 * For tree-shaking benefits, you may import from domain files directly:
 * - types/api/catalog, types/api/executions, types/api/profiles, etc.
 */
export * from './api/index';
