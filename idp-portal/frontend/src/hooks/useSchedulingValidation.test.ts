import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import dayjs from 'dayjs';
import { useSchedulingValidation } from './useSchedulingValidation';

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
});
