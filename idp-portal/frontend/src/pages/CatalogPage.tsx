/**
 * CatalogPage - Main catalog page for browsing actions (Story 3.1, 3.3, 3.5, 4.1, 8.7).
 *
 * Features:
 * - Story 8.7: Category tabs navigation (Tout, Provisioning, Patching, etc.)
 * - Story 8.7: Horizontal filters bar replacing lateral drawer (AC7)
 * - Story 8.7: Active filter chips with individual removal (AC6)
 * - Grid/List view toggle (AC2)
 * - ActionCard display with execution_count (AC3)
 * - Favorite toggle with tooltip (AC4, AC12, AC13; Story 3.5)
 * - "Mes actions" tab with favorites only (AC5; Story 9.6 fix)
 * - Search with debounce 300 ms (AC1), server-side + filters (AC2–AC9)
 * - TagCloud for visual multi-tag filtering, filtered by category (Story 3.5, AC1-6; Story 8.7, AC3)
 * - Empty state "Aucune action ne correspond à vos filtres" (AC5)
 * - Counter with aria-live (AC6)
 * - ExecutionWizard integration (Story 4.1, Task 7)
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Typography,
  Input,
  Row,
  Col,
  Empty,
  Skeleton,
  Button,
  Space,
  Card,
  Drawer,
  App,
} from 'antd';
import {
  AppstoreOutlined,
  BarsOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { ActionCard, type ActionCardProps } from '../components/catalog/ActionCard';
import { ActionDrawerPreview } from '../components/catalog/ActionDrawerPreview';
import { ActionTable } from '../components/catalog/ActionTable';
import { ExecutionWizard } from '../components/catalog/ExecutionWizard';
import { TagCloud } from '../components/catalog/TagCloud';
import { CategoryTabs, type CategoryKey } from '../components/catalog/CategoryTabs';
import { HorizontalFilters } from '../components/catalog/HorizontalFilters';
import { ActiveFiltersChips } from '../components/catalog/ActiveFiltersChips';
import { useAuth } from '../contexts/AuthContext';
import { useDebounce } from '../hooks/useDebounce';
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
import type { ActionPreviewData, ActionStats, ImpactLevel, RemediationSuggestion } from '../types/api';
import logger from '../services/logger';

const { Title, Text } = Typography;

/** localStorage key for view mode (AC2). */
const CATALOG_VIEW_MODE_KEY = 'catalog-view-mode';

/** View mode: grid or list (AC2). */
type ViewMode = 'grid' | 'list';

/** Convert CatalogAction to ActionPreviewData for ActionCard (Story 8.1: optional stats). */
function toPreviewData(action: CatalogAction, stats?: ActionStats | null): ActionPreviewData {
  // Extract default impact level from impact_rules if available
  let impactLevel: ImpactLevel | null = null;
  const impactRules = action.impact_level
    ? null
    : (action as unknown as { impact_rules?: Record<string, { level: ImpactLevel }> }).impact_rules;
  if (impactRules && Object.keys(impactRules).length > 0) {
    // Use first environment's level as default display
    const firstEnv = Object.values(impactRules)[0];
    impactLevel = firstEnv?.level || null;
  }

  return {
    name: action.name,
    description: action.description,
    engine: action.engine,
    platform: action.platform,
    impact_level: action.impact_level || impactLevel,
    parameters_schema: action.parameters_schema,
    tags: action.tags,
    execution_count: action.execution_count,
    stats: stats ?? null,
  };
}

function getStoredViewMode(): ViewMode {
  try {
    const stored = localStorage.getItem(CATALOG_VIEW_MODE_KEY);
    if (stored === 'grid' || stored === 'list') return stored;
  } catch {
    // ignore
  }
  return 'grid';
}

