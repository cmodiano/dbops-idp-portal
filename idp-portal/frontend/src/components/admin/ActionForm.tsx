/**
 * ActionForm component for creating/editing catalog actions (Story 2.1, AC #1, #6; Story 2.2, AC #1, #2, #3).
 *
 * Features:
 * - Inline validation (AC #6)
 * - JSON validation for schema and impact_rules
 * - Execution steps editor (Story 2.2, AC #1, #2)
 * - Change type config (Story 2.2, AC #3)
 * - Accessibility: aria-labels, focus management
 */

import { useEffect, useRef, useState } from 'react';
import { Form, Input, Select, Modal, Alert, Collapse, Typography } from 'antd';
import type {
  ActionCreate,
  ActionCategory,
  ActionEngine,
  ActionPlatform,
  ActionDetail,
  ActionResponse,
  ExecutionStep,
  ChangeType,
  RbacPolicies,
} from '../../types/api';
import { StepsEditor } from './StepsEditor';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { RbacEditor } from './RbacEditor';
import { updateActionSteps, updateActionRbac } from '../../services/admin_service';

const { Text } = Typography;

const { TextArea } = Input;

const CATEGORY_OPTIONS: { value: ActionCategory; label: string }[] = [
  { value: 'Provisioning', label: 'Provisioning' },
  { value: 'Patching', label: 'Patching' },
  { value: 'Administration', label: 'Administration' },
  { value: 'Monitoring', label: 'Monitoring' },
];

const ENGINE_OPTIONS: { value: ActionEngine; label: string }[] = [
  { value: 'Oracle', label: 'Oracle' },
  { value: 'SQL Server', label: 'SQL Server' },
  { value: 'DB2', label: 'DB2' },
];

const PLATFORM_OPTIONS: { value: ActionPlatform; label: string }[] = [
  { value: 'AAP', label: 'AAP (Ansible Automation Platform)' },
  { value: 'GitHub Actions', label: 'GitHub Actions' },
  { value: 'Azure DevOps', label: 'Azure DevOps' },
  { value: 'Terraform', label: 'Terraform' },
];

interface ActionFormValues extends ActionCreate {
  execution_steps?: ExecutionStep[];
  change_type_config?: Record<string, ChangeType>;
}

interface ActionFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (action: ActionCreate) => Promise<ActionDetail | ActionResponse | void>;
  loading?: boolean;
  error?: string | null;
  /** If provided, form is in edit mode for existing action (steps-only save) */
  editAction?: ActionDetail | null;
  /** Called after create+steps or edit steps succeed; parent typically closes modal and refreshes */
  onSuccess?: (action: ActionDetail | ActionResponse) => void;
}

