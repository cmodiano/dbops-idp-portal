/**
 * Debounces a function: only the last call within `waitMs` is executed.
 * Use for rate-limiting async validation (e.g. cron expression).
 * The returned function exposes a `.cancel()` method to clear the pending timeout.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type DebouncedFn<T extends (...args: any[]) => unknown> = ((...args: Parameters<T>) => void) & {
  cancel: () => void;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function debounce<T extends (...args: any[]) => unknown>(
  fn: T,
  waitMs: number
): DebouncedFn<T> {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  const debounced = (...args: Parameters<T>) => {
    if (timeoutId != null) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      timeoutId = null;
      fn(...args);
    }, waitMs);
  };
  debounced.cancel = () => {
    if (timeoutId != null) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };
  return debounced;
}
