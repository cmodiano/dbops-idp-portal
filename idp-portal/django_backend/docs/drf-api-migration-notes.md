# Migration Notes: FastAPI → Django REST Framework

> **📦 Document d'archivage — Migration terminée**  
> Ce document est conservé pour référence historique. La migration FastAPI→Django est complète (février 2026).  
> Voir [MIGRATION_ARCHIVE.md](../../docs/MIGRATION_ARCHIVE.md) pour accéder au code FastAPI archivé.

**Story:** M.4, M.5, M.7, M.8 - API REST — endpoints catalogue, admin (actions, tags), profils, auth, observabilité
**Date:** 2026-02-03, 2026-02-04, 2026-02-05
**Status:** Migration terminée — Document historique conservé

## Vue d'ensemble

Cette migration implémente les endpoints DRF pour remplacer les endpoints FastAPI suivants:
- `/api/v1/admin/actions/*` - Administration des actions (M.4)
- `/api/v1/catalog/actions/*` - Catalogue public des actions (M.4)
- `/api/v1/tags` - Liste des tags (M.4)
- `/api/v1/catalog/tags` - Tags avec comptage d'actions (M.4)
- `/api/v1/admin/profiles/*` - Administration des profils et permissions (M.5)
- `/api/v1/auth/*` - Authentification SAML/JWT (M.7)

## Mapping des endpoints

### Admin Actions

| FastAPI Endpoint | DRF Endpoint | Méthode | Status |
|-----------------|--------------|---------|--------|
| POST `/api/v1/admin/actions` | POST `/api/v1/admin/actions/` | create | ✅ |
| GET `/api/v1/admin/actions` | GET `/api/v1/admin/actions/` | list | ✅ |
| GET `/api/v1/admin/actions/{id}` | GET `/api/v1/admin/actions/{id}/` | retrieve | ✅ |
| PUT `/api/v1/admin/actions/{id}` | PUT `/api/v1/admin/actions/{id}/` | update | ✅ |
| PUT `/api/v1/admin/actions/{id}/tags` | PUT `/api/v1/admin/actions/{id}/tags/` | update_tags | ✅ |
| PATCH `/api/v1/admin/actions/{id}/status` | PATCH `/api/v1/admin/actions/{id}/status/` | update_status | ✅ |
| PUT `/api/v1/admin/actions/{id}/execution-steps` | PUT `/api/v1/admin/actions/{id}/execution-steps/` | update_execution_steps | ✅ |
| GET `/api/v1/admin/actions/eligible-for-workflow` | GET `/api/v1/admin/actions/eligible-for-workflow/` | list_eligible_for_workflow | ✅ |

### Catalog Actions

| FastAPI Endpoint | DRF Endpoint | Méthode | Status |
|-----------------|--------------|---------|--------|
| GET `/api/v1/catalog/actions` | GET `/api/v1/catalog/actions/` | list | ✅ |
| GET `/api/v1/catalog/actions/{id}` | GET `/api/v1/catalog/actions/{id}/` | retrieve | ✅ |
| GET `/api/v1/catalog/actions/{id}/stats` | GET `/api/v1/catalog/actions/{id}/stats/` | get_stats | ✅ |

### Tags

| FastAPI Endpoint | DRF Endpoint | Méthode | Status |
|-----------------|--------------|---------|--------|
| GET `/api/v1/tags` | GET `/api/v1/tags/` | list | ✅ |
| GET `/api/v1/catalog/tags` | GET `/api/v1/catalog/tags` | list_catalog_tags | ✅ |

### Admin Profiles (Story M.5)

| FastAPI Endpoint | DRF Endpoint | Méthode | Status |
|-----------------|--------------|---------|--------|
| GET `/api/v1/admin/profiles` | GET `/api/v1/admin/profiles/` | list | ✅ |
| POST `/api/v1/admin/profiles` | POST `/api/v1/admin/profiles/` | create | ✅ |
| GET `/api/v1/admin/profiles/{id}` | GET `/api/v1/admin/profiles/{id}/` | retrieve | ✅ |
| PUT `/api/v1/admin/profiles/{id}` | PUT `/api/v1/admin/profiles/{id}/` | update | ✅ |
| DELETE `/api/v1/admin/profiles/{id}` | DELETE `/api/v1/admin/profiles/{id}/` | destroy | ✅ |
| GET `/api/v1/admin/profiles/{id}/actions` | GET `/api/v1/admin/profiles/{id}/actions/` | actions (GET) | ✅ |
| PUT `/api/v1/admin/profiles/{id}/actions` | PUT `/api/v1/admin/profiles/{id}/actions/` | actions (PUT) | ✅ |
| GET `/api/v1/admin/profiles/{id}/targets` | GET `/api/v1/admin/profiles/{id}/targets/` | targets (GET) | ✅ |
| PUT `/api/v1/admin/profiles/{id}/targets` | PUT `/api/v1/admin/profiles/{id}/targets/` | targets (PUT) | ✅ |
| GET `/api/v1/admin/profiles/export` | GET `/api/v1/admin/profiles/export/` | export | ✅ |
| POST `/api/v1/admin/profiles/import` | POST `/api/v1/admin/profiles/import/` | import | ✅ |

