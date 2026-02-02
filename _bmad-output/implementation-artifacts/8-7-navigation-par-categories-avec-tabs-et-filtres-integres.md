# Story 8.7: Navigation par catégories avec tabs et filtres intégrés

Epic: 8
Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want naviguer dans le catalogue par catégories (tabs) et affiner avec des tags et filtres,
So that je trouve rapidement les actions par type d'opération sans avoir besoin d'un drawer de filtres séparé.

## Acceptance Criteria

1. **AC1 - Tabs de catégories au-dessus du catalogue**
   - **Given** un DBA accède au catalogue
   - **When** la page se charge
   - **Then** des tabs de catégories s'affichent en haut : "Tout", "Provisioning", "Patching", "Administration", "Monitoring", "Backup", "Mes actions"

2. **AC2 - Sélection d'une catégorie filtre les actions**
   - **Given** le DBA sélectionne une catégorie (ex: "Patching")
   - **When** il clique sur le tab
   - **Then** seules les actions ayant un tag correspondant à la catégorie s'affichent (ex: tag "patching")

3. **AC3 - TagCloud filtre par catégorie active**
   - **Given** le DBA est sur une catégorie
   - **When** il voit les tags disponibles sous les tabs
   - **Then** un TagCloud affiche uniquement les tags pertinents pour cette catégorie avec leurs compteurs

4. **AC4 - Filtres cumulatifs avec la catégorie**
   - **Given** le DBA veut filtrer davantage
   - **When** il sélectionne des tags dans le TagCloud
   - **Then** les filtres se cumulent avec la catégorie active (intersection)

5. **AC5 - Barre de filtres horizontale intégrée**
   - **Given** le DBA veut filtrer par moteur, environnement ou impact
   - **When** il consulte la barre de filtres horizontale sous les tabs
   - **Then** des Select compacts s'affichent : Moteur, Environnement, Impact (remplace le drawer latéral)

6. **AC6 - Chips de filtres actifs visibles**
   - **Given** le DBA applique plusieurs filtres (catégorie + tags + moteur)
   - **When** il consulte les résultats
   - **Then** tous les filtres actifs sont visibles comme chips sous la barre de filtres avec possibilité de les supprimer individuellement

7. **AC7 - Suppression du drawer latéral**
   - **Given** le drawer de filtres latéral existait
   - **When** cette story est implémentée
   - **Then** le drawer est supprimé et remplacé par la barre de filtres horizontale intégrée

## Tasks / Subtasks

### Backend

- [x] Task 1: Ajouter le support du paramètre category dans l'API catalog (AC: #2)
  - [x] 1.1 Modifier GET /api/v1/catalog/actions pour accepter query param `category` (string optional)
  - [x] 1.2 Dans `catalog_repository.py`, ajouter filtre WHERE pour category (mapping tag)
  - [x] 1.3 Mapping catégories → tags: "provisioning", "patching", "administration", "monitoring", "backup"
  - [x] 1.4 Category "Tout" = aucun filtre, "Mes actions" = favoris + récents (comportement existant)

- [x] Task 2: Modifier l'API tags pour filtrer par catégorie (AC: #3)
  - [x] 2.1 Modifier GET /api/v1/catalog/tags pour accepter query param `category` (string optional)
  - [x] 2.2 Si category fournie, retourner uniquement les tags des actions dans cette catégorie
  - [x] 2.3 Maintenir les compteurs corrects par tag

