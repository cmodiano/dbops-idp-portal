/**
 * WizardStep3ImpactChangement — Étape 3 du wizard (Impact & Changement) extraite de ActionWizard (Story 33.5, Task 5).
 * Contient : règles d'impact, niveau par défaut, changeTypeConfig, règles métier, notifications.
 */
import { Form, Select, Space } from 'antd';
import type {
  ActionDetail,
  ChangeTypeConfigEntry,
  GateConfig,
  ImpactLevel,
  ImpactRuleDefinition,
  NotificationConfig,
} from '../../types/api';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { BusinessRulePolicySelector } from './BusinessRulePolicySelector';
import { NotificationConfigSection } from './NotificationConfigSection';
import { ImpactLevelsLegend } from './ImpactLevelsLegend';
import SectionHelp from '../common/SectionHelp';
import { platformCodeToStepType } from '../../utils/integrationHelpers';

type IntegrationLike = { id: number; type: string; name: string };

export interface WizardStep3ImpactChangementProps {
  isWorkflow: boolean;
  isReadOnly: boolean;
  impactRulesList: ImpactRuleDefinition[];
  setImpactRulesList: (list: ImpactRuleDefinition[]) => void;
  defaultImpactLevel: ImpactLevel | null;
  setDefaultImpactLevel: (level: ImpactLevel | null) => void;
  changeTypeConfig: Record<string, ChangeTypeConfigEntry>;
  setChangeTypeConfig: (config: Record<string, ChangeTypeConfigEntry>) => void;
  gateConfig: GateConfig | null;
  setGateConfig: (config: GateConfig | null) => void;
  businessRulePolicyId: number | null;
  setBusinessRulePolicyId: (id: number | null) => void;
  notificationConfig: NotificationConfig | null;
  setNotificationConfig: (config: NotificationConfig | null) => void;
  selectedIntegration?: IntegrationLike;
  editAction?: ActionDetail | null;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
}

export function WizardStep3ImpactChangement({
  isWorkflow,
  isReadOnly,
  impactRulesList,
  setImpactRulesList,
  defaultImpactLevel,
  setDefaultImpactLevel,
  changeTypeConfig,
  setChangeTypeConfig,
  gateConfig,
  setGateConfig,
  businessRulePolicyId,
  setBusinessRulePolicyId,
  notificationConfig,
  setNotificationConfig,
  selectedIntegration,
  editAction,
  getIntegrationById,
}: WizardStep3ImpactChangementProps) {
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* Impact rules and change config for both actions and workflows */}
      <Form.Item
        label="Règles d'impact"
        tooltip="Définissez les règles d'impact par environnement."
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
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

      {/* Only show change config for actions, not workflows */}
      {!isWorkflow && (
        <Form.Item
          label={<span>Gates et Changement ServiceNow par environnement <SectionHelp topicId="action-form-changement-servicenow" /></span>}
          tooltip="Deux parties : (1) Gates — conditions d'exécution (autorisé, plage maintenance, approbation) ; (2) Changement ServiceNow (requis, modèle/template ID, change type)."
        >
          <ChangeTypeConfig
            value={changeTypeConfig}
            onChange={isReadOnly ? () => {} : setChangeTypeConfig}
            gateConfig={gateConfig}
            onGateConfigChange={isReadOnly ? undefined : setGateConfig}
          />
        </Form.Item>
      )}

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
    </Space>
  );
}