### Auth Endpoints (Story M.7)

| FastAPI Endpoint | DRF Endpoint | Méthode | Status |
|-----------------|--------------|---------|--------|
| GET `/api/v1/auth/saml/login` | GET `/api/v1/auth/saml/login` | saml_login | ✅ |
| POST `/api/v1/auth/saml/callback` | POST `/api/v1/auth/saml/callback` | saml_callback | ✅ |
| GET `/api/v1/auth/me` | GET `/api/v1/auth/me` | current_user | ✅ |
| POST `/api/v1/auth/refresh` | POST `/api/v1/auth/refresh` | refresh_token | ✅ |
| POST `/api/v1/auth/logout` | POST `/api/v1/auth/logout` | logout | ✅ |

## Format de réponse

### Format de succès

Les réponses DRF utilisent le même format que FastAPI:

```json
{
  "data": {...}  // ou [...]
}
```

### Format de pagination

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total": 100,
    "total_pages": 4
  }
}
```

### Format d'erreur

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Action non trouvée",
    "details": {"action_id": 123}
  }
}
```

## Différences de comportement

### 1. URLs avec trailing slash

**FastAPI:** `/api/v1/admin/actions`  
**DRF:** `/api/v1/admin/actions/` (avec trailing slash)

**Impact:** Les clients doivent ajouter le trailing slash ou utiliser la redirection automatique de Django.

**Solution:** DRF redirige automatiquement les URLs sans trailing slash vers celles avec trailing slash.

### 2. Permissions

**FastAPI:** Utilise `require_profile("dbops")` et `get_optional_user()`  
**DRF:** Utilise `DBOPSProfilePermission` et `OptionalUserPermission`

**Différence:** La vérification du profil dans `DBOPSProfilePermission` utilise actuellement `is_staff` comme fallback. La vérification réelle du profil nécessitera l'intégration avec le système d'authentification Django (Story M.7).

**Impact:** Temporaire - sera corrigé lors de la migration de l'authentification.

### 3. RBAC Filtering

**FastAPI:** Utilise `cumulative_permissions` directement depuis `UserProfile`  
**DRF:** Utilise `ProfileService.get_cumulative_permissions()` qui nécessite `ad_groups`

**Différence:** Le modèle User Django doit avoir un attribut/méthode `ad_groups` pour que le RBAC fonctionne correctement.

**Impact:** Nécessite vérification de la structure du modèle User.

### 4. Cache

**FastAPI:** Cache TTLCache avec clé incluant tous les paramètres  
**DRF:** Cache TTLCache identique, même logique de clé

**Impact:** Aucun - comportement identique.

### 5. Filtrage par environnement

**FastAPI:** Filtre dans `impact_rules` JSON via requête SQL  
**DRF:** Non implémenté (TODO dans le code)

**Impact:** Le filtre `?environment=PROD` ne fonctionne pas encore en DRF.

**Solution:** Implémenter le filtrage JSON pour `impact_rules` dans Django ORM.

### 6. Import/Export YAML Profiles (M.5)

**FastAPI:** Utilise `profile_export_import_service` avec validation Pydantic  
**DRF:** Utilise `services_export_import.py` avec validation manuelle équivalente

**Différence:** La validation YAML est implémentée manuellement au lieu d'utiliser Pydantic, mais le comportement est identique.

**Impact:** Aucun - format YAML identique, validation équivalente.

### 7. Invalidation cache RBAC (M.5)

**FastAPI:** Utilise `rbac_service.invalidate_permissions_cache()`  
**DRF:** Utilise fonction placeholder `invalidate_permissions_cache()` (à implémenter lors de la migration du service RBAC)

**Différence:** Le cache RBAC n'est pas encore migré vers Django, donc l'invalidation est un placeholder.

**Impact:** Temporaire - sera corrigé lors de la migration du service RBAC (Story M.8 ou future).

## Régressions connues

### 1. Filtrage par environnement non implémenté

**Endpoint:** GET `/api/v1/catalog/actions?environment=PROD`  
**Status:** Non fonctionnel  
**Workaround:** Utiliser FastAPI endpoint temporairement

### 2. Tag list_catalog_tags sans action_count

