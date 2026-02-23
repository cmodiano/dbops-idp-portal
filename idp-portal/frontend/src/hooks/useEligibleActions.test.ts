/**
 * Tests pour useEligibleActions (Story 35.3, Task 4.3).
 * Vérifie que le hook encapsule correctement getEligibleActionsForWorkflow (admin_service).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useEligibleActions } from './useEligibleActions';

vi.mock('../services/admin_service', () => ({
  getEligibleActionsForWorkflow: vi.fn(),
}));

const MOCK_ACTIONS = [
  { id: 1, name: 'Alpha', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
  { id: 2, name: 'Beta', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
  { id: 3, name: 'Gamma', engine: 'Oracle', status: 'published', created_at: '', execution_count: 5 },
];

vi.mock('../services/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { getEligibleActionsForWorkflow } from '../services/admin_service';

describe('useEligibleActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getEligibleActionsForWorkflow).mockResolvedValue(MOCK_ACTIONS);
  });

  it('retourne les actions éligibles après chargement', async () => {
    const { result } = renderHook(() => useEligibleActions());

    // Initialement en chargement
    expect(result.current.loadingActions).toBe(true);
    expect(result.current.loadError).toBeNull();

    await waitFor(() => {
      expect(result.current.loadingActions).toBe(false);
    });

    expect(result.current.eligibleActions).toHaveLength(3);
    expect(result.current.eligibleActions[0].name).toBe('Alpha');
    expect(result.current.loadError).toBeNull();
  });

  it('appelle getEligibleActionsForWorkflow au montage', async () => {
    renderHook(() => useEligibleActions());

    await waitFor(() => {
      expect(getEligibleActionsForWorkflow).toHaveBeenCalledTimes(1);
    });
  });

  it('gère l\'erreur réseau et expose loadError', async () => {
    vi.mocked(getEligibleActionsForWorkflow).mockRejectedValueOnce(
      new Error('Network error')
    );

    const { result } = renderHook(() => useEligibleActions());

    await waitFor(() => {
      expect(result.current.loadingActions).toBe(false);
    });

    expect(result.current.eligibleActions).toEqual([]);
    expect(result.current.loadError).toBe('Network error');
  });

  it('traduit "Unknown error" en message français informatif', async () => {
    vi.mocked(getEligibleActionsForWorkflow).mockRejectedValueOnce(
      new Error('Unknown error')
    );

    const { result } = renderHook(() => useEligibleActions());

    await waitFor(() => {
      expect(result.current.loadError).toContain('Vérifiez votre connexion');
    });
  });

  it('gère un retour non-array en retournant un tableau vide', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(getEligibleActionsForWorkflow).mockResolvedValueOnce(null as any);

    const { result } = renderHook(() => useEligibleActions());

    await waitFor(() => {
      expect(result.current.loadingActions).toBe(false);
    });

    expect(result.current.eligibleActions).toEqual([]);
  });
});
