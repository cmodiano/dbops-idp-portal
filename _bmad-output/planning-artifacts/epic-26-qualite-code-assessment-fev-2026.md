# Epic 26 : Qualité du Code — Correctifs Assessment 6 février 2026

**En tant que** équipe de développement,  
**je veux** traiter les problèmes de conception et opportunités de simplification identifiés dans l'évaluation qualité du code du 6 février 2026,  
**afin de** améliorer la maintenabilité, réduire les fichiers monolithiques, éliminer la duplication et atteindre un score de qualité A.

---

## Contexte

**Source :** `code-quality-assessment.md` (6 février 2026, branche `develop`)

**Score actuel :** B+ (Bon, en progression)

**Problèmes majeurs identifiés :**
- `inventory/services.py` : 1 941 lignes — God Service (point noir du repo)
- `executions/views.py` : 1 375 lignes — trop de responsabilités
- `catalog/views.py` : 1 035 lignes — fonctions RBAC globales
- Frontend : ExecutionsPage (1 023), WorkflowBuilderCanvas (994), CalendarPage (896)
- Normalisation d'environnements incohérente
- Pattern `_is_dba_or_dbops()` fragile et dupliqué
- Format de réponse API inconsistant (`data.data`)
- Fonctions préfixées `_` exportées publiquement

---

## Stories proposées

### Story 26.1 : CRITIQUE — Split `inventory/services.py` en 3 services (1 941 LOC)

**En tant que** développeur,  
**je veux** extraire `InventoryService` en 3 classes distinctes,  
**afin de** éliminer le God Service et améliorer la testabilité.

**Source :** Section 4.1 du code-quality-assessment.md

**Problèmes :**
- `list_targets_for_user()` charge TOUT l'inventaire en mémoire (~300 lignes, 50k objets potentiels en RAM)
- Duplication massive entre `list_servers()`, `list_instances()`, `list_databases()`
- `_read_instances_from_config` et `_read_instances_from_config_multi` quasi-identiques

**Acceptance Criteria:**
- **Given** `inventory/services.py` contient 1 941 lignes
- **When** le refactoring est effectué
- **Then** 3 classes distinctes sont créées :
  - `InventorySourceResolver` — résolution API/DB/fallback
  - `InventoryQueryExecutor` — exécution SQL config-driven
  - `InventoryRBACFilter` — filtrage RBAC multi-couche
- **And** `InventoryService` devient un orchestrateur mince qui délègue aux 3 classes
- **And** les méthodes `_read_*_from_config` et `_read_*_from_config_multi` sont unifiées via `_read_entity_from_config()` (voir §5.1)
- **And** `list_targets_for_user()` est refactorisé en étapes nommées : `_aggregate_profile_permissions`, `_load_targets`, `_apply_rbac_chain`, `_paginate`
- **And** tous les tests existants passent
- **And** ~600 lignes de code dupliqué sont éliminées

**Fichiers concernés :**
- `inventory/services.py` (split)
- `inventory/source_resolver.py` (nouveau)
- `inventory/query_executor.py` (nouveau)
- `inventory/rbac_filter.py` (nouveau)

---

### Story 26.2 : HAUTE — Split `executions/views.py` en 4 modules (1 375 LOC)

**En tant que** développeur,  
**je veux** découper `executions/views.py` en modules distincts par responsabilité,  
**afin de** respecter le Single Responsibility Principle et faciliter la maintenance.

**Source :** Section 4.2 du code-quality-assessment.md

**Problème :** 11 classes APIView dans un seul module. `ExecutionsView.post()` fait ~350 lignes et enchaîne validation, résolution, RBAC, mutex, workflow, création, lancement.

**Acceptance Criteria:**
- **Given** `executions/views.py` contient 1 375 lignes avec 11 classes
- **When** le découpage est effectué
- **Then** 4 modules sont créés :
  - `executions/views/list_views.py` — GET /executions, /stats, /timeseries, /tags
  - `executions/views/execution_views.py` — POST /executions, GET/PATCH /{id}
  - `executions/views/scheduled_views.py` — tout /scheduled-executions
  - `executions/views/approval_views.py` — GET /pending-approvals
- **And** la méthode POST est décomposée en validators/launchers :
  - `ExecutionPayloadValidator`, `TargetValidator`, `EnvironmentConfigResolver`, `MutexValidator`, `ExecutionLauncher`, `ExecutionResponseBuilder`
