# Story 8.10: Vue liste en tableau avec colonnes pour le catalogue

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want voir la vue liste du catalogue sous forme de tableau avec des colonnes correspondant aux champs des cards,
So that je peux comparer rapidement plusieurs actions et accéder aux informations importantes sans ouvrir chaque card.

## Acceptance Criteria

1. **AC1 - Affichage du tableau en vue liste**
   - **Given** un DBA sélectionne la vue liste dans le catalogue
   - **When** la page affiche les actions
   - **Then** un tableau Ant Design s'affiche avec des colonnes : Action (nom + icône), Description, Impact, Tags, Moteur, Exécutions, Favori, Actions

2. **AC2 - Colonne "Action" avec icône et nom**
   - **Given** le DBA consulte le tableau
   - **When** il voit la colonne "Action"
   - **Then** elle affiche l'icône (moteur ou workflow) et le nom de l'action en gras

3. **AC3 - Colonne "Description" tronquée**
   - **Given** le DBA consulte la colonne "Description"
   - **When** il voit le contenu
   - **Then** la description est tronquée à 2 lignes avec ellipsis et tooltip au survol pour voir le texte complet

4. **AC4 - Colonne "Impact" avec indicateur coloré**
   - **Given** le DBA consulte la colonne "Impact"
   - **When** il voit les valeurs
   - **Then** l'ImpactIndicator s'affiche avec le même code couleur que dans les cards (triple coding)

5. **AC5 - Colonne "Tags" avec limite affichage**
   - **Given** le DBA consulte la colonne "Tags"
   - **When** il voit les tags
   - **Then** les 3 premiers tags sont affichés avec un "+N" si d'autres tags existent (comme dans les cards)

6. **AC6 - Colonne "Exécutions" formatée**
   - **Given** le DBA consulte la colonne "Exécutions"
   - **When** il voit le nombre
   - **Then** le format est "N exécution(s)" comme dans les cards

7. **AC7 - Colonne "Favori" interactive**
   - **Given** le DBA consulte la colonne "Favori"
   - **When** il voit l'icône
   - **Then** un bouton avec icône cœur permet de toggle le favori (même comportement que dans les cards)

8. **AC8 - Colonne "Actions" avec bouton détails**
   - **Given** le DBA consulte la colonne "Actions"
   - **When** il voit les boutons
   - **Then** un bouton "Voir détails" ouvre le drawer avec ActionDrawerPreview (même comportement que clic sur card)

9. **AC9 - Tri des colonnes**
   - **Given** le DBA veut trier les actions
   - **When** il clique sur un header de colonne
   - **Then** le tri s'applique sur cette colonne (nom, moteur, exécutions, impact)

10. **AC10 - Survol de ligne**
    - **Given** le DBA survole une ligne du tableau
    - **When** il passe la souris
    - **Then** la ligne est surlignée pour indiquer qu'elle est cliquable

11. **AC11 - Skeleton loading pour tableau**
    - **Given** les données sont en chargement
    - **When** viewMode === 'list'
    - **Then** le skeleton loading affiche des lignes de tableau (pas des cards)

12. **AC12 - Responsive design**
    - **Given** l'utilisateur consulte le tableau sur mobile
    - **When** la largeur d'écran < 768px
    - **Then** certaines colonnes sont masquées ou combinées (Description et Tags masqués, Actions réduit)

## Tasks / Subtasks

### Frontend

