/**
 * ActionWizard — Wizard 3 étapes pour création/édition d'action (Story 2.22, AC #1–#5).
 *
 * Étapes : (1) Général, (2) Paramètres, (3) Impact & Changement.
 * Réutilise ParametersEditor, ImpactRulesEditor et la logique de build payload d'ActionForm.
 */

import { useEffect, useState } from 'react';
import { Modal, Steps, Button, Form, Input, Select, Alert, Space, notification } from 'antd';
import type {
  ActionCreate,
  ActionDetail,
  ActionResponse,
  ParameterDefinition,
  ImpactRuleDefinition,
  ImpactLevel,
  ChangeTypeConfigEntry,
} from '../../types/api';
import { schemaToParameterList, parameterListToSchema } from '../../utils/parametersSchema';
import { impactRulesToList, listToImpactRules } from '../../utils/impactRulesSchema';
import { ParametersEditor } from './ParametersEditor';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { getTags, updateActionTags, updateActionSteps } from '../../services/admin_service';
import { ENGINE_OPTIONS, PLATFORM_OPTIONS } from '../../utils/actionOptions';

const { TextArea } = Input;

const STEP_ITEMS = [
  { title: 'Général', content: 'Nom, moteur, plateforme, tags' },
  { title: 'Paramètres', content: 'Éditeur visuel des paramètres' },
  { title: 'Impact & Changement', content: 'Règles d\'impact et code modèle' },
];

export interface ActionWizardProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (action: ActionCreate) => Promise<ActionDetail | ActionResponse | void>;
  loading?: boolean;
  error?: string | null;
  editAction?: ActionDetail | null;
  onSuccess?: (action: ActionDetail | ActionResponse) => void;
}

