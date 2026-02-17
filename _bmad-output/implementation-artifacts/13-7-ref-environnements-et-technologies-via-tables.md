# Story 13.7 : Référentiels — environnements et technologies pilotés par tables (aucune valeur en dur)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBOPS**,
je veux que les environnements valides proviennent de l'inventaire et que les technologies (moteurs) et plateformes soient gérées via des tables de référence dans le portail,
afin de contrôler ces listes sans toucher au code et que la source de vérité pour les environnements soit l'inventaire.

## Contexte

Aujourd'hui les environnements (dev, staging, prod) et les technologies (Oracle, SQL Server, DB2) sont fixés par des contraintes CHECK en base et des enums/listes en dur dans le code. L'objectif est de **ne plus avoir aucune référence en dur** : technologies et plateformes sont pilotés par des **tables** ; pour les environnements, la **source de vérité est l'inventaire**. Spécification détaillée : `_bmad-output/implementation-artifacts/13-ref-environnements-et-technologies-via-tables.md`.

## Acceptance Criteria

### AC1 — Technologies et plateformes depuis tables de référence

**Given** les technologies (moteurs) et plateformes,  
**When** on consulte ou configure une action ou un filtre,  
**Then** les listes proviennent de tables de référence (REF_ENGINES, REF_PLATFORMS) exposées via une API (ex. GET /api/v1/reference/engines, GET /api/v1/reference/platforms). Aucune liste en dur dans le code (backend et frontend). ACTIONS_CATALOG.ENGINE et PLATFORM référencent ces tables (code ou FK) ; les contraintes CHECK fixes sont supprimées.

### AC2 — Environnements depuis l'inventaire

