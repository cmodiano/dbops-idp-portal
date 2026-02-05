# Story 12.2: Documentation frontend implementation

Status: done

<!-- Story context engine analysis completed - comprehensive developer guide created -->

## Story

As a développeur frontend rejoignant l'équipe,
I want une documentation détaillée de l'implémentation frontend (React),
So that je peux comprendre rapidement la structure, les composants et les patterns utilisés.

## Acceptance Criteria

**Given** le frontend React est en production
**When** la documentation frontend est rédigée
**Then** elle inclut : structure des dossiers et organisation du code, composants principaux et leurs responsabilités, gestion d'état (hooks, context), routing et navigation, intégration avec l'API backend, theming et design system (Ant Design), tests et couverture

**Given** un développeur consulte la documentation
**When** il cherche une information spécifique (ex: comment ajouter une nouvelle page)
**Then** il trouve un guide pas-à-pas avec exemples de code

**And** la documentation inclut des diagrammes de composants et flux de données
**And** la documentation inclut un guide de contribution frontend (setup dev, conventions, processus de review)
**And** la documentation est maintenue à jour avec les changements majeurs

## Tasks / Subtasks

- [x] Task 1: Documenter la structure des dossiers et organisation du code (AC: 1)
  - [x] Documenter la structure racine (src/, public/, config files)
  - [x] Documenter les dossiers principaux (components/, pages/, hooks/, services/, contexts/, types/, utils/, theme/)
  - [x] Documenter les conventions de nommage et organisation par feature
  - [x] Créer un diagramme ASCII de l'arborescence avec descriptions

- [x] Task 2: Documenter les composants principaux et leurs responsabilités (AC: 1)
  - [x] Documenter les composants admin/ (ActionForm, ActionWizard, ProfileWizard, etc.)
  - [x] Documenter les composants catalog/ (ActionCard, ActionTable, ExecutionWizard, CategoryTabs, etc.)
  - [x] Documenter les composants dashboard/ (StatCard, RecentExecutions, ReportingDashboard, etc.)
  - [x] Documenter les composants layout/ (AppLayout, TopNav)
  - [x] Documenter les composants shared/ (ImpactIndicator, CronExpressionHelper)
  - [x] Inclure pour chaque composant: props, usage, dépendances

- [x] Task 3: Documenter la gestion d'état (hooks, context) (AC: 1)
  - [x] Documenter AuthContext (authentication SAML, token management)
  - [x] Documenter ThemeContext (light/dark mode toggle)
  - [x] Documenter DashboardContext (unseen error count)
  - [x] Documenter les custom hooks (useAuth, useWebSocket, useDebounce, useExecutionFilters, useUrlFilters, etc.)
  - [x] Expliquer les patterns de state management utilisés (Context + hooks vs Redux)

- [x] Task 4: Documenter le routing et la navigation (AC: 1)
  - [x] Documenter les routes dans App.tsx (/, /catalog, /executions, /analytics, /admin, /audit, /login)
  - [x] Documenter ProtectedRoute et les guards (AdminGuard, AuditGuard, AnalyticsGuard)
  - [x] Documenter le contrôle d'accès par profil et tabs de navigation
  - [x] Créer un diagramme ASCII du flow de navigation

- [x] Task 5: Documenter l'intégration avec l'API backend (AC: 1)
  - [x] Documenter api_client.ts (apiFetch, apiFetchRaw, apiFetchBlob, apiPostFormData)
  - [x] Documenter les services (catalog_service, execution_service, admin_service, etc.)
  - [x] Documenter les types API dans types/api.ts
  - [x] Documenter la gestion du token Bearer et refresh 401
  - [x] Documenter les patterns de gestion d'erreurs

- [x] Task 6: Documenter le theming et design system Ant Design (AC: 1)
  - [x] Documenter la configuration Ant Design 6 (ConfigProvider, themes)
  - [x] Documenter les thèmes light/dark dans desjardins.ts
  - [x] Documenter les design tokens dans styleTokens.ts
  - [x] Documenter le style liquid glass (styles/glass.css)
  - [x] Documenter les règles d'utilisation Ant Design (App.useApp(), imports publics)

- [x] Task 7: Documenter les tests et couverture (AC: 1)
  - [x] Documenter la stack de test (Vitest, React Testing Library, happy-dom)
  - [x] Documenter la structure des fichiers de test
  - [x] Documenter les patterns de test (wrapping, mocking, async/act)
  - [x] Documenter la configuration dans test-setup.ts et vite.config.ts
  - [x] Documenter les commandes npm (test, test:watch)

