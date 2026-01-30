# Story 3.3 : Recherche et filtrage du catalogue par tags

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBA,
je veux rechercher et filtrer les actions par tags, moteur, environnement, niveau d'impact ou mot-clé,
afin de trouver rapidement l'action dont j'ai besoin parmi 100+ actions.

## Acceptance Criteria

1. **Given** le DBA est sur le catalogue **When** il tape dans la barre de recherche **Then** les résultats se filtrent en temps réel (debounce 300 ms) sur le nom, la description et les tags.

2. **Given** le panneau de filtres latéraux (240 px) est visible **When** le DBA sélectionne des tags (RAC, DATAGUARD), un moteur (Oracle), un environnement (Production), et un impact (Élevé) **Then** les filtres se cumulent (intersection) et la grille/liste se met à jour.

3. **Given** le DBA veut filtrer par tags **When** il clique sur le filtre « Tags » **Then** une liste multi-select affiche tous les tags disponibles avec le nombre d'actions par tag **And** les tags sélectionnés s'affichent comme chips sous la barre de recherche.

4. **Given** des filtres sont actifs **When** le DBA voit les chips sous la barre de recherche **Then** chaque filtre actif (tag, moteur, env, impact) est représenté par un chip avec bouton « X » pour le supprimer **And** un bouton « Réinitialiser les filtres » est disponible.

5. **Given** les filtres ne retournent aucun résultat **When** la grille/liste est vide **Then** un état vide s'affiche : « Aucune action ne correspond à vos filtres » + bouton « Réinitialiser les filtres ».

6. **And** le compteur dynamique (« 12 actions ») se met à jour avec aria-live="polite".

7. **And** la recherche et les filtres sont combinés avec la catégorie sélectionnée (onglet).

8. **And** les filtres latéraux passent en panneau dépliable sous 1280 px.

9. **And** l'API GET /api/v1/catalog/actions accepte les query params : q, tags (comma-separated), category, engine, environment, impact.

10. **And** l'API GET /api/v1/catalog/tags retourne tous les tags avec leur count d'actions.

11. **And** les résultats se chargent en < 1 seconde (NFR4, NFR23).

12. **And** FR11 est satisfaite.

## Tasks / Subtasks

- [x] **Task 1 — Backend : étendre GET /api/v1/catalog/actions** (AC: 9)
  - [x] 1.1 Ajouter query params : `q` (recherche texte nom/description/tags), `engine`, `environment`, `impact` dans `catalog.py` list_catalog_actions. Conserver `tags` et `category` existants.
  - [x] 1.2 Étendre `catalog_repository.list_catalog()` (ou méthode dédiée) pour accepter `q: str | None`, `engine: str | None`, `environment: str | None`, `impact: str | None`. Recherche texte : LIKE sur NAME, DESCRIPTION ; tags via ACTION_TAGS. Filtres engine/impact : colonnes ACTIONS_CATALOG. Environnement : dérivé des impact_rules (clés JSON) ou colonne dédiée si existante.
  - [x] 1.3 Invalider ou adapter la clé de cache catalogue pour inclure tous les paramètres (q, tags, category, engine, environment, impact) afin de respecter NFR4.

- [x] **Task 2 — Backend : GET /api/v1/catalog/tags** (AC: 3, 10)
  - [x] 2.1 Ajouter route GET /catalog/tags dans `catalog.py`. Retourner liste de `{ "name": string, "action_count": number }` pour tous les tags présents sur les actions PUBLISHED, avec RBAC appliqué (même périmètre que list_catalog).
  - [x] 2.2 Requête : agrégation sur ACTION_TAGS + ACTIONS_CATALOG (STATUS = PUBLISHED), jointure avec filtrage RBAC si user authentifié. Ordre : name ASC ou action_count DESC.

