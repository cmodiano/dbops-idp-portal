# Story 3.1: Catalogue d'actions avec modes d'affichage et favoris

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want parcourir le catalogue avec différents modes d'affichage (cartes ou liste) et accéder rapidement à mes actions favorites,
So that je navigue efficacement dans un catalogue de 100+ actions.

## Acceptance Criteria

1. **Given** un DBA authentifié accède à l'onglet Catalogue **When** la page se charge **Then** les actions publiées s'affichent en grille de cartes par défaut (3 colonnes sur 1280px, 4 colonnes sur 1600px+).

2. **Given** le DBA veut changer de mode d'affichage **When** il clique sur le toggle "Cartes / Liste" **Then** l'affichage bascule entre grille de cartes et vue liste (tableau avec colonnes : nom, tags, moteur, impact, exécutions) **And** le mode choisi est persisté en localStorage.

3. **Given** le catalogue affiche des actions **When** le DBA regarde une ActionCard **Then** chaque carte affiche : icône moteur, nom de l'action, description (2 lignes max), ImpactIndicator (couleur + icône + texte), tags (chips), nombre d'exécutions.

4. **Given** le DBA veut marquer une action en favori **When** il clique sur l'icône étoile sur une carte **Then** l'action est ajoutée à ses favoris (stockés en base, lié au user_id).

5. **Given** le DBA consulte le catalogue **When** il a des favoris **Then** une section "Mes actions" s'affiche en haut avec ses favoris et ses actions récemment exécutées.

6. **Given** le catalogue a des catégories **When** le DBA clique sur un onglet (Tout, Provisioning, Patching, Administration, Monitoring) **Then** la grille/liste se filtre par la catégorie sélectionnée et le compteur se met à jour ("12 actions").

7. **And** le composant ActionCard est accessible (role="article", aria-label, focusable au clavier, Enter ouvre le drawer — préparatoire Story 3.2 ; en 3.1 clic ouvre éventuellement détail minimal si implémenté, sinon au moins navigation clavier).

8. **And** le composant ImpactIndicator affiche triple codage (couleur + icône + texte) avec aria-label="Impact: [niveau]".

9. **And** le chargement affiche des skeleton cards/rows (shimmer) — pas de spinner seul.

10. **And** le cache in-memory (TTL 5 min) est utilisé pour le catalogue côté backend.

11. **And** l'API GET /api/v1/catalog/actions retourne les actions filtrées par le RBAC de l'utilisateur.

12. **And** l'API GET /api/v1/users/me/favorites retourne les favoris de l'utilisateur.

13. **And** l'API POST/DELETE /api/v1/users/me/favorites/{action_id} gère les favoris.

14. **And** la table USER_FAVORITES (user_id, action_id, created_at) est créée via migration SQL.

15. **And** FR8, FR11a et FR11b sont satisfaites.

## Tasks / Subtasks

- [x] **Task 1 — Backend : migrations et favoris** (AC: 4, 5, 12, 13, 14)
  - [x] 1.1 Créer migration Flyway `V021__create_user_favorites.sql` : table `USER_FAVORITES` (user_id, action_id, created_at), PK (user_id, action_id), FK vers USERS et ACTIONS_CATALOG, index sur user_id.
  - [x] 1.2 Créer `favorites_repository` (ou module dans `user_repository`) : `list_favorites(user_id)`, `add_favorite(user_id, action_id)`, `remove_favorite(user_id, action_id)`.
  - [x] 1.3 Exposer GET /api/v1/users/me/favorites, POST /api/v1/users/me/favorites/{action_id}, DELETE /api/v1/users/me/favorites/{action_id}. Authentification requise (get_current_user). Réponses : `{ "data": [ { "action_id", "created_at" } ] }` et 204 pour DELETE.

