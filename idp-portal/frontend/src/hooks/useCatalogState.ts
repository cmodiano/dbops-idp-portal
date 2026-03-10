/**
 * useCatalogState Hook — Story 34.10 (SOLID-FE-2)
 *
 * Extracted from CatalogPage.tsx. Manages all catalog UI state:
 * view mode, filters, data loading, drawer, execution wizard.
 *
 * Pattern: same as useCalendarState (Story 26.6), useActionFormState (Story 33.5).
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { App } from 'antd';
import type { CategoryKey } from '../components/catalog/CategoryTabs';
import { useDebounce } from './useDebounce';
import {
  fetchCatalogActions,
  fetchCatalogActionById,
  fetchCatalogTags,
  fetchFavorites,
  addFavorite,
  removeFavorite,
  fetchActionStats,
  type CatalogAction,
  type CatalogActionDetail,
  type CatalogTagWithCount,
  type FavoriteEntry,
} from '../services/catalog_service';
import type { ActionStats, RemediationSuggestion } from '../types/api';
import logger from '../services/logger';

/** localStorage key for view mode (AC2). */
const CATALOG_VIEW_MODE_KEY = 'catalog-view-mode-v1';

/** View mode: grid or list (AC2). */
export type ViewMode = 'grid' | 'list';

function getStoredViewMode(): ViewMode {
  try {
    const stored = localStorage.getItem(CATALOG_VIEW_MODE_KEY);
    if (stored === 'grid' || stored === 'list') return stored;
  } catch {
    // ignore
  }
  return 'grid';
}

export interface UseCatalogStateReturn {
  // Vue
  viewMode: ViewMode;
  handleViewModeChange: (mode: ViewMode) => void;
  // Filtres
  activeCategory: CategoryKey;
  searchText: string;
  setSearchText: React.Dispatch<React.SetStateAction<string>>;
  filterTags: string[];
  setFilterTags: React.Dispatch<React.SetStateAction<string[]>>;
  filterEngines: string[];
  setFilterEngines: React.Dispatch<React.SetStateAction<string[]>>;
  filterImpacts: string[];
  setFilterImpacts: React.Dispatch<React.SetStateAction<string[]>>;
  hasActiveFilters: boolean;
  resetFilters: () => void;
  handleCategoryChange: (category: CategoryKey) => void;
  // Données
  loading: boolean;
  actions: CatalogAction[];
  filteredActions: CatalogAction[];
  tagsWithCounts: CatalogTagWithCount[];
  favorites: Set<number>;
  handleToggleFavorite: (actionId: number, e: React.MouseEvent) => Promise<void>;
  // Sélection / drawer action
  selectedAction: CatalogAction | null;
  selectedActionDetail: CatalogActionDetail | null;
  selectedActionCanExecute: boolean;
  selectedActionEnvs: string[];
  selectedActionStats: ActionStats | null;
  statsLoading: boolean;
  drawerVisible: boolean;
  drawerLoading: boolean;
  lastFocusedCardRef: React.RefObject<HTMLElement | null>;
  handleActionClick: (action: CatalogAction, event?: React.MouseEvent) => Promise<void>;
  handleDrawerClose: () => void;
  // Execution wizard / view
  executionWizardOpen: boolean;
  activeExecutionId: number | null;
  setActiveExecutionId: React.Dispatch<React.SetStateAction<number | null>>;
  executionViewId: number | null;
  setExecutionViewId: React.Dispatch<React.SetStateAction<number | null>>;
  parentExecutionId: number | null;
  setParentExecutionId: React.Dispatch<React.SetStateAction<number | null>>;
  setExecutionWizardOpen: React.Dispatch<React.SetStateAction<boolean>>;
  handleExecuteClick: () => void;
  handleExecutionSuccess: (executionId: number, opts?: { isScheduled?: boolean }) => void;
  handleBackToCatalog: () => void;
  handleRemediationSuggestionClick: (suggestion: RemediationSuggestion) => Promise<void>;
}

