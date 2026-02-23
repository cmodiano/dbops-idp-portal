/**
 * Engine icon cache singleton (Story 31.3).
 * Provides synchronous access to engine icon_url from REF_ENGINES table.
 * Loaded once lazily, then cached in memory for renderEngineIcon() fallback cascade.
 */

import { fetchEngines } from '../services/reference_service';

type EngineIconMap = Record<string, string | null>;

let cache: EngineIconMap | null = null;
let loadingPromise: Promise<EngineIconMap> | null = null;

/**
 * Fetch and cache engine icon_url map (async, deduped).
 * Returns map of engine code → icon_url (null if not defined).
 */
export function getEngineIconMap(): Promise<EngineIconMap> {
  if (cache) return Promise.resolve(cache);
  if (!loadingPromise) {
    loadingPromise = fetchEngines()
      .then((engines) => {
        const map: EngineIconMap = {};
        for (const engine of engines) {
          map[engine.code] = engine.icon_url ?? null;
        }
        cache = map;
        loadingPromise = null;
        return map;
      })
      .catch(() => {
        // échec non-critique — retourne un cache vide, les icônes seront chargées à la demande
        loadingPromise = null;
        return {} as EngineIconMap;
      });
  }
  return loadingPromise;
}

/**
 * Synchronous lookup of engine icon_url from cache.
 * Returns null if cache not yet loaded or engine not found.
 */
export function getEngineIconUrl(engineCode: string): string | null {
  return cache?.[engineCode] ?? null;
}

/**
 * Prefetch engine icons (fire-and-forget).
 * Call early in app lifecycle to warm the cache.
 */
export function prefetchEngineIcons(): void {
  getEngineIconMap().catch(() => {
    // fire-and-forget — prefetch optionnel, l'icône sera chargée à la demande si le cache est vide
  });
}

/**
 * Invalidate the engine icon cache (Story 31.10, AC3).
 * Forces next getEngineIconMap() call to re-fetch from API.
 */
export function invalidateEngineIconCache(): void {
  cache = null;
  loadingPromise = null;
}
