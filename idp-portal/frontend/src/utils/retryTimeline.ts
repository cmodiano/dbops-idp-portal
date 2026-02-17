/**
 * Retry timeline calculation and duration formatting utilities (Story 16.6).
 */

export interface RetryTimelineEntry {
  attempt: number;
  delay: number;
}

/**
 * Calculate the retry timeline with exponential backoff.
 * @param attempts - Number of attempts (1-10)
 * @param interval - Initial interval in seconds (min 1)
 * @param multiplier - Backoff multiplier (1.0-10.0)
 * @returns Array of attempts with delay in seconds
 */
export function calculateRetryTimeline(
  attempts: number,
  interval: number,
  multiplier: number,
): RetryTimelineEntry[] {
  const timeline: RetryTimelineEntry[] = [];

  for (let i = 1; i <= attempts; i++) {
    if (i === 1) {
      timeline.push({ attempt: 1, delay: 0 });
    } else {
      const delay = interval * Math.pow(multiplier, i - 2);
      timeline.push({ attempt: i, delay });
    }
  }

  return timeline;
}

/**
 * Format a duration in seconds to a human-readable string.
 * @param seconds - Duration in seconds
 * @returns Formatted string (e.g., "immédiate", "30 s", "1 min", "2 h 30 min")
 */
export function formatDuration(seconds: number): string {
  if (seconds === 0) return 'immédiate';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours} h`);
  if (minutes > 0) parts.push(`${minutes} min`);
  if (secs > 0 && hours === 0) parts.push(`${secs} s`);

  return parts.join(' ') || '0 s';
}
