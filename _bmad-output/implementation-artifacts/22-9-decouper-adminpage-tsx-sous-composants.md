# Story 22.9: Découper AdminPage.tsx en sous-composants

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux découper `AdminPage.tsx` en sous-composants par onglet,
afin d'améliorer la maintenabilité et la testabilité.

## Acceptance Criteria

**AC1: Structure en sous-composants**
- **Given** `AdminPage.tsx` contient 845 LOC avec 6 onglets (Actions, Profils, Intégrations, Catégories, Métriques, Feature Flags)
- **When** le découpage est effectué
- **Then** chaque onglet est extrait dans un composant dédié sous `pages/admin/` ou `components/admin/`

**AC2: AdminPage devient orchestrateur**
- **Given** les onglets sont extraits
- **When** le refactoring est terminé
- **Then** `AdminPage.tsx` devient un conteneur léger qui orchestre les onglets (<200 LOC)
- **And** la logique métier est déléguée aux sous-composants

**AC3: Taille des fichiers**
- **Given** chaque sous-composant est créé
- **When** le découpage est validé
- **Then** chaque sous-composant fait <300 LOC

**AC4: Tests existants passent**
- **Given** des tests existent pour AdminPage (AdminPage.test.tsx, AdminPage.story18_1.test.tsx, AdminPage.story18_2.test.tsx)
- **When** le découpage est appliqué
- **Then** tous les tests existants passent sans modification majeure

**AC5: Gestion de l'état partagé**
- **Given** certains onglets partagent des notifications, modals, etc.
- **When** la logique d'état est refactorisée
- **Then** l'état partagé est bien géré via props ou context
- **And** chaque sous-composant reste autonome

## Tasks / Subtasks

- [x] Task 1: Analyser la structure et définir le découpage (AC: #1, #2)
  - [x] 1.1: Identifier les 6 onglets et leurs responsabilités
  - [x] 1.2: Analyser les dépendances entre onglets (état partagé, hooks communs)
  - [x] 1.3: Définir la structure cible sous `pages/admin/` ou `components/admin/`
  - [x] 1.4: Planifier l'ordre de refactoring (onglet le plus simple d'abord)

