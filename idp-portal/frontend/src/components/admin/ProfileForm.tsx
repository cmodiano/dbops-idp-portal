/**
 * ProfileForm — create/edit profile (Story 2.9, AC #1, #2, #4).
 * Modal with name, description, ad_group, is_admin, is_auditor. Validation: name and ad_group required.
 */

import { useEffect } from 'react';
import { Form, Input, Modal, Alert, Switch } from 'antd';
import type { ProfileCreate, ProfileUpdate, ProfileResponse } from '../../types/api';

const { TextArea } = Input;

export interface ProfileFormValues {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
}

export interface ProfileFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: ProfileCreate | ProfileUpdate) => Promise<ProfileResponse | void>;
  loading?: boolean;
  error?: string | null;
  editProfile?: ProfileResponse | null;
  onSuccess?: (profile: ProfileResponse) => void;
}

export function ProfileForm({
  open,
  onCancel,
  onSubmit,
  loading,
  error,
  editProfile,
  onSuccess,
}: ProfileFormProps) {
  const [form] = Form.useForm<ProfileFormValues>();
  const isEdit = !!editProfile;

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    if (editProfile) {
      form.setFieldsValue({
        name: editProfile.name,
        description: editProfile.description ?? undefined,
        ad_group: editProfile.ad_group,
        is_admin: editProfile.is_admin,
        is_auditor: editProfile.is_auditor,
      });
    } else {
      form.setFieldsValue({ is_admin: false, is_auditor: false });
    }
  }, [open, editProfile, form]);

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const payload: ProfileCreate | ProfileUpdate = {
      name: values.name.trim(),
      description: values.description?.trim() || null,
      ad_group: values.ad_group.trim(),
      is_admin: values.is_admin,
      is_auditor: values.is_auditor,
    };
    const res = await onSubmit(payload);
    if (res && onSuccess) onSuccess(res);
  };

  return (
    <Modal
      open={open}
      title={isEdit ? 'Modifier le profil' : 'Nouveau profil'}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={loading}
      destroyOnClose
      okText={isEdit ? 'Enregistrer' : 'Créer'}
      cancelText="Annuler"
      cancelButtonProps={{ disabled: loading }}
    >
      {error && (
        <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />
      )}
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="name"
          label="Nom"
          rules={[{ required: true, message: 'Le nom est requis' }, { whitespace: true, message: 'Le nom ne peut pas être vide' }]}
        >
          <Input placeholder="ex. Assurance" disabled={isEdit} />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <TextArea rows={2} placeholder="Description du profil" />
        </Form.Item>
        <Form.Item
          name="ad_group"
          label="Groupe AD"
          rules={[{ required: true, message: 'Le groupe AD est requis' }, { whitespace: true, message: 'Le groupe AD ne peut pas être vide' }]}
        >
          <Input placeholder="ex. GRP-IDP-ASSURANCE" />
        </Form.Item>
        <Form.Item name="is_admin" label="Administrateur" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="is_auditor" label="Auditeur" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
