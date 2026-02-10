import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchInventoryItems } from '../execution_service';

describe('fetchInventoryItems - Story 23.6', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = mockFetch;
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: [] }),
    });
  });

  it('construit query string avec server_names', async () => {
    await fetchInventoryItems('instances', 'dev', {
      server_names: ['srv01', 'srv02'],
    });

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe(
      '/api/v1/inventory/instances?environment=dev&server_names=srv01%2Csrv02'
    );
  });

  it('pas de server_names param sans options', async () => {
    await fetchInventoryItems('servers', 'dev');

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/v1/inventory/servers?environment=dev');
  });

  it('pas de server_names param avec array vide', async () => {
    await fetchInventoryItems('databases', 'dev', { server_names: [] });

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/v1/inventory/databases?environment=dev');
  });

  it('retrocompatibilite sans troisieme argument', async () => {
    await fetchInventoryItems('instances', 'staging');

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/v1/inventory/instances?environment=staging');
  });
});
