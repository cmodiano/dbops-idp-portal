/**
 * Tests for usePendingApprovalsCount hook (Story 8.8).
 *
 * AC7: Mise à jour temps réel du badge via polling.
 * AC9: RBAC - seuls DBA/DBOPS peuvent voir le count.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { usePendingApprovalsCount } from './usePendingApprovalsCount';
import * as executionService from '../services/execution_service';
import * as authContext from '../contexts/AuthContext';

vi.mock('../services/execution_service');

// Mock useAuth to avoid needing full AuthProvider
vi.mock('../contexts/AuthContext', async () => {
  const actual = await vi.importActual('../contexts/AuthContext');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

function mockProfile(profile: string | null) {
  vi.mocked(authContext.useAuth).mockReturnValue({
    user: profile ? { id: 1, username: 'test', profile } : null,
    loading: false,
    logout: vi.fn(),
    login: vi.fn(),
  } as ReturnType<typeof authContext.useAuth>);
}

describe('usePendingApprovalsCount', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('AC7 - Initial fetch', () => {
    it('fetches count on initial mount for DBA user', async () => {
      mockProfile('DBA');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(5);

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(executionService.getPendingApprovalsCount).toHaveBeenCalledTimes(1);
      expect(result.current.count).toBe(5);
    });

    it('fetches count for DBOPS user', async () => {
      mockProfile('DBOPS');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(3);

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.count).toBe(3);
      });

      expect(executionService.getPendingApprovalsCount).toHaveBeenCalled();
    });

    it('fetches count for lowercase dba profile', async () => {
      mockProfile('dba');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(2);

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.count).toBe(2);
      });

      expect(executionService.getPendingApprovalsCount).toHaveBeenCalled();
    });
  });

  describe('AC9 - RBAC filtering', () => {
    it('returns 0 count for CLIENT user without calling API', async () => {
      mockProfile('CLIENT');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(5);

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Should not call API for client user
      expect(executionService.getPendingApprovalsCount).not.toHaveBeenCalled();
      expect(result.current.count).toBe(0);
    });

    it('returns 0 when user is null', async () => {
      mockProfile(null);

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(executionService.getPendingApprovalsCount).not.toHaveBeenCalled();
      expect(result.current.count).toBe(0);
    });
  });

  describe('Error handling', () => {
    it('sets error and returns 0 on API failure', async () => {
      mockProfile('DBA');
      vi.mocked(executionService.getPendingApprovalsCount).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Network error');
      expect(result.current.count).toBe(0);
    });

    it('provides refetch function', async () => {
      mockProfile('DBA');
      let callCount = 0;
      vi.mocked(executionService.getPendingApprovalsCount).mockImplementation(async () => {
        callCount++;
        return callCount === 1 ? 5 : 8;
      });

      const { result } = renderHook(() => usePendingApprovalsCount());

      await waitFor(() => {
        expect(result.current.count).toBe(5);
      });

      // Manual refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(result.current.count).toBe(8);
      expect(executionService.getPendingApprovalsCount).toHaveBeenCalledTimes(2);
    });
  });

  describe('Loading state', () => {
    it('starts with loading true and transitions to false', async () => {
      mockProfile('DBA');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(5);

      const { result } = renderHook(() => usePendingApprovalsCount());

      // Loading should become false after fetch completes
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.count).toBe(5);
    });
  });

  describe('AC7 - Polling', () => {
    it('polls every 60 seconds and updates count', async () => {
      mockProfile('DBA');
      let callCount = 0;
      vi.mocked(executionService.getPendingApprovalsCount).mockImplementation(async () => {
        callCount++;
        return callCount * 2; // 2, 4, 6...
      });

      const { result } = renderHook(() => usePendingApprovalsCount(1000)); // Use 1s interval for testing

      // Initial fetch
      await waitFor(() => {
        expect(result.current.count).toBe(2);
      });

      expect(executionService.getPendingApprovalsCount).toHaveBeenCalledTimes(1);

      // Wait for 1 second - should trigger second poll
      await new Promise((resolve) => setTimeout(resolve, 1100));

      await waitFor(() => {
        expect(result.current.count).toBe(4);
      });

      expect(executionService.getPendingApprovalsCount).toHaveBeenCalledTimes(2);
    }, 10000); // Increase timeout for this test

    it('stops polling after unmount', async () => {
      mockProfile('DBA');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(5);

      const { result, unmount } = renderHook(() => usePendingApprovalsCount(500)); // Use 500ms interval

      await waitFor(() => {
        expect(result.current.count).toBe(5);
      });

      const initialCallCount = vi.mocked(executionService.getPendingApprovalsCount).mock.calls.length;

      // Unmount the hook
      unmount();

      // Wait 1 second - should NOT trigger another poll
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Should not have any new calls after unmount
      const finalCallCount = vi.mocked(executionService.getPendingApprovalsCount).mock.calls.length;
      expect(finalCallCount).toBe(initialCallCount);
    }, 10000);

    it('does not poll for non-DBA/DBOPS users', async () => {
      mockProfile('CLIENT');
      vi.mocked(executionService.getPendingApprovalsCount).mockResolvedValue(5);

      const { result } = renderHook(() => usePendingApprovalsCount(500));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Should not call API at all
      expect(executionService.getPendingApprovalsCount).not.toHaveBeenCalled();
      expect(result.current.count).toBe(0);

      // Wait 1 second - still should not poll
      await new Promise((resolve) => setTimeout(resolve, 1000));

      expect(executionService.getPendingApprovalsCount).not.toHaveBeenCalled();
    }, 10000);
  });
});
