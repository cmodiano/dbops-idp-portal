# Story 13.3 : RBAC — dériver l'environnement du target et filtrer les targets par profil

Status: done

## Story

As a système,
I want calculer les targets autorisés pour un utilisateur à partir de ses profils (environnements autorisés + restriction pattern/liste),
So que le wizard et l'API ne proposent que des targets sur lesquels l'utilisateur a le droit.

## Acceptance Criteria

### AC1 — Filtrage par environnements autorisés
**Given** un utilisateur a des droits sur les environnements [DEV, CERTIF] et aucune restriction target (pattern/liste),
**When** il demande la liste des targets disponibles,
**Then** il obtient uniquement les targets dont l'environnement est DEV ou CERTIF (pas PROD).

### AC2 — Restriction par pattern
**Given** un utilisateur a des droits sur DEV et une restriction target pattern `web-*`,
**When** il demande la liste des targets disponibles,
**Then** il obtient uniquement les targets DEV dont le nom matche `web-*` (ex: web-app-01, web-front-02).

### AC3 — Restriction par liste explicite
**Given** un utilisateur a des droits sur DEV et CERTIF et une restriction target liste [srv1, srv2],
**When** il demande la liste des targets disponibles,
**Then** il obtient uniquement srv1 et srv2 s'ils appartiennent à un environnement autorisé.

### AC4 — Validation backend POST /executions
**Given** une requête POST /api/v1/executions avec action_id et target_id(s),
**When** le backend valide les permissions,
**Then** il vérifie que le target appartient à l'inventaire, qu'il est dans un environnement autorisé pour l'utilisateur et qu'il respecte les restrictions target du profil ; sinon 403.

### AC5 — Cumul multi-profils (RM6)
**And** le cumul multi-profils applique l'union des targets autorisés (règles métier RM6).

## Tasks / Subtasks

### Backend — Renforcement InventoryService

- [x] **Task 1** (AC: 1,2,3,5) — Vérifier et renforcer `list_targets_for_user()` dans `inventory/services.py`
  - [x] Subtask 1.1 — Valider que le filtrage par environnements autorisés fonctionne (vérifié: lignes 455-459)
  - [x] Subtask 1.2 — Valider le filtrage par pattern (fnmatch sur target name) avec casse insensible (vérifié: lignes 500-504)
  - [x] Subtask 1.3 — Valider le filtrage par liste explicite (vérifié: lignes 494-496)
  - [x] Subtask 1.4 — Valider le cumul multi-profils (union des permissions de tous les profils) (vérifié: lignes 379-413)
  - [x] Subtask 1.5 — Ajouter des logs structurés pour traçabilité RBAC (ajouté: lignes 471-483)

### Backend — Renforcement validation POST /executions

- [x] **Task 2** (AC: 4) — Améliorer la validation RBAC dans `executions/views.py`
  - [x] Subtask 2.1 — Vérifier que chaque target_name fourni est dans la liste retournée par `list_targets_for_user()` (vérifié: lignes 246-271)
  - [x] Subtask 2.2 — Si un target n'est pas autorisé : log audit `EXECUTION_TARGET_FORBIDDEN` + réponse 403 avec message explicite (vérifié: lignes 255-271)
  - [x] Subtask 2.3 — Vérifier cohérence environnement : tous les targets doivent avoir le même environnement (vérifié: lignes 277-282)
  - [x] Subtask 2.4 — Tester avec utilisateur ayant pattern restriction qui tente un target hors pattern (test ajouté)

### Backend — Tests complets RBAC

- [x] **Task 3** (AC: 1-5) — Tests unitaires et intégration pour scénarios RBAC
  - [x] Subtask 3.1 — Test `test_list_targets_environment_filter`: utilisateur DEV+STAGING ne voit pas PROD (ajouté dans test_services.py)
  - [x] Subtask 3.2 — Test `test_list_targets_pattern_restriction`: pattern `web-*` filtre correctement (ajouté dans test_services.py)
  - [x] Subtask 3.3 — Test `test_list_targets_list_restriction`: liste explicite filtre correctement (ajouté dans test_services.py)
  - [x] Subtask 3.4 — Test `test_list_targets_multi_profile_union`: cumul multi-profils = union (ajouté dans test_services.py)
  - [x] Subtask 3.5 — Test `test_post_execution_forbidden_target`: target non autorisé → 403 (ajouté dans executions/tests.py)
  - [x] Subtask 3.6 — Test `test_post_execution_pattern_mismatch`: target hors pattern → 403 (ajouté dans executions/tests.py)
  - [x] Subtask 3.7 — Test `test_post_execution_allowed_target`: target autorisé → 201 (ajouté dans executions/tests.py)

