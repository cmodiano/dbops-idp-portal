# Routing et Navigation

Ce document décrit le système de routing et de navigation du frontend IDP Portal.

## Stack technique

- **React Router 7.13.0** - Routing SPA
- **Lazy loading** - Chargement à la demande des pages
- **Guards** - Contrôle d'accès par profil

## Architecture du routing

```
                          ┌─────────────────────────┐
                          │      BrowserRouter      │
                          └───────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │            Routes                 │
                    └─────────────────┬─────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
    ┌─────┴─────┐              ┌──────┴──────┐              ┌─────┴─────┐
    │  /login   │              │ ProtectedRoute │            │    /*     │
    │  /auth/*  │              │   + AppLayout  │            │ NotFound  │
    └───────────┘              └──────┬────────┘            └───────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │           │           │           │           │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │ /catalog  │ │/exec- │ │/analytics │ │/admin │ │  /audit   │
        │           │ │utions │ │ (Guard)   │ │(Guard)│ │  (Guard)  │
        └───────────┘ └───────┘ └───────────┘ └───────┘ └───────────┘
```

## Table des routes

| Route | Page | Guard | Accès |
|-------|------|-------|-------|
| `/` | Redirect → `/catalog` | - | Tous |
| `/login` | LoginPage | - | Non authentifié |
| `/auth/callback` | AuthCallbackPage | - | Callback SAML |
| `/catalog` | CatalogPage | ProtectedRoute | Authentifié |
| `/executions` | ExecutionsPage | ProtectedRoute | Authentifié |
| `/analytics` | DashboardPage | AnalyticsGuard | DBOPS uniquement |
| `/dashboard` | Redirect → `/analytics` | - | Backward compat |
| `/admin` | AdminPage | AdminGuard | Tab admin |
| `/audit` | AuditPage | AuditGuard | Tab audit ou is_auditor |
| `*` | NotFoundPage | - | Tous |

## Configuration des routes

**Fichier :** `src/App.tsx`

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { lazy, Suspense } from 'react';

