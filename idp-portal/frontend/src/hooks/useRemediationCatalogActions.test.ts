/**
 * Tests pour useRemediationCatalogActions (Story 48.8, AC4, AC6).
 * Vérifie que le hook encapsule correctement fetchCatalogActions (catalog_service).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useRemediationCatalogActions } from './useRemediationCatalogActions';

vi.mock('../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(),
}));

vi.mock('../services/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { fetchCatalogActions } from '../services/catalog_service';

const MOCK_CATALOG_ACTIONS = [
  { id: 1, name: 'Action A', engine: 'Oracle', status: 'published' as const },
  { id: 2, name: 'Action B', engine: 'PostgreSQL', status: 'published' as const },
];

describe('useRemediationCatalogActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('charge les actions du catalogue (cas nominal)', async () => {
    vi.mocked(fetchCatalogActions).mockResolvedValue(MOCK_CATALOG_ACTIONS as never);

    const { result } = renderHook(() => useRemediationCatalogActions());
    expect(result.current.loadingCatalog).toBe(true);

    await waitFor(() => expect(result.current.loadingCatalog).toBe(false));

    expect(result.current.catalogActions).toHaveLength(2);
    expect(result.current.catalogActions[0].name).toBe('Action A');
    expect(result.current.catalogError).toBeNull();
  });

  it('gère les erreurs et expose catalogError', async () => {
    vi.mocked(fetchCatalogActions).mockRejectedValue(new Error('timeout catalogue'));

    const { result } = renderHook(() => useRemediationCatalogActions());
    await waitFor(() => expect(result.current.loadingCatalog).toBe(false));

    expect(result.current.catalogActions).toEqual([]);
    expect(result.current.catalogError).toBe('timeout catalogue');
  });

  it('gère les erreurs non-Error avec message par défaut', async () => {
    vi.mocked(fetchCatalogActions).mockRejectedValue('unknown');

    const { result } = renderHook(() => useRemediationCatalogActions());
    await waitFor(() => expect(result.current.loadingCatalog).toBe(false));

    expect(result.current.catalogError).toBe('Erreur chargement catalogue');
  });

  it('cancelled flag — ignore les mises à jour si le composant est démonté', async () => {
    let resolvePromise!: (v: unknown) => void;
    vi.mocked(fetchCatalogActions).mockReturnValue(
      new Promise((res) => { resolvePromise = res; }) as never
    );

    const { result, unmount } = renderHook(() => useRemediationCatalogActions());
    expect(result.current.loadingCatalog).toBe(true);

    // Démonter avant la résolution
    unmount();

    // Résoudre après le démontage — ne doit pas déclencher de setState
    await act(async () => {
      resolvePromise(MOCK_CATALOG_ACTIONS);
      await new Promise((r) => setTimeout(r, 0));
    });

    // Pas d'erreur "Can't perform a React state update on an unmounted component"
    expect(result.current.catalogActions).toEqual([]);
  });

  it('gère un retour non-array en retournant un tableau vide', async () => {
    vi.mocked(fetchCatalogActions).mockResolvedValue(null as never);

    const { result } = renderHook(() => useRemediationCatalogActions());
    await waitFor(() => expect(result.current.loadingCatalog).toBe(false));

    expect(result.current.catalogActions).toEqual([]);
  });
});
