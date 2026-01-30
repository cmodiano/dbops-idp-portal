/**
 * IntegrationForm — création/édition d'intégration (Story 2.28, AC3, AC4).
 * Champs : Type, Nom, URL de base, Référence credentials (optionnel), Icône (optionnel).
 * Preview icône (Avatar si URL, sinon preset par type). Validation type, nom, base_url (URL).
 */

import { useEffect } from 'react';
import { Form, Input, Modal, Alert, Select, Avatar, Space, Button } from 'antd';
import {
  ApiOutlined,
  CloudServerOutlined,
  BuildOutlined,
  BranchesOutlined,
  ProjectOutlined,
  GithubOutlined,
} from '@ant-design/icons';
import type { IntegrationType, IntegrationCreate, IntegrationUpdate, IntegrationResponse } from '../../types/api';
import { INTEGRATION_TYPE_LABELS, INTEGRATION_TYPE_ICON_COLORS } from '../../types/api';

const TYPE_ICONS: Record<IntegrationType, React.ReactNode> = {
  aap: <ApiOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.aap, fontSize: 20 }} />,
  servicenow: <CloudServerOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.servicenow, fontSize: 20 }} />,
  terraform: <BuildOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.terraform, fontSize: 20 }} />,
  azuredevops: <BranchesOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.azuredevops, fontSize: 20 }} />,
  jira: <ProjectOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.jira, fontSize: 20 }} />,
  github_actions: <GithubOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.github_actions, fontSize: 20 }} />,
};

const TYPE_OPTIONS: { value: IntegrationType; label: string }[] = (
  Object.entries(INTEGRATION_TYPE_LABELS) as [IntegrationType, string][]
).map(([value, label]) => ({ value, label }));

export interface IntegrationFormValues {
  type: IntegrationType;
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
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
  const [form] = Form.useForm<IntegrationFormValues>();
  const isEdit = !!editIntegration;

  const watchType = Form.useWatch('type', form);
  const watchIcon = Form.useWatch('icon', form);

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    if (editIntegration) {
      form.setFieldsValue({
        type: editIntegration.type,
        name: editIntegration.name,
        base_url: editIntegration.base_url,
        credential_ref: editIntegration.credential_ref ?? undefined,
        icon: editIntegration.icon ?? undefined,
      });
    } else {
      form.setFieldsValue({
        type: 'aap',
        name: '',
        base_url: '',
        credential_ref: undefined,
        icon: undefined,
      });
    }
  }, [open, editIntegration, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: IntegrationCreate | IntegrationUpdate = {
        type: values.type,
        name: values.name.trim(),
        base_url: values.base_url.trim(),
        credential_ref: values.credential_ref?.trim() || null,
        icon: values.icon?.trim() || null,
      };
      const res = await onSubmit(payload);
      if (res && onSuccess) onSuccess(res);
    } catch (e) {
      const isValidation = e && typeof e === 'object' && 'errorFields' in e;
      if (isValidation) return;
      throw e;
    }
  };

  const iconPreview =
    watchIcon && (watchIcon.startsWith('http://') || watchIcon.startsWith('https://')) ? (
      <Avatar src={watchIcon} shape="square" size={32} />
    ) : (
      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32 }}>
        {watchType && TYPE_ICONS[watchType]}
      </span>
    );

  return (
    <Modal
      open={open}
      title={isEdit ? 'Modifier l\'intégration' : 'Nouvelle intégration'}
      onCancel={onCancel}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onCancel} disabled={loading}>
            Annuler
          </Button>
          <Button type="primary" onClick={handleSubmit} loading={loading}>
            {isEdit ? 'Enregistrer' : 'Créer'}
          </Button>
        </Space>
      }
    >
      {error && (
        <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />
      )}
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="type"
          label="Type de plateforme"
          rules={[{ required: true, message: 'Le type est requis' }]}
        >
          <Select
            placeholder="Sélectionner un type"
            options={TYPE_OPTIONS}
            aria-label="Type de plateforme"
          />
        </Form.Item>
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
        <Form.Item
          name="base_url"
          label="URL de base"
          rules={[
            {
              required: true,
              validator: (_, v) => {
                const s = (v ?? '').toString().trim();
                if (!s) return Promise.reject(new Error('L\'URL de base est requise'));
                if (!URL_PATTERN.test(s)) {
                  return Promise.reject(new Error('L\'URL doit être valide (commencer par http:// ou https://)'));
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
        <Form.Item name="icon" label="Icône">
          <Input
            placeholder="URL de l'icône ou vide pour preset par type"
            aria-label="Icône"
          />
        </Form.Item>
        <Form.Item label="Aperçu" colon={false} style={{ marginBottom: 0 }}>
          <Space align="center">{iconPreview}</Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}
