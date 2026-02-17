/**
 * Impact labels for aria-labels and display (Story 2.5).
 * Extracted from ImpactIndicator for react-refresh/only-export-components compliance.
 */

import type { ImpactLevel } from '../../types/api';

/** Labels for ActionCard aria-label (UX spec: "[nom], impact [niveau]"). */
export const IMPACT_LABELS: Record<ImpactLevel, string> = {
  low: 'Faible',
  medium: 'Moyen',
  high: 'Eleve',
  critical: 'Critique',
};
