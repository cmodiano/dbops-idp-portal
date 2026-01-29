# Story 2.12: Cumul des permissions multi-profiles

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **système**,
I want **cumuler les permissions quand un utilisateur a plusieurs profils**,
so that **les utilisateurs avec plusieurs rôles aient l'union de leurs permissions**.

## Acceptance Criteria

1. **AC1 — Union multi-profils** : Given un utilisateur appartient aux groupes AD [GRP-IDP-ASSURANCE, GRP-IDP-DBA-APP], When il se connecte au portail, Then ses permissions sont l'union des profils Assurance et DBA Applicatif.

2. **AC2 — Union actions et targets** : Given Assurance autorise actions "tag:oracle" sur targets "assurance-*", And DBA Applicatif autorise actions "tag:*" sur targets "*", When les permissions sont cumulées, Then l'utilisateur a accès à actions "tag:*" sur targets "*" (union, pas intersection).

3. **AC3 — Aucun profil reconnu** : Given un utilisateur n'appartient à aucun groupe AD reconnu (hors groupe global portail), When il se connecte, Then l'accès est refusé avec message explicite "Aucun profil associé à votre compte".

4. **AC4 — Calcul au login** : Le service RBAC calcule les permissions cumulées au login (ou première requête authentifiée) et les stocke en session / JWT / cache côté backend.

5. **AC5 — Invalidation cache** : Quand un profil est modifié (CRUD profil, PUT permissions actions, PUT permissions targets), le cache des permissions est invalidé (TTL ou invalidation explicite).

6. **AC6 — FR25c** : FR25c est satisfaite (permissions cumulées pour multi-profils).

## Tasks / Subtasks

- [x] Task 1 : Backend — Résolution des profils utilisateur au login (AC: 1, 3, 4)
  - [x] 1.1 : Dans le flow d'authentification (SAML callback ou JWT refresh), après résolution de l'utilisateur : récupérer les groupes AD de l'utilisateur (attributs SAML ou JWT).
  - [x] 1.2 : Requêter les profils dont le champ ad_group appartient à la liste des groupes de l'utilisateur (repository ou service profiles).
  - [x] 1.3 : Si aucun profil trouvé → refuser l'accès avec message "Aucun profil associé à votre compte" (HTTP 403 ou redirection login avec message). Ne pas créer de session.

- [x] Task 2 : Backend — Agrégation des permissions (actions + targets + environnements) (AC: 2, 4)
  - [x] 2.1 : Pour chaque profil de l'utilisateur, charger les permissions actions (PROFILE_ACTION_PERMISSIONS) et targets (PROFILE_TARGET_PERMISSIONS) via les repositories existants.
  - [x] 2.2 : Implémenter l'union : fusionner les listes/patterns autorisés (actions : union des action_ids + union des tag_patterns, type ALL = tout autoriser ; targets : union des target_names + union des target_patterns, ALL = tout ; environnements : union des listes).
  - [x] 2.3 : Exposer une fonction ou méthode du type `get_cumulative_permissions(user_id)` ou `get_cumulative_permissions(profile_ids)` retournant une structure unifiée (actions autorisées, targets autorisés, environnements autorisés) pour l'évaluation RBAC.

