/**
 * Tests for calendarEventUtils — Story 26.6 AC9
 */
import { describe, it, expect } from 'vitest';
import {
  toUtcIso,
  mapToCalendarEvent,
  describePatternType,
  getDisplayParameters,
  ENV_COLORS,
  ENV_LABELS,
} from '../calendarEventUtils';
import type { ScheduledExecutionListItem } from '../../types/api';

function makeExec(overrides: Partial<ScheduledExecutionListItem> = {}): ScheduledExecutionListItem {
  return {
    scheduled_execution_id: 1,
    action_id: 10,
    action_name: 'Deploy DB',
    user_id: 42,
    user_name: 'admin',
    environment: 'dev',
    scheduled_at: '2026-03-15T10:00:00Z',
    status: 'pending',
    created_at: '2026-03-10T08:00:00Z',
    parameters: null,
    ...overrides,
  };
}

describe('toUtcIso', () => {
  it('should append Z to date without timezone suffix', () => {
    expect(toUtcIso('2026-03-15T10:00:00')).toBe('2026-03-15T10:00:00Z');
  });

  it('should not modify date already ending with Z', () => {
    expect(toUtcIso('2026-03-15T10:00:00Z')).toBe('2026-03-15T10:00:00Z');
  });

  it('should not modify date with positive offset', () => {
    expect(toUtcIso('2026-03-15T10:00:00+05:00')).toBe('2026-03-15T10:00:00+05:00');
  });

  it('should not modify date with negative offset', () => {
    expect(toUtcIso('2026-03-15T10:00:00-04:00')).toBe('2026-03-15T10:00:00-04:00');
  });

  it('should return the input as-is for empty string', () => {
    expect(toUtcIso('')).toBe('');
  });
});

describe('mapToCalendarEvent', () => {
  it('should map a one-time execution with time', () => {
    const exec = makeExec({ scheduled_at: '2026-03-15T10:00:00Z' });
    const event = mapToCalendarEvent(exec);
    expect(event.id).toBe('1');
    expect(event.title).toBe('Deploy DB');
    expect(event.start).toContain('2026-03-15');
    expect(event.end).toBeTruthy();
    expect(event.allDay).toBe(false);
    expect(event.backgroundColor).toBe(ENV_COLORS.dev);
    expect(event.extendedProps.execution).toBe(exec);
  });

  it('should map a recurring execution using next_execution_date', () => {
    const exec = makeExec({
      scheduled_at: null,
      recurring_pattern: {
        recurring_pattern_id: 1,
        scheduled_execution_id: 1,
        pattern_type: 'daily',
        pattern_config: { hour: 9, minute: 0 },
        is_active: true,
        next_execution_date: '2026-03-16T09:00:00Z',
        created_at: '2026-03-10T08:00:00Z',
      },
    });
    const event = mapToCalendarEvent(exec);
    expect(event.start).toContain('2026-03-16');
  });

  it('should use default 9:00 AM for dates without time', () => {
    const exec = makeExec({ scheduled_at: '2026-03-15' });
    const event = mapToCalendarEvent(exec);
    expect(event.start).toContain('09:00:00');
  });

  it('should return empty start when no date available', () => {
    const exec = makeExec({ scheduled_at: null, recurring_pattern: undefined });
    const event = mapToCalendarEvent(exec);
    expect(event.start).toBe('');
    expect(event.end).toBeUndefined();
  });

  it('should use environment color for known env', () => {
    const exec = makeExec({ environment: 'prod' });
    const event = mapToCalendarEvent(exec);
    expect(event.backgroundColor).toBe(ENV_COLORS.prod);
  });

  it('should use fallback color for unknown env', () => {
    const exec = makeExec({ environment: 'lab' as 'dev' });
    const event = mapToCalendarEvent(exec);
    expect(event.backgroundColor).toBe('#888');
  });
});

describe('describePatternType', () => {
  it('should return "Unique" for non-recurring', () => {
    expect(describePatternType(makeExec())).toBe('Unique');
  });

  it('should return "Quotidien" for daily pattern', () => {
    const exec = makeExec({
      recurring_pattern: {
        recurring_pattern_id: 1, scheduled_execution_id: 1,
        pattern_type: 'daily', pattern_config: {}, is_active: true,
        next_execution_date: null, created_at: '',
      },
    });
    expect(describePatternType(exec)).toBe('Quotidien');
  });

  it('should return "Hebdomadaire" for weekly pattern', () => {
    const exec = makeExec({
      recurring_pattern: {
        recurring_pattern_id: 1, scheduled_execution_id: 1,
        pattern_type: 'weekly', pattern_config: {}, is_active: true,
        next_execution_date: null, created_at: '',
      },
    });
    expect(describePatternType(exec)).toBe('Hebdomadaire');
  });

  it('should return "Cron" for cron pattern', () => {
    const exec = makeExec({
      recurring_pattern: {
        recurring_pattern_id: 1, scheduled_execution_id: 1,
        pattern_type: 'cron', pattern_config: {}, is_active: true,
        next_execution_date: null, created_at: '',
      },
    });
    expect(describePatternType(exec)).toBe('Cron');
  });

  it('should return "Récurrent" for unknown pattern type', () => {
    const exec = makeExec({
      recurring_pattern: {
        recurring_pattern_id: 1, scheduled_execution_id: 1,
        pattern_type: 'custom' as 'daily', pattern_config: {}, is_active: true,
        next_execution_date: null, created_at: '',
      },
    });
    expect(describePatternType(exec)).toBe('Récurrent');
  });
});

describe('getDisplayParameters', () => {
  it('should filter out keys starting with underscore', () => {
    const params = { name: 'test', _targets: ['server1'], _env_config: {} };
    const result = getDisplayParameters(params);
    expect(result).toEqual({ name: 'test' });
  });

  it('should return empty object for null input', () => {
    expect(getDisplayParameters(null)).toEqual({});
  });

  it('should return all keys if none start with underscore', () => {
    const params = { name: 'test', value: 42 };
    expect(getDisplayParameters(params)).toEqual(params);
  });
});

describe('ENV_COLORS and ENV_LABELS', () => {
  it('should have color for dev, staging, prod', () => {
    expect(ENV_COLORS.dev).toBe('#1890ff');
    expect(ENV_COLORS.staging).toBe('#fa8c16');
    expect(ENV_COLORS.prod).toBe('#f5222d');
  });

  it('should have labels for dev, staging, prod', () => {
    expect(ENV_LABELS.dev).toBe('Développement');
    expect(ENV_LABELS.staging).toBe('Staging');
    expect(ENV_LABELS.prod).toBe('Production');
  });
});
