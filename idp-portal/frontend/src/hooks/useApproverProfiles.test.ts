/**
 * Tests for useApproverProfiles hook — Story 58.4, AC2, AC4.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useApproverProfiles } from './useApproverProfiles';
import * as apiClient from '../services/api_client';

vi.mock('../services/api_client');

const mockApiFetch = vi.mocked(apiClient.apiFetch);

const mockProfiles = [
  { id: 1, name: 'DBA Approver', is_approver: true, is_admin: false, is_auditor: false, ad_group: 'GRP-DBA', description: null, permission_count: 0 },
  { id: 2, name: 'DBOPS Approver', is_approver: true, is_admin: true, is_auditor: false, ad_group: 'GRP-DBOPS', description: null, permission_count: 0 },
];

describe('useApproverProfiles', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns profiles after successful fetch', async () => {
    mockApiFetch.mockResolvedValue(mockProfiles);
    const { result } = renderHook(() => useApproverProfiles());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.profiles).toEqual([
      { id: 1, name: 'DBA Approver' },
      { id: 2, name: 'DBOPS Approver' },
    ]);
    expect(result.current.approverProfileOptions).toEqual([
      { value: 1, label: 'DBA Approver' },
      { value: 2, label: 'DBOPS Approver' },
    ]);
  });

  it('calls API with is_approver=true filter', async () => {
    mockApiFetch.mockResolvedValue(mockProfiles);
    renderHook(() => useApproverProfiles());

    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledWith('/admin/profiles/?is_approver=true'));
  });

  it('returns empty list on API failure (silent error)', async () => {
    mockApiFetch.mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useApproverProfiles());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.profiles).toEqual([]);
    expect(result.current.approverProfileOptions).toEqual([]);
  });

  it('returns empty list when API returns null', async () => {
    mockApiFetch.mockResolvedValue(null);
    const { result } = renderHook(() => useApproverProfiles());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.profiles).toEqual([]);
  });

  it('does not call API when enabled=false', async () => {
    const { result } = renderHook(() => useApproverProfiles(false));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockApiFetch).not.toHaveBeenCalled();
    expect(result.current.profiles).toEqual([]);
    expect(result.current.approverProfileOptions).toEqual([]);
  });
});
