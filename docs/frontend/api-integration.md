# Intégration API Backend

Ce document décrit l'intégration entre le frontend React et l'API backend Django.

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Component  │───▶│   Service   │───▶│ api_client  │───▶ Backend API
└─────────────┘    └─────────────┘    └─────────────┘     /api/v1/*
```

**Principe :**
1. Les composants n'appellent jamais l'API directement
2. Chaque domaine a son service dédié
3. `api_client` gère l'authentification et les erreurs

---

## api_client.ts

**Fichier :** `src/services/api_client.ts`

Client HTTP de base avec gestion automatique de l'authentification.

### Méthodes disponibles

```typescript
// Retourne body.data (unwrapped)
apiFetch<T>(path: string, init?: RequestInit): Promise<T>

// Retourne le body complet (pour réponses avec champs supplémentaires)
apiFetchRaw<T>(path: string, init?: RequestInit): Promise<T>

// Téléchargement de fichier (retourne Blob)
apiFetchBlob(path: string): Promise<Blob>

// Upload FormData (multipart/form-data)
apiPostFormData<T>(path: string, formData: FormData): Promise<{ data: T }>
```

### Utilisation

```typescript
import { apiFetch, apiFetchRaw, apiFetchBlob } from './api_client';

// GET simple
const actions = await apiFetch<CatalogAction[]>('/catalog/actions');

// GET avec query params
const filtered = await apiFetch<CatalogAction[]>('/catalog/actions?tags=oracle,patching');

// POST avec body JSON
const result = await apiFetch<ExecutionResponse>('/executions', {
  method: 'POST',
  body: JSON.stringify({ action_id: 123, environment: 'DEV', parameters: {} }),
});

// Réponse complète (avec can_execute, allowed_environments)
const detail = await apiFetchRaw<{
  data: CatalogActionDetail;
  can_execute: boolean;
  allowed_environments: string[];
}>('/catalog/actions/123');

// Téléchargement fichier
const blob = await apiFetchBlob('/audit/reports/export?format=pdf');
const url = URL.createObjectURL(blob);
```

### Gestion de l'authentification

```typescript
// Injection token Bearer automatique
headers['Authorization'] = `Bearer ${token}`;

// Intercepteur 401 : refresh automatique + retry
if (response.status === 401 && token) {
  const newToken = await _onRefreshNeeded();
  if (newToken) {
    headers['Authorization'] = `Bearer ${newToken}`;
    response = await fetch(url, { ...init, headers });
  }
}
```

### Gestion des erreurs

```typescript
// Erreur JSON structurée
if (response.headers.get('content-type')?.includes('application/json')) {
  const body = await response.json();
  errorMessage = body.error?.message ?? `Erreur HTTP ${response.status}`;
}

// Erreur texte
else {
  errorMessage = await response.text() || `Erreur HTTP ${response.status}`;
}

throw new Error(errorMessage);
```

---

## Services disponibles

### auth_service.ts

**Fichier :** `src/services/auth_service.ts`

Authentification SAML et gestion de session.

```typescript
// URL de login SAML
loginUrl(): string
// → '/api/v1/auth/saml/login'

// Rafraîchir le token via cookie httpOnly
refreshAccessToken(): Promise<string | null>
// POST /api/v1/auth/refresh

// Récupérer le profil utilisateur
fetchCurrentUser(token: string): Promise<User | null>
// GET /api/v1/auth/me

// Déconnexion
logoutApi(): Promise<void>
// POST /api/v1/auth/logout
```

---

### catalog_service.ts

**Fichier :** `src/services/catalog_service.ts`

Catalogue d'actions et favoris.

```typescript
// Liste des actions (avec filtres optionnels)
fetchCatalogActions(filters?: CatalogFilters): Promise<CatalogAction[]>
// GET /api/v1/catalog/actions?tags=...&q=...&engine=...

// Tags avec compteur
fetchCatalogTags(category?: string): Promise<CatalogTagWithCount[]>
// GET /api/v1/catalog/tags

// Détail d'une action
fetchCatalogActionById(id: number): Promise<CatalogActionDetailResponse>
// GET /api/v1/catalog/actions/{id}
// → { data, can_execute, allowed_environments }

// Statistiques d'une action (scorecard)
fetchActionStats(actionId: number): Promise<ActionStats | null>
// GET /api/v1/catalog/actions/{id}/stats

// Favoris
fetchFavorites(): Promise<FavoriteEntry[]>
// GET /api/v1/users/me/favorites

addFavorite(actionId: number): Promise<void>
// POST /api/v1/users/me/favorites/{id}

removeFavorite(actionId: number): Promise<void>
// DELETE /api/v1/users/me/favorites/{id}
```

**Filtres supportés :**

```typescript
interface CatalogFilters {
  tags?: string[];      // Filtrer par tags
  q?: string;           // Recherche texte (nom, description, tags)
  engine?: string;      // Oracle, SQL Server, DB2
  environment?: string; // DEV, QA, PROD
  impact?: string;      // low, medium, high, critical
  category?: string;    // Catégorie (provisioning, patching, etc.)
}
```

---

### execution_service.ts

**Fichier :** `src/services/execution_service.ts`

Fichier barrel (façade) — réexporte toutes les fonctions des 3 sous-modules spécialisés. Toutes les fonctions restent accessibles depuis ce module par backward compatibility.

```typescript
// Réexporte depuis execution_core.ts :
submitExecution, getExecution, getExecutionSteps, getStepLogs,
listExecutions, listPendingApprovals, getPendingApprovalsCount,
approveExecution, rejectExecution, cancelExecution,
fetchRemediationSuggestions, fetchRemediationContext, buildFilterParams

// Réexporte depuis execution_dashboard.ts :
fetchExecutionStats, fetchExecutionTimeSeries, fetchExecutionTags

// Réexporte depuis execution_inventory.ts :
fetchInventoryItems, fetchInventorySchema, fetchInventoryTargets, fetchTargetsPaginated
```

Voir les sections dédiées ci-dessous pour le détail des signatures. Fonctions clés :

```typescript
// Liste des exécutions (paginée par limit/offset)
listExecutions(limit?: number, offset?: number, scope?: string, filters?: ExecutionFilters): Promise<ListExecutionsResponse>
// GET /api/v1/executions?limit=...&offset=...&scope=...

// Suggestions de remédiation
fetchRemediationSuggestions(executionId: number): Promise<RemediationSuggestion[]>
// GET /api/v1/executions/{id}/remediation-suggestions

// Contexte de remédiation
fetchRemediationContext(executionId: number): Promise<RemediationContext>
// GET /api/v1/executions/{id}/remediation-context
```

---

### admin_service.ts

**Fichier :** `src/services/admin_service.ts`

Administration des actions, profils, intégrations.

```typescript
// === Actions ===
listActions(filters?: AdminActionFilters): Promise<ActionListItem[]>
// GET /api/v1/admin/actions

createAction(data: ActionCreate): Promise<ActionResponse>
// POST /api/v1/admin/actions

getActionById(id: number): Promise<ActionDetail>
// GET /api/v1/admin/actions/{id}

updateAction(id: number, data: Partial<ActionCreate>): Promise<ActionResponse>
// PATCH /api/v1/admin/actions/{id}

updateExecutionSteps(actionId: number, steps: ExecutionStepsUpdate): Promise<void>
// PUT /api/v1/admin/actions/{id}/steps

publishAction(actionId: number): Promise<void>
// POST /api/v1/admin/actions/{id}/status (transition: 'publish')

disableAction(actionId: number): Promise<void>
// POST /api/v1/admin/actions/{id}/status (transition: 'disable')

deleteAction(actionId: number): Promise<void>
// DELETE /api/v1/admin/actions/{id}

// === Tags ===
listTags(): Promise<Tag[]>
// GET /api/v1/admin/tags

createTag(name: string): Promise<Tag>
// POST /api/v1/admin/tags

// === Règles de remédiation ===
fetchRemediationRules(actionId: number): Promise<RemediationRule[]>
// GET /api/v1/admin/actions/{id}/remediation-rules

updateRemediationRules(actionId: number, rules: RemediationRule[]): Promise<void>
// PUT /api/v1/admin/actions/{id}/remediation-rules
```

---

### profiles_service.ts

**Fichier :** `src/services/profiles_service.ts`

Gestion des profils et permissions.

```typescript
listProfiles(): Promise<Profile[]>
// GET /api/v1/admin/profiles

getProfileById(id: number): Promise<ProfileDetail>
// GET /api/v1/admin/profiles/{id}

createProfile(data: ProfileCreate): Promise<Profile>
// POST /api/v1/admin/profiles

updateProfile(id: number, data: Partial<ProfileCreate>): Promise<Profile>
// PATCH /api/v1/admin/profiles/{id}

deleteProfile(id: number): Promise<void>
// DELETE /api/v1/admin/profiles/{id}

importProfilesYaml(yamlContent: string): Promise<ImportResult>
// POST /api/v1/admin/profiles/import

exportProfilesYaml(): Promise<string>
// GET /api/v1/admin/profiles/export
```

---

### integrations_service.ts

**Fichier :** `src/services/integrations_service.ts`

Gestion des intégrations (AAP, ServiceNow, etc.).

```typescript
listIntegrations(): Promise<Integration[]>
// GET /api/v1/admin/integrations

getIntegrationById(id: number): Promise<IntegrationDetail>
// GET /api/v1/admin/integrations/{id}

createIntegration(data: IntegrationCreate): Promise<Integration>
// POST /api/v1/admin/integrations

updateIntegration(id: number, data: Partial<IntegrationCreate>): Promise<Integration>
// PATCH /api/v1/admin/integrations/{id}

deleteIntegration(id: number): Promise<void>
// DELETE /api/v1/admin/integrations/{id}
```

---

### audit_service.ts

**Fichier :** `src/services/audit_service.ts`

Consultation et export des logs d'audit.

```typescript
listAuditExecutions(filters?: AuditFilters): Promise<AuditListResponse>
// GET /api/v1/audit/executions

exportAuditReport(filters?: AuditFilters, format?: 'csv' | 'pdf'): Promise<Blob>
// GET /api/v1/audit/reports/export?format=...
```

---

### dashboard_service.ts

**Fichier :** `src/services/dashboard_service.ts`

Statistiques et analytics.

```typescript
getDashboardStats(): Promise<DashboardStats>
// GET /api/v1/dashboard/stats

getDashboardTimeSeriesData(filters?: TimeSeriesFilters): Promise<TimeSeriesData[]>
// GET /api/v1/dashboard/timeseries

getComparisonData(metric: string, period1: DateRange, period2: DateRange): Promise<ComparisonData>
// GET /api/v1/dashboard/comparison
```

---

### scheduled_execution_service.ts

**Fichier :** `src/services/scheduled_execution_service.ts`

Exécutions planifiées.

```typescript
createScheduledExecution(data: ScheduledExecutionCreate): Promise<ScheduledExecution>
// POST /api/v1/scheduled-executions

listScheduledExecutions(filters?: ScheduledFilters): Promise<ScheduledExecution[]>
// GET /api/v1/scheduled-executions

cancelScheduledExecution(id: number): Promise<void>
// DELETE /api/v1/scheduled-executions/{id}

toggleRecurringPattern(id: number, isActive: boolean): Promise<void>
// PATCH /api/v1/scheduled-executions/{id}/recurring
```

---

### reference_service.ts

**Fichier :** `src/services/reference_service.ts`

Données de référence (engines actifs, environnements disponibles).

```typescript
// Moteurs actifs depuis REF_ENGINES
fetchEngines(): Promise<RefEngine[]>
// GET /api/v1/reference/engines?active_only=true

// Environnements depuis l'inventaire (avec cache global en mémoire)
fetchEnvironments(): Promise<string[]>
// GET /api/v1/inventory/environments
// Cache global : évite les appels API dupliqués — partagé avec fetchInventoryItems('environments')
```

**Note cache :** `fetchEnvironments()` implémente un cache global avec Promise partagée pour éviter les appels simultanés redondants. Fallback sur `['dev', 'staging', 'prod']` si l'endpoint est indisponible.

---

### categories_service.ts

**Fichier :** `src/services/categories_service.ts`

CRUD sur les catégories d'actions (table `REF_CATEGORIES`).

```typescript
// Liste des catégories actives
getCategories(activeOnly?: boolean): Promise<RefCategory[]>
// GET /api/v1/reference/categories?active_only=true

// Créer une catégorie (admin DBOPS uniquement)
createCategory(data: { code, label, display_order, is_active }): Promise<RefCategory>
// POST /api/v1/admin/categories/

// Mettre à jour une catégorie
updateCategory(id: number, data: Partial<...>): Promise<RefCategory>
// PATCH /api/v1/admin/categories/{id}/

// Soft-delete (set is_active=0)
deleteCategory(id: number): Promise<void>
// DELETE /api/v1/admin/categories/{id}/delete/
```

---

### business_rules_service.ts

**Fichier :** `src/services/business_rules_service.ts`

Gestion des politiques de règles métier (validation avant exécution de steps).

```typescript
// Liste avec filtres (step_type, platform, is_active, pagination)
getBusinessRulePolicies(filters?: BusinessRulePolicyFilters): Promise<BusinessRulePolicyListResponse>
// GET /api/v1/admin/business-rule-policies/

// Détail d'une politique
getBusinessRulePolicy(id: number): Promise<BusinessRulePolicyDetail>
// GET /api/v1/admin/business-rule-policies/{id}/

// Créer une politique
createBusinessRulePolicy(payload: BusinessRulePolicyPayload): Promise<BusinessRulePolicyDetail>
// POST /api/v1/admin/business-rule-policies/

// Mettre à jour
updateBusinessRulePolicy(id: number, payload: Partial<...>): Promise<BusinessRulePolicyDetail>
// PATCH /api/v1/admin/business-rule-policies/{id}/

// Supprimer
deleteBusinessRulePolicy(id: number): Promise<void>
// DELETE /api/v1/admin/business-rule-policies/{id}/
```

---

### capabilities_service.ts

**Fichier :** `src/services/capabilities_service.ts`

Capacités backend pour le builder workflow (plateformes d'intégration et types de steps disponibles).

```typescript
// Plateformes + services disponibles
getIntegrationsCapabilities(): Promise<CapabilitiesIntegrationsData>
// GET /api/v1/capabilities/integrations/
// → { platforms: PlatformCapability[], services: ServiceCapability[] }

// Types de steps workflow avec schémas de configuration
getWorkflowStepsCapabilities(): Promise<CapabilitiesWorkflowStepsData>
// GET /api/v1/capabilities/workflow-steps/
// → { step_types: WorkflowStepCapability[] }
```

**Types clés :**

```typescript
interface PlatformCapability {
  code: string;
  display_name: string;
  connector_type: string;
  action_config_schema: Record<string, unknown>; // schéma JSON de configuration
  supports_health_check: boolean;
}

interface ServiceCapability {
  code: string;
  display_name: string;
  credential_mode: 'integration' | 'credential_free';
  operations: ServiceOperation[]; // avec input_schema, output_schema, ui_hints
}
```

---

### engines_service.ts

**Fichier :** `src/services/engines_service.ts`

Gestion admin des moteurs de base de données (Oracle, SQL Server, DB2).

```typescript
// Tous les engines (y compris inactifs) pour l'admin
fetchEnginesForAdmin(activeOnly?: boolean): Promise<RefEngine[]>
// GET /api/v1/reference/engines?active_only=false

// Mettre à jour un engine (icône, label, ordre, actif)
updateEngine(id: number, payload: Partial<RefEngine>): Promise<RefEngine>
// PATCH /api/v1/admin/engines/{id}/
```

**Différence avec `reference_service.ts` :** `engines_service.ts` cible les endpoints admin et retourne tous les engines (incluant inactifs) par défaut.

---

### output_schema_service.ts

**Fichier :** `src/services/output_schema_service.ts`

Schémas de sortie des actions — utilisés dans le builder workflow pour mapper les variables.

```typescript
// Variables disponibles pour un workflow donné (par step)
fetchAvailableVariables(workflowId: number): Promise<AvailableVariablesStep[]>
// GET /api/v1/output-schemas/workflows/{id}/available-variables/

// Liste des OutputSchema filtrés par type
fetchOutputSchemasList(schemaType?: string): Promise<OutputSchemaListItem[]>
// GET /api/v1/output-schemas/?schema_type=...
```

```typescript
interface AvailableVariablesStep {
  step_id: string;
  step_name: string;
  step_type: string;
  variables: OutputField[]; // { name, path, type, description }
}
```

---

### api_keys_service.ts

**Fichier :** `src/services/api_keys_service.ts`

Gestion des clés API personnelles de l'utilisateur connecté.

```typescript
// Lister ses clés
listApiKeys(): Promise<ApiKeyListItem[]>
// GET /api/v1/auth/api-keys/

// Créer une clé (retourne raw_key, affiché une seule fois)
createApiKey(payload: ApiKeyCreateRequest): Promise<ApiKeyCreateResponse>
// POST /api/v1/auth/api-keys/

// Révoquer une clé
revokeApiKey(id: number): Promise<void>
// DELETE /api/v1/auth/api-keys/{id}/
```

**Scopes disponibles :** `'executions'` | `'catalog'` | `'full'`

---

### help_service.ts

**Fichier :** `src/services/help_service.ts`

Aide contextuelle par topic. Cache `sessionStorage` de 10 minutes.

```typescript
getHelpContent(topicId: string): Promise<HelpContent>
// GET /api/v1/help/{topicId}/
// → { topic_id: string, short: string, markdown: string }
// Fallback silencieux si endpoint indisponible (retourne strings vides)
```

**Cache :** Chaque topic est mis en cache dans `sessionStorage` pendant 10 min. Évite les appels répétés lors de la navigation.

---

### feature_flag_service.ts

**Fichier :** `src/services/feature_flag_service.ts`

Accès aux feature flags (lecture utilisateur + administration).

```typescript
// Status des flags pour l'utilisateur courant
fetchFeatureFlagsStatus(): Promise<FeatureFlagsStatus>
// GET /api/v1/feature-flags/status
// → Record<string, boolean>

// Liste complète (admin uniquement)
fetchFeatureFlags(): Promise<FeatureFlagListResponse>
// GET /api/v1/feature-flags
// → { data: FeatureFlagDetail[], source: string }

// Mettre à jour un flag (admin)
updateFeatureFlag(flagKey: string, data: { enabled?, rollout_percent? }): Promise<FeatureFlagDetail>
// PATCH /api/v1/feature-flags/{flagKey}
```

---

### Services d'exécution refactorisés

`execution_service.ts` est une **façade** qui réexporte les fonctions des 3 sous-modules spécialisés.

#### execution_core.ts

**Fichier :** `src/services/execution_core.ts`

Opérations CRUD de base, approbation, annulation et remédiation.

```typescript
submitExecution(request: ExecutionCreateRequest): Promise<ExecutionCreateResponse>
// POST /api/v1/executions

getExecution(executionId: number): Promise<ExecutionResponse>
// GET /api/v1/executions/{id}

getExecutionSteps(executionId: number): Promise<ExecutionStepResponse[]>
// GET /api/v1/executions/{id}/steps

getStepLogs(executionId: number, stepId: number): Promise<StepLogsResponse>
// GET /api/v1/executions/{id}/steps/{stepId}/logs

listExecutions(limit?, offset?, scope?, filters?): Promise<ListExecutionsResponse>
// GET /api/v1/executions?limit=...&offset=...&scope=...

listPendingApprovals(limit?, offset?): Promise<PendingApprovalsResponse>
// GET /api/v1/executions/pending-approvals

approveExecution(executionId: number, comment?: string): Promise<ApproveExecutionResponse>
// POST /api/v1/executions/{id}/approve

rejectExecution(executionId: number, comment?: string): Promise<RejectExecutionResponse>
// POST /api/v1/executions/{id}/reject

cancelExecution(executionId: number): Promise<ExecutionResponse>
// PATCH /api/v1/executions/{id}/cancel

fetchRemediationSuggestions(executionId: number): Promise<RemediationSuggestion[]>
// GET /api/v1/executions/{id}/remediation
```

#### execution_dashboard.ts

**Fichier :** `src/services/execution_dashboard.ts`

Statistiques et données temporelles des exécutions.

```typescript
fetchExecutionStats(scope?, filters?): Promise<DashboardStats>
// GET /api/v1/executions/stats?scope=...

fetchExecutionTimeSeries(scope?, filters?): Promise<DashboardTimeSeriesPoint[]>
// GET /api/v1/executions/timeseries?scope=...

fetchExecutionTags(): Promise<string[]>
// GET /api/v1/executions/tags
```

#### execution_inventory.ts

**Fichier :** `src/services/execution_inventory.ts`

Données d'inventaire pour les formulaires dynamiques. Cache mémoire 5 min + sessionStorage.

```typescript
fetchInventoryItems(
  type: 'databases' | 'servers' | 'instances' | 'environments',
  environment?: string,
  options?: { server_names?: string[]; engine_type?: string }
): Promise<InventoryItem[]>
// GET /api/v1/inventory/{type}?environment=...
// Cache mémoire 5 min ; fallback sessionStorage si 503

fetchInventoryTargets(search?: string): Promise<InventoryTarget[]>
// GET /api/v1/inventory/targets?page=1&page_size=5000

fetchInventorySchema(): Promise<InventorySchema>
// GET /api/v1/inventory/schema
```

---

## Types API

**Fichier :** `src/types/api.ts` (~936 lignes)

### Types de base

```typescript
// Réponse standard
interface ApiResponse<T> {
  data: T;
}

// Réponse paginée
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

// Erreur API
interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
```

### Types de domaine

```typescript
// Moteurs de base de données
type ActionEngine = 'Oracle' | 'SQL Server' | 'DB2';

// Plateformes d'exécution
type ActionPlatform = 'AAP' | 'GitHub Actions' | 'Azure DevOps' | 'Terraform';

// Statuts d'action
type ActionStatus = 'draft' | 'published' | 'disabled';

// Niveaux d'impact
type ImpactLevel = 'low' | 'medium' | 'high' | 'critical';

// Statuts d'exécution
type ExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'APPROVAL_REQUIRED' | 'APPROVED' | 'REJECTED';

// Types d'étape
type ExecutionStepType = 'prerequisite' | 'execution' | 'verification';

// Types de connecteur
type ConnectorType = 'aap' | 'servicenow' | 'azuredevops' | 'jira' | 'github_actions' | 'terraform' | 'none';
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

interface ExecutionStepResponse {
  id: number;
  execution_id: number;
  step_order: number;
  step_name: string;
  step_type: ExecutionStepType;
  status: ExecutionStepStatus;
  started_at: string | null;
  completed_at: string | null;
  output: string | null;
  platform_job_id: string | null;
  error_message: string | null;
}
```

---

## Gestion des erreurs

### Pattern recommandé

```typescript
import { App } from 'antd';

function MyComponent() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const result = await submitExecution(data);
      message.success('Exécution lancée avec succès');
      navigate('/executions');
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };
}
```

### Erreurs courantes

| Code HTTP | Signification | Gestion |
|-----------|---------------|---------|
| 400 | Validation error | Afficher message d'erreur |
| 401 | Non authentifié | Refresh token automatique |
| 403 | Non autorisé | Afficher message permission |
| 404 | Non trouvé | Afficher message |
| 500 | Erreur serveur | Afficher message générique |

---

## Bonnes pratiques

### 1. Ne jamais appeler fetch directement

```typescript
// ❌ Mauvais
const response = await fetch('/api/v1/catalog/actions');

// ✅ Bon
const actions = await apiFetch<CatalogAction[]>('/catalog/actions');
```

### 2. Utiliser les services dédiés

```typescript
// ❌ Mauvais
const actions = await apiFetch<CatalogAction[]>('/catalog/actions');

// ✅ Bon
const actions = await fetchCatalogActions();
```

### 3. Typer les réponses

```typescript
// ❌ Mauvais
const result = await apiFetch('/executions');

// ✅ Bon
const result = await apiFetch<ExecutionResponse[]>('/executions');
```

### 4. Gérer le loading state

```typescript
const [data, setData] = useState<CatalogAction[] | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await fetchCatalogActions();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur');
    } finally {
      setLoading(false);
    }
  }
  load();
}, []);
```
# Architecture API Client — `api_client.ts`

## Vue d'ensemble

Le module `api_client.ts` centralise toute la communication HTTP frontend avec le backend Django REST.

**Flow :** Service → `apiFetch*()` → helpers (`buildHeaders`, `handleAuthenticatedFetch`, `parseErrorResponse`) → `fetch()` → Response

---

## Helpers internes

### `buildHeaders(token, contentType?, customHeaders?)`

Construit les headers HTTP avec authentification et Content-Type.

| Paramètre | Type | Description |
|-----------|------|-------------|
| `token` | `string \| null` | Token JWT (de `_getAccessToken()`) |
| `contentType` | `string?` | Content-Type (default: omis) |
| `customHeaders` | `Record<string, string>?` | Headers additionnels à merger |

**Exemple d'utilisation standalone:**
```typescript
import { buildHeaders } from './api_client';

const token = getAccessToken();
const headers = buildHeaders(token, 'application/json', { 'X-Request-Id': '123' });
// Résultat: { 'Content-Type': 'application/json', 'X-Request-Id': '123', 'Authorization': 'Bearer <token>' }
```

---

### `handleAuthenticatedFetch(path, init, headers)`

Exécute un fetch avec retry automatique sur 401 (token refresh).

1. Fetch initial vers `${API_BASE}${path}`
2. Si 401 et token présent → appel `_onRefreshNeeded()`
3. Si refresh succès → retry avec nouveau token
4. Retourne la Response finale

**Exemple d'utilisation standalone:**
```typescript
import { handleAuthenticatedFetch, buildHeaders } from './api_client';

const token = getAccessToken();
const headers = buildHeaders(token, 'application/json');
const response = await handleAuthenticatedFetch('/catalog', { method: 'GET' }, headers);
// Response inclut retry 401 automatique si token expiré
```

---

### `parseErrorResponse(response, captureBody?)`

Parse une Response en erreur en message structuré.

- **JSON** : Extrait `body.error.message`, fallback `Erreur HTTP {status}`
- **Text** : Utilise le body texte, fallback `Erreur HTTP {status}: {statusText}`
- **captureBody** : Si `true`, capture le body complet (utile pour les détails de validation 400)

**Exemple - Parsing erreur JSON:**
```typescript
import { parseErrorResponse } from './api_client';

const response = await fetch('/api/v1/action/create', { ... });
if (!response.ok) {
  const { message, body } = await parseErrorResponse(response, true);
  // message = "Validation failed"
  // body = { error: { message: "Validation failed", details: { name: "required" } } }
  console.error(message, body?.error?.details);
}
```

**Exemple - Parsing erreur texte:**
```typescript
const response = await fetch('/api/v1/health');
if (!response.ok) {
  const { message } = await parseErrorResponse(response, false);
  // message = "Service Unavailable" (body texte) ou "Erreur HTTP 503: Service Unavailable"
}
```

---

## Fonctions publiques

| Fonction | Content-Type | Réponse | Usage |
|----------|:------------:|---------|-------|
| `apiFetch<T>` | `application/json` | `body.data as T` | Appels standard (catalogue, admin, etc.) |
| `apiFetchRaw<T>` | `application/json` | `body as T` | Réponses avec champs extra (can_execute, etc.) |
| `apiFetchBlob` | aucun | `Blob` | Téléchargement fichiers (export audit) |
| `apiPostFormData<T>` | aucun (FormData auto) | `body as { data: T }` | Upload fichiers (photos profil) |

### Exemples d'utilisation

**`apiFetch<T>` - Standard (unwrap `.data`):**
```typescript
import { apiFetch } from '@/services/api_client';

// GET avec data unwrapping
const actions = await apiFetch<Action[]>('/catalog');
// Backend: { data: [{ id: 1, name: "Action 1" }] }
// Retour: [{ id: 1, name: "Action 1" }]

// POST
const newAction = await apiFetch<Action>('/admin/actions', {
  method: 'POST',
  body: JSON.stringify({ name: 'New Action' }),
});
```

**`apiFetchRaw<T>` - Full body (avec champs extra):**
```typescript
import { apiFetchRaw } from '@/services/api_client';

const response = await apiFetchRaw<{
  data: Action;
  can_execute: boolean;
  allowed_environments: string[];
}>('/action/123');

// Backend: { data: { id: 123, name: "DB Backup" }, can_execute: true, allowed_environments: ["dev", "staging"] }
// Retour complet sans unwrap
console.log(response.data.name);           // "DB Backup"
console.log(response.can_execute);         // true
console.log(response.allowed_environments); // ["dev", "staging"]
```

**`apiFetchBlob` - Téléchargement fichier:**
```typescript
import { apiFetchBlob } from '@/services/api_client';

const blob = await apiFetchBlob('/audit/export/pdf');
const url = URL.createObjectURL(blob);
const link = document.createElement('a');
link.href = url;
link.download = 'audit-report.pdf';
link.click();
```

**`apiPostFormData<T>` - Upload fichier:**
```typescript
import { apiPostFormData } from '@/services/api_client';

const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('name', 'Profile Picture');

const result = await apiPostFormData<{ file_id: string }>('/profiles/upload', formData);
console.log(result.data.file_id); // "abc-123"
```

---

## Exception : `auth_service.ts`

`auth_service.ts` utilise **partiellement** les helpers au lieu de fonctions complètes:

- **`refreshAccessToken()`** : Utilise `fetch()` brut + `parseErrorResponse()` helper
  - **Raison:** C'est le handler de refresh appelé par `handleAuthenticatedFetch` → circularité
  - **Alignment partiel:** Utilise `parseErrorResponse()` pour consistency

- **`fetchCurrentUser()`** : Utilise `buildHeaders()` + `parseErrorResponse()` helpers
  - **Raison:** Pas besoin de retry 401 (appelé après login avec token frais)
  - **Alignment partiel:** Utilise helpers pour consistency

- **`logoutApi()`** : Utilise `fetch()` brut (best effort, pas de throw)

**Exemple auth_service:**
```typescript
import { buildHeaders, parseErrorResponse } from './api_client';

export async function fetchCurrentUser(token: string): Promise<User | null> {
  const headers = buildHeaders(token); // ← Helper usage
  const res = await fetch(`${API_BASE}/auth/me`, { headers });
  if (!res.ok) {
    const { message } = await parseErrorResponse(res); // ← Helper usage
    console.warn(`fetchCurrentUser failed: ${message}`);
    return null;
  }
  const body = await res.json();
  return body.data ?? null;
}
```

---

## Error handling dans composants React

Toutes les erreurs HTTP sont lancées via `ApiError(message, status, responseBody?)`.

**Pattern recommandé:**
```typescript
import { apiFetch, ApiError } from '@/services/api_client';

try {
  const data = await apiFetch<Action>('/action/123');
  setAction(data);
} catch (err) {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      message.error('Accès refusé');
    } else if (err.status === 400) {
      // Validation error avec détails
      const details = err.responseBody?.error?.details;
      message.error(`Validation: ${JSON.stringify(details)}`);
    } else if (err.status === 404) {
      message.warning('Action introuvable');
    } else {
      message.error(err.message);
    }
  } else {
    // Network error ou autre
    message.error('Erreur réseau');
  }
}
```

**Erreur 401:** Gérée automatiquement par `handleAuthenticatedFetch` (retry + refresh), ne remonte pas au composant sauf si refresh échoue.

---

## Avant/Après Refactoring

### Avant (duplication)

Chaque fonction (`apiFetch`, `apiFetchRaw`, `apiFetchBlob`, `apiPostFormData`) dupliquait:
- ~6 lignes: Token injection + headers setup
- ~8 lignes: 401 retry logic
- ~22-24 lignes: Error parsing (try-catch imbriqués)

**Total:** ~60 lignes dupliquées x4 fonctions = ~240 lignes dupliquées

### Après (centralisé)

3 helpers centralisés (29 lignes au total) utilisés par les 4 fonctions:
- `buildHeaders()`: 15 lignes
- `handleAuthenticatedFetch()`: 17 lignes
- `parseErrorResponse()`: 24 lignes

4 fonctions publiques refactorées: ~13-15 lignes chacune (total ~52 lignes)

**Total api_client.ts:** 208 → 157 lignes (-24.5%, 51 lignes économisées)

**Bénéfice maintenabilité:**
- Modifier error parsing: **1 helper** au lieu de 4 fonctions
- Ajouter nouvelle méthode HTTP: **~15 lignes** avec helpers au lieu de copier-coller ~60 lignes
