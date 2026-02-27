/**
 * Tests pour useAdminAnalytics (Story 48.8, AC2, AC6).
 * Vérifie que le hook encapsule correctement fetchAdminAnalytics (admin_service).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAdminAnalytics } from './useAdminAnalytics';

vi.mock('../services/admin_service', () => ({
  fetchAdminAnalytics: vi.fn(),
}));

vi.mock('../services/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { fetchAdminAnalytics } from '../services/admin_service';
import type { AdminAnalytics } from '../types/api';

const MOCK_DATA: AdminAnalytics = {
  total_published_actions: 10,
  executions_by_engine: [],
  executions_by_profile: [],
  adoption_trend: [],
};

describe('useAdminAnalytics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('charge les analytics et expose data', async () => {
    vi.mocked(fetchAdminAnalytics).mockResolvedValue(MOCK_DATA);

    const { result } = renderHook(() => useAdminAnalytics(30));
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual(MOCK_DATA);
    expect(result.current.error).toBeNull();
    expect(fetchAdminAnalytics).toHaveBeenCalledWith(30);
  });

  it('recharge quand days change', async () => {
    vi.mocked(fetchAdminAnalytics).mockResolvedValue(MOCK_DATA);

    const { result, rerender } = renderHook(({ days }: { days: number }) => useAdminAnalytics(days), {
      initialProps: { days: 30 },
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchAdminAnalytics).toHaveBeenCalledWith(30);

    rerender({ days: 90 });
    await waitFor(() => expect(fetchAdminAnalytics).toHaveBeenCalledWith(90));
  });

  it('gère les erreurs et expose error', async () => {
    vi.mocked(fetchAdminAnalytics).mockRejectedValue(new Error('réseau'));

    const { result } = renderHook(() => useAdminAnalytics(30));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('réseau');
    expect(result.current.data).toBeNull();
  });

  it('gère les erreurs non-Error avec message par défaut', async () => {
    vi.mocked(fetchAdminAnalytics).mockRejectedValue('string error');

    const { result } = renderHook(() => useAdminAnalytics(30));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Erreur de chargement des métriques');
  });

  it('cancelled flag — ignore les mises à jour si le composant est démonté', async () => {
    let resolvePromise!: (v: AdminAnalytics) => void;
    vi.mocked(fetchAdminAnalytics).mockReturnValue(
      new Promise((res) => {
        resolvePromise = res;
      }) as never
    );

    const { result, unmount } = renderHook(() => useAdminAnalytics(30));
    expect(result.current.loading).toBe(true);

    unmount();

    await Promise.resolve().then(() => {
      resolvePromise(MOCK_DATA);
    });

    expect(result.current.data).toBeNull();
  });
});
