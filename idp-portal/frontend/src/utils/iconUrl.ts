/**
 * Resolves icon URL for Avatar/img display.
 * - Relative paths (/static/icons/...) must use API origin when frontend and API are on different hosts.
 * - External URLs (http...) are returned as-is.
 */
export function getIconUrl(icon: string | null | undefined): string | undefined {
  if (!icon?.trim()) return undefined;
  const trimmed = icon.trim();
  // External URL: use as-is
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed;
  }
  // Relative path: prefix with API base when set (dev/prod with separate hosts)
  const apiBase = import.meta.env.VITE_API_BASE_URL;
  if (apiBase && trimmed.startsWith('/')) {
    return `${apiBase.replace(/\/$/, '')}${trimmed}`;
  }
  return trimmed;
}
