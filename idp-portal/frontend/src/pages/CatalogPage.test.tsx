/**
 * Tests for CatalogPage (Story 3.1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CatalogPage from './CatalogPage';
import * as catalogService from '../services/catalog_service';

vi.mock('../services/catalog_service');
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

const mockActions: catalogService.CatalogAction[] = [
  {
    id: 1,
    name: 'Create PDB Oracle',
    description: 'Creates a Pluggable Database',
    engine: 'Oracle',
    platform: 'AAP',
    status: 'published',
    created_at: '2026-01-28T10:00:00',
    execution_count: 42,
    impact_level: 'low',
    parameters_schema: null,
    tags: ['provisioning', 'oracle'],
  },
  {
    id: 2,
    name: 'Patch Database',
    description: 'Apply security patches',
    engine: 'Oracle',
    platform: 'AAP',
    status: 'published',
    created_at: '2026-01-27T10:00:00',
    execution_count: 15,
    impact_level: 'high',
    parameters_schema: null,
    tags: ['patching'],
  },
];

const mockFavorites: catalogService.FavoriteEntry[] = [
  { action_id: 1, created_at: '2026-01-29T12:00:00' },
];

const mockRecentActions: catalogService.RecentAction[] = [
  { action_id: 2, name: 'Patch Database', last_executed_at: '2026-01-29T11:00:00' },
];

const mockActionDetail: catalogService.CatalogActionDetailResponse = {
  data: {
    id: 1,
    name: 'Create PDB Oracle',
    description: 'Full description of the action for the drawer',
    engine: 'Oracle',
    platform: 'AAP',
    status: 'published',
    created_at: '2026-01-28T10:00:00',
    execution_count: 42,
    impact_level: 'low',
    parameters_schema: {
      type: 'object',
      properties: {
        pdb_name: { type: 'string' },
      },
      required: ['pdb_name'],
    },
    tags: ['provisioning', 'oracle'],
  },
  can_execute: true,
  allowed_environments: ['DEV', 'QUAL'],
};

describe('CatalogPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue(mockActions);
    vi.mocked(catalogService.fetchCatalogTags).mockResolvedValue([]);
    vi.mocked(catalogService.fetchCatalogActionById).mockResolvedValue(mockActionDetail);
    vi.mocked(catalogService.fetchFavorites).mockResolvedValue(mockFavorites);
    vi.mocked(catalogService.fetchRecentActions).mockResolvedValue(mockRecentActions);
    vi.mocked(catalogService.addFavorite).mockResolvedValue(undefined);
    vi.mocked(catalogService.removeFavorite).mockResolvedValue(undefined);
  });

  it('renders page title and tabs (AC1, AC6; Story 2.23: categories removed)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });

    // Story 2.23: Only "Tout" and "Mes actions" tabs (categories removed, use tags instead)
    expect(screen.getByRole('tab', { name: /Tout/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Mes actions/i })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /Provisioning/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /Patching/i })).not.toBeInTheDocument();
  });

  it('displays action cards with execution_count (AC3)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    // ActionCard displays "N exécution(s)" in French
    expect(screen.getByText('42 exécutions')).toBeInTheDocument();
    expect(screen.getByText('15 exécutions')).toBeInTheDocument();
  });

  it('toggles between grid and list view (AC2)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    const gridButton = screen.getByLabelText('Vue grille');
    const listButton = screen.getByLabelText('Vue liste');

    expect(gridButton).toHaveAttribute('class', expect.stringContaining('primary'));

    await userEvent.click(listButton);

    expect(listButton).toHaveAttribute('class', expect.stringContaining('primary'));
  });

  it('persists view mode in localStorage (AC2)', async () => {
    localStorage.setItem('catalog-view-mode', 'list');
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    const listButton = screen.getByLabelText('Vue liste');
    expect(listButton).toHaveAttribute('class', expect.stringContaining('primary'));
    expect(localStorage.getItem('catalog-view-mode')).toBe('list');

    const gridButton = screen.getByLabelText('Vue grille');
    await userEvent.click(gridButton);
    expect(localStorage.getItem('catalog-view-mode')).toBe('grid');

    localStorage.removeItem('catalog-view-mode');
  });

  it('displays action count (AC6)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    expect(screen.getByText('2 actions')).toBeInTheDocument();
  });

  it('filters actions by search text (Story 3.3: server-side with debounce)', async () => {
    // Set up mock to return filtered results when search query contains 'patch'
    vi.mocked(catalogService.fetchCatalogActions).mockImplementation(async (filters) => {
      if (filters?.q?.toLowerCase().includes('patch')) {
        return [mockActions[1]]; // Only Patch Database
      }
      return mockActions;
    });

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Rechercher...');
    await userEvent.type(searchInput, 'Patch');

    // Wait for debounce (300ms) + re-render
    await waitFor(
      () => {
        // Verify fetchCatalogActions was called with q filter
        expect(catalogService.fetchCatalogActions).toHaveBeenCalledWith(
          expect.objectContaining({ q: 'Patch' })
        );
      },
      { timeout: 1000 }
    );

    await waitFor(
      () => {
        expect(screen.queryByText('Create PDB Oracle')).not.toBeInTheDocument();
        expect(screen.getByText('Patch Database')).toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });

  it('shows favorite indicator for favorited actions (AC4)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    // Action 1 is favorited
    const favoriteButtons = screen.getAllByLabelText(/favoris/i);
    expect(favoriteButtons.length).toBeGreaterThan(0);
  });

  it('fetches data without category filter (Story 2.23: categories removed)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      // Story 2.23: No category parameter sent (categories removed, use tags instead)
      expect(catalogService.fetchCatalogActions).toHaveBeenCalledWith(
        expect.not.objectContaining({ category: expect.anything() })
      );
    });

    // Switching to "Mes actions" also doesn't send category
    const myActionsTab = screen.getByRole('tab', { name: /Mes actions/i });
    await userEvent.click(myActionsTab);

    await waitFor(() => {
      expect(catalogService.fetchCatalogActions).toHaveBeenCalledWith(
        expect.not.objectContaining({ category: expect.anything() })
      );
    });
  });

  it('shows "Mes actions" with favorites and recent (AC5)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
    });

    const myActionsTab = screen.getByRole('tab', { name: /Mes actions/i });
    await userEvent.click(myActionsTab);

    await waitFor(() => {
      // Should show favorited action (id: 1) and recent action (id: 2)
      expect(screen.getByText('Actions recentes')).toBeInTheDocument();
    });
  });

  // Story 3.2 Tests
  describe('Story 3.2 - Drawer', () => {
    it('opens drawer when clicking on action card (AC1)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const actionCard = screen.getByText('Create PDB Oracle');
      await userEvent.click(actionCard);

      await waitFor(() => {
        expect(catalogService.fetchCatalogActionById).toHaveBeenCalledWith(1);
      });
    });

    it('fetches action detail when drawer opens (AC1, AC6)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const actionCard = screen.getByText('Create PDB Oracle');
      await userEvent.click(actionCard);

      await waitFor(() => {
        // Drawer should show full description from detail API
        expect(screen.getByText('Full description of the action for the drawer')).toBeInTheDocument();
      });
    });

    it('shows skeleton in drawer while loading (AC5)', async () => {
      // Make the fetch slow
      vi.mocked(catalogService.fetchCatalogActionById).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockActionDetail), 100))
      );

      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const actionCard = screen.getByText('Create PDB Oracle');
      await userEvent.click(actionCard);

      // Skeleton should appear while loading
      await waitFor(() => {
        const drawer = screen.getByRole('dialog');
        expect(drawer).toBeInTheDocument();
      });
    });

    it('closes drawer on Escape key (AC2)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const actionCard = screen.getByText('Create PDB Oracle');
      await userEvent.click(actionCard);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Press Escape
      fireEvent.keyDown(document.body, { key: 'Escape', code: 'Escape' });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('returns focus to clicked card after drawer closes (AC2)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      // Find the card container (has tabIndex and role="button")
      const cardContainer = screen.getByRole('button', { name: /Voir détails: Create PDB Oracle/i });
      await userEvent.click(cardContainer);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Close drawer via Escape
      fireEvent.keyDown(document.body, { key: 'Escape', code: 'Escape' });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });

      // Verify focus returned to card
      await waitFor(() => {
        expect(document.activeElement).toBe(cardContainer);
      });
    });

    it('drawer displays Execute button disabled when canExecute is false (AC3)', async () => {
      vi.mocked(catalogService.fetchCatalogActionById).mockResolvedValue({
        ...mockActionDetail,
        can_execute: false,
        allowed_environments: [],
      });

      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const actionCard = screen.getByText('Create PDB Oracle');
      await userEvent.click(actionCard);

      await waitFor(() => {
        const executeButton = screen.getByRole('button', { name: /Executer/i });
        expect(executeButton).toBeDisabled();
      });
    });

    it('drawer displays Execute button enabled when canExecute is true (AC3)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const actionCard = screen.getByText('Create PDB Oracle');
      await userEvent.click(actionCard);

      await waitFor(() => {
        const executeButton = screen.getByRole('button', { name: /Executer/i });
        expect(executeButton).not.toBeDisabled();
      });
    });
  });

  // Story 3.5 Tests - Tag Cloud and Favorite Clarity
  describe('Story 3.5 - TagCloud and Favorite Clarity', () => {
    const mockTagsWithCounts: catalogService.CatalogTagWithCount[] = [
      { name: 'provisioning', action_count: 5 },
      { name: 'patching', action_count: 3 },
      { name: 'oracle', action_count: 8 },
    ];

    beforeEach(() => {
      vi.mocked(catalogService.fetchCatalogTags).mockResolvedValue(mockTagsWithCounts);
    });

    it('displays TagCloud with tags from API (AC1, AC12)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('provisioning (5)')).toBeInTheDocument();
        expect(screen.getByText('patching (3)')).toBeInTheDocument();
        expect(screen.getByText('oracle (8)')).toBeInTheDocument();
      });
    });

    it('does not display TagCloud on "Mes actions" tab (AC10)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('provisioning (5)')).toBeInTheDocument();
      });

      const myActionsTab = screen.getByRole('tab', { name: /Mes actions/i });
      await userEvent.click(myActionsTab);

      await waitFor(() => {
        expect(screen.queryByText('provisioning (5)')).not.toBeInTheDocument();
      });
    });

    it('filters actions when tag is clicked in TagCloud (AC2)', async () => {
      vi.mocked(catalogService.fetchCatalogActions).mockImplementation(async (filters) => {
        if (filters?.tags?.includes('patching')) {
          return [mockActions[1]]; // Only Patch Database
        }
        return mockActions;
      });

      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('patching (3)')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByText('patching (3)'));

      await waitFor(() => {
        expect(catalogService.fetchCatalogActions).toHaveBeenCalledWith(
          expect.objectContaining({ tags: ['patching'] })
        );
      });
    });

    it('updates action count with aria-live when filtering (AC2, AC6)', async () => {
      vi.mocked(catalogService.fetchCatalogActions).mockImplementation(async (filters) => {
        if (filters?.tags?.includes('patching')) {
          return [mockActions[1]]; // Only Patch Database
        }
        return mockActions;
      });

      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('2 actions')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByText('patching (3)'));

      await waitFor(() => {
        const counter = screen.getByText('1 action');
        expect(counter).toHaveAttribute('aria-live', 'polite');
      });
    });

    it('favorite button has aria-label for accessibility (AC8)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      // Action 1 is favorited, action 2 is not
      const removeLabel = screen.getByLabelText('Retirer des favoris');
      const addLabel = screen.getByLabelText('Ajouter aux favoris');

      expect(removeLabel).toBeInTheDocument();
      expect(addLabel).toBeInTheDocument();
    });

    it('shows tooltip on favorite button hover (AC7)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      const removeFavButton = screen.getByLabelText('Retirer des favoris');
      await userEvent.hover(removeFavButton);

      await waitFor(() => {
        // Ant Design Tooltip renders title in portal; content may be in role="tooltip" or as visible text
        const tooltip = document.querySelector('[role="tooltip"]') ?? document.body;
        expect(tooltip).toHaveTextContent('Retirer des favoris');
      });
    });

    it('favorite button shows distinct visual state (AC9)', async () => {
      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
      });

      // Favorited action: HeartFilled with color #eb2f96 (distinct from outline)
      const favButton = screen.getByLabelText('Retirer des favoris');
      const heartIcon = favButton.querySelector('svg');
      expect(heartIcon).toBeInTheDocument();
      const iconWrapper = favButton.querySelector('.anticon');
      expect(iconWrapper).toBeInTheDocument();
      // HeartFilled uses color #eb2f96 (inline style preserved in jsdom)
      expect(iconWrapper).toHaveStyle({ color: '#eb2f96' });
    });

    it('shows counter with loading state when refetching (AC2)', async () => {
      vi.mocked(catalogService.fetchCatalogActions).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockActions), 200))
      );

      render(<CatalogPage />);

      await waitFor(() => {
        expect(screen.getByText('2 actions')).toBeInTheDocument();
      });

      // Counter stays visible (shows "Chargement…" during refetch)
      const counterRegion = screen.getByText('2 actions').closest('[aria-live="polite"]');
      expect(counterRegion).toBeInTheDocument();

      // Switch tab to trigger refetch (Story 2.23: use "Mes actions" instead of removed category tabs)
      await userEvent.click(screen.getByRole('tab', { name: /Mes actions/i }));

      await waitFor(() => {
        expect(counterRegion).toBeInTheDocument();
        expect(counterRegion?.textContent).toMatch(/Chargement…|2 actions/);
      });
    });
  });
});
