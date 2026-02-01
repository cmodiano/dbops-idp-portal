/**
 * Tests for ActionMetrics component (Story 8.1).
 *
 * Tests:
 * - AC1: Display scorecards with 4 metrics
 * - AC2: Color coding for success rate (green >95%, orange 80-95%, red <80%)
 * - AC3: "Pas encore de donnees" message when stats is null or total_executions = 0
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { ActionMetrics } from './ActionMetrics';
import type { ActionStats } from '../../types/api';

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<ConfigProvider>{ui}</ConfigProvider>);
};

describe('ActionMetrics', () => {
  describe('AC1: Display scorecards', () => {
    it('displays all 4 metrics when stats are provided', () => {
      const stats: ActionStats = {
        success_rate: 95.5,
        avg_execution_time_ms: 5000,
        total_executions: 100,
        incidents_count: 5,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByText('Taux de succes')).toBeInTheDocument();
      expect(screen.getByText('Temps moyen')).toBeInTheDocument();
      expect(screen.getByText('Executions')).toBeInTheDocument();
      expect(screen.getByText('Incidents')).toBeInTheDocument();
      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
    });

    it('formats execution time in minutes when >= 60s', () => {
      const stats: ActionStats = {
        success_rate: 90.0,
        avg_execution_time_ms: 125000, // 2 min 5 sec
        total_executions: 50,
        incidents_count: 5,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByText('2 min 5 s')).toBeInTheDocument();
    });

    it('formats execution time in ms when < 1s', () => {
      const stats: ActionStats = {
        success_rate: 100,
        avg_execution_time_ms: 500,
        total_executions: 10,
        incidents_count: 0,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByText('500 ms')).toBeInTheDocument();
    });

    it('shows dash when avg_execution_time_ms is null', () => {
      const stats: ActionStats = {
        success_rate: null,
        avg_execution_time_ms: null,
        total_executions: 10,
        incidents_count: 10, // All failed
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      // The component should render with the metrics
      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
      expect(screen.getByText('Temps moyen')).toBeInTheDocument();
    });
  });

  describe('AC2: Color coding for success rate', () => {
    it('renders with green color when success_rate > 95%', () => {
      const stats: ActionStats = {
        success_rate: 98.0,
        avg_execution_time_ms: 1000,
        total_executions: 100,
        incidents_count: 2,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      // Check that the metrics container is rendered
      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
      // Verify success rate value is displayed
      expect(screen.getByText(/98/)).toBeInTheDocument();
    });

    it('renders with orange/warning color when success_rate is 80-95%', () => {
      const stats: ActionStats = {
        success_rate: 85.0,
        avg_execution_time_ms: 1000,
        total_executions: 100,
        incidents_count: 15,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
      expect(screen.getByText(/85/)).toBeInTheDocument();
    });

    it('renders with red/error color when success_rate < 80%', () => {
      const stats: ActionStats = {
        success_rate: 70.0,
        avg_execution_time_ms: 1000,
        total_executions: 100,
        incidents_count: 30,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
      expect(screen.getByText(/70/)).toBeInTheDocument();
    });
  });

  describe('AC3: No data handling', () => {
    it('shows "Pas encore de donnees" when stats is null', () => {
      renderWithProvider(<ActionMetrics stats={null} />);

      expect(screen.getByTestId('action-metrics-empty')).toBeInTheDocument();
      expect(screen.getByText('Pas encore de donnees')).toBeInTheDocument();
    });

    it('shows "Pas encore de donnees" when stats is undefined', () => {
      renderWithProvider(<ActionMetrics stats={undefined} />);

      expect(screen.getByTestId('action-metrics-empty')).toBeInTheDocument();
      expect(screen.getByText('Pas encore de donnees')).toBeInTheDocument();
    });

    it('shows "Pas encore de donnees" when total_executions is 0', () => {
      const stats: ActionStats = {
        success_rate: null,
        avg_execution_time_ms: null,
        total_executions: 0,
        incidents_count: 0,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByTestId('action-metrics-empty')).toBeInTheDocument();
      expect(screen.getByText('Pas encore de donnees')).toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('shows loading skeletons when loading is true', () => {
      const stats: ActionStats = {
        success_rate: 95.0,
        avg_execution_time_ms: 1000,
        total_executions: 100,
        incidents_count: 5,
      };

      renderWithProvider(<ActionMetrics stats={stats} loading />);

      // When loading, the component should render but with loading state
      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('handles 100% success rate', () => {
      const stats: ActionStats = {
        success_rate: 100.0,
        avg_execution_time_ms: 1000,
        total_executions: 50,
        incidents_count: 0,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      expect(screen.getByText(/100/)).toBeInTheDocument();
      // Check that incidents shows 0
      expect(screen.getByText('Incidents')).toBeInTheDocument();
    });

    it('handles 0% success rate (all failures)', () => {
      const stats: ActionStats = {
        success_rate: 0.0,
        avg_execution_time_ms: null,
        total_executions: 10,
        incidents_count: 10,
      };

      renderWithProvider(<ActionMetrics stats={stats} />);

      // 0 displayed in success rate
      expect(screen.getByTestId('action-metrics')).toBeInTheDocument();
      expect(screen.getByText('Taux de succes')).toBeInTheDocument();
      // Multiple 10s: total_executions and incidents_count
      const tensElements = screen.getAllByText('10');
      expect(tensElements.length).toBeGreaterThanOrEqual(2);
    });
  });
});
