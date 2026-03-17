/**
 * Tests for execution_inventory.ts — ERR-FE-03 (Story 88-3)
 * Validates InventoryUnavailableError class and 503 error handling.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchInventoryItems, InventoryUnavailableError } from './execution_inventory';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

vi.mock('./logger', () => ({
  default: { debug: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock('./reference_service', () => ({
  fetchEnvironments: vi.fn().mockResolvedValue(['DEV', 'PROD']),
}));

describe('InventoryUnavailableError', () => {
  it('is an instance of Error', () => {
    const err = new InventoryUnavailableError('test', false, []);
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(InventoryUnavailableError);
  });

  it('has code INVENTORY_UNAVAILABLE', () => {
    const err = new InventoryUnavailableError('test', false, []);
    expect(err.code).toBe('INVENTORY_UNAVAILABLE');
  });

  it('stores useCache and cachedItems', () => {
    const items = [{ id: 'db1', name: 'DB1', environment: 'DEV' }];
    const err = new InventoryUnavailableError('message', true, items);
    expect(err.useCache).toBe(true);
    expect(err.cachedItems).toEqual(items);
  });

  it('sets name to InventoryUnavailableError', () => {
    const err = new InventoryUnavailableError('test', false, []);
    expect(err.name).toBe('InventoryUnavailableError');
  });
});

describe('fetchInventoryItems — ERR-FE-03', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  // ERR-FE-03 / task 5.5 — 503 with valid cache → InventoryUnavailableError(useCache=true)
  it('throws InventoryUnavailableError with useCache=true and cachedItems when 503 and valid cache', async () => {
    const cachedItems = [{ id: 'db1', name: 'DB1', environment: 'DEV' }];
    const cacheKey = 'inventory_cache_databases_DEV';
    sessionStorage.setItem(
      cacheKey,
      JSON.stringify({ items: cachedItems, timestamp: Date.now() })
    );

    vi.mocked(apiClient.apiFetchRaw).mockRejectedValue(new Error('503 Service Unavailable'));

    await expect(fetchInventoryItems('databases', 'DEV')).rejects.toSatisfy(
      (err: unknown) => {
        expect(err).toBeInstanceOf(InventoryUnavailableError);
        const invErr = err as InventoryUnavailableError;
        expect(invErr.useCache).toBe(true);
        expect(invErr.cachedItems).toEqual(cachedItems);
        return true;
      }
    );
  });

  // ERR-FE-03 / task 5.6 — 503 without valid cache → InventoryUnavailableError(useCache=false)
  it('throws InventoryUnavailableError with useCache=false when 503 and no valid cache', async () => {
    // No cache in sessionStorage
    vi.mocked(apiClient.apiFetchRaw).mockRejectedValue(new Error('503 Service Unavailable'));

    await expect(fetchInventoryItems('databases', 'DEV')).rejects.toSatisfy(
      (err: unknown) => {
        expect(err).toBeInstanceOf(InventoryUnavailableError);
        const invErr = err as InventoryUnavailableError;
        expect(invErr.useCache).toBe(false);
        expect(invErr.cachedItems).toEqual([]);
        return true;
      }
    );
  });
});
