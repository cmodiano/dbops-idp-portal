# Story 18.2: Identification visuelle workflow vs action (Admin et Catalogue)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBOPS ou DBA**,
je veux **distinguer facilement les workflows des actions simples** dans les listes,
afin de **identifier rapidement le type d'élément sans lire le détail**.

## Acceptance Criteria

**AC1: Icône workflow visible dans la liste admin**
```gherkin
Given la liste des actions en admin
When j'affiche les lignes du tableau
Then chaque ligne affiche une icône permettant de distinguer workflow vs action
And les workflows affichent l'icône ApartmentOutlined en violet (#722ed1)
And les actions affichent l'icône spécifique à leur moteur (DatabaseOutlined pour Oracle, etc.)
And l'icône apparaît dans la colonne "Nom" avant le texte du nom
```

**AC2: Tooltip accessible sur l'icône admin**
```gherkin
Given une ligne dans la liste admin
When je survole l'icône workflow ou action
Then un tooltip apparaît avec le type: "Workflow (chaîne d'actions)" ou "Action {nom du moteur}"
And le tooltip respecte les normes d'accessibilité ARIA
```

**AC3: Cohérence visuelle avec le catalogue (déjà implémenté)**
```gherkin
Given le catalogue affiche déjà la distinction workflow vs action
When je compare avec l'admin
Then les mêmes icônes et couleurs sont utilisées (ApartmentOutlined violet pour workflows)
And le pattern de design est identique entre Admin et Catalogue
```

**AC4: Vérification catalogue (validation existant)**
```gherkin
Given la page catalogue avec vue carte (ActionCard.tsx)
When j'affiche une action workflow
Then l'icône ApartmentOutlined violet est affichée (lignes 88-122)

Given la page catalogue avec vue tableau (ActionTable.tsx)
When j'affiche une action workflow
Then l'icône ApartmentOutlined violet est affichée (lignes 81-100)

Given la prévisualisation dans le drawer (ActionDrawerPreview.tsx)
When j'ouvre le détail d'un workflow
Then le badge workflow avec icône ApartmentOutlined est affiché (lignes 113, 145-149)
```

**AC5: Accessibilité et responsive**
```gherkin
Given un utilisateur avec lecteur d'écran
When il navigue dans la liste admin
Then chaque icône a un label ARIA approprié ("Type: Workflow" ou "Type: Action")

Given un utilisateur sur mobile
When il consulte la liste admin
Then les icônes restent visibles et bien alignées
```

## Tasks / Subtasks

- [x] **Task 1: Ajouter colonne icône type dans AdminPage.tsx** (AC: 1, 2, 5)
  - [x] Modifier `AdminPage.tsx` table columns pour ajouter `getItemTypeIcon()` function
  - [x] Fonction retourne `<ApartmentOutlined style={{ color: '#722ed1' }} />` si `item_type === 'workflow'`
  - [x] Fonction retourne icône moteur (`getEngineIcon()` existante) si `item_type === 'action'`
  - [x] Ajouter Tooltip Ant Design sur icône: "Workflow (chaîne d'actions)" ou "Action {engine}"
  - [x] Insérer icône dans colonne "Nom" avant le texte (render: `<Space><Icon /><Text>{name}</Text></Space>`)
  - [x] Vérifier que `item_type` est présent dans `ActionListItem` (déjà dans types/api.ts ligne 168)

- [x] **Task 2: Extraire utilitaire getItemTypeIcon partagé** (AC: 1, 3)
  - [x] Créer `frontend/src/utils/iconHelpers.tsx`
  - [x] Exporter fonction `getItemTypeIcon(itemType, engine, options?)` réutilisable
  - [x] Retourner objet `{ icon: ReactNode, color: string, label: string }`
  - [x] Aligner couleurs et icônes avec celles utilisées dans Catalog components (STYLE_TOKENS)
  - [x] Pattern de couleurs: workflow=#722ed1 (violet), oracle=#EF4444 (rouge), sqlserver=#3B82F6 (bleu), db2=#10B981 (vert)

