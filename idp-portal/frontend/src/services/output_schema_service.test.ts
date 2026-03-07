/**
 * Tests pour output_schema_service (Story 63.3).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchAvailableVariables } from './output_schema_service';
import * as apiClient from './api_client';

vi.mock('./api_client');

describe('output_schema_service — fetchAvailableVariables', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('appelle apiFetch avec la bonne URL', async () => {
    const mockData = [
      {
        step_id: 'step-1',
        step_name: 'Créer changement',
        step_type: 'service_call',
        variables: [
          { name: 'change_number', path: '$.number', type: 'string', description: 'Numéro du change' },
        ],
      },
    ];
    vi.mocked(apiClient.apiFetch).mockResolvedValue(mockData);

    const result = await fetchAvailableVariables(42);

    expect(apiClient.apiFetch).toHaveBeenCalledWith(
      '/output-schemas/workflows/42/available-variables/',
    );
    expect(result).toEqual(mockData);
  });

  it('propage les erreurs réseau', async () => {
    vi.mocked(apiClient.apiFetch).mockRejectedValue(new Error('Network error'));

    await expect(fetchAvailableVariables(1)).rejects.toThrow('Network error');
  });
});
