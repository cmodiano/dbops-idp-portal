/**
 * ExecutionWizard - 3-step wizard for action execution.
 * Story 34.13 (SOLID-FE-4, SOLID-FE-7, SOLID-FE-9): Refactored to:
 * - Use useExecutionWizardState hook (all state/effects/handlers)
 * - Provide WizardExecutionContextProvider to steps (DIP prop reduction)
 * - Remove direct service imports (fetchCatalogActionById, fetchInventoryItems)
 *
 * Steps:
 * 1. Target/Environment selection → TargetSelectionStep
 * 2. Parameters form → ParametersFormStep
 * 3. Confirmation → ConfirmationStep
 */

import { lazy, Suspense } from 'react';
import {
  Modal,
  Steps,
  Button,
  Alert,
  Space,
} from 'antd';
import { ToolOutlined, ClockCircleOutlined } from '@ant-design/icons';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { RemediationSuggestion } from '../../types/api';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import type { WizardInitialParams } from '../../types/wizard';
import { useAuth } from '../../contexts/AuthContext';
import { useExecutionWizardState } from '../../hooks/useExecutionWizardState';
import { WizardExecutionContextProvider } from '../../contexts/WizardExecutionContext';
import { TargetSelectionStep } from './TargetSelectionStep';
import { ParametersFormStep } from './ParametersFormStep';
import { ConfirmationStep } from './ConfirmationStep';

const ExecutionTimeline = lazy(() => import('../execution').then(m => ({ default: m.ExecutionTimeline })));

const STEP_ITEMS_DEFAULT = [
  { title: 'Cible(s)', content: 'Choisir la cible' },
  { title: 'Parametres', content: 'Configurer l\'action' },
  { title: 'Confirmation', content: 'Verifier et executer' },
];

const STEP_ITEMS_SIMPLIFIED = [
  { title: 'Ou executer?', content: 'Selectionnez la cible' },
  { title: 'Informations requises', content: 'Remplissez les champs' },
  { title: 'Verifier et lancer', content: 'Tout est pret?' },
];

export interface ExecutionWizardProps {
  open: boolean;
  action: CatalogActionDetail | null;
  allowedEnvironments: string[];
  activeExecutionId?: number | null;
  onCancel: () => void;
  onSuccess?: (executionId: number) => void;
  onBackToCatalog?: () => void;
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;
  parentExecutionId?: number | null;
  /** Story 17.15: Initial parameters to pre-fill the wizard (restart execution). */
  initialParams?: WizardInitialParams;
}

