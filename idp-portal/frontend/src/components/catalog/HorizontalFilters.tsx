/**
 * HorizontalFilters - Horizontal filter bar for catalog (Story 8.7, AC5).
 *
 * Features:
 * - Compact inline layout with 3 Select dropdowns: Moteur, Environnement, Impact
 * - Multi-select mode for each filter (NOTE: backend currently supports only single value per filter)
 * - Replaces the lateral drawer (AC7)
 * - Spacing md (16px)
 */

import { Row, Col, Select, Typography } from 'antd';

const { Text } = Typography;

/** Engine filter options. */
export const ENGINE_OPTIONS = [
  { value: 'Oracle', label: 'Oracle' },
  { value: 'SQL Server', label: 'SQL Server' },
  { value: 'DB2', label: 'DB2' },
];

/** Environment filter options. */
export const ENVIRONMENT_OPTIONS = [
  { value: 'DEV', label: 'DEV' },
  { value: 'QUAL', label: 'QUAL' },
  { value: 'PROD', label: 'PROD' },
];

/** Impact filter options. */
export const IMPACT_OPTIONS = [
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyen' },
  { value: 'high', label: 'Élevé' },
];

export interface HorizontalFiltersProps {
  /** Selected engines. */
  selectedEngines: string[];
  /** Selected environments. */
  selectedEnvironments: string[];
  /** Selected impacts. */
  selectedImpacts: string[];
  /** Callback when engines change. */
  onEnginesChange: (values: string[]) => void;
  /** Callback when environments change. */
  onEnvironmentsChange: (values: string[]) => void;
  /** Callback when impacts change. */
  onImpactsChange: (values: string[]) => void;
}

/**
 * Horizontal filter bar for catalog filtering.
 * Replaces the lateral drawer with inline Select dropdowns.
 */
export function HorizontalFilters({
  selectedEngines,
  selectedEnvironments,
  selectedImpacts,
  onEnginesChange,
  onEnvironmentsChange,
  onImpactsChange,
}: HorizontalFiltersProps) {
  return (
    <Row gutter={16} style={{ marginBottom: 16 }} align="middle">
      <Col xs={24} sm={8}>
        <Text strong style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
          Moteur
        </Text>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="Tous les moteurs"
          value={selectedEngines}
          onChange={onEnginesChange}
          options={ENGINE_OPTIONS}
          allowClear
          maxTagCount="responsive"
          aria-label="Filtrer par moteur"
        />
      </Col>
      <Col xs={24} sm={8}>
        <Text strong style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
          Environnement
        </Text>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="Tous les environnements"
          value={selectedEnvironments}
          onChange={onEnvironmentsChange}
          options={ENVIRONMENT_OPTIONS}
          allowClear
          maxTagCount="responsive"
          aria-label="Filtrer par environnement"
        />
      </Col>
      <Col xs={24} sm={8}>
        <Text strong style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
          Impact
        </Text>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="Tous les impacts"
          value={selectedImpacts}
          onChange={onImpactsChange}
          options={IMPACT_OPTIONS}
          allowClear
          maxTagCount="responsive"
          aria-label="Filtrer par impact"
        />
      </Col>
    </Row>
  );
}

export default HorizontalFilters;
