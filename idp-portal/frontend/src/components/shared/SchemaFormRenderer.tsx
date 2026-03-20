import { type FC, type ReactNode } from 'react';
import { useRef, useState, useEffect } from 'react';
import { Input, InputNumber, Select, Switch, Button } from 'antd';
import { Typography } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

const { Text } = Typography;

export interface SchemaFormRendererProps {
  /** Schéma JSON Schema draft-07 tel qu'exposé par le backend (e.g. config_schema, input_schema, action_config_schema). */
  schema: Record<string, unknown>;
  /** Valeurs courantes (composant contrôlé). */
  value?: Record<string, unknown>;
  /** Callback déclenché à chaque modification d'un champ. */
  onChange?: (values: Record<string, unknown>) => void;
  /** Désactive tous les inputs (défaut : false). */
  disabled?: boolean;
  /**
   * Renderers personnalisés pour des propriétés spécifiques du schema.
   * La fonction reçoit (value, onChange, disabled) et retourne l'input widget uniquement.
   * Le wrapper label + description est conservé par SchemaFormRenderer.
   */
  customRenderers?: Record<string, (value: unknown, onChange: (v: unknown) => void, disabled: boolean) => ReactNode>;
}

/**
 * Rend un formulaire Ant Design à partir d'un schéma JSON Schema draft-07.
 * Supporte : string, number, integer, boolean, enum, array (string[]),
 * object simple (properties définies), mapping key/value (additionalProperties).
 *
 * Composant contrôlé — aucun état interne sur les valeurs.
 * Principe : backend déclare, frontend rend.
 *
 * Réf: docs/reference/extensibility-remaining-work-state-of-the-art.md § B.5
 */
