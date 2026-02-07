/**
 * ImpactRulesEditor component for managing action impact rules visually (Story 2.18, AC #1, #2, #4, #6).
 *
 * Features:
 * - List of impact rules with "Ajouter une regle" button (AC1)
 * - Inline form per rule: environment, level, criteria (AC2)
 * - Delete (X) per rule; inline validation: environment unique, level required (AC4, AC6)
 * - ImpactIndicator preview per rule (Task 2.5)
 * - Same pattern as ParametersEditor (no drag-and-drop — order doesn't matter)
 */

import React from 'react';
import {
  Button,
  Input,
  Select,
  Space,
  Card,
  Typography,
  Form,
} from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ImpactRuleDefinition, ImpactLevel } from '../../types/api';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { IMPACT_ENVIRONMENTS } from '../../utils/impactRulesSchema';

const { Text } = Typography;

const EMPTY_RULES: ImpactRuleDefinition[] = [];

export interface ImpactRulesEditorProps {
  value?: ImpactRuleDefinition[];
  onChange?: (value: ImpactRuleDefinition[]) => void;
}

const IMPACT_LEVEL_OPTIONS: { value: ImpactLevel; label: string }[] = [
  { value: 'low', label: 'Faible (vert)' },
  { value: 'medium', label: 'Moyen (orange)' },
  { value: 'high', label: 'Eleve (rouge)' },
  { value: 'critical', label: 'Critique (rouge fonce)' },
];

const ENVIRONMENT_OPTIONS = IMPACT_ENVIRONMENTS.map((env) => ({
  value: env,
  label: env,
}));

interface RuleCardProps {
  rule: ImpactRuleDefinition;
  index: number;
  allRules: ImpactRuleDefinition[];
  onRuleChange: (index: number, field: keyof ImpactRuleDefinition, fieldValue: unknown) => void;
  onRemove: (index: number) => void;
}

const RuleCard: React.FC<RuleCardProps> = ({
  rule,
  index,
  allRules,
  onRuleChange,
  onRemove,
}) => {
  // Check for duplicate environment
  const duplicateEnv =
    rule.environment.trim() !== '' &&
    allRules.filter((r, i) => i !== index && (r.environment || '').trim() === rule.environment.trim()).length > 0;

  return (
    <Card
      size="small"
      styles={{ body: { padding: '12px' } }}
      style={{ marginBottom: 8 }}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>Regle {index + 1}</Text>
            {/* Task 2.5: Preview ImpactIndicator */}
            {rule.level && <ImpactIndicator level={rule.level} size="small" />}
          </Space>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onRemove(index)}
            aria-label={`Supprimer regle ${index + 1}`}
          />
        </Space>

        <Space wrap style={{ width: '100%' }} size="small">
          <Form.Item
            label="Environnement"
            validateStatus={!rule.environment?.trim() ? 'error' : duplicateEnv ? 'error' : ''}
            help={
              !rule.environment?.trim()
                ? 'Environnement requis'
                : duplicateEnv
                  ? 'Environnement deja utilise'
                  : ''
            }
            style={{ marginBottom: 0 }}
          >
            <Select
              value={rule.environment || undefined}
              onChange={(v) => onRuleChange(index, 'environment', v)}
              options={ENVIRONMENT_OPTIONS}
              placeholder="Selectionnez"
              style={{ width: 140 }}
              aria-label={`Environnement regle ${index + 1}`}
              allowClear={false}
            />
          </Form.Item>

          <Form.Item
            label="Niveau d'impact"
            validateStatus={!rule.level ? 'error' : ''}
            help={!rule.level ? 'Niveau requis' : ''}
            style={{ marginBottom: 0 }}
          >
            <Select
              value={rule.level || undefined}
              onChange={(v) => onRuleChange(index, 'level', v)}
              options={IMPACT_LEVEL_OPTIONS}
              placeholder="Selectionnez"
              style={{ width: 180 }}
              aria-label={`Niveau d'impact regle ${index + 1}`}
            />
          </Form.Item>
        </Space>

        <Form.Item label="Critere / Justification" style={{ marginBottom: 0 }}>
          <Input
            value={rule.criteria ?? ''}
            onChange={(e) => onRuleChange(index, 'criteria', e.target.value || null)}
            placeholder="Ex: Environnement de production, changement a haut risque"
            style={{ width: '100%' }}
            aria-label={`Critere regle ${index + 1}`}
          />
        </Form.Item>
      </Space>
    </Card>
  );
};

export const ImpactRulesEditor: React.FC<ImpactRulesEditorProps> = ({ value = EMPTY_RULES, onChange }) => {
  const handleAdd = () => {
    const newRule: ImpactRuleDefinition = {
      id: `rule-new-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      environment: '',
      level: 'low',
      criteria: null,
    };
    onChange?.([...value, newRule]);
  };

  const handleRemove = (index: number) => {
    onChange?.(value.filter((_, i) => i !== index));
  };

  const handleRuleChange = (index: number, field: keyof ImpactRuleDefinition, fieldValue: unknown) => {
    const next = [...value];
    const current = { ...next[index] };
    (current as Record<string, unknown>)[field] = fieldValue;
    next[index] = current;
    onChange?.(next);
  };

  return (
    <div>
      <Space orientation="vertical" style={{ width: '100%' }}>
        {value.map((rule, index) => (
          <RuleCard
            key={rule.id ?? `rule-${index}`}
            rule={rule}
            index={index}
            allRules={value}
            onRuleChange={handleRuleChange}
            onRemove={handleRemove}
          />
        ))}

        {value.length === 0 && (
          <Text type="secondary">
            Aucune regle d'impact. Le niveau par defaut de l'action s'appliquera a tous les environnements.
          </Text>
        )}

        <Button type="dashed" onClick={handleAdd} icon={<PlusOutlined />} block>
          Ajouter une regle
        </Button>
      </Space>
    </div>
  );
};

export default ImpactRulesEditor;
