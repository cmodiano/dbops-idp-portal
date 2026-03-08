/**
 * Profiles service (Story 2.9, FR25a). CRUD for dynamic profiles.
 * Story 2.10: get/put profile actions permissions. Requires DBOPS profile.
 * Story 2.11: get/put profile targets permissions.
 * Story 2.13: export/import YAML (AC1, AC2).
 */

import { apiFetch, apiFetchBlob, apiPostFormData } from './api_client';
import type {
  ProfileCreate,
  ProfileUpdate,
  ProfileResponse,
  ProfileListItem,
  ProfileActionPermissionsResponse,
  ProfileActionPermissionsUpdate,
  ProfileTargetPermissionsResponse,
  ProfileTargetPermissionsUpdate,
} from '../types/api';

export async function getProfiles(): Promise<ProfileListItem[]> {
  const res = await apiFetch<ProfileListItem[]>('/admin/profiles/');
  return res ?? [];
}

export async function getProfile(id: number): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/admin/profiles/${id}/`);
}

export async function createProfile(payload: ProfileCreate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>('/admin/profiles/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProfile(id: number, payload: ProfileUpdate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/admin/profiles/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteProfile(id: number): Promise<void> {
  await apiFetch<void>(`/admin/profiles/${id}/`, { method: 'DELETE' });
}

/** Story 2.10: Get actions/env permissions for a profile (AC2–AC5). */
export async function getProfileActions(profileId: number): Promise<ProfileActionPermissionsResponse> {
  return apiFetch<ProfileActionPermissionsResponse>(`/admin/profiles/${profileId}/actions/`);
}

/** Story 2.10: Set actions/env permissions for a profile (AC2–AC5). */
export async function putProfileActions(
  profileId: number,
  payload: ProfileActionPermissionsUpdate,
): Promise<ProfileActionPermissionsResponse> {
  return apiFetch<ProfileActionPermissionsResponse>(`/admin/profiles/${profileId}/actions/`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/** Story 2.11: Get target permissions for a profile (AC1–AC5). */
export async function getProfileTargets(profileId: number): Promise<ProfileTargetPermissionsResponse> {
  return apiFetch<ProfileTargetPermissionsResponse>(`/admin/profiles/${profileId}/targets/`);
}

/** Story 2.11: Set target permissions for a profile (AC2, AC3, AC5). */
export async function putProfileTargets(
  profileId: number,
  payload: ProfileTargetPermissionsUpdate,
): Promise<ProfileTargetPermissionsResponse> {
  return apiFetch<ProfileTargetPermissionsResponse>(`/admin/profiles/${profileId}/targets/`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/** Story 2.13: Export profiles as YAML file (AC1). Triggers browser download. */
export async function exportProfilesYaml(): Promise<void> {
  const blob = await apiFetchBlob('/admin/profiles/export/');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'profiles.yaml';
  a.click();
  URL.revokeObjectURL(url);
}

/** Story 2.13: Import profiles from YAML file (AC2). Returns created/updated counts. */
export async function importProfilesYaml(file: File): Promise<{ created: number; updated: number }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiPostFormData<{ created: number; updated: number }>(
    '/admin/profiles/import/',
    formData,
  );
  return res.data;
}

/** Story 64.13: Export a single profile as YAML file. Triggers browser download. */
export async function exportProfileYamlById(id: number, name: string): Promise<void> {
  const blob = await apiFetchBlob(`/admin/profiles/${id}/export/yaml/`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `profiles-${name}.yaml`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