- [x] Task 8: Créer des guides pas-à-pas avec exemples de code (AC: 2)
  - [x] Guide: Comment ajouter une nouvelle page
  - [x] Guide: Comment ajouter un nouveau composant
  - [x] Guide: Comment ajouter un nouveau service API
  - [x] Guide: Comment ajouter un custom hook
  - [x] Guide: Comment ajouter un test pour un composant

- [x] Task 9: Créer des diagrammes de composants et flux de données (AC: 3)
  - [x] Diagramme de hiérarchie des composants principaux
  - [x] Diagramme de flux de données (API → Service → Hook → Component)
  - [x] Diagramme de flux d'authentification SAML
  - [x] Diagramme de flux d'exécution d'action (ExecutionWizard flow)

- [x] Task 10: Créer un guide de contribution frontend (AC: 4)
  - [x] Setup environnement de développement (npm install, .env.development, VITE_DEV_AUTH)
  - [x] Conventions de code (naming, structure, TypeScript, ESLint)
  - [x] Processus de review et validation
  - [x] Comment maintenir la documentation à jour

## Dev Notes

### Architecture Frontend Actuelle

**Stack technique:**
- React 19.2.0 - Framework UI
- TypeScript 5.9.3 - Typage statique
- Vite 7.2.4 - Build tool et dev server
- Ant Design 6.2.2 - Bibliothèque de composants UI
- React Router 7.13.0 - Routing SPA
- Recharts 3.7.0 - Graphiques et visualisations
- Vitest 4.0.18 - Framework de test

**Patterns architecturaux:**
1. **Functional Components Only** - Pas de class components
2. **Service Layer Pattern** - Toutes les API calls passent par /services/
3. **Context + Hooks** - State management sans Redux
4. **URL Filter Persistence** - useUrlFilters pour conserver les filtres dans l'URL
5. **WebSocket Real-time** - useWebSocket pour updates en temps réel

### Structure des dossiers

```
src/
├── components/           # Composants réutilisables par feature
│   ├── admin/           # 24+ fichiers - Admin dashboard
│   ├── auth/            # ProtectedRoute
│   ├── catalog/         # Catalogue actions
│   ├── dashboard/       # Dashboard & reporting
│   ├── execution/       # Détail exécution
│   ├── executions/      # Liste exécutions
│   ├── layout/          # AppLayout, TopNav
│   └── shared/          # Composants partagés
├── pages/               # Pages principales (8 pages)
├── contexts/            # React Context (3 contexts)
├── hooks/               # Custom hooks (13+ hooks)
├── services/            # Intégration API (9 services)
├── types/               # Types TypeScript (api.ts ~936 lignes)
├── utils/               # Fonctions utilitaires
├── theme/               # Design system (desjardins.ts, styleTokens.ts)
├── styles/              # CSS global (glass.css)
├── App.tsx              # Root component avec routing
└── main.tsx             # Entry point React DOM
```

### Composants clés par feature

**Admin (src/components/admin/):**
- `ActionWizard.tsx` - Wizard multi-étapes création/édition action
- `ProfileWizard.tsx` - Wizard profils avec permissions
- `ParametersEditor.tsx` - Éditeur visuel JSON Schema
- `ImpactRulesEditor.tsx` - Règles d'impact par environnement
- `RemediationRulesEditor.tsx` - Actions correctives
- `IntegrationForm.tsx` - Gestion intégrations (AAP, ServiceNow)

**Catalog (src/components/catalog/):**
- `ExecutionWizard.tsx` - 51KB - Plus gros composant, wizard d'exécution 4 étapes
- `ActionCard.tsx` - Vue grille des actions
- `ActionTable.tsx` - Vue liste des actions
- `ActionDrawerPreview.tsx` - Preview détaillée en drawer
- `CategoryTabs.tsx` - Navigation par catégorie
- `TagCloud.tsx` - Nuage de tags pour filtrage

**Dashboard (src/components/dashboard/):**
- `ReportingDashboard.tsx` - Analytics avancés
- `StatCard.tsx` - Cartes KPI
- `TrendLineChart.tsx` - Graphiques temporels
- `ComparisonPanel.tsx` - Comparaisons métriques

### State Management

