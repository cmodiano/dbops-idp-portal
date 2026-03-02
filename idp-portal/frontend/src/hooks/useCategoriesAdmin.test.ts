/**
 * Tests unitaires pour useCategoriesAdmin (Story 54.15, AC8).
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useCategoriesAdmin } from './useCategoriesAdmin';
import { getCategories, deleteCategory } from '../services/categories_service';
import { invalidateCategoriesCache } from './useCategories';

vi.mock('../services/categories_service');
vi.mock('./useCategories', () => ({
  invalidateCategoriesCache: vi.fn(),
}));
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

describe('useCategoriesAdmin', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('charge les catégories au montage', async () => {
    const mockCategories = [
      { id: 1, code: 'backup', label: 'Sauvegarde', display_order: 1, is_active: 1 },
      { id: 2, code: 'deploy', label: 'Déploiement', display_order: 2, is_active: 0 },
    ];
    vi.mocked(getCategories).mockResolvedValue(mockCategories);

    const { result } = renderHook(() => useCategoriesAdmin());
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.categories).toEqual(mockCategories);
    expect(result.current.error).toBeNull();
    expect(getCategories).toHaveBeenCalledWith(false);
  });

  it('gère les erreurs de chargement', async () => {
    vi.mocked(getCategories).mockRejectedValue(new Error('réseau indisponible'));

    const { result } = renderHook(() => useCategoriesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('réseau indisponible');
    expect(result.current.categories).toEqual([]);
  });

  it('handleDelete supprime la catégorie et invalide le cache', async () => {
    const mockCategories = [
      { id: 1, code: 'backup', label: 'Sauvegarde', display_order: 1, is_active: 1 },
      { id: 2, code: 'deploy', label: 'Déploiement', display_order: 2, is_active: 1 },
    ];
    vi.mocked(getCategories).mockResolvedValue(mockCategories);
    vi.mocked(deleteCategory).mockResolvedValue(undefined);

    const { result } = renderHook(() => useCategoriesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleDelete(1);
    });

    expect(deleteCategory).toHaveBeenCalledWith(1);
    expect(invalidateCategoriesCache).toHaveBeenCalled();
    expect(result.current.categories).toEqual([
      { id: 2, code: 'deploy', label: 'Déploiement', display_order: 2, is_active: 1 },
    ]);
  });

  it('handleDelete propage l\'erreur en cas d\'échec', async () => {
    vi.mocked(getCategories).mockResolvedValue([{ id: 1, code: 'test', label: 'Test', display_order: 1, is_active: 1 }]);
    vi.mocked(deleteCategory).mockRejectedValue(new Error('Suppression refusée'));

    const { result } = renderHook(() => useCategoriesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(async () => { await result.current.handleDelete(1); })
    ).rejects.toThrow('Suppression refusée');
  });

  it('refresh force un nouveau chargement', async () => {
    vi.mocked(getCategories).mockResolvedValue([]);

    const { result } = renderHook(() => useCategoriesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(getCategories).toHaveBeenCalledTimes(1);

    act(() => { result.current.refresh(); });
    await waitFor(() => expect(getCategories).toHaveBeenCalledTimes(2));
  });

  it('cancelled flag — composant démonté avant réponse', async () => {
    vi.mocked(getCategories).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve([]), 100))
    );
    const { unmount } = renderHook(() => useCategoriesAdmin());
    unmount();
    await new Promise((r) => setTimeout(r, 150));
    // Pas d'erreur React "setState on unmounted component"
  });
});
