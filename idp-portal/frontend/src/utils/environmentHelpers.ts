import type { BadgeProps } from 'antd';

const STANDARD_ENVIRONMENT_LABELS: Record<string, string> = {
  dev: 'Développement',
  developpement: 'Développement',
  staging: 'Staging',
  certification: 'Certification',
  preprod: 'Pré-production',
  prod: 'Production',
  production: 'Production',
};

const ENVIRONMENT_COLORS: Record<string, BadgeProps['status']> = {
  dev: 'success',
  developpement: 'success',
  staging: 'warning',
  certification: 'warning',
  preprod: 'warning',
  prod: 'error',
  production: 'error',
  test: 'default',
  lab: 'default',
  qa: 'default',
  uat: 'default',
};

/** Hex colors for calendar/visualization — aligned with styleTokens.environmentBadgeColor.
 * Supports all inventory values (dev, developpement, staging, certification, prod, production, etc.). */
const ENVIRONMENT_HEX_COLORS: Record<string, string> = {
  dev: '#3B82F6',
  developpement: '#3B82F6',
  development: '#3B82F6',
  staging: '#F97316',
  certification: '#F97316',
  certif: '#F97316',
  preprod: '#F97316',
  prod: '#EF4444',
  production: '#EF4444',
  test: '#8B5CF6',
  lab: '#6B7280',
  qa: '#6B7280',
  uat: '#6B7280',
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
 * Returns hex color for an environment (calendar, charts, etc.).
 * Supports all inventory values (dev, developpement, staging, certification, prod, production).
 * Unknown envs → gray (#6B7280).
 */
export function getEnvironmentHexColor(env: string): string {
  const normalized = env.toLowerCase().trim();
  return ENVIRONMENT_HEX_COLORS[normalized] ?? '#6B7280';
}

/**
 * Sorts environments by canonical order: dev/developpement, staging/certification, prod/production first,
 * then alphabetical for unknown environments.
 */
export function sortEnvironments(environments: string[]): string[] {
  const priorityOrder = ['dev', 'developpement', 'staging', 'certification', 'preprod', 'prod', 'production', 'test', 'lab', 'qa', 'uat'];

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
