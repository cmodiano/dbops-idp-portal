/**
 * WizardStep3ImpactChangement — Étape 3 du wizard (Impact & Changement) extraite de ActionWizard (Story 33.5, Task 5).
 * Contient : règles d'impact, niveau par défaut.
 * Règles métier et Notifications : déplacées au niveau des étapes de workflow (EvaluationStepConfig, service_call).
 */
import { Form, Select, Space } from 'antd';
import type {
  ImpactLevel,
  ImpactRuleDefinition,
} from '../../types/api';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import { ImpactLevelsLegend } from './ImpactLevelsLegend';

export interface WizardStep3ImpactChangementProps {
  isWorkflow: boolean;
  isReadOnly: boolean;
  impactRulesList: ImpactRuleDefinition[];
  setImpactRulesList: (list: ImpactRuleDefinition[]) => void;
  defaultImpactLevel: ImpactLevel | null;
  setDefaultImpactLevel: (level: ImpactLevel | null) => void;
}

export function WizardStep3ImpactChangement({
  isReadOnly,
  impactRulesList,
  setImpactRulesList,
  defaultImpactLevel,
  setDefaultImpactLevel,
}: WizardStep3ImpactChangementProps) {
  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      {/* Impact rules and change config for both actions and workflows */}
      <Form.Item
        label="Règles d'impact"
        tooltip="Définissez les règles d'impact par environnement."
      >
        <Space orientation="vertical" size="small" style={{ width: '100%' }}>
          <ImpactLevelsLegend />
          <ImpactRulesEditor value={impactRulesList} onChange={isReadOnly ? () => {} : setImpactRulesList} />
        </Space>
      </Form.Item>

      <Form.Item
        label="Niveau d'impact par défaut"
        tooltip="Niveau appliqué quand aucune règle ne correspond à l'environnement."
      >
        <Select
          value={defaultImpactLevel ?? undefined}
          onChange={(v) => setDefaultImpactLevel(v || null)}
          allowClear
          placeholder="Sélectionnez un niveau par défaut"
          style={{ width: 220 }}
          aria-label="Niveau d'impact par défaut"
          disabled={isReadOnly}
          options={[
            { value: 'low', label: 'Faible (vert)' },
            { value: 'medium', label: 'Moyen (orange)' },
            { value: 'high', label: 'Élevé (rouge)' },
            { value: 'critical', label: 'Critique (rouge foncé)' },
          ]}
        />
      </Form.Item>
    </Space>
  );
}