export function ActionForm({ open, onCancel, onSubmit, loading, error, editAction, onSuccess }: ActionFormProps) {
  const [form] = Form.useForm<ActionFormValues>();
  const nameInputRef = useRef<HTMLInputElement>(null);
  const [stepsError, setStepsError] = useState<string | null>(null);
  const [rbacError, setRbacError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [changeTypeConfig, setChangeTypeConfig] = useState<Record<string, ChangeType>>({});
  const [rbacPolicies, setRbacPolicies] = useState<RbacPolicies | null>(null);

  const isEditMode = !!editAction;

  // Focus on name input when modal opens (AC #7 accessibility)
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        nameInputRef.current?.focus();
      }, 100);
    }
  }, [open]);

  // Reset form and steps when modal opens/closes or editAction changes
  useEffect(() => {
    if (open && editAction) {
      // Edit mode: populate form with existing values
      form.setFieldsValue({
        name: editAction.name,
        description: editAction.description,
        category: editAction.category,
        engine: editAction.engine,
        platform: editAction.platform,
        parameters_schema: editAction.parameters_schema
          ? JSON.stringify(editAction.parameters_schema, null, 2)
          : undefined,
        impact_rules: editAction.impact_rules
          ? JSON.stringify(editAction.impact_rules, null, 2)
          : undefined,
      } as unknown as ActionFormValues);
      setExecutionSteps(editAction.execution_steps || []);
      setChangeTypeConfig(editAction.change_type_config || {});
      // Parse rbac_policies if present (it's stored as Record<string, unknown>)
      if (editAction.rbac_policies && typeof editAction.rbac_policies === 'object' && 'environments' in editAction.rbac_policies) {
        setRbacPolicies(editAction.rbac_policies as unknown as RbacPolicies);
      } else {
        setRbacPolicies(null);
      }
    } else if (!open) {
      form.resetFields();
      setExecutionSteps([]);
      setChangeTypeConfig({});
      setRbacPolicies(null);
      setStepsError(null);
      setRbacError(null);
    }
  }, [open, editAction, form]);

  const handleFinish = async (values: ActionFormValues) => {
    setStepsError(null);
    setRbacError(null);
    setSaving(true);
    try {
      // In edit mode, require at least one step (Task 5.3; API does not accept empty steps)
      if (isEditMode && executionSteps.length === 0) {
        setStepsError("Au moins une étape est requise pour enregistrer.");
        return;
      }
      // Validate steps when present (block submit if invalid)
      if (executionSteps.length > 0) {
        for (let i = 0; i < executionSteps.length; i++) {
          const s = executionSteps[i];
          if (!s.name?.trim()) {
            setStepsError(`L'étape ${i + 1} doit avoir un nom.`);
            return;
          }
          if (s.is_servicenow_change && (!s.conditional_environments || s.conditional_environments.length === 0)) {
            setStepsError(`L'étape "${s.name}" (ServiceNow) requiert au moins un environnement conditionné.`);
            return;
          }
        }
      }

      const action: ActionCreate = {
        name: values.name,
        description: values.description,
        category: values.category,
        engine: values.engine,
        platform: values.platform,
        parameters_schema: values.parameters_schema
          ? JSON.parse(values.parameters_schema as unknown as string)
          : null,
        impact_rules: values.impact_rules
          ? JSON.parse(values.impact_rules as unknown as string)
          : null,
      };

      const result = await onSubmit(action);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;

      if (executionSteps.length > 0 && actionId) {
        await updateActionSteps(actionId, {
          steps: executionSteps,
          change_type_config: Object.keys(changeTypeConfig).length > 0 ? changeTypeConfig : null,
        });
      }

      // Update RBAC policies if defined (Story 2.3)
      if (rbacPolicies && actionId) {
        // Validate RBAC before sending (Story 2.3, AC #1, #2 — inline validation)
        for (const [env, perm] of Object.entries(rbacPolicies.environments)) {
          if (!perm.profiles || perm.profiles.length === 0) {
            setRbacError(`L'environnement ${env} doit avoir au moins un profil autorise.`);
            return;
          }
          if (perm.requires_approval && (!perm.approver_profiles || perm.approver_profiles.length === 0)) {
            setRbacError(`L'environnement ${env} requiert des profils approbateurs si l'approbation est activee.`);
            return;
          }
        }
        await updateActionRbac(actionId, { policies: rbacPolicies });
      }

      const done = (result as ActionDetail | ActionResponse) ?? editAction;
      if (done) onSuccess?.(done);
    } catch (err) {
      setStepsError(err instanceof Error ? err.message : 'Erreur lors de la mise à jour des étapes');
    } finally {
      setSaving(false);
    }
  };

  const validateJson = (_: unknown, value: string) => {
    if (!value || value.trim() === '') {
      return Promise.resolve();
    }
    try {
      JSON.parse(value);
      return Promise.resolve();
    } catch {
      return Promise.reject(new Error('JSON invalide'));
    }
  };

  return (
    <Modal
      title={isEditMode ? 'Modifier l\'action' : 'Nouvelle action'}
      open={open}
      onCancel={onCancel}
      onOk={() => form.submit()}
      okText={isEditMode ? 'Enregistrer' : 'Creer'}
      cancelText="Annuler"
      confirmLoading={!!(loading || saving)}
      width={720}
      destroyOnClose
    >
      {error && (
        <Alert
          message="Erreur"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {stepsError && (
        <Alert
          message="Erreur etapes"
          description={stepsError}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {rbacError && (
        <Alert
          message="Erreur contrôle d'accès (RBAC)"
          description={rbacError}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        validateTrigger={['onChange', 'onBlur']}
      >
        <Form.Item
          name="name"
          label="Nom de l'action"
          rules={[
            { required: true, message: 'Le nom est requis' },
            { min: 1, max: 255, message: 'Le nom doit faire entre 1 et 255 caracteres' },
          ]}
        >
          <Input
            ref={nameInputRef as never}
            placeholder="Ex: Creer PDB Oracle"
            aria-label="Nom de l'action"
          />
        </Form.Item>

        <Form.Item
          name="description"
          label="Description"
          rules={[{ max: 4000, message: 'La description ne peut pas depasser 4000 caracteres' }]}
        >
          <TextArea
            rows={3}
            placeholder="Description de l'action..."
            aria-label="Description de l'action"
            showCount
            maxLength={4000}
          />
        </Form.Item>

        <Form.Item
          name="category"
          label="Categorie"
          rules={[{ required: true, message: 'La categorie est requise' }]}
        >
          <Select
            options={CATEGORY_OPTIONS}
            placeholder="Selectionnez une categorie"
            aria-label="Categorie de l'action"
          />
        </Form.Item>

        <Form.Item
          name="engine"
          label="Moteur de base de donnees"
          rules={[{ required: true, message: 'Le moteur est requis' }]}
        >
          <Select
            options={ENGINE_OPTIONS}
            placeholder="Selectionnez un moteur"
            aria-label="Moteur de base de donnees"
          />
        </Form.Item>

        <Form.Item
          name="platform"
          label="Plateforme d'execution"
          rules={[{ required: true, message: 'La plateforme est requise' }]}
        >
          <Select
            options={PLATFORM_OPTIONS}
            placeholder="Selectionnez une plateforme"
            aria-label="Plateforme d'execution"
          />
        </Form.Item>

        <Form.Item
          name="parameters_schema"
          label="Schema des parametres (JSON Schema)"
          rules={[{ validator: validateJson }]}
          tooltip="Schema JSON Schema draft-07 definissant les parametres de l'action"
        >
          <TextArea
            rows={4}
            placeholder='{"type": "object", "properties": {...}}'
            aria-label="Schema des parametres au format JSON"
            style={{ fontFamily: 'monospace' }}
          />
        </Form.Item>

        <Form.Item
          name="impact_rules"
          label="Regles d'impact (JSON)"
          rules={[{ validator: validateJson }]}
          tooltip='Ex: {"DEV": {"level": "low"}, "PROD": {"level": "high"}}'
        >
          <TextArea
            rows={3}
            placeholder='{"DEV": {"level": "low"}, "PROD": {"level": "high"}}'
            aria-label="Regles d'impact au format JSON"
            style={{ fontFamily: 'monospace' }}
          />
        </Form.Item>

        {/* Execution Steps Section (Story 2.2, AC #1, #2, #3) */}
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
                    <StepsEditor value={executionSteps} onChange={setExecutionSteps} />
                  </Form.Item>

                  <Form.Item
                    label="Type de changement ServiceNow par environnement"
                    tooltip="Definissez le type de changement (pre-approuve ou CAB) par environnement (AC #3)"
                  >
                    <ChangeTypeConfig value={changeTypeConfig} onChange={setChangeTypeConfig} />
                  </Form.Item>
                </>
              ),
            },
            {
              key: 'rbac-policies',
              label: (
                <Text strong>
                  Controle d'acces (RBAC)
                  {rbacPolicies && (
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      (configure)
                    </Text>
                  )}
                </Text>
              ),
              children: (
                <Form.Item
                  label="Politiques RBAC par environnement"
                  tooltip="Definissez les profils autorises et les regles d'approbation par environnement (Story 2.3, AC #1, #2)"
                >
                  <RbacEditor value={rbacPolicies ?? undefined} onChange={setRbacPolicies} />
                </Form.Item>
              ),
            },
          ]}
          style={{ marginTop: 16 }}
        />
      </Form>
    </Modal>
  );
}
