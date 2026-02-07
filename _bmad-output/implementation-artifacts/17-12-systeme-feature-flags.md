# Story 17.12: Système de Feature Flags

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'équipe produit / DevOps,
je veux un système de feature flags,
afin de permettre des déploiements progressifs et des rollouts contrôlés.

## Acceptance Criteria

**Given** une fonctionnalité peut être livrée sans être activée pour tous les utilisateurs
**When** un feature flag est configuré (on/off ou pourcentage)
**Then** le frontend et/ou le backend respectent l'état du flag
**And** la configuration des flags est centralisée (fichier, env, ou service dédié)
**And** l'impact sur la CI et le déploiement est documenté

## Context & Rationale

**Source:** Epic 17 - Reduction de la dette technique & amelioration qualite (audit 06/02/2026)
**Assessment Reference:** §6, §7 - Pas de système de feature flags

Le système de feature flags doit permettre de:
1. **Déployer du code désactivé** en production (dark launch)
2. **Activer progressivement** des fonctionnalités (rollout progressif)
3. **Tester en production** avec un sous-ensemble d'utilisateurs (canary release)
4. **Désactiver rapidement** une fonctionnalité problématique (kill switch)
5. **A/B testing** de fonctionnalités

## Technical Requirements

### Backend Django Requirements

**Configuration Pattern** (inspiré de Story 17.11 - Rate Limiting):
- Variables d'environnement pour configuration des flags
- Validation au startup via `core/startup_checks.py`
- Cache-based pour performance (LocMemCache MVP → Redis production)
- Structured logging avec correlation_id

**Feature Flag Service** (`core/feature_flags.py`):
- Service singleton pour évaluation des flags
- Support on/off simple ET pourcentage de rollout
- Context-aware evaluation (user_id, profile, environment)
- Cache avec TTL configurable

**API Endpoint** (`api/v1/feature-flags/`):
- GET `/api/v1/feature-flags/` - liste flags disponibles (admin only)
- GET `/api/v1/feature-flags/status` - état flags pour utilisateur courant
- PATCH `/api/v1/feature-flags/{flag_key}` - modifier flag (admin only)

### Frontend React Requirements

**Feature Flag Context** (`src/contexts/FeatureFlagContext.tsx`):
- Context provider pour état global des flags
- Hook `useFeatureFlag(flagKey)` pour composants
- Auto-refresh périodique ou WebSocket sync

**Components**:
- `<FeatureGuard flag="new-workflow-builder">` - conditional rendering
- `<FeatureFlagToggle flag="dark-mode" />` - admin UI toggle

### Configuration Storage

**MVP Approach** (Simple & Fast):
- Configuration in `.env` files with JSON structure
- Example: `FEATURE_FLAGS='{"new_workflow_builder":{"enabled":true,"rollout":100}}'`
- Fallback to database table `core_feature_flags` si besoin de UI admin

**Production Upgrade Path**:
- Database table avec cache invalidation
- Redis pub/sub pour sync multi-instance
- Admin UI pour gestion flags (optional, hors scope story)

## Tasks / Subtasks

### Backend Implementation

