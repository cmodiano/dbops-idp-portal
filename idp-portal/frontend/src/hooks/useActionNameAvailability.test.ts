/**
 * Tests pour useActionNameAvailability (Story 48.8, AC3, AC6).
 * Vérifie que le hook encapsule correctement checkActionNameAvailable (admin_service).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useActionNameAvailability } from './useActionNameAvailability';

vi.mock('../services/admin_service', () => ({
  checkActionNameAvailable: vi.fn(),
}));

import { checkActionNameAvailable } from '../services/admin_service';

describe('useActionNameAvailability', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('expose checkName qui retourne true quand le nom est disponible', async () => {
    vi.mocked(checkActionNameAvailable).mockResolvedValue(true);

    const { result } = renderHook(() => useActionNameAvailability());
    const available = await result.current.checkName('MonAction');

    expect(available).toBe(true);
    expect(checkActionNameAvailable).toHaveBeenCalledWith('MonAction', undefined);
  });

  it('retourne false quand le nom est déjà pris', async () => {
    vi.mocked(checkActionNameAvailable).mockResolvedValue(false);

    const { result } = renderHook(() => useActionNameAvailability());
    const available = await result.current.checkName('ActionExistante');

    expect(available).toBe(false);
    expect(checkActionNameAvailable).toHaveBeenCalledWith('ActionExistante', undefined);
  });

  it('transmet excludeId au service pour le mode édition', async () => {
    vi.mocked(checkActionNameAvailable).mockResolvedValue(true);

    const { result } = renderHook(() => useActionNameAvailability());
    await result.current.checkName('MonAction', 42);

    expect(checkActionNameAvailable).toHaveBeenCalledWith('MonAction', 42);
  });

  it('propage les erreurs réseau', async () => {
    vi.mocked(checkActionNameAvailable).mockRejectedValue(new Error('réseau'));

    const { result } = renderHook(() => useActionNameAvailability());

    await expect(result.current.checkName('MonAction')).rejects.toThrow('réseau');
  });

  it('retourne une référence stable pour checkName (useCallback)', () => {
    const { result, rerender } = renderHook(() => useActionNameAvailability());
    const first = result.current.checkName;
    rerender();
    expect(result.current.checkName).toBe(first);
  });
});
