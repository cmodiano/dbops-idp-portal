/**
 * CatalogPage — Catalogue actions (Story 3.1, 3.3, 3.5, 4.1, 8.7).
 * State extracted to useCatalogState hook (Story 34.10, SOLID-FE-2).
 */

import { Typography, Input, Row, Col, Empty, Skeleton, Button, Space, Card, Badge, Drawer, theme } from 'antd';
import { AppstoreOutlined, BarsOutlined, SearchOutlined, FilterOutlined, ClearOutlined } from '@ant-design/icons';
import { ActionCard } from '../components/catalog/ActionCard';
import { ActionDrawerPreview } from '../components/catalog/ActionDrawerPreview';
import { ActionTable } from '../components/catalog/ActionTable';
import { ExecutionWizard } from '../components/catalog/ExecutionWizard';
import { ExecutionView } from '../components/execution/ExecutionView';
import { TagCloud } from '../components/catalog/TagCloud';
import { CategoryTabs } from '../components/catalog/CategoryTabs';
import { HorizontalFilters } from '../components/catalog/HorizontalFilters';
import { ActiveFiltersChips } from '../components/catalog/ActiveFiltersChips';
import { useAuth } from '../contexts/AuthContext';
import { useCatalogState } from '../hooks/useCatalogState';
import type { CatalogAction } from '../services/catalog_service';
import type { ActionPreviewData, ActionStats, ImpactLevel } from '../types/api';

const { Title, Text } = Typography;

const contentMaxWidth = 1600;

/** Convert CatalogAction to ActionPreviewData for ActionCard (Story 8.1: optional stats). */
function toPreviewData(action: CatalogAction, stats?: ActionStats | null): ActionPreviewData {
  let impactLevel: ImpactLevel | null = null;
  const impactRules = action.impact_level
    ? null
    : (action as unknown as { impact_rules?: Record<string, { level: ImpactLevel }> }).impact_rules;
  if (impactRules && Object.keys(impactRules).length > 0) {
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
    item_type: action.item_type, // Story 18.2: workflow vs action visual distinction
  };
}

