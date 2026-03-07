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

Exécutions et remédiation.

```typescript
// Soumettre une nouvelle exécution
submitExecution(request: ExecutionCreateRequest): Promise<ExecutionCreateResponse>
// POST /api/v1/executions

// Détail d'une exécution
getExecution(executionId: number): Promise<ExecutionResponse>
// GET /api/v1/executions/{id}

// Étapes d'une exécution
getExecutionSteps(executionId: number): Promise<ExecutionStepResponse[]>
// GET /api/v1/executions/{id}/steps

// Logs d'une étape
getStepLogs(executionId: number, stepId: number): Promise<StepLogsResponse>
// GET /api/v1/executions/{id}/steps/{stepId}/logs

// Liste des exécutions (paginée)
listExecutions(page?: number, pageSize?: number, scope?: string, filters?: ExecutionFilters): Promise<ListExecutionsResponse>
// GET /api/v1/executions?page=...&page_size=...&scope=...

// Suggestions de remédiation
fetchRemediationSuggestions(executionId: number): Promise<RemediationSuggestion[]>
// GET /api/v1/executions/{id}/remediation-suggestions

// Déclencher une action corrective
triggerRemediation(executionId: number, suggestionId: number): Promise<ExecutionCreateResponse>
// POST /api/v1/executions/{id}/remediate/{suggestionId}

// Données inventaire pour formulaire dynamique
fetchInventory(type: string, params?: Record<string, string>): Promise<InventoryItem[]>
// GET /api/v1/inventory/{type}?param=...

// Statistiques globales
fetchDashboardStats(filters?: ExecutionFilters): Promise<DashboardStats>
// GET /api/v1/executions/stats

// Données timeseries
fetchDashboardTimeSeries(filters?: ExecutionFilters): Promise<DashboardTimeSeriesPoint[]>
// GET /api/v1/executions/timeseries
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