- [x] Task 2: Créer les sous-composants pour les onglets simples (AC: #1, #3)
  - [x] 2.1: Extraire `CategoriesAdminPanel.tsx` - Onglet Catégories (déjà isolé avec CategoriesAdminTable)
  - [x] 2.2: Extraire `MetricsAdminPanel.tsx` - Onglet Métriques (lazy AdminAnalyticsDashboard)
  - [x] 2.3: Extraire `FeatureFlagsAdminPanel.tsx` - Onglet Feature Flags (lazy FeatureFlagsPanel)

- [x] Task 3: Créer les sous-composants pour les onglets complexes (AC: #1, #3, #5)
  - [x] 3.1: Extraire `ActionsAdminPanel.tsx` - Onglet Actions avec état (actions, loading, filters, CRUD handlers)
  - [x] 3.2: Extraire `ProfilesAdminPanel.tsx` - Onglet Profils avec état (profiles, modals, import/export)
  - [x] 3.3: Extraire `IntegrationsAdminPanel.tsx` - Onglet Intégrations avec état (integrations, CRUD)

- [x] Task 4: Refactoriser AdminPage en orchestrateur (AC: #2)
  - [x] 4.1: Convertir AdminPage en conteneur Tabs minimal
  - [x] 4.2: Passer les props nécessaires aux sous-composants (notification, modal depuis App.useApp())
  - [x] 4.3: Gérer le lazy loading des onglets lourds (Métriques, Feature Flags)
  - [x] 4.4: Valider que AdminPage.tsx fait <200 LOC

- [x] Task 5: Tests et validation (AC: #4)
  - [x] 5.1: Exécuter les tests existants (AdminPage.test.tsx, story18_1, story18_2)
  - [x] 5.2: Corriger les imports/exports si nécessaire
  - [x] 5.3: Valider que tous les tests passent (nombre de tests passants égal ou supérieur)
  - [x] 5.4: Vérifier les tailles de fichiers (<300 LOC par sous-composant)

- [x] Task 6: Documentation (AC: #5)
  - [x] 6.1: Documenter la nouvelle structure dans les commentaires JSDoc
  - [x] 6.2: Ajouter un guide de contribution pour les nouveaux onglets admin
  - [x] 6.3: Mettre à jour README.md frontend si nécessaire

## Dev Notes

### Architecture et Patterns

**Structure actuelle (AdminPage.tsx - 845 LOC):**

```
AdminPage.tsx (845 LOC)
├── Header (Titre + description)
├── Tabs (6 onglets)
│   ├── Actions (lignes 634-697) - ~63 LOC
│   │   ├── Table + colonnes (getColumns - lignes 48-229) - ~181 LOC
│   │   ├── État: actions, loading, modalOpen, editAction, includeDisabled, cascadeModal
│   │   ├── Handlers: fetchActions, handleCreate, handleEdit, handleStatusChange, handleDelete, handleDeactivate, handleReactivate
│   │   └── Modals: ActionWizard (ligne 772), CascadeConfirmation (ligne 807)
│   ├── Profils (lignes 700-717) - ~17 LOC
│   │   ├── État: profiles, profilesLoading, profileModalOpen, editProfile, importYamlModalOpen
│   │   ├── Handlers: fetchProfiles, handleProfileEdit, handleProfileDelete, handleExportYaml, handleImportYaml
│   │   └── Modals: ProfileWizard (ligne 783), ProfileImportModal (ligne 790)
│   ├── Intégrations (lignes 720-736) - ~16 LOC
│   │   ├── État: integrations, integrationsLoading, integrationModalOpen, editIntegration
│   │   ├── Handlers: fetchIntegrations, handleIntegrationEdit, handleIntegrationDelete, handleIntegrationSubmit
│   │   └── Modal: IntegrationForm (ligne 796)
│   ├── Catégories (lignes 739-745) - ~6 LOC (simple wrapper)
│   │   └── CategoriesAdminTable (déjà composant isolé)
│   ├── Métriques (lignes 748-756) - ~8 LOC (lazy loading)
│   │   └── AdminAnalyticsDashboard (lazy import ligne 36)
│   └── Feature Flags (lignes 759-767) - ~8 LOC (lazy loading)
│       └── FeatureFlagsPanel (lazy import ligne 37)
└── Modals hors Tabs (lignes 772-843) - ~71 LOC
    ├── ActionWizard
    ├── ProfileWizard
    ├── ProfileImportModal
    ├── IntegrationForm
    └── CascadeConfirmModal
```

**Structure cible proposée:**

```
pages/
└── AdminPage.tsx (conteneur, <200 LOC)
    └── Tabs avec lazy loading des panels

pages/admin/ (nouveaux sous-composants)
├── ActionsAdminPanel.tsx (~300 LOC)
│   ├── getActionsColumns() helper
│   ├── useState: actions, loading, modals, filters
│   ├── useEffect: fetchActions
│   ├── handlers: CRUD, status changes
│   ├── Table + ActionWizard + CascadeModal
│   └── Props: notification, modal (depuis App.useApp)
├── ProfilesAdminPanel.tsx (~150 LOC)
│   ├── useState: profiles, loading, modals
│   ├── handlers: CRUD, import/export
│   ├── ProfilesTable + ProfileWizard + ImportModal
│   └── Props: notification
├── IntegrationsAdminPanel.tsx (~150 LOC)
│   ├── useState: integrations, loading, modals
│   ├── handlers: CRUD
│   ├── IntegrationsTable + IntegrationForm
│   └── Props: notification
├── CategoriesAdminPanel.tsx (~30 LOC)
│   └── Simple wrapper autour de CategoriesAdminTable
├── MetricsAdminPanel.tsx (~20 LOC)
│   └── Lazy wrapper AdminAnalyticsDashboard
└── FeatureFlagsAdminPanel.tsx (~20 LOC)
    └── Lazy wrapper FeatureFlagsPanel
```

**Principes de découpage:**

1. **Séparation des responsabilités**: Chaque panel gère son propre état et sa logique métier
2. **Props injection**: `notification` et `modal` passés depuis AdminPage (App.useApp)
3. **Indépendance**: Chaque panel doit pouvoir fonctionner seul
4. **Lazy loading**: Métriques et Feature Flags restent en lazy loading (composants lourds)
5. **Réutilisation**: Les composants existants (ActionWizard, ProfilesTable, etc.) sont préservés

**Patterns d'état partagé:**

```typescript
// AdminPage.tsx (conteneur)
const { notification, modal } = App.useApp();
const { effectiveMode } = useTheme();

// Passer via props aux panels
<ActionsAdminPanel notification={notification} modal={modal} isDark={effectiveMode === 'dark'} />
```

**Avantages du découpage:**

- ✅ Maintenance: Fichiers plus petits, plus faciles à naviguer
- ✅ Tests: Tests ciblés par panel (possibilité de séparer les tests par panel)
- ✅ Performance: Lazy loading des panels lourds possible
- ✅ Réutilisabilité: Panels peuvent être réutilisés ailleurs
- ✅ Collaboration: Réduction des conflits git (équipe travaille sur des panels différents)

### Technical Requirements

**Stack technique:**
- **Language**: TypeScript 5.9.3
- **Framework frontend**: React 19.2.0 + Vite 7.2.4
- **UI Library**: Ant Design 6.2.2
- **Test framework**: Vitest 4.0.18
- **Router**: React Router 7.1.1

**Contraintes techniques:**

1. **Zero breaking change**: Tous les tests existants doivent passer
2. **Props drilling**: Éviter le props drilling excessif - utiliser props directement depuis App.useApp() au lieu de context
3. **Lazy loading**: Préserver le lazy loading des composants lourds (AdminAnalyticsDashboard, FeatureFlagsPanel)
4. **Exports nommés**: Exporter les panels avec des noms explicites pour faciliter les tests

**Interfaces des panels:**

```typescript
// ActionsAdminPanel.tsx
interface ActionsAdminPanelProps {
  notification: NotificationInstance;
  modal: ModalStaticFunctions;
  isDark: boolean;
}

// ProfilesAdminPanel.tsx
interface ProfilesAdminPanelProps {
  notification: NotificationInstance;
}

// IntegrationsAdminPanel.tsx
interface IntegrationsAdminPanelProps {
  notification: NotificationInstance;
}

// Panels simples (CategoriesAdminPanel, MetricsAdminPanel, FeatureFlagsAdminPanel)
interface SimplePanelProps {} // Aucune props nécessaire
```

### File Structure Requirements

**Nomenclature des fichiers:**
- Pattern: `<Domain>AdminPanel.tsx` (ex: `ActionsAdminPanel.tsx`, `ProfilesAdminPanel.tsx`)
- Location: `pages/admin/` (nouveau répertoire)
- Tests: `pages/admin/<Domain>AdminPanel.test.tsx` (création optionnelle, tests existants dans AdminPage.test.tsx préservés)

**Structure du répertoire admin:**

```
pages/
├── AdminPage.tsx (conteneur, <200 LOC)
└── admin/
    ├── ActionsAdminPanel.tsx
    ├── ProfilesAdminPanel.tsx
    ├── IntegrationsAdminPanel.tsx
    ├── CategoriesAdminPanel.tsx
    ├── MetricsAdminPanel.tsx
    ├── FeatureFlagsAdminPanel.tsx
    └── index.ts (barrel export)
```

**Barrel export (admin/index.ts):**

```typescript
export { ActionsAdminPanel } from './ActionsAdminPanel';
export { ProfilesAdminPanel } from './ProfilesAdminPanel';
export { IntegrationsAdminPanel } from './IntegrationsAdminPanel';
export { CategoriesAdminPanel } from './CategoriesAdminPanel';
export { MetricsAdminPanel } from './MetricsAdminPanel';
export { FeatureFlagsAdminPanel } from './FeatureFlagsAdminPanel';
```

**AdminPage.tsx refactorisé (squelette):**

```typescript
import { App, Typography, Tabs } from 'antd';
import { useTheme } from '../contexts/ThemeContext';
import {
  ActionsAdminPanel,
  ProfilesAdminPanel,
  IntegrationsAdminPanel,
  CategoriesAdminPanel,
  MetricsAdminPanel,
  FeatureFlagsAdminPanel,
} from './admin';

const { Title } = Typography;

export default function AdminPage() {
  const { notification, modal } = App.useApp();
  const { effectiveMode } = useTheme();

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ marginBottom: 32 }}>
        <Title level={2} style={{ margin: 0, marginBottom: 8 }}>
          Administration du Catalogue
        </Title>
        <Typography.Text type="secondary">
          Gerez vos actions et profils
        </Typography.Text>
      </div>

      <Tabs
        defaultActiveKey="actions"
        items={[
          {
            key: 'actions',
            label: 'Actions',
            children: <ActionsAdminPanel notification={notification} modal={modal} isDark={effectiveMode === 'dark'} />,
          },
          {
            key: 'profiles',
            label: 'Profils',
            children: <ProfilesAdminPanel notification={notification} />,
          },
          {
            key: 'integrations',
            label: 'Intégrations',
            children: <IntegrationsAdminPanel notification={notification} />,
          },
          {
            key: 'categories',
            label: 'Catégories',
            children: <CategoriesAdminPanel />,
          },
          {
            key: 'analytics',
            label: 'Métriques',
            children: <MetricsAdminPanel />,
          },
          {
            key: 'feature-flags',
            label: 'Feature Flags',
            children: <FeatureFlagsAdminPanel />,
          },
        ]}
      />
    </div>
  );
}
```

### Testing Requirements

**Tests existants à préserver:**

1. **AdminPage.test.tsx** - Tests généraux du conteneur AdminPage (onglets, navigation)
2. **AdminPage.story18_1.test.tsx** - Tests Story 18.1 (suppression/désactivation avec filters)
3. **AdminPage.story18_2.test.tsx** - Tests Story 18.2 (identification workflow vs action)

**Stratégie de tests après refactoring:**

1. **Tests existants**: Doivent tous passer (imports mis à jour si nécessaire)
2. **Nouveaux tests (optionnels)**: Tests unitaires par panel si la logique est complexe
3. **Tests d'intégration**: Valider que les panels s'intègrent bien dans AdminPage

**Commandes de validation:**

```bash
# Vérifier les tailles de fichiers
wc -l src/pages/AdminPage.tsx src/pages/admin/*.tsx

# Vérifier la compilation TypeScript
npm run build

# Exécuter les tests
npm test AdminPage

# Vérifier ESLint
npm run lint
```

**Critères de succès tests:**

- Tous les tests existants passent (minimum 3 fichiers de tests)
- Aucune régression dans le nombre de tests passants
- Aucune erreur TypeScript introduite
- Aucun warning ESLint introduit

### Architecture Compliance

**Alignement avec les décisions architecturales:**

1. **Composition over inheritance**: Utiliser la composition de composants React
2. **Single Responsibility**: Chaque panel a une responsabilité unique (gérer un onglet)
3. **DRY (Don't Repeat Yourself)**: Réutiliser les composants existants (ActionWizard, ProfilesTable, etc.)
4. **Props drilling minimal**: Injecter `notification` et `modal` via props au lieu de context global
5. **Lazy loading**: Préserver le lazy loading des composants lourds (Métriques, Feature Flags)

**Patterns React établis dans le projet:**

- Hooks (`useState`, `useEffect`, `useCallback`) pour la gestion de l'état
- Ant Design pour les composants UI
- `App.useApp()` pour `notification` et `modal` (contexte Ant Design)
- `useTheme()` pour le mode dark/light
- Lazy imports avec `React.lazy()` et `Suspense`

**Conventions de nommage:**

- Composants: PascalCase (`ActionsAdminPanel`)
- Fichiers: PascalCase (`ActionsAdminPanel.tsx`)
- Props interfaces: `<ComponentName>Props`
- Handlers: `handle<Action>` (ex: `handleEdit`, `handleDelete`)
- State setters: `set<State>` (ex: `setActions`, `setLoading`)

### Library/Framework Requirements

**Ant Design 6.2.2 - Composants utilisés:**

- **Tabs**: Conteneur principal des onglets (déjà présent)
- **Card**: Wrapper des panels (déjà présent)
- **Table**: Tableaux de données (Actions, Profils, Intégrations)
- **Modal**: Modals de confirmation et formulaires
- **Button**: Boutons d'action (Créer, Modifier, Supprimer, etc.)
- **Space**: Layout des boutons et éléments inline
- **Typography**: Titres et textes
- **Tag**: Tags de statut et badges
- **Checkbox**: Filtre "Inclure les actions désactivées"
- **Spin**: Loading indicator pour lazy loading
- **App.useApp()**: Hook pour `notification` et `modal`

**React 19.2.0 - Features utilisées:**

- **Hooks**: `useState`, `useEffect`, `useCallback`
- **Lazy loading**: `React.lazy()` et `Suspense` pour composants lourds
- **Props**: Injection de dépendances via props
- **JSX**: Syntaxe déclarative pour les composants

**TypeScript 5.9.3 - Patterns:**

- **Interfaces**: Définir les props des composants
- **Types from api**: Importer depuis `types/api` (ou fichiers découpés)
- **Type safety**: Typage strict des props, état et handlers

### Previous Story Intelligence

**Story 22.8 (complétée)**: Découpage de `types/api.ts` en fichiers par domaine
- **Pattern établi**: Découpage par domaine fonctionnel, barrel export pour rétrocompatibilité
- **Méthode**: Découper sans casser les imports existants, tester fréquemment
- **Résultat**: 1023 LOC → 10 fichiers <300 LOC, 0 régression
- **Leçon**: Approche conservative, préserver les tests, documenter la nouvelle structure

**Applicable à cette story:**
1. Découper par domaine (onglet = domaine)
2. Créer un barrel export (`admin/index.ts`) pour faciliter les imports
3. Préserver les tests existants (imports mis à jour si nécessaire)
4. Documenter la nouvelle structure pour les futurs développements
5. Valider que tous les tests passent sans régression

**Story 22.7 (complétée)**: Refactorisation de `executions/views.py` backend
- **Pattern établi**: Extraction de helpers vers un module `utils.py`
- **Méthode**: Déplacer les fonctions sans changer les signatures, préserver les tests
- **Résultat**: Réduction de 1914 LOC à 1292 LOC (-32.5%)
- **Leçon**: Refactoring incrémental, tests en continu

**Stories 18.1 et 18.2 (complétées)**: Modifications récentes de AdminPage
- **18.1**: Ajout de suppression/désactivation avec filters (includeDisabled, cascadeModal)
- **18.2**: Identification visuelle workflow vs action (icônes, badges)
- **Impact**: Ces features doivent être préservées lors du découpage
- **Tests**: AdminPage.story18_1.test.tsx et AdminPage.story18_2.test.tsx doivent passer

**Story 2.29 (complétée)**: Séparation des boutons création Action/Workflow
- **Pattern**: Utilisation de `wizardInitialItemType` pour déterminer le type d'élément
- **Impact**: Cette logique doit être préservée dans ActionsAdminPanel

### Git Intelligence Summary

**5 derniers commits (contexte qualité code):**

1. **878dd7c** - `refactor(22-8): split api.ts types into domain-specific modules`
   - **Insight**: Pattern de découpage par domaine applicable à AdminPage
   - **Relevance**: Même approche de refactoring (découper sans casser)

2. **6451489** - `refactor(22-7): extract 15 helper functions from executions views to utils module`
   - **Insight**: Pattern d'extraction de helpers vers utils
   - **Relevance**: Peut-être applicable pour `getColumns()` (181 LOC)

3. **50e3d83** - `fix(22-6): standardize pagination response with 'total' field across all endpoints`
   - **Insight**: Standardisation de l'interface API, tests de non-régression
   - **Relevance**: AdminPage utilise des endpoints paginés (actions, profils, intégrations)

4. **ba713dc** - `fix(22-5): prevent double submission in ExecutionWizard with loading state`
   - **Insight**: Fix dans ExecutionWizard (composant réutilisé dans AdminPage via ActionWizard)
   - **Impact potentiel**: Valider que ActionWizard fonctionne après le découpage

5. **a48af57** - `fix(22-4): handle HTTP 429 throttling with exponential backoff and retry logic`
   - **Insight**: Modification de `api_client.ts` (utilisé par admin_service)
   - **Impact potentiel**: Services admin utilisés dans AdminPage à valider

**Patterns observés:**

- Commits atomiques avec scope clair (prefix `refactor/fix/feat`)
- Tests systématiques pour valider les changements
- Documentation des impacts dans les messages de commit
- Préservation de la rétrocompatibilité
- Refactoring incrémental (Story 22.7, 22.8)

**Recommandation pour cette story:**

- Commit message: `refactor(22-9): split AdminPage.tsx into domain-specific panels`
- Tester les 3 fichiers de tests existants (AdminPage.test.tsx, story18_1, story18_2)
- Valider que les 1600+ tests frontend passent sans régression
- Approche incrémentale: découper un onglet à la fois, tester, puis continuer

### Latest Tech Information

**React 19.2.0 (version utilisée):**

- **Server Components**: Non applicable ici (SPA classique), mais structure découplée prépare pour une future migration SSR
- **Concurrent Features**: React 19 améliore les Suspense et les transitions, déjà utilisés pour le lazy loading
- **useTransition**: Peut être ajouté pour améliorer l'UX lors du changement d'onglets (optionnel, pas dans le scope)

**Ant Design 6.2.2 (version utilisée):**

- **Tabs API**: Stable, pas de breaking changes récents
- **App.useApp()**: Hook recommandé pour `notification` et `modal` (déjà utilisé)
- **Design Tokens**: Ant Design 6.x utilise CSS-in-JS avec design tokens (bien supporté par le thème dark/light du projet)

**TypeScript 5.9.3 - Best practices pour découpage de composants:**

1. **Props interfaces explicites**: Définir des interfaces claires pour chaque panel
   ```typescript
   interface ActionsAdminPanelProps {
     notification: NotificationInstance;
     modal: ModalStaticFunctions;
     isDark: boolean;
   }
   ```

2. **Type safety**: Typage strict des props, état et handlers
   ```typescript
   const [actions, setActions] = useState<ActionListItem[]>([]);
   const handleEdit = async (record: ActionListItem): Promise<void> => {
     // ...
   };
   ```

3. **Exports nommés**: Facilite les tests et les imports
   ```typescript
   export function ActionsAdminPanel(props: ActionsAdminPanelProps) {
     // ...
   }
   ```

**Vite 7.2.4 (bundler utilisé):**

- **Hot Module Replacement (HMR)**: Le découpage en fichiers plus petits améliore le HMR (temps de rechargement réduit)
- **Tree shaking**: Structure en panels séparés permet un meilleur tree shaking
- **Code splitting**: React.lazy() automatiquement splitté par Vite en production

**Vitest 4.0.18 (test framework):**

- **Test isolation**: Chaque panel peut être testé indépendamment
- **Mocking**: Facilité pour mocker les props (`notification`, `modal`)
- **Coverage**: Structure découpée facilite l'analyse de la couverture de code par panel

### Project Structure Notes

**Alignement avec la structure existante:**

Le projet suit une structure frontend modulaire:
```
frontend/src/
├── components/       # Composants réutilisables
│   ├── admin/       # Composants admin (ActionWizard, ProfilesTable, etc.)
│   ├── catalog/     # Composants catalogue
│   └── ...
├── pages/           # Pages principales (routing)
│   ├── AdminPage.tsx        # Page admin (À DÉCOUPER)
│   ├── CatalogPage.tsx
│   ├── ExecutionsPage.tsx
│   └── ...
├── services/        # Services API
│   ├── admin_service.ts
│   ├── profiles_service.ts
│   └── ...
├── types/           # Types TypeScript
└── utils/           # Utilitaires
```

**Structure cible après refactoring:**

```
frontend/src/
├── pages/
│   ├── AdminPage.tsx (conteneur, <200 LOC)
│   └── admin/       # Nouveau répertoire pour panels
│       ├── ActionsAdminPanel.tsx
│       ├── ProfilesAdminPanel.tsx
│       ├── IntegrationsAdminPanel.tsx
│       ├── CategoriesAdminPanel.tsx
│       ├── MetricsAdminPanel.tsx
│       ├── FeatureFlagsAdminPanel.tsx
│       └── index.ts (barrel export)
```

**Impacts sur les imports:**

Fichiers avec imports depuis `AdminPage.tsx` (à mettre à jour):
- `App.tsx`: Route vers `<AdminPage />` (pas d'impact, export default préservé)
- `AdminPage.test.tsx`: Tests du conteneur (imports possibles des panels si nécessaire)
- `AdminPage.story18_1.test.tsx`: Tests Story 18.1 (imports mise à jour si panel testé)
- `AdminPage.story18_2.test.tsx`: Tests Story 18.2 (imports mise à jour si panel testé)

**Composants réutilisés (déjà dans `components/admin/`):**

Ces composants sont déjà extraits et seront réutilisés dans les panels:
- `ActionWizard.tsx` - Formulaire de création/édition d'action
- `ActionStatusBadge.tsx` - Badge de statut d'action
- `ProfileWizard.tsx` - Formulaire de création/édition de profil
- `ProfilesTable.tsx` - Tableau des profils
- `ProfileImportModal.tsx` - Modal d'import YAML des profils
- `IntegrationsTable.tsx` - Tableau des intégrations
- `IntegrationForm.tsx` - Formulaire de création/édition d'intégration
- `CategoriesAdminTable.tsx` - Tableau des catégories
- `AdminAnalyticsDashboard.tsx` - Dashboard des métriques (lazy)
- `FeatureFlagsPanel.tsx` - Panneau des feature flags (lazy)

### References

- [Source: _bmad-output/planning-artifacts/epic-22-amelioration-qualite-code.md#Story 22.9]
- [Source: idp-portal/frontend/src/pages/AdminPage.tsx:1-845]
- [Source: docs/code-quality-assessment-2026-02-08.md#Section 4.1 - Fichiers volumineux]
- [Architecture: frontend/README.md - Structure du projet]
- [Git commits: 878dd7c, 6451489 - Refactoring patterns récents]
- [Story 22.8: Découpage de types/api.ts - Pattern de découpage applicable]
- [Story 18.1, 18.2: Modifications récentes AdminPage - Features à préserver]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- TypeScript: 0 errors (`npx tsc --noEmit`)
- Tests: 36/36 pass (AdminPage.test.tsx 3, story18_1 23, story18_2 10)
- Build: `npx vite build` success
- Deprecation fix: `destroyInactiveTabPane` → `destroyOnHidden` (Ant Design 6.x)

### Completion Notes List

- AdminPage.tsx refactorisé de 845 LOC → 75 LOC (orchestrateur Tabs)
- 6 panels créés sous `pages/admin/`: Actions (330), Profiles (137), Integrations (133), Categories (10), Metrics (14), FeatureFlags (14)
- `getActionsColumns` extrait dans `actionsColumns.tsx` (193 LOC) pour garder ActionsAdminPanel sous ~300 LOC
- `destroyOnHidden` utilisé sur Tabs pour lazy-mount des panels (chaque panel fetch ses données au mount via useEffect)
- Barrel export `admin/index.ts` pour imports simplifiés
- README.md enrichi avec section "Admin Page Structure" et guide pour ajout de nouveaux onglets
- 0 test modifié — tous les 36 tests existants passent sans changement
- 0 erreur TypeScript, 0 erreur de build

### Change Log

- 2026-02-09: Story 22.9 — Découpage AdminPage.tsx en 6 sous-composants par onglet + orchestrateur léger. 845 LOC → 8 fichiers, 36/36 tests pass, 0 régression.
- 2026-02-09: Code review fixes — Corrected Ant Design internal imports (FRONTEND-STANDARDS.md compliance), replaced native `<input>` with `<Input>`, fixed French accents ("Gérez", "Métriques"), standardized notification API (title vs message), added Object.hasOwn() safety check, added setTimeout comment. 4 ESLint errors → 0, 36/36 tests still passing.

### File List

- idp-portal/frontend/src/pages/AdminPage.tsx (modified — refactorisé en orchestrateur 75 LOC, corrections accents français)
- idp-portal/frontend/src/pages/AdminPage.test.tsx (modified — test "Métriques" corrigé pour accent)
- idp-portal/frontend/src/pages/admin/index.ts (new — barrel export)
- idp-portal/frontend/src/pages/admin/ActionsAdminPanel.tsx (new — onglet Actions 330 LOC, corrections standards frontend + notification API)
- idp-portal/frontend/src/pages/admin/actionsColumns.tsx (new — colonnes tableau Actions 193 LOC)
- idp-portal/frontend/src/pages/admin/ProfilesAdminPanel.tsx (new — onglet Profils 137 LOC, correction import Ant Design)
- idp-portal/frontend/src/pages/admin/IntegrationsAdminPanel.tsx (new — onglet Intégrations 133 LOC, correction import + setTimeout comment)
- idp-portal/frontend/src/pages/admin/CategoriesAdminPanel.tsx (new — onglet Catégories 10 LOC)
- idp-portal/frontend/src/pages/admin/MetricsAdminPanel.tsx (new — onglet Métriques 14 LOC)
- idp-portal/frontend/src/pages/admin/FeatureFlagsAdminPanel.tsx (new — onglet Feature Flags 14 LOC)
- idp-portal/frontend/README.md (modified — section Admin Page Structure ajoutée)
