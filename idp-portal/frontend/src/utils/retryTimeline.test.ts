/**
 * Tests for retryTimeline utilities (Story 16.6, Task 9.1, 9.2).
 */

import { describe, it, expect } from 'vitest';
import { calculateRetryTimeline, formatDuration } from './retryTimeline';

describe('calculateRetryTimeline', () => {
  it('generates correct timeline for 4 attempts, 60s interval, 2.0 multiplier', () => {
    const timeline = calculateRetryTimeline(4, 60, 2.0);

    expect(timeline).toEqual([
      { attempt: 1, delay: 0 },
      { attempt: 2, delay: 60 },
      { attempt: 3, delay: 120 },
      { attempt: 4, delay: 240 },
    ]);
  });

  it('generates single entry for 1 attempt', () => {
    const timeline = calculateRetryTimeline(1, 60, 2.0);

    expect(timeline).toEqual([{ attempt: 1, delay: 0 }]);
  });

  it('generates correct timeline with multiplier 1.0 (no backoff)', () => {
    const timeline = calculateRetryTimeline(3, 30, 1.0);

    expect(timeline).toEqual([
      { attempt: 1, delay: 0 },
      { attempt: 2, delay: 30 },
      { attempt: 3, delay: 30 },
    ]);
  });

  it('generates correct timeline for max attempts (10)', () => {
    const timeline = calculateRetryTimeline(10, 10, 1.5);

    expect(timeline).toHaveLength(10);
    expect(timeline[0]).toEqual({ attempt: 1, delay: 0 });
    expect(timeline[1]).toEqual({ attempt: 2, delay: 10 });
    // attempt 3: 10 * 1.5^1 = 15
    expect(timeline[2].delay).toBeCloseTo(15, 5);
    // attempt 4: 10 * 1.5^2 = 22.5
    expect(timeline[3].delay).toBeCloseTo(22.5, 5);
  });

  it('handles high multiplier correctly', () => {
    const timeline = calculateRetryTimeline(3, 5, 10.0);

    expect(timeline).toEqual([
      { attempt: 1, delay: 0 },
      { attempt: 2, delay: 5 },
      { attempt: 3, delay: 50 }, // 5 * 10
    ]);
  });
});

describe('formatDuration', () => {
  it('formats 0 seconds as "immédiate"', () => {
    expect(formatDuration(0)).toBe('immédiate');
  });

  it('formats 60 seconds as "1 min"', () => {
    expect(formatDuration(60)).toBe('1 min');
  });

  it('formats 120 seconds as "2 min"', () => {
    expect(formatDuration(120)).toBe('2 min');
  });

  it('formats 3600 seconds as "1 h"', () => {
    expect(formatDuration(3600)).toBe('1 h');
  });

  it('formats 3660 seconds as "1 h 1 min"', () => {
    expect(formatDuration(3660)).toBe('1 h 1 min');
  });

  it('formats 30 seconds as "30 s"', () => {
    expect(formatDuration(30)).toBe('30 s');
  });

  it('formats 90 seconds as "1 min 30 s"', () => {
    expect(formatDuration(90)).toBe('1 min 30 s');
  });

  it('formats 7200 seconds as "2 h"', () => {
    expect(formatDuration(7200)).toBe('2 h');
  });

  it('does not show seconds when hours are present', () => {
    // 3605 = 1h 0min 5s → should show "1 h" (seconds hidden when hours > 0)
    expect(formatDuration(3605)).toBe('1 h');
  });
});
