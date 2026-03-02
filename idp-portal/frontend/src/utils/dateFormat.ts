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

/**
 * Format a date string for display in fr-CA locale (YYYY-MM-DD).
 * Use for dates that should display in ISO-like order (e.g. created_at columns).
 *
 * @param dateStr - ISO 8601 string or any parseable date string
 * @returns Formatted string in fr-CA (YYYY-MM-DD), or '—' if null/empty/invalid
 */
export function formatLocalDate(dateStr: string | null | undefined): string {
  if (!dateStr || typeof dateStr !== 'string') return '—';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('fr-CA', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

/**
 * Format a datetime string for display in fr-CA locale (YYYY-MM-DD HH:mm).
 * Use for datetime fields that should display in ISO-like order.
 *
 * Uses manual time formatting to guarantee consistent "HH:mm" output across
 * all environments (fr-CA toLocaleString produces "HH h mm" on macOS/Safari).
 *
 * @param dateStr - ISO 8601 string or any parseable date string
 * @returns Formatted string "YYYY-MM-DD HH:mm", or '—' if null/empty/invalid
 */
export function formatLocalDateTime(dateStr: string | null | undefined): string {
  if (!dateStr || typeof dateStr !== 'string') return '—';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '—';
  const datePart = date.toLocaleDateString('fr-CA', { year: 'numeric', month: '2-digit', day: '2-digit' });
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${datePart} ${hours}:${minutes}`;
}