- [x] **Task 3: Refactorer Catalog components pour utiliser l'utilitaire partagé** (AC: 3)
  - [x] Modifier `ActionCard.tsx` pour utiliser `getItemTypeIcon()` (workflow icon + fallback engine)
  - [x] Modifier `ActionTable.tsx` pour utiliser `getItemTypeIcon()`
  - [x] Supprimer duplication de logique (constantes WORKFLOW_ICON, ENGINE_ICON_FALLBACKS, getActionIcon inline)
  - [x] Vérifier que le comportement visuel reste identique après refactoring (55/55 catalog tests pass)

- [x] **Task 4: Améliorer accessibilité des icônes** (AC: 5)
  - [x] Ajouter `aria-label` sur chaque icône workflow/action (intégré dans iconHelpers)
  - [x] Format: `aria-label="Type: Workflow"` ou `aria-label="Type: Action Oracle"`
  - [x] Vérifier contraste couleurs (violet #722ed1 sur fond blanc: ratio ~5.6:1 ≥ 4.5:1 WCAG AA)

- [x] **Task 5: Tests frontend AdminPage icônes** (AC: 1, 2, 5)
  - [x] Test: icône workflow ApartmentOutlined affichée pour item_type='workflow'
  - [x] Test: icône moteur (DatabaseOutlined, CloudServerOutlined, HddOutlined) affichée pour item_type='action'
  - [x] Test: tooltip "Workflow (chaîne d'actions)" apparaît au survol workflow
  - [x] Test: tooltip "Action Oracle" apparaît au survol action
  - [x] Test: aria-label correct sur chaque icône ("Type: Workflow", "Type: Action Oracle")
  - [x] Test: icônes visibles dans tableau avec données mixtes (4 actions + 1 workflow)
  - [x] Mock data: `ActionListItem[]` avec item_type='workflow' et 'action' + engine variés (10 tests)

- [x] **Task 6: Tests frontend utilitaire getItemTypeIcon** (AC: 3)
  - [x] Test: `getItemTypeIcon('workflow', null)` retourne ApartmentOutlined violet
  - [x] Test: `getItemTypeIcon('action', 'Oracle')` retourne DatabaseOutlined rouge
  - [x] Test: `getItemTypeIcon('action', 'SQL Server')` retourne CloudServerOutlined bleu
  - [x] Test: `getItemTypeIcon('action', 'DB2')` retourne HddOutlined vert
  - [x] Test: gestion moteur inconnu (fallback HddOutlined gris) + null engine (8 tests)

- [x] **Task 7: Tests visuels régression Catalog** (AC: 3, 4)
  - [x] ActionCard: 22/22 tests pass (aucune régression)
  - [x] ActionTable: 33/33 tests pass (aucune régression)
  - [x] ActionDrawerPreview: 36/40 tests pass (4 échecs pré-existants Story 3.4 markdown, non liés)

- [x] **Task 8: Documentation utilisateur** (AC: all)
  - [x] Mis à jour `docs/frontend/components.md` — section "Identification visuelle des workflows"
  - [x] Documenté fonction `getItemTypeIcon`, tableau icônes/couleurs, composants utilisateurs
  - [x] Mentionné que Admin et Catalogue utilisent le même système d'icônes partagé

## Dev Notes

### Architecture Patterns & Constraints

**🎯 BONNE NOUVELLE: Infrastructure déjà en place!**

L'analyse exhaustive du codebase révèle que **toute l'infrastructure backend/frontend pour distinguer workflows vs actions existe déjà**:

1. **Backend**: champ `item_type` dans modèle Action (enum: 'action' | 'workflow')
2. **API**: `ActionListSerializer` inclut `item_type` dans les réponses GET /api/v1/admin/actions/
3. **Frontend types**: `ActionListItem.item_type?: ItemType` déjà défini
4. **Catalogue**: les 3 composants (ActionCard, ActionTable, ActionDrawerPreview) affichent déjà les icônes correctement

**❌ CE QUI MANQUE:**
- Uniquement le tableau Admin (`AdminPage.tsx`) ne rend pas les icônes, alors que le champ `item_type` est déjà disponible dans les données

**Framework & Stack:**
- Backend: Django 5.2 + DRF 3.16 (migration Epic M complétée)
- Frontend: React 19 + Ant Design 6.2 + TypeScript 5.x
- Icônes: `@ant-design/icons` (ApartmentOutlined, DatabaseOutlined, CloudServerOutlined, HddOutlined)

**Design Pattern Établi (Catalogue):**
```typescript
// Pattern déjà utilisé dans ActionCard.tsx et ActionTable.tsx
const WORKFLOW_ICON = <ApartmentOutlined style={{ color: '#722ed1', fontSize: 16 }} />;
const ENGINE_ICONS = {
  oracle: <DatabaseOutlined style={{ color: '#1677ff' }} />,
  sqlserver: <CloudServerOutlined style={{ color: '#13c2c2' }} />,
  db2: <HddOutlined style={{ color: '#fa8c16' }} />,
  // fallback: HddOutlined gris
};
```

**Objectif de cette Story:**
1. **Réutiliser** le même pattern visuel dans AdminPage.tsx
2. **Refactorer** pour extraire logique commune (éviter duplication)
3. **Améliorer** accessibilité (aria-label, tooltips)

### Previous Story Intelligence (Story 18.1)

**Learnings from 18-1 (admin soft delete):**

1. **AdminPage.tsx Structure:**
   - Table Ant Design avec 7 colonnes: Nom, Moteur, Statut, Executions, Tags, Date, Actions
   - Hook `useAdminActions()` fetch data via `adminService.fetchActions(includeDisabled)`
   - Type `ActionListItem` utilisé pour les lignes (interface ligne 168 de types/api.ts)
   - Render personnalisable via `columns` array avec propriété `render: (text, record) => ReactNode`

2. **Pattern de Modification Colonne:**
   ```typescript
   {
     title: 'Nom',
     dataIndex: 'name',
     key: 'name',
     render: (name: string, record: ActionListItem) => (
       <Space>
         {getItemTypeIcon(record.item_type, record.engine)}
         <Text>{name}</Text>
       </Space>
     )
   }
   ```

3. **Tests Frontend Story 18.1:**
   - 22 tests Vitest dans `AdminPage.story18_1.test.tsx`
   - Pattern: mock `adminService`, render `<AdminPage />`, query `getByText()`, `fireEvent`, assertions
   - Coverage: boutons conditionnels, popconfirm, modal, erreurs API

4. **Git Commit Message Pattern:**
   - Format: `feat(18.1): Add admin soft delete, deactivation, and filtering`
   - Suivre convention: `feat(18.2): Add workflow vs action visual identification`

5. **Fichiers Modifiés Story 18.1:**
   - `frontend/src/pages/AdminPage.tsx` (modification table columns + checkbox filtre)
   - `frontend/src/services/admin_service.ts` (nouveaux endpoints)
   - `frontend/src/types/api.ts` (nouveaux champs `ActionListItem`)
   - Tests: `frontend/src/pages/AdminPage.story18_1.test.tsx`

**Key Insight:** AdminPage.tsx utilise déjà `ActionListItem` qui contient `item_type`, donc aucune modification API/service nécessaire. Il suffit d'ajouter le render de l'icône dans la colonne "Nom".

### Project Structure Notes

**Fichiers à Modifier:**
```
frontend/src/
├── pages/
│   └── AdminPage.tsx                      # Ajouter icône dans colonne Nom (Task 1)
├── utils/
│   └── iconHelpers.ts                     # Créer utilitaire getItemTypeIcon (Task 2)
├── components/catalog/
│   ├── ActionCard.tsx                     # Refactorer pour utiliser iconHelpers (Task 3)
│   ├── ActionTable.tsx                    # Refactorer pour utiliser iconHelpers (Task 3)
│   └── ActionDrawerPreview.tsx            # (Optionnel) vérifier cohérence
└── __tests__/
    ├── AdminPage.story18_2.test.tsx       # Tests icônes Admin (Task 5)
    └── utils/iconHelpers.test.ts          # Tests utilitaire (Task 6)
```

**Fichiers Backend (Aucune Modification Requise):**
- `catalog/models.py` — champ `item_type` existe déjà (ligne 175-180)
- `catalog/serializers.py` — `ActionListSerializer` inclut déjà `item_type` (ligne 262-289)

**Dépendances Existantes:**
```json
{
  "@ant-design/icons": "^5.x",  // ApartmentOutlined, DatabaseOutlined, etc.
  "antd": "^6.2.x"               // Space, Tooltip, Table
}
```

**Dépendances Critiques (Code Review Finding):**
- `frontend/src/theme/styleTokens.ts` — Single source of truth for all icon colors
- `STYLE_TOKENS.workflowColor` (#722ed1) — workflow icon color token
- `STYLE_TOKENS.engineIconColor` — engine icon colors (Oracle, SQL Server, DB2)
- Changes to styleTokens will affect ALL icon rendering across Admin and Catalog

### Testing Standards

**Frontend Tests (Vitest + React Testing Library):**

1. **Mock Data Pattern:**
```typescript
const mockActions: ActionListItem[] = [
  {
    id: 1,
    name: 'Apply Oracle Patch',
    item_type: 'action',
    engine: 'oracle',
    status: 'published',
    // ... autres champs
  },
  {
    id: 2,
    name: 'Full Backup Workflow',
    item_type: 'workflow',
    engine: null,  // workflows n'ont pas de moteur
    status: 'published',
    // ...
  }
];
```

2. **Test Icône Workflow:**
```typescript
test('affiche icône ApartmentOutlined pour workflows', () => {
  const { container } = render(<AdminPage />);
  // Vérifier présence icône workflow (ApartmentOutlined a classe spécifique)
  const workflowIcon = container.querySelector('.anticon-apartment');
  expect(workflowIcon).toBeInTheDocument();
  // Vérifier couleur violette
  expect(workflowIcon).toHaveStyle({ color: '#722ed1' });
});
```

3. **Test Tooltip:**
```typescript
test('tooltip "Workflow" apparaît au survol', async () => {
  const { getByRole, getByText } = render(<AdminPage />);
  const workflowRow = getByText('Full Backup Workflow');
  const icon = workflowRow.closest('td')?.querySelector('.anticon-apartment');

  fireEvent.mouseOver(icon!);
  await waitFor(() => {
    expect(getByText('Workflow (chaîne d\'actions)')).toBeInTheDocument();
  });
});
```

4. **Test Accessibilité:**
```typescript
test('icône workflow a aria-label correct', () => {
  const { container } = render(<AdminPage />);
  const workflowIcon = container.querySelector('[aria-label="Type: Workflow"]');
  expect(workflowIcon).toBeInTheDocument();
});
```

**Coverage Target:**
- AdminPage.tsx: augmenter coverage de 5-10% (ajout render icônes)
- iconHelpers.ts: 100% coverage (fonction pure simple)
- Tests minimum: 8 tests nouveaux (5 AdminPage + 3 iconHelpers)

### References

**Epic Source:**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic-18-Story-18.2]
  - Lignes 3911-3925: Story 18.2 definition

**Previous Story:**
- [Source: _bmad-output/implementation-artifacts/18-1-admin-actions-suppression-desactivation-filtres.md]
  - Learnings: AdminPage structure, tests pattern, git commit format

**Architecture & Design System:**
- [Source: frontend/src/components/catalog/ActionCard.tsx lignes 88-122]
  - Pattern icône workflow: ApartmentOutlined violet #722ed1
- [Source: frontend/src/components/catalog/ActionTable.tsx lignes 81-100]
  - Fonction `getActionIcon()` existante (à extraire vers iconHelpers)
- [Source: frontend/src/components/catalog/ActionDrawerPreview.tsx lignes 145-149]
  - Badge workflow avec tooltip

**Backend Models:**
- [Source: idp-portal/django_backend/catalog/models.py lignes 41-44, 175-180]
  - Enum `ActionItemType` ('action' | 'workflow')
  - Champ `item_type` dans modèle Action
- [Source: idp-portal/django_backend/catalog/serializers.py lignes 262-289]
  - `ActionListSerializer` inclut `item_type` dans réponse API

**Frontend Types:**
- [Source: frontend/src/types/api.ts ligne 35, 168]
  - Type `ItemType = 'action' | 'workflow'`
  - Interface `ActionListItem` avec champ `item_type?: ItemType`

**Git History:**
- Commit récent `f816a8b feat(18.1): Add admin soft delete, deactivation, and filtering`
- Convention commits: `feat(epic.story): Description`

**Ant Design 6.2 Documentation:**
- Icons: https://ant.design/components/icon (ApartmentOutlined, DatabaseOutlined)
- Tooltip: https://ant.design/components/tooltip
- Space: https://ant.design/components/space
- Table columns render: https://ant.design/components/table#Column

**Accessibilité:**
- WCAG 2.1 Level AA: contraste couleurs ≥ 4.5:1
- ARIA labels obligatoires pour icônes décoratives significatives
- Epic 3 story 3-1 (lignes 1349-1395 epics.md): accessibilité catalogue implémentée

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- TypeScript compilation clean (0 errors) after all changes
- 95/95 tests pass across 5 test files (0 regressions)

### Completion Notes List

- **Task 2**: Created `iconHelpers.tsx` shared utility with `getItemTypeIcon()` function returning `{ icon, color, label }`. Supports workflow (ApartmentOutlined violet), Oracle (DatabaseOutlined), SQL Server (CloudServerOutlined), DB2 (HddOutlined), and unknown engine fallback (HddOutlined grey). Options: `withTooltip`, `fontSize`.
- **Task 1**: Added icon render in AdminPage.tsx "Nom" column using `getItemTypeIcon()` with tooltip enabled. Icon appears before name text in `<Space>` layout.
- **Task 3**: Refactored ActionTable.tsx to delegate to `getItemTypeIcon()` (removed inline `getActionIcon` switch/case). Refactored ActionCard.tsx to use `getItemTypeIcon()` for workflow icon and engine fallback (kept SVG override for real vendor logos). Removed `WORKFLOW_ICON`, `ENGINE_ICON_FALLBACKS` constants.
- **Task 4**: Accessibility built into `getItemTypeIcon()` — every icon includes `aria-label` ("Type: Workflow", "Type: Action Oracle", etc.). Contrast ratio #722ed1 on white ~5.6:1 meets WCAG AA.
- **Task 5**: 10 AdminPage tests covering workflow icon, engine icons (Oracle/SQL Server/DB2), tooltips, aria-labels, mixed data rendering.
- **Task 6**: 8 iconHelpers unit tests covering all item types, engines, fallback, tooltip option, fontSize option.
- **Task 7**: Regression verified — ActionCard 22/22, ActionTable 33/33, AdminPage 18.1 22/22 all pass. ActionDrawerPreview 36/40 (4 pre-existing failures).
- **Task 8**: Updated `docs/frontend/components.md` with "Identification visuelle des workflows" section.
- **Code Review Fixes (2026-02-07)**: Refactored workflow color to use STYLE_TOKENS.workflowColor for consistency. Removed unused AppstoreOutlined import. Updated File List to document all changed files including styleTokens.ts. Added critical dependencies documentation for future maintainers.

### Change Log

- 2026-02-07: Story 18.2 implementation complete — shared `getItemTypeIcon()` utility created, AdminPage icon column added, Catalog components refactored, accessibility improved, 18 new tests added (10 AdminPage + 8 iconHelpers)
- 2026-02-07: Code review fixes applied — refactored workflow color to use STYLE_TOKENS.workflowColor, removed unused imports, updated documentation with critical dependencies

### File List

- `idp-portal/frontend/src/utils/iconHelpers.tsx` (NEW) — shared icon utility
- `idp-portal/frontend/src/utils/iconHelpers.test.tsx` (NEW) — 8 unit tests
- `idp-portal/frontend/src/pages/AdminPage.tsx` (MODIFIED) — added icon render in Nom column
- `idp-portal/frontend/src/pages/AdminPage.story18_2.test.tsx` (NEW) — 10 integration tests
- `idp-portal/frontend/src/components/catalog/ActionTable.tsx` (MODIFIED) — refactored to use iconHelpers
- `idp-portal/frontend/src/components/catalog/ActionCard.tsx` (MODIFIED) — refactored to use iconHelpers
- `idp-portal/frontend/src/theme/styleTokens.ts` (MODIFIED) — added workflowColor token for consistency
- `idp-portal/docs/frontend/components.md` (MODIFIED) — added icon system documentation
- `.claude/settings.local.json` (MODIFIED) — IDE config artifact, not application code
- `node_modules/.vite/vitest/.../results.json` (MODIFIED) — build artifact, not application code
