/**
 * Date formatting utilities.
 * API/database dates are UTC (ISO 8601); these helpers format for display in the user's local timezone.
 */

/**
 * Format a UTC ISO date string for display in the user's local timezone (fr-FR).
 * Use for dates from API/database (e.g. scheduled_at, created_at, next_execution_date).
 *
 * @param dateStr - ISO 8601 string (e.g. "2026-02-06T06:00:00Z" or "2026-02-06T06:00:00+00:00")
 * @param format - 'datetime' (DD/MM/YYYY HH:mm) or 'date' (DD/MM/YYYY)
 * @returns Formatted string in local time, or '—' if null/empty
 */
export function formatUtcToLocal(
  dateStr: string | null | undefined,
  format: 'datetime' | 'date' = 'datetime'
): string {
  if (!dateStr || typeof dateStr !== 'string') return '—';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '—';
  if (format === 'date') {
    return date.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  }
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
