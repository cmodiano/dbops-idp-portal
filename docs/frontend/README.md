# Documentation Frontend IDP Portal

Documentation technique du frontend React de l'IDP Portal (DBOps).

## Index de navigation

| Document | Description |
|----------|-------------|
| [folder-structure.md](./folder-structure.md) | Structure des dossiers et organisation du code |
| [components.md](./components.md) | Composants principaux par feature |
| [state-management.md](./state-management.md) | Contexts, hooks et gestion d'état |
| [routing.md](./routing.md) | Routes, guards et navigation |
| [api-integration.md](./api-integration.md) | Services, types API et client HTTP |
| [design-system.md](./design-system.md) | Ant Design 6, thèmes et liquid glass |
| [testing.md](./testing.md) | Stratégie de test et patterns |
| [contributing.md](./contributing.md) | Guide de contribution et setup dev |

---

## Vue d'ensemble

### Stack technique

| Technologie | Version | Rôle |
|-------------|---------|------|
| React | 19.2.0 | Framework UI |
| TypeScript | 5.9.3 | Typage statique |
| Vite | 7.2.4 | Build tool et dev server |
| Ant Design | 6.2.2 | Bibliothèque de composants |
| React Router | 7.13.0 | Routing SPA |
| Recharts | 3.7.0 | Graphiques |
| Vitest | 4.0.18 | Framework de test |

### Patterns architecturaux

- **Functional Components Only** - Pas de class components
- **Service Layer Pattern** - Toutes les API calls via `/services/`
- **Context + Hooks** - State management sans Redux
- **URL Filter Persistence** - Filtres dans query params
- **WebSocket Real-time** - Updates temps réel

---

## Diagrammes

### Hiérarchie des composants principaux

```
                            App
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ThemeProvider   ConfigProvider   AuthProvider
                             │
                       DashboardProvider
                             │
                      BrowserRouter
                             │
                          Routes
                             │
     ┌───────────┬───────────┼───────────┬───────────┐
     │           │           │           │           │
  LoginPage   AppLayout   AuditPage  AdminPage  NotFoundPage
                 │
          ┌──────┼──────┐
          │             │
       TopNav        <Outlet>
                        │
     ┌──────────────────┼──────────────────┐
     │                  │                  │
 CatalogPage      ExecutionsPage     DashboardPage
     │                  │                  │
┌────┴────┐        ┌────┴────┐       ┌────┴────┐
│         │        │         │       │         │
ActionCard ExecutionWizard ExecutionTimeline ReportingDashboard
ActionTable       │         │              │
TagCloud    ExecutionsFiltersPanel    StatCard
CategoryTabs                         TrendLineChart
```

