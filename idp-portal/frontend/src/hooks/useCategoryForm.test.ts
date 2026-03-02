/**
 * Tests unitaires pour useCategoryForm (Story 54.15, AC8).
 */

import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useCategoryForm } from './useCategoryForm';
import { createCategory, updateCategory } from '../services/categories_service';

vi.mock('../services/categories_service');
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

const mockPayload = { code: 'backup', label: 'Sauvegarde', display_order: 1, is_active: 1 };
const mockCategory = { id: 1, ...mockPayload };

describe('useCategoryForm', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('crée une catégorie (pas de editId)', async () => {
    vi.mocked(createCategory).mockResolvedValue(mockCategory);

    const { result } = renderHook(() => useCategoryForm());
    expect(result.current.submitting).toBe(false);

    let returned: typeof mockCategory | undefined;
    await act(async () => {
      returned = await result.current.submit(mockPayload);
    });

    expect(createCategory).toHaveBeenCalledWith(mockPayload);
    expect(updateCategory).not.toHaveBeenCalled();
    expect(returned).toEqual(mockCategory);
    expect(result.current.submitting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('met à jour une catégorie (avec editId)', async () => {
    const updated = { ...mockCategory, label: 'Sauvegarde modifiée' };
    vi.mocked(updateCategory).mockResolvedValue(updated);

    const { result } = renderHook(() => useCategoryForm());

    let returned: typeof updated | undefined;
    await act(async () => {
      returned = await result.current.submit(mockPayload, 1);
    });

    expect(updateCategory).toHaveBeenCalledWith(1, mockPayload);
    expect(createCategory).not.toHaveBeenCalled();
    expect(returned).toEqual(updated);
  });

  it('gère l\'erreur réseau et la propage', async () => {
    vi.mocked(createCategory).mockRejectedValue(new Error('Connexion refusée'));

    const { result } = renderHook(() => useCategoryForm());

    let caughtError: Error | undefined;
    await act(async () => {
      try {
        await result.current.submit(mockPayload);
      } catch (e) {
        caughtError = e as Error;
      }
    });

    expect(caughtError?.message).toBe('Connexion refusée');
    expect(result.current.error).toBe('Connexion refusée');
    expect(result.current.submitting).toBe(false);
  });

  it('passe submitting=true pendant la requête', async () => {
    let resolveCreate!: (v: typeof mockCategory) => void;
    vi.mocked(createCategory).mockImplementation(
      () => new Promise((resolve) => { resolveCreate = resolve; })
    );

    const { result } = renderHook(() => useCategoryForm());

    act(() => { void result.current.submit(mockPayload); });
    expect(result.current.submitting).toBe(true);

    await act(async () => { resolveCreate(mockCategory); });
    expect(result.current.submitting).toBe(false);
  });
});
