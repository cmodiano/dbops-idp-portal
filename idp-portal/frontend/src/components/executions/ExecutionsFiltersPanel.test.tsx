/**
 * Tests for ExecutionsFiltersPanel (Story 34.14 — SOLID-FE-11).
 *
 * Filtres avancés pour la page Executions. Apply-on-change (pas de bouton Appliquer).
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { App } from 'antd';
import { ExecutionsFiltersPanel } from './ExecutionsFiltersPanel';
import type { ExecutionsFiltersPanelProps } from './ExecutionsFiltersPanel';
import type { ExecutionFilters } from '../../types/api';
import { useEngines } from '../../hooks/useEngines';
import { useEnvironments } from '../../hooks/useEnvironments';
import { fetchExecutionTags } from '../../services/execution_service';
import { fetchCatalogActions } from '../../services/catalog_service';

// Mock hooks et services avant import du composant
vi.mock('../../hooks/useEngines', () => ({
  useEngines: vi.fn(() => ({
    engineOptions: [
      { label: 'Oracle', value: 'oracle' },
      { label: 'PostgreSQL', value: 'postgres' },
    ],
    loading: false,
  })),
}));

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(() => ({
    environmentOptions: [
      { label: 'dev', value: 'dev' },
      { label: 'prod', value: 'prod' },
    ],
    loading: false,
  })),
}));

vi.mock('../../services/execution_service', () => ({
  fetchExecutionTags: vi.fn(() => Promise.resolve(['tag1', 'tag2', 'tag3'])),
}));

vi.mock('../../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(() =>
    Promise.resolve([
      { id: 1, name: 'Action Oracle', engine: 'oracle', platform: 'AAP' },
      { id: 2, name: 'Action PostgreSQL', engine: 'postgres', platform: 'Terraform' },
    ]),
  ),
}));

const emptyFilters: ExecutionFilters = {
  start_date: null,
  end_date: null,
  action_id: null,
  engine: null,
  tags: null,
  status: null,
  environment: null,
};

const defaultProps: ExecutionsFiltersPanelProps = {
  filters: emptyFilters,
  onApplyFilters: vi.fn(),
  onResetFilters: vi.fn(),
  activeFilterCount: 0,
};

function renderFiltersPanel(props: Partial<ExecutionsFiltersPanelProps> = {}) {
  return render(
    <App>
      <ExecutionsFiltersPanel {...defaultProps} {...props} />
    </App>,
  );
}

describe('ExecutionsFiltersPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendu smoke', () => {
    it('rend sans erreur', () => {
      expect(() => renderFiltersPanel()).not.toThrow();
    });

    it('affiche le panneau de filtres', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('executions-filters-panel')).toBeInTheDocument();
    });

    it("affiche le titre 'Filtres avancés'", () => {
      renderFiltersPanel();
      expect(screen.getByText('Filtres avancés')).toBeInTheDocument();
    });

    it('affiche le bouton Réinitialiser', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('filter-reset')).toBeInTheDocument();
    });
  });

  describe('Badge compteur de filtres actifs', () => {
    it("n'affiche pas le badge quand activeFilterCount=0", () => {
      renderFiltersPanel({ activeFilterCount: 0 });
      expect(screen.queryByTestId('active-filters-badge')).not.toBeInTheDocument();
    });

    it('affiche le badge quand activeFilterCount>0', () => {
      renderFiltersPanel({ activeFilterCount: 3 });
      expect(screen.getByTestId('active-filters-badge')).toBeInTheDocument();
    });

    it('affiche le bon nombre dans le badge', () => {
      renderFiltersPanel({ activeFilterCount: 5 });
      // Le badge Ant Design affiche le count comme texte
      expect(screen.getByTestId('active-filters-badge')).toHaveTextContent('5');
    });
  });

  describe('Bouton Réinitialiser', () => {
    it('est désactivé quand activeFilterCount=0', () => {
      renderFiltersPanel({ activeFilterCount: 0 });
      expect(screen.getByTestId('filter-reset')).toBeDisabled();
    });

    it("est activé quand activeFilterCount>0", () => {
      renderFiltersPanel({ activeFilterCount: 2 });
      expect(screen.getByTestId('filter-reset')).not.toBeDisabled();
    });

    it("appelle onResetFilters au clic", async () => {
      const user = userEvent.setup();
      const onResetFilters = vi.fn();
      renderFiltersPanel({ activeFilterCount: 1, onResetFilters });
      await user.click(screen.getByTestId('filter-reset'));
      expect(onResetFilters).toHaveBeenCalledTimes(1);
    });

    it("est désactivé quand loading=true", () => {
      renderFiltersPanel({ activeFilterCount: 3, loading: true });
      expect(screen.getByTestId('filter-reset')).toBeDisabled();
    });
  });

  describe('Chargement des options au montage', () => {
    it('charge les tags depuis fetchExecutionTags', async () => {
      renderFiltersPanel();
      await waitFor(() => {
        expect(vi.mocked(fetchExecutionTags)).toHaveBeenCalledTimes(1);
      });
    });

    it('charge les actions depuis fetchCatalogActions', async () => {
      renderFiltersPanel();
      await waitFor(() => {
        expect(vi.mocked(fetchCatalogActions)).toHaveBeenCalledTimes(1);
      });
    });

    it('utilise useEngines pour charger les moteurs', () => {
      renderFiltersPanel();
      expect(vi.mocked(useEngines)).toHaveBeenCalled();
    });

    it('utilise useEnvironments pour charger les environnements', () => {
      renderFiltersPanel();
      expect(vi.mocked(useEnvironments)).toHaveBeenCalled();
    });
  });

  describe('Présence des filtres dans le DOM', () => {
    it('affiche le filtre de période (RangePicker)', () => {
      renderFiltersPanel();
      // Ant Design RangePicker — cherche par placeholder ou label
      expect(screen.getByText('Période')).toBeInTheDocument();
    });

    it('affiche le filtre technologie', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('filter-engine')).toBeInTheDocument();
    });

    it('affiche le filtre statut', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('filter-status')).toBeInTheDocument();
    });

    it('affiche le filtre environnement', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('filter-environment')).toBeInTheDocument();
    });

    it('affiche le filtre tags', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('filter-tags')).toBeInTheDocument();
    });

    it('affiche le filtre action', () => {
      renderFiltersPanel();
      expect(screen.getByTestId('filter-action')).toBeInTheDocument();
    });
  });

  describe('Appel onApplyFilters lors des changements', () => {
    it("appelle onApplyFilters quand le statut change", async () => {
      const user = userEvent.setup();
      const onApplyFilters = vi.fn();
      renderFiltersPanel({ onApplyFilters });

      // Ouvrir le Select Statut
      const statusSelect = screen.getByTestId('filter-status');
      await user.click(statusSelect);

      // Chercher et cliquer sur une option dans le dropdown
      await waitFor(() => {
        const option = screen.queryByText('Terminée');
        if (option) return option;
        throw new Error('Option not found');
      });
      await user.click(screen.getByText('Terminée'));

      expect(onApplyFilters).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'COMPLETED' }),
      );
    });

    it("appelle onApplyFilters quand le moteur change", async () => {
      const user = userEvent.setup();
      const onApplyFilters = vi.fn();
      renderFiltersPanel({ onApplyFilters });

      const engineSelect = screen.getByTestId('filter-engine');
      await user.click(engineSelect);

      await waitFor(() => {
        const option = screen.queryByText('Oracle');
        if (option) return option;
        throw new Error('Oracle option not found');
      });
      await user.click(screen.getByText('Oracle'));

      expect(onApplyFilters).toHaveBeenCalledWith(
        expect.objectContaining({ engine: 'oracle' }),
      );
    });

    it("appelle onApplyFilters quand l'action change", async () => {
      const user = userEvent.setup();
      const onApplyFilters = vi.fn();
      renderFiltersPanel({ onApplyFilters });

      const actionSelect = screen.getByTestId('filter-action');
      await user.click(actionSelect);

      await waitFor(() => {
        const option = screen.queryByText('Action Oracle');
        if (option) return option;
        throw new Error('Action Oracle option not found');
      });
      await user.click(screen.getByText('Action Oracle'));

      expect(onApplyFilters).toHaveBeenCalledWith(
        expect.objectContaining({ action_id: 1 }),
      );
    });
  });
});
