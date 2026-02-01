/**
 * CatalogPage - Main catalog page for browsing actions (Story 3.1, 3.3, 3.5, 4.1).
 *
 * Features:
 * - Two tabs: Tout (all actions), Mes actions (favorites + recent) — Story 2.23: categories removed
 * - Grid/List view toggle (AC2)
 * - ActionCard display with execution_count (AC3)
 * - Favorite toggle with tooltip (AC4, AC12, AC13; Story 3.5)
 * - "Mes actions" tab with favorites and recent actions (AC5)
 * - Search with debounce 300 ms (AC1), server-side + filters (AC2–AC9)
 * - TagCloud for visual multi-tag filtering (Story 3.5, AC1-6)
 * - Lateral filters panel 240 px (AC2, AC3, AC8): Engine, Environment, Impact
 * - Active filter chips + Réinitialiser (AC4, AC5)
 * - Empty state "Aucune action ne correspond à vos filtres" (AC5)
 * - Counter with aria-live (AC6)
 * - ExecutionWizard integration (Story 4.1, Task 7)
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Typography,
  Tabs,
  Input,
  Row,
  Col,
  Empty,
  Skeleton,
  Button,
  Space,
  Card,
  Drawer,
  Select,
  Tag,
  Tooltip,
  App,
} from 'antd';
import {
  AppstoreOutlined,
  BarsOutlined,
  HeartOutlined,
  HeartFilled,
  SearchOutlined,
  FilterOutlined,
} from '@ant-design/icons';
import { ActionCard, type ActionCardProps } from '../components/catalog/ActionCard';
import { ActionDrawerPreview } from '../components/catalog/ActionDrawerPreview';
import { ExecutionWizard } from '../components/catalog/ExecutionWizard';
import { TagCloud } from '../components/catalog/TagCloud';
import { useAuth } from '../contexts/AuthContext';
import { useDebounce } from '../hooks/useDebounce';
import { useMediaQuery } from '../hooks/useMediaQuery';
import {
  fetchCatalogActions,
  fetchCatalogActionById,
  fetchCatalogTags,
  fetchFavorites,
  fetchRecentActions,
  addFavorite,
  removeFavorite,
  fetchActionStats,
  type CatalogAction,
  type CatalogActionDetail,
  type CatalogTagWithCount,
  type FavoriteEntry,
  type RecentAction,
} from '../services/catalog_service';
import type { ActionPreviewData, ActionStats, ImpactLevel } from '../types/api';

const { Title, Text } = Typography;

/** localStorage key for view mode (AC2). */
const CATALOG_VIEW_MODE_KEY = 'catalog-view-mode';

/** Tab definitions: All actions and My actions (Story 2.23: categories removed, use tags instead). */
const CATALOG_TABS = [
  { key: 'all', label: 'Tout' },
  { key: 'my-actions', label: 'Mes actions' },
];