**Contexts (src/contexts/):**

| Context | Responsabilité | Hook |
|---------|---------------|------|
| AuthContext | Auth SAML, token, user, permissions | useAuth() |
| ThemeContext | Light/dark mode, localStorage | useTheme() |
| DashboardContext | Compteur erreurs non vues | useDashboard() |

**Custom Hooks clés:**

| Hook | Fichier | Responsabilité |
|------|---------|---------------|
| useAuth | AuthContext.tsx | Accès user, token, isAuthenticated |
| useWebSocket | useWebSocket.ts (173 lignes) | Updates temps réel exécution |
| useExecutionFilters | useExecutionFilters.ts (143 lignes) | State filtres exécutions |
| useUrlFilters | useUrlFilters.ts (179 lignes) | Persistence filtres URL |
| useDebounce | useDebounce.ts (21 lignes) | Debounce recherche |
| useRemediationSuggestions | useRemediationSuggestions.ts | Récupération suggestions remédiation |

### Intégration API

**api_client.ts:**
```typescript
// 4 méthodes principales
apiFetch<T>(path, init?)      // Retourne .data
apiFetchRaw<T>(path, init?)   // Retourne réponse complète
apiFetchBlob(path)            // Téléchargement fichiers
apiPostFormData<T>(path, formData)  // Upload FormData

// Features
- Injection Bearer token depuis AuthContext
- Intercepteur 401 avec retry après refresh token
- Gestion erreurs structurées (JSON ou text)
- API_BASE = '/api/v1'
```

**Services disponibles:**
- `auth_service.ts` - loginUrl(), refreshAccessToken(), fetchCurrentUser()
- `catalog_service.ts` - fetchCatalogActions(), fetchFavorites(), addFavorite()
- `execution_service.ts` - submitExecution(), getExecution(), getExecutionSteps()
- `admin_service.ts` - createAction(), updateAction(), publishAction()
- `dashboard_service.ts` - getDashboardStats(), getDashboardTimeSeriesData()
- `audit_service.ts` - listAuditExecutions()
- `profiles_service.ts` - createProfile(), updateProfile(), listProfiles()
- `integrations_service.ts` - listIntegrations(), createIntegration()
- `scheduled_execution_service.ts` - createScheduledExecution(), cancelScheduledExecution()

### Design System Ant Design 6

**Configuration (theme/desjardins.ts):**
- Couleur primaire: #00874E (vert Desjardins)
- 2 thèmes: lightTheme, darkTheme
- ConfigProvider wrapping dans App.tsx

**Design Tokens (styleTokens.ts):**
```typescript
STYLE_TOKENS = {
  colorPrimary: '#00874E',
  engineIconColor: { Oracle: '#EF4444', 'SQL Server': '#3B82F6', DB2: '#10B981' },
  impactColor: { low: '#10B981', medium: '#F59E0B', high: '#F97316', critical: '#EF4444' }
}
```

**Règles Ant Design 6 importantes:**
1. Utiliser imports publics uniquement (pas `antd/es/*`)
2. Message/notification via `App.useApp()` hook
3. Composants utilisant `App.useApp()` doivent être wrappés dans `<App>`
4. Modal.confirm via `App.useApp().modal`

### Testing

**Stack:**
- Vitest 4.0.18 - Framework
- React Testing Library @16.3.2 - Utilities
- happy-dom - DOM environment

**Configuration (test-setup.ts):**
```typescript
- Mock window.matchMedia (breakpoints Ant Design)
- Mock ResizeObserver (composants responsive)
- Import @testing-library/jest-dom matchers
```

**Patterns de test:**
1. Wrapper `<App>` pour composants utilisant `App.useApp()`
2. Utiliser `act()` pour updates async
3. Mock des services API dans les tests de composants
4. @testing-library/user-event pour interactions utilisateur

**Commandes:**
```bash
npm run test        # Run once
npm run test:watch  # Watch mode
```

### Routing et Navigation

**Routes (App.tsx):**

| Route | Page | Guard | Accès |
|-------|------|-------|-------|
| `/` | Redirect → /catalog | - | Tous |
| `/catalog` | CatalogPage | ProtectedRoute | Authentifié |
| `/executions` | ExecutionsPage | ProtectedRoute | Authentifié |
| `/analytics` | DashboardPage | AnalyticsGuard | DBOPS only |
| `/admin` | AdminPage | AdminGuard | Tab admin |
| `/audit` | AuditPage | AuditGuard | Tab audit ou is_auditor |
| `/login` | LoginPage | - | Non authentifié |
| `/auth/callback` | AuthCallbackPage | - | Flow auth |

