/**
 * BusinessRulePoliciesEditor component (Story 28.1, AC4, AC5).
 *
 * JSON editor for business_rule_policies with:
 * - Textarea for JSON editing with live validation
 * - "Insérer exemple Terraform" button (AC5)
 * - Help popover with schema documentation (AC5)
 * - Real-time validation errors displayed below editor
 */

import { useState, useCallback, useEffect } from 'react';
import { Input, Button, Alert, Popover, Collapse, Space, Typography } from 'antd';
import { QuestionCircleOutlined, FileAddOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

export interface BusinessRulePoliciesEditorProps {
  value?: string;
  onChange?: (value: string) => void;
}

const TERRAFORM_EXAMPLE = {
  on_step_output: [
    {
      when: {
        step_type: 'terraform_cloud',
        output_key: 'plan_output',
      },
      policy: {
        type: 'review_if_modified',
        require_review_if_modified: [
          {
            resource_type: 'azurerm_sql_database',
            attribute_paths: ['sku_name', 'max_size_gb'],
          },
          {
            resource_type: 'azurerm_sql_server',
          },
          {
            attribute_paths: ['backup_retention_days'],
          },
        ],
        auto_approve_if_none_match: true,
      },
    },
  ],
};

/**
 * Validate business_rule_policies JSON structure (client-side).
 * Returns null if valid, error message string if invalid.
 */
function validatePoliciesJson(jsonStr: string): string | null {
  if (!jsonStr.trim()) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonStr);
  } catch {
    return 'JSON invalide : erreur de syntaxe';
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return 'La valeur doit être un objet JSON';
  }

  const obj = parsed as Record<string, unknown>;

  if (!('on_step_output' in obj)) {
    return "Clé 'on_step_output' obligatoire";
  }

  if (!Array.isArray(obj.on_step_output)) {
    return "'on_step_output' doit être un tableau";
  }

  for (let i = 0; i < obj.on_step_output.length; i++) {
    const rule = obj.on_step_output[i] as Record<string, unknown>;
    if (typeof rule !== 'object' || rule === null) {
      return `on_step_output[${i}] doit être un objet`;
    }

    if (!('when' in rule)) {
      return `on_step_output[${i}] : clé 'when' obligatoire`;
    }

    const when = rule.when as Record<string, unknown>;
    if (typeof when !== 'object' || when === null) {
      return `on_step_output[${i}].when doit être un objet`;
    }

    if (!when.step_type || typeof when.step_type !== 'string') {
      return `on_step_output[${i}].when.step_type obligatoire (chaîne non vide)`;
    }

    if (!('policy' in rule)) {
      return `on_step_output[${i}] : clé 'policy' obligatoire`;
    }

    const policy = rule.policy as Record<string, unknown>;
    if (typeof policy !== 'object' || policy === null) {
      return `on_step_output[${i}].policy doit être un objet`;
    }

    if (!policy.type || typeof policy.type !== 'string') {
      return `on_step_output[${i}].policy.type obligatoire`;
    }

    if (policy.type === 'review_if_modified') {
      if (!Array.isArray(policy.require_review_if_modified)) {
        return `on_step_output[${i}].policy.require_review_if_modified obligatoire (tableau)`;
      }
    }
  }

  return null;
}

const helpContent = (
  <div style={{ maxWidth: 420 }}>
    <Collapse
      size="small"
      items={[
        {
          key: 'structure',
          label: 'Structure on_step_output',
          children: (
            <Paragraph style={{ margin: 0 }}>
              Liste de règles métier. Chaque règle contient <Text code>when</Text> (quand appliquer)
              et <Text code>policy</Text> (quelle politique).
            </Paragraph>
          ),
        },
        {
          key: 'when',
          label: 'Champ when',
          children: (
            <Paragraph style={{ margin: 0 }}>
              <Text code>step_type</Text> (requis) : type d'étape ciblé (terraform_cloud, aap, azure_devops, etc.)
              <br />
              <Text code>output_key</Text> (optionnel) : clé dans la sortie (plan_output, job_summary, etc.)
            </Paragraph>
          ),
        },
        {
          key: 'policy',
          label: 'Champ policy',
          children: (
            <Paragraph style={{ margin: 0 }}>
              <Text code>type</Text> (requis) : type de politique (review_if_modified)
              <br />
              <Text code>require_review_if_modified</Text> : critères de modification déclenchant une revue
              <br />
              <Text code>auto_approve_if_none_match</Text> : approuver auto si aucun critère ne matche
            </Paragraph>
          ),
        },
        {
          key: 'types',
          label: 'Types supportés',
          children: (
            <Paragraph style={{ margin: 0 }}>
              <Text strong>review_if_modified</Text> : Déclenche une revue DBA si des ressources/attributs spécifiques
              sont modifiés dans la sortie d'étape.
              <br />
              D'autres types seront ajoutés dans les stories futures (28.2, 28.3).
            </Paragraph>
          ),
        },
      ]}
    />
    <div style={{ marginTop: 8 }}>
      <a href="/docs/business-rule-policies.md" target="_blank" rel="noopener noreferrer">
        Documentation complète
      </a>
    </div>
  </div>
);

export function BusinessRulePoliciesEditor({ value = '', onChange }: BusinessRulePoliciesEditorProps) {
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleChange = useCallback(
    (newValue: string) => {
      onChange?.(newValue);
    },
    [onChange],
  );

  // Live validation
  useEffect(() => {
    const error = validatePoliciesJson(value);
    setValidationError(error);
  }, [value]);

  const handleInsertExample = useCallback(() => {
    const exampleJson = JSON.stringify(TERRAFORM_EXAMPLE, null, 2);
    handleChange(exampleJson);
  }, [handleChange]);

  const isEmpty = !value.trim();

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        {isEmpty && (
          <Button
            icon={<FileAddOutlined />}
            onClick={handleInsertExample}
            size="small"
            data-testid="insert-example-btn"
          >
            Insérer exemple Terraform
          </Button>
        )}
        <Popover
          content={helpContent}
          title="Structure du schéma business_rule_policies"
          trigger="click"
          overlayStyle={{ maxWidth: 480 }}
        >
          <Button
            icon={<QuestionCircleOutlined />}
            size="small"
            type="text"
            data-testid="help-btn"
          >
            Aide
          </Button>
        </Popover>
      </Space>

      <TextArea
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        rows={12}
        placeholder='{"on_step_output": [...]}'
        style={{ fontFamily: 'monospace', fontSize: 12 }}
        data-testid="policies-editor"
        aria-label="Éditeur de règles métier"
      />

      {validationError && (
        <Alert
          type="error"
          showIcon
          title={validationError}
          style={{ marginTop: 8 }}
          data-testid="validation-error"
        />
      )}
    </div>
  );
}

export default BusinessRulePoliciesEditor;
