/**
 * AdminPreview - Container for real-time action preview in admin form (Story 2.5, AC #1, #2, #3, #4, #5).
 *
 * Displays:
 * - ActionCard (preview variant) at the top
 * - ActionDrawerPreview (simulated inline drawer) below
 *
 * Features:
 * - Real-time updates from form data
 * - aria-live="polite" for accessibility (AC #5)
 * - Read-only preview (no interactions)
 *
 * Used in ActionForm split view layout.
 */

import { Typography, Space, Divider, theme } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { ActionPreviewData } from '../../types/api';
import { ActionCard } from '../catalog/ActionCard';
import { ActionDrawerPreview } from '../catalog/ActionDrawerPreview';

const { Title } = Typography;

export interface AdminPreviewProps {
  formData: ActionPreviewData;
}

export function AdminPreview({ formData }: AdminPreviewProps) {
  const { token } = theme.useToken();

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      style={{
        position: 'sticky',
        top: 24,
        height: 'fit-content',
      }}
    >
      {/* Header */}
      <Space align="center" style={{ marginBottom: 16 }}>
        <EyeOutlined style={{ fontSize: 18, color: token.colorPrimary }} />
        <Title level={5} style={{ margin: 0 }}>
          Preview
        </Title>
      </Space>

      {/* ActionCard preview */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
          Carte catalogue
        </Title>
        <ActionCard action={formData} variant="preview" />
      </div>

      <Divider style={{ margin: '16px 0' }} />

      {/* ActionDrawerPreview */}
      <div>
        <Title level={5} type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
          Fiche action (drawer)
        </Title>
        <ActionDrawerPreview action={formData} />
      </div>
    </div>
  );
}
