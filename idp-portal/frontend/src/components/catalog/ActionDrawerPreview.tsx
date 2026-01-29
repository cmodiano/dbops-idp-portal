/**
 * ActionDrawerPreview - Read-only preview of action detail drawer (Story 2.5, AC #1, #2, #4).
 *
 * Used in AdminPreview to simulate the drawer that DBA will see in the catalog.
 * Displays:
 * - Action name and description
 * - Impact indicator
 * - Engine and category info
 * - Parameters list (from parameters_schema)
 * - Disabled "Executer" button (read-only)
 *
 * Accessibility:
 * - role="region" (not dialog, since it's inline and not modal)
 * - aria-label for screen readers
 * - No focus trap (read-only preview, not interactive dialog)
 */

import { Card, Typography, Button, Descriptions, Space, Empty, theme } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import type { ActionPreviewData } from '../../types/api';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { STYLE_TOKENS } from '../../theme/styleTokens';

const { Title, Paragraph, Text } = Typography;

export interface ActionDrawerPreviewProps {
  action: ActionPreviewData;
  visible?: boolean;
}

function extractParametersList(schema: Record<string, unknown> | null): string[] {
  if (!schema) return [];

  // JSON Schema format: { "properties": { "param1": {...}, "param2": {...} } }
  // TODO: support $ref, allOf, oneOf for advanced schemas (code-review LOW).
  const properties = schema.properties as Record<string, unknown> | undefined;
  if (properties && typeof properties === 'object') {
    return Object.keys(properties);
  }

  return [];
}

export function ActionDrawerPreview({ action, visible = true }: ActionDrawerPreviewProps) {
  const { token } = theme.useToken();

  if (!visible) return null;

  const parameters = extractParametersList(action.parameters_schema);

  return (
    <Card
      role="region"
      aria-label={`Preview fiche action: ${action.name || 'Sans nom'}`}
      style={{
        width: '100%',
        borderRadius: STYLE_TOKENS.drawerPreviewRadius,
        boxShadow: token.boxShadowSecondary,
      }}
      styles={{
        body: { padding: STYLE_TOKENS.drawerPreviewPadding },
      }}
    >
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Title level={4} style={{ margin: 0 }}>
            {action.name || 'Sans nom'}
          </Title>
          {action.impact_level && (
            <ImpactIndicator level={action.impact_level} />
          )}
        </div>

        {/* Description */}
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {action.description || 'Aucune description disponible.'}
        </Paragraph>

        {/* Metadata */}
        <Descriptions column={1} size="small" bordered={false}>
          {action.engine && (
            <Descriptions.Item label="Moteur">
              <Text>{action.engine}</Text>
            </Descriptions.Item>
          )}
          {action.category && (
            <Descriptions.Item label="Categorie">
              <Text>{action.category}</Text>
            </Descriptions.Item>
          )}
          {action.platform && (
            <Descriptions.Item label="Plateforme">
              <Text>{action.platform}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>

        {/* Parameters */}
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            Parametres attendus
          </Text>
          {parameters.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {parameters.map((param) => (
                <li key={param}>
                  <Text code>{param}</Text>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              description="Aucun parametre defini"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ margin: 0 }}
            />
          )}
        </div>

        {/* Disabled Execute button (AC #4 - read-only) */}
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          disabled
          block
          aria-label="Executer (desactive en mode preview)"
        >
          Executer
        </Button>
      </Space>
    </Card>
  );
}
