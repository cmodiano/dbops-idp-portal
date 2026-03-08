/**
 * OutputSchemaPanel — Panneau admin pour déclarer le schéma d'output d'une action.
 * Story 63.9: Déclarer les outputs par action.
 *
 * Permet à un admin de sélectionner un OutputSchema (type 'action') depuis l'API,
 * prévisualise les output_fields du schéma sélectionné.
 */

import { useEffect, useState } from 'react';
import { Select, Space, Typography, Alert } from 'antd';
import { fetchOutputSchemasList } from '../../services/output_schema_service';
import type { OutputSchemaListItem } from '../../services/output_schema_service';

const { Text } = Typography;

export interface OutputSchemaPanelProps {
  /** Identifiant du schéma sélectionné (null = aucun). */
  value: number | null;
  /** Appelé quand l'utilisateur change la sélection. */
  onChange: (id: number | null) => void;
  /** Afficher le panel uniquement si admin. */
  isAdmin: boolean;
  /** Désactiver les interactions (mode lecture seule). */
  disabled?: boolean;
}

export function OutputSchemaPanel({ value, onChange, isAdmin, disabled }: OutputSchemaPanelProps) {
  const [schemas, setSchemas] = useState<OutputSchemaListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchOutputSchemasList('action')
      .then((data) => {
        if (!cancelled) setSchemas(data);
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger les schémas d\'output.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [isAdmin]);

  if (!isAdmin) return null;

  const selectedSchema = schemas.find((s) => s.id === value) ?? null;
  const outputFields = selectedSchema?.schema_json?.output_fields ?? [];

  const options = [
    ...schemas.map((s) => ({
      label: `${s.name} (${s.schema_json?.output_fields?.length ?? 0} champs)`,
      value: s.id,
    })),
  ];

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="small">
      <Text strong>Schéma d'output déclaré</Text>
      {error && <Alert type="error" title={error} showIcon />}
      <Select
        allowClear
        placeholder="Aucun schéma déclaré"
        loading={loading}
        options={options}
        value={value ?? undefined}
        onChange={(id) => onChange(id ?? null)}
        disabled={disabled}
        style={{ width: '100%' }}
        aria-label="Sélectionner un schéma d'output"
      />
      {selectedSchema && outputFields.length > 0 && (
        <div>
          <Text type="secondary">Variables exposées par ce schéma :</Text>
          <ul style={{ margin: 0, padding: '4px 0 0 16px' }}>
            {outputFields.map((field) => (
              <li key={field.name} style={{ padding: '2px 0' }}>
                <Text code>{field.name}</Text>
                <Text type="secondary" style={{ marginLeft: 8 }}>: {field.type}</Text>
                {field.description && (
                  <Text type="secondary" style={{ marginLeft: 8 }}>— {field.description}</Text>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {selectedSchema && outputFields.length === 0 && (
        <Text type="secondary" italic>Ce schéma ne déclare aucun champ output.</Text>
      )}
    </Space>
  );
}