- [x] Task 1: Créer composant ActionTable (AC: #1, #11)
  - [x] 1.1 Créer `components/catalog/ActionTable.tsx`
  - [x] 1.2 Props: `actions: CatalogAction[]`, `favorites: Set<number>`, `loading: boolean`, `onActionClick: (action) => void`, `onToggleFavorite: (id, e) => void`
  - [x] 1.3 Utiliser Ant Design Table avec pagination (pageSize: 20)
  - [x] 1.4 Ajouter loading skeleton avec Table loading prop
  - [x] 1.5 Définir rowKey={record => record.id}
  - [x] 1.6 Ajouter onRow pour click handler (ouvre drawer)

- [x] Task 2: Colonne "Action" avec icône et nom (AC: #2)
  - [x] 2.1 Créer fonction `getActionIcon(action: CatalogAction): ReactNode`
  - [x] 2.2 Si item_type === 'workflow' → ApartmentOutlined (purple #722ed1)
  - [x] 2.3 Sinon utiliser engine: Oracle → DatabaseOutlined, SQL Server → CloudServerOutlined, DB2 → HddOutlined
  - [x] 2.4 Render: Space horizontal avec icon (fontSize: 18px) + Text strong (name)
  - [x] 2.5 Colonne non masquable (fixed: 'left' optionnel pour scroll horizontal)

- [x] Task 3: Colonne "Description" tronquée (AC: #3)
  - [x] 3.1 Utiliser Typography.Paragraph avec ellipsis={{ rows: 2 }}
  - [x] 3.2 Ajouter Tooltip avec description complète au survol
  - [x] 3.3 Width: 300px minimum pour lisibilité
  - [x] 3.4 Responsive: masquer sur mobile (responsive: ['md'])

- [x] Task 4: Colonne "Impact" (AC: #4)
  - [x] 4.1 Importer ImpactIndicator existant
  - [x] 4.2 Render: `<ImpactIndicator level={record.impact_level} size="small" />`
  - [x] 4.3 Ajouter tri (sorter) par niveau d'impact: low=1, medium=2, high=3, critical=4
  - [x] 4.4 Width: 100px, align: 'center'

- [x] Task 5: Colonne "Tags" (AC: #5)
  - [x] 5.1 Créer fonction `renderTags(tags: string[]): ReactNode`
  - [x] 5.2 Afficher max 3 tags comme dans ActionCard (Tag composant Ant)
  - [x] 5.3 Si tags.length > 3, afficher "+N" dans un Tooltip listant tous les tags
  - [x] 5.4 Style tags: borderRadius 16px, pastel colors cohérentes avec ActionCard
  - [x] 5.5 Width: 200px minimum, responsive: masquer sur mobile

- [x] Task 6: Colonne "Moteur" (AC: #2, #9)
  - [x] 6.1 Render: `record.engine || 'N/A'`
  - [x] 6.2 Ajouter tri (sorter) alphabétique
  - [x] 6.3 Width: 120px

- [x] Task 7: Colonne "Exécutions" (AC: #6, #9)
  - [x] 7.1 Render: `${record.execution_count ?? 0} exécution(s)`
  - [x] 7.2 Ajouter tri (sorter) numérique
  - [x] 7.3 Align: 'right'
  - [x] 7.4 Width: 120px

- [x] Task 8: Colonne "Favori" (AC: #7)
  - [x] 8.1 Button avec icon HeartOutlined (non favori) ou HeartFilled (favori)
  - [x] 8.2 Color: token.colorError si favori, token.colorTextSecondary sinon
  - [x] 8.3 onClick: appeler onToggleFavorite(record.id, e) avec e.stopPropagation()
  - [x] 8.4 Aria-label: "Ajouter aux favoris" ou "Retirer des favoris"
  - [x] 8.5 Width: 80px, align: 'center'

- [x] Task 9: Colonne "Actions" avec bouton détails (AC: #8)
  - [x] 9.1 Button "Voir détails" avec icon EyeOutlined
  - [x] 9.2 Type: 'link', size: 'small'
  - [x] 9.3 onClick: appeler onActionClick(record) avec e.stopPropagation()
  - [x] 9.4 Width: 120px, align: 'center'

- [x] Task 10: Implémentation tri des colonnes (AC: #9)
  - [x] 10.1 Ajouter sorter: true pour colonnes: Action (nom), Moteur, Impact, Exécutions
  - [x] 10.2 Tri Impact: mapper level → number (low=1, medium=2, high=3, critical=4)
  - [x] 10.3 Tri par défaut: nom alphabétique ascendant
  - [x] 10.4 onChange handler pour persister tri dans state (optionnel)

- [x] Task 11: Hover effect ligne (AC: #10)
  - [x] 11.1 Configurer Table rowClassName avec hover style
  - [x] 11.2 CSS: cursor: pointer sur ligne entière
  - [x] 11.3 Hover background: token.colorBgTextHover (dark/light theme)
  - [x] 11.4 Transition smooth pour UX fluide

- [x] Task 12: Intégrer ActionTable dans CatalogPage (AC: #1)
  - [x] 12.1 Importer ActionTable dans CatalogPage.tsx
  - [x] 12.2 Modifier render conditionnel viewMode (ligne 482+)
  - [x] 12.3 Si viewMode === 'list', afficher ActionTable au lieu de Space
  - [x] 12.4 Passer props: actions={filteredActions}, favorites={favorites}, loading={loading}
  - [x] 12.5 Passer handlers: onActionClick={handleActionClick}, onToggleFavorite={handleToggleFavorite}

- [x] Task 13: Skeleton loading pour table (AC: #11)
  - [x] 13.1 Dans ActionTable, si loading === true, passer loading prop à Table
  - [x] 13.2 Ant Design Table gère skeleton automatiquement avec loading={true}
  - [x] 13.3 Vérifier rendu skeleton cohérent avec design system

- [x] Task 14: Responsive design colonnes (AC: #12)
  - [x] 14.1 Colonne Description: responsive={['md']} (masquer sur mobile)
  - [x] 14.2 Colonne Tags: responsive={['md']} (masquer sur mobile)
  - [x] 14.3 Colonne Actions: réduire label sur mobile (icon seul)
  - [x] 14.4 Table scroll horizontal si nécessaire: scroll={{ x: 'max-content' }}

- [x] Task 15: Tests frontend ActionTable (AC: #1-#12)
  - [x] 15.1 Créer `components/catalog/ActionTable.test.tsx`
  - [x] 15.2 Test affiche toutes les colonnes attendues
  - [x] 15.3 Test colonne Action avec icône et nom
  - [x] 15.4 Test colonne Description tronquée avec tooltip
  - [x] 15.5 Test colonne Impact avec ImpactIndicator
  - [x] 15.6 Test colonne Tags (max 3 + "+N")
  - [x] 15.7 Test colonne Favori toggle
  - [x] 15.8 Test colonne Actions bouton détails
  - [x] 15.9 Test tri des colonnes
  - [x] 15.10 Test hover effet ligne
  - [x] 15.11 Test click ligne ouvre drawer
  - [x] 15.12 Test skeleton loading

- [x] Task 16: Tests intégration CatalogPage avec table (AC: #1, #11, #12)
  - [x] 16.1 Modifier `pages/CatalogPage.test.tsx`
  - [x] 16.2 Test viewMode='list' affiche ActionTable
  - [x] 16.3 Test ActionTable reçoit filteredActions
  - [x] 16.4 Test ActionTable reçoit favorites Set
  - [x] 16.5 Test ActionTable loading pendant fetch
  - [x] 16.6 Test click ligne table ouvre drawer
  - [x] 16.7 Test toggle favori depuis table

## Dev Notes

### Architecture et patterns à suivre

**Pattern de colonne Action avec icône:**
```typescript
// components/catalog/ActionTable.tsx

const getActionIcon = (action: CatalogAction): React.ReactNode => {
  const iconStyle = { fontSize: 18 };

  if (action.item_type === 'workflow') {
    return <ApartmentOutlined style={{ ...iconStyle, color: '#722ed1' }} />;
  }

  switch (action.engine) {
    case 'Oracle':
      return <DatabaseOutlined style={iconStyle} />;
    case 'SQL Server':
      return <CloudServerOutlined style={iconStyle} />;
    case 'DB2':
      return <HddOutlined style={iconStyle} />;
    default:
      return <AppstoreOutlined style={iconStyle} />;
  }
};

// Dans colonnes:
{
  title: 'Action',
  dataIndex: 'name',
  key: 'name',
  sorter: (a, b) => a.name.localeCompare(b.name),
  render: (_: string, record: CatalogAction) => (
    <Space>
      {getActionIcon(record)}
      <Typography.Text strong>{record.name}</Typography.Text>
    </Space>
  ),
  width: 250,
}
```

**Pattern de colonne Description avec tooltip:**
```typescript
{
  title: 'Description',
  dataIndex: 'description',
  key: 'description',
  render: (text: string | null) => {
    if (!text) return <Typography.Text type="secondary">Aucune description</Typography.Text>;

    return (
      <Tooltip title={text}>
        <Typography.Paragraph
          ellipsis={{ rows: 2 }}
          style={{ margin: 0 }}
        >
          {text}
        </Typography.Paragraph>
      </Tooltip>
    );
  },
  width: 300,
  responsive: ['md'], // Masquer sur mobile
}
```

**Pattern de colonne Tags avec limite:**
```typescript
const renderTags = (tags: string[] | undefined): React.ReactNode => {
  if (!tags || tags.length === 0) {
    return <Typography.Text type="secondary">Aucun tag</Typography.Text>;
  }

  const visibleTags = tags.slice(0, 3);
  const hiddenCount = tags.length - 3;

  return (
    <Space size={4} wrap>
      {visibleTags.map((tag, idx) => (
        <Tag key={idx} style={{ borderRadius: 16 }}>
          {tag}
        </Tag>
      ))}
      {hiddenCount > 0 && (
        <Tooltip title={tags.slice(3).join(', ')}>
          <Tag style={{ borderRadius: 16 }}>+{hiddenCount}</Tag>
        </Tooltip>
      )}
    </Space>
  );
};

// Dans colonnes:
{
  title: 'Tags',
  dataIndex: 'tags',
  key: 'tags',
  render: renderTags,
  width: 200,
  responsive: ['md'], // Masquer sur mobile
}
```

**Pattern de colonne Impact avec tri:**
```typescript
const getImpactSortValue = (level: ImpactLevel | null): number => {
  const mapping: Record<ImpactLevel, number> = {
    low: 1,
    medium: 2,
    high: 3,
    critical: 4,
  };
  return level ? mapping[level] : 0;
};

// Dans colonnes:
{
  title: 'Impact',
  dataIndex: 'impact_level',
  key: 'impact_level',
  sorter: (a, b) => getImpactSortValue(a.impact_level) - getImpactSortValue(b.impact_level),
  render: (level: ImpactLevel | null) => {
    if (!level) return <Typography.Text type="secondary">N/A</Typography.Text>;
    return <ImpactIndicator level={level} size="small" />;
  },
  width: 100,
  align: 'center',
}
```

**Pattern de colonne Favori:**
```typescript
{
  title: 'Favori',
  key: 'favorite',
  render: (_: unknown, record: CatalogAction) => {
    const isFavorite = favorites.has(record.id);
    return (
      <Button
        type="text"
        icon={isFavorite ? <HeartFilled /> : <HeartOutlined />}
        onClick={(e) => {
          e.stopPropagation(); // Empêcher ouverture drawer
          onToggleFavorite(record.id, e);
        }}
        style={{
          color: isFavorite ? token.colorError : token.colorTextSecondary,
        }}
        aria-label={isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
      />
    );
  },
  width: 80,
  align: 'center',
}
```

**Pattern de hover effet:**
```typescript
// Dans ActionTable component
<Table
  columns={columns}
  dataSource={actions}
  loading={loading}
  rowKey={(record) => record.id}
  onRow={(record) => ({
    onClick: () => onActionClick(record),
    style: { cursor: 'pointer' },
  })}
  rowClassName={() => 'catalog-table-row'} // Classe CSS pour hover
  pagination={{
    pageSize: 20,
    showSizeChanger: true,
    showTotal: (total) => `${total} action(s)`,
  }}
  scroll={{ x: 'max-content' }} // Scroll horizontal si nécessaire
/>

// CSS associé (dans styles ou theme)
.catalog-table-row:hover {
  background-color: var(--ant-color-bg-text-hover) !important;
  transition: background-color 0.2s ease;
}
```

**Intégration dans CatalogPage:**
```typescript
// pages/CatalogPage.tsx - Modification du render conditionnel (ligne ~482)

{viewMode === 'grid' ? (
  <Row gutter={[16, 16]}>
    {filteredActions.map((action) => (
      <Col key={action.id} xs={24} sm={12} lg={8} xl={6}>
        {renderActionCard(action)}
      </Col>
    ))}
  </Row>
) : viewMode === 'list' ? (
  <ActionTable
    actions={filteredActions}
    favorites={favorites}
    loading={loading}
    onActionClick={handleActionClick}
    onToggleFavorite={handleToggleFavorite}
  />
) : (
  // Ancien code pour 'list' avec Space + cards (si on garde compatibilité)
  <Space direction="vertical" style={{ width: '100%' }}>
    {filteredActions.map((action) => renderActionCard(action))}
  </Space>
)}
```

### Project Structure Notes

**Frontend - Fichiers à créer:**
- `idp-portal/frontend/src/components/catalog/ActionTable.tsx` - Composant Table pour vue liste
- `idp-portal/frontend/src/components/catalog/ActionTable.test.tsx` - Tests du composant

**Frontend - Fichiers à modifier:**
- `idp-portal/frontend/src/pages/CatalogPage.tsx` - Intégrer ActionTable dans render conditionnel viewMode
- `idp-portal/frontend/src/pages/CatalogPage.test.tsx` - Tests pour table view
- `idp-portal/frontend/src/components/catalog/ActionTable.css` (optionnel) - Styles hover si nécessaire

**Composants réutilisés (pas de modification):**
- `ImpactIndicator` - Déjà existant pour affichage impact
- `ActionDrawerPreview` - Ouverture drawer au clic ligne (même comportement que cards)

### Intelligence de la story précédente (8.9)

**Patterns établis dans story 8-9:**
- ExecutionsTabs pour navigation avec RBAC
- Pattern tabs Ant Design avec style cohérent (theme, indicator)
- Colonne conditionnelle "Utilisateur" basée sur scope
- Conservation état (tri) lors changement de vue
- Tests exhaustifs (7 backend + 41 frontend)

**Learnings de code-review 8-9:**
- Design tokens (token.colorError, token.colorTextSecondary) au lieu de hardcoded colors
- Regex validation pour query params
- RBAC fallback sécurisé backend
- ThemeProvider requirement dans tests (renderWithTheme helper)
- Comprehensive test coverage (100% passing)

**Pattern de commit:** `feat(executions): add tabs for all executions and my executions with RBAC filtering (story 8-9)`

### Git Intelligence (commits récents)

```
a0f2e61 feat(executions): add tabs for all executions and my executions with RBAC filtering (story 8-9)
e0ed14d feat(executions): move approvals to executions page and add notification bell to top bar (story 8-8)
e9f4845 feat(catalog): add category navigation with tabs and integrated horizontal filters (story 8-7)
38c5724 feat(analytics): add advanced comparison and analysis features for reporting dashboard (story 8-6)
4a38a97 feat(analytics): add CSV and PDF export for reporting dashboard (story 8-5)
```

**Observation:** Epic 8 suit un pattern cohérent de features UX incrémentales. Story 8.10 ajoute une vue table au catalogue pour faciliter la comparaison d'actions.

### Analyse du code existant

**CatalogPage.tsx structure actuelle (lignes 482-493):**
- ViewMode state: 'grid' | 'list' (persisted localStorage)
- Grid mode: Row + Col Ant Design responsive
- List mode actuel: Space vertical avec ActionCard (pas encore table)
- Cette story transforme le list mode en vue table

**ActionCard composant (ActionCard.tsx):**
- Champs affichés: icon, name, description (2 lines), impact, tags (max 3), execution_count, favorite button
- Layout: Flex vertical avec header (icon+name+impact), description, tags, footer (count+favorite)
- Triple coding impact: couleur + icône + label (ImpactIndicator)

**CategoryTabs et filtres (CatalogPage.tsx lignes 185-208):**
- Active filters detection: tags, engines, environments, impacts, searchText, category
- Client-side "Mes actions" filter: favorites + recent
- API filters envoyés backend sauf "Mes actions"

**ImpactIndicator (ImpactIndicator.tsx):**
- Levels: low, medium, high, critical
- Triple coding: Tag avec color + icon + label FR
- Size: 'small' (12px) ou 'default'

### Décisions techniques

1. **Table View remplace List View** - Le viewMode 'list' affichera désormais ActionTable au lieu de Space+Cards. Ancien comportement (cards en liste verticale) sera supprimé pour simplifier.

2. **Ant Design Table natif** - Utilisation du composant Table Ant Design 6.2 avec toutes ses features (tri, pagination, loading skeleton, responsive, scroll).

3. **Colonnes responsive** - Description et Tags masqués sur mobile (< 768px) via responsive prop. Colonnes essentielles (Action, Impact, Moteur, Exécutions, Favori, Actions) toujours visibles.

4. **Tri client-side** - Tri géré par Ant Design Table côté client (sorter prop). Pas de tri backend car filteredActions déjà en mémoire (< 100 actions typiquement).

5. **Click handlers avec stopPropagation** - Boutons Favori et Actions stoppent propagation pour éviter ouverture drawer. Click sur ligne entière ouvre drawer (même UX que cards).

6. **Skeleton loading natif** - Ant Design Table loading prop affiche automatiquement skeleton. Pas besoin de custom skeleton.

7. **Pagination 20 items** - PageSize 20 pour équilibrer performance et UX. Showable changer pour permettre utilisateur ajuster (10/20/50).

8. **Icons moteur réutilisés** - Même logique que ActionCard: workflow → ApartmentOutlined purple, Oracle → DatabaseOutlined, etc.

9. **Tags style cohérent** - Même borderRadius 16px et couleurs pastel que ActionCard pour cohérence visuelle.

10. **Hover effet CSS** - Classe CSS pour hover background avec transition smooth. Utilise design tokens (--ant-color-bg-text-hover).

### Architecture compliance

**Frontend Patterns (architecture.md):**
- Composant dans components/catalog/ActionTable.tsx
- Tests co-localisés (ActionTable.test.tsx)
- State management avec props drilling (pas de context nécessaire)
- Ant Design Table 6.2 component

**UX Design Compliance (ux-design-specification.md):**
- Table Ant Design avec style cohérent
- Thème dark/light supporté (design tokens)
- Skeleton loading natif Ant Design
- Hover state pour interactivité
- ARIA: accessibilité native Table Ant Design + aria-labels boutons

**Ant Design 6.2 Patterns:**
- Table component avec sorter, pagination, loading, responsive
- Typography.Paragraph avec ellipsis
- Tooltip pour contenu tronqué
- Space pour layout tags
- Button type="text" pour actions inline

### Réutilisation composants existants

**Composants réutilisés sans modification:**
- `ImpactIndicator` - Affichage impact dans colonne (src/components/shared/ImpactIndicator.tsx)
- `ActionDrawerPreview` - Ouverture drawer au clic ligne (src/components/catalog/ActionDrawerPreview.tsx)
- Icons: DatabaseOutlined, CloudServerOutlined, HddOutlined, ApartmentOutlined, HeartOutlined, HeartFilled, EyeOutlined

**Handlers réutilisés de CatalogPage:**
- `handleActionClick(action)` - Ouvre drawer (ligne ~327)
- `handleToggleFavorite(id, e)` - Toggle favori avec API call (ligne ~296)
- `filteredActions` memo - Données déjà filtrées (ligne ~210)
- `favorites` Set - État favoris (ligne ~108)

### Gestion des cas limites

- **Aucune action:** Empty state existant CatalogPage s'affiche (locale.emptyText Table)
- **Description null:** Afficher "Aucune description" en gris secondaire
- **Tags vide:** Afficher "Aucun tag" en gris secondaire
- **Impact null:** Afficher "N/A" en gris secondaire
- **Execution_count null:** Traiter comme 0 (fallback)
- **Mobile < 768px:** Masquer colonnes Description et Tags, scroll horizontal si nécessaire
- **Tri sur colonne non sortable:** Désactiver sorter (pas d'icône tri)
- **Hover sur ligne loading:** Skeleton n'a pas de hover effect
- **Click rapide toggle favori:** Optimistic update côté client, rollback si erreur API

### Performance considerations

**Table rendering optimization:**
- Ant Design Table virtualization automatique si > 100 items
- Pagination 20 items limite render initial
- Memo columns definition pour éviter re-render inutiles
- rowKey={record => record.id} pour reconciliation React efficace

**Données déjà filtrées:**
- filteredActions memo en CatalogPage (ligne ~210)
- Pas de re-filtering dans ActionTable
- Table reçoit données prêtes à afficher

**Tri client-side acceptable:**
- Catalogue typiquement < 100 actions
- Tri côté client plus rapide que round-trip API
- Pas de complexité backend supplémentaire

### Tests critiques

**Frontend ActionTable.test.tsx:**
- Test affiche 7 colonnes attendues (Action, Description, Impact, Tags, Moteur, Exécutions, Favori, Actions)
- Test colonne Action avec icône correct selon engine/workflow
- Test colonne Description tronquée à 2 lignes avec ellipsis
- Test colonne Impact affiche ImpactIndicator avec bon level
- Test colonne Tags affiche max 3 + "+N" avec tooltip
- Test colonne Exécutions formatée "N exécution(s)"
- Test colonne Favori toggle appelle onToggleFavorite
- Test colonne Actions bouton détails appelle onActionClick
- Test tri colonnes (nom, moteur, impact, exécutions)
- Test click ligne appelle onActionClick
- Test hover ligne ajoute style cursor pointer
- Test loading={true} affiche skeleton

**Frontend CatalogPage.test.tsx (modifications):**
- Test viewMode='list' affiche ActionTable (pas Space+cards)
- Test ActionTable reçoit filteredActions
- Test ActionTable reçoit favorites Set
- Test ActionTable loading pendant fetch
- Test click ligne table ouvre drawer
- Test toggle favori depuis table appelle API

### Compatibilité ascendante

**Backward compatibility:**
- ViewMode localStorage existant reste compatible ('grid' ou 'list')
- Changement transparent: 'list' affiche maintenant table au lieu de cards verticaux
- Handlers CatalogPage inchangés (handleActionClick, handleToggleFavorite)
- Filtres et état partagé entre grid et list (aucun changement)
- Types TypeScript CatalogAction inchangés

### Alternatives considérées et rejetées

**Alternative 1: Garder Space+cards pour 'list', ajouter 'table' mode**
- Avantages: Pas de breaking change, 3 vues distinctes
- Inconvénients: Complexité UI (3 boutons toggle), confusion utilisateur (list vs table)
- Rejetée: UX spec demande vue table, pas 3ème vue séparée

**Alternative 2: Table avec expand rows pour description complète**
- Avantages: Pas de tooltip, description accessible
- Inconvénients: Complexité interaction, pas demandé spec
- Rejetée: Tooltip + drawer suffisent pour détails

**Alternative 3: Tri backend via API query params**
- Avantages: Cohérence avec pagination backend (si implémentée future)
- Inconvénients: Complexité backend, latence réseau, catalogue < 100 items
- Rejetée: Tri client-side plus simple et performant pour ce volume

### Opportunités d'amélioration futures (post-MVP)

- **Colonnes configurables:** Permettre utilisateur masquer/afficher colonnes (ColumnSelector)
- **Export CSV/PDF:** Exporter table avec filtres actifs (Epic 8 Story 8.5 pattern)
- **Tri multi-colonnes:** Tri secondaire (ex: nom puis impact)
- **Filtres inline colonnes:** Mini select dans header colonnes (comme Excel)
- **Resize colonnes:** Drag header pour ajuster largeur
- **Sticky header:** Header fixe lors scroll vertical
- **Density toggle:** Compact/Default/Comfortable row height
- **Batch actions:** Select multiple rows + actions groupées

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 8 Story 8.10 (lignes 2120-2172)]
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx - Page catalogue existante (lignes 482-493)]
- [Source: idp-portal/frontend/src/components/catalog/ActionCard.tsx - Composant card avec fields (lignes 140-260)]
- [Source: idp-portal/frontend/src/components/catalog/CategoryTabs.tsx - Pattern tabs Story 8.7]
- [Source: idp-portal/frontend/src/components/shared/ImpactIndicator.tsx - Composant impact]
- [Source: idp-portal/frontend/src/types/api.ts - Types CatalogAction, ActionPreviewData]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend-Patterns]
- [Source: _bmad-output/implementation-artifacts/8-9-tabs-toutes-les-executions-et-mes-executions.md - Intelligence story précédente]
- [Source: _bmad-output/implementation-artifacts/8-7-navigation-par-categories-avec-tabs-et-filtres-integres.md - Pattern CategoryTabs et filtres]
- [Source: _bmad-output/implementation-artifacts/3-1-catalogue-actions-avec-modes-affichage-et-favoris.md - Story catalogue originale]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Story created with comprehensive context from Epic 8 Story 8.10 in epics.md (lignes 2120-2172)
- Analyzed CatalogPage current implementation: viewMode state, grid/list rendering, filteredActions memo, handlers
- Reviewed ActionCard component fields: icon, name, description (2 lines), impact, tags (max 3), execution_count, favorite button
- Analyzed CategoryTabs and filtering logic: active filters, "Mes actions" client filter, API filters
- Reviewed ImpactIndicator component: triple coding (color + icon + label), size variants
- Explored CatalogPage structure with Task agent (Explore subagent) for comprehensive code analysis
- Determined table view approach: replace current 'list' mode (Space+cards) with ActionTable
- Mapped all 12 acceptance criteria to detailed tasks with subtasks
- Comprehensive Dev Notes with code examples for all columns (Action, Description, Impact, Tags, Moteur, Exécutions, Favori, Actions)
- Applied learnings from Story 8.9 (design tokens, RBAC patterns, comprehensive tests, ThemeProvider)
- Leveraged architecture patterns for Ant Design Table component usage
- Defined responsive design: masquer Description et Tags sur mobile (< 768px)
- Tri client-side acceptable: catalogue < 100 actions, plus performant que backend
- Click handlers avec stopPropagation pour éviter conflit (bouton favori vs ligne)
- Skeleton loading natif Ant Design Table (loading prop)
- Hover effect CSS avec design tokens pour cohérence dark/light theme
- Tests critiques identifiés: 12 tests ActionTable + 6 tests intégration CatalogPage
- Backward compatible: viewMode 'list' devient table transparently
- **IMPLEMENTATION COMPLETE (2026-02-01):**
  - Created ActionTable.tsx with all 8 columns (Action, Description, Impact, Tags, Moteur, Exécutions, Favori, Actions)
  - Implemented sorting for Action (name), Moteur (engine), Impact, and Exécutions columns
  - Added hover effect with cursor:pointer and background transition
  - Integrated responsive design: Description and Tags hidden on mobile (< 768px)
  - Skeleton loading via Ant Design Table loading prop
  - Integrated ActionTable into CatalogPage to replace Space+cards in list view mode
  - Created 33 unit tests for ActionTable covering all acceptance criteria
  - Added 8 integration tests for CatalogPage table view (Story 8.10 specific)
  - All 66 tests passing (33 ActionTable + 33 CatalogPage including Story 8.10 tests)

### File List

**Files created:**

Frontend:
- `idp-portal/frontend/src/components/catalog/ActionTable.tsx` - Table component pour vue liste (316 lines)
- `idp-portal/frontend/src/components/catalog/ActionTable.test.tsx` - 33 tests du composant (387 lines)

**Files modified:**

Frontend:
- `idp-portal/frontend/src/pages/CatalogPage.tsx` - Intégré ActionTable dans render conditionnel viewMode, mis à jour skeleton loading pour table
- `idp-portal/frontend/src/pages/CatalogPage.test.tsx` - Ajouté 8 tests pour table view integration (Story 8.10)

## Change Log

- 2026-02-01: Story implementation complete - all 16 tasks and subtasks completed, 66 tests passing
- 2026-02-01: **Code review adversarial complete** - 10 issues found and fixed automatically:
  - **HIGH (5 fixed):** H1-useMemo dependency, H2-inline styles, H3-design tokens for engine colors, H4-double skeleton loading, H5-rowKey fallback
  - **MEDIUM (3 fixed):** M1-pluralization, M2-i18n pagination, M3-tooltip length limit
  - **LOW (2 fixed):** L1-magic numbers, L2-test IDs
  - All 66 tests still passing after fixes
  - Code quality significantly improved: architecture compliance, performance, maintainability
