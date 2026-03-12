/**
 * useActionFormState — Gestion centralisée de l'état de ActionForm (Story 33.5, Task 2).
 * Extrait de ActionForm.tsx : états, effets d'init/reset/focus/tags, et previewData.
 */
import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { Form } from 'antd';
import type { FormInstance } from 'antd';
import type {
  ActionDetail,
  ActionPreviewData,
  ActionEngine,
  ActionPlatform,
  ExecutionStep,
  ImpactLevel,
  ImpactRuleDefinition,
  ParameterDefinition,
} from '../types/api';
import type { RemediationRuleDefinition } from '../components/admin/RemediationRulesEditor';
import {
  getTags,
  updateActionSteps,
  updateActionTags,
  updateRemediationRules,
  checkActionNameAvailable,
} from '../services/admin_service';
// Story 71.1, AC8: Re-export ApiError for ActionForm error handling (DIP)
export { ApiError } from '../services/api_client';
import { schemaToParameterList, parameterListToSchema } from '../utils/parametersSchema';
import { impactRulesToList } from '../utils/impactRulesSchema';
import { integrationTypeToPlatformCode } from '../utils/integrationHelpers';

type IntegrationLike = { id: number; type: string; name: string };

interface UseActionFormStateParams {
  open: boolean;
  editAction?: ActionDetail | null;
  form: FormInstance;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
}

export function useActionFormState({ open, editAction, form, getIntegrationById }: UseActionFormStateParams) {
  const nameInputRef = useRef<HTMLInputElement>(null);

  const [stepsError, setStepsError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [parameterList, setParameterList] = useState<ParameterDefinition[]>([]);
  const [impactRulesList, setImpactRulesList] = useState<ImpactRuleDefinition[]>([]);
  const [defaultImpactLevel, setDefaultImpactLevel] = useState<ImpactLevel | null>(null);
  const [previewEnvironment, setPreviewEnvironment] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagsOptions, setTagsOptions] = useState<{ value: string; label: string }[]>([]);
  const [remediationRules, setRemediationRules] = useState<RemediationRuleDefinition[]>([]);

  // Form.useWatch values pour previewData en temps réel
  const watchedName = Form.useWatch('name', form);
  const watchedDescription = Form.useWatch('description', form);
  const watchedEngine = Form.useWatch('engine', form);
  const watchedIntegrationId = Form.useWatch('integration_id', form);
  const watchedDocumentationMd = Form.useWatch('documentation_md', form);

  // Chargement des tags à l'ouverture
  useEffect(() => {
    if (!open) return;
    getTags()
      .then((list) => setTagsOptions(list.map((t) => ({ value: t.name, label: t.name }))))
      .catch(() => setTagsOptions([]));
  }, [open]);

  // Données de preview pour AdminPreview (Story 2.5)
  const previewData: ActionPreviewData = useMemo(() => {
    const parsedSchema = parameterListToSchema(parameterList);

    let impactLevel: ImpactLevel | null = null;
    if (impactRulesList.length > 0) {
      const targetEnv = previewEnvironment || impactRulesList[0]?.environment;
      const matchingRule = impactRulesList.find((r) => r.environment === targetEnv);
      if (matchingRule?.level) {
        impactLevel = matchingRule.level;
      } else {
        impactLevel = defaultImpactLevel;
      }
    } else {
      impactLevel = defaultImpactLevel;
    }

    return {
      name: (watchedName as string) || '',
      description: (watchedDescription as string) || null,
      engine: (watchedEngine as ActionEngine) || null,
      platform: watchedIntegrationId
        ? (integrationTypeToPlatformCode(getIntegrationById(watchedIntegrationId as number)?.type ?? '') as ActionPlatform)
        : null,
      impact_level: impactLevel,
      parameters_schema: parsedSchema,
      tags: selectedTags,
      documentation_md: (watchedDocumentationMd as string) || null,
    };
  }, [
    watchedName,
    watchedDescription,
    watchedEngine,
    watchedIntegrationId,
    parameterList,
    impactRulesList,
    previewEnvironment,
    defaultImpactLevel,
    selectedTags,
    watchedDocumentationMd,
    getIntegrationById,
  ]);

  // Focus sur le champ nom à l'ouverture (AC #7 accessibilité)
  useEffect(() => {
    if (open) {
      const timer = setTimeout(() => {
        nameInputRef.current?.focus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [open]);

  // Initialisation / reset de l'état à l'ouverture ou au changement d'action éditée
  useEffect(() => {
    if (open && editAction) {
      form.setFieldsValue({
        name: editAction.name,
        description: editAction.description,
        engine: editAction.engine,
        integration_id: editAction.integration_id ?? undefined,
        documentation_md: editAction.documentation_md,
      });
      setExecutionSteps(editAction.execution_steps || []);
      setParameterList(
        schemaToParameterList(editAction.parameters_schema ?? undefined).map((p, i) => ({
          ...p,
          id: p.id ?? `param-${i}-${Date.now()}`,
        }))
      );
      setImpactRulesList(impactRulesToList(editAction.impact_rules ?? undefined));
      setDefaultImpactLevel(editAction.default_impact_level ?? null);
      setPreviewEnvironment(null);
      setSelectedTags(editAction.tags ?? []);
      setRemediationRules(
        (editAction.remediation_rules ?? []).map((r, i) => ({
          ...r,
          id: `rule-${i}-${Date.now()}`,
        }))
      );
    } else if (!open) {
      form.resetFields();
      setExecutionSteps([]);
      setParameterList([]);
      setImpactRulesList([]);
      setDefaultImpactLevel(null);
      setPreviewEnvironment(null);
      setSelectedTags([]);
      setRemediationRules([]);
      setStepsError(null);
      setSaving(false);
    }
  }, [open, editAction, form]);

  // Story 71.1, AC8: Wrapped service operations for DIP compliance
  const handleUpdateSteps = useCallback(
    (actionId: number, steps: ExecutionStep[]) => updateActionSteps(actionId, { steps }),
    [],
  );
  const handleUpdateTags = useCallback(
    (actionId: number, tagNames: string[]) => updateActionTags(actionId, { tag_names: tagNames }),
    [],
  );
  const handleUpdateRemediationRules = useCallback(
    (actionId: number, rules: import('../types/api').RemediationRule[] | null) => updateRemediationRules(actionId, rules),
    [],
  );
  const handleCheckNameAvailable = useCallback(
    (name: string, excludeId?: number) => checkActionNameAvailable(name, excludeId),
    [],
  );

  return {
    nameInputRef,
    stepsError,
    setStepsError,
    saving,
    setSaving,
    executionSteps,
    setExecutionSteps,
    parameterList,
    setParameterList,
    impactRulesList,
    setImpactRulesList,
    defaultImpactLevel,
    setDefaultImpactLevel,
    previewEnvironment,
    setPreviewEnvironment,
    selectedTags,
    setSelectedTags,
    tagsOptions,
    remediationRules,
    setRemediationRules,
    watchedIntegrationId: watchedIntegrationId as number | undefined,
    previewData,
    // Story 71.1, AC8: Service operations
    handleUpdateSteps,
    handleUpdateTags,
    handleUpdateRemediationRules,
    handleCheckNameAvailable,
  };
}
