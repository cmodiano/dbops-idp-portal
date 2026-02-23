/**
 * Impact labels for aria-labels and display (Story 2.5).
 * Extracted from ImpactIndicator for react-refresh/only-export-components compliance.
 */

import type { ImpactLevel } from '../../types/api';

/** Labels for ActionCard aria-label (UX spec: "[nom], impact [niveau]"). */
export const IMPACT_LABELS: Record<ImpactLevel, string> = {
  low: 'Faible',
  medium: 'Moyen',
  high: 'Élevé',
  critical: 'Critique',
};

/** Descriptions des niveaux d'impact — affichées à la définition d'une action pour guider le choix. */
export const IMPACT_DESCRIPTIONS: Record<ImpactLevel, string> = {
  low: 'Aucun impact.',
  medium: 'Impact possible sur les performances.',
  high: 'Cause une indisponibilité du service.',
  critical:
    "Indisponibilité du service, plus considérations particulières ; doit faire l'objet d'une explication particulière.",
};
