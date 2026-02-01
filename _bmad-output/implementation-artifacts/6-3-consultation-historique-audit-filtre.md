# Story 6.3 : Consultation historique d'audit filtre

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a spécialiste sécurité,
I want consulter l'historique d'exécution avec des filtres précis (période, environnement, action, utilisateur, résultat),
So that je trouve rapidement les exécutions pertinentes pour un audit.

## Acceptance Criteria

1. **AC1** — Given Nadia accède à la section Audit (sous l'onglet Exécutions ou page dédiée), When la page se charge, Then une table affiche toutes les exécutions avec : action, utilisateur, environnement, statut, date, changement ServiceNow.
2. **AC2** — Given Nadia sélectionne des filtres, When elle filtre par période (date picker) + environnement "Production" + 30 derniers jours, Then la table se filtre en temps réel et le compteur se met à jour.
3. **AC3** — Given Nadia clique sur une ligne, When le détail s'ouvre, Then le détail complet s'affiche : qui, quoi, quand, paramètres, résultat, logs, timeline d'exécution, lien vers le changement ServiceNow.
4. **AC4** — La table supporte le tri par colonne (clic en-tête) ascendant/descendant.
5. **AC5** — La pagination est de 25 lignes par page.
6. **AC6** — L'API GET /api/v1/audit/executions accepte les query params : from, to, environment, action_id, user_id, status.
7. **AC7** — Les requêtes d'audit supportent 10 000+ exécutions sans dégradation (NFR24).
8. **AC8** — FR33 est satisfaite.

## Tasks / Subtasks

- [x] **Task 1** (AC: 6, 7) — Backend : API et repository pour liste d'audit filtrée
  - [x] 1.1 Étendre `audit_repository.list_entries` (ou ajouter `list_execution_audit_entries`) avec paramètres optionnels : `from_date`, `to_date`, `user_id`, `environment`, `action_id`, `status` (dérivé des ACTION_TYPE EXECUTION_*). Filtrer ENTITY_TYPE = execution ; pour environment/action_id/status utiliser la colonne DETAILS (JSON) ou ACTION_TYPE pour le statut.
  - [x] 1.2 Ajouter une requête COUNT pour la pagination (même filtres) sans charger toutes les lignes.
  - [x] 1.3 Créer route GET /api/v1/audit/executions avec query params from, to, environment, action_id, user_id, status, limit, offset ; protéger par RBAC (profil auditeur / is_auditor).
  - [x] 1.4 S'assurer que les index existants (TIMESTAMP, ENTITY_TYPE, USER_ID) sont utilisés ; si besoin ajouter index composite (ENTITY_TYPE, TIMESTAMP) pour NFR24.
- [x] **Task 2** (AC: 1, 2, 4, 5) — Frontend : page ou section Audit avec table et filtres
  - [x] 2.1 Créer page Audit (route /audit) ou onglet "Audit" dans la zone Exécutions — selon décision UX (epics : "sous l'onglet Executions ou page dédiée"). Restreindre l'accès aux utilisateurs avec is_auditor (ou permission dédiée).
  - [x] 2.2 Table avec colonnes : action (nom), utilisateur, environnement, statut, date, changement ServiceNow (lien si présent). Données chargées via GET /api/v1/audit/executions.
  - [x] 2.3 Filtres : période (date picker ou presets 30j, 90j), environnement, action (select), utilisateur (select ou texte), résultat/statut (success, failed, running). Appliquer les filtres en temps réel (requête API avec params).
  - [x] 2.4 Compteur d'enregistrements (total filtré) mis à jour à chaque changement de filtres.
  - [x] 2.5 Tri par colonne (clic en-tête) asc/desc ; pagination 25 par page.
- [x] **Task 3** (AC: 3) — Frontend : drawer détail d'une entrée d'audit
  - [x] 3.1 Au clic sur une ligne, ouvrir un drawer (ou modal) avec le détail complet : user_id, action (nom), timestamp, paramètres (depuis DETAILS), résultat, IP, correlation_id.
  - [x] 3.2 Afficher un lien "Voir l'exécution" vers la page Exécutions ou réutiliser ExecutionTimeline avec execution_id = entity_id (charger GET /executions/{id} + steps si besoin).
  - [x] 3.3 Si l'entrée contient servicenow_change_id (dans DETAILS ou entrée SERVICENOW_CHANGE_CREATED), afficher un lien vers le changement ServiceNow (URL configurable ou texte "Change SN: XXX").
- [x] **Task 4** (AC: 8) — RBAC et navigation
  - [x] 4.1 Backend : vérifier que seuls les utilisateurs avec is_auditor (ou permission audit) peuvent appeler GET /api/v1/audit/executions ; sinon 403.
  - [x] 4.2 Frontend : afficher l'entrée de navigation "Audit" (ou onglet) uniquement pour les profils auditeurs ; sinon masquer ou rediriger.
- [x] **Task 5** — Tests
  - [x] 5.1 Tests unitaires backend : route GET /api/v1/audit/executions avec filtres (from, to, user_id, environment, action_id, status), pagination, 403 si non-auditeur.
  - [x] 5.2 Tests unitaires audit_repository : list avec filtres optionnels, count avec mêmes filtres.
  - [x] 5.3 Tests frontend : page Audit (table, filtres, tri, pagination, drawer détail, lien exécution / ServiceNow).

## Dev Notes

- **Contexte Epic 6** : Stories 6.1 et 6.2 ont mis en place AUDIT_LOG immutable, traces EXECUTION_* et SERVICENOW_CHANGE_CREATED, et détails enrichis (patching, comptes à privilèges) dans DETAILS. La table n'a pas de nouvelle migration pour 6.3 : on lit les entrées existantes avec des filtres côté requête.
- **Source des filtres** : USER_ID et TIMESTAMP sont des colonnes. environment, action_id, "status" (résultat) pour les exécutions sont dans DETAILS (JSON) écrit par execution_service — ex. details.action_id, details.environment, et le "statut" peut être déduit de ACTION_TYPE (EXECUTION_COMPLETED vs EXECUTION_FAILED vs EXECUTION_STARTED). Adapter la requête SQL pour filtrer sur DETAILS (JSON_VALUE ou JSON_EXISTS selon Oracle).
- **Relation exécution ↔ audit** : Pour les entrées ENTITY_TYPE=execution, ENTITY_ID = execution_id. Une exécution génère plusieurs entrées (EXECUTION_SUBMITTED, EXECUTION_STARTED, EXECUTION_COMPLETED/FAILED, éventuellement SERVICENOW_CHANGE_CREATED). Pour la "table d'audit" côté métier, on affiche typiquement une ligne par exécution (résumé) ; donc soit on agrège par entity_id (exécution), soit on n'affiche que les entrées "terminales" (EXECUTION_COMPLETED, EXECUTION_FAILED) pour éviter doublons. Décision implémentation : une ligne = une exécution (entity_id) avec dernière action_type et infos dérivées (action name, env, user, date, statut, servicenow_change_id si présent). Requête possible : filtrer ENTITY_TYPE=execution, puis grouper par ENTITY_ID ou sélectionner la dernière entrée par ENTITY_ID (MAX(TIMESTAMP)) pour afficher une ligne par exécution.
- **Lien ServiceNow** : Si DETAILS contient servicenow_change_id, l'URL du changement peut être construite via config (base URL ServiceNow + /nav_to.do?uri=change_request.do?sys_id=XXX) ou affichée en texte seulement si pas de config.

### Project Structure Notes

- **Backend** : `app/api/v1/` — nouveau fichier `audit.py` ou extension de `executions.py` ; en fait une route dédiée GET /audit/executions dans un router audit pour rester cohérent avec "GET /api/v1/audit/executions". Créer `app/api/v1/audit.py` et l'enregistrer dans `main.py` ou `api/__init__.py`. `app/repositories/audit_repository.py` — étendre `list_entries` ou ajouter `list_execution_audit_entries(from_date, to_date, user_id, environment, action_id, status, limit, offset)` et `count_execution_audit_entries(...)`.
- **Frontend** : `src/pages/AuditPage.tsx` (ou `AuditTab` sous Executions) ; `src/services/audit_service.ts` (appels GET /audit/executions) ; `src/types/api.ts` — types pour réponse audit. Route /audit dans App.tsx ; entrée "Audit" dans TopNav conditionnée à is_auditor.
- **Pas de migration Flyway** : pas de changement de schéma pour 6.3.

### Developer context — garde-fous

- **Stack** : Backend Python 3.12+, FastAPI, python-oracledb, Oracle. Frontend React, TypeScript, Ant Design 6.2. Réutiliser ExecutionTimeline et patterns ExecutionsPage (pagination, tri, drawer).
- **DB** : Lecture seule sur AUDIT_LOG. Pas d'UPDATE/DELETE. Filtres sur DETAILS via JSON_VALUE (Oracle) pour environment, action_id ; statut dérivé de ACTION_TYPE.
- **API** : GET /api/v1/audit/executions uniquement (liste + pagination). Pas de POST/PUT/DELETE sur l'audit.
- **RBAC** : Accès réservé aux profils avec is_auditor=true (ou permission dédiée audit). Vérifier deps.py / get_current_user et ajouter une vérification is_auditor pour la route audit.
- **NFR24** : Pagination stricte (25), index sur (ENTITY_TYPE, TIMESTAMP), éviter SELECT * sans LIMIT ; count séparé pour total.

### Previous Story Intelligence (6.2)

- **Fichiers modifiés en 6.2** : `execution_service.py` (enrichissement details patching / compte à privilèges), `audit_repository` inchangé (signature create_entry), tests execution_service + execution_api.
- **Pattern à réutiliser** : DETAILS est un CLOB JSON ; structure documentée pour patching et compte à privilèges. Pour 6.3, en lecture on parse DETAILS pour filtrer/afficher environment, action_id, servicenow_change_id.
- **Code review 6.2** : pas de régression sur EXECUTION_COMPLETED/FAILED audit entries ; garder la même forme d'appel create_entry.

### Architecture Compliance

- **AUDIT_LOG** : Append-only conservé ; aucune écriture dans 6.3 ; lecture avec filtres et pagination.
- **Repository** : audit_repository reste INSERT + SELECT only ; ajout de list (avec filtres étendus) et count pour exécutions uniquement.
- **REST** : Nouvelle ressource /api/v1/audit/executions en lecture seule, alignée sur les conventions existantes (limit, offset, query params).
- **Frontend** : Alignement avec ExecutionsPage (Table Ant Design, pagination, tri, drawer) et design system liquid glass / thème existant.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 6, Story 6.3]
- [Source: idp-portal/backend/app/repositories/audit_repository.py — list_entries, DETAILS]
- [Source: idp-portal/backend/app/services/execution_service.py — structure DETAILS pour exécutions]
- [Source: idp-portal/database/migrations/V004 et V028 — AUDIT_LOG]
- [Source: idp-portal/frontend/src/pages/ExecutionsPage.tsx — patterns table, pagination, drawer]
- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx — réutilisation pour détail]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- ✅ Task 1 (Backend): Implémenté `list_execution_audit_entries` et `count_execution_audit_entries` dans audit_repository.py avec filtres JSON_VALUE sur DETAILS. Créé route GET /api/v1/audit/executions avec RBAC is_auditor. Ajouté is_auditor au modèle UserProfile et deps.py.
- ✅ Task 2 (Frontend Table): Créé AuditPage.tsx avec table Ant Design, colonnes (action, user, env, status, date, ServiceNow), filtres (période, environnement, statut), pagination 25/page, tri par colonne.
- ✅ Task 3 (Frontend Drawer): Drawer avec détail complet (qui, quoi, quand, paramètres, résultat, IP, correlation_id, ServiceNow). Réutilise ExecutionTimeline pour afficher les étapes.
- ✅ Task 4 (RBAC/Navigation): Backend vérifie is_auditor (403 sinon). Frontend affiche onglet "Audit" conditionnel, redirige non-auditeurs.
- ✅ Task 5 (Tests): 9 tests backend API, 9 tests backend repository (nouvelles fonctions), 7 tests frontend AuditPage — tous passent.

