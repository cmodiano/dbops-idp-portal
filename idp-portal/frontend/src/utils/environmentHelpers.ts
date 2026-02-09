import type { BadgeProps } from 'antd';

const STANDARD_ENVIRONMENT_LABELS: Record<string, string> = {
  dev: 'Développement',
  staging: 'Staging',
  prod: 'Production',
};

const ENVIRONMENT_COLORS: Record<string, BadgeProps['status']> = {
  dev: 'success',
  staging: 'warning',
  prod: 'error',
};

/**
 * Returns the display label for an environment.
 * Standard envs get mapped labels, others get capitalized.
 */
export function getEnvironmentLabel(env: string): string {
  const normalized = env.toLowerCase();
  if (STANDARD_ENVIRONMENT_LABELS[normalized]) {
    return STANDARD_ENVIRONMENT_LABELS[normalized];
  }
  return env.charAt(0).toUpperCase() + env.slice(1).toLowerCase();
}

/**
 * Returns the badge color for an environment.
 * Standard envs get specific colors, others get 'default'.
 */
export function getEnvironmentColor(env: string): BadgeProps['status'] {
  const normalized = env.toLowerCase();
  return ENVIRONMENT_COLORS[normalized] || 'default';
}

/**
 * Sorts environments: dev, staging, prod first (in that order), then alphabetical.
 */
export function sortEnvironments(environments: string[]): string[] {
  const priorityOrder = ['dev', 'staging', 'prod'];

  return [...environments].sort((a, b) => {
    const indexA = priorityOrder.indexOf(a.toLowerCase());
    const indexB = priorityOrder.indexOf(b.toLowerCase());

    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
    if (indexA !== -1) return -1;
    if (indexB !== -1) return 1;
    return a.localeCompare(b);
  });
}

/**
 * Checks if an environment is production (case-insensitive, supports 'prod' and 'production').
 */
export function isProductionEnvironment(env: string): boolean {
  const normalized = env.toLowerCase();
  return normalized === 'prod' || normalized === 'production';
}
