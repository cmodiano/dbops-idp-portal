/**
 * Tests for usePendingApprovalsCount hook (Story 71.11, AC #5).
 * Polling + visibilitychange + AuthContext.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// --- Mocks définis avant les imports ---

vi.mock('../../services/execution_service', () => ({
  getPendingApprovalsCount: vi.fn(),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  default: {
    error: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
  },
}));

import { usePendingApprovalsCount } from '../usePendingApprovalsCount';
import { getPendingApprovalsCount } from '../../services/execution_service';
import { useAuth } from '../../contexts/AuthContext';
import logger from '../../services/logger';

const mockGetPendingApprovalsCount = vi.mocked(getPendingApprovalsCount);
const mockUseAuth = vi.mocked(useAuth);

describe('usePendingApprovalsCount', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    vi.clearAllMocks();
    // Default: DBA user
    mockUseAuth.mockReturnValue({ user: { profile: 'dba' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(0);
    // Reset document.hidden
    Object.defineProperty(document, 'hidden', { value: false, writable: true, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('profil non-DBA/DBOPS — count=0, loading=false, pas d\'appel API', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dev' } } as any);

    const { result } = renderHook(() => usePendingApprovalsCount(15000));

    // Flush the initial async fetchCount call
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount).not.toHaveBeenCalled();
    expect(result.current.count).toBe(0);
    expect(result.current.loading).toBe(false);
  });

  it('profil DBA — appel API initial, count mis à jour', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(5);

    const { result } = renderHook(() => usePendingApprovalsCount(15000));

    // Flush async fetch (initial call only, don't run interval)
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.count).toBe(5);
    expect(result.current.loading).toBe(false);
    expect(mockGetPendingApprovalsCount).toHaveBeenCalled();
  });

  it('profil dba_applicatif — considéré comme DBA', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba_applicatif' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(3);

    const { result } = renderHook(() => usePendingApprovalsCount(15000));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount).toHaveBeenCalled();
    expect(result.current.count).toBe(3);
  });

  it('profil dba_infrastructure — considéré comme DBA', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba_infrastructure' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(2);

    const { result } = renderHook(() => usePendingApprovalsCount(15000));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount).toHaveBeenCalled();
    expect(result.current.count).toBe(2);
  });

  it('profil dbops — peut approuver', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dbops' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(1);

    const { result } = renderHook(() => usePendingApprovalsCount(15000));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount).toHaveBeenCalled();
    expect(result.current.count).toBe(1);
  });

  it('erreur API — error non-null, count=0, logger.error appelé', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba' } } as any);
    mockGetPendingApprovalsCount.mockRejectedValue(new Error('Server error'));

    const { result } = renderHook(() => usePendingApprovalsCount(15000));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.count).toBe(0);
    expect(logger.error).toHaveBeenCalled();
  });

  it('polling — fetchCount rappelé après l\'intervalle', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(0);

    renderHook(() => usePendingApprovalsCount(15000));

    // Initial fetch
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const callsAfterInit = mockGetPendingApprovalsCount.mock.calls.length;
    expect(callsAfterInit).toBeGreaterThanOrEqual(1);

    // Advance timer to trigger polling interval
    await act(async () => {
      vi.advanceTimersByTime(15000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount.mock.calls.length).toBeGreaterThan(callsAfterInit);
  });

  it('visibilitychange — fetchCount rappelé quand onglet redevient visible', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(0);

    renderHook(() => usePendingApprovalsCount(15000));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const callsBeforeVisibility = mockGetPendingApprovalsCount.mock.calls.length;

    // Simulate tab becoming visible
    Object.defineProperty(document, 'hidden', { value: false, writable: true, configurable: true });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount.mock.calls.length).toBeGreaterThan(callsBeforeVisibility);
  });

  it('cleanup — interval et event listener supprimés à l\'unmount', async () => {
    mockUseAuth.mockReturnValue({ user: { profile: 'dba' } } as any);
    mockGetPendingApprovalsCount.mockResolvedValue(0);

    const { unmount } = renderHook(() => usePendingApprovalsCount(15000));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const callsBeforeUnmount = mockGetPendingApprovalsCount.mock.calls.length;

    unmount();

    // Advance time — should not trigger more API calls after unmount
    await act(async () => {
      vi.advanceTimersByTime(30000);
      await Promise.resolve();
    });

    expect(mockGetPendingApprovalsCount.mock.calls.length).toBe(callsBeforeUnmount);
  });
});