- [x] **Task 3 — Frontend : barre de recherche avec debounce 300 ms** (AC: 1)
  - [x] 3.1 Dans `CatalogPage`, la barre de recherche existe déjà ; ajouter debounce 300 ms sur la valeur utilisée pour l'appel API (pas seulement filtre client). Déclencher `loadData` avec paramètre `q` après 300 ms d'inactivité. Conserver filtrage client optionnel pour réactivité immédiate si on garde chargement global + filtre client, sinon passer en « search server-side » avec `q` dans fetchCatalogActions.
  - [x] 3.2 Passer `q` (et tous les filtres) à `fetchCatalogActions` pour que les résultats viennent du serveur (recherche + filtres côté backend), garantissant NFR4 et cohérence.

- [x] **Task 4 — Frontend : panneau de filtres latéral 240 px** (AC: 2, 3, 8)
  - [x] 4.1 Créer un panneau latéral gauche (240 px) avec filtres : Tags (multi-select avec count depuis GET /catalog/tags), Moteur (select simple : Oracle, SQL Server, DB2, etc. depuis enum), Environnement (select ou multi-select selon impact_rules), Impact (select : Faible, Moyen, Élevé). Les filtres se cumulent (intersection).
  - [x] 4.2 Sous 1280 px : panneau latéral devient dépliable (collapsed by default, bouton « Filtres » pour ouvrir/fermer).
  - [x] 4.3 Mise à jour de la grille/liste : quand les filtres changent, appeler `fetchCatalogActions` avec tous les paramètres (q, tags, category, engine, environment, impact).

- [x] **Task 5 — Frontend : chips de filtres actifs et Réinitialiser** (AC: 4, 5)
  - [x] 5.1 Sous la barre de recherche : afficher un chip par filtre actif (tag, moteur, env, impact) avec libellé court et bouton X pour retirer ce filtre. Bouton « Réinitialiser les filtres » visible dès qu'au moins un filtre est actif.
  - [x] 5.2 État vide : si aucun résultat après filtres, afficher « Aucune action ne correspond à vos filtres » et bouton « Réinitialiser les filtres » (AC5).

- [x] **Task 6 — Frontend : compteur et accessibilité** (AC: 6, 7)
  - [x] 6.1 Compteur (« X actions ») déjà présent ; s'assurer qu'il reflète le nombre après recherche + filtres et qu'il a aria-live="polite".
  - [x] 6.2 Combiner recherche + filtres avec l'onglet catégorie (Tout, Provisioning, etc.) : la catégorie reste un filtre supplémentaire (déjà mappé à tag côté API).

- [x] **Task 7 — Service et types frontend** (AC: 9, 10)
  - [x] 7.1 Étendre `CatalogFilters` dans `catalog_service.ts` : `q?: string`, `engine?: string`, `environment?: string`, `impact?: string`. Adapter `fetchCatalogActions(filters)` pour envoyer ces paramètres en query string.
  - [x] 7.2 Ajouter `fetchCatalogTags(): Promise<{ name: string; action_count: number }[]>` appelant GET /catalog/tags.

- [x] **Task 8 — Tests** (AC: tous)
  - [x] 8.1 Backend : tests unitaires list_catalog_actions avec q, engine, environment, impact ; GET /catalog/tags (200, liste avec counts, RBAC cohérent).
  - [x] 8.2 Frontend : tests CatalogPage — debounce recherche, panneau filtres, chips, réinitialiser, état vide, compteur aria-live.

## Dev Notes

### Contexte métier

- **FR11** : Tout utilisateur peut rechercher et filtrer les actions par tags, moteur, environnement, niveau d'impact ou mot-clé.
- **NFR4** : La recherche et le filtrage dans le catalogue retournent des résultats en moins de 1 seconde.
- **NFR23** : Le catalogue supporte 100+ actions sans dégradation.
- Stories 3.1 et 3.2 ont livré : catalogue avec onglets catégorie, toggle cartes/liste, favoris, « Mes actions », drawer fiche complète. En 3.3 on ajoute recherche serveur (debounce 300 ms), panneau de filtres latéral (tags avec count, moteur, environnement, impact), chips actifs et réinitialisation.

### Ce qui existe déjà (à réutiliser, ne pas réinventer)

