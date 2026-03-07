/**
 * ConfirmationStep - Step 3 of the execution wizard.
 * Story 17.2, Task 4.3.
 * Story 34.13 (SOLID-FE-7): Reduced from 15 to 12 props — 3 props moved
 * to WizardExecutionContext (derivedEnvironment, currentImpact, environmentsCache).
 *
 * Shows execution recap and handles submit/scheduling.
 */

import { memo } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import {
  Alert,
  Badge,
  Checkbox,
  Descriptions,
  Typography,
} from 'antd';
import type { CatalogActionDetail } from '../../services/catalog_service';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import type { SchedulingState } from '../../hooks/useExecutionSubmit';
import { SchedulingPanel } from './SchedulingPanel';
import type { UseSchedulingValidationReturn } from '../../hooks/useSchedulingValidation';
import type { Target } from './TargetSelector';
import { getEnvironmentLabel, isProductionEnvironment } from '../../utils/environmentHelpers';
import { useWizardExecutionContext } from '../../contexts/WizardExecutionContext';

const { Text, Title } = Typography;

import { STEP_DESCRIPTIONS_SIMPLIFIED } from '../../utils/stepDescriptions';

export interface ConfirmationStepProps {
  action: CatalogActionDetail;
  selectedTargets: Target[];
  // 3 props moved to WizardExecutionContext:
  // derivedEnvironment, currentImpact, environmentsCache
  parameters: Record<string, unknown>;
  submitError: string | null;
  isScheduling: boolean;
  scheduling: SchedulingState;
  onSchedulingChange: (updates: Partial<SchedulingState>) => void;
  schedulingError: string | null;
  submitting: boolean;
  schedulingValidation: UseSchedulingValidationReturn;
  /** Story 31.8: Page me checkbox state. */
  pageMeEnabled: boolean;
  /** Story 31.8: Page me checkbox handler. */
  onPageMeChange: (checked: boolean) => void;
}

export const ConfirmationStep = memo(function ConfirmationStep({
  action,
  selectedTargets,
  parameters,
  submitError,
  isScheduling,
  scheduling,
  onSchedulingChange,
  schedulingError,
  submitting,
  schedulingValidation,
  pageMeEnabled,
  onPageMeChange,
}: ConfirmationStepProps) {
  const { isBusinessProfile, hasTab } = useAuth();
  const isAdmin = hasTab?.('admin') ?? false;
  const {
    derivedEnvironment,
    currentImpact,
    environmentsCache,
  } = useWizardExecutionContext();
  const isChangeRequired = action?.execution_steps?.some(
    (step: unknown) => {
      const s = step as Record<string, unknown>;
      const condition = s.condition as { environment_in?: string[] } | null | undefined;
      return (
        s.step_type === 'service_call' &&
        s.integration_type === 'servicenow' &&
        s.operation === 'create_change' &&
        (!condition?.environment_in ||
          condition.environment_in.some(
            (env) => env.toLowerCase() === derivedEnvironment?.toLowerCase(),
          ))
      );
    },
  ) ?? false;

  const environmentName = environmentsCache?.find((env) => env.id === derivedEnvironment)?.name
    ?? (derivedEnvironment ? getEnvironmentLabel(derivedEnvironment) : '');

  return (
    <div>
      {isBusinessProfile && (
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
            status={derivedEnvironment && isProductionEnvironment(derivedEnvironment) ? 'warning' : 'processing'}
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

      {/* Story 31.8: Page me checkbox — shown only if page_individual_enabled */}
      {action?.notification_config?.page_individual_enabled && (
        <div style={{ marginTop: 16 }}>
          <Checkbox
            checked={pageMeEnabled}
            onChange={(e) => onPageMeChange(e.target.checked)}
          >
            Être pagé en cas d&apos;échec (production + critique uniquement)
          </Checkbox>
        </div>
      )}

      {submitError && (
        <Alert
          title="Erreur"
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
          isAdmin={isAdmin}
        />
      )}
    </div>
  );
});
