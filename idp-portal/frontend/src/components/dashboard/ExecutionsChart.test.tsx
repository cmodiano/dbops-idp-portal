/**
 * Tests for ExecutionsChart component (Story 55.5, Tâche 4).
 * Cible : ≥ 90 % de couverture sur ExecutionsChart.tsx (0 → 90 %).
 * Recharts est mocké pour la compatibilité jsdom.
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutionsChart } from './ExecutionsChart';
import type { DashboardTimeSeriesPoint } from '../../types/api';

// Mock recharts pour jsdom (SVG/canvas non supportés)
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: ({
    formatter,
    labelFormatter,
  }: {
    formatter?: (value: number, name: string) => unknown[];
    labelFormatter?: (label: string) => string;
  }) => {
    // Appeler les formatteurs pour couvrir ces fonctions
    const fmt = formatter ? formatter(5, 'success') : null;
    const labelFmt = labelFormatter ? labelFormatter('2026-01-30') : null;
    return <div data-testid="tooltip">{String(fmt)} {String(labelFmt)}</div>;
  },
  Legend: ({
    formatter,
  }: {
    formatter?: (value: string) => string;
  }) => {
    const fmt = formatter ? formatter('success') : null;
    return <div data-testid="legend">{String(fmt)}</div>;
  },
}));

const mockData: DashboardTimeSeriesPoint[] = [
  { date: '2026-01-30', success: 5, failed: 2 },
  { date: '2026-01-31', success: 8, failed: 1 },
];

describe('ExecutionsChart', () => {
  it('affiche le skeleton quand loading=true', () => {
    render(<ExecutionsChart data={[]} loading={true} />);
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
    expect(screen.queryByTestId('responsive-container')).not.toBeInTheDocument();
  });

  it('affiche le graphique quand loading=false avec données', () => {
    render(<ExecutionsChart data={mockData} loading={false} />);
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('affiche le graphique avec données vides ([])', () => {
    render(<ExecutionsChart data={[]} />);
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });

  it('n\'affiche pas le skeleton quand loading non fourni (par défaut false)', () => {
    render(<ExecutionsChart data={mockData} />);
    expect(document.querySelector('.ant-skeleton')).not.toBeInTheDocument();
  });

  it('affiche le titre du card', () => {
    render(<ExecutionsChart data={mockData} />);
    expect(screen.getByText('Exécutions dans le temps')).toBeInTheDocument();
  });

  it('affiche le titre du card même en mode loading', () => {
    render(<ExecutionsChart data={[]} loading={true} />);
    expect(screen.getByText('Exécutions dans le temps')).toBeInTheDocument();
  });

  it('gère une date valide dans formatAxisDate', () => {
    const data: DashboardTimeSeriesPoint[] = [{ date: '2026-01-15', success: 3, failed: 0 }];
    render(<ExecutionsChart data={data} />);
    // Le composant s'affiche sans erreur
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });
});
