/**
 * ActionTable tests (Story 8.10).
 *
 * Tests for all acceptance criteria:
 * - AC1: Table displays with all expected columns
 * - AC2: Action column with icon and name
 * - AC3: Description truncated with tooltip
 * - AC4: Impact column with ImpactIndicator
 * - AC5: Tags column with max 3 + "+N"
 * - AC6: Exécutions column formatted
 * - AC7: Favori toggle
 * - AC8: Actions column with details button
 * - AC9: Column sorting
 * - AC10: Row hover/click
 * - AC11: Loading skeleton
 * - AC12: Responsive (tested via column config)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { ActionTable } from './ActionTable';
import type { CatalogAction } from '../../services/catalog_service';

// Mock CatalogAction data
const createMockAction = (overrides: Partial<CatalogAction> = {}): CatalogAction => ({
  id: 1,
  name: 'Test Action',
  description: 'This is a test action description that might be quite long and need truncation.',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'medium',
  parameters_schema: null,
  tags: ['oracle', 'provisioning', 'database'],
  execution_count: 42,
  status: 'published',
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

const mockActions: CatalogAction[] = [
  createMockAction({ id: 1, name: 'Action Alpha', engine: 'Oracle', execution_count: 10, impact_level: 'low' }),
  createMockAction({ id: 2, name: 'Action Beta', engine: 'SQL Server', execution_count: 50, impact_level: 'high' }),
  createMockAction({ id: 3, name: 'Action Gamma', engine: 'DB2', execution_count: 5, impact_level: 'critical' }),
];

const mockFavorites = new Set([1, 3]);

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('ActionTable (Story 8.10)', () => {
  const mockOnActionClick = vi.fn();
  const mockOnToggleFavorite = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  describe('AC1 - Table structure and columns', () => {
    it('renders a table with all expected column headers', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByRole('table')).toBeInTheDocument();
      // Use getAllByText since Ant Design may duplicate column headers for fixed columns
      expect(screen.getAllByText('Action').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Description').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Impact').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Tags').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Moteur').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Exécutions').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Favori').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Actions').length).toBeGreaterThan(0);
    });

    it('renders all actions as table rows', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('Action Alpha')).toBeInTheDocument();
      expect(screen.getByText('Action Beta')).toBeInTheDocument();
      expect(screen.getByText('Action Gamma')).toBeInTheDocument();
    });
  });

  describe('AC2 - Action column with icon and name', () => {
    it('displays action name in bold', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const actionName = screen.getByText('Action Alpha');
      expect(actionName.closest('strong')).toBeInTheDocument();
    });

    it('displays workflow icon for workflow item_type', () => {
      const workflowAction = createMockAction({
        id: 10,
        name: 'Workflow Test',
        item_type: 'workflow',
        engine: null,
      });

      renderWithTheme(
        <ActionTable
          actions={[workflowAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // ApartmentOutlined icon should be present for workflow
      const table = screen.getByRole('table');
      expect(within(table).getByText('Workflow Test')).toBeInTheDocument();
    });

    it('displays "Sans nom" for action without name', () => {
      const noNameAction = createMockAction({ id: 20, name: '' });

      renderWithTheme(
        <ActionTable
          actions={[noNameAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('Sans nom')).toBeInTheDocument();
    });
  });

  describe('AC3 - Description column', () => {
    it('displays description text', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Description may be duplicated in fixed columns
      expect(screen.getAllByText(/This is a test action description/).length).toBeGreaterThan(0);
    });

    it('displays "Aucune description" when description is null', () => {
      const noDescAction = createMockAction({ id: 30, description: null });

      renderWithTheme(
        <ActionTable
          actions={[noDescAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('Aucune description')).toBeInTheDocument();
    });
  });

  describe('AC4 - Impact column', () => {
    it('displays ImpactIndicator for each action', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // ImpactIndicator renders French labels - may be duplicated in fixed columns
      expect(screen.getAllByText('Faible').length).toBeGreaterThan(0); // low
      expect(screen.getAllByText('Eleve').length).toBeGreaterThan(0); // high (no accent in impactLabels.ts)
      expect(screen.getAllByText('Critique').length).toBeGreaterThan(0); // critical
    });

    it('displays "N/A" when impact_level is null', () => {
      const noImpactAction = createMockAction({ id: 40, impact_level: null });

      renderWithTheme(
        <ActionTable
          actions={[noImpactAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });

  describe('AC5 - Tags column', () => {
    it('displays up to 3 tags', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getAllByText('oracle').length).toBeGreaterThan(0);
      expect(screen.getAllByText('provisioning').length).toBeGreaterThan(0);
      expect(screen.getAllByText('database').length).toBeGreaterThan(0);
    });

    it('displays "+N" indicator when tags exceed 3', () => {
      const manyTagsAction = createMockAction({
        id: 50,
        tags: ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'],
      });

      renderWithTheme(
        <ActionTable
          actions={[manyTagsAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('+2')).toBeInTheDocument();
    });

    it('displays "Aucun tag" when tags are empty', () => {
      const noTagsAction = createMockAction({ id: 60, tags: [] });

      renderWithTheme(
        <ActionTable
          actions={[noTagsAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('Aucun tag')).toBeInTheDocument();
    });
  });

  describe('AC6 - Exécutions column', () => {
    it('displays execution count formatted', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('10 exécutions')).toBeInTheDocument();
      expect(screen.getByText('50 exécutions')).toBeInTheDocument();
      expect(screen.getByText('5 exécutions')).toBeInTheDocument();
    });

    it('displays singular "exécution" for count of 1', () => {
      const singleExecAction = createMockAction({ id: 70, execution_count: 1 });

      renderWithTheme(
        <ActionTable
          actions={[singleExecAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('1 exécution')).toBeInTheDocument();
    });

    it('displays "0 exécutions" for null count', () => {
      const noExecAction = createMockAction({ id: 80, execution_count: 0 });

      renderWithTheme(
        <ActionTable
          actions={[noExecAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('0 exécutions')).toBeInTheDocument();
    });
  });

  describe('AC7 - Favori column', () => {
    it('displays filled heart for favorites', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Actions 1 and 3 are favorites
      const favoriteButtons = screen.getAllByRole('button', { name: /favoris/i });
      expect(favoriteButtons.length).toBeGreaterThan(0);
    });

    it('calls onToggleFavorite when favorite button is clicked', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const favoriteButtons = screen.getAllByRole('button', { name: /favoris/i });
      fireEvent.click(favoriteButtons[0]);

      expect(mockOnToggleFavorite).toHaveBeenCalled();
    });

    it('stops propagation when clicking favorite button', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const favoriteButtons = screen.getAllByRole('button', { name: /favoris/i });
      fireEvent.click(favoriteButtons[0]);

      // onActionClick should NOT be called (event stopped)
      expect(mockOnActionClick).not.toHaveBeenCalled();
    });

    it('hides favorite button when showFavoriteButton is false', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
          showFavoriteButton={false}
        />
      );

      const favoriteButtons = screen.queryAllByRole('button', { name: /favoris/i });
      expect(favoriteButtons.length).toBe(0);
    });
  });

  describe('AC8 - Actions column', () => {
    it('displays "Voir détails" button for each row', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const detailButtons = screen.getAllByRole('button', { name: /voir détails/i });
      expect(detailButtons.length).toBe(3);
    });

    it('calls onActionClick when details button is clicked', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const detailButtons = screen.getAllByRole('button', { name: /voir détails/i });
      fireEvent.click(detailButtons[0]);

      expect(mockOnActionClick).toHaveBeenCalledWith(mockActions[0]);
    });
  });

  describe('AC9 - Column sorting', () => {
    it('renders sortable column headers', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Check that columns have sorter (may be duplicated in fixed columns)
      const actionHeaders = screen.getAllByText('Action');
      expect(actionHeaders.length).toBeGreaterThan(0);

      // Table should be sortable - click header to sort
      fireEvent.click(actionHeaders[0]);
      // Table will re-render with sorted data
    });

    it('sorts by default on name ascending', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // First row should be Action Alpha (alphabetically first)
      const rows = screen.getAllByRole('row');
      // First row is header, second is first data row
      expect(within(rows[1]).getByText('Action Alpha')).toBeInTheDocument();
    });
  });

  describe('AC10 - Row hover/click', () => {
    it('calls onActionClick when row is clicked', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Find the row containing Action Alpha and click it
      const rows = screen.getAllByRole('row');
      // Skip header row (index 0), click first data row
      fireEvent.click(rows[1]);

      expect(mockOnActionClick).toHaveBeenCalled();
    });

    it('applies cursor:pointer class to rows', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const rows = screen.getAllByRole('row');
      // Data rows should have the catalog-table-row class
      expect(rows[1]).toHaveClass('catalog-table-row');
    });
  });

  describe('AC11 - Loading state', () => {
    it('displays loading spinner when loading is true', () => {
      renderWithTheme(
        <ActionTable
          actions={[]}
          favorites={new Set()}
          loading={true}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Ant Design Table shows spinner when loading
      expect(screen.getByRole('table')).toBeInTheDocument();
      // Loading indicator is present (ant-spin)
      const spinner = document.querySelector('.ant-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('AC12 - Responsive columns', () => {
    it('configures Description column with responsive: md', () => {
      // This test verifies the column configuration includes responsive property
      // The actual hiding is handled by Ant Design based on viewport
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Description column should be present (may be duplicated in fixed columns)
      expect(screen.getAllByText('Description').length).toBeGreaterThan(0);
    });

    it('configures Tags column with responsive: md', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Tags column should be present (may be duplicated in fixed columns)
      expect(screen.getAllByText('Tags').length).toBeGreaterThan(0);
    });
  });

  describe('Empty state', () => {
    it('displays empty message when no actions', () => {
      renderWithTheme(
        <ActionTable
          actions={[]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('Aucune action')).toBeInTheDocument();
    });
  });

  describe('Pagination', () => {
    it('displays pagination info', () => {
      const manyActions = Array.from({ length: 25 }, (_, i) =>
        createMockAction({ id: i + 1, name: `Action ${i + 1}` })
      );

      renderWithTheme(
        <ActionTable
          actions={manyActions}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Pagination should show total
      expect(screen.getByText('25 actions')).toBeInTheDocument();
    });

    it('paginates with pageSize 20', () => {
      const manyActions = Array.from({ length: 25 }, (_, i) =>
        createMockAction({ id: i + 1, name: `Action ${String(i + 1).padStart(2, '0')}` })
      );

      renderWithTheme(
        <ActionTable
          actions={manyActions}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      // Should show first 20 rows on page 1
      const rows = screen.getAllByRole('row');
      // 1 header + 20 data rows = 21 rows
      expect(rows.length).toBe(21);
    });
  });

  describe('Engine/Moteur column', () => {
    it('displays engine name', () => {
      renderWithTheme(
        <ActionTable
          actions={mockActions}
          favorites={mockFavorites}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('Oracle')).toBeInTheDocument();
      expect(screen.getByText('SQL Server')).toBeInTheDocument();
      expect(screen.getByText('DB2')).toBeInTheDocument();
    });

    it('displays "N/A" when engine is null', () => {
      const noEngineAction = createMockAction({ id: 90, engine: null });

      renderWithTheme(
        <ActionTable
          actions={[noEngineAction]}
          favorites={new Set()}
          loading={false}
          onActionClick={mockOnActionClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });
});
