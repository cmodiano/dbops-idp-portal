/**
 * Tests pour useFeatureFlagsAdmin hook (Story 71.1, AC2).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useFeatureFlagsAdmin } from './useFeatureFlagsAdmin';
import * as service from '../services/feature_flag_service';

vi.mock('../services/feature_flag_service');
vi.mock('../services/logger', () => ({ default: { error: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));

const mockFlags = [
  { flag_key: 'flag1', enabled: true, rollout_percent: 100, description: 'Test', updated_at: null, updated_by: 'admin' },
  { flag_key: 'flag2', enabled: false, rollout_percent: 50, description: 'Test 2', updated_at: null, updated_by: 'admin' },
];

describe('useFeatureFlagsAdmin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(service.fetchFeatureFlags).mockResolvedValue({ data: mockFlags, source: 'db' });
  });

  it('charge les flags au montage', async () => {
    const { result } = renderHook(() => useFeatureFlagsAdmin());

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.flags).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('gère les erreurs de chargement', async () => {
    vi.mocked(service.fetchFeatureFlags).mockRejectedValue(new Error('Network'));

    const { result } = renderHook(() => useFeatureFlagsAdmin());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.flags).toEqual([]);
    expect(result.current.error).toBe('Erreur lors du chargement des feature flags');
  });

  it('handleToggle met à jour le flag localement', async () => {
    vi.mocked(service.updateFeatureFlag).mockResolvedValue({ ...mockFlags[0], enabled: false });

    const { result } = renderHook(() => useFeatureFlagsAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleToggle('flag1', false);
    });

    expect(service.updateFeatureFlag).toHaveBeenCalledWith('flag1', { enabled: false });
    expect(result.current.flags.find(f => f.flag_key === 'flag1')?.enabled).toBe(false);
  });

  it('handleRolloutChange met à jour le rollout localement', async () => {
    vi.mocked(service.updateFeatureFlag).mockResolvedValue({ ...mockFlags[1], rollout_percent: 75 });

    const { result } = renderHook(() => useFeatureFlagsAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleRolloutChange('flag2', 75);
    });

    expect(service.updateFeatureFlag).toHaveBeenCalledWith('flag2', { rollout_percent: 75 });
    expect(result.current.flags.find(f => f.flag_key === 'flag2')?.rollout_percent).toBe(75);
  });
});
