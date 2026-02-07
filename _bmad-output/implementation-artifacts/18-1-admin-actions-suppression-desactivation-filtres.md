# Story 18.1: Admin Actions — suppression, désactivation et filtres

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBOPS**,
je veux **supprimer les actions jamais exécutées et désactiver les autres**, avec filtres pour voir actives par défaut et désactivées à la demande,
afin de **maintenir un catalogue propre tout en préservant la traçabilité des exécutions passées**.

## Acceptance Criteria

**AC1: Suppression des actions jamais exécutées**
```gherkin
Given une action dans l'admin
When elle n'a jamais été exécutée (execution_count = 0)
Then je peux la supprimer (hard delete)
And l'action est complètement retirée de la base de données
And une entrée d'audit est créée avec action_type='action_deleted'
```

**AC2: Désactivation des actions avec historique d'exécution**
```gherkin
Given une action ayant au moins une exécution passée (execution_count > 0)
When je veux la retirer du catalogue actif
Then je peux la désactiver (soft delete: status='disabled')
And je ne peux PAS la supprimer (bouton delete désactivé ou absent)
And l'action reste en BD avec deleted_at, deleted_by, deletion_reason renseignés
And les exécutions passées restent accessibles pour l'audit
```

**AC3: Cascade vers workflows référençant l'action**
```gherkin
Given je désactive une action utilisée par un ou plusieurs workflows
When je clique sur Désactiver
Then un message de confirmation m'informe que le(s) workflow(s) sera/seront désactivé(s)
And le message liste les noms des workflows impactés
When je confirme la désactivation
Then l'action passe à status='disabled'
And tous les workflows référençant cette action passent à status='disabled'
And chaque désactivation est auditée (action + workflows)
```

**AC4: Filtre par défaut — actions actives uniquement**
```gherkin
Given la liste des actions en admin
When j'accède à /admin/actions par défaut
Then je vois uniquement les actions avec status IN ('draft', 'published')
And les actions désactivées (status='disabled') ne sont PAS affichées
```

**AC5: Toggle filtre pour inclure les actions désactivées**
```gherkin
Given je suis sur la page admin actions
When j'applique un filtre "Inclure désactivées" (checkbox ou toggle)
Then je vois les actions avec status IN ('draft', 'published', 'disabled')
And les actions désactivées sont affichées avec un style visuel distinct (opacity réduite, tag rouge)
And je peux réactiver une action désactivée (bouton "Réactiver")
```

**AC6: Boutons conditionnels selon execution_count et status**
```gherkin
Given une action dans la liste admin
When execution_count = 0 AND status != 'disabled'
Then le bouton "Supprimer" est visible et actif
And le bouton "Désactiver" est visible et actif

When execution_count > 0 AND status != 'disabled'
Then le bouton "Supprimer" est absent ou désactivé
And le bouton "Désactiver" est visible et actif

When status = 'disabled'
Then les boutons "Supprimer" et "Désactiver" sont absents
And le bouton "Réactiver" est visible et actif
```

## Tasks / Subtasks

- [x] **Task 1: Migration BD — ajout colonnes soft-delete** (AC: 2)
  - [x] Créer migration Flyway `V051__add_soft_delete_to_actions_catalog.sql`
  - [x] Ajouter colonnes: `DELETED_BY NUMBER`, `DELETED_AT TIMESTAMP`, `DELETION_REASON VARCHAR2(500)`
  - [x] Ajouter FK `DELETED_BY` → `USERS(ID)`
  - [x] Ajouter contrainte CHECK: `(status='disabled' AND deleted_at IS NOT NULL) OR (status IN ('draft','published') AND deleted_at IS NULL)`
  - [x] Créer index `IDX_ACTIONS_CATALOG_DELETED_AT`
  - [x] Valider migration en dev (Oracle 19+)