### Frontend — Validation UX (optionnel)

- [x] **Task 4** (AC: 1-3) — Vérifier que TargetSelector affiche uniquement les targets autorisés
  - [x] Subtask 4.1 — Confirmer que `GET /api/v1/inventory/targets` est appelé (confirmé: TargetSelector.tsx:82)
  - [x] Subtask 4.2 — Confirmer que le backend filtre côté serveur (confirmé: TargetSelector.tsx:5 "RBAC filtered")
  - [x] Subtask 4.3 — Test manuel : non applicable - filtrage serveur, tests existants dans ExecutionWizard.targets.test.tsx

## Dev Notes

### Ce qui existe déjà (Stories 13.1 + 13.2)

**InventoryService.list_targets_for_user()** — `inventory/services.py:342-471`:
- Récupère les profils de l'utilisateur via AD groups
- Agrège les environnements autorisés (RM2)
- Applique les restrictions target (PATTERN, LIST, ALL) via `_apply_target_restrictions()`
- Filtre par environnement
- Cumul multi-profils via union des permissions (RM6)

**Pattern matching** — `_apply_target_restrictions()`:
```python
# Utilise fnmatch.fnmatch avec casse insensible
if perm_type == 'PATTERN':
    for pattern in values:
        if fnmatch.fnmatch(target_name.lower(), pattern.lower()):
            matches = True
```

**Validation POST /executions** — `executions/views.py`:
- Appelle `InventoryService.list_targets_for_user()` avec les AD groups
- Vérifie que chaque target demandé est dans la liste autorisée
- Log audit `EXECUTION_TARGET_FORBIDDEN` si refusé (V047)
- Retourne 403 si non autorisé

### Fichiers à modifier / valider

**Backend (validation/tests) :**
- `idp-portal/django_backend/inventory/services.py` — Valider logique existante
- `idp-portal/django_backend/inventory/tests/test_services.py` — Ajouter tests RBAC complets
- `idp-portal/django_backend/executions/views.py` — Valider logique refus
- `idp-portal/django_backend/executions/tests.py` — Ajouter tests scénarios RBAC

**Aucune migration nécessaire** — La structure de permissions existe déjà :
- `PROFILE_ACTION_PERMISSIONS.ENVIRONMENTS` (CLOB JSON)
- `PROFILE_TARGET_PERMISSIONS.PERMISSION_TYPE` + `TARGET_PATTERNS` / `TARGET_NAMES`

### Règles métier (Référence: regles-metier-permissions-par-target-et-environnement.md)

