/**
 * ActionDrawerPreview - Read-only preview of action detail (Story 2.5, AC #1, #2, #4; Story 3.2).
 *
 * Usage contexts:
 * - AdminPreview: inline preview card (role="region", no focus trap)
 * - CatalogPage drawer: inside Ant Design Drawer (role="dialog" on parent, focus trap managed by Drawer)
 *
 * Displays:
 * - Action name and description
 * - Impact indicator
 * - Engine and platform info
 * - Tags (category display) - Story 3.2
 * - Parameters list with types (from parameters_schema) - Story 3.2
 * - "Exécuter" button with permission state (AC3) - Story 3.2
 *
 * Props:
 * - canExecute: undefined = enabled (admin preview), false = disabled with tooltip (catalog)
 *
 * Story 2.23: category removed — use tags for categorization.
 */

import { Card, Typography, Button, Descriptions, Space, Empty, Tag, Tooltip, theme } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import type { ActionPreviewData } from '../../types/api';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { STYLE_TOKENS } from '../../theme/styleTokens';

const { Title, Paragraph, Text } = Typography;

export interface ActionDrawerPreviewProps {
  action: ActionPreviewData;
  visible?: boolean;
  /** Story 3.2 AC3: whether user can execute this action. */
  canExecute?: boolean;
  /** Story 3.2 AC3: environments where user can execute. */
  allowedEnvironments?: string[];
}

/** Parameter info extracted from JSON Schema. */
interface ParameterInfo {
  name: string;
  type: string;
  required: boolean;
}

function extractParametersWithTypes(schema: Record<string, unknown> | null): ParameterInfo[] {
  if (!schema) return [];

  // JSON Schema format: { "properties": { "param1": { "type": "string" }, "param2": { "type": "number" } }, "required": ["param1"] }
  const properties = schema.properties as Record<string, Record<string, unknown>> | undefined;
  const required = (schema.required as string[]) || [];

  if (properties && typeof properties === 'object') {
    return Object.entries(properties).map(([name, prop]) => ({
      name,
      type: (prop?.type as string) || 'any',
      required: required.includes(name),
    }));
  }

  return [];
}

export function ActionDrawerPreview({
  action,
  visible = true,
  canExecute,
  allowedEnvironments = [],
}: ActionDrawerPreviewProps) {
  const { token } = theme.useToken();

  if (!visible) return null;

  const parameters = extractParametersWithTypes(action.parameters_schema);
  const isExecuteDisabled = canExecute === false;
  const executeTooltip = isExecuteDisabled
    ? 'Acces non autorise pour cet environnement'
    : undefined;

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
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
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

        {/* Tags (category) - Story 3.2, AC1 */}
        {action.tags && action.tags.length > 0 && (
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              Categorie
            </Text>
            <Space size={[4, 4]} wrap>
              {action.tags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </Space>
          </div>
        )}

        {/* Metadata */}
        <Descriptions column={1} size="small" bordered={false}>
          {action.engine && (
            <Descriptions.Item label="Moteur">
              <Text>{action.engine}</Text>
            </Descriptions.Item>
          )}
          {action.platform && (
            <Descriptions.Item label="Plateforme">
              <Text>{action.platform}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>

        {/* Parameters with types - Story 3.2, AC1 */}
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            Parametres attendus
          </Text>
          {parameters.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {parameters.map((param) => (
                <li key={param.name}>
                  <Text code>{param.name}</Text>
                  <Text type="secondary"> : {param.type}</Text>
                  {param.required && <Text type="danger"> *</Text>}
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

        {/* Execute button - Story 3.2, AC3 */}
        <Tooltip title={executeTooltip}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            disabled={isExecuteDisabled}
            block
            aria-label={isExecuteDisabled ? 'Executer (acces non autorise)' : 'Executer'}
          >
            Executer
          </Button>
        </Tooltip>
      </Space>
    </Card>
  );
}
