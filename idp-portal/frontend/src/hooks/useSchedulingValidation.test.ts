import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import dayjs from 'dayjs';
import { useSchedulingValidation } from './useSchedulingValidation';
import * as scheduledService from '../services/scheduled_execution_service';

vi.mock('../services/scheduled_execution_service', () => ({
  validateCronExpression: vi.fn(),
  getCronNextExecutions: vi.fn(),
}));

vi.mock('../utils/debounce', () => ({
  debounce: (fn: Function) => fn, // no debounce in tests
}));

describe('useSchedulingValidation', () => {
  describe('validateSchedule', () => {
    it('rejects one-time with no date', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const validation = result.current.validateSchedule('one-time', {});
      expect(validation.isValid).toBe(false);
      expect(validation.error).toContain('date et heure');
    });

    it('rejects one-time with past date', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const pastDate = dayjs().subtract(1, 'hour');
      const validation = result.current.validateSchedule('one-time', { scheduledAt: pastDate });
      expect(validation.isValid).toBe(false);
      expect(validation.error).toContain('futur');
    });

    it('accepts one-time with future date', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const futureDate = dayjs().add(1, 'hour');
      const validation = result.current.validateSchedule('one-time', { scheduledAt: futureDate });
      expect(validation.isValid).toBe(true);
      expect(validation.error).toBeNull();
    });

    it('rejects cron with empty expression', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const validation = result.current.validateSchedule('cron', { cronExpression: '' });
      expect(validation.isValid).toBe(false);
      expect(validation.error).toContain('cron valide');
    });

    it('rejects cron with invalid flag', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const validation = result.current.validateSchedule('cron', {
        cronExpression: '0 2 * * *',
        cronIsValid: false,
      });
      expect(validation.isValid).toBe(false);
    });

    it('accepts cron with valid expression', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const validation = result.current.validateSchedule('cron', {
        cronExpression: '0 2 * * *',
        cronIsValid: true,
      });
      expect(validation.isValid).toBe(true);
      expect(validation.error).toBeNull();
    });

    it('daily scheduling is always valid', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const validation = result.current.validateSchedule('daily', {});
      expect(validation.isValid).toBe(true);
    });

    it('weekly scheduling is always valid', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const validation = result.current.validateSchedule('weekly', {});
      expect(validation.isValid).toBe(true);
    });
  });

  describe('validateCronDebounced', () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it('calls onResult with empty result for blank expression', async () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      await act(async () => {
        await result.current.validateCronDebounced('', onResult);
      });

      expect(onResult).toHaveBeenCalledWith({
        isValid: null,
        error: '',
        nextExecutions: [],
        validating: false,
      });
    });

    it('calls onResult with validating=true before response', async () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();
      vi.mocked(scheduledService.validateCronExpression).mockResolvedValue({ valid: true, error: '' });
      vi.mocked(scheduledService.getCronNextExecutions).mockResolvedValue([]);

      await act(async () => {
        await result.current.validateCronDebounced('0 9 * * *', onResult);
      });

      // Should have called with validating:true first
      expect(onResult).toHaveBeenNthCalledWith(1, expect.objectContaining({ validating: true }));
    });

    it('validates valid cron expression and returns next executions', async () => {
      vi.mocked(scheduledService.validateCronExpression).mockResolvedValue({ valid: true, error: '' });
      vi.mocked(scheduledService.getCronNextExecutions).mockResolvedValue([
        '2025-06-01T09:00:00Z',
        '2025-06-02T09:00:00Z',
      ]);

      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      await act(async () => {
        await result.current.validateCronDebounced('0 9 * * *', onResult);
      });

      expect(onResult).toHaveBeenLastCalledWith(
        expect.objectContaining({
          isValid: true,
          nextExecutions: ['2025-06-01T09:00:00Z', '2025-06-02T09:00:00Z'],
          validating: false,
        }),
      );
    });

    it('handles invalid cron expression', async () => {
      vi.mocked(scheduledService.validateCronExpression).mockResolvedValue({
        valid: false,
        error: 'Invalid cron format',
      });

      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      await act(async () => {
        await result.current.validateCronDebounced('invalid', onResult);
      });

      expect(onResult).toHaveBeenLastCalledWith(
        expect.objectContaining({ isValid: false, error: 'Invalid cron format' }),
      );
    });

    it('uses default error message when validation returns no error', async () => {
      vi.mocked(scheduledService.validateCronExpression).mockResolvedValue({ valid: false, error: '' });

      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      await act(async () => {
        await result.current.validateCronDebounced('0 9 * * *', onResult);
      });

      expect(onResult).toHaveBeenLastCalledWith(
        expect.objectContaining({ isValid: false, error: 'Expression cron invalide' }),
      );
    });

    it('handles service error gracefully', async () => {
      vi.mocked(scheduledService.validateCronExpression).mockRejectedValue(new Error('Service down'));

      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      await act(async () => {
        await result.current.validateCronDebounced('0 9 * * *', onResult);
      });

      expect(onResult).toHaveBeenLastCalledWith(
        expect.objectContaining({ isValid: false, error: 'Erreur de validation' }),
      );
    });
  });

  describe('handleCronPresetChange', () => {
    it('calls onResult with null isValid for "custom" preset', () => {
      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      act(() => {
        result.current.handleCronPresetChange('custom', onResult);
      });

      expect(onResult).toHaveBeenCalledWith({
        isValid: null,
        error: '',
        nextExecutions: [],
        validating: false,
      });
    });

    it('calls validateCronDebounced for non-custom preset', async () => {
      vi.mocked(scheduledService.validateCronExpression).mockResolvedValue({ valid: true, error: '' });
      vi.mocked(scheduledService.getCronNextExecutions).mockResolvedValue([]);

      const { result } = renderHook(() => useSchedulingValidation());
      const onResult = vi.fn();

      await act(async () => {
        await result.current.handleCronPresetChange('0 9 * * 1-5', onResult);
      });

      expect(scheduledService.validateCronExpression).toHaveBeenCalledWith('0 9 * * 1-5');
    });
  });
});
