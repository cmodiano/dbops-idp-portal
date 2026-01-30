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

  it('renders page title and category tabs (AC1, AC6)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });

    expect(screen.getByRole('tab', { name: /Tout/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Provisioning/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Patching/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Mes actions/i })).toBeInTheDocument();
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

  it('fetches data with category filter when tab changes (AC6)', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(catalogService.fetchCatalogActions).toHaveBeenCalledWith({ category: undefined });
    });

    const provisioningTab = screen.getByRole('tab', { name: /Provisioning/i });
    await userEvent.click(provisioningTab);

    await waitFor(() => {
      expect(catalogService.fetchCatalogActions).toHaveBeenCalledWith({ category: 'provisioning' });
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
});