export default function CatalogPage() {
  const { isAuthenticated } = useAuth();
  const { token } = theme.useToken();
  const {
    viewMode, handleViewModeChange,
    activeCategory, handleCategoryChange,
    searchText, setSearchText,
    filterTags, setFilterTags,
    filterEngines, setFilterEngines,
    filterImpacts, setFilterImpacts,
    hasActiveFilters, resetFilters,
    loading, filteredActions, tagsWithCounts, favorites, handleToggleFavorite,
    selectedAction, selectedActionDetail, selectedActionCanExecute,
    selectedActionEnvs, selectedActionStats, statsLoading,
    drawerVisible, drawerLoading,
    handleActionClick, handleDrawerClose, handleExecuteClick,
    executionWizardOpen, activeExecutionId, setActiveExecutionId,
    setExecutionWizardOpen, parentExecutionId, setParentExecutionId,
    handleExecutionSuccess, handleBackToCatalog,
    executionViewId, setExecutionViewId,
    handleRemediationSuggestionClick,
  } = useCatalogState();

  // Story 46.7: Nombre de filtres actifs (category excluant 'tout' et 'mes-actions', tags, engines, impacts)
  const activeFilterCount = [
    activeCategory && !['tout', 'mes-actions'].includes(activeCategory) ? 1 : 0,
    filterTags.length,
    filterEngines.length,
    filterImpacts.length,
  ].reduce((acc, n) => acc + n, 0);

  // Story 46.7: Extra de la Card filtres (Badge + bouton reset)
  const filterCardExtra = (
    <Badge count={activeFilterCount} style={{ backgroundColor: token.colorPrimary }}>
      <Button
        icon={<ClearOutlined />}
        size="large"
        style={{ minHeight: 44 }}
        onClick={resetFilters}
        disabled={activeFilterCount === 0}
      >
        Réinitialiser
      </Button>
    </Badge>
  );

  const renderActionCard = (action: CatalogAction) => (
    <div key={action.id}>
      <ActionCard
        action={toPreviewData(action)}
        onClick={() => handleActionClick(action)}
        isFavorite={favorites.has(action.id)}
        onToggleFavorite={(e) => handleToggleFavorite(action.id, e)}
        showFavoriteButton={isAuthenticated}
      />
    </div>
  );

  const renderSkeleton = () =>
    viewMode === 'list' ? (
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
          <Col key={i} xs={24} sm={12} md={8} lg={8} xl={6} xxl={4}>
            <Card><Skeleton active avatar={{ shape: 'square', size: 'small' }} paragraph={{ rows: 2 }} /></Card>
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
          <Button type="primary" onClick={resetFilters}>Réinitialiser les filtres</Button>
        )}
      </Empty>
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ maxWidth: contentMaxWidth, margin: '0 auto' }}>
        <Title level={2}>Catalogue</Title>

        <CategoryTabs
          activeCategory={activeCategory}
          onCategoryChange={handleCategoryChange}
          favoritesCount={favorites.size}
        />

        {/* Story 46.7: Card filtres avec FilterOutlined + Badge actifs + Reset (AC1, AC3, AC4, AC5) */}
        <Card
          size="small"
          title={
            <Space>
              <FilterOutlined />
              Filtres
            </Space>
          }
          extra={filterCardExtra}
          style={{ marginBottom: 16 }}
        >
          {/* AC3: TagCloud dans la Card pour que le header "Filtres" + FilterOutlined couvre aussi les filtres par tags */}
          {activeCategory !== 'mes-actions' && tagsWithCounts.length > 0 && (
            <TagCloud tags={tagsWithCounts} selectedTags={filterTags} onSelectionChange={setFilterTags} />
          )}
          {activeCategory !== 'mes-actions' && (
            <HorizontalFilters
              selectedEngines={filterEngines}
              selectedImpacts={filterImpacts}
              onEnginesChange={setFilterEngines}
              onImpactsChange={setFilterImpacts}
            />
          )}
          <ActiveFiltersChips
            activeCategory={activeCategory}
            selectedTags={filterTags}
            selectedEngines={filterEngines}
            selectedImpacts={filterImpacts}
            onRemoveCategory={() => handleCategoryChange('tout')}
            onRemoveTag={(tag) => setFilterTags((prev) => prev.filter((t) => t !== tag))}
            onRemoveEngine={(engine) => setFilterEngines((prev) => prev.filter((e) => e !== engine))}
            onRemoveImpact={(impact) => setFilterImpacts((prev) => prev.filter((i) => i !== impact))}
            onClearAll={resetFilters}
          />
        </Card>

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

        <Text type="secondary" aria-live="polite" style={{ display: 'block', marginBottom: 16 }}>
          {loading ? 'Chargement…' : `${filteredActions.length} action${filteredActions.length !== 1 ? 's' : ''}`}
        </Text>

        {filteredActions.length === 0 && !loading ? (
          renderEmpty()
        ) : viewMode === 'grid' ? (
          loading ? (
            renderSkeleton()
          ) : (
            <Row gutter={[16, 16]}>
              {filteredActions.map((action) => (
                <Col key={action.id} xs={24} sm={12} md={8} lg={8} xl={6} xxl={4}>
                  {renderActionCard(action)}
                </Col>
              ))}
            </Row>
          )
        ) : (
          <ActionTable
            actions={filteredActions}
            favorites={favorites}
            loading={loading}
            onActionClick={handleActionClick}
            onToggleFavorite={handleToggleFavorite}
            showFavoriteButton={isAuthenticated}
          />
        )}
      </div>

      <Drawer
        title={selectedAction?.name || 'Detail'}
        placement="right"
        styles={{ wrapper: { width: 480 } }}
        open={drawerVisible}
        onClose={handleDrawerClose}
        keyboard
        aria-label={`Fiche action: ${selectedAction?.name || 'Detail'}`}
        aria-modal="true"
      >
        {drawerLoading ? (
          <Card><Skeleton active avatar={{ shape: 'square', size: 'small' }} paragraph={{ rows: 6 }} /></Card>
        ) : selectedActionDetail ? (
          <ActionDrawerPreview
            action={toPreviewData(selectedActionDetail, selectedActionStats)}
            canExecute={selectedActionCanExecute}
            allowedEnvironments={selectedActionEnvs}
            onExecute={handleExecuteClick}
            statsLoading={statsLoading}
          />
        ) : selectedAction ? (
          <ActionDrawerPreview action={toPreviewData(selectedAction)} statsLoading={statsLoading} />
        ) : null}
      </Drawer>

      <ExecutionWizard
        open={executionWizardOpen}
        action={selectedActionDetail}
        allowedEnvironments={selectedActionEnvs}
        activeExecutionId={activeExecutionId}
        onCancel={() => {
          setActiveExecutionId(null);
          setExecutionWizardOpen(false);
          setParentExecutionId(null);
        }}
        onSuccess={handleExecutionSuccess}
        onBackToCatalog={handleBackToCatalog}
        onSuggestionClick={handleRemediationSuggestionClick}
        parentExecutionId={parentExecutionId}
      />

      <ExecutionView
        executionId={executionViewId}
        onClose={() => {
          setExecutionViewId(null);
          setParentExecutionId(null);
        }}
        onSuggestionClick={handleRemediationSuggestionClick}
      />
    </div>
  );
}
