/**
 * Tests for profiles_service (Story 71.11, AC #2).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  getProfiles,
  getProfile,
  createProfile,
  updateProfile,
  deleteProfile,
  getProfileActions,
  putProfileActions,
  getProfileTargets,
  putProfileTargets,
  exportProfilesYaml,
  exportProfileYamlById,
} from './profiles_service';
import * as apiClient from './api_client';

const mockCreateObjectURL = vi.fn().mockReturnValue('blob:test');
const mockRevokeObjectURL = vi.fn();
const mockAnchorClick = vi.fn();

describe('profiles_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockCreateObjectURL.mockReturnValue('blob:test');
    Object.defineProperty(window, 'URL', {
      value: { createObjectURL: mockCreateObjectURL, revokeObjectURL: mockRevokeObjectURL },
      writable: true,
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(mockAnchorClick);
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => undefined as any);
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => undefined as any);
  });

  describe('getProfiles', () => {
    it('retourne un tableau vide si l\'API retourne null (fallback ?? [])', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(null as any);

      const result = await getProfiles();

      expect(result).toEqual([]);
    });

    it('retourne la liste si l\'API retourne un tableau', async () => {
      const mockProfiles = [{ id: 1, name: 'dba' }];
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockProfiles as any);

      const result = await getProfiles();

      expect(result).toEqual(mockProfiles);
    });
  });

  describe('getProfile', () => {
    it('appelle GET /admin/profiles/{id}/', async () => {
      const mockProfile = { id: 3, name: 'dbops' };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockProfile as any);

      const result = await getProfile(3);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/3/');
      expect(result).toEqual(mockProfile);
    });
  });

  describe('createProfile', () => {
    it('envoie POST /admin/profiles/ avec body JSON', async () => {
      const payload = { name: 'new-profile', description: 'test' } as any;
      const mockResponse = { id: 10, ...payload };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await createProfile(payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('updateProfile', () => {
    it('envoie PUT /admin/profiles/{id}/ avec body JSON', async () => {
      const payload = { name: 'updated' } as any;
      const mockResponse = { id: 5, name: 'updated' };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await updateProfile(5, payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/5/', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('deleteProfile', () => {
    it('envoie DELETE /admin/profiles/{id}/', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(undefined as any);

      await deleteProfile(5);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/5/', { method: 'DELETE' });
    });
  });

  describe('getProfileActions', () => {
    it('appelle GET /admin/profiles/{profileId}/actions/', async () => {
      const mockResponse = { permissions: [] };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await getProfileActions(3);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/3/actions/');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('putProfileActions', () => {
    it('envoie PUT /admin/profiles/{profileId}/actions/ avec body JSON', async () => {
      const payload = { permissions: [] } as any;
      const mockResponse = { permissions: [] };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await putProfileActions(3, payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/3/actions/', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getProfileTargets', () => {
    it('appelle GET /admin/profiles/{profileId}/targets/', async () => {
      const mockResponse = { permissions: [] };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await getProfileTargets(4);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/4/targets/');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('putProfileTargets', () => {
    it('envoie PUT /admin/profiles/{profileId}/targets/ avec body JSON', async () => {
      const payload = { permissions: [] } as any;
      const mockResponse = { permissions: [] };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await putProfileTargets(4, payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/profiles/4/targets/', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('exportProfilesYaml', () => {
    it('télécharge profiles.yaml via apiFetchBlob', async () => {
      const mockBlob = new Blob(['yaml'], { type: 'application/x-yaml' });
      vi.spyOn(apiClient, 'apiFetchBlob').mockResolvedValue(mockBlob);

      await exportProfilesYaml();

      expect(apiClient.apiFetchBlob).toHaveBeenCalledWith('/admin/profiles/export/');
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
      expect(mockAnchorClick).toHaveBeenCalled();
      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:test');
    });
  });

  describe('exportProfileYamlById', () => {
    it('télécharge profiles-{name}.yaml via apiFetchBlob', async () => {
      const mockBlob = new Blob(['yaml'], { type: 'application/x-yaml' });
      vi.spyOn(apiClient, 'apiFetchBlob').mockResolvedValue(mockBlob);

      await exportProfileYamlById(7, 'my-profile');

      expect(apiClient.apiFetchBlob).toHaveBeenCalledWith('/admin/profiles/7/export/yaml/');
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
      expect(mockAnchorClick).toHaveBeenCalled();
      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:test');
    });
  });
});
