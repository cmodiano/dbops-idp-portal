/**
 * Debounces a function: only the last call within `waitMs` is executed.
 * Use for rate-limiting async validation (e.g. cron expression).
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  waitMs: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timeoutId != null) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      timeoutId = null;
      fn(...args);
    }, waitMs);
  };
}