**Guards:**
- `AdminGuard` - vérifie `hasTab('admin')`
- `AuditGuard` - vérifie `hasTab('audit')` ou `is_auditor`
- `AnalyticsGuard` - profil DBOPS uniquement

### Conventions de code (FRONTEND-STANDARDS.md)

**Nommage:**
- Components: PascalCase (`ActionCard.tsx`)
- Hooks: préfixe `use` (`useDebounce.ts`)
- Services: snake_case (`catalog_service.ts`)
- Données API: snake_case (`action_id`, `created_at`)
- Props/Variables: camelCase (`isLoading`, `onSubmit`)

**Structure fichiers:**
- Un composant par fichier
- Barrel exports via `index.ts` dans chaque feature
- Tests co-localisés (`Component.test.tsx`)

### Learnings de la story 12-1 (Backend Documentation)

**Patterns récurrents à éviter:**
1. Ne pas oublier de documenter les méthodes moins visibles (get_by_id, etc.)
2. Vérifier que les signatures de fonctions documentées correspondent à l'implémentation
3. Inclure des exemples d'utilisation pour chaque section
4. Utiliser des diagrammes ASCII pour compatibilité universelle

**Recommandations appliquées:**
- Créer une checklist standard pour nouveaux composants
- Documenter les décisions architecturales (ADRs)
- Inclure guide de contribution avec setup dev détaillé

### Project Structure Notes

**Alignement avec architecture:**
- Structure conforme à FRONTEND-STANDARDS.md
- Components organisés par feature (admin, catalog, dashboard)
- Services alignés sur les endpoints API backend
- Types alignés sur les réponses API (types/api.ts)

**Conventions documentées:**
- FRONTEND-STANDARDS.md - Guide complet des conventions frontend
- README dans idp-portal/frontend/ si existant

### Technical Stack Versions (Février 2026)

| Technologie | Version | Notes |
|-------------|---------|-------|
| React | 19.2.0 | Framework UI principal |
| TypeScript | 5.9.3 | Typage statique |
| Vite | 7.2.4 | Build tool + dev server |
| Ant Design | 6.2.2 | Component library |
| React Router | 7.13.0 | Routing SPA |
| Recharts | 3.7.0 | Charts |
| Vitest | 4.0.18 | Testing framework |
| @dnd-kit | 6.3.1+ | Drag & drop |

### Statistiques codebase

- **Composants:** 40+ composants réutilisables
- **Pages:** 8 pages principales
- **Services:** 9 fichiers de services
- **Custom Hooks:** 13+ hooks personnalisés
- **Contexts:** 3 React contexts
- **Fichiers de test:** 30+ fichiers
- **Types API:** ~936 lignes dans api.ts
- **Total lignes de code:** ~10,000+ (excl. node_modules)

### References

**Structure et organisation:**
- [Source: idp-portal/frontend/src/] - Code source principal
- [Source: idp-portal/frontend/FRONTEND-STANDARDS.md] - Conventions de développement
- [Source: idp-portal/frontend/package.json] - Dépendances et scripts
- [Source: idp-portal/frontend/vite.config.ts] - Configuration Vite

**Composants clés:**
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx] - Plus gros composant (51KB)
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] - Wizard création action
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx] - Page catalogue principale

**State management:**
- [Source: idp-portal/frontend/src/contexts/AuthContext.tsx] - Auth SAML et tokens
- [Source: idp-portal/frontend/src/hooks/useWebSocket.ts] - Real-time updates

**API integration:**
- [Source: idp-portal/frontend/src/services/api_client.ts] - Client HTTP base
- [Source: idp-portal/frontend/src/types/api.ts] - Types API (~936 lignes)

**Design system:**
- [Source: idp-portal/frontend/src/theme/desjardins.ts] - Thèmes Ant Design
- [Source: idp-portal/frontend/src/theme/styleTokens.ts] - Design tokens
- [Source: idp-portal/frontend/src/styles/glass.css] - Liquid glass styles

**Tests:**
- [Source: idp-portal/frontend/src/test-setup.ts] - Configuration tests
- [Source: idp-portal/frontend/vite.config.ts] - Configuration Vitest