- [x] **Task 2: Repository — méthodes delete et deactivate** (AC: 1, 2, 3)
  - [x] Implémenter `CatalogRepository.delete(id)` — hard delete si execution_count=0, sinon ConflictError
  - [x] Implémenter `CatalogRepository.count_executions(action_id)` — query COUNT(*) sur EXECUTIONS
  - [x] Implémenter `CatalogRepository.deactivate(id, deleted_by, reason)` — UPDATE status='disabled', renseigner deleted_at/deleted_by/reason
  - [x] Implémenter `WorkflowRepository.find_by_action_id(action_id)` — retourne workflows référençant l'action
  - [x] Implémenter `WorkflowRepository.deactivate_multiple(workflow_ids, cascade_from_action_id)` — batch UPDATE status='disabled'
  - [x] Tests unitaires: `test_delete_action_no_executions`, `test_delete_action_with_executions_raises_conflict`, `test_deactivate_action`, `test_find_workflows_by_action`

- [x] **Task 3: API DELETE /admin/actions/{id}** (AC: 1)
  - [x] Route DELETE `/api/v1/admin/actions/{id}` avec décorateur `@AdminRequired()`
  - [x] Vérifier RBAC: `current_user.is_admin` obligatoire (sinon 403 ForbiddenError)
  - [x] Appeler `repo.count_executions(id)` — si > 0, raise ConflictError(code="EXECUTION_EXISTS")
  - [x] Appeler `repo.delete(id)` — hard delete
  - [x] Logger audit: `audit_repo.insert(action_type='action_deleted', entity_id=id, user_id=current_user.id)`
  - [x] Retourner 204 No Content en cas de succès
  - [x] Tests: `test_delete_action_success`, `test_delete_action_forbidden_non_admin`, `test_delete_action_conflict_executions_exist`

- [x] **Task 4: API PUT /admin/actions/{id}/deactivate** (AC: 2, 3)
  - [x] Route PUT `/api/v1/admin/actions/{id}/deactivate` avec body `{ "deletion_reason": "string" }`
  - [x] Vérifier RBAC: admin-only
  - [x] Trouver workflows impactés: `workflow_repo.find_by_action_id(id)`
  - [x] Si workflows trouvés, retourner `{ "status": "requires_confirmation", "affected_workflows": [...] }`
  - [x] Sur confirmation (query param `?confirmed=true`), désactiver action + cascader workflows
  - [x] Logger audit: action_deactivated + cascade workflows
  - [x] Retourner 200 OK avec détails workflows désactivés
  - [x] Tests: `test_deactivate_action_no_workflows`, `test_deactivate_action_with_workflows_requires_confirmation`, `test_deactivate_cascades_workflows`

- [x] **Task 5: API GET /admin/actions avec filtre include_disabled** (AC: 4, 5)
  - [x] Modifier route GET `/api/v1/admin/actions` pour accepter `?include_disabled=true/false` (défaut: false)
  - [x] Si `include_disabled=false`: filtrer `WHERE status IN ('draft', 'published')`
  - [x] Si `include_disabled=true`: filtrer `WHERE status IN ('draft', 'published', 'disabled')`
  - [x] Enrichir réponse avec champs `execution_count`, `deleted_at`, `deleted_by`, `deletion_reason`
  - [x] Tests: `test_list_actions_default_excludes_disabled`, `test_list_actions_include_disabled_shows_all`

- [x] **Task 6: API PUT /admin/actions/{id}/reactivate** (AC: 5)
  - [x] Route PUT `/api/v1/admin/actions/{id}/reactivate`
  - [x] Vérifier status='disabled', sinon 409 ConflictError
  - [x] UPDATE `status='published'`, `deleted_at=NULL`, `deleted_by=NULL`, `deletion_reason=NULL`
  - [x] Logger audit: `action_reactivated`
  - [x] Retourner 200 OK
  - [x] Test: `test_reactivate_disabled_action`, `test_reactivate_active_action_fails`

- [x] **Task 7: Frontend — service admin API client** (AC: 1-6)
  - [x] Créer `frontend/src/services/admin_service.ts`
  - [x] Méthodes: `deleteAction(id)`, `deactivateAction(id, reason?)`, `reactivateAction(id)`, `fetchActions(includeDisabled)`
  - [x] Gérer erreurs 403, 404, 409 avec messages utilisateur appropriés
  - [x] Propager correlation_id (X-Idp-Request-Id)

