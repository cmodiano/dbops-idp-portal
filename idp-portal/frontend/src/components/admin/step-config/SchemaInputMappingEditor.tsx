/**
 * SchemaInputMappingEditor — Story 84-4, AC4.
 *
 * Formulaire guidé par input_schema pour remplir le input_mapping d'un step service_call.
 * Différent de SchemaFormRenderer : les valeurs sont toujours des strings
 * (expressions template ou literals). Le schema sert uniquement à guider l'utilisateur.
 */

import type { FC } from 'react';
import { Input, Typography } from 'antd';

const { Text } = Typography;

export interface SchemaInputMappingEditorProps {
  schema: Record<string, unknown>;
  value: Record<string, string> | null;
  onChange: (v: Record<string, string>) => void;
  disabled?: boolean;
}

export const SchemaInputMappingEditor: FC<SchemaInputMappingEditorProps> = ({
  schema,
  value,
  onChange,
  disabled = false,
}) => {
  const properties = schema.properties as Record<string, Record<string, unknown>> | undefined;

  if (!properties || Object.keys(properties).length === 0) {
    return null;
  }

  const required = schema.required as string[] | undefined;

  return (
    <div data-testid="schema-input-mapping-editor">
      {Object.entries(properties).map(([key, propSchema]) => {
        const isRequired = required?.includes(key) ?? false;
        const label = (propSchema.title as string | undefined) ?? key;
        const placeholder =
          (propSchema.description as string | undefined) ?? '{{ steps.<step_id>.output.<champ> }}';

        return (
          <div key={key} style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 2 }}>
              {label}
              {isRequired && (
                <Text type="danger" style={{ marginLeft: 2 }}>
                  *
                </Text>
              )}
            </Text>
            <Input
              size="small"
              value={value?.[key] ?? ''}
              placeholder={placeholder}
              disabled={disabled}
              onChange={(e) => onChange({ ...(value ?? {}), [key]: e.target.value })}
            />
          </div>
        );
      })}
    </div>
  );
};

export default SchemaInputMappingEditor;
