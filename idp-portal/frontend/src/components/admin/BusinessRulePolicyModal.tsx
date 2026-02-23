/**
 * Story 28.4, AC#2: Modal de création/édition d'une règle métier prédéfinie.
 */

import { useEffect, useState, useCallback } from 'react';
import { Modal, Form, Input, Switch, Button, Alert, Space } from 'antd';
import { FileAddOutlined } from '@ant-design/icons';
import type {
  BusinessRulePolicyDetail,
  BusinessRulePolicyPayload,
  BusinessRulePoliciesData,
} from '../../types/api';

const { TextArea } = Input;

const TERRAFORM_EXAMPLE: BusinessRulePoliciesData = {
  on_step_output: [
    {
      when: { step_type: 'terraform_cloud', output_key: 'plan_output' },
      policy: {
        type: 'review_if_modified',
        require_review_if_modified: [
          { resource_type: 'azurerm_mssql_database', attribute_paths: ['sku_name'] },
        ],
        auto_approve_if_none_match: true,
      },
    },
  ],
};

const AAP_EXAMPLE: BusinessRulePoliciesData = {
  on_step_output: [
    {
      when: { step_type: 'aap' },
      policy: {
        type: 'review_if_modified',
        require_review_if_modified: [
          { resource_type: 'host', attribute_paths: ['status'] },
        ],
        auto_approve_if_none_match: false,
      },
    },
  ],
};

interface BusinessRulePolicyModalProps {
  open: boolean;
  onCancel: () => void;
  onSave: (payload: BusinessRulePolicyPayload) => Promise<void>;
  editPolicy?: BusinessRulePolicyDetail | null;
  saving?: boolean;
}

export function BusinessRulePolicyModal({
  open,
  onCancel,
  onSave,
  editPolicy,
  saving,
}: BusinessRulePolicyModalProps) {
  const [form] = Form.useForm();
  const [policyJson, setPolicyJson] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isEdit = !!editPolicy;

  useEffect(() => {
    if (open && editPolicy) {
      form.setFieldsValue({
        name: editPolicy.name,
        description: editPolicy.description ?? '',
        is_active: editPolicy.is_active,
      });
      setPolicyJson(JSON.stringify(editPolicy.policy_json, null, 2));
      setJsonError(null);
      setSubmitError(null);
    } else if (!open) {
      form.resetFields();
      setPolicyJson('');
      setJsonError(null);
      setSubmitError(null);
    }
  }, [open, editPolicy, form]);

  const validateJson = useCallback((value: string): BusinessRulePoliciesData | null => {
    if (!value.trim()) {
      setJsonError('Le JSON de la règle est requis');
      return null;
    }
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>;
      if (!parsed.on_step_output || !Array.isArray(parsed.on_step_output)) {
        setJsonError("'on_step_output' doit être un tableau");
        return null;
      }
      setJsonError(null);
      return parsed as unknown as BusinessRulePoliciesData;
    } catch {
      setJsonError('JSON invalide : erreur de syntaxe');
      return null;
    }
  }, []);

  const handleJsonChange = useCallback(
    (value: string) => {
      setPolicyJson(value);
      if (value.trim()) validateJson(value);
      else setJsonError(null);
    },
    [validateJson],
  );

  const handleSave = async () => {
    setSubmitError(null);
    try {
      await form.validateFields();
    } catch {
      return;
    }

    const parsedJson = validateJson(policyJson);
    if (!parsedJson) return;

    const values = form.getFieldsValue();
    const payload: BusinessRulePolicyPayload = {
      name: values.name,
      description: values.description || null,
      policy_json: parsedJson,
      is_active: values.is_active ?? true,
    };

    try {
      await onSave(payload);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    }
  };

  return (
    <Modal
      title={isEdit ? 'Modifier la règle métier' : 'Créer une règle métier'}
      open={open}
      onCancel={onCancel}
      width={640}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onCancel}>Annuler</Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            {isEdit ? 'Enregistrer' : 'Créer'}
          </Button>
        </Space>
      }
    >
      {submitError && (
        <Alert
          type="error"
          showIcon
          title={submitError}
          closable
          onClose={() => setSubmitError(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      <Form
        form={form}
        layout="vertical"
        initialValues={{ name: '', description: '', is_active: true }}
      >
        <Form.Item
          name="name"
          label="Nom"
          rules={[
            { required: true, message: 'Le nom est requis' },
            { max: 200, message: 'Le nom ne peut pas dépasser 200 caractères' },
          ]}
        >
          <Input placeholder="Ex: Revue Terraform SQL sku_name" disabled={saving} />
        </Form.Item>

        <Form.Item
          name="description"
          label="Description"
          rules={[{ max: 500, message: 'La description ne peut pas dépasser 500 caractères' }]}
        >
          <TextArea rows={2} placeholder="Description de la règle..." showCount maxLength={500} disabled={saving} />
        </Form.Item>

        <Form.Item label="Règle JSON" required>
          <Space style={{ marginBottom: 8 }}>
            {!policyJson.trim() && (
              <>
                <Button
                  icon={<FileAddOutlined />}
                  size="small"
                  onClick={() => handleJsonChange(JSON.stringify(TERRAFORM_EXAMPLE, null, 2))}
                >
                  Insérer exemple Terraform
                </Button>
                <Button
                  icon={<FileAddOutlined />}
                  size="small"
                  onClick={() => handleJsonChange(JSON.stringify(AAP_EXAMPLE, null, 2))}
                >
                  Insérer exemple AAP
                </Button>
              </>
            )}
          </Space>
          <TextArea
            value={policyJson}
            onChange={(e) => handleJsonChange(e.target.value)}
            rows={12}
            placeholder='{"on_step_output": [...]}'
            style={{ fontFamily: 'monospace', fontSize: 12 }}
            disabled={saving}
          />
          {jsonError && (
            <Alert type="error" showIcon title={jsonError} style={{ marginTop: 8 }} />
          )}
        </Form.Item>

        <Form.Item name="is_active" label="Actif" valuePropName="checked">
          <Switch disabled={saving} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
