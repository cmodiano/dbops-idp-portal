/**
 * ActionDrawerPreview - Read-only preview of action detail (Story 2.5, AC #1, #2, #4; Story 3.2; Story 3.4; Story 4.1; Story 7.1).
 *
 * Usage contexts:
 * - AdminPreview: inline preview card (role="region", no focus trap)
 * - CatalogPage drawer: inside Ant Design Drawer (role="dialog" on parent, focus trap managed by Drawer)
 * - Business catalog (Story 7.1): simplified view with variant='business'
 *
 * Displays:
 * - Action name and description (sanitized in business variant)
 * - Impact indicator with visual callout in business variant
 * - Engine and platform info (hidden in business variant)
 * - Tags (category display) - Story 3.2
 * - Parameters list with types (from parameters_schema) - Story 3.2 (simplified labels in business)
 * - Documentation section with rendered Markdown (Story 3.4, FR12)
 * - "Exécuter" button with permission state (AC3) - Story 3.2 (larger in business)
 *
 * Props:
 * - canExecute: undefined = enabled (admin preview), false = disabled with tooltip (catalog)
 * - onExecute: callback when Execute button is clicked (Story 4.1, Task 7)
 * - variant: 'default' | 'business' - simplified UI for business users (Story 7.1)
 *
 * Story 2.23: category removed — use tags for categorization.
 * Story 3.4: documentation_md field with Markdown rendering.
 * Story 4.1: Execute button opens ExecutionWizard.
 * Story 7.1: Business variant with sanitized descriptions, impact callout, larger execute button.
 */

import { Card, Typography, Button, Descriptions, Space, Empty, Tag, Tooltip, Divider, Badge, Alert, theme } from 'antd';
import { PlayCircleOutlined, FileTextOutlined, ApartmentOutlined, BarChartOutlined } from '@ant-design/icons';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { ActionPreviewData } from '../../types/api';
import { useTheme } from '../../contexts/ThemeContext';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { IMPACT_LABELS } from '../shared/impactLabels';
import { getTagStyle } from '../../utils/tagStyles';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { ActionMetrics } from './ActionMetrics';

const { Title, Paragraph, Text } = Typography;