export function ActionWizard({
  open,
  onCancel,
  onSubmit,
  loading,
  error,
  editAction,
  onSuccess,
}: ActionWizardProps) {
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [parameterList, setParameterList] = useState<ParameterDefinition[]>([]);
  const [impactRulesList, setImpactRulesList] = useState<ImpactRuleDefinition[]>([]);
  const [defaultImpactLevel, setDefaultImpactLevel] = useState<ImpactLevel | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagsOptions, setTagsOptions] = useState<{ value: string; label: string }[]>([]);
  const [changeTypeConfig, setChangeTypeConfig] = useState<Record<string, ChangeTypeConfigEntry>>({});

  const isEditMode = !!editAction;

  useEffect(() => {
    if (!open) return;
    getTags()
      .then((list) => setTagsOptions(list.map((t) => ({ value: t.name, label: t.name }))))
      .catch(() => setTagsOptions([]));
  }, [open]);

  useEffect(() => {
    if (open && editAction) {
      form.setFieldsValue({
        name: editAction.name,
        description: editAction.description,
        engine: editAction.engine,
        platform: editAction.platform,
      });
      setParameterList(
        schemaToParameterList(editAction.parameters_schema ?? undefined).map((p, i) => ({
          ...p,
          id: p.id ?? `param-${i}-${Date.now()}`,
        }))
      );
      setImpactRulesList(impactRulesToList(editAction.impact_rules ?? undefined));
      setDefaultImpactLevel(editAction.default_impact_level ?? null);
      setSelectedTags(editAction.tags ?? []);
      setChangeTypeConfig(editAction.change_type_config ?? {});
      setCurrentStep(0);
    } else if (!open) {
      form.resetFields();
      setParameterList([]);
      setImpactRulesList([]);
      setDefaultImpactLevel(null);
      setSelectedTags([]);
      setChangeTypeConfig({});
      setCurrentStep(0);
      setSubmitError(null);
    }
  }, [open, editAction, form]);

  const handleNext = async () => {
    if (currentStep === 0) {
      try {
        await form.validateFields(['name', 'description', 'engine', 'platform']);
      } catch {
        return;
      }
    }
    setCurrentStep((s) => Math.min(s + 1, 2));
  };

  const handlePrev = () => setCurrentStep((s) => Math.max(s - 1, 0));

  const handleSave = async () => {
    setSubmitError(null);
    let values: { name: string; description?: string; engine: ActionEngine; platform: ActionPlatform };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    if (parameterList.length > 0) {
      const names = parameterList.map((p) => (p.name ?? '').trim());
      const emptyIndex = names.findIndex((n) => !n);
      if (emptyIndex >= 0) {
        setSubmitError(`Le paramètre ${emptyIndex + 1} doit avoir un nom.`);
        return;
      }
      const seen = new Set<string>();
      for (let i = 0; i < names.length; i++) {
        if (seen.has(names[i])) {
          setSubmitError(`Deux paramètres ont le même nom "${names[i]}". Chaque nom doit être unique.`);
          return;
        }
        seen.add(names[i]);
      }
    }

    if (impactRulesList.length > 0) {
      const envs = impactRulesList.map((r) => (r.environment ?? '').trim());
      const emptyEnvIndex = envs.findIndex((e) => !e);
      if (emptyEnvIndex >= 0) {
        setSubmitError(`La règle d'impact ${emptyEnvIndex + 1} doit avoir un environnement.`);
        return;
      }
      const seenEnvs = new Set<string>();
      for (let i = 0; i < envs.length; i++) {
        if (seenEnvs.has(envs[i])) {
          setSubmitError(`Deux règles d'impact utilisent l'environnement "${envs[i]}". Chaque environnement doit être unique.`);
          return;
        }
        seenEnvs.add(envs[i]);
      }
      const missingLevelIndex = impactRulesList.findIndex((r) => !r.level);
      if (missingLevelIndex >= 0) {
        setSubmitError(`La règle d'impact ${missingLevelIndex + 1} doit avoir un niveau.`);
        return;
      }
    }

    setSaving(true);
    try {
      const payload: ActionCreate = {
        name: values.name,
        description: values.description,
        engine: values.engine,
        platform: values.platform,
        parameters_schema: parameterListToSchema(parameterList),
        impact_rules: listToImpactRules(impactRulesList),
        default_impact_level: defaultImpactLevel,
      };

      const result = await onSubmit(payload);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;
      const done = (result as ActionDetail | ActionResponse) ?? editAction;

      if (actionId && selectedTags.length >= 0) {
        try {
          await updateActionTags(actionId, { tag_names: selectedTags });
        } catch (tagErr) {
          if (done) onSuccess?.(done);
          notification.warning({
            message: 'Tags non mis à jour',
            description: tagErr instanceof Error ? tagErr.message : 'Les tags n\'ont pas pu être enregistrés. L\'action a bien été créée/modifiée.',
          });
          setSaving(false);
          return;
        }
      }

      if (actionId && Object.keys(changeTypeConfig).length > 0) {
        const change_type_config = Object.fromEntries(
          Object.entries(changeTypeConfig).map(([env, e]) => [
            env,
            { required: e?.required ?? false, change_model_code: e?.required ? (e.change_model_code?.trim() || null) : null },
          ])
        );
        await updateActionSteps(actionId, {
          steps: [{ order: 1, name: 'Étape à configurer', type: 'prerequisite', connector_type: 'none', conditional_environments: null }],
          change_type_config,
        });
      }

      if (done) onSuccess?.(done);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur lors de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  };

  const stepContent = () => {
    return (
      <Form form={form} layout="vertical" initialValues={{ name: '', description: '', engine: undefined, platform: undefined }}>
        <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
          <Form.Item
            name="name"
            label="Nom de l'action"
            rules={[
              { required: true, message: 'Le nom est requis' },
              { min: 1, max: 255, message: 'Le nom doit faire entre 1 et 255 caractères' },
            ]}
          >
            <Input placeholder="Ex: Créer PDB Oracle" aria-label="Nom de l'action" />
          </Form.Item>
          <Form.Item name="description" label="Description" rules={[{ max: 4000, message: 'La description ne peut pas dépasser 4000 caractères' }]}>
            <TextArea rows={3} placeholder="Description de l'action..." aria-label="Description" showCount maxLength={4000} />
          </Form.Item>
          <Form.Item name="engine" label="Moteur de base de données" rules={[{ required: true, message: 'Le moteur est requis' }]}>
            <Select options={ENGINE_OPTIONS} placeholder="Sélectionnez un moteur" aria-label="Moteur" />
          </Form.Item>
          <Form.Item name="platform" label="Plateforme d'exécution" rules={[{ required: true, message: 'La plateforme est requise' }]}>
            <Select options={PLATFORM_OPTIONS} placeholder="Sélectionnez une plateforme" aria-label="Plateforme" />
          </Form.Item>
          <Form.Item label="Tags" tooltip="Tags existants ou saisie libre + Entrée pour en créer un nouveau.">
            <Select
              mode="tags"
              value={selectedTags}
              onChange={(v) => setSelectedTags((Array.isArray(v) ? v : [v]).filter(Boolean) as string[])}
              options={tagsOptions}
              placeholder="Ex: RAC, dataguard, provisioning"
              aria-label="Tags de l'action"
              style={{ width: '100%' }}
              tokenSeparators={[',']}
            />
          </Form.Item>
        </div>
        {currentStep === 1 && (
          <Form.Item label="Paramètres" tooltip="Définissez les paramètres de l'action via l'éditeur visuel.">
            <ParametersEditor value={parameterList} onChange={setParameterList} />
          </Form.Item>
        )}
        {currentStep === 2 && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Form.Item label="Règles d'impact" tooltip="Définissez les règles d'impact par environnement.">
              <ImpactRulesEditor value={impactRulesList} onChange={setImpactRulesList} />
            </Form.Item>
            <Form.Item label="Niveau d'impact par défaut" tooltip="Niveau appliqué quand aucune règle ne correspond à l'environnement.">
              <Select
                value={defaultImpactLevel ?? undefined}
                onChange={(v) => setDefaultImpactLevel(v || null)}
                allowClear
                placeholder="Sélectionnez un niveau par défaut"
                style={{ width: 220 }}
                aria-label="Niveau d'impact par défaut"
                options={[
                  { value: 'low', label: 'Faible (vert)' },
                  { value: 'medium', label: 'Moyen (orange)' },
                  { value: 'high', label: 'Élevé (rouge)' },
                  { value: 'critical', label: 'Critique (rouge foncé)' },
                ]}
              />
            </Form.Item>
            <Form.Item
              label="Changement ServiceNow par environnement"
              tooltip="Pour chaque environnement : activer « Changement requis » et, si actif, saisir le code modèle (alphanumérique, max 50). Story 2.24."
            >
              <ChangeTypeConfig value={changeTypeConfig} onChange={setChangeTypeConfig} />
            </Form.Item>
          </Space>
        )}
      </Form>
    );
  };

  return (
    <Modal
      title={isEditMode ? "Modifier l'action" : 'Nouvelle action'}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={640}
      destroyOnHidden
      styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }}
      aria-label={isEditMode ? "Modifier l'action" : 'Nouvelle action'}
    >
      {error && (
        <Alert message="Erreur" description={error} type="error" showIcon style={{ marginBottom: 16 }} />
      )}
      {submitError && (
        <Alert message="Erreur" description={submitError} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      <Steps
        current={currentStep}
        items={STEP_ITEMS.map((item, i) => ({
          title: item.title,
          ...(item.content != null && { description: item.content }),
          status: i === currentStep ? 'process' : i < currentStep ? 'finish' : 'wait',
        }))}
        style={{ marginBottom: 24 }}
        aria-label={`Étape ${currentStep + 1} sur 3 : ${STEP_ITEMS[currentStep].title}`}
      />

      <div style={{ minHeight: 280 }}>{stepContent()}</div>

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={onCancel}>Annuler</Button>
        <Space>
          {currentStep > 0 && <Button onClick={handlePrev}>Précédent</Button>}
          {currentStep < 2 && (
            <Button type="primary" onClick={handleNext}>
              Suivant
            </Button>
          )}
          {currentStep === 2 && (
            <Button type="primary" onClick={handleSave} loading={!!(loading || saving)}>
              Enregistrer
            </Button>
          )}
        </Space>
      </div>
    </Modal>
  );
}