### Flux de données (API → Service → Hook → Component)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Backend Django                           │
│                        /api/v1/*                                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       api_client.ts                             │
│  ┌─────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐   │
│  │apiFetch │ │apiFetchRaw│ │apiFetchBlob│ │apiPostFormData │   │
│  └────┬────┘ └─────┬─────┘ └─────┬─────┘ └───────┬─────────┘   │
│       │            │             │               │              │
│       └────────────┴──────┬──────┴───────────────┘              │
│                           │                                     │
│              ┌────────────┴────────────┐                        │
│              │ Auth: Bearer Token      │                        │
│              │ 401 Interceptor: Retry  │                        │
│              │ Error: JSON/Text parse  │                        │
│              └────────────┬────────────┘                        │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Services                                │
│  ┌───────────────┐ ┌─────────────────┐ ┌──────────────────┐    │
│  │catalog_service│ │execution_service│ │dashboard_service │    │
│  │               │ │                 │ │                  │    │
│  │fetchActions() │ │submitExecution()│ │getDashboardStats│    │
│  │fetchTags()    │ │getExecution()   │ │getTimeSeries()   │    │
│  │addFavorite()  │ │getSteps()       │ │                  │    │
│  └───────┬───────┘ └────────┬────────┘ └────────┬─────────┘    │
└──────────┼──────────────────┼───────────────────┼──────────────┘
           │                  │                   │
           ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Custom Hooks                                │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────┐        │
│  │useState +   │ │useWebSocket │ │useExecutionFilters │        │
│  │useEffect    │ │(real-time)  │ │useUrlFilters       │        │
│  │(data fetch) │ │             │ │(URL persistence)   │        │
│  └──────┬──────┘ └──────┬──────┘ └─────────┬──────────┘        │
└─────────┼───────────────┼──────────────────┼───────────────────┘
          │               │                  │
          ▼               ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Components                               │
│  ┌───────────┐ ┌─────────────────┐ ┌─────────────────────┐     │
│  │CatalogPage│ │ExecutionTimeline│ │ExecutionsFiltersPanel│    │
│  │           │ │                 │ │                     │     │
│  │ actions[] │ │ steps[]         │ │ filters{}           │     │
│  │ loading   │ │ execution       │ │ onChange()          │     │
│  │ error     │ │ connected       │ │                     │     │
│  └─────┬─────┘ └────────┬────────┘ └──────────┬──────────┘     │
└────────┼────────────────┼─────────────────────┼─────────────────┘
         │                │                     │
         ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                         UI Render                               │
│        ActionCard, ActionTable, Timeline, Filters, etc.         │
└─────────────────────────────────────────────────────────────────┘
```

### Flux d'authentification SAML

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ Browser  │     │   Frontend   │     │   Backend    │     │ IdP SAML │
└────┬─────┘     └──────┬───────┘     └──────┬───────┘     └────┬─────┘
     │                  │                    │                  │
     │  GET /catalog    │                    │                  │
     │─────────────────▶│                    │                  │
     │                  │                    │                  │
     │  ProtectedRoute  │                    │                  │
     │  isLoading=true  │                    │                  │
     │◀─── Spinner ─────│                    │                  │
     │                  │                    │                  │
     │                  │ POST /auth/refresh │                  │
     │                  │───────────────────▶│                  │
     │                  │   401 (no cookie)  │                  │
     │                  │◀───────────────────│                  │
     │                  │                    │                  │
     │◀── Redirect ─────│                    │                  │
     │    /login        │                    │                  │
     │                  │                    │                  │
     │ Click "Login"    │                    │                  │
     │─────────────────▶│                    │                  │
     │                  │                    │                  │
     │ Redirect /api/v1/auth/saml/login     │                  │
     │──────────────────────────────────────▶│                  │
     │                  │                    │                  │
     │                  │                    │ SAML AuthnRequest │
     │                  │                    │─────────────────▶│
     │                  │                    │                  │
     │◀─────────────────────────────────────────── Login Form ──│
     │                  │                    │                  │
     │── Credentials ───────────────────────────────────────────▶│
     │                  │                    │                  │
     │◀────────────────────────────────── SAML Response ────────│
     │                  │                    │                  │
     │ Redirect /auth/callback#access_token=TOKEN               │
     │─────────────────▶│                    │                  │
     │                  │                    │                  │
     │                  │ Extract token      │                  │
     │                  │ from URL hash      │                  │
     │                  │                    │                  │
     │                  │ GET /auth/me       │                  │
     │                  │───────────────────▶│                  │
     │                  │   { user data }    │                  │
     │                  │◀───────────────────│                  │
     │                  │                    │                  │
     │◀── Redirect ─────│                    │                  │
     │    /catalog      │                    │                  │
```

### Flux d'exécution d'action (ExecutionWizard)

```
┌────────────────────────────────────────────────────────────────────┐
│                       ExecutionWizard                              │
│                                                                    │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐  │
│  │   Step 1   │──▶│   Step 2   │──▶│   Step 3   │──▶│  Step 4  │  │
│  │ Paramètres │   │   Impact   │   │Planification│   │Confirmation│
│  └─────┬──────┘   └─────┬──────┘   └──────┬─────┘   └─────┬────┘  │
│        │                │                 │               │       │
│        ▼                ▼                 ▼               ▼       │
│  ┌───────────┐   ┌───────────┐    ┌───────────┐   ┌───────────┐  │
│  │Form inputs│   │ImpactCard │    │DatePicker │   │Summary    │  │
│  │dynamiques │   │ApprovalBox│    │Radio      │   │SubmitBtn  │  │
│  │(JSON      │   │           │    │(immédiate/│   │           │  │
│  │ Schema)   │   │           │    │ planifiée)│   │           │  │
│  └───────────┘   └───────────┘    └───────────┘   └───────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ onFinish()
                                    ▼
                           ┌─────────────────┐
                           │ execution_service│
                           │ .submitExecution()│
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ POST /executions │
                           └────────┬────────┘
                                    │
                                    ▼
                      ┌──────────────────────────┐
                      │ { execution_id, status } │
                      └──────────────────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
                     ▼                             ▼
            ┌─────────────┐              ┌─────────────────┐
            │  Immediate  │              │    Scheduled    │
            │             │              │                 │
            │ Navigate to │              │ Navigate to     │
            │ /executions │              │ /admin/scheduled│
            └─────────────┘              └─────────────────┘
```

---

## Statistiques du codebase

| Métrique | Valeur |
|----------|--------|
| Composants | 40+ |
| Pages | 8 |
| Custom hooks | 13+ |
| Services API | 9 |
| React Contexts | 3 |
| Fichiers de test | 30+ |
| Types API | ~936 lignes |
| Total lignes de code | ~10,000+ |

---

## Quick Start

```bash
# Installation
cd idp-portal/frontend
npm install

# Configuration dev
cp .env.development .env.local
# Éditer VITE_DEV_AUTH=true pour bypasser SAML

# Démarrage
npm run dev
# → http://localhost:5173

# Tests
npm run test
```

---

## Liens utiles

- [FRONTEND-STANDARDS.md](FRONTEND-STANDARDS.md) - Conventions de développement
- [Ant Design 6 Documentation](https://ant.design)
- [React Router v7](https://reactrouter.com)
- [Vitest Documentation](https://vitest.dev)