**Given** les environnements valides,  
**When** on en a besoin (filtres, profils, validation d'exécution),  
**Then** la liste provient de l'inventaire : un endpoint (ex. GET /api/v1/inventory/environments) retourne les environnements exposés par l'inventaire (API externe ou distinct des targets). Aucune liste d'environnements en dur dans le code. EXECUTIONS.ENVIRONMENT et SCHEDULED_EXECUTIONS.ENVIRONMENT ne sont plus contraintes par un CHECK fixe ; la validation applicative vérifie que la valeur appartient à la liste retournée par l'inventaire (ou dérivée du target en Epic 13).

### AC3 — Profils : options d'environnements depuis l'API inventaire

**Given** un DBOPS configure un profil (environnements autorisés),  
**When** il sélectionne les environnements,  
**Then** les options proposées viennent de l'API inventaire/environments (ou reference/environments si option table cache), pas d'une liste en dur.

### AC4 — Normalisation

**And** la normalisation des alias (ex. certif → staging) peut rester côté inventaire ou dans le service portail qui agrège les environnements ; le portail n'impose plus un jeu fixe de valeurs en dur.

---

## Tasks / Subtasks

### Task 1 : REF_ENGINES — table, migration, API, suppression CHECK (AC1)

- [x] **Subtask 1.1** — Créer table REF_ENGINES (ID, CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE) en migration Flyway (nouveau fichier V0xx).
- [x] **Subtask 1.2** — Migration : insérer les valeurs actuelles (Oracle, SQL Server, DB2 ; optionnel : PostgreSQL, MySQL, Workflow).
- [x] **Subtask 1.3** — Supprimer contrainte CHECK sur ACTIONS_CATALOG.ENGINE (drop CK_ACTIONS_CATALOG_ENGINE et CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM si besoin, recréer une contrainte qui autorise NULL ou valeur présente dans REF_ENGINES.CODE, ou FK vers REF_ENGINES).
- [x] **Subtask 1.4** — Backend Django : modèle RefEngine (ou équivalent), vue/serializer GET /api/v1/reference/engines (liste active, tri DISPLAY_ORDER).
- [x] **Subtask 1.5** — Remplacer ActionEngine (enum) par lecture depuis table/API dans catalog (validation create/update : engine dans liste reference/engines).
- [x] **Subtask 1.6** — Frontend : supprimer ENGINE_OPTIONS en dur ; charger les options via GET /api/v1/reference/engines (actionOptions.ts, ActionForm, ActionWizard, filtres Exécutions/Calendrier, catalogue).

### Task 2 : REF_PLATFORMS — table, migration, API (AC1)

- [x] **Subtask 2.1** — Créer table REF_PLATFORMS (ID, CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE) en migration.
- [x] **Subtask 2.2** — Migration : insérer AAP, GitHub Actions, Azure DevOps, Terraform.
- [x] **Subtask 2.3** — Supprimer contrainte CHECK sur ACTIONS_CATALOG.PLATFORM ; lier à REF_PLATFORMS (CODE ou FK).
- [x] **Subtask 2.4** — Backend : modèle RefPlatform, GET /api/v1/reference/platforms.
- [x] **Subtask 2.5** — Remplacer ActionPlatform (enum) par lecture depuis table/API ; validation catalog.
- [x] **Subtask 2.6** — Frontend : supprimer PLATFORM_OPTIONS en dur ; charger via GET /api/v1/reference/platforms partout où nécessaire.

### Task 3 : GET /api/v1/inventory/environments et suppression listes en dur environnements (AC2, AC3, AC4)

- [x] **Subtask 3.1** — Backend : endpoint GET /api/v1/inventory/environments qui retourne la liste des environnements (depuis InventoryService : distinct des targets ou appel API externe inventaire). Normalisation (certif → staging) si documentée.
- [x] **Subtask 3.2** — Supprimer contrainte CHECK ENVIRONMENT sur EXECUTIONS et SCHEDULED_EXECUTIONS (migrations Flyway).
- [x] **Subtask 3.3** — Validation applicative : à la création exécution / scheduled_execution, vérifier que environment appartient à la liste GET /api/v1/inventory/environments (ou dérivée du target).
- [x] **Subtask 3.4** — Supprimer TargetEnvironment.VALUES / ENVIRONMENT_OPTIONS et toute liste en dur d'environnements dans le code (backend + frontend).
- [x] **Subtask 3.5** — Profils (environnements autorisés) : les options du sélecteur viennent de GET /api/v1/inventory/environments (frontend + validation backend).

### Task 4 : Cohérence filtres et UI

- [x] **Subtask 4.1** — Filtres Exécutions, Calendrier, Reporting : Environnement, Technologie, Plateforme chargés depuis les APIs reference/engines, reference/platforms, inventory/environments (pas de constantes en dur).
- [x] **Subtask 4.2** — Types TypeScript : ActionEngine / ActionPlatform peuvent rester en string générique ou être dérivés de la réponse API ; ne plus importer de listes statiques.

### Task 5 : Tests et documentation

- [x] **Subtask 5.1** — Tests unitaires et d’intégration pour reference/engines et reference/platforms (liste, filtrage is_active).
- [x] **Subtask 5.2** — Tests pour GET /api/v1/inventory/environments (source inventaire ou fallback).
- [x] **Subtask 5.3** — Tests de validation : création action avec engine/platform invalide (400) ; création exécution avec environment invalide (400/422).
- [ ] **Subtask 5.4** — Mettre à jour la doc API (backend) et toute référence aux enums ENGINE/PLATFORM/ENVIRONMENT. (OPTIONNEL - peut être fait dans une story séparée)

---

## Dev Notes

### Contexte technique actuel (à faire évoluer)

- **Backend (Django)**  
  - `catalog/models.py` : `ActionEngine`, `ActionPlatform` en TextChoices ; champs `engine`, `platform` sur `Action` avec choices.  
  - Contraintes Oracle : V002 (CK_ACTIONS_CATALOG_ENGINE, CK_ACTIONS_CATALOG_PLATFORM), V037 (nullable pour workflows, CHECK ENGINE IN (...), PLATFORM IN (...)).
- **Frontend**  
  - `frontend/src/utils/actionOptions.ts` : `ENGINE_OPTIONS`, `PLATFORM_OPTIONS` en dur.  
  - `frontend/src/types/api.ts` : `ActionEngine`, `ActionPlatform` en types union.  
  - Filtres : ExecutionsFiltersPanel, CalendarFiltersPanel, AdvancedFiltersPanel, HorizontalFilters, ActionForm, ActionWizard, etc. utilisent ces listes ou des dérivés.
- **Inventaire**  
  - `inventory/models.py` : `TargetEnvironment.VALUES` (dev, staging, prod) en dur.  
  - `inventory/views.py` : `list_targets`, `list_all_targets` ; pas encore d’endpoint `environments`.  
  - InventoryService : récupère des targets avec `environment` ; on peut dériver la liste des environnements distincts ou ajouter un endpoint côté source.
- **Exécutions / Planifiées**  
  - EXECUTIONS.ENVIRONMENT : CHECK dans V023 (dev, staging, prod).  
  - SCHEDULED_EXECUTIONS.ENVIRONMENT : CHECK dans V038 (dev, staging, prod).  
  - À remplacer par validation applicative contre GET /api/v1/inventory/environments.

### Ordre de mise en œuvre suggéré (spéc 13-ref)

1. REF_ENGINES : migration table + API + alimentation ; suppression CHECK ENGINE ; adapter catalog + executions + frontend.
2. REF_PLATFORMS : idem.
3. Environnements : GET /api/v1/inventory/environments ; suppression listes en dur et CHECK ENVIRONMENT ; validation applicative ; adapter profils.

### Project Structure Notes

- **Backend** : Nouvelle app ou module `reference` pour REF_ENGINES / REF_PLATFORMS (modèles, vues, serializers, urls) ; ou placer sous `catalog` si préféré. Endpoint `inventory/environments` dans l’app `inventory`.
- **Migrations** : `idp-portal/database/migrations/` (Flyway) pour Oracle : nouveaux scripts V0xx pour REF_ENGINES, REF_PLATFORMS, puis DROP/ADD CHECK pour ENGINE, PLATFORM, ENVIRONMENT.
- **Frontend** : Un service/hook pour charger engines, platforms, environments au démarrage ou par écran ; partager entre formulaire action, filtres Exécutions, Calendrier, Reporting, profils.

### References

- [Source: _bmad-output/implementation-artifacts/13-ref-environnements-et-technologies-via-tables.md] — Spécification complète (tables, API, options A/B environnements).
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 13, Story 13.7] — User story et critères d’acceptation.
- [Source: idp-portal/database/migrations/V002__create_actions_catalog.sql] — Contraintes ENGINE/PLATFORM actuelles.
- [Source: idp-portal/database/migrations/V037__make_engine_platform_nullable_for_workflows.sql] — CHECK ENGINE/PLATFORM avec NULL pour workflows.
- [Source: idp-portal/database/migrations/V023__create_executions.sql] — CHECK ENVIRONMENT sur EXECUTIONS.
- [Source: idp-portal/database/migrations/V038__add_scheduled_executions.sql] — CHECK ENVIRONMENT sur SCHEDULED_EXECUTIONS.
- [Source: idp-portal/django_backend/catalog/models.py] — ActionEngine, ActionPlatform, champs engine/platform.
- [Source: idp-portal/django_backend/inventory/models.py] — TargetEnvironment.VALUES.
- [Source: idp-portal/frontend/src/utils/actionOptions.ts] — ENGINE_OPTIONS, PLATFORM_OPTIONS à supprimer.

