/**
 * IntegrationForm — création/édition d'intégration (Story 2.28, 4.9, 13.1, 24.2).
 * Story 24.2: Type restreint au catalogue backend (Select), actions disponibles, mode édition disabled, validation type actif.
 * Story 13.1: Si type = inventory_db, champs Schéma et Table (config) pour inventaire BD.
 */

import { useEffect, useState } from 'react';
import { Form, Input, Modal, Alert, Select, Avatar, Space, Button, Upload, App } from 'antd';
import { useAuth } from '../../contexts/AuthContext';
import type { UploadFile } from 'antd';
import { UploadOutlined, ApiOutlined, InfoCircleOutlined, ExclamationCircleOutlined, WarningOutlined } from '@ant-design/icons';
import type { AuthFlow, IntegrationCreate, IntegrationUpdate, IntegrationResponse } from '../../types/api';
import { AUTH_FLOW_LABELS } from '../../types/api';
import { getIconUrl } from '../../utils/iconUrl';
import { useIntegrationTypes } from '../../hooks/useIntegrationTypes';
import { AvailableActionsPanel } from './AvailableActionsPanel';

/** Auth flow options for Select (Story 4.9 AC2). */
const AUTH_FLOW_OPTIONS: { value: AuthFlow; label: string }[] = (
  Object.entries(AUTH_FLOW_LABELS) as [AuthFlow, string][]
).map(([value, label]) => ({ value, label }));

export interface IntegrationFormValues {
  type: string;
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null;
  schema?: string | null;
  table?: string | null;
}

export interface IntegrationFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: IntegrationCreate | IntegrationUpdate) => Promise<IntegrationResponse | void>;
  loading?: boolean;
  error?: string | null;
  editIntegration?: IntegrationResponse | null;
  onSuccess?: (integration: IntegrationResponse) => void;
}

/** URL pattern: must start with http(s):// and have at least one valid hostname character. */
const URL_PATTERN = /^https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)*.*$/;