**Story précédente:**
- [Source: _bmad-output/implementation-artifacts/12-1-documentation-backend-implementation.md] - Documentation backend

**Epic et contexte:**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic-12] - Epic 12: Documentation technique

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Documentation story (no code execution)

### Completion Notes List

- ✅ Task 1: Created `folder-structure.md` with complete directory structure, ASCII diagrams, and naming conventions
- ✅ Task 2: Created `components.md` documenting 40+ components across admin, catalog, dashboard, execution, layout, and shared folders with props, usage examples, and dependencies
- ✅ Task 3: Created `state-management.md` documenting AuthContext, ThemeContext, DashboardContext, and 10+ custom hooks with usage patterns
- ✅ Task 4: Created `routing.md` with route table, guards (AdminGuard, AuditGuard, AnalyticsGuard), navigation flow diagram, and SAML auth flow
- ✅ Task 5: Created `api-integration.md` documenting api_client.ts (4 methods), 9 services, type patterns, error handling, and token management
- ✅ Task 6: Created `design-system.md` covering Ant Design 6 configuration, light/dark themes, styleTokens.ts, liquid glass CSS, and usage rules
- ✅ Task 7: Created `testing.md` with Vitest/RTL stack, test patterns (App wrapper, mocking, async/act), and debugging tips
- ✅ Task 8: Created guides in `contributing.md`: how to add page, component, service, hook, and tests with step-by-step examples
- ✅ Task 9: Created 4 ASCII diagrams in `README.md`: component hierarchy, data flow, SAML auth flow, ExecutionWizard flow
- ✅ Task 10: Created `contributing.md` with setup instructions, code conventions, PR checklist, and documentation maintenance guide

All acceptance criteria satisfied:
- AC1: Documentation includes structure, components, state, routing, API integration, theming, tests ✅
- AC2: Step-by-step guides with code examples for common tasks ✅
- AC3: ASCII diagrams for component hierarchy and data flows ✅
- AC4: Contribution guide with setup, conventions, and review process ✅

### Senior Developer Review (AI) — 2026-02-05

Correctifs appliqués après revue adversarial :
- **folder-structure.md** : ajout de `utils/debounce.ts` dans la liste des utilitaires (utilisé par ExecutionWizard pour validation cron).
- **state-management.md** : distinction useDebounce (valeur) vs `debounce(fn, waitMs)` (fonction) ; ajout sous-section "Utilitaire debounce (fonction)" avec exemple.
- **testing.md** : structure des fichiers de test corrigée (remplacement useDebounce.test.ts par useUrlFilters.test.tsx, le premier n'existant pas).
- **components.md** : dépendance ExecutionWizard → `utils/debounce` documentée.
- **File List** : précision du périmètre (cette story = docs frontend uniquement).
- **Change Log** : volume corrigé ~2500 → ~4300 lignes.

### File List

**Périmètre :** Cette story ne couvre que les fichiers listés ci-dessous. Les autres fichiers modifiés dans le repo (ex. `ExecutionWizard.tsx`, `api.ts`, `utils/debounce.ts`) relèvent d'autres stories ou de travaux parallèles.

**Created in `idp-portal/docs/frontend/`:**
- `README.md` - Point d'entrée avec vue d'ensemble, index de navigation, et diagrammes principaux
- `folder-structure.md` - Structure des dossiers et organisation du code
- `components.md` - Composants principaux par feature avec props et usage
- `state-management.md` - Contexts, hooks, patterns de gestion d'état
- `routing.md` - Routes, guards, navigation et contrôle d'accès
- `api-integration.md` - Services, types, gestion erreurs et tokens
- `design-system.md` - Ant Design 6, thèmes, tokens, liquid glass
- `testing.md` - Stack de test, patterns, configuration, commandes
- `contributing.md` - Setup dev, conventions, guides pas-à-pas

## Change Log

- 2026-02-05: Code review (adversarial) — 6 correctifs appliqués : folder-structure (ajout debounce.ts), state-management (distinction useDebounce vs utils/debounce + exemple), testing (structure exemples sans useDebounce.test.ts inexistant), components (dépendance ExecutionWizard → utils/debounce), File List (périmètre explicité), volume doc (~4300 lignes)
- 2026-02-05: Story 12-2 completed - Created comprehensive frontend documentation (9 files, ~4300 lines) covering all aspects of the React frontend implementation