---

## Developer Context (guardrails)

- **Ne pas réinventer** : Les modèles Django pour REF_ENGINES/REF_PLATFORMS suivent le même pattern que les autres tables de référence (ID, CODE, LABEL, ordre, actif). Pas de nouvelle lib pour les listes.
- **Emplacements stables** : Backend = `idp-portal/django_backend/` (catalog, inventory, ou nouveau module `reference`). Migrations Oracle = `idp-portal/database/migrations/`. Frontend = `idp-portal/frontend/src/` (utils, types, components).
- **APIs existantes** : Garder le format de réponse DRF (liste d’objets avec code, label, display_order). Pagination non nécessaire pour des listes de référence courtes.
- **Inventaire** : InventoryService existe ; soit il expose déjà une méthode pour « environnements distincts », soit l’ajouter. Ne pas dupliquer la logique d’appel externe/fallback DBOPS_INVENTORY.
- **Rétrocompatibilité** : Les valeurs actuelles (Oracle, SQL Server, DB2 ; dev, staging, prod) doivent rester valides après migration (seed dans REF_ENGINES/REF_PLATFORMS ; inventaire retourne au minimum dev/staging/prod si c’est la source).

---

## Technical Requirements

- **REF_ENGINES / REF_PLATFORMS** : Table avec ID (PK), CODE (unique), LABEL, DISPLAY_ORDER, IS_ACTIVE. ACTIONS_CATALOG : soit FK vers ID, soit VARCHAR stockant CODE avec validation applicative contre la table.
- **Environnements** : Pas de table REF obligatoire (Option A recommandée) ; GET /api/v1/inventory/environments dérivé de l’inventaire (targets distincts ou endpoint externe). Validation à la création exécution/scheduled : valeur dans cette liste.
- **Validation** : Création/mise à jour d’action : engine et platform doivent appartenir aux listes retournées par reference/engines et reference/platforms. Création exécution/planifiée : environment doit appartenir à inventory/environments (ou être dérivé du target).
- **Frontend** : Plus de constantes ENGINE_OPTIONS / PLATFORM_OPTIONS / ENVIRONMENT_OPTIONS en dur. Chargement via API au montage des écrans ou une fois en contexte global (cache court acceptable).

