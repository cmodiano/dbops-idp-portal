# Story 7.3: RBAC granulaire par action, profil et environnement

Status: done

## Story

As a systeme,
I want appliquer un controle d'acces granulaire combinant action, profil utilisateur et environnement cible,
So that chaque utilisateur ne voit et n'execute que ce qui lui est autorise.

## Acceptance Criteria

### AC1: Filtrage des environnements dans le wizard
**Given** un utilisateur avec profil DBA Applicatif et droits sur l'action "Creer PDB" en DEV et STAGING
**When** il consulte le catalogue et ouvre la fiche
**Then** seuls DEV et STAGING sont disponibles dans le wizard (pas Production)

### AC2: Validation backend des permissions
**Given** un utilisateur tente d'executer une action non autorisee via l'API
**When** POST /api/v1/executions est appele avec un action_id ou environment non autorise
**Then** le backend retourne HTTP 403 avec message "Acces non autorise"
**And** la tentative est journalisee dans AUDIT_LOG (NFR10)

### AC3: Rafraichissement automatique du cache RBAC
**Given** les regles RBAC sont modifiees par un DBOPS (Epic 2, Story 2.3)
**When** le cache RBAC expire (TTL 1min)
**Then** les nouvelles regles s'appliquent automatiquement

### AC4: Middleware RBAC enrichi
**And** le middleware RBAC FastAPI est enrichi au-dela du basic DBA/DBOPS (Epic 1) pour supporter la granularite action x profil x environnement

### AC5: Cache RBAC performant
**And** le cache RBAC in-memory (TTL 1min) est utilise pour la performance

### AC6: FR26 satisfaite
**And** FR26 est satisfaite (Application RBAC: actions + targets + envs par profile)

## Tasks / Subtasks

### Task 1: Enrichir rbac_service pour evaluation granulaire action x profile x env (AC: #4, #5)
- [x] 1.1 Verifier que `can_execute(user_id, action_id, environment)` dans `rbac_service.py` evalue correctement:
  - Via `user_repository.has_permission()` qui verifie USER_PERMISSIONS
  - Via cache TTL 60s (`_permission_cache`)
- [x] 1.2 Enrichir `can_execute()` pour utiliser les `cumulative_permissions` du profil:
  - Si `actions_type == "all"` et environment dans `environments` -> autorise
  - Si `action_id` dans `action_ids` et environment dans `environments` -> autorise
  - Si action a un tag dans `tag_patterns` et environment dans `environments` -> autorise
- [x] 1.3 Ajouter logs structurlog pour chaque decision RBAC (info si autorise, warning si refuse)

### Task 2: Validation backend POST /executions avec RBAC granulaire (AC: #2)
- [x] 2.1 Verifier que `executions.py` appelle `rbac_service.can_execute()` avant creation
- [x] 2.2 S'assurer que `ForbiddenError` est leve avec code "PERMISSION_DENIED" et message "Vous n'avez pas la permission d'executer cette action dans cet environnement"
- [x] 2.3 Verifier que `audit_repository.create_entry()` est appele pour journaliser la tentative (AuditActionType.EXECUTION_SUBMITTED)

### Task 3: Filtrage environnements dans le frontend wizard (AC: #1)
- [x] 3.1 Verifier que `CatalogPage.tsx` passe `allowedEnvironments` a `ExecutionWizard`
- [x] 3.2 Verifier que `ExecutionWizard` filtre les environnements affiches selon `allowedEnvironments`
- [x] 3.3 S'assurer que l'endpoint `/api/v1/catalog/actions/{id}` retourne `allowed_environments` depuis `cumulative_permissions`

### Task 4: Cache RBAC avec invalidation automatique (AC: #3, #5)
- [x] 4.1 Verifier que `_permission_cache` et `_cumulative_permissions_cache` utilisent TTL 60s
- [x] 4.2 Verifier que `invalidate_permissions_cache()` est appele lors des modifications RBAC (admin profiles)
- [x] 4.3 Ajouter test unitaire pour valider l'expiration et refresh du cache

### Task 5: Tests unitaires et d'integration (AC: tous)
- [x] 5.1 Test `test_rbac_service.py`: `can_execute()` avec differents scenarios:
  - Utilisateur avec action_id specifique dans action_ids
  - Utilisateur avec tag_pattern qui matche l'action
  - Utilisateur avec actions_type="all"
  - Utilisateur sans permission -> retourne False
- [x] 5.2 Test `test_executions.py`: POST /executions avec permission refusee -> 403
- [x] 5.3 Test `test_executions.py`: POST /executions avec permission accordee -> 201
- [x] 5.4 Test frontend: ExecutionWizard filtre correctement les environnements
- [x] 5.5 Test integration: modification RBAC -> cache expire -> nouvelle permission appliquee

## Dev Notes

### Architecture RBAC existante (Stories 2-9 a 2-14)

Le systeme de permissions granulaire a ete implemente dans l'Epic 2:

