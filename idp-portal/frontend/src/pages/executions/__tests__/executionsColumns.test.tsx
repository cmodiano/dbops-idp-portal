/**
 * Tests for executionsColumns.tsx (Story 26.4).
 *
 * Covers: getExecutionsColumns, formatDuration, formatDate, isRunning,
 * Actions column rendering, Utilisateur column, and full table render.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Table } from 'antd';
import {
  getExecutionsColumns,
  formatDuration,
  formatDate,
  isRunning,
  RUNNING_STATUSES,
} from '../executionsColumns';
import type { ExecutionColumnHandlers, ExecutionColumnState } from '../executionsColumns';
import type { ExecutionResponse } from '../../../types/api';
import type { User } from '../../../types/common';

// Mock executionRenderers
vi.mock('../../../utils/executionRenderers', () => ({
  renderStatusIndicator: vi.fn((status: string) => <span data-testid="status-indicator">{status}</span>),
  renderEngineIcon: vi.fn((engine: string) => <span data-testid="engine-icon">{engine}</span>),
  renderPlateformeIcon: vi.fn((name: string) => <span data-testid="plateforme-icon">{name}</span>),
}));

// --- Test fixtures ---

const testUser: User = {
  id: 1,
  username: 'test.user',
  display_name: 'Test User',
  profile: 'dba_applicatif',
  navigation_tabs: ['dashboard', 'catalog', 'executions'],
};

const baseExecution: ExecutionResponse = {
  id: 10,
  action_id: 1,
  action_name: 'Deploy DB',
  user_id: 1,
  user_display_name: 'Test User',
  environment: 'dev',
  parameters: null,
  status: 'COMPLETED',
  servicenow_change_id: null,
  started_at: '2026-02-07T10:00:00Z',
  completed_at: '2026-02-07T10:05:00Z',
  created_at: '2026-02-07T09:59:00Z',
  engine: 'oracle',
  platform: 'aap',
  item_type: 'action',
  integration_id: 1,
  integration_name: 'AAP Prod',
  integration_icon: null,
  parent_execution_id: null,
};

const submittedExecution: ExecutionResponse = {
  ...baseExecution,
  id: 11,
  status: 'SUBMITTED',
  started_at: null,
  completed_at: null,
};

const runningExecution: ExecutionResponse = {
  ...baseExecution,
  id: 12,
  status: 'RUNNING',
  completed_at: null,
};

const otherUserExecution: ExecutionResponse = {
  ...baseExecution,
  id: 13,
  user_id: 999,
  user_display_name: 'Other User',
  status: 'RUNNING',
  completed_at: null,
};

const defaultHandlers: ExecutionColumnHandlers = {
  onCancelExecution: vi.fn(),
  onRestartExecution: vi.fn(),
};

function makeState(overrides: Partial<ExecutionColumnState> = {}): ExecutionColumnState {
  return {
    activeScope: 'mine',
    sortField: 'created_at',
    sortOrder: 'descend',
    integrationIconsMap: null,
    user: testUser,
    canViewAll: false,
    canManage: false,
    cancellingId: null,
    restartLoadingId: null,
    ...overrides,
  };
}

// Helper: render a Table with the columns and return the columns array
function renderTable(
  executions: ExecutionResponse[],
  handlers: ExecutionColumnHandlers,
  state: ExecutionColumnState,
) {
  const columns = getExecutionsColumns(handlers, state);
  return render(
    <Table
      dataSource={executions}
      columns={columns}
      rowKey="id"
      pagination={false}
    />,
  );
}

describe('executionsColumns', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- 1. Column count for scope='mine' ---
  describe('getExecutionsColumns column count', () => {
    it('returns 8 columns for scope="mine" (no Utilisateur)', () => {
      const columns = getExecutionsColumns(defaultHandlers, makeState({ activeScope: 'mine' }));
      expect(columns).toHaveLength(8);
      const keys = columns!.map((c) => c.key);
      expect(keys).not.toContain('user_display_name');
    });

    // --- 2. Column count for scope='all' ---
    it('returns 9 columns for scope="all" (includes Utilisateur)', () => {
      const columns = getExecutionsColumns(defaultHandlers, makeState({ activeScope: 'all' }));
      expect(columns).toHaveLength(9);
      const keys = columns!.map((c) => c.key);
      expect(keys).toContain('user_display_name');
    });
  });

  // --- 3. formatDuration ---
  describe('formatDuration', () => {
    it('returns dash for null started_at', () => {
      expect(formatDuration(null, '2026-02-07T10:05:00Z')).toBe('\u2014');
    });

    it('returns dash for null completed_at', () => {
      expect(formatDuration('2026-02-07T10:00:00Z', null)).toBe('\u2014');
    });

    it('returns "0s" for identical timestamps', () => {
      expect(formatDuration('2026-02-07T10:00:00Z', '2026-02-07T10:00:00Z')).toBe('0s');
    });

    it('returns seconds for durations under 1 minute', () => {
      expect(formatDuration('2026-02-07T10:00:00Z', '2026-02-07T10:00:45Z')).toBe('45s');
    });

    it('returns minutes and seconds for durations over 1 minute', () => {
      expect(formatDuration('2026-02-07T10:00:00Z', '2026-02-07T10:05:30Z')).toBe('5m 30s');
    });

    it('returns minutes only when seconds are zero', () => {
      expect(formatDuration('2026-02-07T10:00:00Z', '2026-02-07T10:05:00Z')).toBe('5m');
    });
  });

  // --- 4. formatDate ---
  describe('formatDate', () => {
    it('returns dash for null date', () => {
      expect(formatDate(null)).toBe('\u2014');
    });

    it('formats a valid date in fr-FR locale', () => {
      const result = formatDate('2026-02-07T10:30:00Z');
      // Should contain day/month/year and time components
      expect(result).toBeTruthy();
      expect(result).not.toBe('\u2014');
      // Verify it contains numeric date parts (locale-dependent but should have digits)
      expect(result).toMatch(/\d{2}\/\d{2}\/\d{4}/);
    });
  });

  // --- 5. isRunning ---
  describe('isRunning', () => {
    it('returns true for RUNNING', () => {
      expect(isRunning('RUNNING')).toBe(true);
    });

    it('returns true for SUBMITTED', () => {
      expect(isRunning('SUBMITTED')).toBe(true);
    });

    it('returns true for PENDING_APPROVAL', () => {
      expect(isRunning('PENDING_APPROVAL')).toBe(true);
    });

    it('returns false for COMPLETED', () => {
      expect(isRunning('COMPLETED')).toBe(false);
    });

    it('returns false for FAILED', () => {
      expect(isRunning('FAILED')).toBe(false);
    });

    it('returns false for CANCELLED', () => {
      expect(isRunning('CANCELLED')).toBe(false);
    });

    it('RUNNING_STATUSES contains exactly 3 statuses', () => {
      expect(RUNNING_STATUSES).toEqual(['RUNNING', 'SUBMITTED', 'PENDING_APPROVAL']);
    });
  });

  // --- 6. Actions column: restart button for user's own execution ---
  describe('Actions column', () => {
    it('renders restart button for user\'s own execution', () => {
      renderTable([baseExecution], defaultHandlers, makeState());
      expect(screen.getByRole('button', { name: /relancer/i })).toBeInTheDocument();
    });

    // --- 7. Cancel button for SUBMITTED/RUNNING ---
    it('renders cancel button for SUBMITTED execution owned by user', () => {
      renderTable([submittedExecution], defaultHandlers, makeState());
      expect(screen.getByRole('button', { name: /annuler/i })).toBeInTheDocument();
    });

    it('renders cancel button for RUNNING execution owned by user', () => {
      renderTable([runningExecution], defaultHandlers, makeState());
      expect(screen.getByRole('button', { name: /annuler/i })).toBeInTheDocument();
    });

    it('does not render cancel button for COMPLETED execution', () => {
      renderTable([baseExecution], defaultHandlers, makeState());
      expect(screen.queryByRole('button', { name: /annuler/i })).not.toBeInTheDocument();
    });

    // --- 8. Loading state when cancellingId matches ---
    it('shows loading state when cancellingId matches execution id', () => {
      renderTable(
        [submittedExecution],
        defaultHandlers,
        makeState({ cancellingId: submittedExecution.id }),
      );
      const cancelBtn = screen.getByRole('button', { name: /annuler/i });
      // Ant Design sets aria-busy or adds a loading spinner
      // The button should exist and be in loading state (has .ant-btn-loading class)
      expect(cancelBtn.closest('.ant-btn-loading') || cancelBtn.classList.contains('ant-btn-loading')).toBeTruthy();
    });

    // --- 9. Loading state when restartLoadingId matches ---
    it('shows loading state when restartLoadingId matches execution id', () => {
      renderTable(
        [baseExecution],
        defaultHandlers,
        makeState({ restartLoadingId: baseExecution.id }),
      );
      const restartBtn = screen.getByRole('button', { name: /relancer/i });
      expect(restartBtn.closest('.ant-btn-loading') || restartBtn.classList.contains('ant-btn-loading')).toBeTruthy();
    });

    // --- 10. Click handlers call correct callbacks ---
    it('calls onRestartExecution when restart button is clicked', async () => {
      const handlers: ExecutionColumnHandlers = {
        onCancelExecution: vi.fn(),
        onRestartExecution: vi.fn(),
      };
      renderTable([baseExecution], handlers, makeState());

      const user = userEvent.setup();
      const restartBtn = screen.getByRole('button', { name: /relancer/i });
      await user.click(restartBtn);

      expect(handlers.onRestartExecution).toHaveBeenCalledWith(baseExecution);
      expect(handlers.onCancelExecution).not.toHaveBeenCalled();
    });

    it('calls onCancelExecution when cancel button is clicked', async () => {
      const handlers: ExecutionColumnHandlers = {
        onCancelExecution: vi.fn(),
        onRestartExecution: vi.fn(),
      };
      renderTable([submittedExecution], handlers, makeState());

      const user = userEvent.setup();
      const cancelBtn = screen.getByRole('button', { name: /annuler/i });
      await user.click(cancelBtn);

      expect(handlers.onCancelExecution).toHaveBeenCalledWith(submittedExecution.id);
      expect(handlers.onRestartExecution).not.toHaveBeenCalled();
    });

    it('does not render any buttons for another user\'s execution when not admin', () => {
      renderTable([otherUserExecution], defaultHandlers, makeState({ canViewAll: false }));
      expect(screen.queryByRole('button', { name: /relancer/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /annuler/i })).not.toBeInTheDocument();
    });

    it('renders buttons for another user\'s execution when canManage is true', () => {
      renderTable([otherUserExecution], defaultHandlers, makeState({ canManage: true }));
      expect(screen.getByRole('button', { name: /relancer/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /annuler/i })).toBeInTheDocument();
    });
  });

  // --- 11. Full table render test ---
  describe('table render integration', () => {
    it('renders all expected column headers for scope="mine"', () => {
      renderTable([baseExecution], defaultHandlers, makeState({ activeScope: 'mine' }));

      expect(screen.getByText('Statut')).toBeInTheDocument();
      expect(screen.getByText('Action')).toBeInTheDocument();
      expect(screen.getByText('Technologie')).toBeInTheDocument();
      expect(screen.getByText('Plateforme')).toBeInTheDocument();
      expect(screen.getByText('Environnement')).toBeInTheDocument();
      expect(screen.getByText('Date')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
      expect(screen.queryByText('Utilisateur')).not.toBeInTheDocument();
    });

    it('renders Utilisateur column header for scope="all"', () => {
      renderTable([baseExecution], defaultHandlers, makeState({ activeScope: 'all' }));

      expect(screen.getByText('Utilisateur')).toBeInTheDocument();
    });

    it('renders execution data in table cells', () => {
      renderTable([baseExecution], defaultHandlers, makeState());

      // Action name
      expect(screen.getByText('Deploy DB')).toBeInTheDocument();
      // Environment (uppercased)
      expect(screen.getByText('DEV')).toBeInTheDocument();
      // Duration: 5 minutes
      expect(screen.getByText('5m')).toBeInTheDocument();
      // Status indicator (mocked)
      expect(screen.getByTestId('status-indicator')).toBeInTheDocument();
    });

    it('renders action fallback when action_name is null', () => {
      const noNameExec: ExecutionResponse = {
        ...baseExecution,
        action_name: null,
      };
      renderTable([noNameExec], defaultHandlers, makeState());
      expect(screen.getByText('Action #1')).toBeInTheDocument();
    });
  });

  // --- 12. Utilisateur column shows "Utilisateur inconnu" for null name ---
  describe('Utilisateur column', () => {
    it('shows "Utilisateur inconnu" when user_display_name is null', () => {
      const nullNameExec: ExecutionResponse = {
        ...baseExecution,
        user_display_name: null,
      };
      renderTable([nullNameExec], defaultHandlers, makeState({ activeScope: 'all' }));
      expect(screen.getByText('Utilisateur inconnu')).toBeInTheDocument();
    });

    it('shows user display name when available', () => {
      renderTable([baseExecution], defaultHandlers, makeState({ activeScope: 'all' }));
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
  });
});