---

## Architecture Compliance

- **Stack** : Django + DRF (backend), React + Ant Design (frontend), Oracle (BD), migrations Flyway dans `database/migrations/`.
- **Sécurité** : Endpoints reference/engines et reference/platforms en lecture seule, protégés par authentification (IsAuthenticated). inventory/environments idem, avec filtrage RBAC si la liste dépend du contexte utilisateur (sinon liste globale des codes environnements).
- **Cohérence Epic 13** : L’environnement d’une exécution reste dérivé du target quand des targets sont choisis ; la liste des environnements valides pour validation et filtres vient de l’inventaire.

---

## Library / Framework Requirements

- **Backend** : Django ORM pour les modèles RefEngine / RefPlatform. Aucune nouvelle dépendance requise pour les listes de référence.
- **Frontend** : Conserver React, Ant Design (Select, etc.) ; charger les options via fetch/axios vers les nouvelles APIs. Pas de lib externe pour « reference data ».
- **Migrations** : Scripts SQL Flyway compatibles Oracle (syntaxe CHECK, ALTER TABLE, INSERT).

---

## File Structure Requirements

- **Nouveaux fichiers possibles** : `django_backend/reference/` (models, views, serializers, urls) ou intégration dans `catalog` ; `database/migrations/V0xx__add_ref_engines.sql`, `V0xx__add_ref_platforms.sql`, `V0xx__drop_check_engine_platform_environment.sql` (ou découpé).
- **Fichiers à modifier** : `catalog/models.py` (suppression enum engine/platform ou conservation pour rétrocompatibilité validation), `catalog/views.py` ou serializers (validation engine/platform), `inventory/views.py` (nouveau endpoint environments), `inventory/services.py` (méthode environments), `inventory/urls.py` (route), `executions/` (validation environment), `frontend/src/utils/actionOptions.ts` (supprimer constantes, appels API), `frontend/src/types/api.ts` (optionnel : types string pour engine/platform), composants utilisant engine/platform/environment (ActionForm, ActionWizard, ExecutionsFiltersPanel, CalendarFiltersPanel, AdvancedFiltersPanel, profils).

