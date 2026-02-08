/**
 * CategoryForm — Modal form for creating/editing categories (Story 2.30, AC5).
 * Pattern: IntegrationForm (Modal + Form).
 */

import { useEffect, useState } from 'react';
import { Modal, Form, Input, InputNumber, Switch, App } from 'antd';
import type { RefCategory } from '../../types/api';
import { createCategory, updateCategory } from '../../services/categories_service';

export interface CategoryFormProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: (category: RefCategory) => void;
  editCategory?: RefCategory | null;
}

export function CategoryForm({ open, onCancel, onSuccess, editCategory }: CategoryFormProps) {
  const { notification } = App.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const isEditMode = !!editCategory;

  useEffect(() => {
    if (open && editCategory) {
      form.setFieldsValue({
        code: editCategory.code,
        label: editCategory.label,
        display_order: editCategory.display_order,
        is_active: editCategory.is_active === 1,
      });
    } else if (!open) {
      form.resetFields();
    }
  }, [open, editCategory, form]);

  const handleSave = async () => {
    let values: { code: string; label: string; display_order: number; is_active: boolean };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    setSaving(true);
    try {
      const payload = {
        code: values.code,
        label: values.label,
        display_order: values.display_order,
        is_active: values.is_active ? 1 : 0,
      };

      let result: RefCategory;
      if (isEditMode) {
        result = await updateCategory(editCategory!.id, payload);
        notification.success({
          message: 'Succès',
          description: `Catégorie « ${result.label} » mise à jour`,
        });
      } else {
        result = await createCategory(payload);
        notification.success({
          message: 'Succès',
          description: `Catégorie « ${result.label} » créée`,
        });
      }
      onSuccess(result);
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
      title={isEditMode ? 'Modifier la catégorie' : 'Nouvelle catégorie'}
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
        initialValues={{ code: '', label: '', display_order: 0, is_active: true }}
      >
        <Form.Item
          name="code"
          label="Code"
          rules={[
            { required: true, message: 'Le code est requis' },
            { max: 50, message: 'Le code ne peut pas dépasser 50 caractères' },
            {
              pattern: /^[a-z0-9_-]+$/,
              message: 'Lettres minuscules, chiffres, tirets et underscores uniquement',
            },
          ]}
        >
          <Input placeholder="Ex: backup" disabled={isEditMode} aria-label="Code de la catégorie" />
        </Form.Item>
        <Form.Item
          name="label"
          label="Libellé"
          rules={[
            { required: true, message: 'Le libellé est requis' },
            { max: 100, message: 'Le libellé ne peut pas dépasser 100 caractères' },
          ]}
        >
          <Input placeholder="Ex: Sauvegarde" aria-label="Libellé de la catégorie" />
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
        <Form.Item name="is_active" label="Active" valuePropName="checked">
          <Switch aria-label="Catégorie active" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
