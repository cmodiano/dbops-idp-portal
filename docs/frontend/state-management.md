# Gestion d'état (State Management)

Ce document décrit les patterns de gestion d'état utilisés dans le frontend IDP Portal.

## Architecture

Le frontend utilise **Context + Hooks** plutôt que Redux pour la gestion d'état :

```
┌─────────────────────────────────────────────────────┐
│                    App.tsx                          │
│  ┌───────────────────────────────────────────────┐  │
│  │              ThemeProvider                    │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │           ConfigProvider                │  │  │
│  │  │  ┌───────────────────────────────────┐  │  │  │
│  │  │  │         AuthProvider              │  │  │  │
│  │  │  │  ┌─────────────────────────────┐  │  │  │  │
│  │  │  │  │     DashboardProvider       │  │  │  │  │
│  │  │  │  │  ┌───────────────────────┐  │  │  │  │  │
│  │  │  │  │  │       Routes          │  │  │  │  │  │
│  │  │  │  │  └───────────────────────┘  │  │  │  │  │
│  │  │  │  └─────────────────────────────┘  │  │  │  │
│  │  │  └───────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Pourquoi Context + Hooks plutôt que Redux ?**

1. Moins de boilerplate
2. Intégré à React (pas de dépendance externe)
3. Suffisant pour l'échelle de l'application
4. Plus facile à tester
5. Meilleure cohabitation avec React 19

---

## React Contexts

### AuthContext

**Fichier :** `src/contexts/AuthContext.tsx`

Gère l'authentification SAML, les tokens JWT et les informations utilisateur.

```typescript
interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<string | null>;
  hasTab: (tabKey: NavigationTabKey) => boolean;
  isBusinessProfile: boolean;
}

interface User {
  id: number;
  username: string;
  display_name: string;
  profile: string;
  navigation_tabs: NavigationTabKey[];
  is_auditor?: boolean;
  is_business_profile?: boolean;
}

type NavigationTabKey = 'catalog' | 'executions' | 'dashboard' | 'admin' | 'audit';
```

**Usage :**

```typescript
import { useAuth } from '../contexts/AuthContext';

function MyComponent() {
  const { user, isAuthenticated, hasTab, logout } = useAuth();

  if (!isAuthenticated) {
    return <LoginPrompt />;
  }

  return (
    <div>
      <p>Bienvenue {user?.display_name}</p>
      {hasTab('admin') && <AdminLink />}
      <button onClick={logout}>Déconnexion</button>
    </div>
  );
}
```

**Fonctionnalités clés :**

1. **Restoration de session** : Au chargement, tente de rafraîchir le token via cookie httpOnly
2. **Token refresh automatique** : L'API client intercepte les 401 et rafraîchit le token
3. **Mode DEV** : `VITE_DEV_AUTH=true` bypass l'auth SAML avec un utilisateur mock DBOPS
4. **Contrôle d'accès** : `hasTab()` vérifie les permissions de navigation

---

### ThemeContext

**Fichier :** `src/contexts/ThemeContext.tsx`

Gère le mode thème (light/dark/system).

```typescript
interface ThemeContextValue {
  mode: ThemeMode;                    // 'light' | 'dark' | 'system'
  effectiveMode: EffectiveThemeMode;  // 'light' | 'dark' (résolu)
  setMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}
```

**Usage :**

```typescript
import { useTheme } from '../contexts/ThemeContext';

