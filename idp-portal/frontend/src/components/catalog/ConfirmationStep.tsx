/**
 * ConfirmationStep - Step 3 of the execution wizard.
 * Story 17.2, Task 4.3.
 *
 * Shows execution recap and handles submit/scheduling.
 */

import { memo } from 'react';
import {
  Alert,
  Badge,
  Descriptions,
  Typography,
} from 'antd';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { ExecutionEnvironment, ImpactLevel, InventoryItem } from '../../types/api';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import type { SchedulingState } from '../../hooks/useExecutionSubmit';
import { SchedulingPanel } from './SchedulingPanel';
import type { UseSchedulingValidationReturn } from '../../hooks/useSchedulingValidation';
import type { Target } from './TargetSelector';

const { Text, Title } = Typography;

const ENVIRONMENT_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Developpement',
  staging: 'Staging',
  prod: 'Production',
};

const STEP_DESCRIPTIONS_SIMPLIFIED = [
  'Selectionnez la cible sur laquelle executer l\'action. L\'environnement sera derive automatiquement.',
  'Remplissez les informations necessaires. Tous les champs marques sont obligatoires.',
  'Verifiez que tout est correct avant de lancer l\'action.',
];

export interface ConfirmationStepProps {
  action: CatalogActionDetail;
  variant: 'default' | 'simplified';
  selectedTargets: Target[];
  derivedEnvironment: ExecutionEnvironment | null;
  currentImpact: ImpactLevel | null;
  parameters: Record<string, unknown>;
  submitError: string | null;
  environmentsCache: InventoryItem[] | null;
  isScheduling: boolean;
  scheduling: SchedulingState;
  onSchedulingChange: (updates: Partial<SchedulingState>) => void;
  schedulingError: string | null;
  submitting: boolean;
  schedulingValidation: UseSchedulingValidationReturn;
}

export const ConfirmationStep = memo(function ConfirmationStep({
  action,
  variant,
  selectedTargets,
  derivedEnvironment,
  currentImpact,
  parameters,
  submitError,
  environmentsCache,
  isScheduling,
  scheduling,
  onSchedulingChange,
  schedulingError,
  submitting,
  schedulingValidation,
}: ConfirmationStepProps) {
  const changeConfig = action?.change_type_config?.[derivedEnvironment?.toUpperCase() ?? ''];
  const isChangeRequired = changeConfig?.required ?? false;

  const environmentName = environmentsCache?.find((env) => env.id === derivedEnvironment)?.name
    ?? ENVIRONMENT_LABELS[derivedEnvironment!]
    ?? derivedEnvironment;

  return (
    <div>
      {variant === 'simplified' && (
        <Alert
          type="info"
          showIcon
          description={STEP_DESCRIPTIONS_SIMPLIFIED[2]}
          style={{ marginBottom: 16 }}
        />
      )}
      <Title level={5}>{action?.name}</Title>

      <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
        {selectedTargets.length > 0 && (
          <Descriptions.Item label="Cible(s)">
            {selectedTargets.map((t, i) => (
              <Badge
                key={t.name}
                status="processing"
                text={t.name}
                style={{ marginRight: i < selectedTargets.length - 1 ? 8 : 0 }}
              />
            ))}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="Environnement">
          <Badge
            status={derivedEnvironment === 'prod' ? 'warning' : 'processing'}
            text={environmentName}
          />
        </Descriptions.Item>
        {currentImpact && (
          <Descriptions.Item label="Impact">
            <ImpactIndicator level={currentImpact} size="small" />
          </Descriptions.Item>
        )}
        <Descriptions.Item label="Type de changement">
          {isChangeRequired ? (
            <Badge status="warning" text="CAB requis" />
          ) : (
            <Badge status="success" text="Pre-approuve" />
          )}
        </Descriptions.Item>
      </Descriptions>

      {Object.keys(parameters).length > 0 && (
        <>
          <Text strong>Parametres:</Text>
          <Descriptions column={1} size="small" bordered style={{ marginTop: 8 }}>
            {Object.entries(parameters).map(([key, value]) => (
              <Descriptions.Item key={key} label={key}>
                <Text code>{JSON.stringify(value)}</Text>
              </Descriptions.Item>
            ))}
          </Descriptions>
        </>
      )}

      {submitError && (
        <Alert
          message="Erreur"
          description={submitError}
          type="error"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}

      {isScheduling && (
        <SchedulingPanel
          scheduling={scheduling}
          onSchedulingChange={onSchedulingChange}
          schedulingError={schedulingError}
          submitting={submitting}
          validation={schedulingValidation}
        />
      )}
    </div>
  );
});