export function useCatalogState(): UseCatalogStateReturn {
  const { message } = App.useApp();

  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode);

  // Story 8.7: Category state
  const [activeCategory, setActiveCategory] = useState<CategoryKey>('tout');

  const [searchText, setSearchText] = useState('');
  const debouncedQ = useDebounce(searchText, 300);
  const [filterTags, setFilterTags] = useState<string[]>([]);

  // Story 8.7: Multi-select filters (engines and impacts only — Story 18.4: environment removed)
  const [filterEngines, setFilterEngines] = useState<string[]>([]);
  const [filterImpacts, setFilterImpacts] = useState<string[]>([]);

  const [tagsWithCounts, setTagsWithCounts] = useState<CatalogTagWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [actions, setActions] = useState<CatalogAction[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [selectedAction, setSelectedAction] = useState<CatalogAction | null>(null);
  const [selectedActionDetail, setSelectedActionDetail] = useState<CatalogActionDetail | null>(null);
  const [selectedActionCanExecute, setSelectedActionCanExecute] = useState(false);
  const [selectedActionEnvs, setSelectedActionEnvs] = useState<string[]>([]);
  const [selectedActionStats, setSelectedActionStats] = useState<ActionStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [executionWizardOpen, setExecutionWizardOpen] = useState(false);
  const [activeExecutionId, setActiveExecutionId] = useState<number | null>(null);
  // Story 19.1: ExecutionView drawer state
  const [executionViewId, setExecutionViewId] = useState<number | null>(null);
  // Story 9.2, Task 19: Parent execution ID for remediation
  const [parentExecutionId, setParentExecutionId] = useState<number | null>(null);
  const lastFocusedCardRef = useRef<HTMLElement | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Story 8.7: Include category in API call
      // Story 18.4: environment parameter removed (environment = target property)
      // NOTE: Backend API currently supports only single engine/impact value (not arrays)
      const [actionsData, favoritesData, tagsData] = await Promise.all([
        fetchCatalogActions({
          tags: filterTags.length > 0 ? filterTags : undefined,
          q: debouncedQ.trim() || undefined,
          engine: filterEngines.length > 0 ? filterEngines[0] : undefined,
          impact: filterImpacts.length > 0 ? filterImpacts[0] : undefined,
          category: activeCategory !== 'tout' && activeCategory !== 'mes-actions' ? activeCategory : undefined,
        }),
        fetchFavorites().catch(() => [] as FavoriteEntry[]),
        // Story 8.7, AC3: Fetch tags filtered by category
        activeCategory !== 'mes-actions'
          ? fetchCatalogTags(activeCategory !== 'tout' ? activeCategory : undefined).catch((error) => {
              logger.error('Failed to load tags', { error: error instanceof Error ? error.message : String(error) });
              message.warning('Impossible de charger les tags');
              return [] as CatalogTagWithCount[];
            })
          : Promise.resolve([] as CatalogTagWithCount[]),
      ]);
      setActions(actionsData);
      setFavorites(new Set(favoritesData.map((f) => f.action_id)));
      if (activeCategory !== 'mes-actions') setTagsWithCounts(tagsData);
    } catch (error) {
      logger.error('Failed to load catalog', { error: error instanceof Error ? error.message : String(error) });
      message.error('Erreur lors du chargement du catalogue');
    } finally {
      setLoading(false);
    }
  }, [activeCategory, debouncedQ, filterTags, filterEngines, filterImpacts, message]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const hasActiveFilters = useMemo(
    () =>
      filterEngines.length > 0 ||
      filterImpacts.length > 0 ||
      filterTags.length > 0 ||
      (activeCategory !== 'tout' && activeCategory !== 'mes-actions') ||
      searchText.trim().length > 0,
    [filterEngines, filterImpacts, filterTags, activeCategory, searchText],
  );

  const resetFilters = useCallback(() => {
    setSearchText('');
    setFilterTags([]);
    setFilterEngines([]);
    setFilterImpacts([]);
    setActiveCategory('tout');
  }, []);

  const filteredActions = useMemo(() => {
    if (activeCategory === 'mes-actions') {
      return actions.filter((a) => favorites.has(a.id));
    }
    return actions;
  }, [actions, activeCategory, favorites]);

  // Toggle favorite
  const handleToggleFavorite = useCallback(async (actionId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const isFav = favorites.has(actionId);
    try {
      if (isFav) {
        await removeFavorite(actionId);
        setFavorites((prev) => {
          const next = new Set(prev);
          next.delete(actionId);
          return next;
        });
        message.success('Retirée des favoris');
      } else {
        await addFavorite(actionId);
        setFavorites((prev) => new Set(prev).add(actionId));
        message.success('Ajoutée aux favoris');
      }
    } catch {
      message.error('Erreur lors de la mise à jour des favoris');
    }
  }, [favorites, message]);

  // Persist view mode (AC2)
  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
    try {
      localStorage.setItem(CATALOG_VIEW_MODE_KEY, mode);
    } catch {
      // ignore
    }
  }, []);

  // Story 8.7: Handle category change - reset tags when switching categories
  const handleCategoryChange = useCallback((category: CategoryKey) => {
    setActiveCategory(category);
    // Reset tag selection when changing category (tags are category-specific)
    setFilterTags([]);
  }, []);

  // Open action drawer and fetch full detail + stats (Story 3.2, AC1, AC5; Story 8.1)
  const handleActionClick = useCallback(async (action: CatalogAction, event?: React.MouseEvent) => {
    // Store the clicked element for focus return (AC2)
    if (event?.currentTarget) {
      lastFocusedCardRef.current = event.currentTarget as HTMLElement;
    }
    setSelectedAction(action);
    setSelectedActionDetail(null);
    setSelectedActionCanExecute(false);
    setSelectedActionEnvs([]);
    setSelectedActionStats(null);
    setDrawerVisible(true);
    setDrawerLoading(true);
    setStatsLoading(true);

    try {
      // Fetch action detail and stats in parallel (Story 8.1, Task 8.2)
      const [detailResponse, statsResponse] = await Promise.all([
        fetchCatalogActionById(action.id),
        fetchActionStats(action.id).catch(() => null), // Stats are optional, don't fail if unavailable
      ]);
      setSelectedActionDetail(detailResponse.data);
      setSelectedActionCanExecute(detailResponse.can_execute);
      setSelectedActionEnvs(detailResponse.allowed_environments);
      setSelectedActionStats(statsResponse);
    } catch (error) {
      logger.error('Failed to load action detail', { error: error instanceof Error ? error.message : String(error) });
      message.error("Erreur lors du chargement de l'action");
      // Keep drawer open with basic info from list
    } finally {
      setDrawerLoading(false);
      setStatsLoading(false);
    }
  }, [message]);

  // Close drawer and clear state, return focus to card (AC2, Story 3.2)
  const handleDrawerClose = useCallback(() => {
    setDrawerVisible(false);
    setSelectedAction(null);
    setSelectedActionDetail(null);
    setSelectedActionCanExecute(false);
    setSelectedActionEnvs([]);
    setSelectedActionStats(null);
    // Return focus to the card that opened the drawer (AC2)
    if (lastFocusedCardRef.current) {
      // Use setTimeout to ensure focus happens after drawer animation completes
      setTimeout(() => {
        lastFocusedCardRef.current?.focus();
        lastFocusedCardRef.current = null;
      }, 0);
    }
  }, []);

  // Open ExecutionWizard (Story 4.1, Task 7)
  const handleExecuteClick = useCallback(() => {
    setExecutionWizardOpen(true);
  }, []);

  // Handle execution success (Story 4.1, 4.6; Story 19.4 AC1, AC8: close wizard + open ExecutionView)
  const handleExecutionSuccess = useCallback(
    (executionId: number, opts?: { isScheduled?: boolean }) => {
      setExecutionWizardOpen(false);
      setActiveExecutionId(null);
      setSelectedAction(null);
      setSelectedActionDetail(null);
      setDrawerVisible(false);
      // Exécution immédiate uniquement : ouvrir ExecutionView. Pour planifiée, scheduledId ≠ execution_id → getExecution 404
      if (!opts?.isScheduled) {
        setExecutionViewId(executionId);
        logger.info('CatalogPage: Opening ExecutionView after execution created', { executionId });
      }
      loadData();
    },
    [loadData],
  );

  // Back to catalog — close timeline, wizard, and execution view (Story 4.6, Task 4.2; Story 9.2, Task 19; Story 19.1)
  const handleBackToCatalog = useCallback(() => {
    setActiveExecutionId(null);
    setExecutionWizardOpen(false);
    setDrawerVisible(false);
    // Story 19.1: Close ExecutionView drawer
    setExecutionViewId(null);
    // Story 9.2, Task 19: Reset parent execution ID
    setParentExecutionId(null);
    loadData();
  }, [loadData]);

  // Story 9.1, Task 12.4; Story 9.2, Task 19: Handle remediation suggestion click
  const handleRemediationSuggestionClick = useCallback(
    async (suggestion: RemediationSuggestion) => {
      try {
        // Story 9.2 code-review fix: Use functional state update to avoid race condition
        let capturedParentId: number | null = null;

        // Close current execution view and capture parent ID atomically
        setActiveExecutionId((prev) => {
          capturedParentId = prev;
          return null;
        });

        // Load the suggested action details
        const detailResponse = await fetchCatalogActionById(suggestion.action_id);
        setSelectedActionDetail(detailResponse.data);
        setSelectedActionCanExecute(detailResponse.can_execute);
        setSelectedActionEnvs(detailResponse.allowed_environments);

        // Story 9.2 code-review fix: Use captured parent ID from functional update
        setParentExecutionId(capturedParentId);

        // Keep wizard open with new action
        setExecutionWizardOpen(true);
      } catch (error) {
        logger.error('Failed to load suggested action', { error: error instanceof Error ? error.message : String(error) });
        message.error("Erreur lors du chargement de l'action corrective");
      }
    },
    [message],
  );

  return {
    viewMode,
    handleViewModeChange,
    activeCategory,
    searchText,
    setSearchText,
    filterTags,
    setFilterTags,
    filterEngines,
    setFilterEngines,
    filterImpacts,
    setFilterImpacts,
    hasActiveFilters,
    resetFilters,
    handleCategoryChange,
    loading,
    actions,
    filteredActions,
    tagsWithCounts,
    favorites,
    handleToggleFavorite,
    selectedAction,
    selectedActionDetail,
    selectedActionCanExecute,
    selectedActionEnvs,
    selectedActionStats,
    statsLoading,
    drawerVisible,
    drawerLoading,
    lastFocusedCardRef,
    handleActionClick,
    handleDrawerClose,
    executionWizardOpen,
    activeExecutionId,
    setActiveExecutionId,
    executionViewId,
    setExecutionViewId,
    parentExecutionId,
    setParentExecutionId,
    setExecutionWizardOpen,
    handleExecuteClick,
    handleExecutionSuccess,
    handleBackToCatalog,
    handleRemediationSuggestionClick,
  };
}