| Règle | Description | Implémentation |
|-------|-------------|----------------|
| **RM1** | Environnement = propriété du target (pas de l'action) | Target.environment depuis inventaire |
| **RM2** | Droits profil par environnement | ProfileActionPermission.environments |
| **RM3** | Restriction optionnelle par pattern | ProfileTargetPermission.permission_type='PATTERN' |
| **RM4** | Filtrage = intersection env + restriction | `list_targets_for_user()` |
| **RM5** | Une action, plusieurs envs via targets différents | Wizard permet multi-targets |
| **RM6** | Cumul multi-profils = union | Boucle sur tous les profils, union des sets |

### Modèles de données (existants)

**ProfileActionPermission** — `profiles/models.py`:
```python
class ProfileActionPermission(models.Model):
    profile = models.OneToOneField(Profile, ...)
    permission_type = models.CharField(max_length=20)  # ALL, LIST, PATTERN
    environments = models.TextField(null=True)  # CLOB JSON: ["dev", "staging", "prod"]

    def get_environments(self) -> list[str]:
        return json.loads(self.environments or '[]')
```

**ProfileTargetPermission** — `profiles/models.py`:
```python
class ProfileTargetPermission(models.Model):
    profile = models.OneToOneField(Profile, ...)
    permission_type = models.CharField(max_length=20)  # ALL, LIST, PATTERN
    target_patterns = models.TextField(null=True)  # CLOB JSON: ["web-*", "db-*"]
    target_names = models.TextField(null=True)  # CLOB JSON: ["srv-01", "srv-02"]

    def get_target_patterns(self) -> list[str]:
        return json.loads(self.target_patterns or '[]')
    def get_target_names(self) -> list[str]:
        return json.loads(self.target_names or '[]')
```

### Patterns de code à suivre

**Récupération AD groups** — Utiliser `get_user_ad_groups()`:
```python
from core.auth_utils import get_user_ad_groups

ad_groups = get_user_ad_groups(request.user)
targets, total = inventory_service.list_targets_for_user(
    user_id=request.user.id,
    ad_groups=ad_groups,
    environment=env_filter,
    search=search_query
)
```

**Audit pour refus** — Utiliser AuditService:
```python
from core.services import AuditService
from core.models import AuditActionType

AuditService.create_entry(
    user_id=str(request.user.id),
    action_type=AuditActionType.EXECUTION_TARGET_FORBIDDEN,
    entity_type="execution",
    entity_id=None,
    details={
        'action_id': action_id,
        'target_name': forbidden_target,
        'reason': 'target_not_in_allowed_list'
    },
    correlation_id=get_correlation_id()
)
```

**Logging structuré** — Utiliser structlog:
```python
import structlog
logger = structlog.get_logger(__name__)

logger.info(
    "rbac_targets_filtered",
    user_id=user_id,
    allowed_environments=list(allowed_environments),
    restriction_type=restriction_type,
    total_targets=len(filtered_targets),
    correlation_id=correlation_id
)
```

### Tests existants (ne pas casser)

- `inventory/tests/test_services.py` — Tests InventoryService
- `inventory/tests/test_views.py` — Tests API inventory (permission admin sur /all)
- `executions/tests.py` — Tests POST /executions avec targets
- `profiles/tests/` — Tests permissions profils

### Scénarios de test RBAC à implémenter

**Scénario 1 — Environnement seul:**
```python
# Profil: envs=[DEV, STAGING], targets=ALL
# Inventaire: srv-dev-01 (DEV), srv-stg-01 (STAGING), srv-prod-01 (PROD)
# Résultat attendu: [srv-dev-01, srv-stg-01] (pas srv-prod-01)
```

**Scénario 2 — Pattern:**
```python
# Profil: envs=[DEV], targets=PATTERN ['web-*']
# Inventaire: web-dev-01 (DEV), db-dev-01 (DEV), web-prod-01 (PROD)
# Résultat attendu: [web-dev-01] (pas db-dev-01 ni web-prod-01)
```

**Scénario 3 — Liste explicite:**
```python
# Profil: envs=[DEV, STAGING], targets=LIST ['srv-01', 'srv-02']
# Inventaire: srv-01 (DEV), srv-02 (STAGING), srv-03 (DEV)
# Résultat attendu: [srv-01, srv-02] (pas srv-03)
```

**Scénario 4 — Multi-profils (union):**
```python
# Profil A: envs=[DEV], targets=LIST ['srv-01']
# Profil B: envs=[STAGING], targets=ALL
# Inventaire: srv-01 (DEV), srv-stg-01 (STAGING), srv-prod-01 (PROD)
# Résultat attendu: [srv-01, srv-stg-01] (union des deux profils)
```

### Dépendances avec autres stories Epic 13

| Story | Dépendance | Statut |
|-------|------------|--------|
| **13.1** | API `/api/v1/inventory/targets` + InventoryService | done |
| **13.2** | Wizard avec TargetSelector + validation POST /executions | done |
| **13.3** | CETTE STORY — renforcement RBAC et tests | ready-for-dev |
| **13.4** | Refactoring action unique (après cette story) | backlog |
| **13.5** | API standalone (utilise même RBAC) | backlog |

### Risques et points d'attention

1. **Performance** — `list_targets_for_user()` charge jusqu'à 5000 targets en mémoire pour filtrage RBAC. Si inventaire > 5000, résultats incomplets. Solution future : filtrage SQL côté Oracle.

2. **Casse des patterns** — `fnmatch.fnmatch` est sensible à la casse par défaut. L'implémentation actuelle convertit en lowercase. Vérifier cohérence.

3. **Profil sans permissions** — Un profil `is_admin=1` sans `ProfileActionPermission` ni `ProfileTargetPermission` explicite obtient accès complet. Vérifier que c'est le comportement souhaité.

4. **Normalisation environnements** — Les valeurs `certif` / `certification` sont normalisées en `staging`. Vérifier que les profils utilisent la forme normalisée.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Pas de bugs rencontrés

### Completion Notes List

- **Task 1 complétée** : Validation de `list_targets_for_user()` - la logique RBAC existante est complète et correcte. Ajout de logs structurés détaillés pour traçabilité (lignes 471-483).
- **Task 2 complétée** : Validation de POST /executions - la logique de refus RBAC est complète avec audit trail `EXECUTION_TARGET_FORBIDDEN` et messages explicites.
- **Task 3 complétée** : 16 nouveaux tests ajoutés couvrant tous les scénarios RBAC :
  - `RBACEnvironmentFilterTests` (2 tests) : filtrage par environnement, normalisation certif→staging
  - `RBACPatternRestrictionTests` (3 tests) : pattern matching, casse insensible, combinaison env+pattern
  - `RBACListRestrictionTests` (3 tests) : liste explicite, combinaison env+liste, casse insensible
  - `RBACMultiProfileUnionTests` (2 tests) : union multi-profils, union multi-patterns
  - `RBACEdgeCaseTests` (5 tests) : cas limites, admin, pagination
  - `ExecutionRBACValidationTests` (6 tests) : POST /executions avec targets interdits
  - `ExecutionRBACMultiProfileTests` (1 test) : union permissions multi-profils
- **Task 4 complétée** : Frontend déjà conforme - `TargetSelector.tsx` appelle `/api/v1/inventory/targets` (RBAC filtré côté serveur).
- **Code review 2026-02-05** : 6 correctifs appliqués — (1) `environments_json` au lieu de `environments` dans executions/tests, (2) logs RBAC consolidés en un seul, (3) LIST case-insensitive aligné sur PATTERN, (4) `rbac_truncated` dans signature `list_targets_for_user` et réponse API, (5) File List complétée (executions/views, inventory/views), (6) test `test_list_targets_list_case_insensitive` ajouté.
- **Code review auto-fixes 2026-02-05** : (1) Normalisation des environnements dans `list_targets_for_user` et `get_allowed_environments_for_user` (certif/certification → staging) pour que les profils avec "certif" voient les cibles staging. (2) 403 avec `inventory_truncated: true` quand la liste des cibles autorisées est tronquée. (3) Audit EXECUTION_TARGET_FORBIDDEN : entity_type=EXECUTION, entity_id=0. (4) Constante MAX_TARGETS_FOR_RBAC_FILTER utilisée dans executions/views. (5) Tests vues : assertion `rbac_truncated` + test quand truncation, test audit entity_type/entity_id, test profil avec env "certif".

### Change Log

- 2026-02-05: Story 13.3 implémentée - renforcement RBAC, logs structurés, tests complets
- 2026-02-05: Code review fixes — `environments_json` (executions/tests), logs consolidés, LIST case-insensitive, `rbac_truncated` dans API, File List complétée
- 2026-02-05: Code review auto-fixes — normalisation envs profil (certif→staging), audit EXECUTION/entity_id=0, 403+inventory_truncated, constant page_size, tests rbac_truncated et certif profil

### File List

**Modified:**
- `idp-portal/django_backend/inventory/services.py` — Normalisation envs (profil + query), LIST case-insensitive, retour `rbac_truncated`, `get_allowed_environments_for_user` normalisé
- `idp-portal/django_backend/inventory/views.py` — Champ `rbac_truncated` dans réponse GET /inventory/targets
- `idp-portal/django_backend/inventory/tests/test_services.py` — +15 tests RBAC, test_list_targets_list_case_insensitive, test_list_targets_profile_env_certif_normalized_to_staging
- `idp-portal/django_backend/inventory/tests/test_views.py` — Assertions `rbac_truncated`, test_list_targets_response_includes_rbac_truncated_true_when_truncated
- `idp-portal/django_backend/executions/views.py` — Validation RBAC POST /executions, MAX_TARGETS_FOR_RBAC_FILTER, audit EXECUTION/0, details 403 + inventory_truncated
- `idp-portal/django_backend/executions/tests.py` — +7 tests RBAC, fix `environments_json`, assertions entity_type/entity_id dans test_post_execution_audit_log_on_forbidden

