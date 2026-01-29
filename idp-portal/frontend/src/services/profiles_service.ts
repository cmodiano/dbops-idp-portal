/**
 * Profiles service (Story 2.9, FR25a). CRUD for dynamic profiles.
 * Requires DBOPS profile.
 */

import { apiFetch } from './api_client';
import type { ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem } from '../types/api';

export async function getProfiles(): Promise<ProfileListItem[]> {
  const res = await apiFetch<ProfileListItem[]>('/admin/profiles');
  return res ?? [];
}

export async function getProfile(id: number): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/admin/profiles/${id}`);
}

export async function createProfile(payload: ProfileCreate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>('/admin/profiles', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProfile(id: number, payload: ProfileUpdate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/admin/profiles/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteProfile(id: number): Promise<void> {
  await apiFetch<void>(`/admin/profiles/${id}`, { method: 'DELETE' });
}
