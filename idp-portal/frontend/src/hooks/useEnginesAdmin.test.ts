/**
 * Tests unitaires pour useEnginesAdmin (Story 54.15, AC8).
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useEnginesAdmin } from './useEnginesAdmin';
import { fetchEnginesForAdmin, updateEngine } from '../services/engines_service';

vi.mock('../services/engines_service');
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

const mockEngines = [
  { id: 1, code: 'oracle', label: 'Oracle', icon_url: null as string | null, display_order: 1, is_active: 1 },
  { id: 2, code: 'mysql', label: 'MySQL', icon_url: null as string | null, display_order: 2, is_active: 0 },
];

describe('useEnginesAdmin', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('charge les moteurs au montage', async () => {
    vi.mocked(fetchEnginesForAdmin).mockResolvedValue(mockEngines);

    const { result } = renderHook(() => useEnginesAdmin());
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.engines).toEqual(mockEngines);
    expect(result.current.error).toBeNull();
    expect(fetchEnginesForAdmin).toHaveBeenCalledWith(false);
  });

  it('gère les erreurs de chargement', async () => {
    vi.mocked(fetchEnginesForAdmin).mockRejectedValue(new Error('Timeout serveur'));

    const { result } = renderHook(() => useEnginesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Timeout serveur');
    expect(result.current.engines).toEqual([]);
  });

  it('handleUpdate appelle updateEngine avec les bons paramètres', async () => {
    vi.mocked(fetchEnginesForAdmin).mockResolvedValue(mockEngines);
    const updatedEngine = { ...mockEngines[0], label: 'Oracle DB' };
    vi.mocked(updateEngine).mockResolvedValue(updatedEngine);

    const { result } = renderHook(() => useEnginesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let returned: typeof updatedEngine | undefined;
    await act(async () => {
      returned = await result.current.handleUpdate(1, { label: 'Oracle DB' });
    });

    expect(updateEngine).toHaveBeenCalledWith(1, { label: 'Oracle DB' });
    expect(returned).toEqual(updatedEngine);
  });

  it('handleUpdate propage l\'erreur en cas d\'échec', async () => {
    vi.mocked(fetchEnginesForAdmin).mockResolvedValue(mockEngines);
    vi.mocked(updateEngine).mockRejectedValue(new Error('Mise à jour refusée'));

    const { result } = renderHook(() => useEnginesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(async () => { await result.current.handleUpdate(1, { is_active: 0 }); })
    ).rejects.toThrow('Mise à jour refusée');
  });

  it('refresh force un nouveau chargement', async () => {
    vi.mocked(fetchEnginesForAdmin).mockResolvedValue([]);

    const { result } = renderHook(() => useEnginesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchEnginesForAdmin).toHaveBeenCalledTimes(1);

    act(() => { result.current.refresh(); });
    await waitFor(() => expect(fetchEnginesForAdmin).toHaveBeenCalledTimes(2));
  });

  it('cancelled flag — composant démonté avant réponse', async () => {
    vi.mocked(fetchEnginesForAdmin).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve([]), 100))
    );
    const { unmount } = renderHook(() => useEnginesAdmin());
    unmount();
    await new Promise((r) => setTimeout(r, 150));
    // Pas d'erreur React "setState on unmounted component"
  });
});
