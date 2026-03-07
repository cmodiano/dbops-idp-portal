/**
 * MappingHelpPopover — Aide contextuelle pour input_mapping et output_mapping (Story 57.20).
 *
 * Affiche un Popover Ant Design avec la syntaxe et les exemples selon le type de mapping.
 * - type="input" : syntaxe Jinja2 {{ steps.X.Y }}, filtres autorisés, liste des étapes disponibles
 * - type="output" : syntaxe dot-notation $.path, outputs typiques par step_type
 */

import React from 'react';
import { Popover, Typography } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

/** Outputs typiques par step_type (données statiques, pas d'endpoint backend). */
const TYPICAL_OUTPUTS: Record<string, { fields: string[]; note: string }> = {
  platform: {
    fields: [
      'child_execution_id',
      'referenced_action_id',
      'referenced_action_name',
      'child_status',
      'parameters_injected',
    ],
    note: "Champs retournés par l'exécution de l'action enfant.",
  },
  service_call: {
    fields: ['number', 'sys_id'],
    note: 'Dépend du service et de l\'opération (ex. ServiceNow create_change → number, sys_id).',
  },
  http_request: {
    fields: ['body', 'status_code'],
    note: 'Si la réponse est du JSON, les champs JSON sont accessibles directement. Sinon : body, status_code.',
  },
};

export interface MappingHelpPopoverProps {
  type: 'input' | 'output';
  stepType?: string;
  availableSteps?: { value: string; label: string }[];
}

function InputHelpContent({ availableSteps }: { availableSteps?: { value: string; label: string }[] }) {
  return (
    <div style={{ maxWidth: 340 }} data-testid="input-help-content">
      <Title level={5} style={{ margin: '0 0 8px' }}>Syntaxe input_mapping</Title>
      <Text>
        Utilisez la syntaxe Jinja2 pour référencer les résultats des étapes précédentes :
      </Text>
      <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, margin: '8px 0', fontSize: 12 }}>
        {'{{ steps.<step_id>.<champ> }}'}
      </pre>

      <Text strong style={{ display: 'block', margin: '8px 0 4px' }}>Filtres autorisés :</Text>
      <ul style={{ paddingLeft: 20, margin: '0 0 8px', fontSize: 13 }}>
        <li><code>join(', ')</code> — concatène une liste</li>
        <li><code>length</code> — nombre d'éléments</li>
        <li><code>first</code> — premier élément</li>
        <li><code>default('valeur', true)</code> — valeur par défaut</li>
      </ul>

      <Text strong style={{ display: 'block', margin: '8px 0 4px' }}>Exemple :</Text>
      <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, margin: '0 0 8px', fontSize: 12 }}>
        {"{{ steps.discovery.databases | join(', ') }}"}
      </pre>

      {availableSteps && availableSteps.length > 0 && (
        <>
          <Text strong style={{ display: 'block', margin: '8px 0 4px' }}>Étapes disponibles :</Text>
          <ul style={{ paddingLeft: 20, margin: 0, fontSize: 13 }}>
            {availableSteps.map((step) => (
              <li key={step.value}>
                <Text>{step.label}</Text>
                {' — '}
                <code>{`{{ steps.${step.value}. }}`}</code>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function OutputHelpContent({ stepType }: { stepType?: string }) {
  const outputs = stepType ? TYPICAL_OUTPUTS[stepType] : undefined;

  return (
    <div style={{ maxWidth: 340 }} data-testid="output-help-content">
      <Title level={5} style={{ margin: '0 0 8px' }}>Syntaxe output_mapping</Title>
      <Text>
        Utilisez la dot-notation pour extraire des champs de la réponse :
      </Text>
      <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, margin: '8px 0', fontSize: 12 }}>
        $.chemin.vers.champ
      </pre>
      <Text type="secondary" style={{ display: 'block', margin: '0 0 8px', fontSize: 12 }}>
        Le préfixe <code>$.</code> est optionnel — <code>data.databases</code> fonctionne aussi.
      </Text>

      <Text strong style={{ display: 'block', margin: '8px 0 4px' }}>Exemple :</Text>
      <Text style={{ fontSize: 13 }}>
        Clé <code>databases</code> → Valeur <code>$.data.databases</code>
      </Text>

      {outputs && (
        <>
          <Text strong style={{ display: 'block', margin: '12px 0 4px' }}>
            Champs de sortie typiques :
          </Text>
          <ul style={{ paddingLeft: 20, margin: '0 0 4px', fontSize: 13 }}>
            {outputs.fields.map((f) => (
              <li key={f}><code>{f}</code></li>
            ))}
          </ul>
          <Text type="secondary" style={{ fontSize: 12 }}>{outputs.note}</Text>
        </>
      )}

      <Text type="secondary" style={{ display: 'block', margin: '8px 0 0', fontSize: 12 }}>
        Les champs extraits seront accessibles par les étapes suivantes via{' '}
        <code>{'{{ steps.<step_id>.<champ_extrait> }}'}</code>
      </Text>
    </div>
  );
}

export const MappingHelpPopover: React.FC<MappingHelpPopoverProps> = ({
  type,
  stepType,
  availableSteps,
}) => {
  const content = type === 'input'
    ? <InputHelpContent availableSteps={availableSteps} />
    : <OutputHelpContent stepType={stepType} />;

  return (
    <Popover content={content} trigger="click" data-testid={`mapping-help-popover-${type}`}>
      <QuestionCircleOutlined
        style={{ cursor: 'pointer', marginLeft: 4, color: '#1677ff' }}
        aria-label={type === 'input' ? "Aide syntaxe input_mapping" : "Aide syntaxe output_mapping"}
        data-testid={`mapping-help-icon-${type}`}
      />
    </Popover>
  );
};

export default MappingHelpPopover;