- **And** chaque module fait <400 LOC
- **And** tous les tests existants passent

**Fichiers concernés :**
- `executions/views.py` → `executions/views/` (package)
- `executions/urls.py` (mise à jour des imports)

---

### Story 26.3 : HAUTE — Extraire RBAC catalog dans un service dédié

**En tant que** développeur,  
**je veux** extraire les fonctions `_filter_by_rbac()`, `_check_rbac_for_action()`, `_get_cumulative_permissions_for_user()` dans un service RBAC,  
**afin de** éliminer la duplication et centraliser la logique RBAC du catalogue.

**Source :** Section 4.3 du code-quality-assessment.md

**Problème :** Fonctions globales dans le module views. `_check_rbac_for_action()` est un `_filter_by_rbac()` pour un seul élément — duplication logique.

**Acceptance Criteria:**
- **Given** `catalog/views.py` contient des fonctions RBAC globales
- **When** le refactoring est effectué
- **Then** une classe `CatalogRBACService` est créée avec :
  - `get_permissions(user) -> CumulativePermissions | None`
  - `filter_actions(actions, perms) -> list`
  - `check_action(action, perms) -> bool` (délègue à `filter_actions`)
- **And** les 3 fonctions globales sont supprimées et remplacées par des appels au service
- **And** tous les tests existants passent

**Fichiers concernés :**
- `catalog/views.py` (réduction)
- `catalog/services.py` ou `catalog/rbac_service.py` (nouveau)

---

### Story 26.4 : HAUTE — Refactoriser ExecutionsPage.tsx (1 023 LOC)

**En tant que** développeur,  
**je veux** extraire les colonnes Table et la logique d'état d'ExecutionsPage dans des fichiers/hooks dédiés,  
**afin de** réduire la complexité du composant (20+ state variables, 500+ lignes de config colonnes).

**Source :** Section 4.4 du code-quality-assessment.md

**Acceptance Criteria:**
- **Given** `ExecutionsPage.tsx` contient 1 023 lignes
- **When** le refactoring est effectué
- **Then** les définitions de colonnes sont extraites dans `executionsColumns.tsx` (comme `actionsColumns.tsx`)
- **And** les hooks custom encapsulent les state variables et la logique de chargement
- **And** le composant principal fait <400 LOC
- **And** tous les tests existants passent

**Fichiers concernés :**
- `frontend/src/pages/ExecutionsPage.tsx`
- `frontend/src/pages/executions/executionsColumns.tsx` (nouveau)
- `frontend/src/pages/executions/useExecutionsPage.ts` (nouveau, hook)

---

### Story 26.5 : HAUTE — Refactoriser WorkflowBuilderCanvas.tsx (994 LOC)

**En tant que** développeur,  
**je veux** extraire la palette et la logique de validation de WorkflowBuilderCanvas,  
**afin de** réduire la complexité du composant (ReactFlow + palette + validation + export).

**Source :** Section 4.4 du code-quality-assessment.md

**Acceptance Criteria:**
- **Given** `WorkflowBuilderCanvas.tsx` contient 994 lignes
- **When** le refactoring est effectué
- **Then** la palette de nœuds est extraite dans un composant dédié
- **And** la logique de validation est extraite dans un hook ou utilitaire
- **And** le composant principal fait <500 LOC
- **And** tous les tests existants passent

**Fichiers concernés :**
- `frontend/src/components/workflow/WorkflowBuilderCanvas.tsx`
- `frontend/src/components/workflow/WorkflowPalette.tsx` (nouveau)
- `frontend/src/hooks/useWorkflowValidation.ts` (nouveau)

---

### Story 26.6 : HAUTE — Refactoriser CalendarPage.tsx (896 LOC)

**En tant que** développeur,  
**je veux** extraire le modal d'édition et la logique de transformation d'événements de CalendarPage,  
**afin de** séparer la logique métier du composant page.

**Source :** Section 4.4 et 4.9 du code-quality-assessment.md

**Problème :** Logique de manipulation de dates, transformation FullCalendar, gestion d'état d'édition dans un seul composant.

**Acceptance Criteria:**
- **Given** `CalendarPage.tsx` contient 896 lignes
- **When** le refactoring est effectué
- **Then** le modal d'édition de scheduled execution est extrait dans `ScheduledExecutionEditModal.tsx`
- **And** la logique de transformation d'événements est extraite dans un hook ou utilitaire
- **And** le composant principal fait <400 LOC
- **And** tous les tests existants passent