export function IntegrationForm({
  open,
  onCancel,
  onSubmit,
  loading,
  error,
  editIntegration,
  onSuccess,
}: IntegrationFormProps) {
  const { message } = App.useApp();
  const { accessToken } = useAuth();
  const [form] = Form.useForm<IntegrationFormValues>();
  const isEdit = !!editIntegration;
  const [uploadedIconUrl, setUploadedIconUrl] = useState<string | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // Story 24.2 AC1: Fetch integration types from backend catalogue
  const { types: integrationTypes, loading: loadingTypes, error: errorTypes, isFallback } = useIntegrationTypes();

  const watchIcon = Form.useWatch('icon', form);
  const watchType = Form.useWatch('type', form);
  const isInventoryDb = (watchType ?? '').trim().toLowerCase() === 'inventory_db';

  // Story 24.3: Status-based UI restrictions
  const editStatus = editIntegration?.status;
  const isInvalid = editStatus === 'invalid';
  const isDeprecated = editStatus === 'deprecated';
  const isSubmitDisabled = isInvalid;

  // Story 24.2 AC3: Find selected type data for actions display
  const selectedTypeData = integrationTypes.find((t) => t.code === watchType) ?? null;

  // Valeurs pour préremplir en édition (stable pour initialValues / key)
  const editConfig = editIntegration?.config as { schema?: string; table?: string } | undefined;
  const editValues =
    open && editIntegration
      ? {
          type: editIntegration.type,
          name: editIntegration.name,
          base_url: editIntegration.base_url,
          credential_ref: editIntegration.credential_ref ?? undefined,
          icon: editIntegration.icon ?? undefined,
          auth_flow: editIntegration.auth_flow ?? undefined,
          schema: editConfig?.schema ?? undefined,
          table: editConfig?.table ?? undefined,
        }
      : null;

  useEffect(() => {
    if (!open) return;
    if (editIntegration) {
      setUploadedIconUrl(null);
      setFileList([]);
      const t = setTimeout(() => {
        const cfg = editIntegration.config as { schema?: string; table?: string } | undefined;
        form.setFieldsValue({
          type: editIntegration.type,
          name: editIntegration.name,
          base_url: editIntegration.base_url,
          credential_ref: editIntegration.credential_ref ?? undefined,
          icon: editIntegration.icon ?? undefined,
          auth_flow: editIntegration.auth_flow ?? undefined,
          schema: cfg?.schema ?? undefined,
          table: cfg?.table ?? undefined,
        });
      }, 0);
      return () => clearTimeout(t);
    } else {
      form.resetFields();
      queueMicrotask(() => {
        setUploadedIconUrl(null);
        setFileList([]);
      });
      form.setFieldsValue({
        type: undefined,
        name: '',
        base_url: '',
        credential_ref: undefined,
        icon: undefined,
        auth_flow: undefined,
        schema: undefined,
        table: undefined,
      });
    }
  }, [open, editIntegration, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      // Story 24.2 AC7: Validate selected type is active
      const typeData = integrationTypes.find((t) => t.code === values.type);

      if (!isEdit) {
        // LOW-2 fix: Specific error messages
        if (!typeData) {
          message.error("Ce type d'intégration n'existe pas");
          return;
        }
        if (!typeData.is_active) {
          message.error("Ce type d'intégration est inactif et ne peut plus être utilisé");
          return;
        }
      } else {
        // MEDIUM-5 fix: Warn if editing an integration with inactive type
        if (typeData && !typeData.is_active) {
          message.warning("Attention : le type de cette intégration est marqué comme inactif");
        }
      }

      const payload: IntegrationCreate | IntegrationUpdate = {
        type: values.type,
        name: values.name.trim(),
        base_url: values.base_url.trim(),
        credential_ref: values.credential_ref?.trim() || null,
        icon: uploadedIconUrl || values.icon?.trim() || null,
        auth_flow: values.auth_flow || null,
      };
      if (isInventoryDb && (values.schema?.trim() || values.table?.trim())) {
        (payload as IntegrationCreate).config = {
          schema: values.schema?.trim() || null,
          table: values.table?.trim() || null,
        };
      }
      const res = await onSubmit(payload);
      if (res && onSuccess) onSuccess(res);
    } catch (e) {
      const isValidation = e && typeof e === 'object' && 'errorFields' in e;
      if (isValidation) return;
      throw e;
    }
  };

  const handleIconUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const headers: Record<string, string> = {};
      if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

      const response = await fetch('/api/v1/admin/integrations/upload-icon', {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json();
        message.error(errorData.error?.message || "Échec de l'upload");
        return;
      }

      const result = await response.json();
      const iconUrl = result.data?.icon_url;
      if (iconUrl) {
        setUploadedIconUrl(iconUrl);
        form.setFieldsValue({ icon: iconUrl });
        message.success('Icône uploadée avec succès');
      }
    } catch {
      message.error("Erreur lors de l'upload de l'icône");
    }
  };

  const iconSrc = getIconUrl(uploadedIconUrl || watchIcon);
  const iconPreview = iconSrc ? (
    <Avatar src={iconSrc} shape="square" size={32} icon={<ApiOutlined />} />
  ) : (
    <Avatar shape="square" size={32} icon={<ApiOutlined />} />
  );

  // Story 24.2 AC2: Build Select options from catalogue
  const typeOptions = integrationTypes
    .filter((t) => t.is_active)
    .map((t) => ({
      value: t.code,
      label: t.name,
    }));

  return (
    <Modal
      open={open}
      title={isEdit ? "Modifier l'intégration" : 'Nouvelle intégration'}
      onCancel={onCancel}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onCancel} disabled={loading}>
            Annuler
          </Button>
          <Button type="primary" onClick={handleSubmit} loading={loading} disabled={isSubmitDisabled}>
            {isEdit ? 'Enregistrer' : 'Créer'}
          </Button>
        </Space>
      }
    >
      {error && (
        <Alert type="error" title={error} style={{ marginBottom: 16 }} showIcon />
      )}
      {/* Story 24.3: Alert if integration is invalid */}
      {isEdit && isInvalid && (
        <Alert
          type="error"
          showIcon
          icon={<ExclamationCircleOutlined />}
          message="Intégration invalide"
          description={`Cette intégration est invalide. Le type '${editIntegration?.type}' n'existe pas dans le catalogue backend. Veuillez contacter un administrateur. Les modifications ne sont pas autorisées pour les intégrations invalides.`}
          style={{ marginBottom: 16 }}
        />
      )}
      {/* Story 24.3: Alert if integration is deprecated */}
      {isEdit && isDeprecated && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message="Intégration dépréciée"
          description={`Attention : le type de cette intégration ('${editIntegration?.type}') est déprécié. Il est recommandé de migrer vers un type supporté. Vous pouvez encore modifier cette intégration, mais son utilisation dans de nouveaux workflows sera bloquée.`}
          style={{ marginBottom: 16 }}
        />
      )}
      {/* Story 24.2 AC2: Warning when using fallback types */}
      {isFallback && (
        <Alert
          type="warning"
          title="Impossible de charger les types depuis le backend. Mode dégradé activé — la liste peut être incomplète."
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={editValues ?? undefined}
        key={editIntegration ? `edit-${editIntegration.id}` : 'create'}
      >
        {/* Story 24.2 AC2: Select replaces AutoComplete */}
        <Form.Item
          name="type"
          label="Type d'intégration"
          rules={[{ required: true, message: "Veuillez sélectionner un type d'intégration" }]}
        >
          <Select
            placeholder={loadingTypes ? 'Chargement des types...' : "Sélectionner un type d'intégration"}
            loading={loadingTypes}
            disabled={isEdit || loadingTypes}
            showSearch
            optionFilterProp="label"
            options={typeOptions}
            aria-label="Type d'intégration"
          />
        </Form.Item>

        {/* Story 24.2 AC6: Info message when type is disabled in edit mode */}
        {isEdit && (
          <Alert
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
            title="Le type d'une intégration ne peut pas être modifié après sa création"
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Story 24.2 AC3, AC4, AC8: Available actions panel */}
        <AvailableActionsPanel selectedType={selectedTypeData} />

        <Form.Item
          name="name"
          label="Nom"
          rules={[
            { required: true, message: 'Le nom est requis' },
            { whitespace: true, message: 'Le nom ne peut pas être vide' },
          ]}
        >
          <Input placeholder="Nom de l'intégration" aria-label="Nom" />
        </Form.Item>
        {isInventoryDb && (
          <>
            <Form.Item
              name="schema"
              label="Schéma BD"
              tooltip="Nom du schéma Oracle contenant la table/vue d'inventaire (ex: DBOPS_INVENTORY). Vide = défaut backend."
              rules={[{ pattern: /^$|^[A-Za-z_][A-Za-z0-9_]*$/, message: 'Alphanumérique et underscore uniquement' }]}
            >
              <Input placeholder="ex: DBOPS_INVENTORY" aria-label="Schéma BD" />
            </Form.Item>
            <Form.Item
              name="table"
              label="Table ou vue"
              tooltip="Nom de la table ou vue avec colonnes NAME, ENVIRONMENT, TYPE. Vide = défaut backend."
              rules={[{ pattern: /^$|^[A-Za-z_][A-Za-z0-9_]*$/, message: 'Alphanumérique et underscore uniquement' }]}
            >
              <Input placeholder="ex: INVENTORY_TARGETS" aria-label="Table ou vue" />
            </Form.Item>
          </>
        )}
        <Form.Item
          name="base_url"
          label="URL de base"
          rules={[
            {
              required: true,
              validator: (_, v) => {
                const s = (v ?? '').toString().trim();
                if (!s) return Promise.reject(new Error("L'URL de base est requise"));
                if (!URL_PATTERN.test(s)) {
                  return Promise.reject(new Error("L'URL doit être valide (commencer par http:// ou https://)"));
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input placeholder="https://example.com/api" aria-label="URL de base" />
        </Form.Item>
        <Form.Item name="credential_ref" label="Référence credentials">
          <Input
            placeholder="secret/idp/aap-prod (optionnel)"
            aria-label="Référence credentials"
          />
        </Form.Item>
        <Form.Item name="auth_flow" label="Flow d'authentification">
          <Select
            placeholder="Sélectionner un flow (optionnel)"
            options={AUTH_FLOW_OPTIONS}
            allowClear
            aria-label="Flow d'authentification"
          />
        </Form.Item>
        <Form.Item label="Icône" tooltip="Uploader une icône ou saisir une URL">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Upload
              accept="image/*"
              maxCount={1}
              fileList={fileList}
              beforeUpload={(file) => {
                const isImage = file.type.startsWith('image/');
                if (!isImage) {
                  message.error('Vous ne pouvez uploader que des images!');
                  return Upload.LIST_IGNORE;
                }
                const isLt2M = file.size / 1024 / 1024 < 2;
                if (!isLt2M) {
                  message.error("L'image doit faire moins de 2MB!");
                  return Upload.LIST_IGNORE;
                }
                handleIconUpload(file);
                setFileList([file]);
                return false;
              }}
              onRemove={() => {
                setFileList([]);
                setUploadedIconUrl(null);
                form.setFieldsValue({ icon: undefined });
              }}
            >
              <Button icon={<UploadOutlined />}>Uploader une icône</Button>
            </Upload>
            <Form.Item name="icon" noStyle>
              <Input
                placeholder="...ou saisir URL de l'icône"
                aria-label="URL icône"
              />
            </Form.Item>
          </Space>
        </Form.Item>
        <Form.Item label="Aperçu" colon={false} style={{ marginBottom: 0 }}>
          <Space align="center">{iconPreview}</Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}