**Endpoint:** GET `/api/v1/catalog/tags`  
**Status:** Retourne les tags mais sans `action_count`  
**Workaround:** Calculer côté client ou utiliser FastAPI endpoint

### 3. ExecutionService.get_action_stats() non disponible

**Endpoint:** GET `/api/v1/catalog/actions/{id}/stats`  
**Status:** Utilise un calcul simplifié au lieu de `ExecutionService.get_action_stats()`  
**Impact:** Les stats peuvent différer légèrement de FastAPI

**Solution:** Créer `ExecutionService.get_action_stats(action_id)` ou ajouter paramètre `action_id` à `get_stats()`.

## Tests

### Tests créés

- `test_admin_views.py` - Tests pour endpoints admin (create, list, retrieve, update, update_tags, update_status)
- `test_catalog_views.py` - Tests pour endpoints catalog (list, retrieve, get_stats)
- `test_tags_views.py` - Tests pour endpoints tags (list, list_catalog_tags)
- `profiles/tests/test_profile_views.py` - Tests CRUD profiles (M.5)
- `profiles/tests/test_permissions_views.py` - Tests permissions actions/targets (M.5)
- `profiles/tests/test_import_export_views.py` - Tests import/export YAML (M.5)

### Couverture

- ✅ Permissions (401, 403)
- ✅ Codes HTTP (200, 201, 400, 404)
- ✅ Format de réponse (enveloppe data, pagination)
- ✅ Filtres de base (status, engine, tags, q)
- ⚠️ RBAC filtering (nécessite setup de profils/permissions)
- ⚠️ Cache (tests basiques)

## Checklist de validation frontend

Pour valider que le frontend fonctionne avec les endpoints DRF:

- [ ] Liste des actions admin (`/admin/actions`) - pagination, filtres
- [ ] Création d'action (`POST /admin/actions`)
- [ ] Édition d'action (`PUT /admin/actions/{id}`)
- [ ] Mise à jour des tags (`PUT /admin/actions/{id}/tags`)
- [ ] Changement de statut (`PATCH /admin/actions/{id}/status`)
- [ ] Liste du catalogue (`/catalog/actions`) - filtres, RBAC
- [ ] Détail d'action (`/catalog/actions/{id}`) - can_execute, allowed_environments
- [ ] Stats d'action (`/catalog/actions/{id}/stats`)
- [ ] Liste des tags (`/tags`)
- [ ] Tags du catalogue (`/catalog/tags`)
- [ ] Liste des profils (`/admin/profiles`)
- [ ] Création/édition de profil (`POST/PUT /admin/profiles/{id}`)
- [ ] Gestion des permissions actions (`GET/PUT /admin/profiles/{id}/actions`)
- [ ] Gestion des permissions targets (`GET/PUT /admin/profiles/{id}/targets`)
- [ ] Export/import YAML (`GET/POST /admin/profiles/export|import`)

## Prochaines étapes

1. **Story M.7:** Migration de l'authentification SAML/JWT vers Django
   - Implémenter vérification réelle du profil dans `DBOPSProfilePermission`
   - Intégrer `ad_groups` dans le modèle User

2. **Story M.8:** Migration middleware logging et observabilité
   - Implémenter service RBAC Django avec cache
   - Implémenter `invalidate_permissions_cache()` réel

3. **Améliorations:** 
   - Implémenter filtrage par environnement dans `impact_rules`
   - Ajouter `action_count` à `list_catalog_tags()`
   - Créer `ExecutionService.get_action_stats(action_id)`

4. **Tests:**
   - Exécuter tests profiles avec environnement Django configuré
   - Ajouter tests RBAC avec profils/permissions réels
   - Ajouter tests de cache plus complets
   - Ajouter tests de parité contractuelle avec FastAPI (comparaison JSON)

4. **Documentation:**
   - Mettre à jour la documentation API
   - Créer guide de migration pour le frontend

## Fichiers modifiés

### Nouveaux fichiers
- `core/pagination.py` - CustomPageNumberPagination
- `core/permissions.py` - DBOPSProfilePermission, OptionalUserPermission
- `core/exceptions.py` - Custom exceptions et exception handler
- `catalog/serializers.py` - Tous les serializers DRF
- `catalog/views.py` - ViewSets pour admin, catalog, tags
- `catalog/tests/test_admin_views.py` - Tests admin
- `catalog/tests/test_catalog_views.py` - Tests catalog
- `catalog/tests/test_tags_views.py` - Tests tags
- `profiles/serializers.py` - Serializers DRF pour profiles et permissions (M.5)
- `profiles/views.py` - ViewSet et APIViews pour profiles (M.5)
- `profiles/urls.py` - Configuration URLs profiles (M.5)
- `profiles/services_export_import.py` - Service import/export YAML (M.5)
- `profiles/tests/test_profile_views.py` - Tests CRUD profiles (M.5)
- `profiles/tests/test_permissions_views.py` - Tests permissions (M.5)
- `profiles/tests/test_import_export_views.py` - Tests import/export YAML (M.5)
- `docs/drf-api-migration-notes.md` - Cette documentation