**Fichiers concernés :**
- `frontend/src/pages/CalendarPage.tsx`
- `frontend/src/components/calendar/ScheduledExecutionEditModal.tsx` (nouveau)

---

### Story 26.7 : MOYENNE — Créer EnvironmentNormalizer unique

**En tant que** développeur,  
**je veux** centraliser la normalisation d'environnements dans une classe unique,  
**afin de** avoir une source unique de vérité pour l'environnement canonique.

**Source :** Section 4.5 du code-quality-assessment.md

**Problème :** Normalisation répartie entre `InventoryService._normalize_environment()`, `_get_env_config_case_insensitive()`, `get_allowed_environments_for_user()`, `list_targets_for_user()` — chaque endroit fait sa propre version.

**Acceptance Criteria:**
- **Given** la normalisation est dupliquée à 4+ endroits
- **When** `EnvironmentNormalizer` est créé
- **Then** une classe avec `ALIASES = {'certif': 'staging', 'stg': 'staging', ...}` est implémentée
- **And** méthodes : `canonical(raw: str) -> str`, `matches(a: str, b: str) -> bool`
- **And** tous les usages existants sont migrés vers `EnvironmentNormalizer`
- **And** les aliases hardcodés sont supprimés des autres modules

**Fichiers concernés :**
- `core/environment.py` ou `executions/environment.py` (nouveau)
- `inventory/services.py`, `executions/utils.py`, `executions/views.py`

---

### Story 26.8 : MOYENNE — Créer permission IsDBAOrDBOPS DRF

**En tant que** développeur,  
**je veux** remplacer les vérifications ad-hoc `_is_dba_or_dbops()` par une permission DRF réutilisable,  
**afin de** utiliser le système RBAC existant et éviter la duplication (4 occurrences dans ScheduledExecutionsView).

**Source :** Section 4.6 du code-quality-assessment.md

**Problème :** `startswith("dba")` dangereux (matcherait `dba_readonly`). Pattern dupliqué dans `executions/views.py` et `executions/utils.py`.

**Acceptance Criteria:**
- **Given** `_is_dba_or_dbops()` est dupliqué et fragile
- **When** la permission est créée
- **Then** `IsDBAOrDBOPS` dans `core/permissions.py` avec `ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}`
- **And** la méthode `has_permission()` vérifie `profile in ADMIN_PROFILES` (pas de startswith)
- **And** tous les usages de `_is_dba_or_dbops()` et checks manuels sont remplacés par la permission ou un mixin
- **And** les tests de permissions sont mis à jour

**Fichiers concernés :**
- `core/permissions.py` (ajout IsDBAOrDBOPS)
- `executions/views.py`, `executions/utils.py` (suppression _is_dba_or_dbops)

---

### Story 26.9 : MOYENNE — Standardiser le format de réponse API

**En tant que** développeur,  
**je veux** éliminer l'imbrication `data.data` et standardiser le format de réponse,  
**afin de** avoir un contrat API cohérent.

**Source :** Section 4.7 du code-quality-assessment.md

**Problème :** `ScheduledExecutionsView.get()` retourne `{"data": {"data": [...], "pagination": {...}}}`. `ScheduledExecutionUpdateView.patch()` construit manuellement au lieu d'utiliser le serializer.

**Acceptance Criteria:**
- **Given** des endpoints retournent des formats inconsistants
- **When** la standardisation est appliquée
- **Then** format unique : `{"data": serializer.data}` ou `{"data": [...], "pagination": {...}}`
- **And** jamais d'imbrication `data` dans `data`
- **And** `ScheduledExecutionUpdateView.patch()` utilise `ScheduledExecutionSerializer`
- **And** le frontend est mis à jour si nécessaire pour consommer le nouveau format

**Fichiers concernés :**
- `executions/views.py` (ScheduledExecutionsView, ScheduledExecutionUpdateView)
- Frontend consommateurs si changement de structure

---

### Story 26.10 : BASSE — Renommer fonctions `_` exportées dans executions/utils.py

**En tant que** développeur,  
**je veux** renommer ou retirer de `__all__` les fonctions préfixées `_` qui sont exportées publiquement,  
**afin de** respecter la convention Python (préfixe `_` = privé).

