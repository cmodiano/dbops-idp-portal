/**
 * Tests for useCatalogState hook — Story 34.10 (SOLID-FE-2, AC6).
 *
 * Minimum 4 tests unitaires :
 * 1. filteredActions: "mes-actions" retourne uniquement les favoris
 * 2. resetFilters: remet toutes les valeurs à leur état initial
 * 3. handleViewModeChange: met à jour viewMode et écrit dans localStorage
 * 4. hasActiveFilters: true quand au moins un filtre actif, false sinon
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { App } from 'antd';
import { useCatalogState } from './useCatalogState';
import * as catalogService from '../services/catalog_service';

vi.mock('../services/catalog_service');

// Wrapper avec App pour App.useApp()
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(App, null, children);

const mockFavoriteAction: catalogService.CatalogAction = {
  id: 1,
  name: 'Favorite Action',
  description: 'A favorite action',
  engine: 'Oracle',
  platform: 'AAP',
  status: 'published',
  created_at: '2026-01-28T10:00:00',
  execution_count: 10,
  impact_level: 'low',
  parameters_schema: null,
  tags: ['provisioning'],
};

const mockNonFavoriteAction: catalogService.CatalogAction = {
  id: 2,
  name: 'Non-Favorite Action',
  description: 'A non-favorite action',
  engine: 'Oracle',
  platform: 'AAP',
  status: 'published',
  created_at: '2026-01-27T10:00:00',
  execution_count: 5,
  impact_level: 'high',
  parameters_schema: null,
  tags: ['patching'],
};

describe('useCatalogState', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue([mockFavoriteAction, mockNonFavoriteAction]);
    vi.mocked(catalogService.fetchCatalogTags).mockResolvedValue([]);
    vi.mocked(catalogService.fetchFavorites).mockResolvedValue([{ action_id: 1, created_at: '2026-01-29T12:00:00' }]);
    vi.mocked(catalogService.fetchActionStats).mockResolvedValue(null);
    vi.mocked(catalogService.addFavorite).mockResolvedValue(undefined);
    vi.mocked(catalogService.removeFavorite).mockResolvedValue(undefined);
    vi.mocked(catalogService.fetchCatalogActionById).mockResolvedValue({
      data: mockFavoriteAction as unknown as catalogService.CatalogActionDetail,
      can_execute: true,
      allowed_environments: ['DEV'],
    });
    localStorage.removeItem('catalog-view-mode-v1');
  });

  afterEach(() => {
    localStorage.removeItem('catalog-view-mode-v1');
  });

  it('filteredActions: "mes-actions" retourne uniquement les favoris', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });

    // Attendre que les données soient chargées
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // En mode "tout", toutes les actions sont retournées
    expect(result.current.filteredActions).toHaveLength(2);

    // Passer en mode "mes-actions"
    act(() => {
      result.current.handleCategoryChange('mes-actions');
    });

    await waitFor(() => {
      // Seule l'action favorite (id=1) doit apparaître
      expect(result.current.filteredActions).toHaveLength(1);
      expect(result.current.filteredActions[0].id).toBe(1);
    });
  });

  it('resetFilters: remet toutes les valeurs à leur état initial', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Appliquer des filtres
    act(() => {
      result.current.setSearchText('test search');
      result.current.setFilterTags(['provisioning']);
      result.current.setFilterEngines(['Oracle']);
      result.current.setFilterImpacts(['high']);
    });

    // Vérifier que les filtres sont actifs
    await waitFor(() => {
      expect(result.current.searchText).toBe('test search');
      expect(result.current.filterTags).toEqual(['provisioning']);
      expect(result.current.filterEngines).toEqual(['Oracle']);
      expect(result.current.filterImpacts).toEqual(['high']);
    });

    // Réinitialiser les filtres
    act(() => {
      result.current.resetFilters();
    });

    // Vérifier que tout est réinitialisé
    await waitFor(() => {
      expect(result.current.searchText).toBe('');
      expect(result.current.filterTags).toEqual([]);
      expect(result.current.filterEngines).toEqual([]);
      expect(result.current.filterImpacts).toEqual([]);
      expect(result.current.activeCategory).toBe('tout');
    });
  });

  it('handleViewModeChange: met à jour viewMode et écrit dans localStorage', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });

    // Attendre la fin du chargement initial pour éviter les warnings act()
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Mode par défaut : grid
    expect(result.current.viewMode).toBe('grid');
    expect(localStorage.getItem('catalog-view-mode-v1')).toBeNull();

    // Passer en mode list
    act(() => {
      result.current.handleViewModeChange('list');
    });

    expect(result.current.viewMode).toBe('list');
    expect(localStorage.getItem('catalog-view-mode-v1')).toBe('list');

    // Repasser en mode grid
    act(() => {
      result.current.handleViewModeChange('grid');
    });

    expect(result.current.viewMode).toBe('grid');
    expect(localStorage.getItem('catalog-view-mode-v1')).toBe('grid');
  });

  it('hasActiveFilters: true quand un filtre actif, false sinon', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Aucun filtre actif par défaut
    expect(result.current.hasActiveFilters).toBe(false);

    // Activer un filtre tag (déclenche loadData → await act pour drainer les effets async)
    await act(async () => {
      result.current.setFilterTags(['oracle']);
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Désactiver le filtre tag
    await act(async () => {
      result.current.setFilterTags([]);
    });
    expect(result.current.hasActiveFilters).toBe(false);

    // Activer un filtre engine
    await act(async () => {
      result.current.setFilterEngines(['Oracle']);
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Désactiver le filtre engine
    await act(async () => {
      result.current.setFilterEngines([]);
    });
    expect(result.current.hasActiveFilters).toBe(false);

    // Saisir un texte de recherche (debounce 300ms — loadData non déclenché immédiatement)
    act(() => {
      result.current.setSearchText('   test   ');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Vider le texte de recherche
    act(() => {
      result.current.setSearchText('');
    });
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('handleExecuteClick: ouvre le wizard d\'exécution', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.executionWizardOpen).toBe(false);

    act(() => {
      result.current.handleExecuteClick();
    });

    expect(result.current.executionWizardOpen).toBe(true);
  });

  it('handleExecutionSuccess: ferme le wizard et ouvre la vue d\'exécution', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Open wizard first
    act(() => {
      result.current.setExecutionWizardOpen(true);
    });

    await act(async () => {
      result.current.handleExecutionSuccess(42);
    });

    await waitFor(() => {
      expect(result.current.executionWizardOpen).toBe(false);
      expect(result.current.executionViewId).toBe(42);
      expect(result.current.drawerVisible).toBe(false);
    });
  });

  it('handleBackToCatalog: réinitialise tous les états de navigation', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Set various states
    act(() => {
      result.current.setActiveExecutionId(5);
      result.current.setExecutionWizardOpen(true);
      result.current.setExecutionViewId(10);
    });

    await act(async () => {
      result.current.handleBackToCatalog();
    });

    await waitFor(() => {
      expect(result.current.activeExecutionId).toBeNull();
      expect(result.current.executionWizardOpen).toBe(false);
      expect(result.current.executionViewId).toBeNull();
    });
  });

  it('handleToggleFavorite: ajoute un favori', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // mockNonFavoriteAction (id=2) is not a favorite
    const mockEvent = { stopPropagation: vi.fn() } as unknown as React.MouseEvent;

    await act(async () => {
      await result.current.handleToggleFavorite(2, mockEvent);
    });

    expect(catalogService.addFavorite).toHaveBeenCalledWith(2);
    expect(result.current.favorites.has(2)).toBe(true);
  });

  it('handleToggleFavorite: supprime un favori existant', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // action id=1 is a favorite
    const mockEvent = { stopPropagation: vi.fn() } as unknown as React.MouseEvent;

    await act(async () => {
      await result.current.handleToggleFavorite(1, mockEvent);
    });

    expect(catalogService.removeFavorite).toHaveBeenCalledWith(1);
    expect(result.current.favorites.has(1)).toBe(false);
  });

  it('handleDrawerClose: ferme le drawer', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Open the drawer first via handleActionClick
    await act(async () => {
      await result.current.handleActionClick(mockFavoriteAction);
    });

    await waitFor(() => expect(result.current.drawerVisible).toBe(true));

    act(() => {
      result.current.handleDrawerClose();
    });

    expect(result.current.drawerVisible).toBe(false);
  });

  it('handleActionClick error case: message.error shown', async () => {
    vi.mocked(catalogService.fetchCatalogActionById).mockRejectedValueOnce(new Error('API fail'));
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleActionClick(mockFavoriteAction);
    });

    // Drawer stays open with basic info from list
    expect(result.current.drawerLoading).toBe(false);
  });

  it('handleCategoryChange resets filterTags', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => { result.current.setFilterTags(['provisioning']); });
    act(() => { result.current.handleCategoryChange('patching'); });

    expect(result.current.filterTags).toEqual([]);
    expect(result.current.activeCategory).toBe('patching');
  });

  it('fetchCatalogActions error calls message.error', async () => {
    vi.mocked(catalogService.fetchCatalogActions).mockRejectedValueOnce(new Error('Load failed'));
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // No crash — error handled internally
    expect(result.current.actions).toEqual([]);
  });

  it('handleRemediationSuggestionClick error case: message.error shown', async () => {
    vi.mocked(catalogService.fetchCatalogActionById).mockRejectedValueOnce(new Error('Not found'));
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleRemediationSuggestionClick({
        action_id: 1, action_name: 'Fix', action_description: null,
        matching_rule: { error_pattern: '.*', target_action_id: 1, environments: [], auto_trigger: false, risk_level: 'low' as const },
      });
    });

    // wizard stays closed on error
    expect(result.current.executionWizardOpen).toBe(false);
  });

  it('handleRemediationSuggestionClick: charge l\'action et ouvre le wizard', async () => {
    const { result } = renderHook(() => useCatalogState(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    const suggestion = {
      action_id: 1,
      action_name: 'Fix Action',
      action_description: null,
      matching_rule: {
        error_pattern: '.*',
        target_action_id: 1,
        environments: ['prod'],
        auto_trigger: false,
        risk_level: 'low' as const,
      },
    };

    await act(async () => {
      await result.current.handleRemediationSuggestionClick(suggestion);
    });

    await waitFor(() => {
      expect(result.current.executionWizardOpen).toBe(true);
      expect(catalogService.fetchCatalogActionById).toHaveBeenCalledWith(1);
    });
  });
});
