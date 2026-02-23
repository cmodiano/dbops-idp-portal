/**
 * useExecutionWizardState - Aggregate state hook for ExecutionWizard.
 * Story 34.13 (SOLID-FE-9): Extracts all coordination logic (7 useEffect +
 * all state + handlers) from ExecutionWizard.tsx into this dedicated hook.
 *
 * Integrates:
 * - useTargetInventory (DIP for fetchInventoryItems)
 * - useWorkflowStepActions (DIP for fetchCatalogActionById)
 * - usePatternResolver
 * - useExecutionSubmit
 * - useSchedulingValidation
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Form, App } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { CatalogActionDetail } from '../services/catalog_service';
import type { ExecutionEnvironment, ImpactLevel, RecurringPatternRequest } from '../types/api';
import type { WizardInitialParams } from '../types/wizard';
import type { Target } from '../components/catalog/TargetSelector';
import { extractParameterFields } from './useDynamicForm';
import { usePatternResolver } from './usePatternResolver';
import { useSchedulingValidation } from './useSchedulingValidation';
import { useExecutionSubmit } from './useExecutionSubmit';
import { useTargetInventory } from './useTargetInventory';
import { useWorkflowStepActions } from './useWorkflowStepActions';
import type { WizardExecutionContextValue } from '../contexts/WizardExecutionContext';
import logger from '../services/logger';

dayjs.extend(utc);

// === Pure functions moved from ExecutionWizard.tsx ===

function evaluateImpact(
  impactRules: Record<string, { level: ImpactLevel; criteria?: string | null }> | null,
  defaultImpact: ImpactLevel | null,
  environment: string
): ImpactLevel | null {
  if (!impactRules) return defaultImpact;
  const envUpper = environment.toUpperCase();
  for (const [env, rule] of Object.entries(impactRules)) {
    if (env.toUpperCase() === envUpper) return rule.level;
  }
  return defaultImpact;
}

function getInvalidWorkflowStepOrders(form: ReturnType<typeof Form.useForm>[0]): number[] {
  const allErrors = form.getFieldsError();
  const invalid = new Set<number>();
  for (const fe of allErrors) {
    if (!fe.errors?.length) continue;
    const name = fe.name as (string | number)[];
    if (name?.[0] !== 'workflow_step_parameters') continue;
    const stepOrderStr = name?.[1];
    const stepOrderNum = typeof stepOrderStr === 'string' ? Number(stepOrderStr) : Number.NaN;
    if (Number.isFinite(stepOrderNum)) invalid.add(stepOrderNum);
  }
  return Array.from(invalid).sort((a, b) => a - b);
}

function buildWorkflowStepParams(
  parameters: Record<string, unknown>,
  isWorkflow: boolean
): Record<string, { parameters: Record<string, unknown> }> | undefined {
  if (!isWorkflow) return undefined;
  const raw = (parameters as Record<string, unknown>)?.workflow_step_parameters as
    | Record<string, { parameters?: Record<string, unknown> }>
    | undefined;
  if (!raw || typeof raw !== 'object') return undefined;
  const out: Record<string, { parameters: Record<string, unknown> }> = {};
  for (const [order, entry] of Object.entries(raw)) {
    const params = entry?.parameters ?? {};
    if (params && typeof params === 'object' && Object.keys(params).length > 0) {
      out[String(order)] = { parameters: params };
    }
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

export interface UseExecutionWizardStateOptions {
  open: boolean;
  action: CatalogActionDetail | null;
  allowedEnvironments: string[];
  onCancel: () => void;
  onSuccess?: (executionId: number) => void;
  parentExecutionId?: number | null;
  initialParams?: WizardInitialParams;
}

export interface UseExecutionWizardStateReturn {
  form: ReturnType<typeof Form.useForm>[0];
  currentStep: number;
  // Target state
  selectedTargets: Target[];
  targetInputMode: 'list' | 'pattern' | 'manual';
  targetPattern: string;
  manualTargetInput: string;
  selectedEnvironment: ExecutionEnvironment | null;
  setSelectedTargets: (targets: Target[]) => void;
  setTargetInputMode: (mode: 'list' | 'pattern' | 'manual') => void;
  setTargetPattern: (p: string) => void;
  setManualTargetInput: (v: string) => void;
  setSelectedEnvironment: (env: ExecutionEnvironment) => void;
  parameters: Record<string, unknown>;
  setParameters: (params: Record<string, unknown>) => void;
  // Workflow
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowInvalidStepOrders: number[];
  workflowValidationSummary: string | null;
  isWorkflow: boolean;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
  isWorkflowStep2Valid: boolean;
  // Derived
  parameterFields: ReturnType<typeof extractParameterFields>;
  effectiveTargetNames: string[];
  requiresTarget: boolean;
  // Submit/scheduling
  execSubmit: ReturnType<typeof useExecutionSubmit>;
  schedulingValidation: ReturnType<typeof useSchedulingValidation>;
  pageMeEnabled: boolean;
  setPageMeEnabled: (v: boolean) => void;
  // Handlers
  handleNext: () => Promise<void>;
  handlePrev: () => void;
  handleSubmit: () => Promise<void>;
  handleSubmitScheduled: () => Promise<void>;
  handleKeyDown: (e: React.KeyboardEvent) => void;
  // Context value for WizardExecutionContextProvider
  wizardCtxValue: WizardExecutionContextValue;
}

export function useExecutionWizardState({
  open,
  action,
  allowedEnvironments,
  onCancel,
  onSuccess,
  parentExecutionId,
  initialParams,
}: UseExecutionWizardStateOptions): UseExecutionWizardStateReturn {
  const { notification } = App.useApp();
  const schedulingValidation = useSchedulingValidation();
  const execSubmit = useExecutionSubmit();
  const { setSubmitError, resetScheduling } = execSubmit;

  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);

  // Target state
  const [selectedTargets, setSelectedTargets] = useState<Target[]>([]);
  const [targetInputMode, setTargetInputMode] = useState<'list' | 'pattern' | 'manual'>('list');
  const [targetPattern, setTargetPattern] = useState('');
  const [manualTargetInput, setManualTargetInput] = useState('');
  const [selectedEnvironment, setSelectedEnvironment] = useState<ExecutionEnvironment | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [pageMeEnabled, setPageMeEnabled] = useState(false);

  // Workflow validation state
  const [workflowInvalidStepOrders, setWorkflowInvalidStepOrders] = useState<number[]>([]);
  const [workflowValidationSummary, setWorkflowValidationSummary] = useState<string | null>(null);

  const isSubmittingRef = useRef(false);

  const isWorkflow = action?.item_type === 'workflow';
  const workflowSteps = useMemo(() => {
    const steps = action?.workflow_steps ?? null;
    if (!isWorkflow || !steps || !Array.isArray(steps)) return [];
    return [...steps].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  }, [action?.workflow_steps, isWorkflow]);

  // Pattern resolution
  const { resolvedTargets: resolvedPatternTargets, isResolving: patternResolving } = usePatternResolver({
    enabled: open,
    inputMode: targetInputMode,
    pattern: targetPattern,
  });

  // Derived values
  const parameterFields = useMemo(() => extractParameterFields(action?.parameters_schema ?? null), [action?.parameters_schema]);

  const effectiveTargetNames = useMemo((): string[] => {
    if (targetInputMode === 'list') return selectedTargets.map((t) => t.name);
    if (targetInputMode === 'pattern') return resolvedPatternTargets.map((t) => t.name);
    if (targetInputMode === 'manual') return manualTargetInput.split(',').map((s) => s.trim()).filter(Boolean);
    return [];
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, manualTargetInput]);

  const selectedServerNames = useMemo((): string[] => effectiveTargetNames, [effectiveTargetNames]);

  const derivedEnvironment = useMemo((): ExecutionEnvironment | null => {
    if (targetInputMode === 'list' && selectedTargets.length > 0)
      return (selectedTargets[0]?.environment as ExecutionEnvironment) ?? null;
    if (targetInputMode === 'pattern' && resolvedPatternTargets.length > 0)
      return (resolvedPatternTargets[0]?.environment as ExecutionEnvironment) ?? null;
    if (targetInputMode === 'manual' || targetInputMode === 'list') {
      if (selectedTargets.length === 0) return selectedEnvironment;
    }
    return selectedEnvironment;
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, selectedEnvironment]);

  const targetsToCheck = targetInputMode === 'pattern' ? resolvedPatternTargets : selectedTargets;
  const hasMixedEnvironments = useMemo((): boolean => {
    if (targetsToCheck.length <= 1) return false;
    return new Set(targetsToCheck.map((t) => t.environment)).size > 1;
  }, [targetsToCheck]);

  const requiresTarget = action?.requires_target !== false;
  const envForInventory = selectedEnvironment || derivedEnvironment;

  const currentImpact = useMemo((): ImpactLevel | null => {
    if (!derivedEnvironment || !action) return null;
    return evaluateImpact(action.impact_rules, action.default_impact_level, derivedEnvironment);
  }, [derivedEnvironment, action]);

  // === DIP: Inventory via useTargetInventory ===
  const { environmentsCache, inventoryData, inventoryWarnings, loadingInventory } = useTargetInventory({
    open,
    actionId: action?.id,
    currentStep,
    parameterFields,
    environment: envForInventory,
    selectedServerNames,
  });

  // === DIP: Workflow step actions via useWorkflowStepActions ===
  const { workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError } = useWorkflowStepActions({
    open,
    actionId: action?.id,
    isWorkflow,
    currentStep,
    workflowSteps,
  });

  const isWorkflowStep2Valid = useMemo(() => {
    if (!isWorkflow || !workflowSteps.length) return true;
    return workflowInvalidStepOrders.length === 0;
  }, [isWorkflow, workflowSteps.length, workflowInvalidStepOrders.length]);

  // === useEffect 1: Reset state on open/close ===
  useEffect(() => {
    if (open && action) {
      if (action.status !== 'published') {
        notification.error({ title: 'Action non disponible', description: "Cette action n'est pas publiée et ne peut pas être exécutée." });
        onCancel();
        return;
      }
      setCurrentStep(0); setParameters({}); setPageMeEnabled(false); setSubmitError(null);
      isSubmittingRef.current = false;
      setWorkflowInvalidStepOrders([]); setWorkflowValidationSummary(null);
      form.resetFields();
      setSelectedTargets([]); setTargetInputMode('list'); setTargetPattern('');
      setManualTargetInput('');
      resetScheduling();
      if (initialParams?.environment) {
        setSelectedEnvironment(initialParams.environment as ExecutionEnvironment);
      } else if (action?.requires_target === false && allowedEnvironments.length === 1) {
        setSelectedEnvironment(allowedEnvironments[0] as ExecutionEnvironment);
      } else {
        setSelectedEnvironment(null);
      }
      if (initialParams?.targetNames && initialParams.targetNames.length > 0) {
        setTargetInputMode('manual');
        setManualTargetInput(initialParams.targetNames.join(', '));
      }
      if (initialParams?.parameters && Object.keys(initialParams.parameters).length > 0) {
        setParameters(initialParams.parameters);
        form.setFieldsValue(initialParams.parameters);
      }
    }
  }, [open, action, form, notification, onCancel, allowedEnvironments, setSubmitError, resetScheduling, initialParams]);

  // === useEffect 2: Validate workflow step parameters ===
  useEffect(() => {
    if (!open || !isWorkflow || currentStep !== 1 || !workflowSteps.length || loadingWorkflowStepActions) return;
    let cancelled = false;
    const run = async () => {
      try {
        await form.validateFields();
        if (!cancelled) { setWorkflowInvalidStepOrders([]); setWorkflowValidationSummary(null); }
      } catch {
        if (cancelled) return;
        const invalidOrders = getInvalidWorkflowStepOrders(form);
        setWorkflowInvalidStepOrders(invalidOrders);
        setWorkflowValidationSummary(invalidOrders.length > 0 ? `Étapes invalides : ${invalidOrders.join(', ')}` : null);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [open, isWorkflow, currentStep, workflowSteps, loadingWorkflowStepActions, workflowStepActions, form, parameters]);

  // === useEffect 3: Re-apply form values on step 2 ===
  useEffect(() => {
    if (!open || currentStep !== 1 || !parameters || Object.keys(parameters).length === 0) return;
    if (isWorkflow && loadingWorkflowStepActions) return;
    if (isWorkflow && workflowSteps.length > 0 && Object.keys(workflowStepActions || {}).length === 0) return;
    try { form.setFieldsValue(parameters); } catch { /* ignore */ }
  }, [open, currentStep, parameters, form, isWorkflow, loadingWorkflowStepActions, workflowSteps.length, workflowStepActions]);

  // === Handlers ===

  const handleNext = useCallback(async () => {
    if (currentStep === 0) {
      if (requiresTarget) {
        if (effectiveTargetNames.length === 0) {
          notification.warning({ title: targetInputMode === 'pattern' ? 'Entrez un pattern (ex: srv-dev-*) et attendez la résolution.' : targetInputMode === 'manual' ? 'Entrez une ou plusieurs cibles, séparées par des virgules.' : 'Veuillez sélectionner au moins une cible.' });
          return;
        }
        if (hasMixedEnvironments) notification.warning({ title: 'Attention', description: 'Les cibles sélectionnées appartiennent à des environnements différents.' });
      } else if (!selectedEnvironment) {
        notification.warning({ title: 'Veuillez sélectionner un environnement.' });
        return;
      }
    } else if (currentStep === 1) {
      try { const values = await form.validateFields(); setParameters(values); setWorkflowValidationSummary(null); }
      catch {
        if (isWorkflow) {
          const invalidOrders = getInvalidWorkflowStepOrders(form);
          setWorkflowInvalidStepOrders(invalidOrders);
          if (invalidOrders.length > 0) setWorkflowValidationSummary(`Étapes invalides : ${invalidOrders.join(', ')}`);
        }
        return;
      }
    }
    setCurrentStep((s) => Math.min(s + 1, 2));
  }, [currentStep, selectedEnvironment, effectiveTargetNames, targetInputMode, requiresTarget, hasMixedEnvironments, form, notification, isWorkflow]);

  const handlePrev = useCallback(() => setCurrentStep((s) => Math.max(s - 1, 0)), []);

  const handleSubmit = useCallback(async () => {
    if (isSubmittingRef.current || execSubmit.isSubmitting) {
      logger.debug('Double-submit blocked in handleSubmit', { component: 'ExecutionWizard', action: 'double_submit_blocked' });
      return;
    }
    if (!action || (!derivedEnvironment && effectiveTargetNames.length === 0)) {
      notification.warning({ title: 'Données incomplètes', description: 'Veuillez compléter toutes les étapes du wizard.' }); return;
    }
    if (action.status !== 'published') {
      const msg = "Cette action n'est plus publiée et ne peut pas être exécutée.";
      execSubmit.setSubmitError(msg);
      notification.error({ title: 'Action non disponible', description: msg });
      return;
    }
    isSubmittingRef.current = true;
    try {
      const targetNames = effectiveTargetNames.length > 0 ? effectiveTargetNames : undefined;
      const executionId = await execSubmit.submitImmediate({
        action_id: action.id, environment: targetNames ? undefined : (derivedEnvironment ?? undefined),
        target_names: targetNames,
        parameters: isWorkflow ? null : (Object.keys(parameters).length > 0 ? parameters : null),
        workflow_step_parameters: buildWorkflowStepParams(parameters, isWorkflow),
        parent_execution_id: parentExecutionId ?? null,
        page_me: pageMeEnabled || undefined,
      });
      if (executionId != null) onSuccess?.(executionId);
    } finally { isSubmittingRef.current = false; }
  }, [action, derivedEnvironment, effectiveTargetNames, parameters, notification, onSuccess, parentExecutionId, isWorkflow, execSubmit, pageMeEnabled]);

  const handleSubmitScheduled = useCallback(async () => {
    if (isSubmittingRef.current || execSubmit.isSubmitting) {
      logger.debug('Double-submit blocked in handleSubmitScheduled', { component: 'ExecutionWizard', action: 'double_submit_blocked' });
      return;
    }
    if (!action || !derivedEnvironment) {
      notification.warning({ title: 'Données incomplètes', description: 'Veuillez compléter toutes les étapes du wizard.' });
      return;
    }
    const { schedulingType, scheduledAt, cronExpression, cronIsValid, dailyHour, dailyMinute, weeklyDayOfWeek, weeklyHour, weeklyMinute } = execSubmit.scheduling;
    if (schedulingType === 'one-time') {
      if (!scheduledAt) { execSubmit.setSchedulingError('Veuillez sélectionner une date et heure'); return; }
      if (scheduledAt.isBefore(dayjs())) { execSubmit.setSchedulingError('La date planifiée doit être dans le futur'); return; }
    } else if (schedulingType === 'cron' && (!cronExpression || !cronIsValid)) {
      execSubmit.setSchedulingError('Veuillez saisir une expression cron valide');
      return;
    }
    if (action.status !== 'published') {
      const msg = "Cette action n'est plus publiée et ne peut pas être planifiée.";
      execSubmit.setSchedulingError(msg);
      notification.error({ title: 'Action non disponible', description: msg });
      return;
    }
    isSubmittingRef.current = true;
    try {
      let recurringPattern: RecurringPatternRequest | undefined;
      if (schedulingType === 'daily') {
        const l = dayjs().hour(dailyHour).minute(dailyMinute).second(0).millisecond(0).utc();
        recurringPattern = { pattern_type: 'daily', pattern_config: { hour: l.hour(), minute: l.minute() } };
      } else if (schedulingType === 'weekly') {
        const l = dayjs().isoWeekday(weeklyDayOfWeek).hour(weeklyHour).minute(weeklyMinute).second(0).millisecond(0).utc();
        recurringPattern = { pattern_type: 'weekly', pattern_config: { day_of_week: l.isoWeekday(), hour: l.hour(), minute: l.minute() } };
      } else if (schedulingType === 'cron') {
        recurringPattern = { pattern_type: 'cron', pattern_config: { cron_expression: cronExpression } };
      }

      const scheduledId = await execSubmit.submitScheduled({
        action_id: action.id, environment: derivedEnvironment,
        parameters: isWorkflow ? null : (Object.keys(parameters).length > 0 ? parameters : null),
        workflow_step_parameters: buildWorkflowStepParams(parameters, isWorkflow),
        scheduled_at: schedulingType === 'one-time' ? scheduledAt?.utc().toISOString() : null,
        recurring_pattern: recurringPattern,
        target_names: selectedTargets.length > 0 ? selectedTargets.map((t) => t.name) : undefined,
        page_me: pageMeEnabled || undefined,
      });

      if (scheduledId != null) {
        if (recurringPattern) {
          let txt = ''; const pad = (n: number) => String(n).padStart(2, '0');
          if (schedulingType === 'daily') txt = `Tous les jours à ${pad(dailyHour)}:${pad(dailyMinute)} (heure locale)`;
          else if (schedulingType === 'weekly') txt = `Tous les ${['', 'lundis', 'mardis', 'mercredis', 'jeudis', 'vendredis', 'samedis', 'dimanches'][weeklyDayOfWeek]} à ${pad(weeklyHour)}:${pad(weeklyMinute)} (heure locale)`;
          else if (schedulingType === 'cron') txt = `Expression cron : ${cronExpression}`;
          notification.success({ title: 'Exécution récurrente créée', description: txt });
        } else {
          notification.success({ title: 'Exécution planifiée', description: `Exécution planifiée pour le ${scheduledAt?.format('DD/MM/YYYY [à] HH:mm')} (heure locale)` });
        }
        onCancel(); if (onSuccess) onSuccess(scheduledId);
      }
    } finally { isSubmittingRef.current = false; }
  }, [action, derivedEnvironment, selectedTargets, parameters, notification, onCancel, onSuccess, isWorkflow, execSubmit, pageMeEnabled]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onCancel();
    else if (e.key === 'Enter' && !e.shiftKey && currentStep < 2) {
      if ((e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); void handleNext(); }
    }
  }, [onCancel, currentStep, handleNext]);

  // Context value (memoized)
  const wizardCtxValue = useMemo((): WizardExecutionContextValue => ({
    environmentsCache,
    inventoryData,
    inventoryWarnings,
    loadingInventory,
    derivedEnvironment,
    currentImpact,
    hasMixedEnvironments,
    resolvedPatternTargets,
    patternResolving,
    selectedServerNames,
  }), [environmentsCache, inventoryData, inventoryWarnings, loadingInventory, derivedEnvironment, currentImpact, hasMixedEnvironments, resolvedPatternTargets, patternResolving, selectedServerNames]);

  return {
    form, currentStep,
    selectedTargets, targetInputMode, targetPattern, manualTargetInput, selectedEnvironment,
    setSelectedTargets, setTargetInputMode, setTargetPattern, setManualTargetInput, setSelectedEnvironment,
    parameters, setParameters,
    workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError,
    workflowInvalidStepOrders, workflowValidationSummary, isWorkflow, workflowSteps, isWorkflowStep2Valid,
    parameterFields, effectiveTargetNames, requiresTarget,
    execSubmit, schedulingValidation,
    pageMeEnabled, setPageMeEnabled,
    handleNext, handlePrev, handleSubmit, handleSubmitScheduled, handleKeyDown,
    wizardCtxValue,
  };
}