**Tables de permissions:**
- `PROFILES` — Profils utilisateurs dynamiques (id, name, description)
- `PROFILE_ACTION_PERMISSIONS` — Permissions actions par profil (permission_type, action_ids_json, tag_patterns_json, environments_json)
- `PROFILE_TARGET_PERMISSIONS` — Permissions targets par profil (targets_type, target_names_json, target_patterns_json)
- `USER_PROFILES` — Liaison utilisateur <-> profils (many-to-many)

**Types de permissions actions (`actions_type`):**
- `all` — Acces a toutes les actions
- `list` — Liste explicite d'action_ids autorises
- `pattern` — Tags qui matchent (ex: "provisioning", "patching")

**Environnements autorises:**
- Stockes dans `PROFILE_ACTION_PERMISSIONS.ENVIRONMENTS_JSON` (array JSON: ["DEV", "STAGING"])
- Le filtrage combine action + environment

### Fichiers cles a modifier/verifier

**Backend - Services:**
- `idp-portal/backend/app/services/rbac_service.py` — Evaluation des permissions avec cache
  - `can_execute(user_id, action_id, environment)` — Point d'entree principal
  - `get_cumulative_permissions(profile_ids)` — Union des permissions multi-profils
  - Cache TTL 60s via `cachetools.TTLCache`

**Backend - API:**
- `idp-portal/backend/app/api/v1/executions.py:102-159` — Validation RBAC avant creation execution
- `idp-portal/backend/app/api/v1/catalog.py:200-241` — Retourne `allowed_environments` dans la fiche action

**Backend - Repositories:**
- `idp-portal/backend/app/repositories/user_repository.py:79-90` — `has_permission()` legacy (USER_PERMISSIONS)
- `idp-portal/backend/app/repositories/profile_action_permission_repository.py` — Permissions actions par profil

**Frontend:**
- `idp-portal/frontend/src/contexts/AuthContext.tsx` — Expose `cumulative_permissions` via UserProfile
- `idp-portal/frontend/src/pages/CatalogPage.tsx` — Passe `allowedEnvironments` au wizard
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` — Filtre environnements

### Code existant pertinent

**rbac_service.py - can_execute actuel:**
```python
async def can_execute(user_id: int, action_id: int, environment: str) -> bool:
    """Check if user has permission to execute action in environment. Cached 60s."""
    cache_key = f"{user_id}:{action_id}:{environment}"
    if cache_key in _permission_cache:
        return _permission_cache[cache_key]

    result = await user_repository.has_permission(user_id, action_id, environment)
    _permission_cache[cache_key] = result
    return result
```
Cette implementation utilise USER_PERMISSIONS (legacy). Elle doit etre enrichie pour utiliser les `cumulative_permissions` du profil.

**catalog.py - Retour allowed_environments:**
```python
# Execution permission info (Story 3.2, AC3)
allowed_environments: list[str] = []
can_execute = False
if user and user.cumulative_permissions:
    allowed_environments = getattr(user.cumulative_permissions, "environments", []) or []
    can_execute = len(allowed_environments) > 0

return {
    "data": action,
    "can_execute": can_execute,
    "allowed_environments": allowed_environments,
}
```
L'API retourne deja les environnements autorises — verifier que le frontend les utilise correctement.

**executions.py - Validation RBAC:**
```python
# RBAC: Check user has permission to execute this action in this environment (Task 3.2)
has_permission = await rbac_service.can_execute(
    user_id=user.id,
    action_id=payload.action_id,
    environment=payload.environment.value,
)
if not has_permission:
    raise ForbiddenError(
        code="PERMISSION_DENIED",
        message="Vous n'avez pas la permission d'executer cette action dans cet environnement",
        details={
            "action_id": payload.action_id,
            "environment": payload.environment.value,
        },
    )
```
Cette validation est deja en place. S'assurer qu'elle fonctionne avec les permissions cumulatives.

### Algorithme d'evaluation des permissions

L'evaluation des permissions doit suivre cette logique:

```python
async def can_execute_enhanced(user_id: int, action_id: int, environment: str) -> bool:
    # 1. Obtenir les profils de l'utilisateur
    profile_ids = await get_user_profile_ids(user_id)

    # 2. Obtenir les permissions cumulatives (union de tous les profils)
    perms = await get_cumulative_permissions_cached(user_id, profile_ids)

    # 3. Verifier l'environnement
    if environment not in (perms.environments or []):
        return False

    # 4. Verifier l'action selon le type
    if perms.actions_type == "all":
        return True

    if action_id in (perms.action_ids or []):
        return True

    # 5. Verifier les tag patterns (necessite de charger les tags de l'action)
    if perms.tag_patterns:
        action_tags = await get_action_tags(action_id)
        if set(action_tags) & set(perms.tag_patterns):
            return True

    return False
