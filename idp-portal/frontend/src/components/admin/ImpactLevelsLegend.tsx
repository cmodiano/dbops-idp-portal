/**
 * ImpactLevelsLegend — Légende partagée des niveaux d'impact (Story 33.5, AC1, AC6).
 * Utilisée dans ActionForm et ActionWizard pour décrire les niveaux low/medium/high/critical.
 * Aucune prop : auto-suffisant, utilise IMPACT_LABELS et IMPACT_DESCRIPTIONS directement.
 */
import { IMPACT_LABELS, IMPACT_DESCRIPTIONS } from '../shared/impactLabels';

export function ImpactLevelsLegend() {
  return (
    <div
      style={{ fontSize: 12, color: 'rgba(0, 0, 0, 0.45)' }}
      role="region"
      aria-label="Signification des niveaux d'impact"
    >
      <strong>Signification des niveaux :</strong>
      <ul style={{ margin: '4px 0 8px 0', paddingLeft: 20 }}>
        {(['low', 'medium', 'high', 'critical'] as const).map((level) => (
          <li key={level}>
            <strong>{IMPACT_LABELS[level]}</strong> — {IMPACT_DESCRIPTIONS[level]}
          </li>
        ))}
      </ul>
    </div>
  );
}
