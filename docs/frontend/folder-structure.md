# Structure des dossiers Frontend

Ce document décrit l'organisation du code source du frontend IDP Portal.

## Structure racine

```
idp-portal/frontend/
├── public/                    # Assets statiques (favicon, manifest)
├── src/                       # Code source principal
├── dist/                      # Build de production (généré)
├── node_modules/              # Dépendances npm (généré)
├── .env.development           # Variables d'environnement - dev
├── .env.production            # Variables d'environnement - prod
├── .env.staging               # Variables d'environnement - staging
├── .env.local                 # Variables locales (git ignored)
├── package.json               # Dépendances et scripts npm
├── package-lock.json          # Lockfile npm
├── vite.config.ts             # Configuration Vite (build + test)
├── tsconfig.json              # Configuration TypeScript racine
├── tsconfig.app.json          # Config TS pour l'application
├── tsconfig.node.json         # Config TS pour config Node
├── eslint.config.js           # Configuration ESLint
├── index.html                 # Point d'entrée HTML
├── FRONTEND-STANDARDS.md      # Conventions et règles de développement
└── README.md                  # Documentation du frontend
```

## Structure du dossier src/

```
src/
├── App.tsx                    # Composant racine - routing et providers
├── App.test.tsx               # Tests du composant App
├── main.tsx                   # Point d'entrée React DOM
├── test-setup.ts              # Configuration Vitest/RTL
│
├── components/                # Composants React par feature
│   ├── admin/                 # 24+ composants administration
│   ├── auth/                  # Composants authentification
│   ├── catalog/               # Composants catalogue actions
│   ├── dashboard/             # Dashboard et statistiques
│   ├── execution/             # Détail d'une exécution
│   ├── executions/            # Liste des exécutions
│   ├── layout/                # Layout et navigation
│   └── shared/                # Composants partagés
│
├── pages/                     # Pages principales (8 pages)
│   ├── AdminPage.tsx          # Page administration
│   ├── AuditPage.tsx          # Page audit SOC1
│   ├── AuthCallbackPage.tsx   # Callback SAML
│   ├── CatalogPage.tsx        # Catalogue des actions
│   ├── DashboardPage.tsx      # Analytics (DBOPS only)
│   ├── ExecutionsPage.tsx     # Liste exécutions
│   ├── LoginPage.tsx          # Page de connexion
│   └── NotFoundPage.tsx       # Page 404
│
├── contexts/                  # React Contexts (state global)
│   ├── AuthContext.tsx        # Auth SAML, user, token, permissions
│   ├── ThemeContext.tsx       # Light/dark mode
│   └── DashboardContext.tsx   # Compteur erreurs non vues
│
├── hooks/                     # Custom hooks (13+ hooks)
│   ├── useDebounce.ts         # Debounce pour recherche
│   ├── useExecutionFilters.ts # State filtres exécutions
│   ├── useMediaQuery.ts       # Media queries responsive
│   ├── useThemeMode.ts        # Gestion mode thème
│   ├── useUrlFilters.ts       # Persistence filtres URL
│   ├── useWebSocket.ts        # WebSocket temps réel
│   ├── useDashboardWebSocket.ts    # WebSocket dashboard
│   ├── usePendingApprovalsCount.ts # Compteur approbations
│   ├── useRemediationContext.ts    # Context remédiation
│   └── useRemediationSuggestions.ts # Suggestions correctives
│
├── services/                  # Intégration API backend
│   ├── api_client.ts          # Client HTTP de base
│   ├── admin_service.ts       # API admin (actions, profils)
│   ├── audit_service.ts       # API audit
│   ├── auth_service.ts        # API authentification SAML
│   ├── catalog_service.ts     # API catalogue
│   ├── dashboard_service.ts   # API statistiques
│   ├── execution_service.ts   # API exécutions
│   ├── integrations_service.ts # API intégrations
│   ├── profiles_service.ts    # API profils
│   └── scheduled_execution_service.ts # API planification
│
├── types/                     # Types TypeScript
│   ├── api.ts                 # Types API (~936 lignes)
│   └── common.ts              # Types communs (User, NavigationTabKey)
│
├── utils/                     # Fonctions utilitaires
│   ├── actionOptions.ts       # Options actions (environnements)
│   ├── businessLanguage.ts    # Labels métier français
│   ├── cronHelper.ts          # Aide expressions cron
│   ├── debounce.ts            # Debounce de fonction (rate-limiting callbacks)
│   ├── executionRenderers.tsx # Renderers colonnes exécution
│   ├── impactRulesSchema.ts   # Schéma règles d'impact
│   ├── parametersSchema.ts    # Schéma paramètres action
│   ├── profileOptions.ts      # Options profils
│   ├── profileYamlTemplate.ts # Template YAML profil
│   └── tagStyles.ts           # Styles tags par catégorie
│
├── theme/                     # Design system Ant Design
│   ├── desjardins.ts          # Thèmes light/dark
│   ├── desjardins.test.ts     # Tests thèmes
│   └── styleTokens.ts         # Design tokens (couleurs, tailles)
│
└── styles/                    # CSS global
    └── glass.css              # Styles liquid glass (~16KB)
```

