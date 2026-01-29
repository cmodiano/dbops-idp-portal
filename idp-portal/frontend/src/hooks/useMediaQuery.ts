/**
 * useMediaQuery - Hook for responsive layout (Story 2.5, Task 4.4).
 * Architecture: desktop min-width 1280px; layout stacks below that.
 */

import { useState, useEffect } from 'react';

/**
 * Returns true when viewport width is >= minWidth (default 1280px).
 * Used for split-view breakpoint (form left, preview right) per AC3.
 */
export function useMediaQuery(minWidth: number = 1280): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(`(min-width: ${minWidth}px)`).matches;
  });

  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${minWidth}px)`);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [minWidth]);

  return matches;
}
