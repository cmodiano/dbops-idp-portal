/**
 * WizardStep3ImpactChangement — Étape 3 du wizard (Impact & Changement) extraite de ActionWizard (Story 33.5, Task 5).
 * Contient : règles d'impact, niveau par défaut, règles métier, notifications.
 */
import { Form, Select, Space } from 'antd';
import type {
  ActionDetail,
  ImpactLevel,
  ImpactRuleDefinition,
  NotificationConfig,
} from '../../types/api';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import { BusinessRulePolicySelector } from './BusinessRulePolicySelector';
import { NotificationConfigSection } from './NotificationConfigSection';
import { ImpactLevelsLegend } from './ImpactLevelsLegend';
import { platformCodeToStepType } from '../../utils/integrationHelpers';

type IntegrationLike = { id: number; type: string; name: string };

export interface WizardStep3ImpactChangementProps {
  isWorkflow: boolean;
  isReadOnly: boolean;
  impactRulesList: ImpactRuleDefinition[];
  setImpactRulesList: (list: ImpactRuleDefinition[]) => void;
  defaultImpactLevel: ImpactLevel | null;
  setDefaultImpactLevel: (level: ImpactLevel | null) => void;
  businessRulePolicyId: number | null;
  setBusinessRulePolicyId: (id: number | null) => void;
  notificationConfig: NotificationConfig | null;
  setNotificationConfig: (config: NotificationConfig | null) => void;
  selectedIntegration?: IntegrationLike;
  editAction?: ActionDetail | null;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
}

export function WizardStep3ImpactChangement({
  isWorkflow: _isWorkflow,
  isReadOnly,
  impactRulesList,
  setImpactRulesList,
  defaultImpactLevel,
  setDefaultImpactLevel,
  businessRulePolicyId,
  setBusinessRulePolicyId,
  notificationConfig,
  setNotificationConfig,
  selectedIntegration,
  editAction,
  getIntegrationById,
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

      {/* Règles métier et Notifications : uniquement pour les actions (pas les workflows).
          Pour les workflows, ce sont des étapes indépendantes (evaluation, service_call notification). */}
      {!_isWorkflow && (
        <>
          {/* Story 28.4: Règles métier — sélecteur prédéfini (filtré par plateforme) */}
          <Form.Item
            label="Règles métier"
            tooltip="Choisissez une règle prédéfinie du catalogue (Admin → Règles métier). Seules les règles liées à votre plateforme d'exécution sont proposées."
          >
            <BusinessRulePolicySelector
              policyId={businessRulePolicyId}
              onPolicyIdChange={setBusinessRulePolicyId}
              stepType={
                selectedIntegration?.type
                ?? (editAction?.integration_id ? getIntegrationById(editAction.integration_id)?.type : undefined)
                ?? (editAction?.platform ? platformCodeToStepType(editAction.platform) : undefined)
              }
              disabled={isReadOnly}
            />
          </Form.Item>

          {/* Story 31.8: Notification configuration */}
          <Form.Item
            label="Notifications"
            tooltip="Configurez les canaux de notification (email, Teams, page) et leurs conditions."
          >
            <NotificationConfigSection
              value={notificationConfig}
              onChange={isReadOnly ? () => {} : setNotificationConfig}
            />
          </Form.Item>
        </>
      )}
    </Space>
  );
}
