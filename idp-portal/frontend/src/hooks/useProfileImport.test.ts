/**
 * Tests unitaires pour useProfileImport (Story 54.15, AC8).
 */

import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useProfileImport } from './useProfileImport';
import { importProfilesYaml } from '../services/profiles_service';

vi.mock('../services/profiles_service');
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

const mockFile = new File(['content'], 'profiles.yaml', { type: 'application/x-yaml' });
const mockResult = { created: 3, updated: 1 };

describe('useProfileImport', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('état initial — pas d\'import en cours', () => {
    const { result } = renderHook(() => useProfileImport());
    expect(result.current.importing).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('importFile — succès : retourne le résultat avec created/updated', async () => {
    vi.mocked(importProfilesYaml).mockResolvedValue(mockResult);

    const { result } = renderHook(() => useProfileImport());

    let returned: typeof mockResult | undefined;
    await act(async () => {
      returned = await result.current.importFile(mockFile);
    });

    expect(importProfilesYaml).toHaveBeenCalledWith(mockFile);
    expect(returned).toEqual(mockResult);
    expect(result.current.importing).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('importFile — état importing=true pendant la requête', async () => {
    let resolveImport!: (v: typeof mockResult) => void;
    vi.mocked(importProfilesYaml).mockImplementation(
      () => new Promise((resolve) => { resolveImport = resolve; })
    );

    const { result } = renderHook(() => useProfileImport());

    act(() => { void result.current.importFile(mockFile); });
    expect(result.current.importing).toBe(true);

    await act(async () => { resolveImport(mockResult); });
    expect(result.current.importing).toBe(false);
  });

  it('importFile — erreur : set error, remet importing=false, propage', async () => {
    vi.mocked(importProfilesYaml).mockRejectedValue(new Error('Format YAML invalide'));

    const { result } = renderHook(() => useProfileImport());

    let caughtError: Error | undefined;
    await act(async () => {
      try {
        await result.current.importFile(mockFile);
      } catch (e) {
        caughtError = e as Error;
      }
    });

    expect(caughtError?.message).toBe('Format YAML invalide');
    expect(result.current.error).toBe('Format YAML invalide');
    expect(result.current.importing).toBe(false);
  });

  it('reset — efface l\'état d\'erreur', async () => {
    vi.mocked(importProfilesYaml).mockRejectedValue(new Error('Erreur'));

    const { result } = renderHook(() => useProfileImport());
    await act(async () => {
      try { await result.current.importFile(mockFile); } catch { /* expected */ }
    });
    expect(result.current.error).toBe('Erreur');

    act(() => { result.current.reset(); });
    expect(result.current.error).toBeNull();
  });
});