// Lazy loading des pages
const CatalogPage = lazy(() => import('./pages/CatalogPage'));
const ExecutionsPage = lazy(() => import('./pages/ExecutionsPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const AuditPage = lazy(() => import('./pages/AuditPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const AuthCallbackPage = lazy(() => import('./pages/AuthCallbackPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

// Dans le JSX
<BrowserRouter>
  <Suspense fallback={null}>
    <Routes>
      {/* Routes publiques */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />

      {/* Routes protégées avec layout */}
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/catalog" replace />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/executions" element={<ExecutionsPage />} />
        <Route path="/analytics" element={<AnalyticsGuard><DashboardPage /></AnalyticsGuard>} />
        <Route path="/dashboard" element={<Navigate to="/analytics" replace />} />
        <Route path="/admin" element={<AdminGuard><AdminPage /></AdminGuard>} />
        <Route path="/audit" element={<AuditGuard><AuditPage /></AuditGuard>} />
      </Route>

      {/* 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  </Suspense>
</BrowserRouter>
```

---

## Guards (Contrôle d'accès)

### ProtectedRoute

**Fichier :** `src/components/auth/ProtectedRoute.tsx`

Guard de base pour les pages authentifiées.

```typescript
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <Spin size="large" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

**Comportement :**
- `isLoading` → Affiche spinner
- Non authentifié → Redirige vers `/login`
- Authentifié → Affiche le contenu

---

### AdminGuard

**Fichier :** `src/App.tsx`

Guard pour la page d'administration.

```typescript
function AdminGuard({ children }: { children: React.ReactNode }) {
  const { hasTab } = useAuth();

  if (!hasTab('admin')) {
    return <Navigate to="/catalog" replace />;
  }

  return <>{children}</>;
}
```

**Condition :** `user.navigation_tabs` doit contenir `'admin'`

---

### AuditGuard

**Fichier :** `src/App.tsx`

Guard pour la page d'audit SOC1.

```typescript
function AuditGuard({ children }: { children: React.ReactNode }) {
  const { hasTab, user } = useAuth();

  // Story 6.3, AC8: Access restricted to auditors
  if (!hasTab('audit') && !user?.is_auditor) {
    return <Navigate to="/catalog" replace />;
  }

  return <>{children}</>;
}
```

**Conditions (OR) :**
- `user.navigation_tabs` contient `'audit'`
- `user.is_auditor === true`

---

### AnalyticsGuard

**Fichier :** `src/App.tsx`

Guard pour la page Analytics (anciennement Dashboard).

```typescript
function AnalyticsGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  // DBOPS only for advanced analytics
  const isDbops = user?.profile?.toLowerCase() === 'dbops';
  if (!isDbops) {
    return <Navigate to="/executions" replace />;
  }

  return <>{children}</>;
}
```

**Condition :** `user.profile === 'DBOPS'` (case-insensitive)

---

## Navigation (TopNav)

**Fichier :** `src/components/layout/TopNav.tsx`

La barre de navigation affiche les tabs selon les permissions utilisateur.

```typescript
// Définition des tabs de navigation
const NAV_ITEMS: Array<{ key: string; path: string; label: string; icon: ReactNode }> = [
  { key: 'catalog', path: '/catalog', label: 'Catalogue', icon: <AppstoreOutlined /> },
  { key: 'executions', path: '/executions', label: 'Exécutions', icon: <ThunderboltOutlined /> },
  { key: 'analytics', path: '/analytics', label: 'Analytics', icon: <BarChartOutlined /> },
  { key: 'admin', path: '/admin', label: 'Admin', icon: <SettingOutlined /> },
  { key: 'audit', path: '/audit', label: 'Audit', icon: <AuditOutlined /> },
];

// Filtrage selon permissions
const visibleItems = NAV_ITEMS.filter(item => {
  if (item.key === 'analytics') {
    return user?.profile?.toLowerCase() === 'dbops';
  }
  if (item.key === 'admin' || item.key === 'audit') {
    return hasTab(item.key as NavigationTabKey);
  }
  return true; // catalog et executions toujours visibles
});
```

### Diagramme de flux de navigation

```
┌────────────────────────────────────────────────────────────────┐
│                         TopNav                                  │
│  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌───────┐ ┌───────┐   │
│  │Catalogue│ │Exécutions │ │Analytics*│ │Admin* │ │Audit* │   │
│  └────┬────┘ └─────┬─────┘ └────┬─────┘ └───┬───┘ └───┬───┘   │
│       │            │            │           │         │        │
│       │            │            │           │         │        │
└───────┼────────────┼────────────┼───────────┼─────────┼────────┘
        │            │            │           │         │
        ▼            ▼            ▼           ▼         ▼
  ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ ┌────────┐
  │CatalogPage│ │Executions│ │Dashboard│ │AdminPg │ │AuditPg │
  └───────────┘ │   Page   │ │  Page   │ │        │ │        │
                └──────────┘ └─────────┘ └────────┘ └────────┘

* = Conditionnel selon profil/permissions
```

---

## Flux d'authentification

### 1. Accès initial (non authentifié)

```
Utilisateur         Frontend            Backend
    │                   │                   │
    │──────────────────▶│                   │
    │   GET /catalog    │                   │
    │                   │                   │
    │   ProtectedRoute: │                   │
    │   isLoading=true  │                   │
    │◀──── Spinner ─────│                   │
    │                   │                   │
    │                   │───────────────────▶
    │                   │ POST /auth/refresh │
    │                   │◀──────────────────│
    │                   │    401 (no cookie) │
    │                   │                   │
    │   isAuthenticated │                   │
    │   = false         │                   │
    │◀── Redirect ──────│                   │
    │   /login          │                   │
```

### 2. Login SAML

```
Utilisateur         Frontend            Backend            IdP SAML
    │                   │                   │                   │
    │── Click Login ───▶│                   │                   │
    │                   │                   │                   │
    │◀─── Redirect ─────│                   │                   │
    │ /api/v1/auth/saml/│                   │                   │
    │      login        │                   │                   │
    │                   │                   │                   │
    │───────────────────┼──────────────────▶│                   │
    │                   │                   │                   │
    │                   │                   │──── SAML Req ────▶│
    │                   │                   │                   │
    │◀──────────────────┼───────────────────┼── Login Form ─────│
    │                   │                   │                   │
    │── Credentials ────┼───────────────────┼──────────────────▶│
    │                   │                   │                   │
    │◀──────────────────┼───────────────────┼── SAML Response ──│
    │                   │                   │                   │
    │   Redirect to     │                   │                   │
    │   /auth/callback  │                   │                   │
    │   #access_token=  │                   │                   │
    │        TOKEN      │                   │                   │
    │                   │                   │                   │
    │──────────────────▶│                   │                   │
    │                   │                   │                   │
    │                   │── Extract token ──│                   │
    │                   │   from URL hash   │                   │
    │                   │                   │                   │
    │                   │───────────────────▶                   │
    │                   │ GET /auth/me      │                   │
    │                   │ Authorization:    │                   │
    │                   │   Bearer TOKEN    │                   │
    │                   │◀──────────────────│                   │
    │                   │    User data      │                   │
    │                   │                   │                   │
    │◀── Redirect ──────│                   │                   │
    │   /catalog        │                   │                   │
```

### 3. Callback d'authentification

**Fichier :** `src/pages/AuthCallbackPage.tsx`

```typescript
// Le token est passé via URL fragment (pas query param)
// Les fragments ne sont pas envoyés au serveur = plus sécurisé
// URL: /auth/callback#access_token=TOKEN

useEffect(() => {
  const hash = window.location.hash;
  if (hash.includes('access_token=')) {
    const tokenMatch = hash.match(/access_token=([^&]+)/);
    const token = tokenMatch ? tokenMatch[1] : null;
    if (token) {
      setAccessToken(token);
      // Nettoyer l'URL immédiatement
      window.history.replaceState(null, '', window.location.pathname);
      // Récupérer le profil utilisateur
      fetchCurrentUser(token).then(setUser);
    }
  }
}, []);
```

---

## Mode développement (DEV_AUTH)

Pour bypasser l'authentification SAML en développement :

```env
# .env.local
VITE_DEV_AUTH=true
```

**Comportement :**
- Utilise un utilisateur mock DBOPS
- Toutes les permissions activées
- Aucun appel API d'authentification

```typescript
const DEV_MOCK_USER: User = {
  id: 1,
  username: 'dev.dbops',
  display_name: 'Dev DBOPS User',
  profile: 'dbops',
  navigation_tabs: ['catalog', 'executions', 'dashboard', 'admin', 'audit'],
  is_auditor: true,
};
```

---

## Lazy loading

Les pages sont chargées à la demande pour optimiser le bundle initial :

```typescript
// ❌ Import direct (tout dans le bundle initial)
import { CatalogPage } from './pages/CatalogPage';

// ✅ Lazy loading (chargé quand nécessaire)
const CatalogPage = lazy(() => import('./pages/CatalogPage'));
```

**Suspense fallback :**

```typescript
<Suspense fallback={null}>
  <Routes>
    {/* ... */}
  </Routes>
</Suspense>
```

Le fallback est `null` car le layout affiche déjà un état de chargement.

---

## Navigation programmatique

### Avec useNavigate

```typescript
import { useNavigate } from 'react-router';

function MyComponent() {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate('/executions');
    // Ou avec state
    navigate('/executions', { state: { filter: 'failed' } });
    // Ou replace (pas d'historique)
    navigate('/catalog', { replace: true });
  };
}
```

### Avec Link

```typescript
import { Link } from 'react-router';

<Link to="/catalog">Catalogue</Link>
<Link to={`/executions?actionId=${action.id}`}>Voir exécutions</Link>
```

### Redirection après action

```typescript
const handleSubmit = async () => {
  const execution = await submitExecution(data);
  // Redirection vers les exécutions après soumission
  navigate('/executions');
};
```

---

## Query params et filtres

Les filtres sont persistés dans l'URL via `useUrlFilters` :

```typescript
// URL: /executions?status=FAILED&actionId=123&tab=mine

const { filters, setFilter } = useUrlFilters({
  status: null,
  actionId: null,
  tab: 'all',
});

// Mise à jour de l'URL
setFilter('status', 'COMPLETED');
// URL devient: /executions?status=COMPLETED&actionId=123&tab=mine
```

**Avantages :**
- Partage de liens avec filtres
- Historique browser fonctionnel
- Rechargement préserve les filtres
