/**
 * Tests for dateFormat utilities — timezone handling (Story 22.15).
 *
 * Verifies that formatUtcToLocal correctly parses ISO 8601 strings
 * with explicit UTC timezone (Z and +00:00) and converts to local time.
 */

import { describe, it, expect } from 'vitest';
import { formatUtcToLocal, formatLocalDate, formatLocalDateTime } from './dateFormat';

describe('formatUtcToLocal', () => {
  // ── Z timezone suffix ──────────────────────────────────────────

  it('parses ISO date with Z timezone suffix', () => {
    const result = formatUtcToLocal('2026-02-09T14:30:00Z');
    // Should not return the fallback dash
    expect(result).not.toBe('—');
    // The result should contain the date components
    expect(result).toMatch(/09\/02\/2026/);
  });

  it('parses ISO date with Z suffix and microseconds', () => {
    const result = formatUtcToLocal('2026-02-09T14:30:00.123456Z');
    expect(result).not.toBe('—');
    expect(result).toMatch(/09\/02\/2026/);
  });

  // ── +00:00 timezone offset ────────────────────────────────────

  it('parses ISO date with +00:00 timezone offset', () => {
    const result = formatUtcToLocal('2026-02-09T14:30:00+00:00');
    expect(result).not.toBe('—');
    expect(result).toMatch(/09\/02\/2026/);
  });

  // ── Z and +00:00 produce same result ──────────────────────────

  it('Z and +00:00 produce identical results', () => {
    const withZ = formatUtcToLocal('2026-02-09T14:30:00Z');
    const withOffset = formatUtcToLocal('2026-02-09T14:30:00+00:00');
    expect(withZ).toBe(withOffset);
  });

  // ── datetimeWithSeconds format ─────────────────────────────────

  it('formats datetime with seconds (HH:mm:ss)', () => {
    const result = formatUtcToLocal('2026-02-09T14:30:45Z', 'datetimeWithSeconds');
    expect(result).not.toBe('—');
    expect(result).toMatch(/09\/02\/2026/);
    expect(result).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  // ── Date-only format ──────────────────────────────────────────

  it('formats date-only with Z suffix', () => {
    const result = formatUtcToLocal('2026-02-09T14:30:00Z', 'date');
    expect(result).toMatch(/09\/02\/2026/);
    // Should NOT contain time component
    expect(result).not.toMatch(/\d{2}:\d{2}/);
  });

  // ── Fallback handling ─────────────────────────────────────────

  it('returns dash for null', () => {
    expect(formatUtcToLocal(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatUtcToLocal(undefined)).toBe('—');
  });

  it('returns dash for empty string', () => {
    expect(formatUtcToLocal('')).toBe('—');
  });

  it('returns dash for invalid date string', () => {
    expect(formatUtcToLocal('not-a-date')).toBe('—');
  });

  // ── Local time conversion ─────────────────────────────────────

  it('converts UTC to local time (Date object validates timezone)', () => {
    // 2026-02-09T14:30:00Z is 14:30 UTC
    // new Date() should interpret Z as UTC, regardless of local timezone
    const utcDate = new Date('2026-02-09T14:30:00Z');
    expect(utcDate.getUTCHours()).toBe(14);
    expect(utcDate.getUTCMinutes()).toBe(30);

    // formatUtcToLocal should produce a non-dash result
    const result = formatUtcToLocal('2026-02-09T14:30:00Z');
    expect(result).not.toBe('—');
  });

  it('date without timezone would be interpreted as local time (baseline)', () => {
    // This test documents the behavior that dates WITHOUT timezone
    // are ambiguous — new Date("...") treats them as local time.
    // With our backend fix, all dates now include Z suffix.
    const withZ = new Date('2026-02-09T14:30:00Z');
    const withoutZ = new Date('2026-02-09T14:30:00');

    // If local timezone is not UTC, these will differ
    // This test just confirms they are valid dates
    expect(Number.isNaN(withZ.getTime())).toBe(false);
    expect(Number.isNaN(withoutZ.getTime())).toBe(false);
  });
});

// ── formatLocalDate (MAINT-FE-5, Story 54.16) ────────────────────────────────

describe('formatLocalDate', () => {
  it('formats a valid ISO date string in fr-CA (YYYY-MM-DD)', () => {
    // Use noon UTC to avoid date boundary shift in any UTC-12..UTC+12 timezone
    const result = formatLocalDate('2026-02-28T12:00:00Z');
    expect(result).toBe('2026-02-28');
  });

  it('returns — for null', () => {
    expect(formatLocalDate(null)).toBe('—');
  });

  it('returns — for undefined', () => {
    expect(formatLocalDate(undefined)).toBe('—');
  });

  it('returns — for empty string', () => {
    expect(formatLocalDate('')).toBe('—');
  });

  it('returns — for an invalid date string', () => {
    expect(formatLocalDate('not-a-date')).toBe('—');
  });

  it('does not contain time component', () => {
    const result = formatLocalDate('2026-02-28T12:00:00Z');
    expect(result).not.toMatch(/\d{2}:\d{2}/);
  });
});

// ── formatLocalDateTime (MAINT-FE-5, Story 54.16) ────────────────────────────

describe('formatLocalDateTime', () => {
  it('formats a valid ISO datetime string as YYYY-MM-DD HH:mm', () => {
    // formatLocalDateTime uses manual formatting to ensure consistent "HH:mm" output
    // across all environments (fr-CA toLocaleString produces "HH h mm" on macOS/Safari).
    // Use noon UTC to avoid date boundary shift in any UTC-12..UTC+12 timezone.
    const result = formatLocalDateTime('2026-02-28T12:30:00Z');
    expect(result).not.toBe('—');
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  });

  it('returns — for null', () => {
    expect(formatLocalDateTime(null)).toBe('—');
  });

  it('returns — for undefined', () => {
    expect(formatLocalDateTime(undefined)).toBe('—');
  });

  it('returns — for empty string', () => {
    expect(formatLocalDateTime('')).toBe('—');
  });

  it('returns — for an invalid date string', () => {
    expect(formatLocalDateTime('not-a-date')).toBe('—');
  });
});