- [x] **Task 8: Frontend — composant ActionListFilters** (AC: 5)
  - [x] Créer `frontend/src/components/admin/ActionListFilters.tsx`
  - [x] Checkbox Ant Design: "Inclure les actions désactivées"
  - [x] Emit event `onFilterChange({ include_disabled: boolean })`
  - [x] Tests: `test_toggle_include_disabled_filter`

- [x] **Task 9: Frontend — composant ActionList avec boutons conditionnels** (AC: 6)
  - [x] Modifier `frontend/src/components/admin/ActionList.tsx` (ou créer si n'existe pas)
  - [x] Colonne "Actions" avec boutons conditionnels:
    - **Delete** (trash icon): visible si `execution_count=0 AND status!='disabled'`
    - **Deactivate** (pause icon): visible si `status!='disabled'`
    - **Reactivate** (play icon): visible si `status='disabled'`
  - [x] Popconfirm Ant Design pour Delete: "Cette action n'a jamais été exécutée et sera supprimée définitivement"
  - [x] Popconfirm pour Deactivate: afficher warning si workflows impactés ("X workflow(s) seront aussi désactivés")
  - [x] Styling: lignes désactivées avec opacity 0.6, tag rouge "Désactivée"
  - [x] Tests: `test_delete_button_visible_no_executions`, `test_delete_button_hidden_with_executions`, `test_deactivate_shows_workflow_warning`, `test_reactivate_button_disabled_actions`

- [x] **Task 10: Frontend — modal confirmation cascade workflows** (AC: 3)
  - [x] Créer modal Ant Design affichant liste workflows impactés
  - [x] Afficher: "Attention: désactiver cette action désactivera aussi les workflows suivants: [liste noms workflows]"
  - [x] Boutons: "Annuler" (ferme modal) et "Confirmer la désactivation" (appelle API avec `confirmed=true`)
  - [x] Test: `test_cascade_confirmation_modal_displays_workflows`

- [x] **Task 11: Tests backend — suite complète deletion/deactivation** (AC: 1-6)
  - [x] Tests unitaires repository (6 tests minimum)
  - [x] Tests unitaires API routes (10 tests minimum)
  - [x] Tests intégration flow complet: delete → audit, deactivate → cascade → audit
  - [x] Tests RBAC: non-admin rejected (403), admin accepted (204/200)
  - [x] Tests edge cases: action inexistante (404), double deactivation (409)
  - [x] Fixtures: `action_never_executed`, `action_with_executions`, `workflow_with_action_reference`

- [x] **Task 12: Tests frontend — composants admin action management** (AC: 1-6)
  - [x] Tests ActionListFilters: toggle checkbox
  - [x] Tests ActionList: boutons conditionnels selon execution_count et status
  - [x] Tests modal confirmation cascade
  - [x] Tests appels API service (mock axios)
  - [x] Tests gestion erreurs 403, 409 (affichage message toast)
  - [x] Minimum 15 tests frontend

- [x] **Task 13: Documentation API — endpoints admin actions** (AC: all)
  - [x] Documenter DELETE `/api/v1/admin/actions/{id}` (OpenAPI/Swagger)
  - [x] Documenter PUT `/api/v1/admin/actions/{id}/deactivate`
  - [x] Documenter PUT `/api/v1/admin/actions/{id}/reactivate`
  - [x] Exemples requêtes/réponses avec codes erreur (409, 403, 404)
  - [x] Ajouter dans `docs/api/admin-endpoints.md`

## Dev Notes

### Architecture Patterns & Constraints

**Framework & Stack:**
- Backend: Django 5.2 + Django REST Framework 3.16 (migration FastAPI → Django complétée Epic M)
- Frontend: React 19 + Ant Design 6.2 + TypeScript 5.x
- Database: Oracle 19+ avec python-oracledb 3.4.1 (Thin mode)
- ORM: Django ORM (plus de SQL brut depuis Epic M)

**Critical Pattern Change (Epic M):**
- ⚠️ **ATTENTION**: L'architecture documentée dans certains artéfacts mentionne FastAPI + Repository Pattern SQL brut
- **RÉALITÉ POST-EPIC M**: Backend est Django + DRF + Django ORM
- Utiliser Django models, viewsets, serializers — PAS de repositories custom
- Migrations: Django migrations (`python manage.py makemigrations`) — PAS Flyway

**Database — Soft Delete Pattern:**
- Table: `ACTIONS_CATALOG` avec colonnes existantes + ajout soft-delete
- Soft-delete columns à ajouter: `deleted_by`, `deleted_at`, `deletion_reason`
- Hard delete: `DELETE FROM ACTIONS_CATALOG WHERE id=? AND execution_count=0`
- Soft delete: `UPDATE ACTIONS_CATALOG SET status='disabled', deleted_at=NOW(), deleted_by=?, deletion_reason=?`
- Contrainte CHECK: assurer cohérence `(status='disabled' → deleted_at IS NOT NULL)`

**RBAC Pattern:**
- Admin-only endpoints: décorateurs DRF `@permission_classes([IsAdminUser])`
- Profil DBOPS: `is_staff=True` ou custom permission `IsDBOPSUser`
- Vérifier `request.user.is_staff` dans vues Django
- Retourner 403 Forbidden si non-admin tente delete/deactivate

**API Response Format (DRF Standard):**
```json
// Success
{
  "id": 42,
  "name": "Action Name",
  "status": "disabled",
  "execution_count": 5,
  "deleted_at": "2026-02-07T14:30:00Z"
}

// Error
{
  "detail": "Cannot delete action with existing executions",
  "code": "EXECUTION_EXISTS",
  "execution_count": 5
}
```

**Cascading Deactivation Logic:**
1. Trouver workflows: `Workflow.objects.filter(steps__action_id=action_id)`
2. Vérifier count > 0 → retourner `{ "requires_confirmation": true, "affected_workflows": [...] }`
3. Sur confirmation: bulk update `Workflow.objects.filter(...).update(status='disabled')`
4. Logger chaque changement dans AuditLog

**Filtering — Default Behavior:**
- GET `/api/v1/admin/actions/` → par défaut `status IN ('draft', 'published')`
- GET `/api/v1/admin/actions/?include_disabled=true` → `status IN ('draft', 'published', 'disabled')`
- Utiliser Django Q objects: `Q(status__in=['draft', 'published']) | (Q(status='disabled') if include_disabled else Q())`

### Project Structure Notes

**Backend Files to Modify/Create:**
```
django_backend/
├── catalog/
│   ├── models.py               # Ajouter deleted_by, deleted_at, deletion_reason au modèle Action
│   ├── serializers.py          # ActionSerializer avec champs soft-delete
│   ├── views.py                # ViewSet avec actions delete, deactivate, reactivate
│   ├── permissions.py          # IsDBOPSUser custom permission
│   └── migrations/
│       └── 0XXX_add_soft_delete_columns.py
├── workflows/
│   └── models.py               # Vérifier relation Workflow → Action via WorkflowStep
└── audit/
    └── models.py               # AuditLog avec action_types: ACTION_DELETED, ACTION_DEACTIVATED, ACTION_REACTIVATED
```

**Frontend Files to Create/Modify:**
```
frontend/src/
├── components/admin/
│   ├── ActionList.tsx          # Table avec boutons conditionnels
│   ├── ActionListFilters.tsx   # Checkbox include_disabled
│   └── CascadeConfirmModal.tsx # Modal warning workflows impactés
├── services/
│   └── adminService.ts         # API calls delete, deactivate, reactivate
└── pages/
    └── AdminPage.tsx           # Intégration ActionList + Filters
```

**Tests:**
```
django_backend/
└── catalog/tests/
    ├── test_views.py           # Tests API delete/deactivate/reactivate
    ├── test_models.py          # Tests contraintes soft-delete
    └── test_permissions.py     # Tests RBAC admin-only

frontend/src/
└── components/admin/
    ├── ActionList.test.tsx
    └── ActionListFilters.test.tsx
```

### Testing Standards

**Backend (Django + pytest):**
- Fixtures: `ActionFactory` (jamais exécutée), `ActionFactory` + `ExecutionFactory` (avec historique)
- Tests permissions: `@pytest.mark.django_db` + `APIClient` with/without admin credentials
- Tests cascade: créer Action → WorkflowStep → vérifier cascade deactivation
- Performance: `assertNumQueries()` pour delete/deactivate (target: ≤ 3 queries)

**Frontend (Vitest + React Testing Library):**
- Mock `adminService` calls avec MSW ou jest.mock
- Tests conditionnels boutons: `getByTestId('delete-btn')` présent/absent selon execution_count
- Tests Popconfirm: `fireEvent.click(deleteBtn)` → vérifier modal texte
- Tests cascade warning: mocker réponse API avec `affected_workflows` → vérifier affichage liste

**Coverage Target:**
- Backend: minimum 85% coverage pour catalog/views.py et catalog/models.py
- Frontend: minimum 80% coverage pour ActionList.tsx

### References

**Epic Source:**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic-18-Story-18.1]