export function ExecutionWizard({
  open,
  action,
  allowedEnvironments,
  activeExecutionId,
  onCancel,
  onSuccess,
  onBackToCatalog,
  onSuggestionClick,
  parentExecutionId,
  initialParams,
}: ExecutionWizardProps) {
  const { isBusinessProfile } = useAuth();
  const STEP_ITEMS = isBusinessProfile ? STEP_ITEMS_SIMPLIFIED : STEP_ITEMS_DEFAULT;

  const {
    form, currentStep,
    selectedTargets, targetInputMode, targetPattern, manualTargetInput, selectedEnvironment,
    setSelectedTargets, setTargetInputMode, setTargetPattern, setManualTargetInput, setSelectedEnvironment,
    parameters, setParameters,
    workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError, workflowValidationSummary,
    isWorkflow, workflowSteps, isWorkflowStep2Valid,
    parameterFields, effectiveTargetNames, requiresTarget,
    execSubmit, schedulingValidation,
    pageMeEnabled, setPageMeEnabled,
    handleNext, handlePrev, handleSubmit, handleSubmitScheduled, handleKeyDown,
    wizardCtxValue,
  } = useExecutionWizardState({ open, action, allowedEnvironments, onCancel, onSuccess, parentExecutionId, initialParams });

  if (!action && !activeExecutionId) return null;

  if (activeExecutionId != null) {
    return (
      <Modal title="Execution en cours" open={open} onCancel={onBackToCatalog ?? onCancel}
        footer={<Button type="primary" onClick={onBackToCatalog ?? onCancel}>Retour au catalogue</Button>}
        width={640} destroyOnHidden styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }} aria-label="Timeline d'execution">
        <Suspense fallback={<div style={{ textAlign: 'center', padding: 24 }}>Chargement...</div>}>
          <ExecutionTimeline executionId={activeExecutionId} mode="realtime" onRetry={onBackToCatalog ?? onCancel}
            onContact={() => { window.location.href = 'mailto:?subject=IDP%20Portal%20-%20Support%20DBA'; }}
            errorCardVariant={isBusinessProfile ? 'business' : 'default'} onSuggestionClick={onSuggestionClick} />
        </Suspense>
      </Modal>
    );
  }

  const { scheduling, isSubmitting: submitting } = execSubmit;

  return (
    <Modal title={`Executer: ${action!.name}`} open={open} onCancel={onCancel} footer={null} width={640} destroyOnHidden
      styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }} aria-label={`Wizard d'execution: ${action!.name}`}>
      <WizardExecutionContextProvider value={wizardCtxValue}>
        <div onKeyDown={handleKeyDown}>
          {parentExecutionId && (
            <Alert type="info" showIcon icon={<ToolOutlined />} title={`Action corrective pour l'exécution #${parentExecutionId}`} style={{ marginBottom: 16 }} />
          )}

          <Steps current={currentStep}
            items={STEP_ITEMS.map((item, i) => ({ title: item.title, content: item.content, status: i === currentStep ? 'process' as const : i < currentStep ? 'finish' as const : 'wait' as const }))}
            style={{ marginBottom: 24 }} aria-label={`Etape ${currentStep + 1} sur 3: ${STEP_ITEMS[currentStep].title}`} />
          <div aria-live="polite" aria-atomic="true" style={{ position: 'absolute', left: '-9999px' }}>
            Étape {currentStep + 1} sur 3: {STEP_ITEMS[currentStep].title}
          </div>

          <div style={{ minHeight: 200, padding: '0 8px' }}>
            {currentStep === 0 && (
              <TargetSelectionStep
                action={action!} allowedEnvironments={allowedEnvironments}
                selectedTargets={selectedTargets} onTargetsChange={setSelectedTargets}
                targetInputMode={targetInputMode} onTargetInputModeChange={setTargetInputMode}
                targetPattern={targetPattern} onTargetPatternChange={setTargetPattern}
                manualTargetInput={manualTargetInput} onManualTargetInputChange={setManualTargetInput}
                selectedEnvironment={selectedEnvironment} onEnvironmentChange={setSelectedEnvironment}
              />
            )}
            <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
              <ParametersFormStep
                form={form} parameterFields={parameterFields}
                parameters={parameters} onParametersChange={setParameters}
                isWorkflow={isWorkflow} workflowSteps={workflowSteps}
                workflowStepActions={workflowStepActions} loadingWorkflowStepActions={loadingWorkflowStepActions}
                workflowStepActionsError={workflowStepActionsError} workflowValidationSummary={workflowValidationSummary}
              />
            </div>
            {currentStep === 2 && (
              <ConfirmationStep
                action={action!} selectedTargets={selectedTargets}
                parameters={parameters} submitError={execSubmit.submitError}
                isScheduling={scheduling.isScheduling} scheduling={scheduling}
                onSchedulingChange={execSubmit.updateScheduling} schedulingError={execSubmit.schedulingError}
                submitting={submitting} schedulingValidation={schedulingValidation}
                pageMeEnabled={pageMeEnabled} onPageMeChange={setPageMeEnabled}
              />
            )}
          </div>

          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={onCancel}>Annuler</Button>
            <Space>
              {currentStep > 0 && <Button onClick={handlePrev}>Precedent</Button>}
              {currentStep < 2 && (
                <Button type="primary" onClick={handleNext}
                  disabled={(currentStep === 0 && (requiresTarget ? effectiveTargetNames.length === 0 : !selectedEnvironment)) || (currentStep === 1 && isWorkflow && !isWorkflowStep2Valid)}>
                  Suivant
                </Button>
              )}
              {currentStep === 2 && !scheduling.isScheduling && (
                <>
                  <Button type="primary" onClick={handleSubmit} loading={submitting} disabled={submitting} aria-busy={submitting} style={{ backgroundColor: STYLE_TOKENS.primaryColor }}>Exécuter maintenant</Button>
                  <Button type="default" onClick={() => execSubmit.updateScheduling({ isScheduling: true })} icon={<ClockCircleOutlined />}>Planifier</Button>
                </>
              )}
              {currentStep === 2 && scheduling.isScheduling && (
                <>
                  <Button onClick={() => { execSubmit.updateScheduling({ isScheduling: false }); execSubmit.setSchedulingError(null); execSubmit.updateScheduling({ scheduledAt: null }); }}>Annuler planification</Button>
                  <Button type="primary" onClick={handleSubmitScheduled} loading={submitting}
                    disabled={submitting || (scheduling.schedulingType === 'one-time' ? !scheduling.scheduledAt : scheduling.schedulingType === 'cron' ? !scheduling.cronIsValid : false)}
                    aria-busy={submitting}
                    style={{ backgroundColor: STYLE_TOKENS.primaryColor }}>Confirmer planification</Button>
                </>
              )}
            </Space>
          </div>
        </div>
      </WizardExecutionContextProvider>
    </Modal>
  );
}
