/**
 * ExecutionWizard - 3-step wizard for action execution.
 * Refactored in Story 17.2 to delegate rendering to sub-components
 * and use extracted hooks for state management.
 *
 * Steps:
 * 1. Target/Environment selection → TargetSelectionStep
 * 2. Parameters form → ParametersFormStep
 * 3. Confirmation → ConfirmationStep
 */

import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import logger from '../../services/logger';
import {
  Modal,
  Steps,
  Button,
  Form,
  Alert,
  Space,
  App,
} from 'antd';
import { ToolOutlined, ClockCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type {
  ExecutionEnvironment,
  ImpactLevel,
  RemediationSuggestion,
  RecurringPatternRequest,
} from '../../types/api';
import { fetchCatalogActionById } from '../../services/catalog_service';
import { fetchInventoryItems } from '../../services/execution_service';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import type { WizardInitialParams } from '../../types/wizard';
import type { Target } from './TargetSelector';
import { extractParameterFields } from '../../hooks/useDynamicForm';
import { usePatternResolver } from '../../hooks/usePatternResolver';
import { useSchedulingValidation } from '../../hooks/useSchedulingValidation';
import { useExecutionSubmit } from '../../hooks/useExecutionSubmit';
import { TargetSelectionStep } from './TargetSelectionStep';
import { ParametersFormStep } from './ParametersFormStep';
import { ConfirmationStep } from './ConfirmationStep';

const ExecutionTimeline = lazy(() => import('../execution').then(m => ({ default: m.ExecutionTimeline })));

dayjs.extend(utc);

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
  variant?: 'default' | 'simplified';
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;
  parentExecutionId?: number | null;
  /** Story 17.15: Initial parameters to pre-fill the wizard (restart execution). */
  initialParams?: WizardInitialParams;
}

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

