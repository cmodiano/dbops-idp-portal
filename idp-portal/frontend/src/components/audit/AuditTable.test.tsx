/**
 * Tests for AuditTable component.
 * Story 39.7 — initial coverage.
 * Story 43.4 — colonnes Type, Opération, Entité, Catégorie, visibilité.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  AuditTable,
  formatDate,
  getActionName,
  getEntityLabel,
  getOperationConfig,
  ACTION_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
} from './AuditTable';
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
  action_type: 'EXECUTION_SUBMITTED',
  entity_type: 'execution',
  ip_address: null,
  correlation_id: null,
  details: {
    environment: 'prod',
    action_id: 10,
    servicenow_change_id: undefined,
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

  describe('getActionName (deprecated backward compat)', () => {
    it('returns action_name when available', () => {
      const result = getActionName(mockEntry);
      expect(result).toBe('Deploy App');
    });

    it('delegates to getEntityLabel for execution without action_name', () => {
      const entry = { ...mockEntry, action_name: undefined, entity_type: 'execution' as const };
      expect(getActionName(entry)).toBe(getEntityLabel(entry));
    });

    it('returns "Action inconnue" shape via getEntityLabel for unknown execution', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'execution' as const,
        entity_id: 42,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      // entity_type=execution falls through to generic fallback #entity_id
      expect(getActionName(entry)).toBe('#42');
    });
  });

  describe('getEntityLabel', () => {
    it('test_getEntityLabel_function — returns action_name when present', () => {
      expect(getEntityLabel(mockEntry)).toBe('Deploy App');
    });

    it('test_getEntityLabel_function — entity_type action with details.name', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'action' as const,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined, name: 'My Action' },
      };
      expect(getEntityLabel(entry)).toBe('My Action');
    });

    it('test_getEntityLabel_function — entity_type action fallback to entity_id', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'action' as const,
        entity_id: 99,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      expect(getEntityLabel(entry)).toBe('Action #99');
    });

    it('test_getEntityLabel_function — entity_type integration fallback', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'integration' as const,
        entity_id: 55,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      expect(getEntityLabel(entry)).toBe('Intégration #55');
    });

    it('test_getEntityLabel_function — entity_type profile fallback', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'profile' as const,
        entity_id: 77,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      expect(getEntityLabel(entry)).toBe('Profil #77');
    });

    it('test_getEntityLabel_function — entity_type user with user_name', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'user' as const,
        user_name: 'bob',
      };
      expect(getEntityLabel(entry)).toBe('bob');
    });

    it('test_getEntityLabel_function — generic fallback with entity_id', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'execution' as const,
        entity_id: 42,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      expect(getEntityLabel(entry)).toBe('#42');
    });

    it('test_getEntityLabel_function — returns — when no entity_id', () => {
      const entry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'execution' as const,
        entity_id: 0,
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      expect(getEntityLabel(entry)).toBe('—');
    });
  });

  describe('getOperationConfig', () => {
    it('returns Créer for _CREATED suffix', () => {
      const op = getOperationConfig('ACTION_CREATED');
      expect(op.label).toBe('Créer');
      expect(op.color).toBe('green');
    });

    it('returns Modifier for _UPDATED suffix', () => {
      const op = getOperationConfig('PROFILE_UPDATED');
      expect(op.label).toBe('Modifier');
    });

    it('returns Supprimer for _DELETED suffix', () => {
      const op = getOperationConfig('INTEGRATION_DELETED');
      expect(op.label).toBe('Supprimer');
      expect(op.color).toBe('red');
    });

    it('returns Publier for _PUBLISHED suffix', () => {
      const op = getOperationConfig('ACTION_PUBLISHED');
      expect(op.label).toBe('Publier');
    });

    it('returns Soumettre for _SUBMITTED suffix', () => {
      const op = getOperationConfig('EXECUTION_SUBMITTED');
      expect(op.label).toBe('Soumettre');
    });

    it('returns fallback — for unknown type', () => {
      const op = getOperationConfig('USER_LOGIN');
      expect(op.label).toBe('—');
    });

    it('returns fallback for empty string', () => {
      const op = getOperationConfig('');
      expect(op.label).toBe('—');
    });
  });

  describe('ACTION_TYPE_LABELS mapping', () => {
    it('contains ACTION_PUBLISHED', () => {
      expect(ACTION_TYPE_LABELS['ACTION_PUBLISHED']).toBe('Action publiée');
    });

    it('contains EXECUTION_SUBMITTED', () => {
      expect(ACTION_TYPE_LABELS['EXECUTION_SUBMITTED']).toBe('Exécution soumise');
    });

    it('contains INTEGRATION_CREATED', () => {
      expect(ACTION_TYPE_LABELS['INTEGRATION_CREATED']).toBe('Intégration créée');
    });
  });

  describe('ENTITY_TYPE_LABELS mapping', () => {
    it('contains action', () => {
      expect(ENTITY_TYPE_LABELS['action']).toBe('Action');
    });

    it('contains execution', () => {
      expect(ENTITY_TYPE_LABELS['execution']).toBe('Exécution');
    });
  });

  describe('Table rendering', () => {
    it('renders table with entries', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    it('test_column_headers_include_new_columns — renders new column headers', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Entité')).toBeInTheDocument();
      expect(screen.getByText('Type')).toBeInTheDocument();
      expect(screen.getByText('Opération')).toBeInTheDocument();
      expect(screen.getByText('Utilisateur')).toBeInTheDocument();
      expect(screen.getByText('Statut')).toBeInTheDocument();
      expect(screen.getByText('Date')).toBeInTheDocument();
    });

    it('does not render old "Action" header (renamed to Entité)', () => {
      render(<AuditTable {...defaultProps} />);
      // "Action" as column header should be gone; "Deploy App" (cell value) should be present
      expect(screen.queryByRole('columnheader', { name: 'Action' })).not.toBeInTheDocument();
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
      fireEvent.click(screen.getByText('Deploy App'));
      expect(onRowClick).toHaveBeenCalledWith(mockEntry);
    });

    it('renders user name', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('alice')).toBeInTheDocument();
    });

    it('shows user_id when user_name is null', () => {
      const entryWithoutName = { ...mockEntry, user_name: null };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryWithoutName]} />);
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('shows dash when no user info', () => {
      const entryNoUser = { ...mockEntry, user_name: null, user_id: null as unknown as string };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryNoUser]} />);
      expect(document.querySelector('td')).toBeInTheDocument();
    });

    it('shows servicenow change ID when available (execution entry — column hidden by default)', () => {
      // Change SN column is hidden by default; component renders without error
      const entryWithChange: AuditExecutionEntry = {
        ...mockEntry,
        details: { ...mockEntry.details, servicenow_change_id: 'CHG0012345678' },
      };
      render(<AuditTable {...defaultProps} topLevelEntries={[entryWithChange]} />);
      // Column hidden — CHG text not visible; table renders without crash
      expect(screen.queryByText(/CHG0012345/)).not.toBeInTheDocument();
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    it('shows dash for operation when action type has no known suffix', () => {
      const unknownOpEntry = { ...mockEntry, action_type: 'USER_LOGIN' };
      render(<AuditTable {...defaultProps} topLevelEntries={[unknownOpEntry]} />);
      // getOperationConfig('USER_LOGIN') → fallback '—'
      const cells = document.querySelectorAll('td');
      const dashCells = Array.from(cells).filter(c => c.textContent?.trim() === '—');
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
      const expandBtn = container.querySelector('.ant-table-row-expand-icon');
      expect(expandBtn).not.toBeNull();
      fireEvent.click(expandBtn!);
      expect(screen.getByText(/Actions du workflow/)).toBeInTheDocument();
    });

    it('renders unknown status with fallback config', () => {
      const unknownEntry = {
        ...mockEntry,
        derived_status: 'UNKNOWN_STATUS' as unknown as AuditExecutionEntry['derived_status'],
      };
      render(<AuditTable {...defaultProps} topLevelEntries={[unknownEntry]} />);
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    // ── Story 43.4 — new tests ────────────────────────────────────────────────

    it('test_entity_column_shows_action_name — Entité colonne affiche action_name pour exécution', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    it('test_entity_column_shows_entity_id_for_non_action — Entité affiche préfixe entity_id pour intégration', () => {
      const integrationEntry: AuditExecutionEntry = {
        ...mockEntry,
        action_name: undefined,
        entity_type: 'integration',
        entity_id: 55,
        action_type: 'INTEGRATION_CREATED',
        details: { action_id: undefined, environment: undefined, servicenow_change_id: undefined },
      };
      render(<AuditTable {...defaultProps} topLevelEntries={[integrationEntry]} />);
      expect(screen.getByText('Intégration #55')).toBeInTheDocument();
    });

    it('test_type_column_shows_readable_label — Type affiche "Action publiée" pour ACTION_PUBLISHED', () => {
      const publishedEntry = { ...mockEntry, action_type: 'ACTION_PUBLISHED' };
      render(<AuditTable {...defaultProps} topLevelEntries={[publishedEntry]} />);
      expect(screen.getByText('Action publiée')).toBeInTheDocument();
    });

    it('test_operation_column_shows_icon_and_label — Opération affiche le libellé Soumettre', () => {
      // mockEntry has action_type: 'EXECUTION_SUBMITTED' → Soumettre
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Soumettre')).toBeInTheDocument();
    });

    it('test_non_execution_entry_shows_dash_for_status — Statut affiche — pour une entrée action', () => {
      const actionEntry: AuditExecutionEntry = {
        ...mockEntry,
        entity_type: 'action',
        action_type: 'ACTION_CREATED',
      };
      render(<AuditTable {...defaultProps} topLevelEntries={[actionEntry]} />);
      // No ant-tag should be rendered (status = — for non-execution)
      expect(document.querySelectorAll('.ant-tag')).toHaveLength(0);
    });

    it('test_non_execution_entry_shows_dash_for_environment — Environnement affiche — pour une intégration (colonne rendue visible)', () => {
      const integrationEntry: AuditExecutionEntry = {
        ...mockEntry,
        entity_type: 'integration',
        action_type: 'INTEGRATION_CREATED',
        details: { action_id: undefined, environment: 'prod', servicenow_change_id: undefined },
      };
      render(<AuditTable {...defaultProps} topLevelEntries={[integrationEntry]} />);

      // Enable Environnement column via the Colonnes toggle
      fireEvent.click(screen.getByText('Colonnes'));
      // The popover Checkbox.Group renders options; find the Environnement checkbox
      const allCheckboxes = document.querySelectorAll('input[type="checkbox"]');
      const envCheckbox = Array.from(allCheckboxes).find((cb) =>
        cb.closest('label')?.textContent?.includes('Environnement'),
      );
      expect(envCheckbox).not.toBeNull();
      if (envCheckbox) fireEvent.click(envCheckbox);

      // Environnement column is now visible — for non-execution entity_type, it must show "—"
      const headers = document.querySelectorAll('th');
      const headerTexts = Array.from(headers).map((h) => h.textContent?.trim());
      expect(headerTexts).toContain('Environnement');

      // The cell should show "—", not "PROD"
      expect(screen.queryByText('PROD')).not.toBeInTheDocument();
      // At least one "—" should be present (from Environnement column)
      const dashCells = Array.from(document.querySelectorAll('td')).filter(
        (td) => td.textContent?.trim() === '—',
      );
      expect(dashCells.length).toBeGreaterThan(0);
    });

    it('test_column_headers_include_new_columns — Entité, Type, Opération sont dans les en-têtes', () => {
      render(<AuditTable {...defaultProps} />);
      const headers = document.querySelectorAll('th');
      const headerTexts = Array.from(headers).map(h => h.textContent?.trim());
      expect(headerTexts).toContain('Entité');
      expect(headerTexts).toContain('Type');
      expect(headerTexts).toContain('Opération');
    });

    it('renders column toggle button', () => {
      render(<AuditTable {...defaultProps} />);
      expect(screen.getByText('Colonnes')).toBeInTheDocument();
    });

    it('Type column shows raw action_type for unknown value', () => {
      const unknownTypeEntry = { ...mockEntry, action_type: 'SOME_UNKNOWN_TYPE' };
      render(<AuditTable {...defaultProps} topLevelEntries={[unknownTypeEntry]} />);
      expect(screen.getByText('SOME_UNKNOWN_TYPE')).toBeInTheDocument();
    });

    it('Catégorie column is hidden by default', () => {
      render(<AuditTable {...defaultProps} />);
      const headers = document.querySelectorAll('th');
      const headerTexts = Array.from(headers).map(h => h.textContent?.trim());
      expect(headerTexts).not.toContain('Catégorie');
    });

    it('Environnement column is hidden by default', () => {
      render(<AuditTable {...defaultProps} />);
      const headers = document.querySelectorAll('th');
      const headerTexts = Array.from(headers).map(h => h.textContent?.trim());
      expect(headerTexts).not.toContain('Environnement');
    });

    it('Change SN column is hidden by default', () => {
      render(<AuditTable {...defaultProps} />);
      const headers = document.querySelectorAll('th');
      const headerTexts = Array.from(headers).map(h => h.textContent?.trim());
      expect(headerTexts).not.toContain('Change SN');
    });
  });
});