## Détails des dossiers components/

### components/admin/ (24+ fichiers)

Composants d'administration pour DBOPS et admins.

```
admin/
├── ActionForm.tsx             # Formulaire création/édition action
├── ActionWizard.tsx           # Wizard multi-étapes action
├── ActionStatusBadge.tsx      # Badge statut action
├── AdminPreview.tsx           # Preview action en édition
├── ChangeTypeConfig.tsx       # Config type changement ServiceNow
├── ImpactRulesEditor.tsx      # Éditeur règles d'impact visuel
├── IntegrationForm.tsx        # Formulaire intégration (AAP, etc.)
├── IntegrationsTable.tsx      # Table des intégrations
├── ParametersEditor.tsx       # Éditeur paramètres JSON Schema
├── ProfileForm.tsx            # Formulaire profil utilisateur
├── ProfileWizard.tsx          # Wizard création profil
├── ProfilesTable.tsx          # Table des profils
├── RemediationRulesEditor.tsx # Éditeur actions correctives
├── ScheduledExecutionsPage.tsx # Page planifications
├── StepsEditor.tsx            # Éditeur étapes action
├── WorkflowStepsEditor.tsx    # Éditeur workflow AAP
├── analytics/                 # Sous-composants analytics
│   └── (28 fichiers)          # Graphiques et rapports
└── index.ts                   # Barrel exports
```

### components/catalog/ (11 fichiers)

Composants du catalogue d'actions.

```
catalog/
├── ActionCard.tsx             # Carte action (vue grille)
├── ActionDrawerPreview.tsx    # Drawer preview détaillée
├── ActionMetrics.tsx          # Métriques action (succès, durée)
├── ActionTable.tsx            # Table actions (vue liste)
├── ActiveFiltersChips.tsx     # Chips filtres actifs
├── CategoryTabs.tsx           # Navigation par catégorie
├── ExecutionWizard.tsx        # Wizard exécution 4 étapes (~52KB)
├── HorizontalFilters.tsx      # Barre de filtres horizontale
├── TagCloud.tsx               # Nuage de tags pour filtrage
└── index.ts                   # Barrel exports
```

### components/dashboard/ (8 fichiers)

Composants dashboard et statistiques.

```
dashboard/
├── ExecutionsChart.tsx        # Graphique évolution exécutions
├── PendingApprovalsList.tsx   # Liste approbations en attente
├── RecentExecutions.tsx       # Exécutions récentes
├── StatCard.tsx               # Carte KPI statistique
├── reporting/                 # Reporting avancé (DBOPS)
│   └── (28 fichiers)          # Charts, filtres, exports
└── index.ts                   # Barrel exports
```

### components/layout/ (4 fichiers)

Layout principal et navigation.

```
layout/
├── AppLayout.tsx              # Layout avec sidebar/header
├── TopNav.tsx                 # Barre navigation supérieure
├── TopNav.css                 # Styles navigation
└── index.ts                   # Barrel exports
```

### components/shared/ (4 fichiers)

Composants réutilisables partagés.

```
shared/
├── CronExpressionHelper.tsx   # Helper expressions cron
├── ImpactIndicator.tsx        # Indicateur impact (couleur + label)
├── impactLabels.ts            # Labels impact français
└── index.ts                   # Barrel exports
```

## Conventions de nommage

| Type | Convention | Exemple |
|------|------------|---------|
| Composants | PascalCase | `ActionCard.tsx` |
| Pages | PascalCase + Page suffix | `CatalogPage.tsx` |
| Hooks | camelCase + use prefix | `useDebounce.ts` |
| Services | snake_case + _service suffix | `catalog_service.ts` |
| Types | PascalCase | `ExecutionResponse` |
| Utils | camelCase | `cronHelper.ts` |
| Tests | même nom + .test suffix | `ActionCard.test.tsx` |

## Organisation par feature

Le code est organisé par fonctionnalité métier plutôt que par type de fichier :

```
components/
├── admin/           # Tout ce qui concerne l'administration
├── catalog/         # Tout ce qui concerne le catalogue
├── dashboard/       # Tout ce qui concerne le dashboard
└── execution/       # Tout ce qui concerne les exécutions
```

Chaque dossier feature contient :
- Composants `.tsx`
- Tests `.test.tsx` co-localisés
- Barrel export `index.ts`
- Sous-composants si nécessaire

## Fichiers de configuration

| Fichier | Description |
|---------|-------------|
| `vite.config.ts` | Build, dev server, proxy API, config tests |
| `tsconfig.json` | Config TypeScript racine |
| `eslint.config.js` | Règles ESLint (React hooks, TypeScript) |
| `package.json` | Dépendances et scripts npm |
| `.env.*` | Variables d'environnement par environnement |

## Statistiques du codebase

| Métrique | Valeur |
|----------|--------|
| Composants | 40+ |
| Pages | 8 |
| Custom hooks | 13+ |
| Services API | 9 |
| Types API | ~936 lignes |
| Fichiers de test | 30+ |
| Total lignes | ~10,000+ |
