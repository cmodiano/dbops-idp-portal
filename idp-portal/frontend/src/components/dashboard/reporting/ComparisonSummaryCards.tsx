/**
 * ComparisonSummaryCards - Display comparison metrics as cards with deltas.
 * Story 8.6, AC5.
 *
 * Shows 4 cards: Success Rate, Avg Time, Executions, Incidents.
 * Each card shows value1, value2, and delta badge.
 */

import type { ReactNode } from 'react';
import { Row, Col, Card, Typography } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  RocketOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { DeltaBadge } from './DeltaBadge';
import type { ComparisonResult, ComparisonMetric } from '../../../types/api';
import { STYLE_TOKENS } from '../../../theme/styleTokens';

const { Text } = Typography;

export interface ComparisonSummaryCardsProps {
  /** Comparison result data. */
  data: ComparisonResult | null;
  /** Whether the cards are loading. */
  loading?: boolean;
  /** Callback when a metric card is clicked (for drill-down). */
  onMetricClick?: (metric: ComparisonMetric) => void;
}

/** Card configuration for each metric. */
const METRIC_CONFIG: Array<{
  key: ComparisonMetric;
  label: string;
  icon: ReactNode;
  invertDelta?: boolean;
  formatter?: (val: number | null) => string;
}> = [
  {
    key: 'success_rate',
    label: 'Taux de succès',
    icon: <CheckCircleOutlined style={{ color: STYLE_TOKENS.iconSuccess }} />,
    invertDelta: false,
    formatter: (v) => v !== null ? `${v.toFixed(1)}%` : 'N/A',
  },
  {
    key: 'avg_time',
    label: 'Temps moyen',
    icon: <ClockCircleOutlined style={{ color: '#1890ff' }} />,
    invertDelta: true, // Lower is better
    formatter: (v) => v !== null ? `${v.toFixed(1)}s` : 'N/A',
  },
  {
    key: 'execution_count',
    label: 'Exécutions',
    icon: <RocketOutlined style={{ color: STYLE_TOKENS.workflowColor }} />,
    invertDelta: false,
    formatter: (v) => v !== null ? v.toString() : 'N/A',
  },
  {
    key: 'incident_count',
    label: 'Incidents',
    icon: <ExclamationCircleOutlined style={{ color: STYLE_TOKENS.iconError }} />,
    invertDelta: true, // Lower is better
    formatter: (v) => v !== null ? v.toString() : 'N/A',
  },
];

export function ComparisonSummaryCards({ data, loading = false, onMetricClick }: ComparisonSummaryCardsProps) {
  return (
    <Row gutter={[16, 16]}>
      {METRIC_CONFIG.map(({ key, label, icon, invertDelta, formatter }) => {
        const value1 = data?.value1_stats[key as keyof typeof data.value1_stats] as number | null;
        const value2 = data?.value2_stats[key as keyof typeof data.value2_stats] as number | null;
        const delta = data?.deltas[key] ?? null;

        return (
          <Col key={key} xs={24} sm={12} md={6}>
            <Card
              size="small"
              hoverable={!!onMetricClick}
              onClick={() => onMetricClick?.(key)}
              style={{ cursor: onMetricClick ? 'pointer' : 'default' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                {icon}
                <Text strong>{label}</Text>
              </div>

              {loading ? (
                <div style={{ height: 60, background: '#f5f5f5', borderRadius: 4 }} />
              ) : data ? (
                <>
                  <Row gutter={8}>
                    <Col span={12}>
                      <div style={{ fontSize: 12, color: STYLE_TOKENS.textMuted }}>{data.value1}</div>
                      <div style={{ fontSize: 16, fontWeight: 600 }}>
                        {formatter ? formatter(value1) : (value1 ?? 'N/A')}
                      </div>
                    </Col>
                    <Col span={12}>
                      <div style={{ fontSize: 12, color: STYLE_TOKENS.textMuted }}>{data.value2}</div>
                      <div style={{ fontSize: 16, fontWeight: 600 }}>
                        {formatter ? formatter(value2) : (value2 ?? 'N/A')}
                      </div>
                    </Col>
                  </Row>
                  <div style={{ marginTop: 8 }}>
                    <DeltaBadge delta={delta} invertColors={invertDelta} />
                  </div>
                </>
              ) : (
                <Text type="secondary">Aucune donnée</Text>
              )}
            </Card>
          </Col>
        );
      })}
    </Row>
  );
}

export default ComparisonSummaryCards;