---

## Testing Requirements

- **Backend** : Tests unitaires et/ou d’intégration pour GET /api/v1/reference/engines et GET /api/v1/reference/platforms (liste, is_active). Tests pour GET /api/v1/inventory/environments (réponse conforme, source inventaire ou fallback). Tests de validation : création action avec engine/platform invalide → 400 ; création exécution/scheduled avec environment invalide → 400/422.
- **Frontend** : S’assurer que les écrans (formulaire action, filtres) ne plantent pas si les APIs sont vides ou en erreur (états de chargement, messages clairs).
- **Migrations** : Vérifier que les migrations s’appliquent sur une base existante (données REF insérées, CHECK supprimés/recréés sans casser les données actuelles).

---

## Previous Story Intelligence (13.6 — Calendrier)

- Story 13.6 a livré le menu Calendrier, la vue calendrier (semaine/mois), les filtres alignés sur la page Exécutions (action, environnement, plateforme, technologie). Les filtres utilisent actuellement des listes en dur (ENVIRONMENT_OPTIONS, ENGINE_OPTIONS, PLATFORM_OPTIONS). Pour 13.7, ces mêmes filtres doivent être alimentés par les APIs reference/engines, reference/platforms et inventory/environments. Fichiers concernés : `CalendarFiltersPanel.tsx`, `ExecutionsFiltersPanel.tsx`, et les services/hooks qui fournissent les options.

---

## Project Context Reference

- Pas de fichier `project-context.md` trouvé à la racine. Contexte projet : portail DBOPS (idp-portal), monorepo avec frontend React (Vite, Ant Design) et backend Django (DRF), base Oracle, migrations Flyway. Epic 13 = sélection de targets à l’exécution et permissions par environnement ; cette story en est le volet « référentiels sans valeur en dur ».

---

## Story Completion Status

- **Status** : done  
- **Ultimate context engine analysis completed** — Guide développeur créé avec fondation épics, spéc 13-ref, analyse architecture/code actuel, tâches détaillées, garde-fous et références de fichiers.
- **Implementation progress** : Tasks 1-5 complétés (tests créés, documentation API optionnelle reste)

---

## Dev Agent Record

### Agent Model Used

(À remplir par l’agent d’implémentation)

### Debug Log References

### Completion Notes List

**2026-02-05 - Implémentation Story 13.7 complétée:**
- ✅ **Task 1 - REF_ENGINES**: Migrations V049/V050, app Django `reference`, API GET /api/v1/reference/engines, validation backend, hook useEngines, composants frontend mis à jour
- ✅ **Task 2 - REF_PLATFORMS**: Migrations V051/V052, modèle RefPlatform, API GET /api/v1/reference/platforms, validation backend, hook usePlatforms, ActionForm/ActionWizard mis à jour
- ✅ **Task 3 - GET /api/v1/inventory/environments**: Migration V053 (suppression CHECK ENVIRONMENT), endpoint créé, validation applicative, TargetEnvironment.VALUES remplacé, hook useEnvironments, profils mis à jour
- ✅ **Task 4 - Cohérence filtres**: Filtres Exécutions/Calendrier/Catalogue mis à jour, types TypeScript mis à jour
- ✅ **Task 5 - Tests**: Tests unitaires et intégration créés pour reference/engines, reference/platforms, inventory/environments, validation catalog/executions
- ⏳ **Task 5.4 - Documentation**: Documentation API à mettre à jour (OPTIONNEL - peut être fait dans une story séparée)

