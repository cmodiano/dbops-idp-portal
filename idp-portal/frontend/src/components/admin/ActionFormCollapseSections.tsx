/**
 * ActionFormCollapseSections — Sections Collapse extraites de ActionForm (Story 33.5, Task 4).
 * Regroupe les 4 panneaux avancés : Étapes/ServiceNow, Remédiation, Règles métier, Notifications.
 */
import { Collapse, Form, Typography } from 'antd';
import type {
  ActionDetail,
  ChangeTypeConfigEntry,
  ExecutionStep,
  GateConfig,
  NotificationConfig,
} from '../../types/api';
import type { RemediationRuleDefinition } from './RemediationRulesEditor';
import { StepsEditor } from './StepsEditor';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { RemediationRulesEditor } from './RemediationRulesEditor';
import { BusinessRulePolicySelector } from './BusinessRulePolicySelector';
import { NotificationConfigSection } from './NotificationConfigSection';
import SectionHelp from '../common/SectionHelp';
import { platformCodeToStepType } from '../../utils/integrationHelpers';

const { Text } = Typography;

type IntegrationLike = { id: number; type: string; name: string } & Record<string, unknown>;

export interface ActionFormCollapseSectionsProps {
  executionSteps: ExecutionStep[];
  setExecutionSteps: (steps: ExecutionStep[]) => void;
  changeTypeConfig: Record<string, ChangeTypeConfigEntry>;
  setChangeTypeConfig: (config: Record<string, ChangeTypeConfigEntry>) => void;
  gateConfig: GateConfig | null;
  setGateConfig: (config: GateConfig | null) => void;
  remediationRules: RemediationRuleDefinition[];
  setRemediationRules: (rules: RemediationRuleDefinition[]) => void;
  businessRulePolicyId: number | null;
  setBusinessRulePolicyId: (id: number | null) => void;
  notificationConfig: NotificationConfig | null;
  setNotificationConfig: (config: NotificationConfig | null) => void;
  editAction?: ActionDetail | null;
  watchedIntegrationId: number | undefined;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
}

export function ActionFormCollapseSections({
  executionSteps,
  setExecutionSteps,
  changeTypeConfig,
  setChangeTypeConfig,
  gateConfig,
  setGateConfig,
  remediationRules,
  setRemediationRules,
  businessRulePolicyId,
  setBusinessRulePolicyId,
  notificationConfig,
  setNotificationConfig,
  editAction,
  watchedIntegrationId,
  getIntegrationById,
}: ActionFormCollapseSectionsProps) {
  return (
    <Collapse
      ghost
      items={[
        {
          key: 'execution-steps',
          label: (
            <Text strong>
              Etapes d'execution et changement ServiceNow
              {executionSteps.length > 0 && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  ({executionSteps.length} etape{executionSteps.length > 1 ? 's' : ''})
                </Text>
              )}
            </Text>
          ),
          children: (
            <>
              <Form.Item
                label="Etapes d'execution"
                tooltip="Definissez les etapes d'execution de l'action (AC #1, #2)"
                style={{ marginBottom: 16 }}
              >
                <StepsEditor
                  value={executionSteps}
                  onChange={setExecutionSteps}
                  integrationId={watchedIntegrationId}
                />
              </Form.Item>

              <Form.Item
                label={<span>Gates et Changement ServiceNow par environnement <SectionHelp topicId="action-form-changement-servicenow" /></span>}
                tooltip="Deux parties : (1) Gates — conditions d'exécution (autorisé, plage maintenance, approbation) ; (2) Changement ServiceNow (requis, modèle/template ID, change type)."
                style={{ marginBottom: 16 }}
              >
                <ChangeTypeConfig
                  value={changeTypeConfig}
                  onChange={setChangeTypeConfig}
                  gateConfig={gateConfig}
                  onGateConfigChange={setGateConfig}
                />
              </Form.Item>
            </>
          ),
        },
        {
          key: 'remediation-rules',
          label: (
            <Text strong>
              Règles de remédiation automatique
              {remediationRules.length > 0 && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  ({remediationRules.length} règle{remediationRules.length > 1 ? 's' : ''})
                </Text>
              )}
            </Text>
          ),
          children: (
            <Form.Item
              label="Règles de remédiation"
              tooltip="Configurez des règles pour proposer des actions correctives automatiques lorsque cette action échoue (Story 9.1)."
              style={{ marginBottom: 16 }}
            >
              <RemediationRulesEditor
                value={remediationRules}
                onChange={setRemediationRules}
                currentActionId={editAction?.id}
              />
            </Form.Item>
          ),
        },
        {
          key: 'business-rule-policies',
          label: (
            <Text strong>
              Règles métier
              {businessRulePolicyId != null && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  (configuré)
                </Text>
              )}
            </Text>
          ),
          children: (
            <Form.Item
              label="Règles métier"
              tooltip="Choisissez une règle prédéfinie du catalogue (Admin → Règles métier). Seules les règles liées à votre plateforme d'exécution sont proposées."
              style={{ marginBottom: 16 }}
            >
              <BusinessRulePolicySelector
                policyId={businessRulePolicyId}
                onPolicyIdChange={setBusinessRulePolicyId}
                stepType={
                  getIntegrationById(watchedIntegrationId ?? editAction?.integration_id ?? 0)?.type
                  ?? (editAction?.platform ? platformCodeToStepType(editAction.platform) : undefined)
                }
              />
            </Form.Item>
          ),
        },
        {
          key: 'notifications',
          label: (
            <Text strong>
              Notifications
              {notificationConfig && (notificationConfig.channels.some(ch => ch.enabled) || notificationConfig.page_individual_enabled) && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  (configuré)
                </Text>
              )}
            </Text>
          ),
          children: (
            <Form.Item
              label="Configuration des notifications"
              tooltip="Configurez les canaux de notification (email, Teams, page) et leurs conditions de déclenchement."
              style={{ marginBottom: 16 }}
            >
              <NotificationConfigSection
                value={notificationConfig}
                onChange={setNotificationConfig}
              />
            </Form.Item>
          ),
        },
      ]}
      style={{ marginTop: 16 }}
    />
  );
}
