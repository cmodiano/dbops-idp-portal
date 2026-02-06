/**
 * Simple fnmatch-style pattern matching for target names.
 * Supports * (any chars) and ? (single char).
 * Aligns with backend fnmatch usage (e.g. srv-dev-*, assurance-*).
 */
export function matchGlob(pattern: string, name: string): boolean {
  if (!pattern || !name) return false;
  const regex = globToRegex(pattern);
  return regex.test(name);
}

function globToRegex(pattern: string): RegExp {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*/g, '.*')
    .replace(/\?/g, '.');
  return new RegExp(`^${escaped}$`, 'i');
}
