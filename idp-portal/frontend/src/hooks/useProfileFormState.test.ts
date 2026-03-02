/**
 * Tests pour useProfileFormState (Story 35.3, Task 4.3).
 * Vérifie que le hook encapsule correctement les appels de services profiles_service et admin_service.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useProfileFormState } from './useProfileFormState';

vi.mock('../services/profiles_service', () => ({
  getProfileActions: vi.fn().mockResolvedValue({
    actions_type: 'all',
    action_ids: [],
    tag_patterns: [],
    environments: ['DEV', 'PROD'],
  }),
  getProfileTargets: vi.fn().mockResolvedValue({
    targets_type: 'all',
    target_names: [],
    target_patterns: [],
    exclusion_patterns: [],
  }),
  putProfileActions: vi.fn().mockResolvedValue({}),
  putProfileTargets: vi.fn().mockResolvedValue({}),
  createProfile: vi.fn().mockResolvedValue({ id: 99, name: 'Test', ad_group: 'GRP', is_admin: false, is_auditor: false, created_at: '', updated_at: '' }),
  updateProfile: vi.fn().mockResolvedValue({ id: 5, name: 'Updated', ad_group: 'GRP', is_admin: false, is_auditor: false, created_at: '', updated_at: '' }),
}));

vi.mock('../services/admin_service', () => ({
  getAdminActions: vi.fn().mockResolvedValue({
    data: [
      { id: 1, name: 'Action Alpha', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
      { id: 2, name: 'Action Beta', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
    ],
  }),
  getTags: vi.fn().mockResolvedValue([{ name: 'oracle' }, { name: 'sql' }]),
}));

import {
  getProfileActions,
  getProfileTargets,
  putProfileActions,
  putProfileTargets,
  createProfile,
  updateProfile,
} from '../services/profiles_service';
import { getAdminActions, getTags } from '../services/admin_service';

describe('useProfileFormState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('charge actionsOptions et tagsOptions en mode création (sans editProfileId)', async () => {
    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: null })
    );

    await waitFor(() => {
      expect(result.current.actionsOptions).toHaveLength(2);
      expect(result.current.tagsOptions).toHaveLength(2);
    });

    expect(getAdminActions).toHaveBeenCalledTimes(1);
    expect(getTags).toHaveBeenCalledTimes(1);
    expect(getProfileActions).not.toHaveBeenCalled();
  });

  it('charge les permissions en mode édition (avec editProfileId)', async () => {
    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: 5 })
    );

    await waitFor(() => {
      expect(result.current.profileActionsPerms).not.toBeNull();
      expect(result.current.profileTargetsPerms).not.toBeNull();
    });

    expect(getProfileActions).toHaveBeenCalledWith(5);
    expect(getProfileTargets).toHaveBeenCalledWith(5);
    expect(result.current.profileActionsPerms?.actions_type).toBe('all');
    expect(result.current.profileActionsPerms?.environments).toEqual(['DEV', 'PROD']);
  });

  it('expose les handlers putProfileActions et putProfileTargets', async () => {
    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: null })
    );

    await result.current.handlePutProfileActions(10, {
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: [],
    });

    expect(putProfileActions).toHaveBeenCalledWith(10, {
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: [],
    });

    await result.current.handlePutProfileTargets(10, {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
    });

    expect(putProfileTargets).toHaveBeenCalledWith(10, {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
    });
  });

  it('handleCreateProfile appelle createProfile avec le payload', async () => {
    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: null })
    );

    const created = await result.current.handleCreateProfile({
      name: 'Test',
      ad_group: 'GRP',
      is_admin: false,
      is_auditor: false,
    });

    expect(createProfile).toHaveBeenCalledWith({ name: 'Test', ad_group: 'GRP', is_admin: false, is_auditor: false });
    expect(created.id).toBe(99);
  });

  it('handleUpdateProfile appelle updateProfile avec le payload', async () => {
    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: 5 })
    );

    const updated = await result.current.handleUpdateProfile(5, {
      name: 'Updated',
      ad_group: 'GRP',
      is_admin: false,
      is_auditor: false,
    });

    expect(updateProfile).toHaveBeenCalledWith(5, {
      name: 'Updated',
      ad_group: 'GRP',
      is_admin: false,
      is_auditor: false,
    });
    expect(updated.name).toBe('Updated');
  });

  it('réinitialise profileActionsPerms et profileTargetsPerms quand open passe à false', async () => {
    const { result, rerender } = renderHook(
      ({ open, editProfileId }: { open: boolean; editProfileId: number | null }) =>
        useProfileFormState({ open, editProfileId }),
      { initialProps: { open: true, editProfileId: 5 } }
    );

    await waitFor(() => {
      expect(result.current.profileActionsPerms).not.toBeNull();
    });

    rerender({ open: false, editProfileId: 5 });

    await waitFor(() => {
      expect(result.current.profileActionsPerms).toBeNull();
      expect(result.current.profileTargetsPerms).toBeNull();
    });
  });

  it('ne charge rien quand open=false', () => {
    renderHook(() => useProfileFormState({ open: false, editProfileId: 5 }));
    expect(getProfileActions).not.toHaveBeenCalled();
    expect(getAdminActions).not.toHaveBeenCalled();
  });

  it('gère l\'erreur en mode édition et retourne des tableaux vides avec loadingData=false', async () => {
    vi.mocked(getProfileActions).mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: 5 })
    );

    await waitFor(() => {
      expect(result.current.loadingData).toBe(false);
    });

    expect(result.current.actionsOptions).toEqual([]);
    expect(result.current.tagsOptions).toEqual([]);
  });

  it('gère l\'erreur en mode création et retourne des tableaux vides', async () => {
    vi.mocked(getAdminActions).mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: null })
    );

    await waitFor(() => {
      expect(result.current.loadingData).toBe(false);
    });

    expect(result.current.actionsOptions).toEqual([]);
    expect(result.current.tagsOptions).toEqual([]);
  });

  it('active loadingData en mode création pendant le chargement', async () => {
    // Vérifier que loadingData passe à false après chargement en mode création
    const { result } = renderHook(() =>
      useProfileFormState({ open: true, editProfileId: null })
    );

    await waitFor(() => {
      expect(result.current.loadingData).toBe(false);
      expect(result.current.actionsOptions).toHaveLength(2);
    });
  });
});