export default function CatalogPage() {
  const { message } = App.useApp();
  const { isAuthenticated, isBusinessProfile } = useAuth();
  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode);

  // Story 8.7: Category state (replaces old activeTab)
  const [activeCategory, setActiveCategory] = useState<CategoryKey>('tout');

  const [searchText, setSearchText] = useState('');
  const debouncedQ = useDebounce(searchText, 300);
  const [filterTags, setFilterTags] = useState<string[]>([]);

  // Story 8.7: Multi-select filters (replaces single-select)
  const [filterEngines, setFilterEngines] = useState<string[]>([]);
  const [filterEnvironments, setFilterEnvironments] = useState<string[]>([]);
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
  // Story 9.2, Task 19: Parent execution ID for remediation
  const [parentExecutionId, setParentExecutionId] = useState<number | null>(null);
  const lastFocusedCardRef = useRef<HTMLElement | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Story 8.7: Include category in API call
      // NOTE: Backend API currently supports only single engine/environment/impact value (not arrays)
      // HorizontalFilters uses multi-select UI but we send only the first selected value
      // TODO: Enhance backend to support multi-value filters (e.g., ?engine=Oracle&engine=SQL%20Server)
      const [actionsData, favoritesData, tagsData] = await Promise.all([
        fetchCatalogActions({
          tags: filterTags.length > 0 ? filterTags : undefined,
          q: debouncedQ.trim() || undefined,
          engine: filterEngines.length > 0 ? filterEngines[0] : undefined,
          environment: filterEnvironments.length > 0 ? filterEnvironments[0] : undefined,
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
  }, [activeCategory, debouncedQ, filterTags, filterEngines, filterEnvironments, filterImpacts, message]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const hasActiveFilters =
    filterTags.length > 0 ||
    filterEngines.length > 0 ||
    filterEnvironments.length > 0 ||
    filterImpacts.length > 0 ||
    searchText.trim().length > 0 ||
    (activeCategory !== 'tout' && activeCategory !== 'mes-actions');

  const resetFilters = useCallback(() => {
    setSearchText('');
    setFilterTags([]);
    setFilterEngines([]);
    setFilterEnvironments([]);
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
  const handleToggleFavorite = async (actionId: number, e: React.MouseEvent) => {
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
  };

  // Persist view mode (AC2)
  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
    try {
      localStorage.setItem(CATALOG_VIEW_MODE_KEY, mode);
    } catch {
      // ignore
    }
  };

  // Story 8.7: Handle category change - reset tags when switching categories
  const handleCategoryChange = useCallback((category: CategoryKey) => {
    setActiveCategory(category);
    // Reset tag selection when changing category (tags are category-specific)
    setFilterTags([]);
  }, []);

  // Open action drawer and fetch full detail + stats (Story 3.2, AC1, AC5; Story 8.1)
  const handleActionClick = async (action: CatalogAction, event?: React.MouseEvent) => {
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
      message.error('Erreur lors du chargement de l\'action');
      // Keep drawer open with basic info from list
    } finally {
      setDrawerLoading(false);
      setStatsLoading(false);
    }
  };

  // Close drawer and clear state, return focus to card (AC2, Story 3.2)
  const handleDrawerClose = () => {
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
  };

  // Open ExecutionWizard (Story 4.1, Task 7)
  const handleExecuteClick = useCallback(() => {
    setExecutionWizardOpen(true);
  }, []);

  // Handle execution success (Story 4.1, 4.6) — show timeline in wizard, do not close
  const handleExecutionSuccess = useCallback((executionId: number) => {
    setActiveExecutionId(executionId);
    message.success(`Execution #${executionId} demarree`);
    loadData();
  }, [loadData, message]);

  // Back to catalog — close timeline and wizard (Story 4.6, Task 4.2; Story 9.2, Task 19)
  const handleBackToCatalog = useCallback(() => {
    setActiveExecutionId(null);
    setExecutionWizardOpen(false);
    setDrawerVisible(false);
    // Story 9.2, Task 19: Reset parent execution ID
    setParentExecutionId(null);
    loadData();
  }, [loadData]);

  // Story 9.1, Task 12.4; Story 9.2, Task 19: Handle remediation suggestion click - load suggested action and open wizard
  const handleRemediationSuggestionClick = useCallback(async (suggestion: RemediationSuggestion) => {
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
      message.error('Erreur lors du chargement de l\'action corrective');
    }
  }, [message]);

  // Render action card with favorite button (disabled when not authenticated — Task 5.1)
  // Story 7.1: Use 'business' variant for business profiles (simplified descriptions)
  const renderActionCard = (action: CatalogAction) => {
    const isFav = favorites.has(action.id);
    const preview = toPreviewData(action);
    const cardVariant: ActionCardProps['variant'] = isBusinessProfile ? 'business' : 'default';

    return (
      <div key={action.id}>
        <ActionCard
          action={preview}
          onClick={(e) => handleActionClick(action, e)}
          variant={cardVariant}
          isFavorite={isFav}
          onToggleFavorite={(e) => handleToggleFavorite(action.id, e)}
          showFavoriteButton={isAuthenticated}
        />
      </div>
    );
  };

  // Loading skeleton: cards in grid mode, table skeleton in list mode (AC9, AC11 Story 8.10)
  const renderSkeleton = () =>
    viewMode === 'list' ? (
      /* Story 8.10 AC11: Table loading skeleton - ActionTable handles this via loading prop */
      <ActionTable
        actions={[]}
        favorites={favorites}
        loading={true}
        onActionClick={handleActionClick}
        onToggleFavorite={handleToggleFavorite}
        showFavoriteButton={isAuthenticated}
      />
    ) : (
      <Row gutter={[16, 16]}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Col key={i} xs={24} sm={12} md={8} lg={8} xl={6}>
            <Card>
              <Skeleton active avatar={{ shape: 'square', size: 'small' }} paragraph={{ rows: 2 }} />
            </Card>
          </Col>
        ))}
      </Row>
    );

  const renderEmpty = () => {
    const noResultsFromFilters = !loading && filteredActions.length === 0 && hasActiveFilters && activeCategory !== 'mes-actions';
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          noResultsFromFilters
            ? 'Aucune action ne correspond à vos filtres'
            : activeCategory === 'mes-actions'
              ? "Aucune action dans 'Mes actions'. Ajoutez des favoris pour les retrouver ici."
              : 'Aucune action trouvee'
        }
      >
        {noResultsFromFilters && (
          <Button type="primary" onClick={resetFilters}>
            Réinitialiser les filtres
          </Button>
        )}
      </Empty>
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Catalogue</Title>

      {/* Story 8.7: Category Tabs (AC1, AC2) */}
      <CategoryTabs
        activeCategory={activeCategory}
        onCategoryChange={handleCategoryChange}
        favoritesCount={favorites.size}
      />

      {/* Story 8.7: Horizontal Filters (AC5) - replaces lateral drawer (AC7) */}
      {activeCategory !== 'mes-actions' && (
        <HorizontalFilters
          selectedEngines={filterEngines}
          selectedEnvironments={filterEnvironments}
          selectedImpacts={filterImpacts}
          onEnginesChange={setFilterEngines}
          onEnvironmentsChange={setFilterEnvironments}
          onImpactsChange={setFilterImpacts}
        />
      )}

      {/* Story 8.7: Active Filter Chips (AC6) */}
      <ActiveFiltersChips
        activeCategory={activeCategory}
        selectedTags={filterTags}
        selectedEngines={filterEngines}
        selectedEnvironments={filterEnvironments}
        selectedImpacts={filterImpacts}
        onRemoveCategory={() => setActiveCategory('tout')}
        onRemoveTag={(tag) => setFilterTags((prev) => prev.filter((t) => t !== tag))}
        onRemoveEngine={(engine) => setFilterEngines((prev) => prev.filter((e) => e !== engine))}
        onRemoveEnvironment={(env) => setFilterEnvironments((prev) => prev.filter((e) => e !== env))}
        onRemoveImpact={(impact) => setFilterImpacts((prev) => prev.filter((i) => i !== impact))}
        onClearAll={resetFilters}
      />

      {/* Controls: View toggle + Search */}
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Space.Compact>
          <Button
            type={viewMode === 'grid' ? 'primary' : 'default'}
            icon={<AppstoreOutlined />}
            onClick={() => handleViewModeChange('grid')}
            aria-label="Vue grille"
          />
          <Button
            type={viewMode === 'list' ? 'primary' : 'default'}
            icon={<BarsOutlined />}
            onClick={() => handleViewModeChange('list')}
            aria-label="Vue liste"
          />
        </Space.Compact>
        <Input
          placeholder="Rechercher..."
          prefix={<SearchOutlined />}
          allowClear
          style={{ maxWidth: 300 }}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </Space>

      {/* Tag Cloud for multi-select filtering (Story 3.5, AC1-6; Story 8.7, AC3) */}
      {activeCategory !== 'mes-actions' && tagsWithCounts.length > 0 && (
        <TagCloud
          tags={tagsWithCounts}
          selectedTags={filterTags}
          onSelectionChange={setFilterTags}
        />
      )}

      <Text type="secondary" aria-live="polite" style={{ display: 'block', marginBottom: 16 }}>
        {loading ? 'Chargement…' : `${filteredActions.length} action${filteredActions.length !== 1 ? 's' : ''}`}
      </Text>

      {/* Actions Grid/List (Story 8.10: table view for list mode) */}
      {/* H4 fix: Removed duplicate skeleton for table view - ActionTable handles its own loading state */}
      {filteredActions.length === 0 && !loading ? (
        renderEmpty()
      ) : viewMode === 'grid' ? (
        loading ? (
          renderSkeleton()
        ) : (
          <Row gutter={[16, 16]}>
            {filteredActions.map((action) => (
              <Col key={action.id} xs={24} sm={12} md={8} lg={8} xl={6}>
                {renderActionCard(action)}
              </Col>
            ))}
          </Row>
        )
      ) : (
        /* Story 8.10: ActionTable replaces Space+cards for list view */
        /* H4 fix: ActionTable manages its own loading skeleton */
        <ActionTable
          actions={filteredActions}
          favorites={favorites}
          loading={loading}
          onActionClick={handleActionClick}
          onToggleFavorite={handleToggleFavorite}
          showFavoriteButton={isAuthenticated}
        />
      )}

      {/* Action Detail Drawer (Story 3.2, AC1, AC2, AC4, AC5) */}
      <Drawer
        title={selectedAction?.name || 'Detail'}
        placement="right"
        styles={{ wrapper: { width: 480 } }}
        open={drawerVisible}
        onClose={handleDrawerClose}
        keyboard
        aria-label={`Fiche action: ${selectedAction?.name || 'Detail'}`}
        role="dialog"
        aria-modal="true"
      >
        {drawerLoading ? (
          <Card>
            <Skeleton active avatar={{ shape: 'square', size: 'small' }} paragraph={{ rows: 6 }} />
          </Card>
        ) : selectedActionDetail ? (
          <ActionDrawerPreview
            action={toPreviewData(selectedActionDetail, selectedActionStats)}
            canExecute={selectedActionCanExecute}
            allowedEnvironments={selectedActionEnvs}
            onExecute={handleExecuteClick}
            variant={isBusinessProfile ? 'business' : 'default'}
            statsLoading={statsLoading}
          />
        ) : selectedAction ? (
          <ActionDrawerPreview
            action={toPreviewData(selectedAction)}
            variant={isBusinessProfile ? 'business' : 'default'}
            statsLoading={statsLoading}
          />
        ) : null}
      </Drawer>

      {/* ExecutionWizard + Timeline (Story 4.1, 4.6, Task 4; Story 7.2, Task 4.1; Story 9.1, Task 12; Story 9.2, Task 19) */}
      <ExecutionWizard
        open={executionWizardOpen}
        action={selectedActionDetail}
        allowedEnvironments={selectedActionEnvs}
        activeExecutionId={activeExecutionId}
        onCancel={() => {
          setActiveExecutionId(null);
          setExecutionWizardOpen(false);
          // Story 9.2, Task 19: Reset parent execution ID
          setParentExecutionId(null);
        }}
        onSuccess={handleExecutionSuccess}
        onBackToCatalog={handleBackToCatalog}
        variant={isBusinessProfile ? 'simplified' : 'default'}
        onSuggestionClick={handleRemediationSuggestionClick}
        parentExecutionId={parentExecutionId}
      />
    </div>
  );
}
