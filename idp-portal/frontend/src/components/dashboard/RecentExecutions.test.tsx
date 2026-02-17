/**
 * Tests for RecentExecutions (Story 5.1, Task 5.2).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { RecentExecutions } from './RecentExecutions';
import type { DashboardRecentExecution } from '../../types/api';

// Wrapper to provide App context for useApp() hook
function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

const mockExecutions: DashboardRecentExecution[] = [
  {
    id: 1,
    action_name: 'Create PDB',
    user_display_name: 'Alice DBA',
    environment: 'dev',
    status: 'COMPLETED',
    created_at: '2026-01-30T10:00:00Z',
  },
  {
    id: 2,
    action_name: 'Drop PDB',
    user_display_name: 'Bob Ops',
    environment: 'prod',
    status: 'FAILED',
    created_at: '2026-01-30T09:00:00Z',
  },
  {
    id: 3,
    action_name: 'Refresh Stats',
    user_display_name: 'Charlie Admin',
    environment: 'staging',
    status: 'RUNNING',
    created_at: '2026-01-30T08:00:00Z',
  },
];

describe('RecentExecutions', () => {
  it('renders table with all columns', () => {
    renderWithApp(<RecentExecutions executions={mockExecutions} />);

    // Check column headers (status is icon-only, no "Statut" header)
    expect(screen.getByText('Action')).toBeInTheDocument();
    expect(screen.getByText('Utilisateur')).toBeInTheDocument();
    expect(screen.getByText('Env')).toBeInTheDocument();
    expect(screen.getByText('Date')).toBeInTheDocument();
  });

  it('renders execution data correctly', () => {
    renderWithApp(<RecentExecutions executions={mockExecutions} />);

    // Check action names
    expect(screen.getByText('Create PDB')).toBeInTheDocument();
    expect(screen.getByText('Drop PDB')).toBeInTheDocument();
    expect(screen.getByText('Refresh Stats')).toBeInTheDocument();

    // Check users
    expect(screen.getByText('Alice DBA')).toBeInTheDocument();
    expect(screen.getByText('Bob Ops')).toBeInTheDocument();
    expect(screen.getByText('Charlie Admin')).toBeInTheDocument();

    // Check environments (uppercased)
    expect(screen.getByText('DEV')).toBeInTheDocument();
    expect(screen.getByText('PROD')).toBeInTheDocument();
    expect(screen.getByText('STAGING')).toBeInTheDocument();
  });

  it('renders status icons with correct aria-labels', () => {
    renderWithApp(<RecentExecutions executions={mockExecutions} />);

    expect(screen.getByLabelText('Terminée')).toBeInTheDocument();
    expect(screen.getByLabelText('Échouée')).toBeInTheDocument();
    expect(screen.getByLabelText('En cours')).toBeInTheDocument();
  });

  it('shows empty state when no executions', () => {
    renderWithApp(<RecentExecutions executions={[]} />);

    expect(screen.getByText('Aucune exécution récente')).toBeInTheDocument();
  });

  it('shows skeleton rows when loading', () => {
    renderWithApp(<RecentExecutions executions={[]} loading />);

    // Should have skeleton elements
    expect(document.querySelectorAll('.ant-skeleton').length).toBeGreaterThan(0);
    // Should not show empty message when loading
    expect(screen.queryByText('Aucune exécution récente')).not.toBeInTheDocument();
  });

  it('calls onRowClick when row is clicked', async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();

    renderWithApp(<RecentExecutions executions={mockExecutions} onRowClick={onRowClick} />);

    // Click on first row (by action name)
    await user.click(screen.getByText('Create PDB'));

    expect(onRowClick).toHaveBeenCalledTimes(1);
    expect(onRowClick).toHaveBeenCalledWith(mockExecutions[0]);
  });

  it('does not have pointer cursor when onRowClick is not provided', () => {
    renderWithApp(<RecentExecutions executions={mockExecutions} />);

    const rows = document.querySelectorAll('.ant-table-row');
    rows.forEach((row) => {
      expect(row).not.toHaveStyle({ cursor: 'pointer' });
    });
  });

  it('has pointer cursor when onRowClick is provided', () => {
    const onRowClick = vi.fn();
    renderWithApp(<RecentExecutions executions={mockExecutions} onRowClick={onRowClick} />);

    const rows = document.querySelectorAll('.ant-table-row');
    rows.forEach((row) => {
      expect(row).toHaveStyle({ cursor: 'pointer' });
    });
  });

  it('handles null action_name gracefully', () => {
    const execWithNullName: DashboardRecentExecution[] = [
      {
        id: 99,
        action_name: null,
        user_display_name: 'Test User',
        environment: 'dev',
        status: 'COMPLETED',
        created_at: '2026-01-30T10:00:00Z',
      },
    ];

    renderWithApp(<RecentExecutions executions={execWithNullName} />);

    expect(screen.getByText('Action #99')).toBeInTheDocument();
  });
});
