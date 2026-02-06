/**
 * ExecutionWizard - 3-step wizard for action execution (Story 4.1, AC #1–#5).
 *
 * Steps:
 * 1. Environnement - Select target environment (dev, staging, prod)
 * 2. Parametres - Dynamic form from action's parameters_schema
 * 3. Confirmation - Recap and confirm execution
 *
 * Features:
 * - State persists when navigating back
 * - Inline validation with real-time feedback
 * - ImpactIndicator updates based on environment selection
 * - Accessible: aria-labels, keyboard navigation, focus management
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Modal,
  Steps,
  Button,
  Form,
  Select,
  Input,
  InputNumber,
  Switch,
  DatePicker,
  Alert,
  Space,
  Typography,
  Descriptions,
  Badge,
  Tooltip,
  App,
  Radio,
} from 'antd';
import { InfoCircleOutlined, WarningOutlined, ToolOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type {
  ExecutionEnvironment,
  ImpactLevel,
  InventoryItem,
  RemediationSuggestion,
  RecurringPatternRequest,
} from '../../types/api';
import { submitExecution, fetchInventoryItems, fetchInventoryTargets } from '../../services/execution_service';
import { createScheduledExecution, validateCronExpression, getCronNextExecutions } from '../../services/scheduled_execution_service';
import { CRON_PRESETS } from '../../utils/cronHelper';
import CronExpressionHelper from '../shared/CronExpressionHelper';
import { debounce } from '../../utils/debounce';
import { useDebounce } from '../../hooks/useDebounce';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { ExecutionTimeline } from '../execution';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { TargetSelector, type Target } from './TargetSelector';
import { matchGlob } from '../../utils/globMatch';

dayjs.extend(utc);

const { Text, Title } = Typography;

/** Step items for default variant (technical users). Story 13.2: renamed Environnement → Cible(s). */
const STEP_ITEMS_DEFAULT = [
  { title: 'Cible(s)', content: 'Choisir la cible' },
  { title: 'Parametres', content: 'Configurer l\'action' },
  { title: 'Confirmation', content: 'Verifier et executer' },
];

/** Step items for simplified variant (business users) — Story 7.2, Task 1.2; Story 13.2: renamed. */
const STEP_ITEMS_SIMPLIFIED = [
  { title: 'Ou executer?', content: 'Selectionnez la cible' },
  { title: 'Informations requises', content: 'Remplissez les champs' },
  { title: 'Verifier et lancer', content: 'Tout est pret?' },
];

/** Step descriptions for simplified variant (business users) — Story 7.2, Task 1.3; Story 13.2: updated. */
const STEP_DESCRIPTIONS_SIMPLIFIED = [
  'Selectionnez la cible sur laquelle executer l\'action. L\'environnement sera derive automatiquement.',
  'Remplissez les informations necessaires. Tous les champs marques sont obligatoires.',
  'Verifiez que tout est correct avant de lancer l\'action.',
];

/** Environment display names. */
const ENVIRONMENT_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Developpement',
  staging: 'Staging',
  prod: 'Production',
};

export interface ExecutionWizardProps {
  /** Whether the wizard modal is open. */
  open: boolean;
  /** Action to execute. */
  action: CatalogActionDetail | null;
  /** Environments where user is allowed to execute. */
  allowedEnvironments: string[];
  /** When set, wizard shows timeline instead of steps (Story 4.6, Task 4.2). */
  activeExecutionId?: number | null;
  /** Callback when wizard is cancelled. */
  onCancel: () => void;
  /** Callback on successful execution submission. Returns execution_id. */
  onSuccess?: (executionId: number) => void;
  /** Callback to close timeline and return to catalog (Story 4.6). */
  onBackToCatalog?: () => void;
  /** Display variant: 'default' for technical users, 'simplified' for business users (Story 7.2, Task 1.1). */
  variant?: 'default' | 'simplified';
  /** Callback when a remediation suggestion is clicked (Story 9.1, Task 12.2). */
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;
  /** Parent execution ID for remediation actions (Story 9.2, Task 14). */
  parentExecutionId?: number | null;
}

/** Parameter field info extracted from JSON Schema. */
interface ParameterField {
  name: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'date-time' | 'select' | 'array';
  label: string;
  description?: string;
  required: boolean;
  enum?: string[];
  pattern?: string;
  minimum?: number;
  maximum?: number;
  default?: unknown;
  /** Inventory source for dropdown population. */
  inventorySource?: 'databases' | 'servers';
}

/** Extract parameter fields from JSON Schema. */
function extractParameterFields(schema: Record<string, unknown> | null): ParameterField[] {
  if (!schema) return [];

  const properties = schema.properties as Record<string, Record<string, unknown>> | undefined;
  const required = (schema.required as string[]) || [];

  if (!properties || typeof properties !== 'object') return [];

  return Object.entries(properties).map(([name, prop]) => {
    let type: ParameterField['type'] = 'string';
    const propType = prop?.type as string | undefined;
    const format = prop?.format as string | undefined;

    if (prop?.enum) {
      type = 'select';
    } else if (propType === 'array') {
      type = 'array';
    } else if (propType === 'number') {
      type = 'number';
    } else if (propType === 'integer') {
      type = 'integer';
    } else if (propType === 'boolean') {
      type = 'boolean';
    } else if (format === 'date') {
      type = 'date';
    } else if (format === 'date-time') {
      type = 'date-time';
    }

    return {
      name,
      type,
      label: (prop?.title as string) || name,
      description: prop?.description as string | undefined,
      required: required.includes(name),
      enum: prop?.enum as string[] | undefined,
      pattern: prop?.pattern as string | undefined,
      minimum: prop?.minimum as number | undefined,
      maximum: prop?.maximum as number | undefined,
      default: prop?.default,
      inventorySource: (prop as Record<string, unknown>)?.source === 'inventory'
        ? ((prop as Record<string, unknown>)?.inventory_type as 'databases' | 'servers' | undefined)
        : undefined,
    };
  });
}

