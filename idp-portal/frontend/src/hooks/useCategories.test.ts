/**
 * Tests for useCategories hook (Story 48.7 — cache invalidation).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useCategories, invalidateCategoriesCache } from './useCategories';
import { getCategories } from '../services/categories_service';
import type { RefCategory } from '../types/api';

vi.mock('../services/categories_service');

const mockCategories: RefCategory[] = [
  { id: 1, code: 'CAT1', label: 'Category 1', display_order: 1, is_active: 1 },
  { id: 2, code: 'CAT2', label: 'Category 2', display_order: 2, is_active: 1 },
];

describe('useCategories', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCategoriesCache(); // isolation test-à-test
  });

  it('charge les catégories depuis l\'API', async () => {
    vi.mocked(getCategories).mockResolvedValue(mockCategories);

    const { result } = renderHook(() => useCategories());
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.categories).toEqual(mockCategories);
    expect(getCategories).toHaveBeenCalledTimes(1);
    expect(getCategories).toHaveBeenCalledWith(true); // active-only filter
  });

  it('utilise le cache — pas de double requête API', async () => {
    vi.mocked(getCategories).mockResolvedValue(mockCategories);

    const { result: r1 } = renderHook(() => useCategories());
    const { result: r2 } = renderHook(() => useCategories());

    await waitFor(() => expect(r1.current.loading).toBe(false));
    await waitFor(() => expect(r2.current.loading).toBe(false));

    expect(getCategories).toHaveBeenCalledTimes(1); // déduplication
    expect(r1.current.categories).toEqual(mockCategories);
    expect(r2.current.categories).toEqual(mockCategories);
  });

  it('invalidateCategoriesCache déclenche un nouveau fetch', async () => {
    vi.mocked(getCategories).mockResolvedValue(mockCategories);

    const { result: r1 } = renderHook(() => useCategories());
    await waitFor(() => expect(r1.current.loading).toBe(false));

    invalidateCategoriesCache();

    const updatedCategories: RefCategory[] = [
      ...mockCategories,
      { id: 3, code: 'CAT3', label: 'Category 3', display_order: 3, is_active: 1 },
    ];
    vi.mocked(getCategories).mockResolvedValue(updatedCategories);

    const { result: r2 } = renderHook(() => useCategories());
    await waitFor(() => expect(r2.current.loading).toBe(false));

    expect(getCategories).toHaveBeenCalledTimes(2); // refetch après invalidation
    expect(r2.current.categories).toEqual(updatedCategories);
  });

  it('gère les erreurs API — error défini et loading=false', async () => {
    vi.mocked(getCategories).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useCategories());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('Network error');
    expect(result.current.categories).toEqual([]);
  });

  it('retourne categoryOptions filtrées et triées', async () => {
    const mixed: RefCategory[] = [
      { id: 1, code: 'ZZZ', label: 'Last', display_order: 3, is_active: 1 },
      { id: 2, code: 'AAA', label: 'First', display_order: 1, is_active: 1 },
      { id: 3, code: 'INACTIVE', label: 'Inactive', display_order: 2, is_active: 0 },
    ];
    vi.mocked(getCategories).mockResolvedValue(mixed);

    const { result } = renderHook(() => useCategories());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.categoryOptions).toEqual([
      { value: 'AAA', label: 'First' },
      { value: 'ZZZ', label: 'Last' },
    ]);
  });
});