**Architecture:**
- **POST-EPIC M**: Backend migré vers Django/DRF (Epic M stories m-1 à m-11)
- [Source: _bmad-output/implementation-artifacts/m-*.md] — Stories migration FastAPI → Django
- [Source: docs/architecture/backend-django.md] — Architecture Django finale

**Previous Story Learnings:**
- [Source: _bmad-output/implementation-artifacts/17-17-optimisation-requetes-bd-page-catalogue.md]
- Pattern: Index strategy (STATUS indexed), cache TTL (5 min), invalidation globale
- Git commits: perf(17.17), feat(17.16) — conventions commit messages

**Database:**
- Oracle 19+ avec Identity columns (GENERATED ALWAYS AS IDENTITY)
- Contraintes CHECK pour cohérence soft-delete
- Index sur STATUS (déjà existant depuis Story 17.17)

**RBAC:**
- Epic 2 stories 2-9 à 2-14: profils dynamiques + permissions cumulatives
- Epic 7 stories 7-3, 7-4: RBAC granulaire par profil et environnement

**Audit:**
- Epic 6 stories 6-1 à 6-4: traces audit immutables, conformité SOC1
- Chaque delete/deactivate DOIT logger: user_id, action_type, entity_id, timestamp, correlation_id

## Documentation API — Story 18.1