- [x] Task 3 : Backend — Cache et invalidation (AC: 4, 5)
  - [x] 3.1 : Stocker le résultat des permissions cumulées en cache (in-memory, TTL 1 min conforme à l'architecture). Clé = user_id (ou session_id).
  - [x] 3.2 : Lors de toute modification d'un profil ou de ses permissions (PUT/PATCH /admin/profiles, PUT .../actions, PUT .../targets), invalider le cache RBAC (tous les utilisateurs ou marquer dirty). Pas besoin d'invalider par user si on invalide tout le cache permissions.
  - [x] 3.3 : Documenter ou centraliser les points d'appel d'invalidation (admin routes + service layer).

- [x] Task 4 : Backend — Intégration dans le middleware / service RBAC (AC: 1–6)
  - [x] 4.1 : S'assurer que le middleware RBAC (ou rbac_service) utilise les permissions cumulées (cache ou recalcul) pour autoriser l'accès aux actions, targets et environnements.
  - [x] 4.2 : Les endpoints catalogue, exécution, etc. doivent filtrer selon ces permissions cumulées (déjà prévu si le RBAC est basé sur un "current user permissions" dérivé des profils).

- [x] Task 5 : Tests et non-régression (AC: 1–6)
  - [x] 5.1 : Tests unitaires : résolution profils à partir de groupes AD (0, 1, N profils) ; agrégation permissions (union de 2 profils avec list/pattern/all) ; refus si 0 profil avec message.
  - [x] 5.2 : Tests API : login avec groupes multi-profils → permissions cumulées ; login sans groupe reconnu → 403 / message.
  - [x] 5.3 : Test d'invalidation : modifier un profil → prochaine requête RBAC utilise les nouvelles données (cache invalidé).
  - [x] 5.4 : Pas de régression sur stories 2.9, 2.10, 2.11 (CRUD profils, permissions actions, permissions targets).

## Dev Notes

- **Contexte métier** : FR25c — Les permissions d'un utilisateur multi-profils sont cumulées (union). Les stories 2.9 (profils), 2.10 (permissions actions), 2.11 (permissions targets) ont livré les données par profil ; cette story implémente la **logique de cumul** côté backend et l'intégration au flux d'authentification et au cache RBAC.
- **Où cumuler** : Au login (ou première requête après login), une fois les profils utilisateur résolus via groupes AD. Résultat stocké en cache (TTL 1 min). Pas de nouvelle table : lecture des tables PROFILES, PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS et agrégation en mémoire.
- **Union sémantique** : Pour "list" : union des listes. Pour "pattern" : union des patterns (un utilisateur peut exécuter si au moins un de ses profils autorise l'action/target/env). Pour "all" : tout autoriser (équivalent à ne pas restreindre). Les environnements autorisés = union des listes d'environnements de chaque profil.

### Ce qui existe déjà (NE PAS RÉIMPLÉMENTER)

| Élément | Fichier | Rôle |
|--------|---------|------|
| PROFILES | V010_create_profiles.sql | Table profils avec ad_group |
| PROFILE_ACTION_PERMISSIONS | V011 | Permissions actions par profil (story 2.10) |
| PROFILE_TARGET_PERMISSIONS | V012 | Permissions targets par profil (story 2.11) |
| profile_repository, profile_action_permission_repository, profile_target_permission_repository | backend/app/repositories/ | CRUD profils, get/set actions, get/set targets |
| Auth flow (SAML/JWT) | backend/app/core/security.py, api/v1/auth.py | Récupération user + attributs (groupes AD) |
| Cache in-memory (architecture) | cachetools / lru_cache, TTL 1 min | Utiliser pour cache RBAC cumulé |

### Architecture (extrait)

- **Repository Pattern** : Pas de nouveau repository ; utiliser les existants pour charger par profile_id. Nouveau service ou fonctions dans `rbac_service.py` pour résolution profils par groupes AD et agrégation.
- **API** : Pas de nouvel endpoint public. Comportement interne : auth callback + RBAC middleware. Réponses d'erreur 403 avec message "Aucun profil associé à votre compte" lorsque aucun profil ne correspond.
- **Cache** : In-memory, TTL 1 min, clé par user_id. Invalidation lors de toute modification admin sur profils/permissions.

### Project Structure Notes

- Backend : `services/rbac_service.py` (ou équivalent) pour `get_profiles_by_ad_groups(ad_groups)`, `get_cumulative_permissions(profile_ids)`, cache + invalidation. `core/security.py` ou `api/deps.py` pour exposer les permissions courantes. Routes admin existantes : appeler une fonction d'invalidation après PUT .../profiles, .../actions, .../targets.
- Pas de migration SQL pour cette story (données déjà en place avec 2.9, 2.10, 2.11).
- Frontend : Aucun changement obligatoire pour FR25c (comportement backend). Optionnel : afficher en profil utilisateur "Profils actifs : Assurance, DBA Applicatif" si les infos sont exposées par l'API me/profile.

### References

- [Source: epics.md — Story 2.12, FR25c]
- [Source: architecture.md — Cache RBAC TTL 1 min, middleware RBAC, Repository Pattern]
- [Source: 2-11-permissions-targets-par-profile.md — PROFILE_TARGET_PERMISSIONS, PUT .../targets]
- [Source: 2-10-permissions-actions-par-profile.md — PROFILE_ACTION_PERMISSIONS, PUT .../actions]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Python 3.12+, FastAPI. Résolution profils : requête sur PROFILES où ad_group IN (groupes utilisateur). Agrégation : boucle sur profile_ids, chargement PROFILE_ACTION_PERMISSIONS et PROFILE_TARGET_PERMISSIONS, union des listes/patterns. Gestion "ALL" : si un profil a type ALL pour actions ou targets, l'union inclut tout. Cache : cachetools TTLCache ou équivalent, TTL 60 s, clé user_id. Invalidation : vider le cache ou marquer dirty après toute écriture admin sur profils/permissions.
- **Auth** : Utiliser les attributs de groupe AD déjà exposés par le flow SAML/JWT (ex. `groups` ou `ad_groups` dans le token ou la table USERS). Si les groupes ne sont pas encore persistés, les lire depuis l'assertion SAML au callback et les stocker (table USERS ou session).
- **Erreur "Aucun profil associé"** : HTTP 403 Forbidden avec body `{ "error": { "code": "NO_PROFILE", "message": "Aucun profil associé à votre compte." } }` (ou message équivalent en français).

### Architecture compliance

- Cache in-memory, TTL 1 min (architecture). Pas de Redis. Réponses API : `{ "data" }` / `{ "error" }`. Codes HTTP 403 pour accès refusé. Logging structuré avec correlation_id sur refus et invalidation cache.

### Library / framework requirements

- Aucune nouvelle dépendance. Réutiliser cachetools ou functools.lru_cache + TTL manuel si besoin. Pas de Redis.

### File structure requirements

- Backend : `app/services/rbac_service.py` (ou `app/core/rbac.py`) pour cumul + cache. `app/repositories/profile_repository.py` pour requête profils par ad_group (méthode du type `find_by_ad_groups(ad_groups)`). Invalidation appelée depuis `api/v1/admin.py` (routes PUT profiles, PUT actions, PUT targets).
- Pas de nouveau fichier frontend requis pour AC.

### Testing requirements

- Tests unitaires : résolution profils (0, 1, N) ; agrégation union (2 profils avec list + pattern) ; message "Aucun profil associé" quand 0 profil.
- Tests API : login avec groupes multi-profils → accès catalogue/exécution conforme à l'union ; login sans groupe reconnu → 403 + message.
- Test invalidation : après PUT .../profiles/{id} ou .../actions ou .../targets, prochaine requête RBAC reflète les changements.

---

## Previous Story Intelligence (2.11)

- **Permissions targets** : Story 2.11 a livré PROFILE_TARGET_PERMISSIONS (V012), ProfileTargetPermissionsUpdate, repository profile_target_permission_repository, PUT /admin/profiles/{id}/targets, section UI « Targets autorisées ».
- **Pattern** : Les permissions par profil sont lues via repositories. Pour 2.12, ne pas modifier les tables ni les endpoints admin ; ajouter la couche « résolution profils utilisateur + agrégation + cache + invalidation » et brancher le RBAC sur cette couche.
- **Fichiers utiles** : profile_repository.py (liste profils, find par id), profile_action_permission_repository.py (get_action_permissions(profile_id)), profile_target_permission_repository.py (get_target_permissions(profile_id)).

---

## Git Intelligence Summary

- Contexte récent : stories 2.9–2.11 (profils, permissions actions, permissions targets). Migrations V010–V012, repositories et routes admin en place. S'appuyer sur les mêmes conventions (snake_case, repository SQL brut, cache in-memory).

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — Cache RBAC TTL 1 min, rbac_service, security middleware]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.12, FR25c]
- [Source: idp-portal/backend/app/repositories/profile_repository.py — CRUD profils]
- [Source: idp-portal/backend/app/repositories/profile_action_permission_repository.py — Permissions actions (2.10)]
- [Source: idp-portal/backend/app/repositories/profile_target_permission_repository.py — Permissions targets (2.11)]
- [Source: idp-portal/backend/app/api/v1/admin.py — Routes PUT profiles, actions, targets ; point d’appel invalidation cache]

