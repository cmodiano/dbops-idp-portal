/**
 * Hook to load platforms from reference API (Story 13.7).
 * Caches result to avoid multiple API calls.
 */

import { useState, useEffect } from 'react';
import { fetchPlatforms, type RefPlatform } from '../services/reference_service';

interface UsePlatformsResult {
  platforms: RefPlatform[];
  loading: boolean;
  error: Error | null;
  platformOptions: { value: string; label: string }[];
}

/**
 * Hook to fetch and cache platforms from REF_PLATFORMS table.
 * Returns platforms as options array for Select components.
 */
export function usePlatforms(): UsePlatformsResult {
  const [platforms, setPlatforms] = useState<RefPlatform[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPlatforms() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchPlatforms();
        if (!cancelled) {
          setPlatforms(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error('Failed to load platforms'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadPlatforms();

    return () => {
      cancelled = true;
    };
  }, []);

  // Convert to options format for Select components
  const platformOptions = platforms
    .filter((p) => p.is_active === 1)
    .sort((a, b) => a.display_order - b.display_order || a.code.localeCompare(b.code))
    .map((p) => ({
      value: p.code,
      label: p.label,
    }));

  return { platforms, loading, error, platformOptions };
}