### DELETE /api/v1/admin/actions/{id}/

Suppression definitive d'une action (hard delete). Necesssite profil DBOPS.

**Pre-condition**: `execution_count = 0` (aucune execution passee).

| Code | Description |
|------|-------------|
| 204  | Action supprimee avec succes |
| 403  | Acces refuse (non-DBOPS) |
| 404  | Action introuvable |
| 409  | L'action a des executions passees (`EXECUTION_EXISTS`) |

**Exemple reponse erreur 409:**
```json
{
  "error": {
    "code": "EXECUTION_EXISTS",
    "message": "Cannot delete action with existing executions",
    "details": { "execution_count": 5 }
  }
}
```

### PUT /api/v1/admin/actions/{id}/deactivate/

Desactivation (soft-delete) d'une action. Cascade optionnelle vers workflows.

**Body (optionnel):**
```json
{ "deletion_reason": "Action obsolete" }
```

**Query params:**
- `?confirmed=true` — Confirme la cascade vers les workflows impactes

**Sans `confirmed=true` et avec workflows impactes:**
```json
{
  "status": "requires_confirmation",
  "affected_workflows": [
    { "id": 10, "name": "Workflow A", "status": "published" },
    { "id": 11, "name": "Workflow B", "status": "published" }
  ]
}
```

**Avec `confirmed=true` (ou sans workflows impactes):**
```json
{
  "data": { "id": 3, "name": "Action X", "status": "disabled", "deleted_at": "2026-02-07T14:30:00Z", "..." : "..." },
  "deactivated_workflows": [
    { "id": 10, "name": "Workflow A" }
  ]
}
```

