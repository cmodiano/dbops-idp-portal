/**
 * ActionFormCollapseSections — Sections Collapse extraites de ActionForm (Story 33.5, Task 4).
 * Regroupe les panneaux avancés : Étapes/ServiceNow, Remédiation.
 * Règles métier et Notifications : déplacées au niveau des étapes de workflow (EvaluationStepConfig, service_call).
 */
import { Collapse, Form, Typography } from 'antd';
import type { ActionDetail, ExecutionStep } from '../../types/api';
import type { RemediationRuleDefinition } from './RemediationRulesEditor';
import { StepsEditor } from './StepsEditor';
import { RemediationRulesEditor } from './RemediationRulesEditor';

const { Text } = Typography;

export interface ActionFormCollapseSectionsProps {
  executionSteps: ExecutionStep[];
  setExecutionSteps: (steps: ExecutionStep[]) => void;
  remediationRules: RemediationRuleDefinition[];
  setRemediationRules: (rules: RemediationRuleDefinition[]) => void;
  editAction?: ActionDetail | null;
  watchedIntegrationId: number | undefined;
}

export function ActionFormCollapseSections({
  executionSteps,
  setExecutionSteps,
  remediationRules,
  setRemediationRules,
  editAction,
  watchedIntegrationId,
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
      ]}
      style={{ marginTop: 16 }}
    />
  );
}
