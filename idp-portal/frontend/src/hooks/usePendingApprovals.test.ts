/**
 * Tests for usePendingApprovals hook (Story 71.11, AC #4).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePendingApprovals } from './usePendingApprovals';
import * as executionService from '../services/execution_service';

vi.mock('../services/execution_service', () => ({
  approveExecution: vi.fn(),
  rejectExecution: vi.fn(),
}));

describe('usePendingApprovals', () => {
  const mockOnActionComplete = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('approve', () => {
    it('retourne { success: true } et appelle onActionComplete en cas de succès', async () => {
      vi.mocked(executionService.approveExecution).mockResolvedValue(undefined as any);

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      let outcome: any;
      await act(async () => {
        outcome = await result.current.approve(10);
      });

      expect(executionService.approveExecution).toHaveBeenCalledWith(10, undefined);
      expect(mockOnActionComplete).toHaveBeenCalled();
      expect(outcome).toEqual({ success: true });
    });

    it('retourne { success: false, error } si approveExecution rejette', async () => {
      vi.mocked(executionService.approveExecution).mockRejectedValue(new Error('Permission denied'));

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      let outcome: any;
      await act(async () => {
        outcome = await result.current.approve(10);
      });

      expect(outcome.success).toBe(false);
      expect(outcome.error).toBe('Permission denied');
    });

    it('approveLoading=false après résolution', async () => {
      vi.mocked(executionService.approveExecution).mockResolvedValue(undefined as any);

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      await act(async () => {
        await result.current.approve(10);
      });

      expect(result.current.approveLoading).toBe(false);
    });

    it('onActionComplete qui lance une erreur ne masque pas le succès', async () => {
      vi.mocked(executionService.approveExecution).mockResolvedValue(undefined as any);
      mockOnActionComplete.mockImplementation(() => { throw new Error('callback error'); });

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      let outcome: any;
      await act(async () => {
        outcome = await result.current.approve(10);
      });

      // Success is not masked by callback error
      expect(outcome).toEqual({ success: true });
    });
  });

  describe('reject', () => {
    it('retourne { success: true } et appelle onActionComplete en cas de succès', async () => {
      vi.mocked(executionService.rejectExecution).mockResolvedValue(undefined as any);

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      let outcome: any;
      await act(async () => {
        outcome = await result.current.reject(20, 'Refusé');
      });

      expect(executionService.rejectExecution).toHaveBeenCalledWith(20, 'Refusé');
      expect(mockOnActionComplete).toHaveBeenCalled();
      expect(outcome).toEqual({ success: true });
    });

    it('retourne { success: false, error } si rejectExecution rejette', async () => {
      vi.mocked(executionService.rejectExecution).mockRejectedValue(new Error('Forbidden'));

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      let outcome: any;
      await act(async () => {
        outcome = await result.current.reject(20);
      });

      expect(outcome.success).toBe(false);
      expect(outcome.error).toBe('Forbidden');
    });

    it('rejectLoading=false après résolution', async () => {
      vi.mocked(executionService.rejectExecution).mockResolvedValue(undefined as any);

      const { result } = renderHook(() => usePendingApprovals(mockOnActionComplete));

      await act(async () => {
        await result.current.reject(20);
      });

      expect(result.current.rejectLoading).toBe(false);
    });
  });
});