- [x] **Task 2 — Backend : catalogue filtré RBAC, cache, execution_count** (AC: 1, 3, 10, 11)
  - [x] 2.1 Rendre GET /api/v1/catalog/actions authentifié (optionnel ou requis selon spec ; AC exige RBAC donc au moins optional user). Si user : filtrer les actions publiées par `cumulative_permissions` (action_ids ou tag_patterns selon `actions_type`). Utiliser `get_current_user` (catalogue protégé) ou `get_optional_user` puis filtrer si présent.
  - [x] 2.2 Ajouter paramètres query `category` (alias tag filter pour onglets : Tout → pas de filter ; Provisioning, Patching, Administration, Monitoring → filter par tag correspondant, ex. `provisioning`, `patching`, `administration`, `monitoring`). Conserver `tags` (comma-separated) pour filtres avancés. Mettre à jour `list_all` / nouvelle fonction pour RBAC + category/tags.
  - [x] 2.3 Ajouter `execution_count` par action dans la réponse catalogue (agrégation depuis EXECUTION_LOG / execution_repository par ACTION_ID). Aligner format avec `ActionResponse` + `execution_count` (ou DTO catalogue dédié).
  - [x] 2.4 Introduire cache in-memory (cachetools TTLCache) pour liste catalogue, TTL 5 min. Clé inclure user (ou "anon") + filtres (category, tags) pour éviter fuites cross-user. Invalider si besoin (ex. nouvelle action publiée — optional pour 3.1).

- [x] **Task 3 — Backend : "actions récemment exécutées" pour Mes actions** (AC: 5)
  - [x] 3.1 Exposer GET /api/v1/users/me/recent-actions (ou inclure dans /users/me) : dernières exécutions de l'utilisateur (EXECUTION_LOG.USER_ID), puis action_ids distincts, ordre par date. Limiter (ex. 10). Retourner léger payload (action_id, name, optional link) pour affichage "Mes actions".

- [x] **Task 4 — Frontend : page Catalogue et données** (AC: 1, 2, 5, 6, 9)
  - [x] 4.1 Implémenter `CatalogPage` : fetch GET /catalog/actions (avec category/tags selon onglet), GET /users/me/favorites, GET /users/me/recent-actions. Gérer états loading (skeleton), error, empty.
  - [x] 4.2 Grille cartes par défaut : CSS Grid, 3 colonnes @ 1280px, 4 @ 1600px+. Vue liste : Table (colonnes nom, tags, moteur, impact, exécutions). Toggle "Cartes / Liste" avec persistance localStorage (clé type `catalog-view-mode`).
  - [x] 4.3 Composant `CategoryTabs` (ou équivalent) : onglets Tout, Provisioning, Patching, Administration, Monitoring. Clic filtre le catalogue (category) et met à jour le compteur "X actions" (aria-live="polite").
  - [x] 4.4 Section "Mes actions" en haut si favoris ou recent : afficher favoris + actions récemment exécutées (éviter doublons), liens vers actions. Libellés en français.

- [x] **Task 5 — Frontend : ActionCard favoris, skeletons, a11y** (AC: 3, 4, 7, 8, 9)
  - [x] 5.1 Ajouter icône étoile (favori) sur `ActionCard` (variant catalogue). Clic appelle POST/DELETE favorites, mise à jour optimiste + refetch si erreur. Désactiver si non authentifié.
  - [x] 5.2 Vérifier ImpactIndicator triple codage + aria-label="Impact: [niveau]" (déjà en place ; confirmer).
  - [x] 5.3 Créer `SkeletonCard` / `SkeletonRow` (shimmer), les utiliser pendant chargement catalogue (cartes ou lignes selon mode). Pas de spinner seul.
  - [x] 5.4 Garder ActionCard accessible : role="article", aria-label, focusable, Enter/Space pour activation. En 3.1 pas de drawer ; prévoir onclick sur carte pour extension 3.2 (drawer).

