/**
 * IntegrationForm — création/édition d'intégration (Story 2.28, 4.9).
 * Story 4.9: Type libre (AutoComplete), auth_flow (Select), Upload icône.
 * Champs : Type (libre), Nom, URL de base, Référence credentials, Auth flow, Icône (upload ou URL).
 */

import { useEffect, useState } from 'react';
import { Form, Input, Modal, Alert, Select, Avatar, Space, Button, AutoComplete, Upload, App } from 'antd';
import type { UploadFile } from 'antd';
import { UploadOutlined, ApiOutlined } from '@ant-design/icons';
import type { AuthFlow, IntegrationCreate, IntegrationUpdate, IntegrationResponse } from '../../types/api';
import { SUGGESTED_INTEGRATION_TYPES, AUTH_FLOW_LABELS } from '../../types/api';

/** Type suggestions for AutoComplete (Story 4.9 AC1). */
const TYPE_SUGGESTIONS = SUGGESTED_INTEGRATION_TYPES.map((t) => ({ value: t }));

/** Auth flow options for Select (Story 4.9 AC2). */
const AUTH_FLOW_OPTIONS: { value: AuthFlow; label: string }[] = (
  Object.entries(AUTH_FLOW_LABELS) as [AuthFlow, string][]
).map(([value, label]) => ({ value, label }));

export interface IntegrationFormValues {
  type: string; // Story 4.9 AC1: free-form platform name
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null; // Story 4.9 AC2: authentication flow
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
  const [form] = Form.useForm<IntegrationFormValues>();
  const isEdit = !!editIntegration;
  const [uploadedIconUrl, setUploadedIconUrl] = useState<string | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  const watchIcon = Form.useWatch('icon', form);

  // Valeurs pour préremplir en édition (stable pour initialValues / key)
  const editValues =
    open && editIntegration
      ? {
          type: editIntegration.type,
          name: editIntegration.name,
          base_url: editIntegration.base_url,
          credential_ref: editIntegration.credential_ref ?? undefined,
          icon: editIntegration.icon ?? undefined,
          auth_flow: editIntegration.auth_flow ?? undefined,
        }
      : null;

  useEffect(() => {
    if (!open) return;
    if (editIntegration) {
      setUploadedIconUrl(null);
      setFileList([]);
      // Appliquer après le rendu des champs (évite que la modal n'ait pas encore monté les inputs)
      const t = setTimeout(() => {
        form.setFieldsValue({
          type: editIntegration.type,
          name: editIntegration.name,
          base_url: editIntegration.base_url,
          credential_ref: editIntegration.credential_ref ?? undefined,
          icon: editIntegration.icon ?? undefined,
          auth_flow: editIntegration.auth_flow ?? undefined,
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
        type: '',
        name: '',
        base_url: '',
        credential_ref: undefined,
        icon: undefined,
        auth_flow: undefined,
      });
    }
  }, [open, editIntegration, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: IntegrationCreate | IntegrationUpdate = {
        type: values.type.trim(),
        name: values.name.trim(),
        base_url: values.base_url.trim(),
        credential_ref: values.credential_ref?.trim() || null,
        icon: uploadedIconUrl || values.icon?.trim() || null, // Prioritize uploaded icon
        auth_flow: values.auth_flow || null,
      };
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

    // Get JWT token from localStorage (Story 4.9 fix: add Authorization header)
    const token = localStorage.getItem('access_token');

    try {
      const response = await fetch('/api/v1/admin/integrations/upload-icon', {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        const errorData = await response.json();
        message.error(errorData.error?.message || 'Échec de l\'upload');
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
      message.error('Erreur lors de l\'upload de l\'icône');
    }
  };

  const iconPreview = watchIcon ? (
    <Avatar
      src={watchIcon.startsWith('/') ? watchIcon : watchIcon}
      shape="square"
      size={32}
      icon={<ApiOutlined />}
    />
  ) : (
    <Avatar shape="square" size={32} icon={<ApiOutlined />} />
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
        <Alert type="error" title={error} style={{ marginBottom: 16 }} showIcon />
      )}
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={editValues ?? undefined}
        key={editIntegration ? `edit-${editIntegration.id}` : 'create'}
      >
        <Form.Item
          name="type"
          label="Type de plateforme (libre)"
          rules={[
            { required: true, message: 'Le type est requis' },
            { max: 100, message: 'Le type ne peut pas dépasser 100 caractères' },
          ]}
          tooltip="Nom libre de la plateforme (ex: aap, terraform, jenkins...)"
        >
          <AutoComplete
            placeholder="Saisir ou choisir un type"
            options={TYPE_SUGGESTIONS}
            filterOption={(input, option) =>
              (option?.value ?? '').toLowerCase().includes(input.toLowerCase())
            }
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
        <Form.Item name="auth_flow" label="Flow d'authentification">
          <Select
            placeholder="Sélectionner un flow (optionnel)"
            options={AUTH_FLOW_OPTIONS}
            allowClear
            aria-label="Flow d'authentification"
          />
        </Form.Item>
        <Form.Item label="Icône" tooltip="Uploader une icône ou saisir une URL">
          <Space orientation="vertical" style={{ width: '100%' }}>
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
                  message.error('L\'image doit faire moins de 2MB!');
                  return Upload.LIST_IGNORE;
                }
                handleIconUpload(file);
                setFileList([file]);
                return false; // Prevent default upload
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
