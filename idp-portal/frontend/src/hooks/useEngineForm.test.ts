/**
 * Tests unitaires pour useEngineForm (Story 54.15, AC8).
 */

import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useEngineForm } from './useEngineForm';
import { updateEngine } from '../services/engines_service';

vi.mock('../services/engines_service');

const mockEngine = { id: 1, code: 'oracle', label: 'Oracle', icon_url: null as string | null, display_order: 1, is_active: 1 };

describe('useEngineForm', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('état initial — pas de sauvegarde en cours', () => {
    const { result } = renderHook(() => useEngineForm());
    expect(result.current.saving).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handleUpdate — succès : retourne le moteur mis à jour', async () => {
    const updatedEngine = { ...mockEngine, label: 'Oracle DB' };
    vi.mocked(updateEngine).mockResolvedValue(updatedEngine);

    const { result } = renderHook(() => useEngineForm());

    let returned: typeof updatedEngine | undefined;
    await act(async () => {
      returned = await result.current.handleUpdate(1, { label: 'Oracle DB' });
    });

    expect(updateEngine).toHaveBeenCalledWith(1, { label: 'Oracle DB' });
    expect(returned).toEqual(updatedEngine);
    expect(result.current.saving).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handleUpdate — état saving=true pendant la requête', async () => {
    let resolveUpdate!: (v: typeof mockEngine) => void;
    vi.mocked(updateEngine).mockImplementation(
      () => new Promise((resolve) => { resolveUpdate = resolve; })
    );

    const { result } = renderHook(() => useEngineForm());

    act(() => { void result.current.handleUpdate(1, { label: 'Oracle DB' }); });
    expect(result.current.saving).toBe(true);

    await act(async () => { resolveUpdate(mockEngine); });
    expect(result.current.saving).toBe(false);
  });

  it('handleUpdate — erreur : set error, remet saving=false, propage', async () => {
    vi.mocked(updateEngine).mockRejectedValue(new Error('Mise à jour refusée'));

    const { result } = renderHook(() => useEngineForm());

    let caughtError: Error | undefined;
    await act(async () => {
      try {
        await result.current.handleUpdate(1, { is_active: 0 });
      } catch (e) {
        caughtError = e as Error;
      }
    });

    expect(caughtError?.message).toBe('Mise à jour refusée');
    expect(result.current.error).toBe('Mise à jour refusée');
    expect(result.current.saving).toBe(false);
  });
});