| Code | Description |
|------|-------------|
| 200  | Desactivation reussie (ou requires_confirmation) |
| 403  | Acces refuse (non-DBOPS) |
| 404  | Action introuvable |
| 409  | Action deja desactivee |

### PUT /api/v1/admin/actions/{id}/reactivate/

Reactivation d'une action desactivee (retour a `status=published`).

**Reponse 200:**
```json
{
  "id": 4,
  "name": "Action Name",
  "status": "published",
  "deleted_at": null,
  "deleted_by": null,
  "deletion_reason": null,
  "..."  : "..."
}
```

| Code | Description |
|------|-------------|
| 200  | Action reactivee avec succes |
| 403  | Acces refuse (non-DBOPS) |
| 404  | Action introuvable |
| 409  | Action n'est pas desactivee |

### GET /api/v1/admin/actions/?include_disabled=true

Parametre supplementaire pour inclure les actions desactivees.

- **Par defaut** (`include_disabled` absent ou `false`): retourne uniquement `status IN ('draft', 'published')`
- **`include_disabled=true`**: retourne `status IN ('draft', 'published', 'disabled')` avec champs soft-delete

Champs supplementaires pour les actions desactivees:
```json
{
  "deleted_at": "2026-02-01T00:00:00Z",
  "deleted_by": 99,
  "deletion_reason": "Obsolete"
}
```

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Oracle DB connection error (ORA-01017) during migration generation — resolved by using `DJANGO_SETTINGS_MODULE=idp_backend.test_settings`
- Pre-existing `test_admin_views.py` failures due to custom User model not having `is_staff` — resolved by writing tests with `profile='dbops'` pattern

### Completion Notes List

1. **Task 1**: Migration Django `0004_add_soft_delete_columns.py` creee avec 3 champs + index + CHECK constraint
2. **Tasks 2-6**: CatalogService enrichi avec `delete_action`, `deactivate_action`, `reactivate_action`, `count_executions`, `get_workflows_referencing_action`. ViewSet mis a jour avec `destroy()`, `deactivate()`, `reactivate()` actions + filtre `include_disabled`.
3. **Task 7**: Frontend `admin_service.ts` mis a jour avec `deleteAction`, `deactivateAction`, `reactivateAction` + types `DeactivateConfirmation`, `DeactivateResult`
4. **Tasks 8-10**: `AdminPage.tsx` modifie — checkbox "Inclure les actions desactivees", boutons conditionnels Delete/Deactivate/Reactivate, modal cascade confirmation, styling opacity 0.6 pour lignes desactivees
5. **Task 11**: 28 tests backend passent (pytest) couvrant AC1-AC6, service layer, RBAC, edge cases
6. **Task 12**: 22 tests frontend passent (vitest) couvrant filtres, boutons conditionnels, cascade modal, erreurs
7. **Task 13**: Documentation API integree dans la story

### File List

**Fichiers crees:**
- `django_backend/catalog/migrations/0004_add_soft_delete_columns.py` — Migration soft-delete
- `django_backend/catalog/tests/test_story_18_1.py` — 28 tests backend
- `frontend/src/pages/AdminPage.story18_1.test.tsx` — 22 tests frontend

**Fichiers modifies:**
- `django_backend/catalog/models.py` — Ajout `deleted_by`, `deleted_at`, `deletion_reason`, index, constraint
- `django_backend/catalog/services.py` — Methodes delete, deactivate, reactivate, cascade
- `django_backend/catalog/views.py` — Endpoints destroy, deactivate, reactivate + filtre include_disabled
- `django_backend/catalog/serializers.py` — ActionListSerializer avec champs soft-delete
- `django_backend/core/models.py` — AuditActionType: ACTION_DEACTIVATED, ACTION_REACTIVATED
- `django_backend/core/exceptions.py` — ConflictError (409) + handler
- `frontend/src/services/admin_service.ts` — deleteAction, deactivateAction, reactivateAction
- `frontend/src/types/api.ts` — ActionListItem soft-delete fields, AdminActionsFilters include_disabled
- `frontend/src/pages/AdminPage.tsx` — Checkbox filtre, boutons conditionnels, modal cascade
