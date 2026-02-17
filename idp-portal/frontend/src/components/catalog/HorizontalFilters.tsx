/**
 * HorizontalFilters - Horizontal filter bar for catalog (Story 8.7, AC5; Story 18.4: removed Environment filter).
 *
 * Features:
 * - Compact inline layout with 2 Select dropdowns: Moteur, Impact
 * - Multi-select mode for both filters (NOTE: backend currently supports only single value per filter)
 * - Replaces the lateral drawer (AC7)
 * - Spacing md (16px)
 * - Story 18.4: Environment filter removed (environment is a target property, not an action property)
 */

import { Row, Col, Select, Typography } from 'antd';
import { useEngines } from '../../hooks/useEngines';

const { Text } = Typography;

/** Impact filter options. */
// eslint-disable-next-line react-refresh/only-export-components
export const IMPACT_OPTIONS = [
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyen' },
  { value: 'high', label: 'Élevé' },
];

export interface HorizontalFiltersProps {
  /** Selected engines. */
  selectedEngines: string[];
  /** Selected impacts. */
  selectedImpacts: string[];
  /** Callback when engines change. */
  onEnginesChange: (values: string[]) => void;
  /** Callback when impacts change. */
  onImpactsChange: (values: string[]) => void;
}

/**
 * Horizontal filter bar for catalog filtering.
 * Replaces the lateral drawer with inline Select dropdowns.
 */
export function HorizontalFilters({
  selectedEngines,
  selectedImpacts,
  onEnginesChange,
  onImpactsChange,
}: HorizontalFiltersProps) {
  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions, loading: enginesLoading } = useEngines();

  return (
    <Row gutter={16} style={{ marginBottom: 16 }} align="middle">
      <Col xs={24} sm={12}>
        <Text strong style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
          Moteur
        </Text>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder={enginesLoading ? "Chargement..." : "Tous les moteurs"}
          value={selectedEngines}
          onChange={onEnginesChange}
          options={engineOptions}
          allowClear
          maxTagCount="responsive"
          aria-label="Filtrer par moteur"
          loading={enginesLoading}
        />
      </Col>
      <Col xs={24} sm={12}>
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
