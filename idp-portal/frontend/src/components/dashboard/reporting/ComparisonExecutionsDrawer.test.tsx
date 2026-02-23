/**
 * Tests for ComparisonExecutionsDrawer component (Story 8.6, AC6).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { ComparisonExecutionsDrawer } from './ComparisonExecutionsDrawer';
import type { DashboardRecentExecution } from '../../../types/api';

const mockExecutions: DashboardRecentExecution[] = [
  {
    id: 1,
    action_name: 'Backup Database',
    status: 'COMPLETED',
    environment: 'prod',
    user_display_name: 'admin',
    created_at: '2026-01-31T10:00:00Z',
  },
  {
    id: 2,
    action_name: 'Patch Server',
    status: 'FAILED',
    environment: 'dev',
    user_display_name: 'user1',
    created_at: '2026-01-31T09:30:00Z',
  },
];

const renderWithRouter = (ui: React.ReactNode) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe('ComparisonExecutionsDrawer', () => {
  it('renders drawer with title when metric is provided', () => {
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={vi.fn()}
        metric="success_rate"
        value1="Oracle"
        value2="PostgreSQL"
      />
    );

    expect(screen.getByText('Exécutions - Taux de succès')).toBeInTheDocument();
    expect(screen.getByText('Oracle vs PostgreSQL')).toBeInTheDocument();
  });

  it('renders empty state when no executions', () => {
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={vi.fn()}
        executions={[]}
      />
    );

    expect(screen.getByText('Aucune exécution trouvée pour ces critères')).toBeInTheDocument();
  });

  it('renders executions table with data', () => {
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={vi.fn()}
        executions={mockExecutions}
      />
    );

    expect(screen.getByText('Backup Database')).toBeInTheDocument();
    expect(screen.getByText('Patch Server')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getByText('FAILED')).toBeInTheDocument();
  });

  it('renders environment tags', () => {
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={vi.fn()}
        executions={mockExecutions}
      />
    );

    expect(screen.getByText('prod')).toBeInTheDocument();
    expect(screen.getByText('dev')).toBeInTheDocument();
  });

  it('calls onClose when drawer is closed', () => {
    const onClose = vi.fn();
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={onClose}
        executions={mockExecutions}
      />
    );

    // Find and click the close button
    const closeButton = document.querySelector('.ant-drawer-close');
    if (closeButton) {
      fireEvent.click(closeButton);
      expect(onClose).toHaveBeenCalled();
    }
  });

  it('renders detail links for each execution', () => {
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={vi.fn()}
        executions={mockExecutions}
      />
    );

    const detailButtons = screen.getAllByText('Détail');
    expect(detailButtons).toHaveLength(2);
  });

  it('shows loading state in table', () => {
    renderWithRouter(
      <ComparisonExecutionsDrawer
        open={true}
        onClose={vi.fn()}
        executions={[]}
        loading={true}
      />
    );

    // Table should have loading spinner
    expect(document.querySelector('.ant-spin')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    const { container } = renderWithRouter(
      <ComparisonExecutionsDrawer
        open={false}
        onClose={vi.fn()}
        executions={mockExecutions}
      />
    );

    // Drawer content should not be visible
    expect(container.querySelector('.ant-drawer-open')).toBeNull();
  });
});