- [x] **Task 1: Modèle de données et configuration** (AC: #1)
  - [x] 1.1: Créer migration pour table `core_feature_flags` (FEATURE_KEY, ENABLED, ROLLOUT_PERCENT, UPDATED_AT, UPDATED_BY)
  - [x] 1.2: Créer modèle Django `FeatureFlag` avec validation (rollout_percent 0-100)
  - [x] 1.3: Ajouter variables d'environnement dans `.env.production.template`: `FEATURE_FLAGS_SOURCE` (env|database), `FEATURE_FLAGS_CACHE_TTL`
  - [x] 1.4: Parser JSON de `FEATURE_FLAGS` env var dans `settings.py` avec fallback vide

- [x] **Task 2: Service d'évaluation de flags** (AC: #1, #2)
  - [x] 2.1: Créer `core/feature_flags.py` avec classe `FeatureFlagService` (singleton pattern)
  - [x] 2.2: Méthode `is_enabled(flag_key: str, context: dict = None) -> bool` avec cache lookup
  - [x] 2.3: Méthode `get_rollout_status(flag_key: str, user_id: str = None) -> bool` avec hash % rollout_percent
  - [x] 2.4: Intégration cache Django avec TTL (clé: `feature_flag:{flag_key}`, TTL: `FEATURE_FLAGS_CACHE_TTL`)
  - [x] 2.5: Logging structuré: `feature_flag_evaluated` (flag_key, enabled, rollout_percent, user_id, correlation_id)

- [x] **Task 3: API REST pour gestion des flags** (AC: #2)
  - [x] 3.1: Créer serializers `FeatureFlagSerializer` (DRF) avec validation rollout_percent
  - [x] 3.2: ViewSet `FeatureFlagViewSet` avec permissions admin only (IsAdminUser)
  - [x] 3.3: Endpoint GET `/api/v1/feature-flags/` - liste tous flags (admin only)
  - [x] 3.4: Endpoint GET `/api/v1/feature-flags/status` - état flags pour utilisateur courant (authenticated)
  - [x] 3.5: Endpoint PATCH `/api/v1/feature-flags/{flag_key}` - toggle enabled ou modifier rollout (admin only)
  - [x] 3.6: Invalidation cache après PATCH (cache.delete pattern)

- [x] **Task 4: Startup validation et observabilité** (AC: #3)
  - [x] 4.1: Ajouter `validate_feature_flags_config()` dans `core/startup_checks.py`
  - [x] 4.2: Valider format JSON de `FEATURE_FLAGS` env var (fail-fast si invalide en production)
  - [x] 4.3: Valider cohérence base de données si `FEATURE_FLAGS_SOURCE=database`
  - [x] 4.4: Logger startup event: `feature_flags_initialized` (source, count, correlation_id)

- [x] **Task 5: Tests backend** (AC: #1, #2)
  - [x] 5.1: Tests unitaires `test_feature_flag_service.py` (is_enabled, rollout_status, cache behavior)
  - [x] 5.2: Tests API `test_feature_flag_api.py` (GET liste, GET status, PATCH toggle, permissions)
  - [x] 5.3: Tests integration cache invalidation (PATCH → cache cleared)
  - [x] 5.4: Tests rollout logic (user_id hashing, 0%/50%/100% rollout scenarios)

### Frontend Implementation

- [x] **Task 6: Context et hooks** (AC: #2)
  - [x] 6.1: Créer `src/contexts/FeatureFlagContext.tsx` avec FeatureFlagProvider
  - [x] 6.2: Hook `useFeatureFlag(flagKey: string): boolean` pour evaluation côté client
  - [x] 6.3: Hook `useFeatureFlags(): Record<string, boolean>` pour état global
  - [x] 6.4: Service API `src/services/featureFlagService.ts` (GET /status endpoint)
  - [x] 6.5: Auto-refresh périodique (5min) ou WebSocket event pour invalidation

- [x] **Task 7: Composants de guard** (AC: #2)
  - [x] 7.1: Composant `<FeatureGuard flag="flag_key" fallback={<Loading />}>` pour conditional rendering
  - [x] 7.2: Composant `<FeatureToggle flag="flag_key" on={<NewUI />} off={<OldUI />}>` pour A/B testing
  - [x] 7.3: Integration avec AuthContext pour user_id propagation

- [x] **Task 8: Admin UI pour gestion flags (optionnel)** (AC: #3)
  - [x] 8.1: Page `/admin/feature-flags` avec liste flags (AdminGuard protected)
  - [x] 8.2: Table Ant Design avec colonnes: Flag Key, Enabled (Switch), Rollout % (Slider), Updated
  - [x] 8.3: Inline editing avec PATCH API call
  - [x] 8.4: Notification toast après modification réussie

- [x] **Task 9: Tests frontend** (AC: #2)
  - [x] 9.1: Tests `FeatureFlagContext.test.tsx` (provider, hook, fetch, cache)
  - [x] 9.2: Tests `FeatureGuard.test.tsx` (render when enabled, fallback when disabled)
  - [x] 9.3: Tests `FeatureToggle.test.tsx` (render on vs off branches)
  - [x] 9.4: Tests integration avec mock API (GET /status, auto-refresh)

### Documentation

- [x] **Task 10: Documentation technique** (AC: #4)
  - [x] 10.1: Créer `docs/feature-flags.md` avec guide utilisation (backend + frontend)
  - [x] 10.2: Exemples d'usage: nouveau composant, refactor progressif, A/B testing
  - [x] 10.3: Configuration déploiement: variables d'environnement, migration base de données
  - [x] 10.4: Procédure activation/désactivation d'urgence (kill switch)
  - [x] 10.5: Impact CI/CD: pas de changement requis, flags désactivés par défaut

## Dev Notes

### Architecture Compliance

**Configuration Pattern** (référence: Story 17.5, 17.11):
- Variables d'environnement via `.env` files
- Validation au startup (fail-fast en production)
- Cache-based pour performance (TTL configurable)
- Structured logging JSON avec correlation_id

**Middleware Stack** (référence: `idp_backend/settings.py`):
- Pas de nouveau middleware requis
- Intégration via service singleton pattern (similaire à rate limiting)

**Security Considerations**:
- RBAC: Admin only pour modification flags (IsAdminUser permission)
- Audit trail: Log tous changements de flags (AuditActionType.FEATURE_FLAG_UPDATED)
- Cache invalidation après modification (éviter stale state)

### File Structure Requirements

**Backend Files** (pattern: snake_case):
```
django_backend/
├── core/
│   ├── models.py                     # Ajouter FeatureFlag model
│   ├── feature_flags.py              # NEW - FeatureFlagService singleton
│   ├── startup_checks.py             # Ajouter validate_feature_flags_config()
│   └── tests/
│       └── test_feature_flags.py     # NEW - Tests service + API
├── api/
│   └── v1/
│       └── feature_flags.py          # NEW - ViewSet + serializers
├── migrations/
│   └── V052_feature_flags.sql        # NEW - Table core_feature_flags
└── .env.production.template           # Ajouter FEATURE_FLAGS, FEATURE_FLAGS_SOURCE
```

**Frontend Files** (pattern: PascalCase components, camelCase utilities):
```
frontend/
├── src/
│   ├── contexts/
│   │   └── FeatureFlagContext.tsx    # NEW - Provider + hooks
│   ├── components/
│   │   ├── FeatureGuard.tsx          # NEW - Conditional rendering
│   │   └── FeatureToggle.tsx         # NEW - A/B testing component
│   ├── services/
│   │   └── featureFlagService.ts     # NEW - API client
│   ├── pages/
│   │   └── admin/
│   │       └── FeatureFlagsPage.tsx  # NEW - Admin UI (optionnel)
│   └── __tests__/
│       └── FeatureFlag.test.tsx      # NEW - Tests context + components
└── .env.development                   # Ajouter VITE_FEATURE_FLAGS_ENABLED
```

### Library & Framework Requirements

**Backend** (référence: pyproject.toml):
- Django 5.2 + DRF 3.16 (déjà installé)
- `django.core.cache` (LocMemCache, déjà configuré)
- Pas de nouvelle dépendance requise

**Frontend** (référence: package.json):
- React 19 + Context API (déjà installé)
- Ant Design 6.2 pour admin UI (Switch, Slider, Table - déjà installé)
- Pas de nouvelle dépendance requise

### Testing Requirements

**Test Coverage** (référence: Story 17.11 - 37 tests):
- Minimum 20 tests backend (service + API + permissions)
- Minimum 15 tests frontend (context + components + integration)
- Tests de rollout logic (0%, 50%, 100% scenarios)
- Tests permissions (admin vs user)
- Tests cache invalidation

**Test Pattern** (référence: pytest + vitest):
```python
# Backend: pytest + factory-boy
def test_is_enabled_returns_true_when_flag_enabled(feature_flag_service):
    assert feature_flag_service.is_enabled('new_feature') is True

def test_rollout_percent_50_half_users_enabled(feature_flag_service):
    enabled_count = sum(
        feature_flag_service.get_rollout_status('gradual_rollout', f'user_{i}')
        for i in range(100)
    )
    assert 40 <= enabled_count <= 60  # ~50% ±10%
```

```typescript
// Frontend: vitest + React Testing Library
test('FeatureGuard renders children when flag enabled', () => {
  render(
    <FeatureFlagProvider initialFlags={{ new_ui: true }}>
      <FeatureGuard flag="new_ui">
        <div>New UI</div>
      </FeatureGuard>
    </FeatureFlagProvider>
  );
  expect(screen.getByText('New UI')).toBeInTheDocument();
});
```

### Previous Story Intelligence

**Story 17.11 - Rate Limiting** (pattern de référence):
- Configuration via env vars (`THROTTLE_*_RATE`, `RATELIMIT_ENABLED`)
- Cache-based implementation (LocMemCache)
- DRF throttle classes avec configuration dynamique
- Emergency bypass via env var (`RATELIMIT_ENABLED=false`)
- Structured logging: `rate_limit_exceeded`, `rate_limit_config_validated`

**Patterns à réutiliser**:
1. **Startup validation pattern**: `validate_rate_limit_config()` → `validate_feature_flags_config()`
2. **Cache key pattern**: `ratelimit:{scope}:{ident}` → `feature_flag:{flag_key}`
3. **Emergency toggle**: `RATELIMIT_ENABLED` → `FEATURE_FLAGS_ENABLED`
4. **Logging pattern**: Structured events avec correlation_id
5. **Test coverage**: 29 unit tests + 8 security tests = 37 total

**Story 17.5 - Secret Management** (validation pattern):
- Fail-fast au startup si configuration invalide
- Warnings en development, errors en production
- Validation via `core/startup_checks.py`
- Forbidden defaults detection

**Story 17.10 - Docker** (déploiement):
- Variables d'environnement via `.env` ou volume mount
- Healthcheck includes configuration validation
- Multi-stage build avec secrets protection

### Git Intelligence Summary

**Recent Commits** (derniers 10 commits Epic 17):
1. `c92169f` - Rate limiting (Story 17.11) → **Pattern de référence direct**
2. `d0d3deb` - Docker (Story 17.10) → Configuration conteneurisée
3. `edb4541` - Mypy (Story 17.9) → Type safety requirements
4. `feada9c` - Lockfile (Story 17.8) → Dependency management
5. `b7975dc` - Logging (Story 17.7) → Structured JSON logging pattern
6. `ca4a9c7` - Exceptions (Story 17.6) → Error handling pattern
7. `6d13795` - Secrets (Story 17.5) → Validation fail-fast pattern

**Patterns établis**:
- ✅ Cache-based services (rate limiting → feature flags)
- ✅ Startup validation fail-fast
- ✅ Structured logging JSON
- ✅ Environment-based configuration
- ✅ Type safety (mypy, TypeScript)
- ✅ Test coverage minimum 20+ tests

### Project Structure Notes

**Configuration Centralisée**:
- Backend: `django_backend/idp_backend/settings.py` (ligne 14-21: dotenv loading)
- Frontend: `frontend/.env.development`, `.env.production`
- Secrets: `.env.production.template` avec placeholders `CHANGE_*`

**Middleware Stack** (pas de modification requise):
```python
MIDDLEWARE = [
    'core.middleware.CorrelationIdMiddleware',           # Déjà en place
    'core.middleware.RequestResponseLoggingMiddleware',  # Déjà en place
    'core.middleware.RateLimitHeadersMiddleware',        # Story 17.11
    # Feature flags = service-level, pas de middleware
]
```

**Cache Configuration** (déjà configuré):
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'idp-cache',  # Partagé avec rate limiting
    }
}
```

### Latest Tech Information

**Feature Flag Libraries** (web research - February 2026):

**Python/Django Options**:
1. **django-waffle** 4.1.0 (lightweight, mature)
   - Database-backed flags avec cache
   - Context-aware evaluation (user, groups, percentages)
   - Admin UI intégré
   - **Cons**: Overhead pour simple use cases

2. **Custom Implementation** (RECOMMANDÉ pour MVP)
   - Zero dependencies
   - Control total sur cache strategy
   - Aligné avec patterns existants (rate limiting)
   - Upgrade path vers Waffle si besoin UI admin complexe

**React/Frontend Options**:
1. **Context API** (RECOMMANDÉ)
   - Zero dependencies
   - Simple context + hooks pattern
   - Déjà utilisé (AuthContext, ThemeContext, DashboardContext)

2. **react-feature-flags** (overkill pour notre use case)

**Cache Strategy Best Practices**:
- TTL: 5-10 minutes pour MVP (configurable `FEATURE_FLAGS_CACHE_TTL=300`)
- Invalidation: Explicit après modification (cache.delete)
- Redis upgrade: Pub/sub pour sync multi-instance (out of scope MVP)

**Rollout Percentage Algorithm**:
```python
def is_user_in_rollout(user_id: str, rollout_percent: int) -> bool:
    """Consistent hashing for stable rollout assignment."""
    import hashlib
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return (hash_value % 100) < rollout_percent
```

**Security Considerations** (OWASP, SOC1):
- Audit trail: Log tous toggles de flags (entity_type='FEATURE_FLAG')
- RBAC: Admin only pour modification (IsAdminUser)
- Rate limiting: Appliquer aux endpoints feature-flags (inherit général)
- Validation: Rollout percent 0-100, flag_key format [a-z0-9_-]+

### References

- **Epic 17 Definition**: [Source: `_bmad-output/planning-artifacts/epics.md`, Epic 17, Story 17.12, lignes 3719-3734]
- **Architecture Document**: [Source: `_bmad-output/planning-artifacts/architecture.md`, sections Configuration Management, Cache, Deployment]
- **Story 17.11 - Rate Limiting**: [Source: `_bmad-output/implementation-artifacts/17-11-rate-limiting-endpoints-publics.md`] - Pattern de référence principal
- **Story 17.5 - Secrets**: [Source: `_bmad-output/implementation-artifacts/17-5-securiser-gestion-secrets.md`] - Validation pattern
- **Story 17.10 - Docker**: [Source: `_bmad-output/implementation-artifacts/17-10-dockerfile-backend-frontend.md`] - Déploiement
- **Settings Configuration**: [Source: `django_backend/idp_backend/settings.py`, lignes 14-21, 180-189 (CACHES), 275-285 (REST_FRAMEWORK throttling)]
- **Startup Validation Pattern**: [Source: `django_backend/core/startup_checks.py`, `validate_required_secrets()`, `validate_rate_limit_config()`]
- **Frontend Context Pattern**: [Source: `frontend/src/contexts/AuthContext.tsx`, `ThemeContext.tsx`]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Backend tests: 53/53 pass (`core/tests/test_feature_flags.py`)
- Frontend tests: 17/17 pass (4 service + 6 context + 4 guard + 3 toggle)
- Regression core/tests/: 161 passed, 10 failed (pre-existing health_check.py 301 redirect issues, NOT caused by new code)

### Completion Notes List

- Implémentation custom sans dépendance externe (zéro nouvelle dépendance backend et frontend)
- Service avec double source: `env` (JSON) et `database` (modèle Django)
- Consistent hashing MD5 pour rollout déterministe (flag_key:user_id)
- Cache Django LocMemCache avec TTL configurable (défaut 300s)
- Startup validation fail-fast en production, warnings en dev
- Audit trail SOC1 via AuditLog (FEATURE_FLAG_CREATED, FEATURE_FLAG_UPDATED)
- Frontend auto-refresh toutes les 5 minutes
- Admin UI intégrée dans l'onglet Admin existant (pas de nouvelle page)
- Fixtures pytest locales dans test file (contournement scope conftest.py)

### File List

**Backend - Nouveaux fichiers:**
- `django_backend/core/feature_flags.py` — Service d'évaluation (is_enabled, get_rollout_status, cache, invalidation)
- `django_backend/core/feature_flag_views.py` — API views (List, Status, Update)
- `django_backend/core/migrations/0003_feature_flags.py` — Migration Django
- `django_backend/core/tests/test_feature_flags.py` — 53 tests (modèle, service, API, startup, rollout)

**Backend - Fichiers modifiés:**
- `django_backend/core/models.py` — Ajout FeatureFlag model + AuditActionType/AuditEntityType enums
- `django_backend/core/urls.py` — 3 URL patterns feature-flags
- `django_backend/core/startup_checks.py` — validate_feature_flags_config()
- `django_backend/core/apps.py` — Appel validation au startup
- `django_backend/idp_backend/settings.py` — 4 variables FEATURE_FLAGS_*
- `django_backend/.env.production.template` — Variables d'environnement documentées
- `django_backend/tests/factories.py` — FeatureFlagFactory
- `django_backend/tests/conftest.py` — Import FeatureFlagFactory

**Frontend - Nouveaux fichiers:**
- `frontend/src/services/featureFlagService.ts` — API client (fetchStatus, fetchAll, update)
- `frontend/src/contexts/FeatureFlagContext.tsx` — Provider + hooks (useFeatureFlag, useFeatureFlags)
- `frontend/src/components/FeatureGuard.tsx` — Conditional rendering component
- `frontend/src/components/FeatureToggle.tsx` — A/B testing component
- `frontend/src/components/admin/FeatureFlagsPanel.tsx` — Admin panel (Table, Switch, Slider)
- `frontend/src/services/featureFlagService.test.ts` — 4 tests service
- `frontend/src/contexts/FeatureFlagContext.test.tsx` — 6 tests context
- `frontend/src/components/FeatureGuard.test.tsx` — 4 tests guard
- `frontend/src/components/FeatureToggle.test.tsx` — 3 tests toggle

**Frontend - Fichiers modifiés:**
- `frontend/src/App.tsx` — FeatureFlagProvider ajouté entre AuthProvider et DashboardProvider
- `frontend/src/pages/AdminPage.tsx` — Onglet "Feature Flags" ajouté

**Documentation:**
- `docs/feature-flags.md` — Guide technique complet (backend + frontend + déploiement)