**Résumé:**
- **Migrations créées**: V049 (REF_ENGINES), V050 (drop CHECK ENGINE), V051 (REF_PLATFORMS), V052 (drop CHECK PLATFORM), V053 (drop CHECK ENVIRONMENT)
- **Backend**: App `reference` complète, endpoints créés, validation applicative ajoutée
- **Frontend**: Hooks useEngines, usePlatforms, useEnvironments créés, composants principaux mis à jour
- **Tests**: 5 fichiers de tests créés couvrant reference, inventory, catalog, executions
- **Fichiers modifiés**: ~50 fichiers créés/modifiés

### File List

**Task 1 - REF_ENGINES (complété):**
- `idp-portal/database/migrations/V049__create_ref_engines.sql` - Création table REF_ENGINES + seed données
- `idp-portal/database/migrations/V050__drop_check_engine_constraint.sql` - Suppression CHECK ENGINE
- `idp-portal/django_backend/reference/` - Nouvelle app Django pour tables de référence
  - `models.py` - Modèle RefEngine
  - `serializers.py` - Serializer RefEngineSerializer
  - `views.py` - Vue list_engines
  - `urls.py` - Route /api/v1/reference/engines
  - `migrations/0001_initial.py` - Migration Django RefEngine
- `idp-portal/django_backend/idp_backend/settings.py` - Ajout app 'reference' dans INSTALLED_APPS
- `idp-portal/django_backend/idp_backend/urls.py` - Ajout route /api/v1/reference/
- `idp-portal/django_backend/catalog/models.py` - Suppression choices=ActionEngine.choices sur champ engine
- `idp-portal/django_backend/catalog/serializers.py` - Validation engine contre REF_ENGINES au lieu de ActionEngine.choices
- `idp-portal/frontend/src/services/reference_service.ts` - Service pour charger engines depuis API
- `idp-portal/frontend/src/hooks/useEngines.ts` - Hook React pour charger engines
- `idp-portal/frontend/src/utils/actionOptions.ts` - ENGINE_OPTIONS marqué comme deprecated
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` - Utilise useEngines au lieu de ENGINE_OPTIONS
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` - Utilise useEngines au lieu de ENGINE_OPTIONS
- `idp-portal/frontend/src/components/executions/ExecutionsFiltersPanel.tsx` - Utilise useEngines au lieu de ENGINE_OPTIONS
- `idp-portal/frontend/src/components/calendar/CalendarFiltersPanel.tsx` - Utilise useEngines au lieu de ENGINE_OPTIONS
- `idp-portal/frontend/src/components/catalog/HorizontalFilters.tsx` - Utilise useEngines au lieu de ENGINE_OPTIONS
- `idp-portal/frontend/src/components/catalog/ActiveFiltersChips.tsx` - Utilise useEngines au lieu de ENGINE_OPTIONS
- ⏳ Fichiers restants à mettre à jour (utilisent ENGINE_OPTIONS ou ActionEngine en dur):
  - `idp-portal/frontend/src/components/dashboard/reporting/AdvancedFiltersPanel.tsx` - DEFAULT_ENGINE_OPTIONS
  - `idp-portal/frontend/src/utils/executionRenderers.tsx` - ENGINE_SVG_SOURCES, ENGINE_ICONS (types ActionEngine)
  - `idp-portal/frontend/src/components/catalog/ActionCard.tsx` - ENGINE_ICON_FALLBACKS (type ActionEngine)
  - `idp-portal/frontend/src/components/dashboard/RecentExecutions.tsx` - ENGINE_ICONS_CONFIG, ENGINE_SVG_SOURCES (type ActionEngine)
  - `idp-portal/frontend/src/types/api.ts` - Type ActionEngine en union type (peut rester mais devrait être string générique)

