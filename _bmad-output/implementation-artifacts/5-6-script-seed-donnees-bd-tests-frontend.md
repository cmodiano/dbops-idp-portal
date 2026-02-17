# Story 5.6 : Script de seed de données en base pour tests frontend

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **développeur**,
je veux **un script exécutable qui insère un jeu de données de test cohérent en base (seed)**,
afin que **je puisse tester correctement le frontend dans tous les cas : catalogue avec actions variées, profils, intégrations, exécutions dans tous les statuts, favoris, etc.**

## Contexte

La base de dev est souvent vide ou partielle après migration, ce qui ne permet pas de valider tous les écrans et états du frontend (liste vide vs avec données, exécutions en cours / terminées / en erreur, différents types d'actions, profils et permissions). Un script de seed reproductible couvrant tous les cas d'usage frontend est nécessaire.

## Acceptance Criteria

1. **AC1 — Script exécutable**
   **Given** l'environnement de dev (Oracle + app configurée),
   **When** on exécute le script de seed (ex. `scripts/seed_dev_data.py` ou `database/seed/run_seed.sh`),
   **Then** le script s'exécute sans erreur et insère un jeu de données cohérent ; il est idempotent ou documente clairement qu'il ne doit être lancé qu'une fois sur une base vide (ou avec option `--reset` / `--force`).

2. **AC2 — Couverture des entités**
   **Given** le script a été exécuté,
   **Then** la base contient des données pour : utilisateurs (au moins 2–3, dont un DBOPS/DBA), profils (plusieurs avec permissions action/target), tags (plusieurs), actions catalogue (plusieurs, avec étapes d'exécution variées : AAP, ServiceNow, mixte), liaisons action–tags, intégrations (au moins AAP et ServiceNow avec noms/URLs de démo), favoris utilisateur (au moins un utilisateur avec des favoris), exécutions (plusieurs avec statuts variés : SUBMITTED, RUNNING, COMPLETED, FAILED, CANCELLED).

3. **AC3 — Cas frontend couverts**
   **And** avec ce seed, un développeur peut vérifier manuellement : catalogue (liste, filtres par tag, favoris, fiche détail), admin (actions, profils, intégrations), exécutions (liste avec tous les statuts, détail avec timeline/logs/erreur), dashboard (stats et activité récente avec des données), sans avoir à saisir les données à la main.

4. **AC4 — Documentation**
   **And** un README ou une section dans la doc (ex. `idp-portal/README.md` ou `database/seed/README.md`) explique comment lancer le script, sur quelle base (dev uniquement), et quelles données sont créées (résumé par entité).

5. **AC5 — Non-impact production**
   **And** le script est conçu pour la base de dev uniquement (variable d'env ou paramètre explicite) ; pas d'exécution accidentelle sur une base de prod.

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 5) — Choix technique et squelette
  - [x] 1.1 : Choisir l'implémentation : script Python utilisant les repositories existants ou SQL direct (scripts SQL dans `database/seed/`). Préférer Python si les modèles sont complexes (JSON/CLOB) pour réutiliser la logique existante.
  - [x] 1.2 : Créer le point d'entrée (ex. `scripts/seed_dev_data.py` ou `database/seed/run_seed.py`) avec vérification explicite d'environnement (DEV) ou argument `--env=dev`.
  - [x] 1.3 : Documenter que le script ne doit pas être exécuté sur prod.

- [x] Task 2 (AC: 2) — Données à insérer
  - [x] 2.1 : Utilisateurs : 2–3 users (ex. dbops1, dba1, user1) avec profils associés si la table USERS lie aux profils.
  - [x] 2.2 : Profils : au moins 2 profils (ex. DBOPS, DBA) avec permissions (PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS) cohérentes.
  - [x] 2.3 : Tags : 5–10 tags (ex. backup, patching, dev, prod, urgente).
  - [x] 2.4 : Actions catalogue : 5–10 actions avec noms, descriptions, EXECUTION_STEPS (JSON), tags (ACTION_TAGS), statut publié, impact, etc. Varier les connecteurs (AAP, ServiceNow) pour couvrir les différents types.
  - [x] 2.5 : Intégrations : au moins 2 (ex. AAP démo, ServiceNow démo) avec base_url, type, credential_ref (valeur de démo ou vide), auth_flow.
  - [x] 2.6 : Favoris : USER_FAVORITES pour au moins un utilisateur sur plusieurs actions.
  - [x] 2.7 : Exécutions : 10–20 exécutions avec statuts variés (SUBMITTED, RUNNING, COMPLETED, FAILED, CANCELLED), liées aux actions et utilisateurs créés ; EXECUTION_STEPS remplis pour quelques-unes (pour tester timeline/détail).

- [x] Task 3 (AC: 3) — Vérification manuelle
  - [x] 3.1 : Checklist ou section dans le README listant les écrans à tester après seed (catalogue, admin, exécutions, dashboard) et les cas couverts.

- [x] Task 4 (AC: 4) — Documentation
  - [x] 4.1 : README du seed : commande pour lancer, prérequis (migrations à jour, base dev), résumé des données créées (nombre par table ou liste des libellés).

- [x] Task 5 — Idempotence ou sécurité
  - [x] 5.1 : Soit le script est idempotent (vérifier existence avant insert, ou truncate/delete puis insert avec option `--reset`), soit documenter « à lancer une fois sur base vide ».

## Dev Notes

### Contexte technique

- **Epic 5** : Dashboard & Activité (Phase 2). Cette story est une story outillage : script de seed pour faciliter les tests frontend et la démo, sans changer la logique métier.
- **Problème adressé** : Bases vides ou partielles après migration → impossible de valider tous les écrans (catalogue, admin, exécutions, dashboard) sans saisie manuelle.

### Architecture Compliance

- [Source: architecture.md] **Accès données** : SQL brut via python-oracledb ; Repository Pattern. Le script peut soit réutiliser les repositories existants (recommandé pour CLOB/JSON), soit exécuter des scripts SQL dans `database/seed/`.
- [Source: architecture.md] **Connexion DB** : Pool oracledb ou connexion unique ; utiliser la même config que l'application (`app/core/config.py`, variables d'environnement).
- [Source: architecture.md] **Migrations** : Scripts SQL versionnés dans `database/migrations/`. Le seed s'exécute *après* les migrations (prérequis documenté).
- [Source: architecture.md] **Naming** : Tables UPPER_SNAKE_CASE (USERS, ACTIONS_CATALOG, EXECUTIONS, INTEGRATIONS, PROFILES, TAGS, ACTION_TAGS, USER_FAVORITES, PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS, EXECUTION_STEPS). Colonnes UPPER_SNAKE_CASE. Contraintes CHECK sur STATUS et ENVIRONMENT (voir V023, V002, etc.).
- [Source: architecture.md] **Structure projet** : `idp-portal/scripts/` pour scripts exécutables ; `idp-portal/database/seed/` pour données SQL ou script Python de seed. Référencer dans `idp-portal/README.md`.

### Technical Requirements

- **Environnement** : Le script doit refuser de s'exécuter en prod (vérifier `ENVIRONMENT=dev` ou `APP_ENV=dev` ou argument `--env=dev`). Pas de variable par défaut « prod ».
- **Idempotence** : Soit idempotent (vérifier existence des données avant insert ; ou option `--reset` qui truncate/delete puis réinsère), soit clairement documenté « une seule fois sur base vide ».
- **Oracle** : Respecter les contraintes (IDENTITY, CHECK, FK). Pour les CLOB/JSON (PARAMETERS, EXECUTION_STEPS, PARAMETERS_SCHEMA, IMPACT_RULES, etc.), utiliser le même format que l'application (JSON valide).
- **Ordre d'insertion** : Respecter les FK : USERS → PROFILES (si lien) ; TAGS ; ACTIONS_CATALOG ; ACTION_TAGS ; INTEGRATIONS ; PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS ; USER_FAVORITES ; EXECUTIONS ; EXECUTION_STEPS.

### Library / Framework Requirements

- **Python 3.12+** : Même runtime que le backend. Pas de nouvelle dépendance obligatoire : utiliser `oracledb` (déjà dans le backend) et la config app.
- **Réutilisation** : Préférer les repositories existants (`user_repository`, `catalog_repository`, `execution_repository`, `integration_repository`, `profile_repository`, `profile_action_permission_repository`, `profile_target_permission_repository`, `favorites_repository`) pour créer les données si les modèles Pydantic et le format JSON sont alignés — évite la duplication de logique et les erreurs de format.
- **Alternative SQL** : Si script SQL pur dans `database/seed/`, utiliser le même schéma que les migrations (préfixe IDP_APP si applicable, schéma cible documenté).

### Project Structure Notes

- **Emplacement script** : `idp-portal/scripts/seed_dev_data.py` (recommandé si Python) ou `idp-portal/database/seed/run_seed.py`. Si SQL pur : `idp-portal/database/seed/*.sql` + script shell `run_seed.sh` qui enchaîne les fichiers dans l'ordre.
- **Référence README** : Ajouter une section dans `idp-portal/README.md` (ou créer `idp-portal/database/seed/README.md`) : commande pour lancer le seed, prérequis (migrations à jour, base dev), résumé des données créées.
- **Alignement** : Ne pas créer de nouveau package Python hors `scripts/` ; le script peut importer depuis `app` si exécuté depuis la racine du backend (`python -m scripts.seed_dev_data` ou `cd backend && python scripts/seed_dev_data.py` selon structure retenue).

### Référence story précédente (5.5)

- **Story 5.5** (Alignement React & Ant Design 6.2) : Audit frontend, pas de changement backend. Pour 5.6 : le seed alimente les données que le frontend affiche ; après seed, les écrans catalogue, admin, exécutions, dashboard doivent afficher des données cohérentes pour les tests manuels et la non-régression (5.5).

### Testing Requirements

- **Pas de tests unitaires obligatoires** pour le script de seed lui-même. La validation est manuelle : lancer le script, puis vérifier les écrans frontend (AC3).
- **Checklist manuelle** : README ou section doc listant les écrans à vérifier après seed (Catalogue : liste, filtres tags, favoris, fiche ; Admin : actions, profils, intégrations ; Exécutions : liste statuts, détail timeline/logs ; Dashboard : stats, activité récente).
- **Non-régression** : Le seed ne doit pas casser les migrations ni les tests existants (pas de modification des migrations ; le script ne fait qu'INSERT).

### Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md] Stack backend (FastAPI, python-oracledb, Repository Pattern), structure dossiers, naming DB et API.
- [Source: idp-portal/database/migrations/] Schéma exact des tables : V001 (USERS), V002 (ACTIONS_CATALOG), V007 (TAGS, ACTION_TAGS), V010 (PROFILES), V011 (PROFILE_ACTION_PERMISSIONS), V012 (PROFILE_TARGET_PERMISSIONS), V020 (INTEGRATIONS), V021 (USER_FAVORITES), V023 (EXECUTIONS), V025 (EXECUTION_STEPS), etc.
- [Source: idp-portal/backend/app/repositories/] Signatures des repositories pour réutilisation éventuelle (create, get_by_id, etc.).
- [Source: idp-portal/backend/app/core/config.py] Variables d'environnement et connexion DB.

### References

- [Source: idp-portal/database/migrations/] Contraintes CHECK (STATUS, ENVIRONMENT), FK, colonnes CLOB/JSON.
- [Source: idp-portal/backend/app/models/] Modèles Pydantic pour format JSON (parameters_schema, impact_rules, execution steps).
- [Source: _bmad-output/planning-artifacts/architecture.md] Project structure, database/seed, scripts/.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- **Task 1**: Choisi Python avec SQL direct via oracledb (mêmes patterns que les repositories). Script créé à `scripts/seed_dev_data.py` avec vérification env (APP_ENV=development ou --env=dev) et message d'erreur explicite si exécution sur prod.

- **Task 2**: Données complètes insérées :
  - 3 users (dbops1, dba1, user1) avec profils différents
  - 3 profiles (DBOPS admin, DBA, BUSINESS) avec permissions granulaires (ALL, PATTERN, LIST)
  - 8 tags (oracle, patching, backup, dev, prod, urgente, provisioning, monitoring)
  - 2 integrations (AAP Demo, ServiceNow Demo) avec auth_flow et config
  - 8 actions variées (backup, patching, provisioning, monitoring, urgente) avec EXECUTION_STEPS JSON complets, 7 published + 1 draft
  - 5 favoris répartis sur 2 utilisateurs
  - 15 executions avec tous les statuts (COMPLETED×6, FAILED×3, RUNNING×2, SUBMITTED×2, CANCELLED×1, PENDING_APPROVAL×1)
  - 20 execution_steps pour 5 executions (timeline détaillée)

- **Task 3**: Checklist ajoutée dans README : Catalogue (liste, filtres, favoris, détail), Admin (actions, profils, intégrations), Exécutions (liste tous statuts, détail timeline/logs), Dashboard (stats, activité récente).

- **Task 4**: Documentation complète dans README : commande d'exécution, options --env et --reset, tableau récapitulatif des données par entité, écrans à tester.

- **Task 5**: Script idempotent avec option `--reset` qui supprime toutes les données en respectant l'ordre FK inverse avant réinsertion.

### File List

- idp-portal/scripts/seed_dev_data.py (new)
- idp-portal/README.md (modified)

### Change Log

- 2026-01-30: Story completed — Script seed Python créé avec données complètes (users, profiles, tags, actions, integrations, favorites, executions, execution_steps). Documentation ajoutée au README. Option --reset pour idempotence.
- 2026-01-30: Code review (adversarial) — Corrections appliquées : RETURNING INTO (variable de sortie explicite partout), vérification données existantes sans --reset, doc config/env alignée backend, README clarifié (deux façons de lancer, rollback), résumé exécutions basé sur la base.
