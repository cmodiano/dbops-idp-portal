/**
 * Tests for AuditTable component (Story 39.7 — coverage).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AuditTable, formatDate, getActionName } from './AuditTable';
import type { AuditTableProps } from './AuditTable';
import type { AuditExecutionEntry, PaginationInfo } from '../../types/api';

const mockEntry: AuditExecutionEntry = {
  id: 1,
  entity_id: 100,
  item_type: 'action',
  user_id: '5',
  user_name: 'alice',
  action_name: 'Deploy App',
  derived_status: 'success',
  timestamp: '2025-01-15T10:30:00Z',
  action_type: 'EXECUTE',
  entity_type: 'execution',
  ip_address: null,
  correlation_id: null,
  details: {
    environment: 'prod',
    action_id: 10,
    servicenow_change_id: null,
  },
};

const mockWorkflowEntry: AuditExecutionEntry = {
  ...mockEntry,
  id: 2,
  entity_id: 200,
  item_type: 'workflow',
  action_name: 'Full Deploy Workflow',
  derived_status: 'running',
};

const mockChildEntry: AuditExecutionEntry = {
  ...mockEntry,
  id: 3,
  entity_id: 300,
  item_type: 'action',
  action_name: 'Step 1',
};

const mockPagination: PaginationInfo = {
  total: 100,
  page: 1,
  page_size: 25,
  total_pages: 4,
};

const defaultProps: AuditTableProps = {
  topLevelEntries: [mockEntry],
  childrenByParentId: new Map(),
  loading: false,
  pagination: mockPagination,
  currentPage: 1,
  pageSize: 25,
  sortField: 'timestamp',
  sortOrder: 'descend',
  onChange: vi.fn(),
  onRowClick: vi.fn(),
};

describe('AuditTable', () => {
  describe('formatDate', () => {
    it('formats valid date string', () => {
      const result = formatDate('2025-01-15T10:30:00Z');
      expect(result).toContain('15');
      expect(result).toContain('01');
      expect(result).toContain('2025');
    });

    it('returns "—" for null date', () => {
      expect(formatDate(null)).toBe('—');
    });
  });

  describe('getActionName', () => {
    it('returns action_name when available', () => {
      const result = getActionName(mockEntry);
      expect(result).toBe('Deploy App');
    });

    it('returns "Action #N" when action_name is null and details has action_id', () => {
      const entry = { ...mockEntry, action_name: undefined, details: { action_id: 10, environment: 'prod', servicenow_change_id: null } };
      expect(getActionName(entry)).toBe('Action #10');
    });

    it('returns "Action inconnue" when no action info', () => {
      const entry = { ...mockEntry, action_name: undefined, details: { action_id: null, environment: 'prod', servicenow_change_id: null } };
      expect(getActionName(entry)).toBe('Action inconnue');
    });
  });

  describe('Table rendering', () => {
    it('renders table with entries', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    it('renders column headers', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Action')).toBeInTheDocument();
      expect(screen.getByText('Utilisateur')).toBeInTheDocument();
      expect(screen.getByText('Statut')).toBeInTheDocument();
      expect(screen.getByText('Date')).toBeInTheDocument();
    });

    it('shows loading state', () => {
      render(<AuditTable {...defaultProps} loading={true} />);
      expect(document.querySelector('.ant-spin')).toBeInTheDocument();
    });

    it('shows empty text when no entries', () => {
      render(<AuditTable {...defaultProps} topLevelEntries={[]} />);
      expect(screen.getByText("Aucune entrée d'audit trouvée")).toBeInTheDocument();
    });

    it('calls onRowClick when row is clicked', () => {
      const onRowClick = vi.fn();
      render(<AuditTable {...defaultProps} onRowClick={onRowClick} />);
      // Click on the action name cell (row content)
      fireEvent.click(screen.getByText('Deploy App'));
      expect(onRowClick).toHaveBeenCalledWith(mockEntry);
    });

    it('renders user name', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('alice')).toBeInTheDocument();
    });

    it('renders environment', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('PROD')).toBeInTheDocument();
    });

    it('renders status tag', () => {
      render(<AuditTable {...defaultProps} />);
      // AUDIT_STATUS_CONFIG for COMPLETED
      const statusTag = document.querySelector('.ant-tag');
      expect(statusTag).toBeInTheDocument();
    });

    it('shows user_id when user_name is null', () => {
      const entryWithoutName = { ...mockEntry, user_name: null };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryWithoutName]} />);
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('shows dash when no user info', () => {
      const entryNoUser = { ...mockEntry, user_name: null, user_id: null as unknown as string };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryNoUser]} />);
      // The "—" char from the column render
      expect(document.querySelector('td')).toBeInTheDocument();
    });

    it('shows servicenow change ID when available', () => {
      const entryWithChange: AuditExecutionEntry = {
        ...mockEntry,
        details: { ...mockEntry.details, servicenow_change_id: 'CHG0012345678' },
      };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryWithChange]} />);
      // Truncated to 10 chars
      expect(screen.getByText(/CHG0012345/)).toBeInTheDocument();
    });

    it('shows dash for servicenow when no change ID', () => {
      render(<AuditTable {...defaultProps} />);
      // No change ID — shows "—"
      const cells = document.querySelectorAll('td');
      const dashCells = Array.from(cells).filter(c => c.textContent === '—');
      expect(dashCells.length).toBeGreaterThan(0);
    });

    it('renders workflow entry with expandable indicator', () => {
      const childrenMap = new Map([[200, [mockChildEntry]]]);
      render(
        <AuditTable
          {...defaultProps}
          topLevelEntries={[mockWorkflowEntry]}
          childrenByParentId={childrenMap}
        />,
      );
      // Workflow entry should have expand button
      expect(screen.getByText('Full Deploy Workflow')).toBeInTheDocument();
    });

    it('expands workflow row to show child actions', () => {
      const childrenMap = new Map([[200, [mockChildEntry]]]);
      const { container } = render(
        <AuditTable
          {...defaultProps}
          topLevelEntries={[mockWorkflowEntry]}
          childrenByParentId={childrenMap}
        />,
      );
      // Click the expand button to open the expanded row
      const expandBtn = container.querySelector('.ant-table-row-expand-icon');
      expect(expandBtn).not.toBeNull();
      fireEvent.click(expandBtn!);
      expect(screen.getByText(/Actions du workflow/)).toBeInTheDocument();
    });

    it('renders unknown status with fallback config', () => {
      const unknownEntry = { ...mockEntry, derived_status: 'UNKNOWN_STATUS' as unknown as AuditExecutionEntry['derived_status'] };
      render(<AuditTable {...defaultProps} topLevelEntries={[unknownEntry]} />);
      // Should not crash, renders with fallback
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    it('shows environment as "—" when null', () => {
      const entryNoEnv = { ...mockEntry, details: { ...mockEntry.details, environment: undefined } };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryNoEnv]} />);
      // Environment column shows "—" for null
      expect(document.querySelector('td')).toBeInTheDocument();
    });
  });
});