/** Evaluate impact level for an environment based on action's impact_rules. */
function evaluateImpact(
  impactRules: Record<string, { level: ImpactLevel; criteria?: string | null }> | null,
  defaultImpact: ImpactLevel | null,
  environment: string
): ImpactLevel | null {
  if (!impactRules) return defaultImpact;

  // Try exact match (case-insensitive)
  const envUpper = environment.toUpperCase();
  for (const [env, rule] of Object.entries(impactRules)) {
    if (env.toUpperCase() === envUpper) {
      return rule.level;
    }
  }

  return defaultImpact;
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
}: ExecutionWizardProps) {
  const { notification } = App.useApp();

  // Story 7.2, Task 1.2: Select step items based on variant
  const STEP_ITEMS = variant === 'simplified' ? STEP_ITEMS_SIMPLIFIED : STEP_ITEMS_DEFAULT;
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Persisted state across steps
  // Story 13.2: Replace selectedEnvironment with selectedTargets
  const [selectedTargets, setSelectedTargets] = useState<Target[]>([]);
  // Multi-target: input mode (list, pattern, manual)
  const [targetInputMode, setTargetInputMode] = useState<'list' | 'pattern' | 'manual'>('list');
  const [targetPattern, setTargetPattern] = useState('');
  const [manualTargetInput, setManualTargetInput] = useState('');
  const [resolvedPatternTargets, setResolvedPatternTargets] = useState<Target[]>([]);
  const [patternResolving, setPatternResolving] = useState(false);
  // Legacy: keep selectedEnvironment for backward compatibility (actions without targets)
  const [selectedEnvironment, setSelectedEnvironment] = useState<ExecutionEnvironment | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});

  // Multi-target: effective target names for submit (list, pattern, manual)
  const effectiveTargetNames = useMemo((): string[] => {
    if (targetInputMode === 'list') return selectedTargets.map((t) => t.name);
    if (targetInputMode === 'pattern') return resolvedPatternTargets.map((t) => t.name);
    if (targetInputMode === 'manual') {
      return manualTargetInput
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [];
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, manualTargetInput]);

  // Story 13.2, Task 2: Derive environment from selected targets (AC2)
  const derivedEnvironment = useMemo((): ExecutionEnvironment | null => {
    if (targetInputMode === 'list' && selectedTargets.length > 0) {
      const firstEnv = selectedTargets[0]?.environment as ExecutionEnvironment;
      return firstEnv ?? null;
    }
    if (targetInputMode === 'pattern' && resolvedPatternTargets.length > 0) {
      const firstEnv = resolvedPatternTargets[0]?.environment as ExecutionEnvironment;
      return firstEnv ?? null;
    }
    if (targetInputMode === 'manual' || targetInputMode === 'list') {
      if (selectedTargets.length === 0) return selectedEnvironment;
    }
    return selectedEnvironment;
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, selectedEnvironment]);

  // Story 13.2, Task 2.3: Check if targets have mixed environments
  const targetsToCheck = targetInputMode === 'pattern' ? resolvedPatternTargets : selectedTargets;
  const hasMixedEnvironments = useMemo((): boolean => {
    if (targetsToCheck.length <= 1) return false;
    const environments = new Set(targetsToCheck.map((t) => t.environment));
    return environments.size > 1;
  }, [targetsToCheck]);

  // Story 13.2, Task 3: Check if action requires targets
  const requiresTarget = action?.requires_target !== false;

  // Story 11.5: Scheduling state (AC1, AC2)
  const [isScheduling, setIsScheduling] = useState(false);
  const [scheduledAt, setScheduledAt] = useState<Dayjs | null>(null);
  const [schedulingError, setSchedulingError] = useState<string | null>(null);

  // Story 11.7, 11.8: Recurring pattern state (AC1, AC2, AC3)
  const [schedulingType, setSchedulingType] = useState<'one-time' | 'daily' | 'weekly' | 'cron'>('one-time');
  const [dailyHour, setDailyHour] = useState<number>(2);
  const [dailyMinute, setDailyMinute] = useState<number>(0);
  const [weeklyDayOfWeek, setWeeklyDayOfWeek] = useState<number>(1); // 1=Monday
  const [weeklyHour, setWeeklyHour] = useState<number>(14);
  const [weeklyMinute, setWeeklyMinute] = useState<number>(0);
  // Story 11.8: Cron expression state (AC1, AC2, AC3)
  const [cronExpression, setCronExpression] = useState<string>('');
  const [cronIsValid, setCronIsValid] = useState<boolean | null>(null);
  const [cronError, setCronError] = useState<string>('');
  const [cronNextExecutions, setCronNextExecutions] = useState<string[]>([]);
  const [cronValidating, setCronValidating] = useState(false);
  const [showCronHelper, setShowCronHelper] = useState(false);

  // Inventory data for dropdowns (with caching)
  const [inventoryData, setInventoryData] = useState<Record<string, InventoryItem[]>>({});
  const [loadingInventory, setLoadingInventory] = useState(false);
  // Cache for environments (loaded once, reused)
  const [environmentsCache, setEnvironmentsCache] = useState<InventoryItem[] | null>(null);
  // Track inventory availability warnings (Task 4.2)
  const [inventoryWarnings, setInventoryWarnings] = useState<Record<string, boolean>>({});

  // Refs for focus management
  const firstFieldRef = useRef<HTMLElement | null>(null);

  // Parse parameter fields from schema
  const parameterFields = useMemo(
    () => extractParameterFields(action?.parameters_schema ?? null),
    [action?.parameters_schema]
  );

  // Evaluate impact for selected environment (Story 13.2: use derivedEnvironment)
  const currentImpact = useMemo(() => {
    if (!derivedEnvironment || !action) return null;
    return evaluateImpact(
      action.impact_rules,
      action.default_impact_level,
      derivedEnvironment
    );
  }, [derivedEnvironment, action]);

  // Reset state when modal opens/closes or action changes
  useEffect(() => {
    if (open && action) {
      // Verify action is published before allowing execution
      if (action.status !== 'published') {
        notification.error({
          title: 'Action non disponible',
          description: 'Cette action n\'est pas publiee et ne peut pas etre executee.',
        });
        onCancel();
        return;
      }
      setCurrentStep(0);
      setParameters({});
      setSubmitError(null);
      form.resetFields();
      // Story 13.2: Reset targets state
      setSelectedTargets([]);
      setTargetInputMode('list');
      setTargetPattern('');
      setManualTargetInput('');
      setResolvedPatternTargets([]);
      // Story 11.5, 11.7: Reset scheduling state
      setIsScheduling(false);
      setScheduledAt(null);
      setSchedulingError(null);
      setSchedulingType('one-time');
      setDailyHour(2);
      setDailyMinute(0);
      setWeeklyDayOfWeek(1);
      setWeeklyHour(14);
      setWeeklyMinute(0);
      // Story 11.8: Reset cron state
      setCronExpression('');
      setCronIsValid(null);
      setCronError('');
      setCronNextExecutions([]);

      // Story 13.2: For actions without required targets, auto-select environment if only one available
      // For actions with targets, environment is derived from target selection
      if (action.requires_target === false && allowedEnvironments.length === 1) {
        setSelectedEnvironment(allowedEnvironments[0] as ExecutionEnvironment);
      } else {
        setSelectedEnvironment(null);
      }
    }
  }, [open, action, form, notification, onCancel, allowedEnvironments]);

  // Load environments from inventory (cached, loaded once)
  useEffect(() => {
    if (!open || environmentsCache !== null) return;

    fetchInventoryItems('environments')
      .then((items) => {
        setEnvironmentsCache(items);
        setInventoryWarnings((prev) => ({ ...prev, environments: false }));
      })
      .catch((err: Error & { code?: string; useCache?: boolean; cachedItems?: InventoryItem[] }) => {
        if (err.code === 'INVENTORY_UNAVAILABLE' && err.useCache && err.cachedItems) {
          // Use cached data and show discrete warning (Task 4.2)
          setEnvironmentsCache(err.cachedItems);
          setInventoryWarnings((prev) => ({ ...prev, environments: true }));
        } else {
          // Fallback to default environments
          setEnvironmentsCache(null);
        }
      });
  }, [open, environmentsCache, notification]);

  // Track last environment used for inventory fetch to detect changes
  const lastInventoryEnvRef = useRef<string | null>(null);

  // Load inventory data for fields that need it (only on step 2 with environment selected)
  const envForInventory = selectedEnvironment || derivedEnvironment;
  useEffect(() => {
    // Only load inventory when:
    // 1. Modal is open with an action
    // 2. User is on step 2 (parameters step, index 1)
    // 3. Environment has been selected or derived from targets
    if (!open || !action || currentStep !== 1 || !envForInventory) return;

    const sourcesToLoad = new Set<'databases' | 'servers'>();
    parameterFields.forEach((field) => {
      if (field.inventorySource) {
        sourcesToLoad.add(field.inventorySource);
      }
    });

    if (sourcesToLoad.size === 0) return;

    // Check if environment changed - if so, clear cache and re-fetch
    const envChanged = lastInventoryEnvRef.current !== envForInventory;
    if (envChanged) {
      lastInventoryEnvRef.current = envForInventory;
    }

    // Check cache first (skip if environment changed)
    const cached: Record<string, InventoryItem[]> = {};
    const toFetch: Array<'databases' | 'servers'> = [];

    sourcesToLoad.forEach((source) => {
      if (!envChanged && inventoryData[source] && inventoryData[source].length > 0) {
        cached[source] = inventoryData[source];
      } else {
        toFetch.push(source);
      }
    });

    if (toFetch.length === 0) {
      // All data cached, no need to fetch
      return;
    }

    setLoadingInventory(true);
    Promise.all(
      toFetch.map(async (source) => {
        try {
          const items = await fetchInventoryItems(source, envForInventory);
          setInventoryWarnings((prev) => ({ ...prev, [source]: false }));
          return [source, items] as const;
        } catch (err: unknown) {
          const error = err as Error & { code?: string; useCache?: boolean; cachedItems?: InventoryItem[] };
          if (error.code === 'INVENTORY_UNAVAILABLE' && error.useCache && error.cachedItems) {
            // Use cached data and show discrete warning (Task 4.2)
            setInventoryWarnings((prev) => ({ ...prev, [source]: true }));
            return [source, error.cachedItems] as const;
          }
          // Return empty array on error
          return [source, []] as const;
        }
      })
    )
      .then((results) => {
        const data: Record<string, InventoryItem[]> = { ...cached };
        results.forEach(([source, items]) => {
          data[source] = items;
        });
        setInventoryData(data);
      })
      .finally(() => setLoadingInventory(false));
  }, [open, action, currentStep, parameterFields, envForInventory, inventoryData]);

  // Focus first field when step changes
  useEffect(() => {
    if (open && firstFieldRef.current) {
      setTimeout(() => firstFieldRef.current?.focus(), 100);
    }
  }, [open, currentStep]);

  // Multi-target: resolve pattern when targetPattern changes (debounced)
  const debouncedTargetPattern = useDebounce(targetPattern.trim(), 400);
  useEffect(() => {
    if (!open || targetInputMode !== 'pattern' || !debouncedTargetPattern) {
      setResolvedPatternTargets([]);
      return;
    }
    let cancelled = false;
    setPatternResolving(true);
    fetchInventoryTargets()
      .then((targets) => {
        if (cancelled) return;
        const matched = targets.filter((t) => matchGlob(debouncedTargetPattern, t.name));
        setResolvedPatternTargets(matched as Target[]);
      })
      .catch(() => {
        if (!cancelled) setResolvedPatternTargets([]);
      })
      .finally(() => {
        if (!cancelled) setPatternResolving(false);
      });
    return () => { cancelled = true; };
  }, [open, targetInputMode, debouncedTargetPattern]);

  // Handle environment selection
  const handleEnvironmentChange = useCallback((env: ExecutionEnvironment) => {
    setSelectedEnvironment(env);
  }, []);

  // Handle step navigation
  const handleNext = useCallback(async () => {
    if (currentStep === 0) {
      // Story 13.2: Validate target or environment selection
      if (requiresTarget) {
        // Target-based: validate targets (list, pattern, or manual)
        if (effectiveTargetNames.length === 0) {
          const msg = targetInputMode === 'pattern'
            ? 'Entrez un pattern (ex: srv-dev-*) et attendez la resolution.'
            : targetInputMode === 'manual'
              ? 'Entrez une ou plusieurs cibles, separees par des virgules.'
              : 'Veuillez selectionner au moins une cible.';
          notification.warning({ message: msg });
          return;
        }
        // Story 13.2, Task 2.3: Warn if mixed environments
        if (hasMixedEnvironments) {
          notification.warning({
            message: 'Attention',
            description: 'Les cibles selectionnees appartiennent a des environnements differents.',
          });
        }
      } else {
        // Legacy: environment-based selection
        if (!selectedEnvironment) {
          notification.warning({ message: 'Veuillez selectionner un environnement.' });
          return;
        }
      }
    } else if (currentStep === 1) {
      // Validate form fields
      try {
        const values = await form.validateFields();
        setParameters(values);
      } catch {
        return;
      }
    }
    setCurrentStep((s) => Math.min(s + 1, 2));
  }, [currentStep, selectedEnvironment, effectiveTargetNames, targetInputMode, requiresTarget, hasMixedEnvironments, form, notification]);

  const handlePrev = useCallback(() => {
    setCurrentStep((s) => Math.max(s - 1, 0));
  }, []);

  // Story 11.8: Debounced cron validation (AC2)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const validateCronDebounced = useCallback(
    debounce(async (expression: string) => {
      if (!expression || !expression.trim()) {
        setCronIsValid(null);
        setCronError('');
        setCronNextExecutions([]);
        return;
      }

      setCronValidating(true);

      try {
        // Validate expression
        const validation = await validateCronExpression(expression);

        if (validation.valid) {
          setCronIsValid(true);
          setCronError('');

          // Get next executions for preview
          const nextExecs = await getCronNextExecutions(expression, 5);
          setCronNextExecutions(nextExecs);
        } else {
          setCronIsValid(false);
          setCronError(validation.error || 'Expression cron invalide');
          setCronNextExecutions([]);
        }
      } catch {
        setCronIsValid(false);
        setCronError('Erreur de validation');
        setCronNextExecutions([]);
      } finally {
        setCronValidating(false);
      }
    }, 500),
    []
  );

  // Story 11.8: Handle cron expression input change (AC2)
  const handleCronChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const expression = e.target.value;
      setCronExpression(expression);
      validateCronDebounced(expression);
    },
    [validateCronDebounced]
  );

  // Story 11.8: Handle cron preset selection (AC3)
  const handleCronPresetChange = useCallback(
    (value: string) => {
      if (value === 'custom') {
        setCronExpression('');
        setCronIsValid(null);
        setCronNextExecutions([]);
      } else {
        setCronExpression(value);
        validateCronDebounced(value);
      }
    },
    [validateCronDebounced]
  );

  // Handle submission
  const handleSubmit = useCallback(async () => {
    // Story 13.2: Use derivedEnvironment or target_names (backend derives env from targets)
    if (!action || (!derivedEnvironment && effectiveTargetNames.length === 0)) {
      notification.warning({
        message: 'Donnees incompletes',
        description: 'Veuillez completer toutes les etapes du wizard.',
      });
      return;
    }

    // Double-check action is still published
    if (action.status !== 'published') {
      const message = 'Cette action n\'est plus publiee et ne peut pas etre executee.';
      setSubmitError(message);
      notification.error({
        message: 'Action non disponible',
        description: message,
      });
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      // Story 13.2, Task 4: Submit with target_names (list, pattern, or manual)
      const targetNames = effectiveTargetNames.length > 0 ? effectiveTargetNames : undefined;

      const response = await submitExecution({
        action_id: action.id,
        // Story 13.2, AC4: If targets provided, backend derives environment; else use derivedEnvironment
        environment: targetNames ? undefined : derivedEnvironment,
        target_names: targetNames,
        parameters: Object.keys(parameters).length > 0 ? parameters : null,
        // Story 9.2, Task 14: Include parent_execution_id for remediation
        parent_execution_id: parentExecutionId ?? null,
      });

      notification.success({
        title: 'Execution soumise',
        description: `Execution #${response.execution_id} creee avec succes.`,
      });

      // Close wizard and call success callback
      onSuccess?.(response.execution_id);
    } catch (err) {
      // Story 9.2, Task 14: Handle parent validation errors
      const error = err as Error & { code?: string };
      let message = error.message || 'Erreur lors de la soumission';
      if (error.code === 'INVALID_PARENT_STATUS' || message.includes('FAILED')) {
        message = 'L\'exécution parente n\'est pas en échec';
      } else if (error.code === 'PARENT_NOT_FOUND' || message.includes('not found')) {
        message = 'L\'exécution parente est introuvable';
      } else if (error.code === 'FORBIDDEN' || message.includes('forbidden')) {
        message = 'Accès refusé à l\'exécution parente';
      }
      setSubmitError(message);
      notification.error({
        title: 'Erreur',
        description: message,
        duration: 5, // Show error longer
      });
      // Don't close wizard on error - let user retry or cancel
    } finally {
      setSubmitting(false);
    }
  }, [action, derivedEnvironment, effectiveTargetNames, parameters, notification, onSuccess, parentExecutionId]);

  // Story 11.5: Handle scheduled execution error messages (AC6)
  const getSchedulingErrorMessage = useCallback((error: Error & { code?: string; message?: string }) => {
    if (error.code === 'INVALID_SCHEDULED_DATE' || error.message?.includes('past')) {
      return 'La date planifiée doit être dans le futur (vérifiez l\'heure de votre appareil si ce message persiste)';
    }
    if (error.code === 'PERMISSION_DENIED' || error.message?.includes('permission') || error.message?.includes('403')) {
      return "Vous n'avez pas la permission de planifier cette action dans cet environnement";
    }
    if (error.code === 'ACTION_NOT_FOUND' || error.message?.includes('not found') || error.message?.includes('404')) {
      return 'Action introuvable ou non publiée';
    }
    if (error.code === 'INVALID_PARAMETERS') {
      return `Paramètre invalide : ${error.message}`;
    }
    return error.message || 'Une erreur est survenue lors de la planification';
  }, []);

  // Story 11.5, 11.7: Handle scheduled execution submission (AC3)
  const handleSubmitScheduled = useCallback(async () => {
    // Story 13.2: Use derivedEnvironment (from targets or legacy selection)
    if (!action || !derivedEnvironment) {
      notification.warning({
        message: 'Données incomplètes',
        description: 'Veuillez compléter toutes les étapes du wizard.',
      });
      return;
    }

    // Story 11.7, 11.8: Validate based on scheduling type
    if (schedulingType === 'one-time') {
      if (!scheduledAt) {
        setSchedulingError('Veuillez sélectionner une date et heure');
        return;
      }

      // Client-side validation: date must be in the future (AC5)
      if (scheduledAt.isBefore(dayjs())) {
        setSchedulingError('La date planifiée doit être dans le futur');
        return;
      }
    } else if (schedulingType === 'cron') {
      // Story 11.8: Validate cron expression (AC2, AC4)
      if (!cronExpression || !cronIsValid) {
        setSchedulingError('Veuillez saisir une expression cron valide');
        return;
      }
    }

    // Edge case: action unpublished while wizard was open (rare but defensive)
    if (action.status !== 'published') {
      const message = "Cette action n'est plus publiée et ne peut pas être planifiée.";
      setSchedulingError(message);
      notification.error({
        message: 'Action non disponible',
        description: message,
      });
      return;
    }

    setSubmitting(true);
    setSchedulingError(null);

    try {
      // Story 11.7: Build request based on scheduling type
      let recurringPattern: RecurringPatternRequest | undefined;

      if (schedulingType === 'daily') {
        // User enters local time → convert to UTC for storage
        const localMoment = dayjs().hour(dailyHour).minute(dailyMinute).second(0).millisecond(0);
        const utcMoment = localMoment.utc();
        recurringPattern = {
          pattern_type: 'daily',
          pattern_config: {
            hour: utcMoment.hour(),
            minute: utcMoment.minute(),
          },
        };
      } else if (schedulingType === 'weekly') {
        // User enters local time → convert to UTC for storage (day_of_week can change across TZ boundary)
        const localMoment = dayjs().isoWeekday(weeklyDayOfWeek).hour(weeklyHour).minute(weeklyMinute).second(0).millisecond(0);
        const utcMoment = localMoment.utc();
        recurringPattern = {
          pattern_type: 'weekly',
          pattern_config: {
            day_of_week: utcMoment.isoWeekday(),
            hour: utcMoment.hour(),
            minute: utcMoment.minute(),
          },
        };
      } else if (schedulingType === 'cron') {
        // Story 11.8: Cron pattern (AC4)
        recurringPattern = {
          pattern_type: 'cron',
          pattern_config: {
            cron_expression: cronExpression,
          },
        };
      }

      // Story 13.2: scheduled executions also use derivedEnvironment
      const response = await createScheduledExecution({
        action_id: action.id,
        environment: derivedEnvironment,
        parameters: Object.keys(parameters).length > 0 ? parameters : null,
        scheduled_at: schedulingType === 'one-time' ? scheduledAt?.utc().toISOString() : null,
        recurring_pattern: recurringPattern,
        // Story 13.2: Include target_names for scheduled executions
        target_names: selectedTargets.length > 0 ? selectedTargets.map((t) => t.name) : undefined,
      });

      if (import.meta.env.DEV) {
        console.log('[ExecutionWizard] Scheduled execution created:', response.scheduled_execution_id);
      }

      // Story 11.7, 11.8: Different success message for recurring vs one-time
      if (recurringPattern) {
        let scheduleText = '';
        if (schedulingType === 'daily') {
          scheduleText = `Tous les jours à ${String(dailyHour).padStart(2, '0')}:${String(dailyMinute).padStart(2, '0')} (heure locale)`;
        } else if (schedulingType === 'weekly') {
          scheduleText = `Tous les ${['', 'lundis', 'mardis', 'mercredis', 'jeudis', 'vendredis', 'samedis', 'dimanches'][weeklyDayOfWeek]} à ${String(weeklyHour).padStart(2, '0')}:${String(weeklyMinute).padStart(2, '0')} (heure locale)`;
        } else if (schedulingType === 'cron') {
          scheduleText = `Expression cron : ${cronExpression}`;
        }

        notification.success({
          message: 'Exécution récurrente créée',
          description: scheduleText,
        });
      } else {
        notification.success({
          message: 'Exécution planifiée',
          description: `Exécution planifiée pour le ${scheduledAt?.format('DD/MM/YYYY [à] HH:mm')} (heure locale)`,
        });
      }

      // Close wizard after success
      onCancel();
      if (onSuccess) onSuccess(response.scheduled_execution_id);
    } catch (err) {
      const error = err as Error & { code?: string; correlation_id?: string };
      const errorMessage = getSchedulingErrorMessage(error);

      if (import.meta.env.DEV) {
        console.error('[ExecutionWizard] Scheduled execution failed:', error, 'correlation_id:', error.correlation_id);
      }

      notification.error({
        message: 'Erreur de planification',
        description: errorMessage,
        duration: 5,
      });

      setSchedulingError(errorMessage);
      // Wizard stays open for correction (AC6)
    } finally {
      setSubmitting(false);
    }
  }, [action, derivedEnvironment, selectedTargets, parameters, scheduledAt, schedulingType, dailyHour, dailyMinute, weeklyDayOfWeek, weeklyHour, weeklyMinute, cronExpression, cronIsValid, notification, onCancel, onSuccess, getSchedulingErrorMessage]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      } else if (e.key === 'Enter' && !e.shiftKey && currentStep < 2) {
        // Enter advances to next step (except on last step or in multiline inputs)
        const target = e.target as HTMLElement;
        if (target.tagName !== 'TEXTAREA') {
          e.preventDefault();
          handleNext();
        }
      }
    },
    [onCancel, currentStep, handleNext]
  );

  // Render Step 1: Target selection (Story 13.2) or Environment selection (fallback)
  const renderTargetStep = () => (
    <div>
      {/* Story 7.2, Task 1.3: Contextual help description for simplified variant */}
      {variant === 'simplified' && (
        <Alert
          type="info"
          showIcon
          description={STEP_DESCRIPTIONS_SIMPLIFIED[0]}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 13.2: Target-based selection for actions that require targets */}
      {requiresTarget ? (
        <>
          <Form.Item
            label={variant === 'simplified' ? 'Mode de selection' : 'Comment choisir les cibles?'}
            required
          >
            <Radio.Group
              value={targetInputMode}
              onChange={(e) => setTargetInputMode(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="list">Liste</Radio.Button>
              <Radio.Button value="pattern">Pattern</Radio.Button>
              <Radio.Button value="manual">Saisie manuelle</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {targetInputMode === 'list' && (
            <Form.Item
              label={variant === 'simplified' ? 'Cible(s)' : 'Cible(s)'}
              required
              tooltip={variant === 'simplified' ? undefined : 'Selectionnez une ou plusieurs cibles dans la liste.'}
            >
              <TargetSelector
                inputRef={firstFieldRef as React.Ref<HTMLElement>}
                multiple
                value={selectedTargets}
                onChange={setSelectedTargets}
                placeholder="Selectionnez une ou plusieurs cibles"
                ariaLabel="Selection de cibles"
              />
            </Form.Item>
          )}

          {targetInputMode === 'pattern' && (
            <Form.Item
              label="Pattern"
              required
              tooltip="Utilisez * pour tout correspondre et ? pour un caractere (ex: srv-dev-*, assurance-*)"
            >
              <Input
                ref={firstFieldRef as React.Ref<HTMLInputElement>}
                value={targetPattern}
                onChange={(e) => setTargetPattern(e.target.value)}
                placeholder="ex: srv-dev-* ou assurance-*"
                aria-label="Pattern de cibles"
                suffix={patternResolving ? <LoadingOutlined spin /> : null}
              />
              {targetPattern && !patternResolving && (
                <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                  {resolvedPatternTargets.length} cible(s) correspondante(s)
                  {resolvedPatternTargets.length > 0 && `: ${resolvedPatternTargets.map((t) => t.name).slice(0, 5).join(', ')}${resolvedPatternTargets.length > 5 ? '...' : ''}`}
                </Text>
              )}
            </Form.Item>
          )}

          {targetInputMode === 'manual' && (
            <Form.Item
              label="Cibles (séparees par des virgules)"
              required
              tooltip="Entrez les noms des cibles, separes par des virgules (ex: srv-01, srv-02, srv-03)"
            >
              <Input.TextArea
                ref={firstFieldRef as React.Ref<any>}
                value={manualTargetInput}
                onChange={(e) => setManualTargetInput(e.target.value)}
                placeholder="ex: srv-dev-01, srv-dev-02, srv-dev-03"
                aria-label="Liste des cibles"
                rows={3}
              />
              {manualTargetInput && (
                <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                  {manualTargetInput.split(',').map((s) => s.trim()).filter(Boolean).length} cible(s) detectee(s)
                </Text>
              )}
            </Form.Item>
          )}

          {/* Story 13.2, Task 2.3: Warning if targets have mixed environments */}
          {hasMixedEnvironments && (
            <Alert
              type="warning"
              showIcon
              icon={<WarningOutlined />}
              message="Attention"
              description="Les cibles selectionnees appartiennent a des environnements differents. Cela peut causer des problemes."
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Show derived environment */}
          {derivedEnvironment && (
            <Alert
              type="info"
              showIcon
              description={`Environnement derive : ${ENVIRONMENT_LABELS[derivedEnvironment] || derivedEnvironment}`}
              style={{ marginBottom: 16 }}
            />
          )}
        </>
      ) : (
        /* Story 13.2, Task 3: Fallback to environment selection for actions without required targets */
        <>
          <Form.Item
            label={variant === 'simplified' ? 'Environnement' : 'Environnement cible'}
            required
            tooltip={variant === 'simplified' ? undefined : 'Selectionnez l\'environnement sur lequel executer l\'action.'}
          >
            <Select
              ref={(ref) => {
                firstFieldRef.current = ref as unknown as HTMLElement;
              }}
              value={selectedEnvironment ?? undefined}
              onChange={handleEnvironmentChange}
              placeholder="Selectionnez un environnement"
              aria-label="Environnement cible"
              style={{ width: '100%' }}
              loading={environmentsCache === null}
              options={
                environmentsCache && environmentsCache.length > 0
                  ? environmentsCache
                      .filter((env) => allowedEnvironments.includes(env.id) || allowedEnvironments.includes(env.id.toUpperCase()))
                      .map((env) => ({
                        value: env.id as ExecutionEnvironment,
                        label: env.name,
                        disabled: false,
                      }))
                  : (['dev', 'staging', 'prod'] as ExecutionEnvironment[])
                      .filter((env) => allowedEnvironments.includes(env) || allowedEnvironments.includes(env.toUpperCase()))
                      .map((env) => ({
                        value: env,
                        label: ENVIRONMENT_LABELS[env],
                        disabled: false,
                      }))
              }
            />
          </Form.Item>

          {inventoryWarnings.environments && (
            <Badge
              status="warning"
              text="Données inventaire temporairement indisponibles — dernières valeurs en cache"
              style={{
                marginBottom: 8,
                fontSize: '12px',
                color: '#faad14',
                display: 'block',
              }}
            />
          )}

          {/* Story 7.2, Task 2.3: Informative message when environment is auto-selected */}
          {allowedEnvironments.length === 1 && selectedEnvironment && (
            <Alert
              type="success"
              showIcon
              description="Environnement selectionne automatiquement car c'est le seul disponible pour vous."
              style={{ marginBottom: 16 }}
            />
          )}
        </>
      )}

      {/* Production warning (applies to both modes) */}
      {derivedEnvironment === 'prod' && (
        <Alert
          message="Avertissement - Environnement Production"
          description="Vous etes sur le point d'executer une action en production. Verifiez attentivement les parametres."
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Impact indicator (applies to both modes) */}
      {currentImpact !== null && (
        <div style={{ marginTop: 16 }}>
          <Text strong>Niveau d'impact: </Text>
          <ImpactIndicator level={currentImpact} />
        </div>
      )}
    </div>
  );

  // Render Step 2: Parameters form
  const renderParametersStep = () => (
    <Form
      form={form}
      layout="vertical"
      initialValues={parameters}
      onValuesChange={(_, allValues) => setParameters(allValues)}
    >
      {/* Story 7.2, Task 1.3: Contextual help description for simplified variant */}
      {variant === 'simplified' && (
        <Alert
          type="info"
          showIcon
          description={STEP_DESCRIPTIONS_SIMPLIFIED[1]}
          style={{ marginBottom: 16 }}
        />
      )}
      {parameterFields.length === 0 ? (
        <Alert
          title="Aucun parametre requis"
          description={variant === 'simplified'
            ? 'Aucune information supplementaire n\'est necessaire.'
            : 'Cette action ne necessite pas de parametres.'}
          type="info"
          showIcon
        />
      ) : (
        parameterFields.map((field, index) => {
          const rules: unknown[] = [];
          if (field.required) {
            rules.push({ required: true, message: `${field.label} est requis` });
          }
          if (field.pattern) {
            rules.push({ pattern: new RegExp(field.pattern), message: `Format invalide` });
          }
          if (field.minimum !== undefined) {
            rules.push({ type: 'number', min: field.minimum, message: `Minimum: ${field.minimum}` });
          }
          if (field.maximum !== undefined) {
            rules.push({ type: 'number', max: field.maximum, message: `Maximum: ${field.maximum}` });
          }

          // Story 7.2, Task 1.4: Apply sanitizeDescription() in simplified mode
          const displayDescription = variant === 'simplified' && field.description
            ? sanitizeDescription(field.description)
            : field.description;

          const getFieldInput = () => {
            if (field.inventorySource && inventoryData[field.inventorySource]) {
              const hasWarning = inventoryWarnings[field.inventorySource];
              return (
                <div>
                  <Select
                    placeholder={`Selectionnez ${field.label.toLowerCase()}`}
                    aria-label={field.label}
                    loading={loadingInventory}
                    options={inventoryData[field.inventorySource].map((item) => ({
                      value: item.id,
                      label: item.name,
                    }))}
                  />
                  {hasWarning && (
                    <Badge
                      status="warning"
                      text="Données inventaire temporairement indisponibles — dernières valeurs en cache"
                      style={{
                        marginTop: 4,
                        fontSize: '12px',
                        color: '#faad14',
                      }}
                    />
                  )}
                </div>
              );
            }

            switch (field.type) {
              case 'select':
                return (
                  <Select
                    placeholder={`Selectionnez ${field.label.toLowerCase()}`}
                    aria-label={field.label}
                    options={(field.enum || []).map((v) => ({ value: v, label: v }))}
                  />
                );
              case 'number':
              case 'integer':
                return (
                  <InputNumber
                    style={{ width: '100%' }}
                    aria-label={field.label}
                    min={field.minimum}
                    max={field.maximum}
                    precision={field.type === 'integer' ? 0 : undefined}
                  />
                );
              case 'boolean':
                return <Switch aria-label={field.label} />;
              case 'date':
              case 'date-time':
                return (
                  <DatePicker
                    style={{ width: '100%' }}
                    showTime={field.type === 'date-time'}
                    aria-label={field.label}
                  />
                );
              case 'array':
                return (
                  <Select
                    mode="tags"
                    placeholder={`Entrez ${field.label.toLowerCase()}`}
                    aria-label={field.label}
                  />
                );
              default:
                return <Input aria-label={field.label} />;
            }
          };

          return (
            <Form.Item
              key={field.name}
              name={field.name}
              label={field.label}
              rules={rules}
              tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
            >
              {index === 0 ? (
                <div ref={(ref) => { firstFieldRef.current = ref?.querySelector('input, select, [role="combobox"]') as HTMLElement; }}>
                  {getFieldInput()}
                </div>
              ) : (
                getFieldInput()
              )}
            </Form.Item>
          );
        })
      )}
    </Form>
  );

  // Render Step 3: Confirmation
  const renderConfirmationStep = () => {
    // Story 13.2: Use derivedEnvironment for change config lookup
    const changeConfig = action?.change_type_config?.[derivedEnvironment?.toUpperCase() ?? ''];
    const isChangeRequired = changeConfig?.required ?? false;

    // Get environment display name from inventory cache or fallback to labels
    const environmentName = environmentsCache?.find((env) => env.id === derivedEnvironment)?.name
      ?? ENVIRONMENT_LABELS[derivedEnvironment!]
      ?? derivedEnvironment;

    return (
      <div>
        {/* Story 7.2, Task 1.3: Contextual help description for simplified variant */}
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
          {/* Story 13.2: Show targets if selected */}
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

        {/* Story 11.5, 11.7: Scheduling options (AC1, AC2, AC3) */}
        {isScheduling && (
          <div style={{ marginTop: 16 }}>
            {/* Story 11.7: Type de planification (AC1) */}
            <Form.Item label="Type de planification" required>
              <Radio.Group
                value={schedulingType}
                onChange={(e) => {
                  setSchedulingType(e.target.value);
                  setSchedulingError(null);
                }}
                disabled={submitting}
              >
                <Radio value="one-time">Une seule fois</Radio>
                <Radio value="daily">Tous les jours</Radio>
                <Radio value="weekly">Toutes les semaines</Radio>
                <Radio value="cron">Avancé (cron)</Radio>
              </Radio.Group>
            </Form.Item>

            {/* One-time: DatePicker (Story 11.5) */}
            {schedulingType === 'one-time' && (
              <Form.Item
                label="Date et heure d'exécution"
                required
                validateStatus={schedulingError ? 'error' : undefined}
                help={schedulingError}
              >
                <Space align="start">
                  <DatePicker
                    showTime={{ format: 'HH:mm' }}
                    format="DD/MM/YYYY HH:mm"
                    value={scheduledAt}
                    onChange={(date) => {
                      setScheduledAt(date);
                      setSchedulingError(null);
                    }}
                    disabledDate={(current) => current && current.isBefore(dayjs())}
                    disabled={submitting}
                    style={{ width: 220 }}
                    placeholder="Sélectionner une date/heure"
                    aria-label="Date et heure d'exécution planifiée"
                  />
                  <Tooltip title="Heure locale. Convertie automatiquement en UTC pour le stockage.">
                    <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
                  </Tooltip>
                </Space>
              </Form.Item>
            )}

            {/* Daily: Hour and Minute selects (Story 11.7, AC2) */}
            {schedulingType === 'daily' && (
              <Form.Item label="Heure d'exécution (heure locale)" required>
                <Space>
                  <Select
                    value={dailyHour}
                    onChange={setDailyHour}
                    style={{ width: 100 }}
                    disabled={submitting}
                    aria-label="Heure"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <Select.Option key={i} value={i}>
                        {String(i).padStart(2, '0')}h
                      </Select.Option>
                    ))}
                  </Select>
                  <Select
                    value={dailyMinute}
                    onChange={setDailyMinute}
                    style={{ width: 100 }}
                    disabled={submitting}
                    aria-label="Minutes"
                  >
                    {[0, 15, 30, 45].map((m) => (
                      <Select.Option key={m} value={m}>
                        {String(m).padStart(2, '0')}min
                      </Select.Option>
                    ))}
                  </Select>
                  <Tooltip title="Heure locale. Convertie en UTC pour le stockage.">
                    <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
                  </Tooltip>
                </Space>
              </Form.Item>
            )}

            {/* Weekly: Day, Hour and Minute selects (Story 11.7, AC3) */}
            {schedulingType === 'weekly' && (
              <Form.Item label="Jour et heure (heure locale)" required>
                <Space>
                  <Select
                    value={weeklyDayOfWeek}
                    onChange={setWeeklyDayOfWeek}
                    style={{ width: 120 }}
                    disabled={submitting}
                    aria-label="Jour de la semaine"
                  >
                    <Select.Option value={1}>Lundi</Select.Option>
                    <Select.Option value={2}>Mardi</Select.Option>
                    <Select.Option value={3}>Mercredi</Select.Option>
                    <Select.Option value={4}>Jeudi</Select.Option>
                    <Select.Option value={5}>Vendredi</Select.Option>
                    <Select.Option value={6}>Samedi</Select.Option>
                    <Select.Option value={7}>Dimanche</Select.Option>
                  </Select>
                  <Select
                    value={weeklyHour}
                    onChange={setWeeklyHour}
                    style={{ width: 100 }}
                    disabled={submitting}
                    aria-label="Heure"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <Select.Option key={i} value={i}>
                        {String(i).padStart(2, '0')}h
                      </Select.Option>
                    ))}
                  </Select>
                  <Select
                    value={weeklyMinute}
                    onChange={setWeeklyMinute}
                    style={{ width: 100 }}
                    disabled={submitting}
                    aria-label="Minutes"
                  >
                    {[0, 15, 30, 45].map((m) => (
                      <Select.Option key={m} value={m}>
                        {String(m).padStart(2, '0')}min
                      </Select.Option>
                    ))}
                  </Select>
                  <Tooltip title="Heure locale. Convertie en UTC pour le stockage.">
                    <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
                  </Tooltip>
                </Space>
              </Form.Item>
            )}

            {/* Cron: Expression input with validation and preview (Story 11.8, AC1-AC5) */}
            {schedulingType === 'cron' && (
              <div>
                <Form.Item
                  label="Expression cron"
                  required
                  validateStatus={cronIsValid === false ? 'error' : cronIsValid === true ? 'success' : undefined}
                  help={cronError || undefined}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Space>
                      <Select
                        placeholder="Préréglages courants"
                        onChange={handleCronPresetChange}
                        style={{ width: 200 }}
                        disabled={submitting}
                        aria-label="Préréglages cron"
                        allowClear
                        value={CRON_PRESETS.some(p => p.value === cronExpression) ? cronExpression : undefined}
                      >
                        {CRON_PRESETS.map((preset) => (
                          <Select.Option key={preset.value} value={preset.value}>
                            {preset.label}
                          </Select.Option>
                        ))}
                      </Select>
                      <Tooltip title="Aide sur les expressions cron">
                        <Button
                          type="link"
                          icon={<QuestionCircleOutlined />}
                          onClick={() => setShowCronHelper(true)}
                          style={{ padding: 0 }}
                        >
                          Aide
                        </Button>
                      </Tooltip>
                    </Space>
                    <Input
                      value={cronExpression}
                      onChange={handleCronChange}
                      placeholder="minute heure jour mois jour_semaine (ex: 0 2 * * 1-5)"
                      disabled={submitting}
                      aria-label="Expression cron"
                      suffix={
                        cronValidating ? (
                          <LoadingOutlined style={{ color: '#1890ff' }} />
                        ) : cronIsValid === true ? (
                          <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        ) : cronIsValid === false ? (
                          <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                        ) : null
                      }
                    />
                  </Space>
                </Form.Item>

                {/* Next executions preview (Story 11.8, AC5) */}
                {cronIsValid && cronNextExecutions.length > 0 && (
                  <Alert
                    type="info"
                    showIcon
                    icon={<ClockCircleOutlined />}
                    message="Prochaines exécutions (UTC)"
                    description={
                      <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
                        {cronNextExecutions.map((exec, i) => (
                          <li key={i}>
                            {dayjs(exec).utc().format('DD/MM/YYYY HH:mm')}
                          </li>
                        ))}
                      </ul>
                    }
                    style={{ marginBottom: 16 }}
                  />
                )}
              </div>
            )}
          </div>
        )}

        {schedulingError && !submitError && (
          <Alert
            message="Erreur de planification"
            description={schedulingError}
            type="error"
            showIcon
            role="alert"
            aria-live="assertive"
            style={{ marginTop: 16 }}
          />
        )}
      </div>
    );
  };

  if (!action && !activeExecutionId) return null;

  // Story 4.6, Task 4.2: Timeline mode after execution success
  if (activeExecutionId != null) {
    return (
      <Modal
        title="Execution en cours"
        open={open}
        onCancel={onBackToCatalog ?? onCancel}
        footer={
          <Button type="primary" onClick={onBackToCatalog ?? onCancel}>
            Retour au catalogue
          </Button>
        }
        width={640}
        destroyOnHidden
        styles={{
          body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' },
        }}
        aria-label="Timeline d'execution"
      >
        <ExecutionTimeline
          executionId={activeExecutionId}
          mode="realtime"
          onRetry={onBackToCatalog ?? onCancel}
          onContact={() => {
            window.location.href = 'mailto:?subject=IDP%20Portal%20-%20Support%20DBA';
          }}
          errorCardVariant={variant === 'simplified' ? 'business' : 'default'}
          onSuggestionClick={onSuggestionClick}
        />
      </Modal>
    );
  }

  return (
    <Modal
      title={`Executer: ${action!.name}`}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={640}
      destroyOnHidden
      styles={{
        body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' },
      }}
      aria-label={`Wizard d'execution: ${action!.name}`}
    >
      <div onKeyDown={handleKeyDown}>
        {/* Story 9.2, Task 14: Contextual note when executing as remediation */}
        {parentExecutionId && (
          <Alert
            type="info"
            showIcon
            icon={<ToolOutlined />}
            message={`Action corrective pour l'exécution #${parentExecutionId}`}
            style={{ marginBottom: 16 }}
          />
        )}

        <Steps
          current={currentStep}
          items={STEP_ITEMS.map((item, i) => ({
            title: item.title,
            content: item.content,
            status: i === currentStep ? 'process' : i < currentStep ? 'finish' : 'wait',
          }))}
          style={{ marginBottom: 24 }}
          aria-label={`Etape ${currentStep + 1} sur 3: ${STEP_ITEMS[currentStep].title}`}
        />
        {/* ARIA live region for step changes */}
        <div aria-live="polite" aria-atomic="true" style={{ position: 'absolute', left: '-9999px' }}>
          Étape {currentStep + 1} sur 3: {STEP_ITEMS[currentStep].title}
        </div>

        <div style={{ minHeight: 200, padding: '0 8px' }}>
          {currentStep === 0 && renderTargetStep()}
          {currentStep === 1 && renderParametersStep()}
          {currentStep === 2 && renderConfirmationStep()}
        </div>

        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
          <Button onClick={onCancel}>Annuler</Button>
          <Space>
            {currentStep > 0 && (
              <Button onClick={handlePrev}>
                Precedent
              </Button>
            )}
            {currentStep < 2 && (
              <Button
                type="primary"
                onClick={handleNext}
                disabled={currentStep === 0 && (requiresTarget ? selectedTargets.length === 0 : !selectedEnvironment)}
              >
                Suivant
              </Button>
            )}
            {/* Story 11.5: Two execution options (AC1, AC4) */}
            {currentStep === 2 && !isScheduling && (
              <>
                <Button
                  type="primary"
                  onClick={handleSubmit}
                  loading={submitting}
                  style={{ backgroundColor: STYLE_TOKENS.primaryColor }}
                >
                  Exécuter maintenant
                </Button>
                <Button
                  type="default"
                  onClick={() => setIsScheduling(true)}
                  icon={<ClockCircleOutlined />}
                >
                  Planifier
                </Button>
              </>
            )}
            {/* Story 11.5, 11.7, 11.8: Scheduling mode buttons (AC3) */}
            {currentStep === 2 && isScheduling && (
              <>
                <Button onClick={() => { setIsScheduling(false); setSchedulingError(null); setScheduledAt(null); }}>
                  Annuler planification
                </Button>
                <Button
                  type="primary"
                  onClick={handleSubmitScheduled}
                  loading={submitting}
                  disabled={
                    schedulingType === 'one-time' ? !scheduledAt :
                    schedulingType === 'cron' ? !cronIsValid :
                    false // daily/weekly always valid
                  }
                  style={{ backgroundColor: STYLE_TOKENS.primaryColor }}
                >
                  Confirmer planification
                </Button>
              </>
            )}
          </Space>
        </div>

        {/* Story 11.8: Cron expression helper modal (AC3) */}
        <CronExpressionHelper
          open={showCronHelper}
          onClose={() => setShowCronHelper(false)}
        />
      </div>
    </Modal>
  );
}