- **Backend** : `catalog.py` — GET /catalog/actions avec `tags`, `category`. `catalog_repository.list_catalog(status, tags_filter, action_ids_filter)`. Pas de paramètre `q`, `engine`, `environment`, `impact`. Pas d’endpoint GET /catalog/tags. Table ACTION_TAGS (action_id, tag_id) + TAGS (id, name) ; tags déjà chargés par action dans list_catalog.
- **Frontend** : `CatalogPage` — barre de recherche (état `searchText`), filtrage client sur name/description/tags. Onglets catégorie, toggle vue, favoris. `catalog_service.fetchCatalogActions({ category, tags })`. Pas de debounce 300 ms côté API, pas de panneau latéral 240 px, pas de chips « filtres actifs », pas d’état vide spécifique « Aucune action ne correspond à vos filtres ».

### Developer Context — Patterns à respecter

- **API** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`, dates ISO 8601 UTC. [Source: architecture]
- **Frontend** : données API en snake_case → camelCase au point d’usage. [Source: architecture]
- **Repository** : SQL brut via python-oracledb, pas d’ORM. [Source: architecture]
- **Cache catalogue** : TTL 5 min ; clé de cache doit inclure tous les paramètres de requête pour ne pas servir un cache incorrect. [Source: catalog.py]

### Architecture & technique

- **GET /catalog/actions** : Étendre avec `q`, `engine`, `environment`, `impact`. Recherche texte : OR sur NAME (LIKE), DESCRIPTION (LIKE), et tags (via sous-requête ou jointure ACTION_TAGS/TAGS). Filtres engine/impact : colonnes ENGINE, DEFAULT_IMPACT_LEVEL (ou impact_rules selon env). Environnement : si pas de colonne dédiée, dériver des clés de impact_rules (JSON).
- **GET /catalog/tags** : Agrégation sur actions PUBLISHED, avec même RBAC que list_catalog (action_ids / tag_patterns). Retourner name + count.
- **Panneau 240 px** : Layout UX — filtres latéraux 240 px (Architecture/UX : « filtres lateraux 240px »). Sous 1280 px : panneau dépliable.
- **Debounce** : 300 ms sur la valeur envoyée au serveur pour éviter trop de requêtes pendant la frappe.

### Project Structure Notes

- **Backend** : `app/api/v1/catalog.py` — étendre list_catalog_actions, ajouter GET /tags. `app/repositories/catalog_repository.py` — étendre list_catalog (q, engine, environment, impact) et ajouter méthode list_tags_with_counts ou équivalent.
- **Frontend** : `src/pages/CatalogPage.tsx` — barre recherche + debounce, panneau filtres, chips, état vide, compteur. `src/services/catalog_service.ts` — CatalogFilters étendu, fetchCatalogTags. Nouveau composant optionnel : `CatalogFiltersPanel.tsx` (filtres latéral) et/ou intégration inline dans CatalogPage. Tests : `CatalogPage.test.tsx`, `catalog_service.test.ts`.

### Previous Story Intelligence (3.2)

- **Fichiers modifiés** : `catalog.py` (GET /catalog/actions/{id}), `CatalogPage.tsx` (drawer 480 px, fetch par id, skeleton), `ActionDrawerPreview.tsx`, `catalog_service.ts` (fetchCatalogActionById). En 3.3 on ne modifie pas le drawer ; on étend la liste (recherche, filtres) et l’API list + nouveau endpoint tags.
- **Patterns** : catalog_service pour tous les appels catalogue ; Ant Design Input, Select, Drawer ; état loading/skeleton. Réutiliser ces patterns pour le panneau filtres (Select multiple pour tags, Select pour moteur/env/impact).
- **RBAC** : list_catalog et _filter_by_rbac déjà en place ; GET /catalog/tags doit appliquer le même périmètre (seuls les tags des actions visibles par l’utilisateur).

### References

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 3, Story 3.3, FR11, AC détaillés (recherche debounce, panneau 240 px, tags avec count, chips, état vide, API q/tags/engine/environment/impact, GET /tags, NFR4).
- [Source: idp-portal/backend/app/api/v1/catalog.py] — list_catalog_actions actuel (tags, category).
- [Source: idp-portal/backend/app/repositories/catalog_repository.py] — list_catalog, list_all ; structure ACTIONS_CATALOG, ACTION_TAGS, TAGS.
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx] — searchText, filteredActions, fetchCatalogActions({ category }), compteur, empty state.
- [Source: idp-portal/frontend/src/services/catalog_service.ts] — fetchCatalogActions, CatalogFilters.
- [Source: _bmad-output/planning-artifacts/architecture.md] — FR8–FR12, CatalogSearch + CatalogFilters, index catalogue, cache TTL 5 min.

## Dev Agent Record

### Agent Model Used

Claude (Dev Story workflow)

### Debug Log References

- Task 1–2: Backend catalog API + repository + list_tags_with_counts; cache key extended.
- Task 3–6: CatalogPage — useDebounce(300), useMediaQuery(1280), panneau filtres 240px (inline / Drawer <1280px), chips + Réinitialiser, état vide AC5, compteur aria-live.
- Task 7: CatalogFilters + fetchCatalogTags; catalog_service.test.ts extended.
- Task 8: test_catalog_api + test_catalog_repository (q/engine/env/impact, GET /tags); CatalogPage.test mock fetchCatalogTags + search test server-side.

### Completion Notes List

- Backend: GET /catalog/actions accepts q, engine, environment, impact; cache key includes all params. GET /catalog/tags returns name + action_count with RBAC. Repository: list_catalog(q, engine, environment, impact), list_tags_with_counts(action_ids_filter). Environment filter uses JSON_EXISTS(IMPACT_RULES, '$.' || :environment).
- Frontend: useDebounce(300) for search; loadData passes all filters to fetchCatalogActions. Panneau filtres 240px (Tags multi-select with count, Moteur, Environnement, Impact); under 1280px Drawer "Filtres". Chips + Réinitialiser; empty state "Aucune action ne correspond à vos filtres". Compteur aria-live="polite".

### File List

- idp-portal/backend/app/api/v1/catalog.py
- idp-portal/backend/app/repositories/catalog_repository.py
- idp-portal/backend/tests/unit/test_catalog_api.py
- idp-portal/backend/tests/unit/test_catalog_repository.py
- idp-portal/frontend/src/services/catalog_service.ts
- idp-portal/frontend/src/services/catalog_service.test.ts
- idp-portal/frontend/src/hooks/useDebounce.ts
- idp-portal/frontend/src/pages/CatalogPage.tsx
- idp-portal/frontend/src/pages/CatalogPage.test.tsx
- idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/3-3-recherche-et-filtrage-du-catalogue-par-tags.md

### Senior Developer Review (AI)

**Date:** 2026-01-29
**Reviewer:** Claude (Adversarial Code Review)
**Outcome:** APPROVED with fixes applied

#### Issues Found & Fixed

| # | Severity | Issue | Fix Applied |
|---|----------|-------|-------------|
| 1 | HIGH | Tasks all marked `[ ]` despite implementation complete | Checked all tasks `[x]` |
| 2 | HIGH | useDebounce.ts untracked (`??` in git) | `git add` executed |
| 3 | MEDIUM | SQL injection risk in `environment` param (JSON path) | Added regex validation `^[A-Za-z0-9_]+$` |
| 4 | MEDIUM | No validation for `impact` param | Added ImpactLevel enum validation |
| 5 | MEDIUM | ActionDrawerPreview.tsx missing from File List | Added to File List |
| 6 | MEDIUM | Case-sensitive search in Oracle | Changed to `UPPER()` for case-insensitive |

#### Tests Added
- `test_list_catalog_actions_rejects_invalid_environment` — validates environment param
- `test_list_catalog_actions_rejects_invalid_impact` — validates impact param
- `test_list_catalog_actions_accepts_valid_impact_values` — accepts low/medium/high
- Updated `test_list_catalog_with_q_engine_environment_impact` for UPPER() pattern

#### Acceptance Criteria Verification

All 12 ACs verified as IMPLEMENTED:
- AC1–AC10: Fully implemented and tested
- AC11: NFR (< 1s) — not testable without production environment
- AC12: FR11 satisfied by implementation

### Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-29 | Dev Agent | Initial implementation complete |
| 2026-01-29 | Code Review | Fixed HIGH/MEDIUM issues; status → done |