function ThemeToggle() {
  const { effectiveMode, toggleTheme } = useTheme();

  return (
    <button onClick={toggleTheme}>
      {effectiveMode === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}
```

**Fonctionnalités :**

1. **Persistence localStorage** : Le choix est sauvegardé
2. **Mode system** : Suit les préférences OS (`prefers-color-scheme`)
3. **Transition animée** : Changement fluide de thème (0.4s)

---

### DashboardContext

**Fichier :** `src/contexts/DashboardContext.tsx`

Gère le compteur d'erreurs non vues pour le badge de notification.

```typescript
interface DashboardContextValue {
  unseenErrorCount: number;
  addUnseenError: (executionId: number) => void;
  markAllSeen: () => void;
  hasUnseenError: (executionId: number) => boolean;
}
```

**Usage :**

```typescript
import { useDashboard } from '../contexts/DashboardContext';

function NotificationBadge() {
  const { unseenErrorCount, markAllSeen } = useDashboard();

  return (
    <Badge count={unseenErrorCount} onClick={markAllSeen}>
      <BellIcon />
    </Badge>
  );
}
```

**Persistence :** Les IDs d'erreurs vues sont stockés dans localStorage.

---

## Custom Hooks

### useAuth

**Fichier :** `src/contexts/AuthContext.tsx` (exporté avec le context)

Accès simplifié au contexte d'authentification.

```typescript
const { user, isAuthenticated, hasTab, isBusinessProfile, logout } = useAuth();
```

---

### useTheme

**Fichier :** `src/contexts/ThemeContext.tsx` (exporté avec le context)

Accès au contexte de thème.

```typescript
const { effectiveMode, toggleTheme, setMode } = useTheme();
```

---

### useDebounce

**Fichier :** `src/hooks/useDebounce.ts`

Debounce une valeur pour éviter les appels API trop fréquents.

```typescript
function useDebounce<T>(value: T, delay: number): T
```

**Usage :**

```typescript
const [searchTerm, setSearchTerm] = useState('');
const debouncedSearch = useDebounce(searchTerm, 300);

useEffect(() => {
  if (debouncedSearch) {
    fetchResults(debouncedSearch);
  }
}, [debouncedSearch]);
```

**À ne pas confondre avec :** `src/utils/debounce.ts` — utilitaire pour **debouncer une fonction** (ex. validation cron en temps réel dans ExecutionWizard). Le hook `useDebounce` debounce une **valeur** ; `debounce(fn, waitMs)` retourne une fonction qui n'exécute `fn` qu'après un délai sans nouvel appel.

#### Utilitaire debounce (fonction)

**Fichier :** `src/utils/debounce.ts`

Pour rate-limiter des callbacks (validation async, handlers fréquents) :

```typescript
import { debounce } from '../utils/debounce';

const debouncedValidate = debounce(async (expression: string) => {
  const valid = await validateCron(expression);
  setCronError(valid ? null : 'Expression invalide');
}, 300);
```

---

### useWebSocket

**Fichier :** `src/hooks/useWebSocket.ts`

Connexion WebSocket pour les mises à jour temps réel d'une exécution.

```typescript
interface UseWebSocketResult {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  loading: boolean;
  error: string | null;
  lastMessage: { type: string; execution_id?: number; data?: unknown } | null;
}

function useWebSocket(executionId: number | null): UseWebSocketResult
```

**Usage :**

```typescript
const { steps, execution, loading, error } = useWebSocket(executionId);

// Afficher la timeline
return (
  <Timeline>
    {steps.map(step => (
      <Timeline.Item key={step.id} color={getStatusColor(step.status)}>
        {step.step_name}
      </Timeline.Item>
    ))}
  </Timeline>
);
```

**Fonctionnalités :**

1. **Reconnexion automatique** : Retry après 2 secondes en cas de déconnexion
2. **Re-sync complet** : Appel GET API à chaque reconnexion
3. **Messages supportés** : `step_update`, `execution_complete`, `execution_failed`

---

### useExecutionFilters

**Fichier :** `src/hooks/useExecutionFilters.ts`

State des filtres pour la page des exécutions.

```typescript
interface ExecutionFilters {
  status: string | null;
  actionId: number | null;
  dateRange: [string, string] | null;
  technology: string | null;
  environment: string | null;
  tags: string[];
  tab: 'all' | 'mine';
}

interface UseExecutionFiltersResult {
  filters: ExecutionFilters;
  setFilter: <K extends keyof ExecutionFilters>(key: K, value: ExecutionFilters[K]) => void;
  resetFilters: () => void;
  activeFilterCount: number;
}
```

**Usage :**

```typescript
const { filters, setFilter, activeFilterCount, resetFilters } = useExecutionFilters();

return (
  <Select
    value={filters.status}
    onChange={(v) => setFilter('status', v)}
  />
);
```

---

### useUrlFilters

**Fichier :** `src/hooks/useUrlFilters.ts`

Synchronise les filtres avec les query params URL.

```typescript
interface UseUrlFiltersResult<T> {
  filters: T;
  setFilter: <K extends keyof T>(key: K, value: T[K]) => void;
  setFilters: (filters: Partial<T>) => void;
  resetFilters: () => void;
}

function useUrlFilters<T extends Record<string, unknown>>(
  defaultFilters: T,
  options?: { paramPrefix?: string }
): UseUrlFiltersResult<T>
```

**Usage :**

```typescript
const { filters, setFilter } = useUrlFilters({
  status: null,
  search: '',
  page: 1,
});

// L'URL devient : ?status=COMPLETED&search=oracle&page=2
setFilter('status', 'COMPLETED');
setFilter('search', 'oracle');
setFilter('page', 2);
```

**Avantages :**
- Partage de liens avec filtres pré-appliqués
- Navigation browser (back/forward) préserve les filtres
- Bookmarks avec filtres

---

### useThemeMode

**Fichier :** `src/hooks/useThemeMode.ts`

Hook interne utilisé par ThemeContext pour la logique de thème.

```typescript
interface UseThemeModeResult {
  mode: ThemeMode;
  effectiveMode: EffectiveThemeMode;
  setMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}
```

---

### usePendingApprovalsCount

**Fichier :** `src/hooks/usePendingApprovalsCount.ts`

Compte les approbations en attente pour le badge de notification.

```typescript
function usePendingApprovalsCount(): {
  count: number;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}
```

**Usage :**

```typescript
const { count } = usePendingApprovalsCount();

return <Badge count={count}><ApprovalIcon /></Badge>;
```

---

### useRemediationSuggestions

**Fichier :** `src/hooks/useRemediationSuggestions.ts`

Récupère les suggestions de remédiation pour une exécution en erreur.

```typescript
function useRemediationSuggestions(executionId: number | null): {
  suggestions: RemediationSuggestion[];
  loading: boolean;
  error: string | null;
}
```

---

### useDashboardWebSocket

**Fichier :** `src/hooks/useDashboardWebSocket.ts`

WebSocket pour les mises à jour temps réel du dashboard.

```typescript
function useDashboardWebSocket(): {
  stats: DashboardStats | null;
  recentExecutions: ExecutionSummary[];
  connected: boolean;
}
```

---

### useMediaQuery

**Fichier :** `src/hooks/useMediaQuery.ts`

Hook pour les media queries responsive.

```typescript
function useMediaQuery(query: string): boolean
```

**Usage :**

```typescript
const isMobile = useMediaQuery('(max-width: 768px)');

return isMobile ? <MobileView /> : <DesktopView />;
```

---

## Patterns recommandés

### État local vs Context

| Type de state | Solution | Exemple |
|---------------|----------|---------|
| UI local | `useState` | Ouverture d'un modal |
| Formulaire | `useState` | Valeurs d'input |
| Liste paginée | `useState` + service | Résultats de recherche |
| Auth/User | Context | `AuthContext` |
| Thème global | Context | `ThemeContext` |
| Filtres partagés | Hook + URL | `useUrlFilters` |
| Temps réel | Hook + WebSocket | `useWebSocket` |

### Éviter les re-renders

```typescript
// ❌ Mauvais - crée un nouvel objet à chaque render
const value = { user, token, login };
return <AuthContext.Provider value={value}>...</AuthContext.Provider>;

// ✅ Bon - mémoïse la valeur
const value = useMemo(() => ({ user, token, login }), [user, token, login]);
return <AuthContext.Provider value={value}>...</AuthContext.Provider>;
```

### Séparer les concerns

```typescript
// ✅ Bon - chaque hook a une responsabilité claire
const { filters, setFilter } = useExecutionFilters();
const { executions, loading } = useExecutions(filters);
const { count: approvalCount } = usePendingApprovalsCount();
```

### Tests des hooks

```typescript
import { renderHook, act } from '@testing-library/react';

it('should debounce value', async () => {
  const { result } = renderHook(() => useDebounce('test', 300));

  expect(result.current).toBe('test');

  // Attendre le délai
  await act(async () => {
    await new Promise(r => setTimeout(r, 350));
  });

  expect(result.current).toBe('test');
});
```

---

## Flux de données

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Service   │───▶│    Hook     │───▶│  Component  │
│  (API call) │    │  (state)    │    │   (UI)      │
└─────────────┘    └─────────────┘    └─────────────┘
       ▲                                     │
       └─────────────────────────────────────┘
                    (user action)
```

**Exemple concret :**

```
catalog_service.fetchCatalogActions()
        │
        ▼
useEffect dans CatalogPage
        │
        ▼
setActions(data) - state local
        │
        ▼
ActionCard/ActionTable - render UI
        │
        ▼
onClick → onExecute(actionId)
        │
        ▼
execution_service.submitExecution()
```