/** Filter options (Story 3.3, AC2, AC3). */
const ENGINE_OPTIONS = [
  { value: 'Oracle', label: 'Oracle' },
  { value: 'SQL Server', label: 'SQL Server' },
  { value: 'DB2', label: 'DB2' },
];
const ENVIRONMENT_OPTIONS = [
  { value: 'DEV', label: 'DEV' },
  { value: 'QUAL', label: 'QUAL' },
  { value: 'PROD', label: 'PROD' },
];
const IMPACT_OPTIONS = [
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyen' },
  { value: 'high', label: 'Élevé' },
];

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
  const isWide = useMediaQuery(1280);
  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode);
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const debouncedQ = useDebounce(searchText, 300);
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterEngine, setFilterEngine] = useState<string | undefined>(undefined);
  const [filterEnvironment, setFilterEnvironment] = useState<string | undefined>(undefined);
  const [filterImpact, setFilterImpact] = useState<string | undefined>(undefined);
  const [tagsWithCounts, setTagsWithCounts] = useState<CatalogTagWithCount[]>([]);
  const [filtersPanelOpen, setFiltersPanelOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actions, setActions] = useState<CatalogAction[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [recentActions, setRecentActions] = useState<RecentAction[]>([]);
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
  const lastFocusedCardRef = useRef<HTMLElement | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [actionsData, favoritesData, recentData, tagsData] = await Promise.all([
        fetchCatalogActions({
          tags: filterTags.length > 0 ? filterTags : undefined,
          q: debouncedQ.trim() || undefined,
          engine: filterEngine,
          environment: filterEnvironment,
          impact: filterImpact,
        }),
        fetchFavorites().catch(() => [] as FavoriteEntry[]),
        fetchRecentActions(10).catch(() => [] as RecentAction[]),
        activeTab !== 'my-actions' ? fetchCatalogTags().catch(() => [] as CatalogTagWithCount[]) : Promise.resolve([] as CatalogTagWithCount[]),
      ]);
      setActions(actionsData);
      setFavorites(new Set(favoritesData.map((f) => f.action_id)));
      setRecentActions(recentData);
      if (activeTab !== 'my-actions') setTagsWithCounts(tagsData);
    } catch (error) {
      console.error('Failed to load catalog:', error);
      message.error('Erreur lors du chargement du catalogue');
    } finally {
      setLoading(false);
    }
  }, [activeTab, debouncedQ, filterTags, filterEngine, filterEnvironment, filterImpact, message]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const hasActiveFilters = filterTags.length > 0 || filterEngine || filterEnvironment || filterImpact || (searchText.trim().length > 0);
  const resetFilters = useCallback(() => {
    setSearchText('');
    setFilterTags([]);
    setFilterEngine(undefined);
    setFilterEnvironment(undefined);
    setFilterImpact(undefined);
  }, []);

  const filteredActions = useMemo(() => {
    if (activeTab === 'my-actions') {
      const recentIds = new Set(recentActions.map((r) => r.action_id));
      return actions.filter((a) => favorites.has(a.id) || recentIds.has(a.id));
    }
    return actions;
  }, [actions, activeTab, favorites, recentActions]);

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
      console.error('Failed to load action detail:', error);
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

  // Back to catalog — close timeline and wizard (Story 4.6, Task 4.2)
  const handleBackToCatalog = useCallback(() => {
    setActiveExecutionId(null);
    setExecutionWizardOpen(false);
    setDrawerVisible(false);
    loadData();
  }, [loadData]);

  // Render action card with favorite button (disabled when not authenticated — Task 5.1)
  // Story 7.1: Use 'business' variant for business profiles (simplified descriptions)
  const renderActionCard = (action: CatalogAction) => {
    const isFav = favorites.has(action.id);
    const preview = toPreviewData(action);
    const cardVariant: ActionCardProps['variant'] = isBusinessProfile ? 'business' : 'default';

    return (
      <div
        key={action.id}
        tabIndex={0}
        role="button"
        aria-label={`Voir détails: ${action.name}`}
        onClick={(e) => handleActionClick(action, e)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleActionClick(action, e as unknown as React.MouseEvent);
          }
        }}
      >
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

  // Loading skeleton: cards in grid mode, rows in list mode (AC9)
  const renderSkeleton = () =>
    viewMode === 'list' ? (
      <Space orientation="vertical" style={{ width: '100%' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <Skeleton active paragraph={{ rows: 1 }} />
          </Card>
        ))}
      </Space>
    ) : (
      <Row gutter={[16, 16]}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Col key={i} xs={24} sm={12} lg={8} xl={6}>
            <Card>
              <Skeleton active avatar={{ shape: 'square', size: 'small' }} paragraph={{ rows: 2 }} />
            </Card>
          </Col>
        ))}
      </Row>
    );

  const renderEmpty = () => {
    const noResultsFromFilters = !loading && filteredActions.length === 0 && hasActiveFilters && activeTab !== 'my-actions';
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          noResultsFromFilters
            ? 'Aucune action ne correspond à vos filtres'
            : activeTab === 'my-actions'
              ? "Aucune action dans 'Mes actions'. Ajoutez des favoris ou executez des actions."
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

  const renderFiltersPanel = () => (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Text strong>Moteur</Text>
      <Select
        placeholder="Moteur"
        style={{ width: '100%' }}
        value={filterEngine ?? undefined}
        onChange={(v) => setFilterEngine(v ?? undefined)}
        options={ENGINE_OPTIONS}
        allowClear
      />
      <Text strong>Environnement</Text>
      <Select
        placeholder="Environnement"
        style={{ width: '100%' }}
        value={filterEnvironment ?? undefined}
        onChange={(v) => setFilterEnvironment(v ?? undefined)}
        options={ENVIRONMENT_OPTIONS}
        allowClear
      />
      <Text strong>Impact</Text>
      <Select
        placeholder="Impact"
        style={{ width: '100%' }}
        value={filterImpact ?? undefined}
        onChange={(v) => setFilterImpact(v ?? undefined)}
        options={IMPACT_OPTIONS}
        allowClear
      />
    </Space>
  );

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Catalogue</Title>

      <Row gutter={24} wrap={false}>
        {/* Sidebar 240px (AC2, AC8) — inline when >= 1280px, Drawer when narrow */}
        {isWide && (
          <Col flex="0 0 240px" style={{ minWidth: 240 }}>
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>Filtres</Text>
              {renderFiltersPanel()}
            </div>
          </Col>
        )}

        <Col flex="1" style={{ minWidth: 0 }}>
          {/* Controls: View toggle + Search */}
          <Space style={{ marginBottom: 8, width: '100%', justifyContent: 'space-between' }} wrap>
            <Space.Compact>
              {!isWide && (
                <Button
                  icon={<FilterOutlined />}
                  onClick={() => setFiltersPanelOpen(true)}
                  aria-label="Ouvrir les filtres"
                >
                  Filtres
                </Button>
              )}
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

          {/* Chips filtres actifs + Réinitialiser (AC4, AC5) */}
          {(filterTags.length > 0 || filterEngine || filterEnvironment || filterImpact) && (
            <Space style={{ marginBottom: 8 }} wrap>
              {filterTags.map((tag) => (
                <Tag
                  key={tag}
                  closable
                  onClose={() => setFilterTags((prev) => prev.filter((t) => t !== tag))}
                >
                  Tag: {tag}
                </Tag>
              ))}
              {filterEngine && (
                <Tag closable onClose={() => setFilterEngine(undefined)}>
                  Moteur: {ENGINE_OPTIONS.find((o) => o.value === filterEngine)?.label ?? filterEngine}
                </Tag>
              )}
              {filterEnvironment && (
                <Tag closable onClose={() => setFilterEnvironment(undefined)}>
                  Env: {filterEnvironment}
                </Tag>
              )}
              {filterImpact && (
                <Tag closable onClose={() => setFilterImpact(undefined)}>
                  Impact: {IMPACT_OPTIONS.find((o) => o.value === filterImpact)?.label ?? filterImpact}
                </Tag>
              )}
              <Button type="link" size="small" onClick={resetFilters}>
                Réinitialiser les filtres
              </Button>
            </Space>
          )}

          {/* Catalog Tabs (Story 2.23: categories removed, use tags for filtering) */}
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={CATALOG_TABS.map((tab) => ({
              key: tab.key,
              label: (
                <span>
                  {tab.key === 'my-actions' && <HeartOutlined style={{ marginRight: 4 }} />}
                  {tab.key === 'my-actions'
                    ? `Mes actions${favorites.size > 0 ? ` (${favorites.size})` : ''}`
                    : tab.label}
                </span>
              ),
            }))}
            style={{ marginBottom: 16 }}
          />

          {/* Tag Cloud for multi-select filtering (Story 3.5, AC1-6) */}
          {activeTab !== 'my-actions' && tagsWithCounts.length > 0 && (
            <TagCloud
              tags={tagsWithCounts}
              selectedTags={filterTags}
              onSelectionChange={setFilterTags}
            />
          )}

          <Text type="secondary" aria-live="polite" style={{ display: 'block', marginBottom: 16 }}>
            {loading ? 'Chargement…' : `${filteredActions.length} action${filteredActions.length !== 1 ? 's' : ''}`}
          </Text>

          {/* Actions Grid/List */}
          {loading ? (
            renderSkeleton()
          ) : filteredActions.length === 0 ? (
            renderEmpty()
          ) : viewMode === 'grid' ? (
            <Row gutter={[16, 16]}>
              {filteredActions.map((action) => (
                <Col key={action.id} xs={24} sm={12} lg={8} xl={6}>
                  {renderActionCard(action)}
                </Col>
              ))}
            </Row>
          ) : (
            <Space orientation="vertical" style={{ width: '100%' }}>
              {filteredActions.map((action) => renderActionCard(action))}
            </Space>
          )}

          {/* "Mes actions" recent section */}
          {activeTab === 'my-actions' && recentActions.length > 0 && (
            <div style={{ marginTop: 32 }}>
              <Title level={4}>Actions recentes</Title>
              <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
                Vos dernieres executions
              </Text>
              <Row gutter={[16, 16]}>
                {recentActions.map((recent) => {
                  const action = actions.find((a) => a.id === recent.action_id);
                  if (!action) return null;
                  return (
                    <Col key={recent.action_id} xs={24} sm={12} lg={8} xl={6}>
                      {renderActionCard(action)}
                    </Col>
                  );
                })}
              </Row>
            </div>
          )}
        </Col>
      </Row>

      {/* Filtres panel Drawer (AC8: under 1280px) */}
      <Drawer
        title="Filtres"
        placement="left"
        styles={{ wrapper: { width: 240 } }}
        open={filtersPanelOpen && !isWide}
        onClose={() => setFiltersPanelOpen(false)}
        aria-label="Panneau de filtres"
      >
        {renderFiltersPanel()}
      </Drawer>

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

      {/* ExecutionWizard + Timeline (Story 4.1, 4.6, Task 4; Story 7.2, Task 4.1) */}
      <ExecutionWizard
        open={executionWizardOpen}
        action={selectedActionDetail}
        allowedEnvironments={selectedActionEnvs}
        activeExecutionId={activeExecutionId}
        onCancel={() => {
          setActiveExecutionId(null);
          setExecutionWizardOpen(false);
        }}
        onSuccess={handleExecutionSuccess}
        onBackToCatalog={handleBackToCatalog}
        variant={isBusinessProfile ? 'simplified' : 'default'}
      />
    </div>
  );
}
