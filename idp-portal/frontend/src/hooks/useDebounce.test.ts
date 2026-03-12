/**
 * Tests for useDebounce hook (Story 71.11, AC #3).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebounce } from './useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('retourne la valeur initiale immédiatement (pas encore debouncée)', () => {
    const { result } = renderHook(() => useDebounce('hello', 300));

    expect(result.current).toBe('hello');
  });

  it('met à jour la valeur après le délai', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 300 } },
    );

    rerender({ value: 'updated', delay: 300 });

    // Pas encore mis à jour
    expect(result.current).toBe('initial');

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe('updated');
  });

  it('annule le timer si la valeur change avant le délai', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'first' } },
    );

    rerender({ value: 'second' });
    act(() => { vi.advanceTimersByTime(100); });

    rerender({ value: 'third' });
    act(() => { vi.advanceTimersByTime(100); });

    // Pas encore mis à jour (timer réinitialisé à chaque changement)
    expect(result.current).toBe('first');

    act(() => { vi.advanceTimersByTime(300); });

    expect(result.current).toBe('third');
  });

  it('fonctionne avec un type number', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 200),
      { initialProps: { value: 0 } },
    );

    rerender({ value: 42 });
    act(() => { vi.advanceTimersByTime(200); });

    expect(result.current).toBe(42);
  });

  it('fonctionne avec un type string', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: '' } },
    );

    rerender({ value: 'test' });
    act(() => { vi.advanceTimersByTime(500); });

    expect(result.current).toBe('test');
  });
});
