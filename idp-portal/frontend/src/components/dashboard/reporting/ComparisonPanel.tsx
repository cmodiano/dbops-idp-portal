/**
 * ComparisonPanel - Controls for setting up comparison parameters.
 * Story 8.6, AC1, AC2, AC3, AC4.
 *
 * Displays:
 * - Dimension selector (Technology, Environment, Period)
 * - Value selectors based on dimension (2 selects or 2 date range pickers)
 * - Compare button
 */

import { useState, useCallback } from 'react';
import { Space, Select, Button, DatePicker } from 'antd';
import { SwapOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import type { ComparisonDimension, FilterOptions } from '../../../types/api';

const { RangePicker } = DatePicker;

export interface ComparisonPanelProps {
  /** Available filter options for dropdowns. */
  filterOptions: FilterOptions | null;
  /** Whether comparison is loading. */
  loading?: boolean;
  /** Callback when compare is triggered. */
  onCompare: (
    dimension: ComparisonDimension,
    value1: string,
    value2: string,
    period1Start?: string,
    period1End?: string,
    period2Start?: string,
    period2End?: string,
  ) => void;
}

const DIMENSION_OPTIONS = [
  { label: 'Technologie', value: 'technology' as const },
  { label: 'Environnement', value: 'environment' as const },
  { label: 'Période', value: 'period' as const },
];

export function ComparisonPanel({ filterOptions, loading = false, onCompare }: ComparisonPanelProps) {
  const [dimension, setDimension] = useState<ComparisonDimension>('technology');
  const [value1, setValue1] = useState<string>('');
  const [value2, setValue2] = useState<string>('');
  const [period1, setPeriod1] = useState<[Dayjs | null, Dayjs | null]>([null, null]);
  const [period2, setPeriod2] = useState<[Dayjs | null, Dayjs | null]>([null, null]);

  // Get value options based on dimension
  const valueOptions = dimension === 'technology'
    ? (filterOptions?.engines || []).map((e) => ({ label: e, value: e }))
    : dimension === 'environment'
      ? (filterOptions?.environments || []).map((e) => ({ label: e, value: e }))
      : [];

  // Check if compare button should be enabled
  const canCompare = dimension === 'period'
    ? period1[0] && period1[1] && period2[0] && period2[1]
    : value1 && value2 && value1 !== value2;

  // Handle compare button click
  const handleCompare = useCallback(() => {
    if (dimension === 'period') {
      if (period1[0] && period1[1] && period2[0] && period2[1]) {
        onCompare(
          dimension,
          'Période 1',
          'Période 2',
          period1[0].format('YYYY-MM-DD'),
          period1[1].format('YYYY-MM-DD'),
          period2[0].format('YYYY-MM-DD'),
          period2[1].format('YYYY-MM-DD'),
        );
      }
    } else {
      onCompare(dimension, value1, value2);
    }
  }, [dimension, value1, value2, period1, period2, onCompare]);

  // Reset values when dimension changes
  const handleDimensionChange = useCallback((newDimension: ComparisonDimension) => {
    setDimension(newDimension);
    setValue1('');
    setValue2('');
    setPeriod1([null, null]);
    setPeriod2([null, null]);
  }, []);

  return (
    <Space wrap size="middle" style={{ width: '100%' }}>
      <Select
        style={{ width: 160 }}
        value={dimension}
        onChange={handleDimensionChange}
        options={DIMENSION_OPTIONS}
        aria-label="Dimension de comparaison"
      />

      {dimension === 'period' ? (
        <>
          <RangePicker
            value={period1}
            onChange={(dates) => setPeriod1(dates || [null, null])}
            placeholder={['Début P1', 'Fin P1']}
            aria-label="Période 1"
          />
          <SwapOutlined style={{ color: '#8c8c8c' }} />
          <RangePicker
            value={period2}
            onChange={(dates) => setPeriod2(dates || [null, null])}
            placeholder={['Début P2', 'Fin P2']}
            aria-label="Période 2"
          />
        </>
      ) : (
        <>
          <Select
            style={{ width: 180 }}
            value={value1 || undefined}
            onChange={setValue1}
            options={valueOptions}
            placeholder="Valeur 1"
            showSearch
            allowClear
            aria-label="Première valeur"
          />
          <SwapOutlined style={{ color: '#8c8c8c' }} />
          <Select
            style={{ width: 180 }}
            value={value2 || undefined}
            onChange={setValue2}
            options={valueOptions.filter((o) => o.value !== value1)}
            placeholder="Valeur 2"
            showSearch
            allowClear
            aria-label="Deuxième valeur"
          />
        </>
      )}

      <Button
        type="primary"
        onClick={handleCompare}
        disabled={!canCompare}
        loading={loading}
      >
        Comparer
      </Button>
    </Space>
  );
}

export default ComparisonPanel;