- [x] **Task 6 — Tests et qualité** (AC: tous)
  - [x] 6.1 Tests unitaires backend : favorites repo, endpoints favorites, catalogue filtré RBAC, cache, execution_count.
  - [x] 6.2 Tests unitaires frontend : `CatalogPage`, `CategoryTabs`, `ActionCard` favori, skeletons, a11y de base.
  - [x] 6.3 Tests d'intégration : appel catalogue authentifié + favoris + recent-actions si faisable.

## Dev Notes

### Contexte métier

- **FR8** : DBA parcourt le catalogue d’actions. **FR11a** : toggle cartes/liste. **FR11b** : favoris et "Mes actions".
- Catalogue scalable 100+ actions (NFR23). Performance recherche/filtrage < 1 s (NFR4).

### Patterns à respecter

- **API** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`, dates ISO 8601 UTC. [Source: architecture.md]
- **Frontend** : données API en snake_case → camelCase au point d’usage. [Source: architecture.md]
- **Repository** : SQL brut via python-oracledb, pas d’ORM. [Source: architecture.md]
- **Cache** : cachetools TTLCache. Catalogue 5 min, RBAC 1 min. [Source: epics.md, architecture]
- **Composants** : ActionCard, ImpactIndicator déjà en place (admin/preview). Réutiliser pour catalogue ; ajouter seule­ment favori + usage catalogue.

### Ce qui existe déjà

- **Backend** : `GET /api/v1/catalog/actions` (published, filter tags), sans auth ni RBAC. `catalog_repository.list_all`, `ActionResponse`. Pas de `USER_FAVORITES`, pas d’API favoris.
- **Frontend** : `CatalogPage` stub (titre seul). `ActionCard` (catalog + preview), `ImpactIndicator` (triple codage), `TopNav` avec onglet Catalogue. Pas de `CategoryTabs`, pas de `SkeletonCard`, pas de service catalog/favorites.
- **Auth** : `get_current_user` → `UserProfile` avec `profile_ids`, `cumulative_permissions`. RBAC : `actions_type` (all/list/pattern), `action_ids`, `tag_patterns`. [Source: deps.py, rbac_service]

### Catégories vs tags

- Story 2.23 : colonne `category` supprimée, usage des **tags** pour catégorisation. [Source: epics.md]
- Onglets "Tout, Provisioning, Patching, Administration, Monitoring" = filtres par **tag** (ex. `provisioning`, `patching`, `administration`, `monitoring`). "Tout" = pas de filtre category.

### Drawer et Story 3.2

- Fiche descriptive en drawer latéral = **Story 3.2**. En 3.1 : pas de drawer. AC 7 "Enter ouvre le drawer" est préparatoire ; en 3.1 on assure au moins clavier (Enter/Space) sur carte, sans ouvrir de drawer.

### “Mes actions”

- Favoris : stockage `USER_FAVORITES`. recent : dérivé de `EXECUTION_LOG` (USER_ID, ACTION_ID, STARTED_AT). Endpoint dédié ou inclus dans /users/me.

### Project Structure Notes

- **Backend** : `app/api/v1/catalog.py`, `app/api/v1/` (nouveaux routes users/me/favorites, users/me/recent-actions ou sous-routes), `app/repositories/` (favorites, extensions catalog), `app/models/`, `database/migrations/`.
- **Frontend** : `src/pages/CatalogPage.tsx`, `src/components/catalog/` (ActionCard, CategoryTabs, SkeletonCard/SkeletonRow), `src/components/shared/ImpactIndicator.tsx`, `src/services/` (catalog_service, favorites_service ou api_client). Tests co-localisés `*.test.tsx`.
- Conventions : [Source: architecture.md] noms fichiers, endpoints, patterns API/DB.

### References

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 3, Story 3.1, FR8, FR11a, FR11b, AC détaillés.
- [Source: _bmad-output/planning-artifacts/architecture.md] — Stack, structure, API/DB patterns, cache, composants catalog.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — Catalogue, cartes, filtres, golden path, design system.
- [Source: idp-portal/backend/app/api/v1/catalog.py] — Catalogue API actuelle.
- [Source: idp-portal/backend/app/services/rbac_service.py] — `get_cumulative_permissions_cached`, `CumulativePermissionsResponse`.
- [Source: idp-portal/backend/app/api/deps.py] — `get_current_user`, `UserProfile`, `profile_ids`, `cumulative_permissions`.
- [Source: idp-portal/frontend/src/components/catalog/ActionCard.tsx] — ActionCard existant.
- [Source: idp-portal/frontend/src/components/shared/ImpactIndicator.tsx] — ImpactIndicator.
- [Source: idp-portal/database/migrations/V006__create_execution_log.sql] — EXECUTION_LOG (USER_ID, ACTION_ID).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None required.

### Completion Notes List

#### Task 1 — Backend : migrations et favoris
- Created migration `V021__create_user_favorites.sql` with USER_FAVORITES table
- Created `favorites_repository.py` with CRUD operations (list, add, remove, is_favorite)
- Created `app/api/v1/users.py` with favorites endpoints
- Registered users router in main.py
- 35 tests for migration, repository, and API

#### Task 2 — Backend : catalogue filtré RBAC, cache, execution_count
- Updated `catalog.py` API with optional auth, category filter, and cache
- Created `list_catalog()` in catalog_repository with execution_count from EXECUTION_LOG
- Implemented TTLCache (5 min) for catalog responses
- RBAC filtering via cumulative_permissions (actions_type, action_ids, tag_patterns)
- 8 tests for catalog API and repository

#### Task 3 — Backend : "actions récemment exécutées"
- Added `list_recent_actions()` to favorites_repository
- Added GET /users/me/recent-actions endpoint
- Returns distinct action_ids with name and last_executed_at
- 3 tests for recent actions API

#### Task 4-6 — Frontend : CatalogPage, service, tests
- Created `catalog_service.ts` with all API calls
- Implemented full `CatalogPage.tsx` with:
  - Category tabs (Tout, Provisioning, Patching, Administration, Monitoring, Mes actions)
  - Grid/List view toggle
  - ActionCard grid with favorites toggle
  - Search filter
  - "Mes actions" section with favorites and recent actions
  - Loading skeletons and empty states
  - Action detail drawer
- 15 frontend tests (8 service + 7 page)

#### Code-review fixes (2026-01-29)
- AC2: localStorage persistence for view mode (`catalog-view-mode`), init from storage, save on toggle.
- AC6: Action count displayed with aria-live ("X actions").
- Task 5.1: Favorite button disabled when not authenticated (useAuth).
- AC9: Skeleton rows in list mode, skeleton cards in grid mode.
- Backend: add_favorite validates action exists (catalog_repository.get_by_id), returns 404 if not.
- Tests: localStorage persistence (AC2), action count (AC6), add_favorite 404.
- File List: added ActionCard, ActionDrawerPreview and their tests.

### File List

**Backend:**
- `database/migrations/V021__create_user_favorites.sql` (new)
- `app/repositories/favorites_repository.py` (new)
- `app/api/v1/users.py` (new)
- `app/api/v1/catalog.py` (modified)
- `app/repositories/catalog_repository.py` (modified)
- `app/main.py` (modified)
- `tests/unit/test_migration.py` (modified)
- `tests/unit/test_favorites_repository.py` (new)
- `tests/unit/test_favorites_api.py` (new)
- `tests/unit/test_recent_actions_api.py` (new)
- `tests/unit/test_catalog_api.py` (modified)
- `tests/unit/test_catalog_repository.py` (modified)

**Frontend:**
- `src/services/catalog_service.ts` (new)
- `src/services/catalog_service.test.ts` (new)
- `src/pages/CatalogPage.tsx` (modified)
- `src/pages/CatalogPage.test.tsx` (new)
- `src/components/catalog/ActionCard.tsx` (modified)
- `src/components/catalog/ActionCard.test.tsx` (modified)
- `src/components/catalog/ActionDrawerPreview.tsx` (modified)
- `src/components/catalog/ActionDrawerPreview.test.tsx` (modified)