---

## Story Completion Status

- **Status** : done
- **Sprint status** : development_status["2-12-cumul-des-permissions-multi-profiles"] = "done"

## Dev Agent Record

### Agent Model Used

Amelia (Developer Agent) — Story 2.12 implémentée en une session.

### Debug Log References

- Résolution profils : SAML callback lit `groups` / `memberOf` / `ad_groups`, fallback `profile` ; `profile_repository.find_by_ad_groups(ad_groups)` ; 0 profils → 403 NO_PROFILE.
- Agrégation : `get_cumulative_permissions(profile_ids)` union actions/targets/envs ; `get_cumulative_permissions_cached(user_id, profile_ids)` TTL 60s.
- Invalidation : `invalidate_permissions_cache()` appelé depuis create/update/delete profile, set_actions, set_targets (api/v1/profiles.py).

### Completion Notes List

- Task 1 : auth.py callback extrait ad_groups (SAML), find_by_ad_groups, 403 JSONResponse si 0 profils ; TokenPayload + JWT ad_groups ; profile_repository.find_by_ad_groups(ad_groups).
- Task 2 : CumulativePermissionsResponse, get_cumulative_permissions(profile_ids) dans rbac_service, union list/pattern/all.
- Task 3 : TTLCache 60s _cumulative_permissions_cache ; invalidate_permissions_cache() dans profiles.py (create, update, delete, set_actions, set_targets).
- Task 4 : get_current_user (deps) résout profils par ad_groups, 403 NO_PROFILE si 0, get_cumulative_permissions_cached, UserProfile.profile_ids + cumulative_permissions ; get_optional_user aligné.
- Task 5 : tests auth (no profile 403, multi groups), profile_repository find_by_ad_groups, rbac_service get_cumulative + cache + invalidate, deps NO_PROFILE ; conftest mock profile resolution pour tests admin/catalog/profiles (hors test_profile_repository).