export interface ActionDrawerPreviewProps {
  action: ActionPreviewData;
  visible?: boolean;
  /** Story 3.2 AC3: whether user can execute this action. */
  canExecute?: boolean;
  /** Story 3.2 AC3: environments where user can execute. */
  allowedEnvironments?: string[];
  /** Story 4.1 Task 7: callback when Execute button is clicked. Opens ExecutionWizard. */
  onExecute?: () => void;
  /** Story 7.1: 'business' variant for simplified UI for business users. */
  variant?: 'default' | 'business';
  /** Story 8.1: Loading state for stats (separate from action data). */
  statsLoading?: boolean;
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
  onExecute,
  variant = 'default',
  statsLoading = false,
}: ActionDrawerPreviewProps) {
  // Note: allowedEnvironments is passed to the component for future env-specific execute button logic
  // Currently used in parent (CatalogPage) to determine canExecute; kept here for complete prop interface
  void allowedEnvironments;
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';
  const { token } = theme.useToken();
  const isBusiness = variant === 'business';

  if (!visible) return null;

  const parameters = extractParametersWithTypes(action.parameters_schema);
  const isExecuteDisabled = canExecute === false;
  const executeTooltip = isExecuteDisabled
    ? 'Acces non autorise pour cet environnement'
    : undefined;
  const isWorkflow = action.item_type === 'workflow';

  // Story 7.1: Sanitize description for business users
  const displayDescription = isBusiness
    ? sanitizeDescription(action.description)
    : action.description;

  // Story 7.1: Impact label for business callout
  const impactLabel = action.impact_level ? IMPACT_LABELS[action.impact_level] : null;
  const impactAlertType = action.impact_level === 'high' ? 'error' : action.impact_level === 'medium' ? 'warning' : 'info';

  // Story 7.1: Simplified labels for business variant
  const parametersLabel = isBusiness ? 'Options' : 'Parametres attendus';
  const categoryLabel = isBusiness ? 'Type' : 'Categorie';

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
          <Space align="center" size={8}>
            {/* Story 5.7, AC3: Workflow indicator */}
            {isWorkflow && (
              <Tooltip title="Workflow (chaîne d'actions)">
                <Badge
                  count={<ApartmentOutlined style={{ color: '#722ed1' }} />}
                  style={{ backgroundColor: 'transparent' }}
                />
              </Tooltip>
            )}
            <Title level={4} style={{ margin: 0 }}>
              {action.name || 'Sans nom'}
            </Title>
          </Space>
          {action.impact_level && (
            <ImpactIndicator level={action.impact_level} />
          )}
        </div>

        {/* Description - sanitized for business variant (Story 7.1) */}
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {displayDescription || 'Aucune description disponible.'}
        </Paragraph>

        {/* Story 7.1 AC3: Impact callout for business users (triple coding: icon, color, text) */}
        {isBusiness && action.impact_level && (
          <Alert
            type={impactAlertType}
            title={`Niveau d'impact: ${impactLabel}`}
            showIcon
            style={{ marginTop: 8 }}
          />
        )}

        {/* Tags (category) - Story 3.2, AC1; Story 7.1: simplified label */}
        {action.tags && action.tags.length > 0 && (
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              {categoryLabel}
            </Text>
            <Space size={[4, 4]} wrap>
              {action.tags.map((tag) => {
                const tagStyle = getTagStyle(tag, isDark);
                return (
                  <Tag key={tag} style={{ borderRadius: 16, padding: '2px 10px', ...tagStyle }}>
                    {tag}
                  </Tag>
                );
              })}
            </Space>
          </div>
        )}

        {/* Metadata - hidden for business variant (Story 7.1: action as black box) */}
        {!isBusiness && (
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
        )}

        {/* Parameters with types - Story 3.2, AC1; Story 7.1: simplified label */}
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            {parametersLabel}
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

        {/* Documentation section - Story 3.4, FR12, AC1, AC2, AC3, AC5 */}
        <Divider style={{ margin: '16px 0' }} />
        <div>
          <Space align="center" style={{ marginBottom: 8 }}>
            <FileTextOutlined />
            <Text strong>Documentation</Text>
          </Space>
          {action.documentation_md ? (
            <div
              style={{
                maxHeight: 300,
                overflowY: 'auto',
                padding: '12px 16px',
                backgroundColor: token.colorBgTextHover,
                borderRadius: token.borderRadius,
              }}
              data-testid="documentation-content"
            >
              <Markdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeSanitize]}
                components={{
                  // Style headings to match Ant Design
                  h1: ({ children }) => <Title level={3}>{children}</Title>,
                  h2: ({ children }) => <Title level={4}>{children}</Title>,
                  h3: ({ children }) => <Title level={5}>{children}</Title>,
                  h4: ({ children }) => <Text strong style={{ display: 'block', marginTop: 8 }}>{children}</Text>,
                  h5: ({ children }) => <Text strong style={{ display: 'block', marginTop: 8 }}>{children}</Text>,
                  h6: ({ children }) => <Text strong style={{ display: 'block', marginTop: 8 }}>{children}</Text>,
                  // Style paragraphs
                  p: ({ children }) => <Paragraph style={{ marginBottom: 8 }}>{children}</Paragraph>,
                  // Style code blocks
                  code: ({ className, children }) => {
                    const isInline = !className;
                    if (isInline) {
                      return <Text code>{children}</Text>;
                    }
                    return (
                      <pre
                        style={{
                          backgroundColor: token.colorBgContainer,
                          padding: 12,
                          borderRadius: token.borderRadius,
                          overflow: 'auto',
                          fontSize: 13,
                          border: `1px solid ${token.colorBorder}`,
                        }}
                      >
                        <code>{children}</code>
                      </pre>
                    );
                  },
                  // Style tables for Ant Design consistency
                  table: ({ children }) => (
                    <table
                      style={{
                        width: '100%',
                        borderCollapse: 'collapse',
                        marginBottom: 16,
                      }}
                    >
                      {children}
                    </table>
                  ),
                  th: ({ children }) => (
                    <th
                      style={{
                        padding: '8px 12px',
                        backgroundColor: token.colorBgTextHover,
                        border: `1px solid ${token.colorBorder}`,
                        textAlign: 'left',
                      }}
                    >
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td
                      style={{
                        padding: '8px 12px',
                        border: `1px solid ${token.colorBorder}`,
                      }}
                    >
                      {children}
                    </td>
                  ),
                }}
              >
                {action.documentation_md}
              </Markdown>
            </div>
          ) : (
            <Empty
              description="Aucune documentation disponible"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ margin: 0 }}
              data-testid="documentation-empty"
            />
          )}
        </div>

        {/* Metrics section - Story 8.1, AC1, AC2, AC3 (hidden in business variant) */}
        {!isBusiness && (
          <>
            <Divider style={{ margin: '16px 0' }} />
            <div data-testid="metrics-section">
              <Space align="center" style={{ marginBottom: 8 }}>
                <BarChartOutlined />
                <Text strong>Metriques (30 derniers jours)</Text>
              </Space>
              <ActionMetrics stats={action.stats} loading={statsLoading} />
            </div>
          </>
        )}

        {/* Execute button - Story 3.2 AC3, Story 4.1 Task 7, Story 7.1: larger for business */}
        <Tooltip title={executeTooltip}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            disabled={isExecuteDisabled}
            block
            size={isBusiness ? 'large' : 'middle'}
            aria-label={isExecuteDisabled ? 'Executer (acces non autorise)' : 'Executer'}
            onClick={onExecute}
          >
            Executer
          </Button>
        </Tooltip>
      </Space>
    </Card>
  );
}