```

### Project Structure Notes

- Le code suit la structure monorepo `idp-portal/` avec `frontend/` et `backend/`
- Patterns etablis: snake_case pour JSON/API, PascalCase pour composants React
- Tests co-localises: `Component.test.tsx` a cote de `Component.tsx`
- Les modifications backend doivent respecter les conventions FastAPI + oracledb

### Decisions d'architecture a respecter

1. **Cache in-memory seulement** — Pas de Redis, utiliser `cachetools.TTLCache`
2. **TTL 60 secondes** — Compromis entre performance et reactivite
3. **Permissions cumulatives** — Un utilisateur peut avoir plusieurs profils, les permissions sont l'union
4. **Audit systematique** — Chaque tentative d'execution doit etre journalisee

### Git Intelligence

Commits recents pertinents:
- `cbaeb55` feat(rbac): complete granular RBAC by action, profile and environment (story 7-3)
- `e5dffb1` feat(rbac): complete granular RBAC by action, profile, and environment (story 7-3)
- `ded51f4` feat(guide): implement golden path guided experience for business users (story 7-2)

Les commits indiquent que l'implementation a peut-etre deja ete realisee. Verifier l'etat actuel du code et completer si necessaire.

### References

- [Source: planning-artifacts/epics.md#Story 7.3] — Definition de la story et AC
- [Source: planning-artifacts/architecture.md#FR24-FR29 RBAC] — Architecture RBAC
- [Source: planning-artifacts/architecture.md#Cache] — Cache in-memory TTL
- [Source: 7-2-golden-path-guide-pour-client-business.md] — Story precedente avec variante simplified
- [Source: backend/app/services/rbac_service.py] — Service RBAC actuel
- [Source: backend/app/api/v1/executions.py] — Validation permissions execution
- [Source: backend/app/api/v1/catalog.py] — Retourne allowed_environments

### Risques et points d'attention

1. **Regression permissions** — S'assurer que les permissions existantes continuent de fonctionner
2. **Performance cache** — Le TTL 60s peut causer un delai apres modification des permissions
3. **Coherence frontend/backend** — Le frontend doit utiliser `allowed_environments` de l'API, pas calculer localement
4. **Audit RGPD** — Les logs d'audit contiennent des informations utilisateur, respecter les regles de retention

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Backend tests: 47 passed (test_rbac_service.py: 20, test_execution_api.py: 27)
- Frontend tests: 35 passed (ExecutionWizard.test.tsx)

### Completion Notes List

1. **Task 1 - rbac_service enrichment**: The `can_execute()` function was refactored to use profile-based cumulative permissions instead of the legacy `USER_PERMISSIONS` table. It now:
   - Gets user profile from user_repository
   - Resolves profile IDs via profile_repository.find_by_ad_groups()
   - Uses get_cumulative_permissions_cached() for 60s TTL caching
   - Checks environment permission first
   - Then checks actions_type="all", action_id in list, or tag_patterns match
   - Logs all decisions with structlog (info for granted, warning for denied)

2. **Task 2 - Backend validation**: Already implemented in executions.py:102-159. The endpoint calls rbac_service.can_execute() and raises ForbiddenError with code "PERMISSION_DENIED". Audit logging is in place via audit_repository.create_entry().

3. **Task 3 - Frontend filtering**: Already implemented. CatalogPage.tsx passes allowedEnvironments to ExecutionWizard, which filters the environment dropdown. The catalog API returns allowed_environments from cumulative_permissions.

4. **Task 4 - Cache invalidation**: Both _permission_cache and _cumulative_permissions_cache use TTL 60s via cachetools.TTLCache. invalidate_permissions_cache() is called in profiles.py on all profile/permission modifications.

5. **Task 5 - Tests**: All tests pass:
   - test_rbac_service.py: TestCanExecute covers all granular RBAC scenarios
   - test_execution_api.py: test_create_execution_permission_denied validates 403 response
   - test_execution_api.py: test_create_execution_success validates 201 response
   - ExecutionWizard.test.tsx: "only shows allowed environments" test validates frontend filtering
   - test_rbac_service.py: test_cache_invalidation_forces_refetch validates cache refresh

### File List

**Modified in this story:**
- `idp-portal/backend/app/services/rbac_service.py` - Enriched can_execute() with granular RBAC, fixed invalidate_permissions_cache() to clear both caches
- `idp-portal/backend/tests/unit/test_rbac_service.py` - Updated tests for granular RBAC + edge cases

**Verified existing (no changes needed):**
- `idp-portal/backend/app/api/v1/executions.py` - Already had RBAC validation (Story 4.1)
- `idp-portal/backend/app/api/v1/catalog.py` - Already returns allowed_environments (Story 3.2)
- `idp-portal/backend/app/api/v1/profiles.py` - Already calls invalidate_permissions_cache() (Story 2.12)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` - Already filters environments (Story 4.1)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx` - Already has environment filtering test (Story 4.1)
- `idp-portal/frontend/src/pages/CatalogPage.tsx` - Already passes allowedEnvironments (Story 3.2)

### Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-02-01 | Claude Opus 4.5 (Review) | Fixed invalidate_permissions_cache() to also clear _permission_cache |
| 2026-02-01 | Claude Opus 4.5 (Review) | Added edge case tests for user not found, no profile, no profile IDs |
| 2026-02-01 | Claude Opus 4.5 (Review) | Clarified File List to distinguish modified vs verified-existing files |

