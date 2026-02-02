/**
 * DeltaBadge - Display percentage change with color and arrow icon.
 * Story 8.6, AC5.
 *
 * Shows delta with:
 * - Green for improvement (up arrow for positive when higher is better)
 * - Red for degradation
 * - Gray for neutral (0%)
 */

import { Tag } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons';

export interface DeltaBadgeProps {
  /** Delta value as percentage. */
  delta: number | null;
  /** If true, a negative delta is an improvement (e.g., for time, incidents). */
  invertColors?: boolean;
}

export function DeltaBadge({ delta, invertColors = false }: DeltaBadgeProps) {
  if (delta === null || delta === 0) {
    return (
      <Tag icon={<MinusOutlined />} color="default">
        0%
      </Tag>
    );
  }

  const isPositive = delta > 0;
  const isGood = invertColors ? !isPositive : isPositive;
  const color = isGood ? 'green' : 'red';
  const Icon = isPositive ? ArrowUpOutlined : ArrowDownOutlined;

  return (
    <Tag icon={<Icon />} color={color}>
      {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
    </Tag>
  );
}

export default DeltaBadge;
