/**
 * ExecutionTimeline utilities — Story 34.12 (SOLID-FE-1)
 *
 * Pure utility functions shared by ExecutionTimeline sub-components.
 */

export function formatDuration(started: string | null, completed: string | null): string {
  if (!started || !completed) return '';
  const a = new Date(started).getTime();
  const b = new Date(completed).getTime();
  const s = Math.round((b - a) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}