**Source :** Section 4.8 du code-quality-assessment.md

**Problème :** `__all__` exporte `_get_env_config_case_insensitive`, `_parse_int`, `_is_dba_or_dbops` — confusion sur la responsabilité du module.

**Acceptance Criteria:**
- **Given** `executions/utils.py` exporte des fonctions préfixées `_`
- **When** le nettoyage est effectué
- **Then** les fonctions publiques sont renommées sans préfixe `_` (ex: `get_env_config_case_insensitive`)
- **Or** les fonctions restent privées et sont retirées de `__all__` (appelées uniquement en interne)
- **And** tous les imports sont mis à jour

**Fichiers concernés :**
- `executions/utils.py`
- Fichiers importants depuis `executions.utils`

---

### Story 26.11 : MOYENNE — Standardiser la pagination (utilitaire réutilisable)

**En tant que** développeur,  
**je veux** créer un utilitaire `paginate_queryset()` réutilisable,  
**afin de** éliminer la réimplémentation du pattern dans chaque view.

**Source :** Section 5.2 du code-quality-assessment.md

**Acceptance Criteria:**
- **Given** le pattern pagination est dupliqué dans plusieurs views
- **When** l'utilitaire est créé
- **Then** `paginate_queryset(qs, offset, limit)` retourne `{'items': [...], 'pagination': {page, page_size, total, total_pages}}`
- **And** les views existantes sont migrées vers l'utilitaire
- **And** tous les tests existants passent

**Fichiers concernés :**
- `core/pagination.py` ou nouveau module
- Views avec pagination manuelle

---

### Story 26.12 : MOYENNE — Unifier les checks RBAC dans les views (permission/mixin)

**En tant que** développeur,  
**je veux** remplacer les répétitions `if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user)` par une permission DRF ou mixin,  
**afin de** respecter DRY.

**Source :** Section 5.4 du code-quality-assessment.md

**Acceptance Criteria:**
- **Given** ce check est répété 5+ fois dans les views
- **When** la refactorisation est effectuée
- **Then** une permission DRF ou mixin `IsOwnerOrDBA` est créé
- **And** tous les usages du pattern sont remplacés
- **And** les tests de permissions couvrent les cas owner vs non-owner

**Fichiers concernés :**
- `core/permissions.py`
- `executions/views.py`

---

## Priorisation recommandée

### Court terme (1-2 sprints)
| # | Story | Impact | Effort |
|---|-------|--------|--------|
| 1 | 26.1 — Split inventory/services.py | Maintenabilité | M |
| 2 | 26.2 — Split executions/views.py | Lisibilité | M |
| 3 | 26.3 — Extraire RBAC catalog | Réutilisabilité | S |
| 4 | 26.10 — Renommer fonctions _ exportées | Convention | XS |
| 5 | 26.9 — Standardiser format réponse | Contrat API | S |

### Moyen terme (1-2 mois)
| # | Story | Impact | Effort |
|---|-------|--------|--------|
| 6 | 26.7 — EnvironmentNormalizer | Cohérence | S |
| 7 | 26.8 — Permission IsDBAOrDBOPS | DRY | S |
| 8 | 26.4 — Extraire colonnes ExecutionsPage | Lisibilité | S |
| 9 | 26.5, 26.6 — Refactor WorkflowBuilder + CalendarPage | Maintenabilité | M |
| 10 | 26.11, 26.12 — Pagination + RBAC unifiés | DRY | S |

---

## Métriques de succès

- **Score qualité :** B+ → A
- **Fichiers >900 LOC :** 6 → 0 (ou justification documentée)
- **inventory/services.py :** 1 941 → <700 LOC (orchestrateur + 3 services)
- **executions/views.py :** 1 375 → 4 modules <400 LOC chacun
- **Duplication éliminée :** ~600 lignes dans InventoryService
- **Couverture tests :** Maintien ≥80% avec tests pour les nouveaux modules

---

## Notes

- Cette epic complète Epic 17 et Epic 22 — elle traite les problèmes identifiés dans l'évaluation du 6 février 2026 après les améliorations déjà livrées (FastAPI supprimé, OracleJSONField, logger frontend, api_client refactorisé, etc.)
- Les stories 26.1 et 26.2 sont les plus impactantes — prioriser en premier
- Story 26.8 peut être combinée avec 26.10 si les fichiers se chevauchent
