/**
 * Tests for integrations_service (Story 2.28). CRUD via apiFetch.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { setAuthAccessors } from './api_client';
import {
  getIntegrations,
  getIntegration,
  createIntegration,
  updateIntegration,
  deleteIntegration,
} from './integrations_service';

const base = {
  id: 1,
  type: 'aap' as const,
  name: 'AAP Prod',
  base_url: 'https://aap.example.com',
  credential_ref: null as string | null,
  icon: null as string | null,
  created_at: '2026-01-28T10:00:00Z',
  updated_at: '2026-01-28T10:00:00Z',
};

describe('integrations_service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  it('getIntegrations calls GET /admin/integrations and returns list', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: [base] }),
    });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    const result = await getIntegrations();
    expect(result).toEqual([base]);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/integrations',
      expect.objectContaining({ headers: expect.any(Object) })
    );
  });

  it('getIntegrations returns empty array when data is undefined', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    const result = await getIntegrations();
    expect(result).toEqual([]);
  });

  it('getIntegration calls GET /admin/integrations/:id and returns integration', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: base }),
    });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    const result = await getIntegration(1);
    expect(result).toEqual(base);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/integrations/1',
      expect.any(Object)
    );
  });

  it('createIntegration calls POST /admin/integrations with payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ data: base }),
    });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    const payload = {
      type: 'aap' as const,
      name: 'AAP Prod',
      base_url: 'https://aap.example.com',
      credential_ref: null as string | null,
      icon: null as string | null,
    };
    const result = await createIntegration(payload);
    expect(result).toEqual(base);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/integrations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('updateIntegration calls PUT /admin/integrations/:id with payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { ...base, name: 'AAP Updated' } }),
    });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    const payload = { name: 'AAP Updated' };
    const result = await updateIntegration(1, payload);
    expect(result.name).toBe('AAP Updated');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/integrations/1',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(payload),
      })
    );
  });

  it('deleteIntegration calls DELETE /admin/integrations/:id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => undefined,
    });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    await deleteIntegration(1);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/integrations/1',
      expect.objectContaining({ method: 'DELETE' })
    );
  });
});