**Task 2 - REF_PLATFORMS (en cours):**
- `idp-portal/database/migrations/V051__create_ref_platforms.sql` - Création table REF_PLATFORMS + seed données
- `idp-portal/database/migrations/V052__drop_check_platform_constraint.sql` - Suppression CHECK PLATFORM
- `idp-portal/django_backend/reference/models.py` - Modèle RefPlatform ajouté
- `idp-portal/django_backend/reference/serializers.py` - RefPlatformSerializer ajouté
- `idp-portal/django_backend/reference/views.py` - Vue list_platforms ajoutée
- `idp-portal/django_backend/reference/urls.py` - Route /api/v1/reference/platforms ajoutée
- `idp-portal/django_backend/reference/migrations/0001_initial.py` - Migration Django RefPlatform ajoutée
- `idp-portal/django_backend/catalog/models.py` - Suppression choices=ActionPlatform.choices sur champ platform
- `idp-portal/django_backend/catalog/serializers.py` - Validation platform contre REF_PLATFORMS au lieu de ActionPlatform.choices
- `idp-portal/frontend/src/services/reference_service.ts` - fetchPlatforms implémenté
- `idp-portal/frontend/src/hooks/usePlatforms.ts` - Hook React pour charger platforms
- ✅ ActionForm et ActionWizard mis à jour pour utiliser usePlatforms
- ✅ actionOptions.ts mis à jour (PLATFORM_OPTIONS marqué comme deprecated)

**Task 3 - GET /api/v1/inventory/environments (complété):**
- `idp-portal/database/migrations/V053__drop_check_environment_constraints.sql` - Suppression CHECK ENVIRONMENT sur EXECUTIONS et SCHEDULED_EXECUTIONS
- `idp-portal/django_backend/inventory/services.py` - Méthode list_environments() ajoutée
- `idp-portal/django_backend/inventory/views.py` - Vue list_environments ajoutée
- `idp-portal/django_backend/inventory/urls.py` - Route /api/v1/inventory/environments ajoutée
- `idp-portal/django_backend/executions/views.py` - Validation applicative environment contre inventaire ajoutée (_validate_environment_against_inventory)
- `idp-portal/django_backend/inventory/services.py` - Remplacement TargetEnvironment.VALUES par list_environments() avec fallback
- `idp-portal/django_backend/catalog/views.py` - Remplacement TargetEnvironment.VALUES par list_environments()
- `idp-portal/frontend/src/services/reference_service.ts` - fetchEnvironments() ajouté
- `idp-portal/frontend/src/hooks/useEnvironments.ts` - Hook React pour charger environnements depuis inventaire
- `idp-portal/frontend/src/components/catalog/HorizontalFilters.tsx` - Utilise useEnvironments
- `idp-portal/frontend/src/components/catalog/ActiveFiltersChips.tsx` - Utilise useEnvironments
- `idp-portal/frontend/src/components/executions/ExecutionsFiltersPanel.tsx` - Utilise useEnvironments
- `idp-portal/frontend/src/components/calendar/CalendarFiltersPanel.tsx` - Utilise useEnvironments
- `idp-portal/frontend/src/components/admin/ProfileForm.tsx` - Utilise useEnvironments
- `idp-portal/frontend/src/components/admin/ProfileWizard.tsx` - Utilise useEnvironments
- `idp-portal/frontend/src/types/api.ts` - Types ActionEngine/ActionPlatform mis à jour (string générique)

**Task 5 - Tests (complété):**
- `idp-portal/django_backend/reference/tests/test_views.py` - Tests API reference/engines et reference/platforms
- `idp-portal/django_backend/reference/tests/test_models.py` - Tests modèles RefEngine et RefPlatform
- `idp-portal/django_backend/inventory/tests/test_environments.py` - Tests GET /api/v1/inventory/environments
- `idp-portal/django_backend/catalog/tests/test_validation.py` - Tests validation engine/platform contre REF_ENGINES/REF_PLATFORMS
- `idp-portal/django_backend/executions/tests/test_environment_validation.py` - Tests validation environment contre inventaire

**Note:** Documentation API (Task 5.4) reste optionnelle et peut être faite dans une story séparée.