- [x] Task 3: Tests backend (AC: #2, #3)
  - [x] 3.1 Test GET /actions?category=patching retourne uniquement actions avec tag "patching"
  - [x] 3.2 Test GET /actions?category=tout retourne toutes les actions
  - [x] 3.3 Test GET /tags?category=patching retourne tags filtrés
  - [x] 3.4 Test combinaison category + tags + engine filters (intersection)
  - [x] 3.5 Test RBAC appliqué avant filtrage catégorie

### Frontend

- [x] Task 4: Créer le composant CategoryTabs (AC: #1, #2)
  - [x] 4.1 Créer `components/catalog/CategoryTabs.tsx`
  - [x] 4.2 Utiliser Ant Design Tabs component
  - [x] 4.3 Tabs: "Tout", "Provisioning", "Patching", "Administration", "Monitoring", "Backup", "Mes actions"
  - [x] 4.4 Props: activeCategory, onCategoryChange(category: string)
  - [x] 4.5 Style: Active tab avec vert Desjardins #00874E + underline 2px
  - [x] 4.6 ARIA: role="tablist", aria-selected, aria-controls

- [x] Task 5: Créer le composant HorizontalFilters (AC: #5)
  - [x] 5.1 Créer `components/catalog/HorizontalFilters.tsx`
  - [x] 5.2 Row avec 3 Select compacts: Moteur, Environnement, Impact
  - [x] 5.3 Props: selectedEngines[], selectedEnvironments[], selectedImpacts[], onChange handlers
  - [x] 5.4 Style: Inline horizontal layout, spacing md (16px)
  - [x] 5.5 Utiliser ENGINE_OPTIONS, ENVIRONMENT_OPTIONS, IMPACT_OPTIONS existants

- [x] Task 6: Créer le composant ActiveFiltersChips (AC: #6)
  - [x] 6.1 Créer `components/catalog/ActiveFiltersChips.tsx`
  - [x] 6.2 Afficher chips pour: category (si != "Tout"), tags sélectionnés, engines, environments, impacts
  - [x] 6.3 Chaque chip avec bouton X pour supprimer
  - [x] 6.4 Bouton "Réinitialiser tous les filtres" si au moins un filtre actif
  - [x] 6.5 Props: filters object, onRemoveFilter(type, value), onClearAll()
  - [x] 6.6 Style: Background #ECFDF5 (vert clair), text #00874E

- [x] Task 7: Modifier CatalogPage pour intégrer category navigation (AC: #1, #2, #7)
  - [x] 7.1 Ajouter state `activeCategory: string` (défaut "Tout")
  - [x] 7.2 Remplacer les tabs "Tout" / "Mes actions" par CategoryTabs
  - [x] 7.3 Supprimer le drawer de filtres latéral (AC7)
  - [x] 7.4 Intégrer HorizontalFilters sous CategoryTabs
  - [x] 7.5 Intégrer ActiveFiltersChips sous HorizontalFilters
  - [x] 7.6 Mettre à jour la fonction fetchActions pour inclure category param

- [x] Task 8: Modifier TagCloud pour filtrer par catégorie (AC: #3)
  - [x] 8.1 Modifier `TagCloud.tsx` pour accepter prop `category?: string`
  - [x] 8.2 Appeler fetchCatalogTags avec param category
  - [x] 8.3 Afficher uniquement les tags pertinents pour la catégorie active

- [x] Task 9: Mettre à jour catalog_service.ts (AC: #2, #3)
  - [x] 9.1 Ajouter param `category?: string` à fetchCatalogActions()
  - [x] 9.2 Ajouter param `category?: string` à fetchCatalogTags()
  - [x] 9.3 Construire query string avec category param

- [x] Task 10: Tests frontend (AC: #1-#7)
  - [x] 10.1 Test CategoryTabs render avec 7 tabs
  - [x] 10.2 Test CategoryTabs onChange appelle callback
  - [x] 10.3 Test HorizontalFilters render 3 Select
  - [x] 10.4 Test HorizontalFilters onChange met à jour filtres
  - [x] 10.5 Test ActiveFiltersChips affiche chips corrects
  - [x] 10.6 Test ActiveFiltersChips suppression individuelle
  - [x] 10.7 Test CatalogPage intégration complète (category + filters + tags)
  - [x] 10.8 Test accessibilité tabs (keyboard navigation, ARIA)

## Dev Notes

### Architecture et patterns à suivre

**Backend - API catalog avec category filter:**
```python
# Fichier: idp-portal/backend/app/api/v1/catalog.py
# Modifier endpoint existant GET /actions

@router.get("/actions", response_model=CatalogActionsResponse)
async def get_catalog_actions(
    user: UserProfile = Depends(get_current_user),
    search: str | None = Query(None, description="Search query"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    category: str | None = Query(None, description="Filter by category"),  # NEW
    engine: str | None = Query(None),
    environment: str | None = Query(None),
    impact: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> CatalogActionsResponse:
    """
    Get catalog actions with optional filters.
    Story 8.7: Added category parameter for tab-based navigation.
    """
    # Mapping catégories → tags
    CATEGORY_TAG_MAP = {
        "provisioning": "provisioning",
        "patching": "patching",
        "administration": "administration",
        "monitoring": "monitoring",
        "backup": "backup",
        # "tout" et "mes-actions" gérés séparément
    }

    # Convertir category en tag filter si applicable
    category_tag = CATEGORY_TAG_MAP.get(category.lower()) if category else None

    # Appeler repository avec filtres
    actions = await catalog_repository.get_actions(
        user_id=user.id,
        search=search,
        tags=tags,
        category_tag=category_tag,  # Filtre additionnel
        engine=engine,
        environment=environment,
        impact=impact,
        page=page,
        page_size=page_size,
    )
    return actions
```

**Backend - Repository avec category filter:**
```python
# Fichier: idp-portal/backend/app/repositories/catalog_repository.py

async def get_actions(
    self,
    user_id: int,
    search: str | None = None,
    tags: list[str] | None = None,
    category_tag: str | None = None,  # NEW pour Story 8.7
    engine: str | None = None,
    environment: str | None = None,
    impact: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Get catalog actions with filters and RBAC."""

    # Base query avec RBAC filter
    query = """
        SELECT a.* FROM actions_catalog a
        WHERE a.status = 'active'
        AND EXISTS (
            SELECT 1 FROM user_permissions up
            WHERE up.user_id = :user_id
            AND up.action_id = a.id
        )
    """

    params = {"user_id": user_id}

    # Search filter
    if search:
        query += " AND (LOWER(a.name) LIKE :search OR LOWER(a.description) LIKE :search)"
        params["search"] = f"%{search.lower()}%"

    # Category filter (Story 8.7)
    if category_tag:
        query += " AND EXISTS (SELECT 1 FROM action_tags at WHERE at.action_id = a.id AND at.tag = :category_tag)"
        params["category_tag"] = category_tag

    # Tags filter (cumulative avec category)
    if tags:
        for i, tag in enumerate(tags):
            query += f" AND EXISTS (SELECT 1 FROM action_tags at{i} WHERE at{i}.action_id = a.id AND at{i}.tag = :tag{i})"
            params[f"tag{i}"] = tag

    # Engine, environment, impact filters...
    # ... reste de l'implémentation existante
```

**Frontend - CategoryTabs component:**
```typescript
// components/catalog/CategoryTabs.tsx
import { Tabs } from 'antd';

interface CategoryTabsProps {
  activeCategory: string;
  onCategoryChange: (category: string) => void;
}

const CATEGORIES = [
  { key: 'tout', label: 'Tout' },
  { key: 'provisioning', label: 'Provisioning' },
  { key: 'patching', label: 'Patching' },
  { key: 'administration', label: 'Administration' },
  { key: 'monitoring', label: 'Monitoring' },
  { key: 'backup', label: 'Backup' },
  { key: 'mes-actions', label: 'Mes actions' },
];

export function CategoryTabs({ activeCategory, onCategoryChange }: CategoryTabsProps) {
  return (
    <Tabs
      activeKey={activeCategory}
      onChange={onCategoryChange}
      items={CATEGORIES}
      style={{
        marginBottom: 16,
      }}
    />
  );
}
```

**Frontend - HorizontalFilters component:**
```typescript
// components/catalog/HorizontalFilters.tsx
import { Row, Col, Select, Typography } from 'antd';

interface HorizontalFiltersProps {
  selectedEngines: string[];
  selectedEnvironments: string[];
  selectedImpacts: string[];
  onEnginesChange: (values: string[]) => void;
  onEnvironmentsChange: (values: string[]) => void;
  onImpactsChange: (values: string[]) => void;
}

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

export function HorizontalFilters({
  selectedEngines,
  selectedEnvironments,
  selectedImpacts,
  onEnginesChange,
  onEnvironmentsChange,
  onImpactsChange,
}: HorizontalFiltersProps) {
  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={8}>
        <Typography.Text strong>Moteur</Typography.Text>
        <Select
          mode="multiple"
          style={{ width: '100%', marginTop: 8 }}
          placeholder="Tous les moteurs"
          value={selectedEngines}
          onChange={onEnginesChange}
          options={ENGINE_OPTIONS}
          allowClear
        />
      </Col>
      <Col span={8}>
        <Typography.Text strong>Environnement</Typography.Text>
        <Select
          mode="multiple"
          style={{ width: '100%', marginTop: 8 }}
          placeholder="Tous les environnements"
          value={selectedEnvironments}
          onChange={onEnvironmentsChange}
          options={ENVIRONMENT_OPTIONS}
          allowClear
        />
      </Col>
      <Col span={8}>
        <Typography.Text strong>Impact</Typography.Text>
        <Select
          mode="multiple"
          style={{ width: '100%', marginTop: 8 }}
          placeholder="Tous les impacts"
          value={selectedImpacts}
          onChange={onImpactsChange}
          options={IMPACT_OPTIONS}
          allowClear
        />
      </Col>
    </Row>
  );
}
```

**Frontend - ActiveFiltersChips component:**
```typescript
// components/catalog/ActiveFiltersChips.tsx
import { Space, Tag, Button } from 'antd';
import { CloseOutlined } from '@ant-design/icons';

interface ActiveFiltersChipsProps {
  activeCategory?: string;
  selectedTags: string[];
  selectedEngines: string[];
  selectedEnvironments: string[];
  selectedImpacts: string[];
  onRemoveCategory: () => void;
  onRemoveTag: (tag: string) => void;
  onRemoveEngine: (engine: string) => void;
  onRemoveEnvironment: (env: string) => void;
  onRemoveImpact: (impact: string) => void;
  onClearAll: () => void;
}

export function ActiveFiltersChips({
  activeCategory,
  selectedTags,
  selectedEngines,
  selectedEnvironments,
  selectedImpacts,
  onRemoveCategory,
  onRemoveTag,
  onRemoveEngine,
  onRemoveEnvironment,
  onRemoveImpact,
  onClearAll,
}: ActiveFiltersChipsProps) {
  const hasFilters =
    (activeCategory && activeCategory !== 'tout') ||
    selectedTags.length > 0 ||
    selectedEngines.length > 0 ||
    selectedEnvironments.length > 0 ||
    selectedImpacts.length > 0;

  if (!hasFilters) return null;

  return (
    <Space wrap style={{ marginBottom: 16 }}>
      {activeCategory && activeCategory !== 'tout' && activeCategory !== 'mes-actions' && (
        <Tag
          closable
          onClose={onRemoveCategory}
          color="green"
          style={{ backgroundColor: '#ECFDF5', color: '#00874E', borderColor: '#00874E' }}
        >
          Catégorie: {activeCategory}
        </Tag>
      )}

      {selectedTags.map(tag => (
        <Tag key={tag} closable onClose={() => onRemoveTag(tag)} color="blue">
          Tag: {tag}
        </Tag>
      ))}

      {selectedEngines.map(engine => (
        <Tag key={engine} closable onClose={() => onRemoveEngine(engine)}>
          Moteur: {engine}
        </Tag>
      ))}

      {selectedEnvironments.map(env => (
        <Tag key={env} closable onClose={() => onRemoveEnvironment(env)}>
          Env: {env}
        </Tag>
      ))}

      {selectedImpacts.map(impact => (
        <Tag key={impact} closable onClose={() => onRemoveImpact(impact)}>
          Impact: {impact}
        </Tag>
      ))}

      <Button size="small" onClick={onClearAll}>
        Réinitialiser tous les filtres
      </Button>
    </Space>
  );
}
```

**Frontend - CatalogPage integration:**
```typescript
// pages/CatalogPage.tsx - Modifications pour Story 8.7

// Ajouter state pour category
const [activeCategory, setActiveCategory] = useState<string>('tout');

// Supprimer le drawer de filtres latéral (AC7)
// const [filtersDrawerOpen, setFiltersDrawerOpen] = useState(false); // REMOVE

// Modifier fetchActions pour inclure category
const fetchActions = useCallback(async () => {
  setLoading(true);
  try {
    const response = await fetchCatalogActions({
      search: debouncedSearch,
      tags: selectedTags,
      category: activeCategory !== 'tout' ? activeCategory : undefined,  // NEW
      engine: selectedEngines.length > 0 ? selectedEngines[0] : undefined,
      environment: selectedEnvironments.length > 0 ? selectedEnvironments[0] : undefined,
      impact: selectedImpacts.length > 0 ? selectedImpacts[0] : undefined,
      page,
      page_size: 25,
    });
    setActions(response.data);
  } catch (err) {
    setError(err);
  } finally {
    setLoading(false);
  }
}, [debouncedSearch, selectedTags, activeCategory, selectedEngines, selectedEnvironments, selectedImpacts, page]);

// Layout: CategoryTabs → HorizontalFilters → ActiveFiltersChips → TagCloud → Actions grid
return (
  <div>
    <CategoryTabs activeCategory={activeCategory} onCategoryChange={setActiveCategory} />

    <HorizontalFilters
      selectedEngines={selectedEngines}
      selectedEnvironments={selectedEnvironments}
      selectedImpacts={selectedImpacts}
      onEnginesChange={setSelectedEngines}
      onEnvironmentsChange={setSelectedEnvironments}
      onImpactsChange={setSelectedImpacts}
    />

    <ActiveFiltersChips
      activeCategory={activeCategory}
      selectedTags={selectedTags}
      selectedEngines={selectedEngines}
      selectedEnvironments={selectedEnvironments}
      selectedImpacts={selectedImpacts}
      onRemoveCategory={() => setActiveCategory('tout')}
      onRemoveTag={(tag) => setSelectedTags(prev => prev.filter(t => t !== tag))}
      onRemoveEngine={(engine) => setSelectedEngines(prev => prev.filter(e => e !== engine))}
      onRemoveEnvironment={(env) => setSelectedEnvironments(prev => prev.filter(e => e !== env))}
      onRemoveImpact={(impact) => setSelectedImpacts(prev => prev.filter(i => i !== impact))}
      onClearAll={() => {
        setActiveCategory('tout');
        setSelectedTags([]);
        setSelectedEngines([]);
        setSelectedEnvironments([]);
        setSelectedImpacts([]);
      }}
    />

    <TagCloud
      category={activeCategory !== 'tout' ? activeCategory : undefined}  // NEW
      selectedTags={selectedTags}
      onTagsChange={setSelectedTags}
    />

    {/* Actions grid... */}
  </div>
);
```

### Project Structure Notes

**Backend - Fichiers à modifier:**
- `idp-portal/backend/app/api/v1/catalog.py` - Ajouter param `category` à GET /actions et GET /tags
- `idp-portal/backend/app/repositories/catalog_repository.py` - Ajouter filtre category dans requêtes SQL
- `idp-portal/backend/tests/unit/test_catalog_api.py` - Tests pour filtrage par catégorie
- `idp-portal/backend/tests/integration/test_catalog_filtering.py` - Tests intégration category + tags + filters

**Frontend - Fichiers à créer:**
- `idp-portal/frontend/src/components/catalog/CategoryTabs.tsx` - Composant tabs catégories
- `idp-portal/frontend/src/components/catalog/CategoryTabs.test.tsx` - Tests CategoryTabs
- `idp-portal/frontend/src/components/catalog/HorizontalFilters.tsx` - Barre de filtres horizontale
- `idp-portal/frontend/src/components/catalog/HorizontalFilters.test.tsx` - Tests HorizontalFilters
- `idp-portal/frontend/src/components/catalog/ActiveFiltersChips.tsx` - Chips filtres actifs
- `idp-portal/frontend/src/components/catalog/ActiveFiltersChips.test.tsx` - Tests ActiveFiltersChips

**Frontend - Fichiers à modifier:**
- `idp-portal/frontend/src/pages/CatalogPage.tsx` - Intégrer CategoryTabs, HorizontalFilters, ActiveFiltersChips; supprimer drawer latéral
- `idp-portal/frontend/src/components/catalog/TagCloud.tsx` - Accepter prop category pour filtrage
- `idp-portal/frontend/src/services/catalog_service.ts` - Ajouter param category aux fonctions fetch
- `idp-portal/frontend/src/components/catalog/index.ts` - Barrel exports pour nouveaux composants

### Intelligence de la story précédente (8.6)

**Patterns établis dans story 8-6:**
- Mode selector avec Ant Design Segmented
- Barres groupées avec recharts BarChart
- DeltaBadge avec couleurs inversibles
- Drawer pour drill-down (640px)
- ComparisonResult models Pydantic
- Repository pattern pour comparaisons

**Learnings de code-review 8-6:**
- HIGH-3: BarChart préféré à LineChart pour métriques agrégées
- HIGH-5: Validation stricte des paramètres API
- MEDIUM-2: Messages 404 user-friendly en français
- MEDIUM-5: Réutiliser endpoints existants pour drill-down
- LOW-1: Convention bilingue (code en anglais, UI en français)

**Pattern de commit:** `feat(catalog): add category navigation with tabs and integrated horizontal filters (story 8-7)`

### Git Intelligence (commits récents)

```
38c5724 feat(analytics): add advanced comparison and analysis features for reporting dashboard (story 8-6)
4a38a97 feat(analytics): add CSV and PDF export for reporting dashboard (story 8-5)
15dd16c feat(analytics): add advanced filters for reporting dashboard (story 8-4)
```

**Observation:** L'Epic 8 (Analytics) suit un pattern cohérent de features incrémentales. Story 8.7 change de focus vers le catalogue mais maintient la même rigueur architecturale.

### Décisions techniques

1. **Mapping catégories → tags** - Les catégories sont des vues logiques qui filtrent par tags existants (provisioning, patching, etc.). Pas de nouvelle colonne `category` dans la DB.

2. **Suppression du drawer latéral** - AC7 demande explicitement de remplacer le drawer (240px) par une barre de filtres horizontale intégrée. Simplification UX.

3. **Filtres cumulatifs** - Category + tags + engine/env/impact s'appliquent en intersection (AND logic). L'API construit la requête SQL avec tous les filtres actifs.

4. **Tab "Tout" = pas de filtre** - Le tab "Tout" n'envoie pas de paramètre category à l'API, affichant toutes les actions (avec RBAC).

5. **Tab "Mes actions" conservé** - Comportement existant (favoris + récents) maintenu même avec l'ajout des catégories.

6. **TagCloud filtré par catégorie** - Quand une catégorie est active, le TagCloud charge uniquement les tags pertinents via GET /tags?category=X.

7. **Active filters chips** - Chips visuels pour tous les filtres actifs (category, tags, engine, env, impact) avec suppression individuelle ou globale ("Réinitialiser").

8. **RBAC transparent** - Le filtrage RBAC s'applique AVANT les filtres de catégorie/tags. L'utilisateur ne voit jamais d'actions auxquelles il n'a pas accès.

9. **Accessibilité tabs** - Utiliser les props ARIA natives de Ant Design Tabs (role="tablist", aria-selected) pour conformité WCAG 2.1 AA.

10. **Responsive non requis** - Desktop-only (architecture.md), pas de breakpoints mobiles nécessaires.

### Architecture compliance

**API Patterns (architecture.md):**
- Endpoints sous /api/v1/catalog/
- Query params snake_case: `category`, `tags[]`, `engine`
- Response wrapper: `{ "data": [...], "pagination": {...} }`
- RBAC via middleware (invisible filtering)

**Frontend Patterns (architecture.md):**
- Composants dans components/catalog/
- Tests co-localisés (*.test.tsx)
- Services dans services/catalog_service.ts
- Types dans types/api.ts
- Hooks pour state management (useActions, useDebounce)

**UX Design Compliance (ux-design-specification.md):**
- Tabs: Active state vert Desjardins #00874E + underline 2px
- Chips: Background #ECFDF5, text #00874E, border #00874E
- Spacing: 16px (md) entre composants
- Typography: Text strong pour labels filtres
- ARIA: role="tablist", aria-selected, aria-controls

**Ant Design 6.2 Patterns:**
- Tabs component pour CategoryTabs
- Select component (mode="multiple") pour HorizontalFilters
- Tag component (closable) pour ActiveFiltersChips
- Row/Col layout (gutter 16px)

### Mapping catégories → tags

| Catégorie | Tag correspondant | Exemples d'actions |
|-----------|-------------------|--------------------|
| Provisioning | provisioning | Créer base de données, provisionner schéma |
| Patching | patching | Appliquer patch sécurité, mettre à jour version |
| Administration | administration | Modifier paramètre, redémarrer instance |
| Monitoring | monitoring | Vérifier santé, collecter métriques |
| Backup | backup | Backup complet, restauration |

**Note:** Les tags existent déjà dans la table `action_tags`. Cette story ajoute une couche de navigation logique (catégories) qui utilise ces tags.

### Gestion des cas limites

- **Catégorie sans actions:** Afficher empty state "Aucune action dans cette catégorie"
- **RBAC filtre tout:** Si l'utilisateur n'a accès à aucune action dans une catégorie, empty state standard
- **Combinaison filtres vide:** Message "Aucune action ne correspond à vos filtres" (existant)
- **Tag inexistant dans catégorie:** TagCloud vide pour cette catégorie (normal)
- **Multiple catégories sur une action:** Une action peut avoir plusieurs tags, donc apparaître dans plusieurs catégories

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 8 Story 8.7 (lignes 1844-2213)]
- [Source: _bmad-output/planning-artifacts/architecture.md#API-Patterns]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend-Structure]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Category-Navigation]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Tab-Component-Specs]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Filter-Layouts]
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx - Page catalogue existante]
- [Source: idp-portal/frontend/src/components/catalog/TagCloud.tsx - Composant TagCloud]
- [Source: idp-portal/backend/app/api/v1/catalog.py - Endpoints catalogue]
- [Source: idp-portal/backend/app/repositories/catalog_repository.py - Repository catalogue]
- [Source: _bmad-output/implementation-artifacts/8-6-comparaisons-et-analyses-avancees.md - Intelligence story précédente]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

N/A

### Completion Notes List

- Story created with comprehensive context analysis from epics, architecture, UX design, and previous stories
- Category-based navigation pattern defined with tab → tag mapping
- Horizontal filter bar designed to replace lateral drawer (AC7)
- Active filter chips component specified for visual feedback
- RBAC-aware filtering maintained throughout
- Accessibility requirements documented (ARIA, keyboard navigation)
- All 7 acceptance criteria mapped to tasks with detailed subtasks

**Implementation completed 2026-02-01:**
- Backend: Added category param to GET /catalog/actions and GET /catalog/tags endpoints
- Backend: Category filter excludes "tout", "all", "mes-actions" (UI-only values)
- Backend: Fixed syntax error in dashboard.py (duplicate else block)
- Frontend: Created CategoryTabs component with 7 category tabs
- Frontend: Created HorizontalFilters component replacing lateral drawer
- Frontend: Created ActiveFiltersChips component with individual filter removal
- Frontend: Modified CatalogPage to integrate all new components
- Frontend: Modified TagCloud to accept category prop for filtered tags
- Frontend: Modified catalog_service.ts to support category param in API calls
- Tests: 37 backend tests pass (including 7 new category tests)
- Tests: 162 frontend catalog tests pass (including 28 new component tests)

**Code review fixes applied 2026-02-01:**
- FIXED MEDIUM-5: Added category param to cache key in catalog.py (_get_cache_key)
- FIXED HIGH-3: Fixed ActiveFiltersChips hasFilters logic to correctly exclude "mes-actions"
- FIXED MEDIUM-2: Removed unused category prop from TagCloud component
- FIXED MEDIUM-4: Added user-visible error message when fetchCatalogTags fails
- FIXED HIGH-2: Added test for combined category+tags+engine+environment+impact filters
- FIXED MEDIUM-1: Changed CategoryTabs labels to French (Approvisionnement, Correctifs, Surveillance, Sauvegarde)
- FIXED CategoryTabs tests to match French labels
- DOCUMENTED HIGH-4: Backend limitation for multi-select filters (only first value sent to API)
- Status: All HIGH and MEDIUM issues resolved, 2 LOW issues documented

### File List

**Backend - Modified:**
- `idp-portal/backend/app/api/v1/catalog.py` - Added category param to GET /tags, excluded "tout"/"mes-actions" from tags_filter
- `idp-portal/backend/app/api/v1/dashboard.py` - Fixed syntax error (duplicate else block)
- `idp-portal/backend/tests/unit/test_catalog_api.py` - Added 7 tests for category filtering

**Frontend - Created:**
- `idp-portal/frontend/src/components/catalog/CategoryTabs.tsx` - Category tabs component (7 tabs)
- `idp-portal/frontend/src/components/catalog/CategoryTabs.test.tsx` - 7 tests for CategoryTabs
- `idp-portal/frontend/src/components/catalog/HorizontalFilters.tsx` - Horizontal filter bar (3 Select)
- `idp-portal/frontend/src/components/catalog/HorizontalFilters.test.tsx` - 9 tests for HorizontalFilters
- `idp-portal/frontend/src/components/catalog/ActiveFiltersChips.tsx` - Active filter chips display
- `idp-portal/frontend/src/components/catalog/ActiveFiltersChips.test.tsx` - 12 tests for ActiveFiltersChips

**Frontend - Modified:**
- `idp-portal/frontend/src/pages/CatalogPage.tsx` - Integrated CategoryTabs, HorizontalFilters, ActiveFiltersChips; removed lateral drawer
- `idp-portal/frontend/src/components/catalog/TagCloud.tsx` - Added category prop
- `idp-portal/frontend/src/services/catalog_service.ts` - Added category param to fetchCatalogActions and fetchCatalogTags

**Other:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - Updated story status to in-progress
