/**
 * useProfileFormState — Encapsulation DIP des appels de services pour ProfileForm et ProfileWizard.
 * Story 35.3 (SOLID-FE-4): Supprime les imports directs de profiles_service et admin_service dans ces composants.
 *
 * Wraps :
 * - getProfileActions, getProfileTargets, putProfileActions, putProfileTargets (profiles_service)
 * - createProfile, updateProfile (profiles_service)
 * - getAdminActions, getTags (admin_service)
 *
 * Pattern :
 * - `actionsOptions` et `tagsOptions` chargés via useEffect quand open=true
 * - `profileActionsPerms` et `profileTargetsPerms` chargés en mode édition
 * - Handlers exposés pour les opérations de sauvegarde
 */

import { useEffect, useState } from 'react';
import type {
  ProfileCreate,
  ProfileUpdate,
  ProfileResponse,
  ProfileActionPermissionsResponse,
  ProfileActionPermissionsUpdate,
  ProfileTargetPermissionsResponse,
  ProfileTargetPermissionsUpdate,
} from '../types/api';
import {
  createProfile,
  updateProfile,
  getProfileActions,
  getProfileTargets,
  putProfileActions,
  putProfileTargets,
} from '../services/profiles_service';
import { getAdminActions, getTags } from '../services/admin_service';

export interface UseProfileFormStateOptions {
  open: boolean;
  /** Identifiant du profil en cours d'édition (undefined = mode création). */
  editProfileId?: number | null;
}

export interface UseProfileFormStateReturn {
  actionsOptions: { id: number; name: string }[];
  tagsOptions: string[];
  loadingData: boolean;
  /** Permissions actions chargées (null jusqu'à la fin du chargement en mode édition). */
  profileActionsPerms: ProfileActionPermissionsResponse | null;
  /** Permissions targets chargées (null jusqu'à la fin du chargement en mode édition). */
  profileTargetsPerms: ProfileTargetPermissionsResponse | null;
  /** Handlers de sauvegarde */
  handlePutProfileActions: (profileId: number, payload: ProfileActionPermissionsUpdate) => Promise<void>;
  handlePutProfileTargets: (profileId: number, payload: ProfileTargetPermissionsUpdate) => Promise<void>;
  /** Création / mise à jour du profil (pour ProfileWizard qui appelle directement les services) */
  handleCreateProfile: (payload: ProfileCreate) => Promise<ProfileResponse>;
  handleUpdateProfile: (id: number, payload: ProfileUpdate) => Promise<ProfileResponse>;
}

export function useProfileFormState({
  open,
  editProfileId,
}: UseProfileFormStateOptions): UseProfileFormStateReturn {
  const [actionsOptions, setActionsOptions] = useState<{ id: number; name: string }[]>([]);
  const [tagsOptions, setTagsOptions] = useState<string[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [profileActionsPerms, setProfileActionsPerms] = useState<ProfileActionPermissionsResponse | null>(null);
  const [profileTargetsPerms, setProfileTargetsPerms] = useState<ProfileTargetPermissionsResponse | null>(null);

  useEffect(() => {
    if (!open) {
      // Réinitialiser les données chargées à la fermeture
      setProfileActionsPerms(null);
      setProfileTargetsPerms(null);
      return;
    }

    let cancelled = false;

    if (editProfileId != null) {
      // Mode édition : chargement des permissions + données de référence
      // Conserver le pattern queueMicrotask pour Oracle/React batch update (point d'attention #4 story 35.3)
      queueMicrotask(() => {
        if (!cancelled) setLoadingData(true);
      });

      Promise.all([
        getProfileActions(editProfileId),
        getProfileTargets(editProfileId),
        getAdminActions().then((r) => r.data),
        getTags(),
      ])
        .then(([perms, targetsPerms, actions, tags]) => {
          if (cancelled) return;
          setProfileActionsPerms(perms);
          setProfileTargetsPerms(targetsPerms);
          setActionsOptions(actions.map((a) => ({ id: a.id, name: a.name })));
          setTagsOptions(tags.map((t) => t.name));
        })
        .catch(() => {
          if (cancelled) return;
          setActionsOptions([]);
          setTagsOptions([]);
        })
        .finally(() => {
          if (!cancelled) setLoadingData(false);
        });
    } else {
      // Mode création : uniquement les données de référence
      // Conserver le pattern queueMicrotask pour Oracle/React batch update (point d'attention #4 story 35.3)
      queueMicrotask(() => {
        if (!cancelled) setLoadingData(true);
      });

      Promise.all([getAdminActions().then((r) => r.data), getTags()])
        .then(([actions, tags]) => {
          if (cancelled) return;
          setActionsOptions(actions.map((a) => ({ id: a.id, name: a.name })));
          setTagsOptions(tags.map((t) => t.name));
        })
        .catch(() => {
          if (cancelled) return;
          setActionsOptions([]);
          setTagsOptions([]);
        })
        .finally(() => {
          if (!cancelled) setLoadingData(false);
        });
    }

    return () => {
      cancelled = true;
    };
  }, [open, editProfileId]);

  const handlePutProfileActions = async (
    profileId: number,
    payload: ProfileActionPermissionsUpdate
  ): Promise<void> => {
    await putProfileActions(profileId, payload);
  };

  const handlePutProfileTargets = async (
    profileId: number,
    payload: ProfileTargetPermissionsUpdate
  ): Promise<void> => {
    await putProfileTargets(profileId, payload);
  };

  const handleCreateProfile = async (payload: ProfileCreate): Promise<ProfileResponse> => {
    return createProfile(payload);
  };

  const handleUpdateProfile = async (id: number, payload: ProfileUpdate): Promise<ProfileResponse> => {
    return updateProfile(id, payload);
  };

  return {
    actionsOptions,
    tagsOptions,
    loadingData,
    profileActionsPerms,
    profileTargetsPerms,
    handlePutProfileActions,
    handlePutProfileTargets,
    handleCreateProfile,
    handleUpdateProfile,
  };
}
