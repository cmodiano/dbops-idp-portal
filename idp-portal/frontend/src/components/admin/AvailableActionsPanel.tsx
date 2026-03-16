/**
 * AvailableActionsPanel — Displays available actions for a selected integration type (Story 24.2 AC3, AC4, AC8).
 * Shows a compact table with expandable rows for parameter details.
 */

import { Table, Tag, Badge, Typography, Empty } from 'antd';
import type { IntegrationAction, IntegrationTypeCatalogue } from '../../types/api';

interface JsonSchemaProperty {
  type?: string;
  description?: string;
}

function parseSchemaProperties(schema: Record<string, unknown>): Record<string, JsonSchemaProperty> {
  const properties = schema?.properties;
  if (!properties || typeof properties !== 'object') return {};
  return properties as Record<string, JsonSchemaProperty>;
}

function ParamList({ schema, label }: { schema: Record<string, unknown>; label: string }) {
  const properties = parseSchemaProperties(schema);
  const entries = Object.entries(properties);

  if (entries.length === 0) {
    return (
      <div style={{ marginBottom: 8 }}>
        <Typography.Text strong>{label} :</Typography.Text>
        <Typography.Text type="secondary"> Schéma non disponible</Typography.Text>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 8 }}>
      <Typography.Text strong>{label} :</Typography.Text>
      <ul style={{ margin: '4px 0 0 0', paddingLeft: 20 }}>
        {entries.map(([key, prop]) => (
          <li key={key}>
            <code>{key}</code> ({prop.type ?? 'unknown'}) — {prop.description ?? 'Pas de description'}
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface AvailableActionsPanelProps {
  selectedType: IntegrationTypeCatalogue | null;
}

export function AvailableActionsPanel({ selectedType }: AvailableActionsPanelProps) {
  if (!selectedType) return null;

  const actions = (selectedType.actions ?? []).filter((a) => a.is_active);

  return (
    <div style={{ marginTop: 16 }} data-testid="available-actions-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>
          Actions disponibles
        </Typography.Title>
        <div>
          <Badge count={actions.length} color="blue" style={{ marginRight: 8 }} />
          <Tag color="default">Version {selectedType.version}</Tag>
        </div>
      </div>

      {actions.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="Aucune action définie pour ce type d'intégration"
        />
      ) : (
        <Table<IntegrationAction>
          size="small"
          dataSource={actions}
          pagination={false}
          rowKey="id"
          columns={[
            {
              title: 'Action',
              dataIndex: 'action_label',
              key: 'label',
              width: '30%',
            },
            {
              title: 'Code',
              dataIndex: 'action_code',
              key: 'code',
              width: '20%',
              render: (code: string) => <Tag color="default">{code}</Tag>,
            },
            {
              title: 'Description',
              dataIndex: 'description',
              key: 'description',
              width: '40%',
            },
            {
              title: 'Paramètres',
              key: 'params',
              width: '10%',
              render: (_, record) => {
                const requiredCount = Object.keys(
                  parseSchemaProperties(record.required_params),
                ).length;
                return requiredCount > 0 ? (
                  <Badge count={`${requiredCount} requis`} color="orange" />
                ) : (
                  <Typography.Text type="secondary">—</Typography.Text>
                );
              },
            },
          ]}
          expandable={{
            expandedRowRender: (record) => (
              <div style={{ padding: 8 }}>
                <ParamList schema={record.required_params} label="Paramètres requis" />
                <ParamList schema={record.optional_params} label="Paramètres optionnels" />
              </div>
            ),
          }}
        />
      )}
    </div>
  );
}
