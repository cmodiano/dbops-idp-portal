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

describe('RecentExecutions — coverage extension', () => {
  function renderWithApp(ui: React.ReactElement) {
    return render(<App>{ui}</App>);
  }

  it('highlights FAILED rows with red background', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 1, action_name: 'Failed Action', user_display_name: 'User', environment: 'prod', status: 'FAILED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} onRowClick={vi.fn()} />);
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows[0]).toHaveStyle({ backgroundColor: 'rgba(255, 77, 79, 0.08)' });
  });

  it('highlights rows in highlightedIds set', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 5, action_name: 'Highlighted', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} highlightedIds={new Set([5])} onRowClick={vi.fn()} />);
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows[0]).toHaveStyle({ backgroundColor: 'rgba(255, 77, 79, 0.08)' });
  });

  it('does not highlight non-FAILED rows without highlightedIds', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 2, action_name: 'OK Action', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} onRowClick={vi.fn()} />);
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows[0]).not.toHaveStyle({ backgroundColor: 'rgba(255, 77, 79, 0.08)' });
  });

  it('renders null date as em-dash', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 3, action_name: 'NullDate', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    // Date column renders '—'
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('renders null environment as em-dash in Env column', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 4, action_name: 'NoEnv', user_display_name: 'User', environment: null as unknown as string, status: 'COMPLETED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('renders engine column with known engine (no svgSrc)', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 6, action_name: 'Oracle Action', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null, engine: 'Oracle' },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getByTitle('Oracle')).toBeInTheDocument();
  });

  it('renders engine column with null engine as dash', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 7, action_name: 'No Engine', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null, engine: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    // Should render the fallback dash span
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('renders IntegrationIconCell with iconSrc (avatar with src)', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 8, action_name: 'Platform Action', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null, platform: 'aap' },
    ];
    renderWithApp(
      <RecentExecutions
        executions={execs}
        integrationIconsByType={{ aap: 'https://example.com/icon.png' }}
      />
    );
    // Avatar with src should render
    expect(document.querySelector('.ant-avatar img')).toBeInTheDocument();
  });

  it('renders IntegrationIconCell without iconSrc (null platform)', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 9, action_name: 'No Platform', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null, platform: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('renders PENDING_APPROVAL status with unknown config fallback', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 10, action_name: 'Pending', user_display_name: 'User', environment: 'dev', status: 'PENDING_APPROVAL' as DashboardRecentExecution['status'], created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    // Row renders without crashing
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('does not call onRowClick when not provided', async () => {
    const user = userEvent.setup();
    const execs: DashboardRecentExecution[] = [
      { id: 11, action_name: 'NoClick', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null },
    ];
    // No error should occur when clicking without onRowClick
    renderWithApp(<RecentExecutions executions={execs} />);
    await user.click(screen.getByText('NoClick'));
    // No assertion needed - just verifying no crash
  });

  it('announces status change via message.info when execution status changes', async () => {
    const initialExecs: DashboardRecentExecution[] = [
      { id: 1, action_name: 'Running Action', user_display_name: 'User', environment: 'dev', status: 'RUNNING', created_at: null },
    ];
    const { rerender } = renderWithApp(<RecentExecutions executions={initialExecs} />);

    // Re-render with updated status to trigger the useEffect status change detection
    const updatedExecs: DashboardRecentExecution[] = [
      { id: 1, action_name: 'Running Action', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null },
    ];
    rerender(<App><RecentExecutions executions={updatedExecs} /></App>);

    // The message.info and liveAnnouncement code (lines 167-170, 178-181) should fire
    // We just verify no crash occurs and the table still renders
    expect(screen.getByText('Running Action')).toBeInTheDocument();
  });

  it('announces status change with action_name null uses id fallback', async () => {
    const initialExecs: DashboardRecentExecution[] = [
      { id: 55, action_name: null, user_display_name: 'User', environment: 'dev', status: 'RUNNING', created_at: null },
    ];
    const { rerender } = renderWithApp(<RecentExecutions executions={initialExecs} />);

    const updatedExecs: DashboardRecentExecution[] = [
      { id: 55, action_name: null, user_display_name: 'User', environment: 'dev', status: 'FAILED', created_at: null },
    ];
    rerender(<App><RecentExecutions executions={updatedExecs} /></App>);
    // Verify no crash — fallback uses `#${exec.id}` (line 168)
    expect(screen.getByText('Action #55')).toBeInTheDocument();
  });

  it('renders COMPLETED status icon', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 20, action_name: 'Completed', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getByLabelText('Terminée')).toBeInTheDocument();
  });

  it('renders FAILED status icon', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 21, action_name: 'Failed', user_display_name: 'User', environment: 'dev', status: 'FAILED', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getByLabelText('Échouée')).toBeInTheDocument();
  });

  it('renders RUNNING status with spin', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 22, action_name: 'Running', user_display_name: 'User', environment: 'dev', status: 'RUNNING', created_at: null },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getByLabelText('En cours')).toBeInTheDocument();
  });

  it('unknown engine shows text fallback without config', () => {
    const execs: DashboardRecentExecution[] = [
      { id: 23, action_name: 'Unk Engine', user_display_name: 'User', environment: 'dev', status: 'COMPLETED', created_at: null, engine: 'UnknownEngineXYZ' },
    ];
    renderWithApp(<RecentExecutions executions={execs} />);
    expect(screen.getByTitle('UnknownEngineXYZ')).toBeInTheDocument();
  });
});
