# Architecture Frontend — Structure et consommation du backend

Ce document décrit la structure complète du répertoire `src/` du frontend React, l'architecture en couches, les contextes, les hooks principaux, la liste des services API et les types TypeScript clés.

---

## Table des matières

1. [Arborescence `src/`](#arborescence-src)
2. [Architecture 3 couches](#architecture-3-couches)
3. [Contextes React](#contextes-react)
4. [Hooks principaux](#hooks-principaux)
5. [Services API](#services-api)
6. [Types TypeScript clés](#types-typescript-clés)

---

## Arborescence `src/`

```
idp-portal/frontend/src/
├── App.tsx                     — Composant racine React, configuration du routage (React Router)
├── App.test.tsx                — Tests d'intégration du composant racine
├── main.tsx                    — Point d'entrée : montage des providers (Auth, Theme, FeatureFlag)
├── test-setup.ts               — Configuration Vitest / Testing Library
│
├── __tests__/                  — Tests d'intégration root
│
├── components/                 — Composants UI réutilisables, organisés par domaine
│   ├── admin/                 — Gestion des actions catalog, profils, intégrations, règles métier
│   ├── audit/                 — Vue audit trail et filtres de recherche
│   ├── auth/                  — Composants d'authentification (écran de connexion, callback)
│   ├── calendar/              — Calendrier des exécutions planifiées (cron)
│   ├── catalog/               — Catalogue d'actions (ParametersFormStep, WorkflowStepsRenderer,
│   │                            renderFieldInput — rendu champs formulaires dynamiques)
│   ├── common/                — Composants génériques partagés (loaders, modales, badges)
│   ├── dashboard/             — Widgets et charts du dashboard (statistiques, timeseries)
│   ├── execution/             — Vue détail d'une exécution (steps, WebSocket temps réel, timeline)
│   ├── executions/            — Liste paginée et filtres des exécutions
│   ├── icons/                 — Composants icônes (wrappers SVG)
│   ├── layout/                — Layout global (sidebar, header, navigation principale)
│   ├── shared/                — Composants métier partagés entre plusieurs domaines
│   └── workflow/              — Builder visuel de workflows (React Flow)
│       ├── WorkflowBuilderCanvas.tsx     — Canvas React Flow principal
│       ├── WorkflowStepNode.tsx          — Nœud step dans le graphe
│       ├── StartNode.tsx / EndNode.tsx   — Nœuds terminaux
│       └── Fonctions utilitaires :
│           ├── workflowStepsToReactFlow() — Conversion config → graphe React Flow
│           ├── reactFlowToWorkflowSteps() — Conversion graphe → config backend
│           └── validateWorkflowGraph()   — Validation topologique du graphe
│
├── contexts/                   — Contextes React (état global partagé)
│   ├── AuthContext.tsx
│   ├── FeatureFlagContext.tsx
│   ├── ThemeContext.tsx
│   ├── DashboardContext.tsx
│   └── WizardExecutionContext.tsx
│
├── hooks/                      — Hooks custom (logique métier et appels API)
│   ├── useDynamicForm.ts       — Génération formulaire depuis JSON Schema
│   ├── useWebSocket.ts         — WebSocket temps réel /ws/executions/{id}
│   ├── useExecutionWizardState.ts   — État du wizard d'exécution
│   ├── useActionWizardState.ts      — État du wizard création action (admin)
│   ├── useInventorySchema.ts   — Chargement schéma d'inventaire pour dropdowns
│   ├── useOutputSchemas.ts     — Chargement des schémas de sortie
│   ├── useDashboardWebSocket.ts     — WebSocket dashboard (stats temps réel)
│   └── ...                    — 40+ hooks métier par domaine
│
├── pages/                      — Composants page (niveau route)
│   ├── AdminPage.tsx           — Administration (actions, profils, intégrations, règles, catégories)
│   ├── AuditPage.tsx           — Audit trail des exécutions
│   ├── CatalogPage.tsx         — Catalogue d'actions disponibles
│   ├── DashboardPage.tsx       — Dashboard et statistiques
│   ├── ExecutionsPage.tsx      — Liste des exécutions
│   ├── LoginPage.tsx           — Page d'authentification SAML
│   ├── CalendarPage.tsx        — Exécutions planifiées (vue calendrier)
│   ├── ApiKeysPage.tsx         — Gestion des clés API personnelles
│   ├── AuthCallbackPage.tsx    — Callback SAML après login
│   ├── NotFoundPage.tsx        — Page 404
│   ├── admin/                 — Sous-pages administration
│   └── executions/            — Sous-pages détail exécutions
│
├── services/                   — Couche API (un fichier par domaine métier)
│   ├── api_client.ts           — Client HTTP central (apiFetch, apiFetchRaw, etc.)
│   ├── auth_service.ts         — Authentification SAML et session
│   ├── catalog_service.ts      — Catalogue d'actions et favoris
│   ├── execution_service.ts    — Façade des services d'exécution (réexporte core + dashboard + inventory)
│   ├── execution_core.ts       — Opérations CRUD de base sur les exécutions
│   ├── execution_dashboard.ts  — Statistiques et timeseries d'exécutions
│   ├── execution_inventory.ts  — Données inventaire pour formulaires dynamiques
│   ├── admin_service.ts        — Administration (actions, tags, règles de remédiation)
│   ├── profiles_service.ts     — Profils et permissions
│   ├── integrations_service.ts — Intégrations (AAP, ServiceNow, Azure DevOps, etc.)
│   ├── audit_service.ts        — Logs d'audit et export
│   ├── dashboard_service.ts    — Statistiques et analytics dashboard
│   ├── scheduled_execution_service.ts — Exécutions planifiées (cron)
│   ├── categories_service.ts   — Catégories d'actions (CRUD)
│   ├── reference_service.ts    — Données de référence (engines, environments)
│   ├── business_rules_service.ts — Politiques de règles métier
│   ├── capabilities_service.ts — Capacités plateformes et steps workflow
│   ├── engines_service.ts      — Moteurs de BD pour admin (Oracle, SQL Server, DB2)
│   ├── output_schema_service.ts — Schémas de sortie des actions
│   ├── api_keys_service.ts     — Gestion des clés API utilisateur
│   ├── help_service.ts         — Aide contextuelle (topics avec cache sessionStorage)
│   ├── feature_flag_service.ts — Feature flags (lecture + admin)
│   └── logger.ts              — Logging frontend structuré (JSON)
│
├── styles/                     — Styles globaux CSS
├── theme/                      — Configuration thème Ant Design (tokens, palettes)
├── types/                      — Définitions TypeScript
│   ├── api.ts                 — ~936 lignes : tous les types API (ExecutionResponse, CatalogAction, etc.)
│   ├── common.ts              — Types communs (utilitaires, helpers de types)
│   ├── wizard.ts              — Types du wizard d'exécution (étapes, state)
│   └── api/                   — Sous-types API organisés par domaine
└── utils/                      — Fonctions utilitaires pures
    ├── parametersSchema.ts     — Conversion JSON Schema ↔ ParameterDefinition (éditeur admin)
    └── impactRulesSchema.ts    — Conversion JSON ↔ liste ImpactRuleDefinition (règles d'impact)
```

---

## Architecture 3 couches

Le frontend suit une architecture strictement en 3 couches. **Aucune couche ne peut appeler une couche inférieure en sautant un niveau.**

```
┌─────────────────────────────────────────────────────┐
│           Pages / Components                        │
│  (AdminPage, CatalogPage, ExecutionDetail, etc.)    │
└──────────────────┬──────────────────────────────────┘
                   │ appel de hooks ou services
                   ▼
┌─────────────────────────────────────────────────────┐
│           Custom Hooks (logique métier, state)      │
│  (useDynamicForm, useWebSocket, useExecution*, etc.)│
└──────────────────┬──────────────────────────────────┘
                   │ appel de services
                   ▼
┌─────────────────────────────────────────────────────┐
│           Services (couche API par domaine)         │
│  (catalog_service, execution_core, admin_service…)  │
└──────────────────┬──────────────────────────────────┘
                   │ via api_client
                   ▼
┌─────────────────────────────────────────────────────┐
│           api_client.ts                             │
│  apiFetch / apiFetchRaw / apiFetchBlob /            │
│  apiPostFormData                                    │
└──────────────────┬──────────────────────────────────┘
                   │ fetch() HTTP
                   ▼
             Backend Django REST API
                /api/v1/*
```

### Règles d'architecture

| Règle | Description |
|-------|-------------|
| **R1** | Les composants n'appellent **jamais** l'API directement via `fetch()` |
| **R2** | Les composants appellent des hooks ou des services |
| **R3** | Les services utilisent **toujours** `api_client.ts` |
| **R4** | `api_client.ts` gère seul : authentification, refresh 401, retries 429/503, erreurs |
| **R5** | Exception : `auth_service.ts` utilise `fetch()` brut + helpers partiels pour éviter la circularité |

### `api_client.ts` — Fonctions publiques

| Fonction | Content-Type envoyé | Retour | Usage typique |
|----------|---------------------|--------|---------------|
| `apiFetch<T>(path, init?)` | `application/json` | `body.data as T` | Appels standard (catalogue, admin, exécutions) |
| `apiFetchRaw<T>(path, init?)` | `application/json` | `body as T` (complet) | Réponses avec champs supplémentaires (`can_execute`, pagination) |
| `apiFetchBlob(path)` | aucun | `Blob` | Téléchargement fichier (export audit PDF/CSV) |
| `apiPostFormData<T>(path, formData)` | `multipart/form-data` auto | `{ data: T }` | Upload de fichier (photos, import YAML) |

### Gestion automatique des erreurs HTTP

`handleAuthenticatedFetch()` gère automatiquement :

- **401** : refresh du token via `POST /api/v1/auth/refresh` + retry automatique
- **429** : retry avec backoff exponentiel (full jitter) jusqu'à `MAX_429_RETRIES=3` ; utilise l'en-tête `Retry-After` si présent
- **503 DB_UNAVAILABLE** : retry avec `Retry-After` jusqu'à `MAX_503_RETRIES=2`

Chaque requête reçoit un `X-Correlation-ID` unique pour la traçabilité backend.

---

## Contextes React

Les contextes fournissent l'état global accessible à tous les composants sans prop drilling.

### `AuthContext.tsx`

État d'authentification global.

```typescript
const { accessToken, user, refreshAccessToken, logout } = useAuth();
```

| Valeur | Type | Description |
|--------|------|-------------|
| `accessToken` | `string \| null` | Token JWT courant (Bearer) |
| `user` | `User \| null` | Profil utilisateur connecté |
| `refreshAccessToken()` | `() => Promise<string \| null>` | Refresh explicite du token |
| `logout()` | `() => void` | Déconnexion et nettoyage de session |

`AuthContext` injecte `setAuthAccessors(getToken, refreshFn)` dans `api_client.ts` au montage, permettant au client HTTP d'accéder au token sans dépendance circulaire.

---

### `FeatureFlagContext.tsx`

Accès aux feature flags de l'application.

```typescript
const { isEnabled } = useFeatureFlag();
const showNewDashboard = isEnabled('new_dashboard');
```

La source des flags est configurable via la variable d'environnement `FEATURE_FLAGS_SOURCE` :
- `api` (défaut production) : `GET /api/v1/feature-flags/status/`
- `env` : variables d'environnement Vite au build

---

### `ThemeContext.tsx`

Basculement thème Ant Design light/dark.

```typescript
const { theme, toggleTheme } = useTheme();
// theme: 'light' | 'dark'
```

---

### `DashboardContext.tsx`

Filtres globaux partagés entre les widgets du dashboard (plage de dates, scope, filtres moteur).

```typescript
const { filters, setFilters } = useDashboardContext();
```

---

### `WizardExecutionContext.tsx`

État partagé du wizard d'exécution multi-étapes (contexte partagé entre les steps du wizard).

```typescript
const { wizardState, setWizardState } = useWizardExecutionContext();
```

---

## Hooks principaux

### `useWebSocket(executionId)` — WebSocket temps réel

**Fichier :** `src/hooks/useWebSocket.ts`

Connexion WebSocket à `/ws/executions/{id}` pour suivre l'avancement d'une exécution en temps réel.

```typescript
const { steps, execution, loading, error, isAuthenticated } = useWebSocket(executionId);
// executionId = null → pas de connexion, nettoyage automatique
```

**Retour :**

| Champ | Type | Description |
|-------|------|-------------|
| `steps` | `ExecutionStepResponse[]` | Étapes de l'exécution, triées par `step_order` |
| `execution` | `ExecutionResponse \| null` | État courant de l'exécution |
| `loading` | `boolean` | Chargement initial en cours |
| `error` | `string \| null` | Message d'erreur (auth, réseau) |
| `lastMessage` | `{ type: string; execution_id?: number; data?: unknown } \| null` | Dernier message WebSocket brut reçu (utile pour les composants qui réagissent à des événements custom) |
| `isAuthenticated` | `boolean` | Authentification WebSocket confirmée |

**Séquence de connexion :**

```
1. connect() → new WebSocket("/ws/executions/{id}")
2. onopen   → send { type: "auth", token: "<JWT>" }
3. server   → { type: "auth_success", user_id: "..." }
4. client   → re-sync : GET /executions/{id} + GET /executions/{id}/steps
5. server   → messages métier (step_update, status_update, execution_complete, …)
```

**Codes de fermeture :**

| Code | Signification | Reconnexion |
|------|---------------|-------------|
| `4001` | Échec authentification | ❌ Non |
| `4003` | Accès non autorisé | ❌ Non |
| Autre | Fermeture normale ou réseau | ✅ Oui (après 2 secondes) |

**Événements reçus :**

| Type | Payload clé | Action |
|------|-------------|--------|
| `auth_success` | `{ user_id }` | `setIsAuthenticated(true)`, re-sync |
| `step_update` | `{ id, step_order, step_name, status, step_type, started_at, completed_at, config_step_id }` | Upsert dans `steps[]` par `step_order` |
| `status_update` | `{ data: { status } }` | Mise à jour du statut de l'exécution |
| `execution_complete` | — | `status = "COMPLETED"`, fermeture WS |
| `execution_failed` | `{ error_message }` | `status = "FAILED"`, fermeture WS |

> **`config_step_id`** : Identifiant du step dans la configuration workflow. Permet au composant `WorkflowExecutionGraph` de colorier le bon nœud dans React Flow — fiable même pour les workflows avec branches (contrairement à l'index du tableau).

---

### `useDynamicForm({ schema })` — Formulaire dynamique

**Fichier :** `src/hooks/useDynamicForm.ts`

Génère la liste des champs de formulaire à partir d'un JSON Schema `parameters_schema`.

```typescript
const { parameterFields } = useDynamicForm({ schema: action.parameters_schema });
// parameterFields: ParameterField[] — un élément par propriété du schéma
```

Voir le [Guide JSON Schemas](./json-schemas-guide.md) pour la documentation complète du flux.

---

### `useExecutionWizardState` — State wizard d'exécution

**Fichier :** `src/hooks/useExecutionWizardState.ts`

Gère l'état multi-étapes du wizard d'exécution (sélection action, environnement, paramètres, confirmation).

---

### `useActionWizardState` — State wizard création action

**Fichier :** `src/hooks/useActionWizardState.ts`

Gère l'état du wizard de création/édition d'une action catalog (admin).

---

### `useInventorySchema` — Schéma d'inventaire

**Fichier :** `src/hooks/useInventorySchema.ts`

Charge le schéma d'inventaire (`GET /api/v1/inventory/schema`) pour alimenter les dropdowns de sélection d'inventaire dans les formulaires.

---

### `useOutputSchemas` — Schémas de sortie

**Fichier :** `src/hooks/useOutputSchemas.ts`

Charge les `OutputSchema` disponibles via `output_schema_service.ts`, utilisés dans le builder workflow pour mapper les variables de sortie.

---

## Services API

Chaque service est un module TypeScript dans `src/services/`. Tous utilisent `api_client.ts`.

### Vue d'ensemble

| Service | Fichier | Endpoints couverts |
|---------|---------|-------------------|
| **api_client** | `api_client.ts` | Client central — aucun endpoint direct |
| **auth_service** | `auth_service.ts` | `/auth/saml/login`, `/auth/refresh`, `/auth/me`, `/auth/logout` |
| **catalog_service** | `catalog_service.ts` | `/catalog/actions`, `/catalog/tags`, `/users/me/favorites` |
| **execution_service** | `execution_service.ts` | Façade — réexporte `execution_core` + `execution_dashboard` + `execution_inventory` |
| **execution_core** | `execution_core.ts` | `/executions` (CRUD, approve, reject, cancel, remediation) |
| **execution_dashboard** | `execution_dashboard.ts` | `/executions/stats`, `/executions/timeseries`, `/executions/tags` |
| **execution_inventory** | `execution_inventory.ts` | `/inventory/{type}`, `/inventory/targets`, `/inventory/schema` |
| **admin_service** | `admin_service.ts` | `/admin/actions`, `/admin/tags`, `/admin/actions/{id}/remediation-rules` |
| **profiles_service** | `profiles_service.ts` | `/admin/profiles` (CRUD, export/import YAML) |
| **integrations_service** | `integrations_service.ts` | `/admin/integrations` (CRUD) |
| **audit_service** | `audit_service.ts` | `/audit/executions`, `/audit/reports/export` |
| **dashboard_service** | `dashboard_service.ts` | `/dashboard/stats`, `/dashboard/timeseries`, `/dashboard/comparison` |
| **scheduled_execution_service** | `scheduled_execution_service.ts` | `/scheduled-executions` (CRUD, toggle récurrence) |
| **categories_service** | `categories_service.ts` | `/reference/categories`, `/admin/categories` (CRUD) |
| **reference_service** | `reference_service.ts` | `/reference/engines`, `/inventory/environments` (avec cache global) |
| **business_rules_service** | `business_rules_service.ts` | `/admin/business-rule-policies` (CRUD) |
| **capabilities_service** | `capabilities_service.ts` | `/capabilities/integrations`, `/capabilities/workflow-steps` |
| **engines_service** | `engines_service.ts` | `/reference/engines`, `/admin/engines/{id}` (admin) |
| **output_schema_service** | `output_schema_service.ts` | `/output-schemas`, `/output-schemas/workflows/{id}/available-variables` |
| **api_keys_service** | `api_keys_service.ts` | `/auth/api-keys` (list, create, revoke) |
| **help_service** | `help_service.ts` | `/help/{topicId}` (avec cache sessionStorage 10 min) |
| **feature_flag_service** | `feature_flag_service.ts` | `/feature-flags/status`, `/feature-flags` (admin), `/feature-flags/{key}` |
| **logger** | `logger.ts` | — Logging structuré frontend (JSON) |

### Détail des services principaux

#### `reference_service.ts` — Données de référence

Charge les engines actifs et les environnements depuis les tables de référence backend. Implémente un **cache global en mémoire** pour éviter les appels API dupliqués sur `fetchEnvironments()`.

```typescript
fetchEngines(): Promise<RefEngine[]>
// GET /api/v1/reference/engines?active_only=true

fetchEnvironments(): Promise<string[]>
// GET /api/v1/inventory/environments
// → cache global (Promise partagée pour éviter les appels parallèles)
// → Fallback silencieux sur ['dev', 'staging', 'prod'] si l'endpoint est indisponible
//   ⚠️ Les valeurs du fallback sont en lowercase (contrairement aux envs prod en UPPERCASE)
```

#### `categories_service.ts` — Catégories d'actions

CRUD sur les catégories d'actions (table `REF_CATEGORIES`).

```typescript
getCategories(activeOnly?: boolean): Promise<RefCategory[]>
// GET /api/v1/reference/categories?active_only=true

createCategory(data): Promise<RefCategory>
// POST /api/v1/admin/categories/

updateCategory(id, data): Promise<RefCategory>
// PATCH /api/v1/admin/categories/{id}/

deleteCategory(id): Promise<void>
// DELETE /api/v1/admin/categories/{id}/delete/
```

#### `business_rules_service.ts` — Règles métier

Gestion des politiques de règles métier (validation avant exécution).

```typescript
getBusinessRulePolicies(filters?): Promise<BusinessRulePolicyListResponse>
// GET /api/v1/admin/business-rule-policies/

getBusinessRulePolicy(id): Promise<BusinessRulePolicyDetail>
// GET /api/v1/admin/business-rule-policies/{id}/

createBusinessRulePolicy(payload): Promise<BusinessRulePolicyDetail>
// POST /api/v1/admin/business-rule-policies/

updateBusinessRulePolicy(id, payload): Promise<BusinessRulePolicyDetail>
// PATCH /api/v1/admin/business-rule-policies/{id}/

deleteBusinessRulePolicy(id): Promise<void>
// DELETE /api/v1/admin/business-rule-policies/{id}/
```

#### `capabilities_service.ts` — Capacités plateformes

Expose les capacités backend pour le builder workflow (plateformes d'intégration + types de steps).

```typescript
getIntegrationsCapabilities(): Promise<CapabilitiesIntegrationsData>
// GET /api/v1/capabilities/integrations/
// → { platforms: PlatformCapability[], services: ServiceCapability[] }

getWorkflowStepsCapabilities(): Promise<CapabilitiesWorkflowStepsData>
// GET /api/v1/capabilities/workflow-steps/
// → { step_types: WorkflowStepCapability[] }
```

#### `engines_service.ts` — Moteurs de BD (admin)

Gestion admin des moteurs de base de données.

```typescript
fetchEnginesForAdmin(activeOnly?: boolean): Promise<RefEngine[]>
// GET /api/v1/reference/engines?active_only=false

updateEngine(id, payload): Promise<RefEngine>
// PATCH /api/v1/admin/engines/{id}/
```

#### `output_schema_service.ts` — Schémas de sortie

Gestion des schémas de sortie des actions pour le builder workflow.

```typescript
fetchAvailableVariables(workflowId): Promise<AvailableVariablesStep[]>
// GET /api/v1/output-schemas/workflows/{id}/available-variables/

fetchOutputSchemasList(schemaType?): Promise<OutputSchemaListItem[]>
// GET /api/v1/output-schemas/?schema_type=...
```

#### `api_keys_service.ts` — Clés API

Gestion des clés API personnelles de l'utilisateur connecté.

```typescript
listApiKeys(): Promise<ApiKeyListItem[]>
// GET /api/v1/auth/api-keys/

createApiKey(payload): Promise<ApiKeyCreateResponse>
// POST /api/v1/auth/api-keys/
// → retourne raw_key (affiché une seule fois)

revokeApiKey(id): Promise<void>
// DELETE /api/v1/auth/api-keys/{id}/
```

Scopes disponibles : `'executions'` | `'catalog'` | `'full'`

#### `help_service.ts` — Aide contextuelle

Charge le contenu d'aide par `topicId`. Cache dans `sessionStorage` pendant 10 minutes.

```typescript
getHelpContent(topicId: string): Promise<HelpContent>
// GET /api/v1/help/{topicId}/
// → { topic_id, short, markdown }
// Cache sessionStorage 10 min — fallback silencieux si endpoint indisponible
```

#### `feature_flag_service.ts` — Feature flags

```typescript
fetchFeatureFlagsStatus(): Promise<FeatureFlagsStatus>
// GET /api/v1/feature-flags/status  ← utilisateur courant
// → Record<string, boolean>

fetchFeatureFlags(): Promise<FeatureFlagListResponse>
// GET /api/v1/feature-flags  ← admin seulement

updateFeatureFlag(flagKey, data): Promise<FeatureFlagDetail>
// PATCH /api/v1/feature-flags/{flagKey}
```

#### Services d'exécution refactorisés

`execution_service.ts` est une **façade** qui réexporte les 3 sous-modules :

| Sous-module | Fichier | Rôle |
|-------------|---------|------|
| **Core** | `execution_core.ts` | CRUD exécutions, approve/reject/cancel, remediation |
| **Dashboard** | `execution_dashboard.ts` | Stats et timeseries (filtres scope + date) |
| **Inventory** | `execution_inventory.ts` | Données inventaire pour formulaires (avec cache mémoire 5 min + sessionStorage) |

```typescript
// execution_core.ts — fonctions principales
submitExecution(request): Promise<ExecutionCreateResponse>
// POST /api/v1/executions

listExecutions(limit, offset, scope, filters?): Promise<ListExecutionsResponse>
// GET /api/v1/executions?limit=...&offset=...&scope=...

approveExecution(executionId, comment?): Promise<ApproveExecutionResponse>
// POST /api/v1/executions/{id}/approve

rejectExecution(executionId, comment?): Promise<RejectExecutionResponse>
// POST /api/v1/executions/{id}/reject

cancelExecution(executionId): Promise<ExecutionResponse>
// PATCH /api/v1/executions/{id}/cancel

// execution_dashboard.ts
fetchExecutionStats(scope, filters?): Promise<DashboardStats>
// GET /api/v1/executions/stats?scope=...

fetchExecutionTimeSeries(scope, filters?): Promise<DashboardTimeSeriesPoint[]>
// GET /api/v1/executions/timeseries?scope=...

// execution_inventory.ts
fetchInventoryItems(type, environment?, options?): Promise<InventoryItem[]>
// GET /api/v1/inventory/{type}?environment=...
// Cache mémoire 5 min + fallback sessionStorage si 503

fetchInventorySchema(): Promise<InventorySchema>
// GET /api/v1/inventory/schema
```

---

## Types TypeScript clés

**Fichier principal :** `src/types/api.ts` (~936 lignes)

### Types de base

```typescript
// Réponse standard (body.data unwrapped par apiFetch)
interface ApiResponse<T> {
  data: T;
}

// Réponse paginée (body complet via apiFetchRaw)
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

// Erreur HTTP structurée
class ApiError extends Error {
  status: number;
  responseBody?: {
    error?: { code?: string; message?: string; details?: Record<string, unknown> }
  };
}
```

### Types de domaine

```typescript
type ActionEngine    = 'Oracle' | 'SQL Server' | 'DB2';
type ActionPlatform  = 'AAP' | 'GitHub Actions' | 'Azure DevOps' | 'Terraform';
type ActionStatus    = 'draft' | 'published' | 'disabled';
type ImpactLevel     = 'low' | 'medium' | 'high' | 'critical';
type ExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
                     | 'CANCELLED' | 'APPROVAL_REQUIRED' | 'APPROVED' | 'REJECTED';
type ConnectorType   = 'aap' | 'servicenow' | 'azuredevops' | 'jira'
                     | 'github_actions' | 'terraform' | 'none';
type InventorySourceType = 'databases' | 'servers' | 'instances';
```

### Types d'exécution

```typescript
interface ExecutionCreateRequest {
  action_id: number;
  environment: string;
  parameters: Record<string, unknown>;
  parent_execution_id?: number;  // Pour remédiation
}

interface ExecutionResponse {
  id: number;
  action_id: number;
  action_name: string;
  environment: string;
  parameters: Record<string, unknown>;
  status: ExecutionStatus;
  started_at: string | null;
  completed_at: string | null;
  created_by: number;
  correlation_id: string;
  parent_execution_id?: number | null;
  servicenow_change_id?: string | null;
}
```

### Types JSON Schema

```typescript
// Définition d'un paramètre dans l'éditeur visuel admin
interface ParameterDefinition {
  name: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'date-time' | 'select';
  required: boolean;
  default?: string;
  description?: string;
  enum?: string[];
  source?: 'inventory' | 'manual';
  inventory_type?: 'databases' | 'servers' | 'instances';
  inventory_value_column?: string;
}

// Champ de formulaire d'exécution généré par useDynamicForm
interface ParameterField {
  name: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'date-time' | 'select' | 'array';
  label: string;
  description?: string;
  required: boolean;
  enum?: string[];
  pattern?: string;
  minimum?: number;
  maximum?: number;
  default?: unknown;
  inventorySource?: InventorySourceType;
  inventoryValueColumn?: string;
}
```

### `src/types/wizard.ts` — Types du wizard d'exécution

Contient les types pour l'état multi-étapes du wizard d'exécution :
- État courant du wizard (étape active, données saisies)
- Configuration des étapes (sélection action → choix environnement → saisie paramètres → confirmation)
- Résultat de soumission

---

## Voir aussi

- [Guide JSON Schemas](./json-schemas-guide.md) — Flux `parameters_schema` → formulaire dynamique
- [Intégration API](./api-integration.md) — Documentation détaillée de `api_client.ts` et services
- [Workflow Builder](./workflow-builder.md) — Builder visuel React Flow
- [Contrats API Frontend](../api/contracts-frontend.md) — Contrats endpoints consommés
