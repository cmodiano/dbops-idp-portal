/**
 * EngineForm — Modal form for editing engines (Story 31.10, AC2).
 * Pattern: CategoryForm (Modal + Form). Edit only, no creation.
 */

import { useEffect, useState } from 'react';
import { Modal, Form, Input, InputNumber, Switch, App } from 'antd';
import type { RefEngine } from '../../services/reference_service';
import { updateEngine } from '../../services/engines_service';

export interface EngineFormProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  editEngine: RefEngine | null;
}

export function EngineForm({ open, onCancel, onSuccess, editEngine }: EngineFormProps) {
  const { notification } = App.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && editEngine) {
      form.setFieldsValue({
        code: editEngine.code,
        label: editEngine.label,
        icon_url: editEngine.icon_url ?? '',
        display_order: editEngine.display_order,
        is_active: editEngine.is_active === 1,
      });
    } else if (!open) {
      form.resetFields();
    }
  }, [open, editEngine, form]);

  const handleSave = async () => {
    let values: { label: string; icon_url: string; display_order: number; is_active: boolean };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    if (!editEngine) return;

    setSaving(true);
    try {
      const payload = {
        label: values.label,
        icon_url: values.icon_url || null,
        display_order: values.display_order,
        is_active: values.is_active ? 1 : 0,
      };

      await updateEngine(editEngine.id, payload);
      notification.success({
        message: 'Succès',
        description: `Moteur « ${values.label} » mis à jour`,
      });
      onSuccess();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : "Erreur lors de l'enregistrement",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="Modifier le moteur"
      open={open}
      onCancel={onCancel}
      onOk={handleSave}
      confirmLoading={saving}
      okText="Enregistrer"
      cancelText="Annuler"
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ code: '', label: '', icon_url: '', display_order: 0, is_active: true }}
      >
        <Form.Item name="code" label="Code">
          <Input disabled aria-label="Code du moteur" />
        </Form.Item>
        <Form.Item
          name="label"
          label="Libellé"
          rules={[
            { required: true, message: 'Le libellé est requis' },
            { max: 100, message: 'Le libellé ne peut pas dépasser 100 caractères' },
          ]}
        >
          <Input placeholder="Ex: Oracle" aria-label="Libellé du moteur" />
        </Form.Item>
        <Form.Item
          name="icon_url"
          label="URL de l'icône"
          rules={[
            {
              pattern: /^(\/|https?:\/\/)/,
              message: "L'URL doit commencer par / ou http(s)://",
            },
          ]}
        >
          <Input placeholder="URL de l'icône SVG/PNG (ex: /static/icons/oracle.svg)" aria-label="URL de l'icône" />
        </Form.Item>
        <Form.Item
          name="display_order"
          label="Ordre d'affichage"
          rules={[
            { required: true, message: "L'ordre est requis" },
            { type: 'number', min: 0, message: "L'ordre doit être >= 0" },
          ]}
        >
          <InputNumber min={0} style={{ width: '100%' }} aria-label="Ordre d'affichage" />
        </Form.Item>
        <Form.Item name="is_active" label="Actif" valuePropName="checked">
          <Switch aria-label="Moteur actif" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