### Change Log

- 2026-01-28 : Story 2.12 implémentée (résolution profils, agrégation permissions, cache TTL 60s, invalidation admin, intégration get_current_user). Tous les AC couverts ; 452 tests unitaires passent.
- 2026-01-28 : **Code Review** — Corrigé HIGH-1: `get_optional_user` retourne maintenant `None` au lieu de lever `ForbiddenError` quand aucun profil n'est trouvé. Ajouté test `test_get_optional_user_no_profile_returns_none`. File List mise à jour avec tous les fichiers modifiés. Ajouté test d'invalidation cache `test_cache_invalidation_forces_refetch` (Task 5.3). Docstring auth.py mis à jour.

### File List

**Backend - Code source:**
- idp-portal/backend/app/repositories/profile_repository.py (find_by_ad_groups)
- idp-portal/backend/app/models/auth.py (TokenPayload.ad_groups, UserProfile.profile_ids, cumulative_permissions)
- idp-portal/backend/app/models/profile.py (CumulativePermissionsResponse)
- idp-portal/backend/app/api/v1/auth.py (SAML groups, find_by_ad_groups, 403 NO_PROFILE, token ad_groups, refresh ad_groups)
- idp-portal/backend/app/api/deps.py (get_current_user: 403 NO_PROFILE; get_optional_user: returns None if no profile)
- idp-portal/backend/app/services/rbac_service.py (get_cumulative_permissions, get_cumulative_permissions_cached, invalidate_permissions_cache, _cumulative_permissions_cache)
- idp-portal/backend/app/api/v1/profiles.py (invalidate_permissions_cache après create, update, delete, set_actions, set_targets)
- idp-portal/backend/app/api/v1/admin.py (include profiles router — invalidation propagée)
- idp-portal/backend/app/models/catalog.py (ajustements imports pour compatibilité)
- idp-portal/backend/pyproject.toml (dépendances cachetools)

**Backend - Tests:**
- idp-portal/backend/tests/unit/test_profile_repository.py (TestFindByAdGroups)
- idp-portal/backend/tests/unit/test_auth_api.py (test_saml_callback_no_profile_returns_403, test_saml_callback_multi_groups_resolves_profiles)
- idp-portal/backend/tests/unit/test_deps.py (test_get_current_user_no_profile_returns_403, test_get_optional_user_no_profile_returns_none)
- idp-portal/backend/tests/unit/test_rbac_service.py (TestGetCumulativePermissions, TestGetCumulativePermissionsCached)
- idp-portal/backend/tests/unit/test_admin_api.py (mocks profile resolution pour tests admin)
- idp-portal/backend/tests/unit/test_profiles_api.py (mocks profile resolution)
- idp-portal/backend/tests/unit/test_catalog_models.py (ajustements compatibilité)
- idp-portal/backend/tests/unit/conftest.py (mock_profile_resolution_for_auth, exclut test_profile_repository)

**Frontend (compatibilité, hors scope AC):**
- idp-portal/frontend/src/components/admin/ProfileForm.tsx
- idp-portal/frontend/src/components/admin/ProfileForm.test.tsx
- idp-portal/frontend/src/services/profiles_service.ts
- idp-portal/frontend/src/types/api.ts
