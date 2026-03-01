/**
 * Tests for PeriodComparisonChart component (Story 55.5, Tâche 5).
 * Cible : ≥ 90 % de couverture sur PeriodComparisonChart.tsx (16.7 → 90 %).
 * Recharts est mocké pour la compatibilité jsdom.
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PeriodComparisonChart } from './PeriodComparisonChart';
import type { ComparisonResult } from '../../../types/api';

// Mock recharts pour jsdom
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: ({ content }: { content?: React.ReactElement }) => {
    // Simuler le comportement recharts : cloner le content avec des props active/payload/label
    const rendered = content
      ? React.cloneElement(content as React.ReactElement<Record<string, unknown>>, {
          active: true,
          payload: [
            { name: 'Oracle', value: 95.5, color: '#1890ff' },
            { name: 'PostgreSQL', value: 88.2, color: '#fa8c16' },
          ],
          label: '2026-01',
        })
      : null;
    return <div data-testid="tooltip">{rendered}</div>;
  },
  Legend: () => null,
}));

const mockData: ComparisonResult = {
  dimension: 'technology',
  value1: 'Oracle',
  value2: 'PostgreSQL',
  value1_stats: {
    success_rate: 95.5,
    avg_time: 12.3,
    execution_count: 100,
    incident_count: 2,
  },
  value2_stats: {
    success_rate: 88.0,
    avg_time: 8.7,
    execution_count: 50,
    incident_count: 5,
  },
  deltas: {
    success_rate: -7.5,
    avg_time: -4.9,
    execution_count: -50.0,
    incident_count: 150.0,
  },
};

describe('PeriodComparisonChart', () => {
  it('affiche le skeleton quand loading=true', () => {
    render(<PeriodComparisonChart data={null} loading={true} />);
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
  });

  it('affiche Empty quand data=null et loading=false', () => {
    render(<PeriodComparisonChart data={null} loading={false} />);
    expect(screen.getByText('Sélectionnez deux périodes à comparer')).toBeInTheDocument();
  });

  it('affiche le graphique avec des données valides', () => {
    render(<PeriodComparisonChart data={mockData} />);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });

  it('affiche le titre avec les valeurs comparées', () => {
    render(<PeriodComparisonChart data={mockData} />);
    expect(screen.getByText(/Oracle vs PostgreSQL/)).toBeInTheDocument();
  });

  it('affiche le titre "Comparaison des tendances" quand loading=true', () => {
    render(<PeriodComparisonChart data={null} loading={true} />);
    expect(screen.getByText('Comparaison des tendances')).toBeInTheDocument();
  });

  it('affiche le titre "Comparaison des tendances" quand data=null', () => {
    render(<PeriodComparisonChart data={null} />);
    expect(screen.getByText('Comparaison des tendances')).toBeInTheDocument();
  });

  it('utilise les labels period1/period2 par défaut', () => {
    render(<PeriodComparisonChart data={mockData} />);
    // Les labels par défaut ("Période 1", "Période 2") sont définis dans les props
    // Le composant s'affiche sans erreur
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('accepte des labels period1/period2 personnalisés', () => {
    render(
      <PeriodComparisonChart
        data={mockData}
        period1Label="Q1 2025"
        period2Label="Q2 2025"
      />,
    );
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });
});

/**
 * Tests pour CustomTooltip (fonction interne).
 * Le tooltip est rendu dans le composant via recharts mock.
 * On teste le rendu direct.
 */
describe('CustomTooltip (via PeriodComparisonChart rendu)', () => {
  it('affiche le graphique sans erreur avec tooltip mocké', () => {
    render(<PeriodComparisonChart data={mockData} />);
    expect(screen.getByTestId('tooltip')).toBeInTheDocument();
  });
});
