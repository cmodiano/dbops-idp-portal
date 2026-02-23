/**
 * Tests for useAAPTemplates hook — Story 31.5, Task 8.5.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAAPTemplates } from './useAAPTemplates';

vi.mock('../services/integrations_service', () => ({
  getAAPTemplates: vi.fn(),
}));

import { getAAPTemplates } from '../services/integrations_service';
const mockGetAAPTemplates = getAAPTemplates as ReturnType<typeof vi.fn>;

describe('useAAPTemplates', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('returns fallback=true when integrationId is null', () => {
    const { result } = renderHook(() => useAAPTemplates(null, 'job_template'));
    expect(result.current.fallback).toBe(true);
    expect(result.current.templates).toEqual([]);
    expect(result.current.loading).toBe(false);
  });

  it('returns fallback=true when integrationId is undefined', () => {
    const { result } = renderHook(() => useAAPTemplates(undefined, 'job_template'));
    expect(result.current.fallback).toBe(true);
    expect(result.current.templates).toEqual([]);
  });

  it('fetches templates when integrationId is provided', async () => {
    mockGetAAPTemplates.mockResolvedValue({
      templates: [{ id: 10, name: 'Deploy', description: '' }],
      fallback: false,
    });

    const { result } = renderHook(() => useAAPTemplates(1, 'job_template'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.templates).toEqual([{ id: 10, name: 'Deploy', description: '' }]);
    expect(result.current.fallback).toBe(false);
    expect(mockGetAAPTemplates).toHaveBeenCalledWith(1, 'job_template', undefined);
  });

  it('sets fallback=true on API error', async () => {
    mockGetAAPTemplates.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useAAPTemplates(1, 'job_template'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.fallback).toBe(true);
    expect(result.current.error).toBe('Network error');
  });

  it('uses sessionStorage cache on second call', async () => {
    mockGetAAPTemplates.mockResolvedValue({
      templates: [{ id: 10, name: 'Deploy', description: '' }],
      fallback: false,
    });

    // First render: fetches from API
    const { result, unmount } = renderHook(() => useAAPTemplates(1, 'job_template'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockGetAAPTemplates).toHaveBeenCalledTimes(1);
    unmount();

    // Second render: should use cache
    mockGetAAPTemplates.mockClear();
    const { result: result2 } = renderHook(() => useAAPTemplates(1, 'job_template'));
    // Cache hit — templates should be available immediately
    expect(result2.current.templates).toEqual([{ id: 10, name: 'Deploy', description: '' }]);
    expect(result2.current.fallback).toBe(false);
    expect(mockGetAAPTemplates).not.toHaveBeenCalled();
  });
});