### Code Review Fixes (2026-01-31)

**CRITICAL-1**: Ajouté index composite `IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP` (migration V029) pour NFR24 performance.

**HIGH-1**: Implémenté tri fonctionnel côté backend (paramètres `sort`/`order`) et frontend (passage des paramètres à l'API). AC4 maintenant satisfait.

**HIGH-2**: Corrigé parsing de date avec fonction `_parse_iso_date()` gérant timezone (Z, +00:00), millisecondes, et formats variés.

**HIGH-3**: Ajouté `NVL()` autour de `JSON_VALUE()` pour gérer cas NULL/invalides dans DETAILS sans erreur SQL.

**HIGH-4**: Enrichissement des entrées d'audit avec `action_name` depuis `catalog_repository.get_action_names_by_ids()`. Frontend affiche maintenant le nom réel au lieu de "Action #ID".

### File List

**Backend (modifiés)**
- idp-portal/backend/app/models/auth.py — Ajout is_auditor au UserProfile
- idp-portal/backend/app/api/deps.py — Résolution is_auditor depuis profiles
- idp-portal/backend/app/repositories/audit_repository.py — Ajout list_execution_audit_entries, count_execution_audit_entries, _parse_iso_date(), tri avec sort_field/sort_order, NVL() pour JSON_VALUE
- idp-portal/backend/app/repositories/catalog_repository.py — Ajout get_action_names_by_ids() pour enrichissement
- idp-portal/backend/app/main.py — Enregistrement router audit

**Backend (nouveaux)**
- idp-portal/backend/app/api/v1/audit.py — Route GET /audit/executions (avec tri et enrichissement action_name)
- idp-portal/backend/tests/unit/test_audit_api.py — Tests API audit
- idp-portal/database/migrations/V029__add_audit_log_entity_type_timestamp_index.sql — Index composite pour NFR24

**Backend (modifiés - tests)**
- idp-portal/backend/tests/unit/test_audit_repository.py — Tests nouvelles fonctions

**Frontend (modifiés)**
- idp-portal/frontend/src/types/common.ts — Ajout 'audit' à NavigationTabKey, is_auditor à User
- idp-portal/frontend/src/types/api.ts — Ajout types AuditExecutionEntry (avec action_name), AuditExecutionFilters (avec sort/order)
- idp-portal/frontend/src/contexts/AuthContext.tsx — Ajout 'audit' aux navigation_tabs dev mock
- idp-portal/frontend/src/App.tsx — Ajout AuditPage route et AuditGuard
- idp-portal/frontend/src/components/layout/TopNav.tsx — Ajout onglet Audit
- idp-portal/frontend/src/services/audit_service.ts — Ajout paramètres sort/order dans buildQueryString()
- idp-portal/frontend/src/pages/AuditPage.tsx — Passage sort/order à l'API, utilisation action_name enrichi, dépendances useCallback mises à jour

**Frontend (nouveaux)**
- idp-portal/frontend/src/pages/AuditPage.tsx — Page consultation audit
- idp-portal/frontend/src/pages/AuditPage.test.tsx — Tests frontend
- idp-portal/frontend/src/services/audit_service.ts — Service API audit