### Fichiers modifiés
- `catalog/models.py` - Ajout `default_impact_level`, `normalize_tag_name()`
- `catalog/services.py` - Support `default_impact_level`
- `catalog/urls.py` - Configuration DRF routers
- `idp_backend/urls.py` - Inclusion catalog.urls et profiles.urls
- `idp_backend/settings.py` - Configuration pagination et exception handler
- `profiles/services.py` - Ajout méthode `get_by_name()` pour import YAML
- `requirements.txt` - Ajout PyYAML>=6.0.0

## Story M.8 - Observabilité et Logging

### Logging structuré JSON

**FastAPI:** Utilise `structlog` avec processors JSON
**DRF:** Utilise `structlog` avec la même configuration

**Parité:** Le format de log est identique pour permettre l'analyse unifiée dans Splunk.

Format commun:
```json
{
  "timestamp": "2026-02-05T14:30:05.123Z",
  "level": "info",
  "event": "request_completed",
  "correlation_id": "uuid",
  "user_id": "42",
  "path": "/api/v1/catalog/actions",
  "status_code": 200,
  "duration_ms": 45
}
```

### Correlation ID

**FastAPI:** Header `X-Idp-Request-Id` via `CorrelationIdMiddleware`, bind dans `structlog.contextvars`
**DRF:** Header `X-Idp-Request-Id` via `CorrelationIdMiddleware`, bind dans `structlog.contextvars` + thread-local

**Différence:** Django utilise thread-local en plus de contextvars pour compatibilité avec le code synchrone.

### Health Check étendu

**FastAPI:** Vérifie Oracle + Vault + ServiceNow
**DRF:** Vérifie Oracle + Vault + ServiceNow

**Parité:** Format de réponse identique:
```json
{
  "data": {
    "status": "healthy|degraded",
    "timestamp": "ISO8601Z",
    "oracle": "connected|disconnected",
    "vault": "reachable|unreachable",
    "servicenow": "reachable|unreachable"
  }
}
```

### Request/Response Logging

**FastAPI:** `RequestLoggingMiddleware` avec `request_completed`
**DRF:** `RequestResponseLoggingMiddleware` avec `request_received` + `request_completed` + `request_failed`

**Différence:** Django log 3 événements au lieu de 1:
- `request_received`: Quand la requête entre
- `request_completed`: Quand la réponse sort (niveau selon status_code)
- `request_failed`: En cas d'exception non gérée

### Exception Handling

**FastAPI:** Utilise `ExceptionHandler` avec logging structuré
**DRF:** Utilise `custom_exception_handler` avec logging structuré

**Parité:**
- Même format d'erreur: `{"error": {"code": "...", "message": "...", "details": {...}}}`
- Logging des exceptions avec contexte complet
- Masquage des détails internes pour les 500

### CORS

**FastAPI:** Configuration via `CORSMiddleware`
**DRF:** Configuration via `django-cors-headers`

**Parité:** Mêmes origines autorisées, `credentials=true`, header `X-Idp-Request-Id` exposé.

### Fichiers créés (M.8)

- `core/logging.py` - Configuration structlog
- `core/middleware.py` - RequestResponseLoggingMiddleware ajouté
- `core/views.py` - Health check étendu
- `core/exceptions.py` - Logging des exceptions
- `core/tests/test_middleware.py` - Tests middleware
- `core/tests/test_health_check.py` - Tests health check
- `docs/observability-architecture.md` - Architecture observabilité
- `docs/observability-runbook.md` - Runbook monitoring
- `docs/logging-conventions.md` - Conventions de logging

## Notes techniques

### Serializers

Les serializers DRF gèrent automatiquement:
- Champs CLOB/JSON via méthodes helper `get_*()` et `set_*()` des modèles
- Relations (tags via ActionTag, created_by via User)
- Champs calculés (execution_count via annotation)

### ViewSets

Les ViewSets utilisent:
- `CatalogService` pour toute la logique métier (pas d'accès direct aux modèles)
- `@transaction.atomic` pour atomicité (déjà dans les services)
- `AuditService` pour audit automatique (déjà dans les services)

### Performance

- Utilisation de `select_related()` et `prefetch_related()` pour éviter N+1 queries
- Cache TTLCache pour catalog list (5 min TTL)
- Annotations pour execution_count (pas de requêtes séparées)
