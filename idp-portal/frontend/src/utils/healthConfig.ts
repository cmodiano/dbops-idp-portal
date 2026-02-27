/**
 * Story 51.4: Shared health check badge configuration.
 * Used by IntegrationsTable and IntegrationForm.
 */

import type { HealthStatus } from '../types/api';

export const HEALTH_CONFIG: Record<HealthStatus, { color: string; text: string; ariaLabel: string }> = {
  ok:      { color: 'success', text: 'OK',      ariaLabel: 'Santé : OK' },
  error:   { color: 'error',   text: 'Erreur',  ariaLabel: 'Santé : Erreur' },
  unknown: { color: 'default', text: 'Inconnu', ariaLabel: 'Santé : Inconnu' },
};
