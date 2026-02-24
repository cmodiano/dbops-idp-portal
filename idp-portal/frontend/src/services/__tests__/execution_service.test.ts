import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
      '/api/v1/inventory/instances/?environment=dev&server_names=srv01%2Csrv02'
    );
  });

  it('pas de server_names param sans options', async () => {
    await fetchInventoryItems('servers', 'dev');

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/v1/inventory/servers/?environment=dev');
  });

  it('pas de server_names param avec array vide', async () => {
    await fetchInventoryItems('databases', 'dev', { server_names: [] });

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/v1/inventory/databases/?environment=dev');
  });

  it('retrocompatibilite sans troisieme argument', async () => {
    await fetchInventoryItems('instances', 'staging');

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/v1/inventory/instances/?environment=staging');
  });
});

describe('fetchInventoryItems - Story 37.3 engine_type', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = mockFetch;
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: [] }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('test_fetch_inventory_items_engine_type_in_url : engine_type apparaît dans la query string', async () => {
    await fetchInventoryItems('instances', 'dev', { engine_type: 'Oracle' });

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toContain('engine_type=Oracle');
    expect(calledUrl).toBe('/api/v1/inventory/instances/?environment=dev&engine_type=Oracle');
  });

  it('test_fetch_inventory_items_cache_key_includes_engine_type : cacheKey diffère quand engine_type change', async () => {
    // Deux appels avec même type/env mais engine_type différent → deux appels fetch (pas de cache partagé)
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: [{ id: '1', name: 'test', environment: null }] }),
    });

    await fetchInventoryItems('databases', 'prod', { engine_type: 'Oracle_37_3_test_A' });
    await fetchInventoryItems('databases', 'prod', { engine_type: 'SQLServer_37_3_test_B' });

    // Les deux apiKey sont différents donc deux appels fetch
    expect(mockFetch).toHaveBeenCalledTimes(2);
    const firstUrl: string = mockFetch.mock.calls[0][0];
    const secondUrl: string = mockFetch.mock.calls[1][0];
    expect(firstUrl).toContain('engine_type=Oracle_37_3_test_A');
    expect(secondUrl).toContain('engine_type=SQLServer_37_3_test_B');
  });

  it('test_fetch_inventory_items_no_engine_type_no_param : sans engine_type l\'URL est inchangée (régression AC3)', async () => {
    // Utilise un environnement unique pour éviter le cache module-level des tests précédents
    await fetchInventoryItems('servers', 'regression_37_3');

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).not.toContain('engine_type');
    expect(calledUrl).toBe('/api/v1/inventory/servers/?environment=regression_37_3');
  });

  it('engine_type combiné avec server_names', async () => {
    await fetchInventoryItems('instances', 'dev', {
      server_names: ['srv01'],
      engine_type: 'Oracle',
    });

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl: string = mockFetch.mock.calls[0][0];
    expect(calledUrl).toContain('server_names=srv01');
    expect(calledUrl).toContain('engine_type=Oracle');
  });
});