export const SchemaFormRenderer: FC<SchemaFormRendererProps> = ({
  schema,
  value = {},
  onChange,
  disabled = false,
  customRenderers,
}) => {
  const properties = schema.properties as Record<string, Record<string, unknown>> | undefined;
  const requiredFields = schema.required as string[] | undefined;

  if (!properties) return <div />;

  return (
    <div>
      {Object.entries(properties).map(([key, propSchema]) =>
        renderProperty(key, propSchema, value, onChange, disabled, customRenderers, requiredFields)
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Helper interne — NE PAS exporter
// ---------------------------------------------------------------------------

function renderProperty(
  key: string,
  propSchema: Record<string, unknown>,
  parentValue: Record<string, unknown>,
  onChange?: (v: Record<string, unknown>) => void,
  disabled = false,
  customRenderers?: Record<string, (value: unknown, onChange: (v: unknown) => void, disabled: boolean) => ReactNode>,
  required?: string[],
): ReactNode {
  const label = (propSchema.title as string) ?? key;
  const description = propSchema.description as string | undefined;
  const type = propSchema.type as string | undefined;
  const enumValues = propSchema.enum as unknown[] | undefined;
  const isRequired = required?.includes(key) ?? false;

  const handleChange = (newFieldVal: unknown) => {
    onChange?.({ ...parentValue, [key]: newFieldVal });
  };

  // Custom renderer prend priorité sur le rendu standard (input seulement)
  if (customRenderers?.[key]) {
    const customInput = customRenderers[key](parentValue[key], handleChange, disabled);
    return (
      <div key={key} style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          {label}
          {isRequired && <Text type="danger" style={{ marginLeft: 2 }}>*</Text>}
        </Text>
        {customInput}
        {description && (
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            {description}
          </Text>
        )}
      </div>
    );
  }

  let input: ReactNode;

  // Enum prend priorité sur type
  if (enumValues) {
    input = (
      <Select
        style={{ width: '100%' }}
        value={parentValue[key] as string | undefined}
        onChange={handleChange}
        disabled={disabled}
        aria-label={label}
        options={enumValues.map((v) => ({ value: v, label: String(v) }))}
      />
    );
  } else if (type === 'boolean') {
    input = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Text>{label}</Text>
        {isRequired && <Text type="danger" style={{ marginLeft: 2 }}>*</Text>}
        <Switch
          checked={!!(parentValue[key])}
          onChange={handleChange}
          disabled={disabled}
          aria-label={label}
        />
      </div>
    );
  } else if (type === 'number' || type === 'integer') {
    input = (
      <InputNumber
        style={{ width: '100%' }}
        value={parentValue[key] as number | undefined}
        onChange={handleChange}
        min={propSchema.minimum as number | undefined}
        max={propSchema.maximum as number | undefined}
        precision={type === 'integer' ? 0 : undefined}
        disabled={disabled}
        aria-label={label}
      />
    );
  } else if (type === 'array') {
    input = (
      <Select
        mode="tags"
        style={{ width: '100%' }}
        value={(parentValue[key] as string[]) ?? []}
        onChange={handleChange}
        disabled={disabled}
        aria-label={label}
      />
    );
  } else if (type === 'object') {
    const subProperties = propSchema.properties as Record<string, Record<string, unknown>> | undefined;
    const additionalProperties = propSchema.additionalProperties;

    if (additionalProperties && !subProperties) {
      // Mapping key/value
      input = (
        <MappingEditor
          value={(parentValue[key] as Record<string, string>) ?? {}}
          onChange={handleChange}
          disabled={disabled}
        />
      );
    } else if (subProperties) {
      // Object avec propriétés définies — rendu récursif (1 niveau max)
      const subValue = (parentValue[key] as Record<string, unknown>) ?? {};
      input = (
        <div style={{ paddingLeft: 12, borderLeft: '2px solid #f0f0f0' }}>
          {Object.entries(subProperties).map(([subKey, subSchema]) =>
            renderProperty(
              subKey,
              subSchema,
              subValue,
              (newSub) => handleChange(newSub),
              disabled,
              customRenderers,
            )
          )}
        </div>
      );
    } else {
      input = null;
    }
  } else {
    // Défaut : string
    input = (
      <Input
        value={(parentValue[key] as string) ?? ''}
        onChange={(e) => handleChange(e.target.value)}
        disabled={disabled}
        aria-label={label}
      />
    );
  }

  if (type === 'boolean') {
    // Boolean : label intégré au rendu
    return (
      <div key={key} style={{ marginBottom: 12 }}>
        {input}
        {description && (
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            {description}
          </Text>
        )}
      </div>
    );
  }

  return (
    <div key={key} style={{ marginBottom: 12 }}>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
        {label}
        {isRequired && <Text type="danger" style={{ marginLeft: 2 }}>*</Text>}
      </Text>
      {input}
      {description && (
        <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
          {description}
        </Text>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MappingEditor — interne au module, non exporté
// ---------------------------------------------------------------------------

interface MappingEditorProps {
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
  disabled?: boolean;
}

const MappingEditor: FC<MappingEditorProps> = ({ value, onChange, disabled = false }) => {
  const nextIdRef = useRef(0);
  const [rows, setRows] = useState<{ id: number; k: string; v: string }[]>(() =>
    Object.entries(value).map(([k, v]) => ({ id: nextIdRef.current++, k, v }))
  );
  const prevValueRef = useRef<Record<string, string>>(value);

  useEffect(() => {
    if (JSON.stringify(value) !== JSON.stringify(prevValueRef.current)) {
      prevValueRef.current = value;
      nextIdRef.current = 0;
      setRows(Object.entries(value).map(([k, v]) => ({ id: nextIdRef.current++, k, v })));
    }
  }, [value]);

  const emit = (newRows: { id: number; k: string; v: string }[]) => {
    const obj: Record<string, string> = {};
    for (const r of newRows) {
      if (r.k.trim()) obj[r.k.trim()] = r.v;
    }
    onChange(obj);
  };

  const updateRow = (idx: number, field: 'k' | 'v', val: string) => {
    const next = rows.map((r, i) => (i === idx ? { ...r, [field]: val } : r));
    setRows(next);
    emit(next);
  };

  const addRow = () => setRows([...rows, { id: nextIdRef.current++, k: '', v: '' }]);

  const removeRow = (idx: number) => {
    const next = rows.filter((_, i) => i !== idx);
    setRows(next);
    emit(next);
  };

  return (
    <div>
      {rows.map((row, idx) => (
        <div key={row.id} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
          <Input
            placeholder="Clé"
            value={row.k}
            onChange={(e) => updateRow(idx, 'k', e.target.value)}
            disabled={disabled}
            style={{ flex: 1 }}
          />
          <Input
            placeholder="Valeur"
            value={row.v}
            onChange={(e) => updateRow(idx, 'v', e.target.value)}
            disabled={disabled}
            style={{ flex: 1 }}
          />
          {!disabled && (
            <Button
              icon={<DeleteOutlined />}
              size="small"
              onClick={() => removeRow(idx)}
              aria-label="Supprimer"
            />
          )}
        </div>
      ))}
      {!disabled && (
        <Button
          icon={<PlusOutlined />}
          size="small"
          onClick={addRow}
          style={{ marginTop: 4 }}
        >
          Ajouter
        </Button>
      )}
    </div>
  );
};