export function ExecutionWizard({
  open,
  action,
  allowedEnvironments,
  activeExecutionId,
  onCancel,
  onSuccess,
  onBackToCatalog,
  variant = 'default',
  onSuggestionClick,
  parentExecutionId,
  initialParams,
}: ExecutionWizardProps) {
  const { notification } = App.useApp();
  const schedulingValidation = useSchedulingValidation();
  const execSubmit = useExecutionSubmit();

  // Extract stable references for useEffect dependencies
  const { setSubmitError, resetScheduling } = execSubmit;

  const STEP_ITEMS = variant === 'simplified' ? STEP_ITEMS_SIMPLIFIED : STEP_ITEMS_DEFAULT;
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);

  // Target/environment state
  const [selectedTargets, setSelectedTargets] = useState<Target[]>([]);
  const [targetInputMode, setTargetInputMode] = useState<'list' | 'pattern' | 'manual'>('list');
  const [targetPattern, setTargetPattern] = useState('');
  const [manualTargetInput, setManualTargetInput] = useState('');
  const [selectedEnvironment, setSelectedEnvironment] = useState<ExecutionEnvironment | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});

  // Pattern resolution (Story 20.4: extracted to usePatternResolver)
  const { resolvedTargets: resolvedPatternTargets, isResolving: patternResolving } = usePatternResolver({
    enabled: open,
    inputMode: targetInputMode,
    pattern: targetPattern,
  });

  // Workflow state
  const [workflowStepActions, setWorkflowStepActions] = useState<Record<number, CatalogActionDetail>>({});
  const [loadingWorkflowStepActions, setLoadingWorkflowStepActions] = useState(false);
  const [workflowStepActionsError, setWorkflowStepActionsError] = useState<string | null>(null);
  const isWorkflow = action?.item_type === 'workflow';
  const [workflowInvalidStepOrders, setWorkflowInvalidStepOrders] = useState<number[]>([]);
  const [workflowValidationSummary, setWorkflowValidationSummary] = useState<string | null>(null);

  // Inventory state
  const [inventoryData, setInventoryData] = useState<Record<string, import('../../types/api').InventoryItem[]>>({});
  const [loadingInventory, setLoadingInventory] = useState(false);
  const [environmentsCache, setEnvironmentsCache] = useState<import('../../types/api').InventoryItem[] | null>(null);
  const [inventoryWarnings, setInventoryWarnings] = useState<Record<string, boolean>>({});

  const firstFieldRef = useRef<HTMLElement | null>(null);
  const lastInventoryEnvRef = useRef<string | null>(null);
  // Story 23.6 - Track previous selectedServerNames for cache invalidation
  const lastServerNamesRef = useRef<string[] | null>(null);

  // Story 22.5: Synchronous guard to prevent double-submit (React state updates are batched)
  const isSubmittingRef = useRef(false);

  // Derived values
  const parameterFields = useMemo(() => extractParameterFields(action?.parameters_schema ?? null), [action?.parameters_schema]);

  const effectiveTargetNames = useMemo((): string[] => {
    if (targetInputMode === 'list') return selectedTargets.map((t) => t.name);
    if (targetInputMode === 'pattern') return resolvedPatternTargets.map((t) => t.name);
    if (targetInputMode === 'manual') return manualTargetInput.split(',').map((s) => s.trim()).filter(Boolean);
    return [];
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, manualTargetInput]);

  const derivedEnvironment = useMemo((): ExecutionEnvironment | null => {
    if (targetInputMode === 'list' && selectedTargets.length > 0) return (selectedTargets[0]?.environment as ExecutionEnvironment) ?? null;
    if (targetInputMode === 'pattern' && resolvedPatternTargets.length > 0) return (resolvedPatternTargets[0]?.environment as ExecutionEnvironment) ?? null;
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

  const workflowSteps = useMemo(() => {
    const steps = action?.workflow_steps ?? null;
    if (!isWorkflow || !steps || !Array.isArray(steps)) return [];
    return [...steps].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  }, [action?.workflow_steps, isWorkflow]);

  const isWorkflowStep2Valid = useMemo(() => {
    if (!isWorkflow || !workflowSteps.length) return true;
    return workflowInvalidStepOrders.length === 0;
  }, [isWorkflow, workflowSteps.length, workflowInvalidStepOrders.length]);

  const currentImpact = useMemo(() => {
    if (!derivedEnvironment || !action) return null;
    return evaluateImpact(action.impact_rules, action.default_impact_level, derivedEnvironment);
  }, [derivedEnvironment, action]);

  const envForInventory = selectedEnvironment || derivedEnvironment;

  // Story 23.6 - Compute selectedServerNames from effectiveTargetNames
  const selectedServerNames = useMemo((): string[] => {
    return effectiveTargetNames;
  }, [effectiveTargetNames]);

  // === Effects ===

  // Reset state when modal opens/closes
  useEffect(() => {
    if (open && action) {
      if (action.status !== 'published') {
        notification.error({ title: 'Action non disponible', description: 'Cette action n\'est pas publiee et ne peut pas etre executee.' });
        onCancel();
        return;
      }
      setCurrentStep(0); setParameters({}); setSubmitError(null); isSubmittingRef.current = false;
      setWorkflowStepActions({}); setWorkflowStepActionsError(null);
      setWorkflowInvalidStepOrders([]); setWorkflowValidationSummary(null);
      form.resetFields();
      setSelectedTargets([]); setTargetInputMode('list'); setTargetPattern('');
      setManualTargetInput('');
      resetScheduling();

      // Story 17.15: Apply initialParams for restart execution
      if (initialParams?.environment) {
        setSelectedEnvironment(initialParams.environment as ExecutionEnvironment);
      } else if (action?.requires_target === false && allowedEnvironments.length === 1) {
        setSelectedEnvironment(allowedEnvironments[0] as ExecutionEnvironment);
      } else {
        setSelectedEnvironment(null);
      }

      // Story 17.15: Pre-fill target names via manual input mode
      if (initialParams?.targetNames && initialParams.targetNames.length > 0) {
        setTargetInputMode('manual');
        setManualTargetInput(initialParams.targetNames.join(', '));
      }

      // Story 17.15: Pre-fill dynamic parameters
      if (initialParams?.parameters && Object.keys(initialParams.parameters).length > 0) {
        setParameters(initialParams.parameters);
        form.setFieldsValue(initialParams.parameters);
      }
    }
  }, [open, action, form, notification, onCancel, allowedEnvironments, setSubmitError, resetScheduling, initialParams]);

  // Load workflow step actions
  useEffect(() => {
    if (!open || !action || !isWorkflow || currentStep !== 1) return;
    if (!workflowSteps || workflowSteps.length === 0) return;
    const referencedIds = Array.from(new Set(workflowSteps.map((s) => s.referenced_action_id).filter((id): id is number => typeof id === 'number' && Number.isFinite(id))));
    if (referencedIds.length === 0) return;
    let cancelled = false;
    setLoadingWorkflowStepActions(true); setWorkflowStepActionsError(null);
    Promise.all(referencedIds.map(async (id) => {
      if (workflowStepActions[id]) return workflowStepActions[id];
      const res = await fetchCatalogActionById(id);
      return res.data;
    }))
      .then((actions) => { if (!cancelled) { const map = { ...workflowStepActions }; actions.forEach((a) => { map[a.id] = a; }); setWorkflowStepActions(map); } })
      .catch((err: unknown) => { if (!cancelled) setWorkflowStepActionsError(err instanceof Error ? err.message : 'Erreur lors du chargement des actions du workflow'); })
      .finally(() => { if (!cancelled) setLoadingWorkflowStepActions(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, action?.id, isWorkflow, currentStep, workflowSteps]);

  // Validate workflow step parameters
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

  // Load environments
  useEffect(() => {
    if (!open || environmentsCache !== null) return;
    fetchInventoryItems('environments')
      .then((items) => { setEnvironmentsCache(items); setInventoryWarnings((p) => ({ ...p, environments: false })); })
      .catch((err: Error & { code?: string; useCache?: boolean; cachedItems?: import('../../types/api').InventoryItem[] }) => {
        if (err.code === 'INVENTORY_UNAVAILABLE' && err.useCache && err.cachedItems) {
          setEnvironmentsCache(err.cachedItems); setInventoryWarnings((p) => ({ ...p, environments: true }));
        } else { setEnvironmentsCache(null); }
      });
  }, [open, environmentsCache, notification]);

  // Load inventory data for parameter fields
  useEffect(() => {
    if (!open || !action || currentStep !== 1 || !envForInventory) return;
    const sourcesToLoad = new Set<'databases' | 'servers' | 'instances'>();
    parameterFields.forEach((f) => { if (f.inventorySource) sourcesToLoad.add(f.inventorySource); });
    if (sourcesToLoad.size === 0) return;
    const envChanged = lastInventoryEnvRef.current !== envForInventory;
    if (envChanged) lastInventoryEnvRef.current = envForInventory;
    // Story 23.6 — Invalider cache si serveurs sélectionnés changent (LOW-1 fix: French comment)
    const serverNamesChanged = JSON.stringify(lastServerNamesRef.current) !== JSON.stringify(selectedServerNames);
    if (serverNamesChanged) lastServerNamesRef.current = selectedServerNames;
    const toFetch: Array<'databases' | 'servers' | 'instances'> = [];
    sourcesToLoad.forEach((source) => {
      const needsRefetch = source === 'instances' || source === 'databases'
        ? envChanged || serverNamesChanged
        : envChanged;
      if (!needsRefetch && inventoryData[source]?.length > 0) {
        // Already cached and nothing changed - skip
      } else {
        toFetch.push(source);
      }
    });
    if (toFetch.length === 0) return;
    setLoadingInventory(true);
    Promise.all(toFetch.map(async (source) => {
      try {
        // Story 23.6 - Pass server_names for instances/databases
        const options = (source === 'instances' || source === 'databases')
          ? { server_names: selectedServerNames }
          : undefined;
        const items = await fetchInventoryItems(source, envForInventory, options);
        setInventoryWarnings((p) => ({ ...p, [source]: false }));
        return [source, items] as const;
      }
      catch (err: unknown) { const e = err as Error & { code?: string; useCache?: boolean; cachedItems?: import('../../types/api').InventoryItem[] }; if (e.code === 'INVENTORY_UNAVAILABLE' && e.useCache && e.cachedItems) { setInventoryWarnings((p) => ({ ...p, [source]: true })); return [source, e.cachedItems] as const; } return [source, []] as const; }
    })).then((results) => {
      setInventoryData((prevData) => {
        const data = { ...prevData };
        results.forEach(([s, items]) => { data[s] = items; });
        return data;
      });
    }).finally(() => setLoadingInventory(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, action, currentStep, parameterFields, envForInventory, selectedServerNames]);

  // Focus management
  useEffect(() => { if (open && firstFieldRef.current) setTimeout(() => firstFieldRef.current?.focus(), 100); }, [open, currentStep]);

  // Re-apply persisted form values when returning to step 2
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
          notification.warning({ title: targetInputMode === 'pattern' ? 'Entrez un pattern (ex: srv-dev-*) et attendez la resolution.' : targetInputMode === 'manual' ? 'Entrez une ou plusieurs cibles, separees par des virgules.' : 'Veuillez selectionner au moins une cible.' });
          return;
        }
        if (hasMixedEnvironments) notification.warning({ title: 'Attention', description: 'Les cibles selectionnees appartiennent a des environnements differents.' });
      } else if (!selectedEnvironment) {
        notification.warning({ title: 'Veuillez selectionner un environnement.' });
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

  /**
   * Submit immediate execution with double-submit protection.
   *
   * **Double-Submit Protection:**
   * Uses a synchronous ref guard (`isSubmittingRef`) because React batches state updates.
   * A double-click within the same React batch will be blocked by the ref guard.
   * The secondary check (`execSubmit.isSubmitting`) provides defense-in-depth for UI state
   * but is NOT a synchronous guard (React state is batched).
   *
   * **Side Effects:**
   * - Calls `execSubmit.submitImmediate()` (async API call)
   * - Triggers `onSuccess(executionId)` on success
   * - Logs blocked double-submit attempts via `logger.debug()`
   * - Sets ref to `true` before async operation, resets in `finally` block
   *
   * @returns {Promise<void>} Resolves when submission completes (success or error)
   * @throws Never throws — errors are handled by `useExecutionSubmit` hook
   */
  const handleSubmit = useCallback(async () => {
    // Story 22.5: Synchronous guard to prevent double-submit
    // Note: execSubmit.isSubmitting is a React state (batched), so the ref is the primary guard
    if (isSubmittingRef.current || execSubmit.isSubmitting) {
      logger.debug('Double-submit blocked in handleSubmit', { component: 'ExecutionWizard', action: 'double_submit_blocked' });
      return;
    }
    if (!action || (!derivedEnvironment && effectiveTargetNames.length === 0)) {
      notification.warning({ title: 'Donnees incompletes', description: 'Veuillez completer toutes les etapes du wizard.' }); return;
    }
    if (action.status !== 'published') { const msg = 'Cette action n\'est plus publiee et ne peut pas etre executee.'; execSubmit.setSubmitError(msg); notification.error({ title: 'Action non disponible', description: msg }); return; }

    isSubmittingRef.current = true;
    try {
      const targetNames = effectiveTargetNames.length > 0 ? effectiveTargetNames : undefined;
      const executionId = await execSubmit.submitImmediate({
        action_id: action.id, environment: targetNames ? undefined : (derivedEnvironment ?? undefined),
        target_names: targetNames,
        parameters: isWorkflow ? null : (Object.keys(parameters).length > 0 ? parameters : null),
        workflow_step_parameters: buildWorkflowStepParams(parameters, isWorkflow),
        parent_execution_id: parentExecutionId ?? null,
      });
      if (executionId != null) onSuccess?.(executionId);
    } finally {
      isSubmittingRef.current = false;
    }
  }, [action, derivedEnvironment, effectiveTargetNames, parameters, notification, onSuccess, parentExecutionId, isWorkflow, execSubmit]);

  /**
   * Submit scheduled execution with double-submit protection.
   *
   * **Double-Submit Protection:**
   * Uses a synchronous ref guard (`isSubmittingRef`) because React batches state updates.
   * A double-click within the same React batch will be blocked by the ref guard.
   * The secondary check (`execSubmit.isSubmitting`) provides defense-in-depth for UI state
   * but is NOT a synchronous guard (React state is batched).
   *
   * **Side Effects:**
   * - Calls `execSubmit.submitScheduled()` (async API call)
   * - Triggers `onSuccess(scheduledId)` on success
   * - Shows success notification with recurring pattern details
   * - Logs blocked double-submit attempts via `logger.debug()`
   * - Sets ref to `true` before async operation, resets in `finally` block
   *
   * @returns {Promise<void>} Resolves when submission completes (success or error)
   * @throws Never throws — errors are handled by `useExecutionSubmit` hook
   */
  const handleSubmitScheduled = useCallback(async () => {
    // Story 22.5: Synchronous guard to prevent double-submit
    // Note: execSubmit.isSubmitting is a React state (batched), so the ref is the primary guard
    if (isSubmittingRef.current || execSubmit.isSubmitting) {
      logger.debug('Double-submit blocked in handleSubmitScheduled', { component: 'ExecutionWizard', action: 'double_submit_blocked' });
      return;
    }
    if (!action || !derivedEnvironment) { notification.warning({ title: 'Données incomplètes', description: 'Veuillez compléter toutes les étapes du wizard.' }); return; }
    const { schedulingType, scheduledAt, cronExpression, cronIsValid, dailyHour, dailyMinute, weeklyDayOfWeek, weeklyHour, weeklyMinute } = execSubmit.scheduling;
    if (schedulingType === 'one-time') {
      if (!scheduledAt) { execSubmit.setSchedulingError('Veuillez sélectionner une date et heure'); return; }
      if (scheduledAt.isBefore(dayjs())) { execSubmit.setSchedulingError('La date planifiée doit être dans le futur'); return; }
    } else if (schedulingType === 'cron' && (!cronExpression || !cronIsValid)) { execSubmit.setSchedulingError('Veuillez saisir une expression cron valide'); return; }
    if (action.status !== 'published') { const msg = "Cette action n'est plus publiée et ne peut pas être planifiée."; execSubmit.setSchedulingError(msg); notification.error({ title: 'Action non disponible', description: msg }); return; }

    isSubmittingRef.current = true;
    try {
      let recurringPattern: RecurringPatternRequest | undefined;
      if (schedulingType === 'daily') { const l = dayjs().hour(dailyHour).minute(dailyMinute).second(0).millisecond(0).utc(); recurringPattern = { pattern_type: 'daily', pattern_config: { hour: l.hour(), minute: l.minute() } }; }
      else if (schedulingType === 'weekly') { const l = dayjs().isoWeekday(weeklyDayOfWeek).hour(weeklyHour).minute(weeklyMinute).second(0).millisecond(0).utc(); recurringPattern = { pattern_type: 'weekly', pattern_config: { day_of_week: l.isoWeekday(), hour: l.hour(), minute: l.minute() } }; }
      else if (schedulingType === 'cron') recurringPattern = { pattern_type: 'cron', pattern_config: { cron_expression: cronExpression } };

      const scheduledId = await execSubmit.submitScheduled({
        action_id: action.id, environment: derivedEnvironment,
        parameters: isWorkflow ? null : (Object.keys(parameters).length > 0 ? parameters : null),
        workflow_step_parameters: buildWorkflowStepParams(parameters, isWorkflow),
        scheduled_at: schedulingType === 'one-time' ? scheduledAt?.utc().toISOString() : null,
        recurring_pattern: recurringPattern,
        target_names: selectedTargets.length > 0 ? selectedTargets.map((t) => t.name) : undefined,
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
    } finally {
      isSubmittingRef.current = false;
    }
  }, [action, derivedEnvironment, selectedTargets, parameters, notification, onCancel, onSuccess, isWorkflow, execSubmit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onCancel();
    else if (e.key === 'Enter' && !e.shiftKey && currentStep < 2) {
      if ((e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); handleNext(); }
    }
  }, [onCancel, currentStep, handleNext]);

  // === Render ===

  if (!action && !activeExecutionId) return null;

  if (activeExecutionId != null) {
    return (
      <Modal title="Execution en cours" open={open} onCancel={onBackToCatalog ?? onCancel}
        footer={<Button type="primary" onClick={onBackToCatalog ?? onCancel}>Retour au catalogue</Button>}
        width={640} destroyOnHidden styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }} aria-label="Timeline d'execution">
        <Suspense fallback={<div style={{ textAlign: 'center', padding: 24 }}>Chargement...</div>}>
          <ExecutionTimeline executionId={activeExecutionId} mode="realtime" onRetry={onBackToCatalog ?? onCancel}
            onContact={() => { window.location.href = 'mailto:?subject=IDP%20Portal%20-%20Support%20DBA'; }}
            errorCardVariant={variant === 'simplified' ? 'business' : 'default'} onSuggestionClick={onSuggestionClick} />
        </Suspense>
      </Modal>
    );
  }

  const { scheduling, isSubmitting: submitting } = execSubmit;

  return (
    <Modal title={`Executer: ${action!.name}`} open={open} onCancel={onCancel} footer={null} width={640} destroyOnHidden
      styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }} aria-label={`Wizard d'execution: ${action!.name}`}>
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
              action={action!} allowedEnvironments={allowedEnvironments} variant={variant}
              selectedTargets={selectedTargets} onTargetsChange={setSelectedTargets}
              targetInputMode={targetInputMode} onTargetInputModeChange={setTargetInputMode}
              targetPattern={targetPattern} onTargetPatternChange={setTargetPattern}
              manualTargetInput={manualTargetInput} onManualTargetInputChange={setManualTargetInput}
              selectedEnvironment={selectedEnvironment} onEnvironmentChange={setSelectedEnvironment}
              derivedEnvironment={derivedEnvironment} hasMixedEnvironments={hasMixedEnvironments}
              currentImpact={currentImpact} environmentsCache={environmentsCache}
              inventoryWarnings={inventoryWarnings} resolvedPatternTargets={resolvedPatternTargets}
              patternResolving={patternResolving}
            />
          )}
          <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
            <ParametersFormStep
              form={form} action={action!} variant={variant} parameterFields={parameterFields}
              parameters={parameters} onParametersChange={setParameters}
              isWorkflow={isWorkflow} workflowSteps={workflowSteps}
              workflowStepActions={workflowStepActions} loadingWorkflowStepActions={loadingWorkflowStepActions}
              workflowStepActionsError={workflowStepActionsError} workflowValidationSummary={workflowValidationSummary}
              inventoryData={inventoryData} inventoryWarnings={inventoryWarnings} loadingInventory={loadingInventory}
              selectedServerNames={selectedServerNames}
            />
          </div>
          {currentStep === 2 && (
            <ConfirmationStep
              action={action!} variant={variant} selectedTargets={selectedTargets}
              derivedEnvironment={derivedEnvironment} currentImpact={currentImpact}
              parameters={parameters} submitError={execSubmit.submitError} environmentsCache={environmentsCache}
              isScheduling={scheduling.isScheduling} scheduling={scheduling}
              onSchedulingChange={execSubmit.updateScheduling} schedulingError={execSubmit.schedulingError}
              submitting={submitting} schedulingValidation={schedulingValidation}
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
    </Modal>
  );
}
