# Story 2.19: Setup environnement Oracle dev avec Docker

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developpeur,
I want un environnement Oracle local via Docker Compose,
So that je peux tester les operations CRUD et valider le comportement de la base de donnees en developpement.

## Acceptance Criteria

1. **AC1 — Container Oracle au demarrage**
   **Given** un developpeur clone le repo,
   **When** il execute `docker-compose up -d oracle` (ou `docker compose up -d oracle`),
   **Then** un container Oracle Free (ou XE) demarre sur le port 1521,
   **And** les migrations s'appliquent automatiquement au demarrage (ou via script documente).

2. **AC2 — Tests d'integration CRUD**
   **Given** le container Oracle est demarre,
   **When** le developpeur execute les tests d'integration,
   **Then** les tests peuvent inserer, modifier et supprimer des donnees dans des tables representatives (ex. USERS, PROFILES).

3. **AC3 — Persistance des donnees**
   **Given** le container Oracle est arrete,
   **When** le developpeur relance `docker-compose up -d oracle`,
   **Then** les donnees persistees sont restaurees (volume Docker).

4. **AC4 — Configuration et documentation**
   **And** le fichier docker-compose.yml inclut le service Oracle avec volume persistant.
   **And** un script init.sql ou entrypoint applique les migrations (ou README indique d'appeler run_migrations.sh apres demarrage).
   **And** le README documente le setup dev avec les commandes essentielles (Oracle, backend, frontend).
   **And** les variables d'environnement (user, password, SID/Service) sont configurables via .env.

## Tasks / Subtasks

- [x] Task 1: Docker Compose Oracle (AC: 1, 3, 4)
  - [x] 1.1: Creer ou completer `idp-portal/docker-compose.yml` avec un service `oracle` (image officielle Oracle Free ou gvenzl/oracle-xe, port 1521 expose).
  - [x] 1.2: Definir un volume nomme pour les donnees Oracle (persistance).
  - [x] 1.3: Documenter les variables d'environnement (ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD) et fournir un `.env.example` a jour si besoin.
  - [x] 1.4: Choisir strategie migrations : entrypoint/init qui appelle run_migrations.sh apres Oracle ready, ou instructions README pour lancer run_migrations.sh manuellement apres premier demarrage.

- [x] Task 2: Appliquer les migrations au demarrage (AC: 1)
  - [x] 2.1: Si entrypoint : attendre que Oracle soit pret (healthcheck ou script wait-for), puis executer `./scripts/run_migrations.sh` (ou un script wrapper dans le container).
  - [x] 2.2: Alternativement : documenter dans README la sequence `docker-compose up -d oracle`, attendre ~1-2 min, puis `ORACLE_DSN=... ORACLE_USER=... ORACLE_PASSWORD=... ./scripts/run_migrations.sh` depuis l'hote.
  - [x] 2.3: S'assurer que run_migrations.sh reste utilisable avec les memes variables (ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD).

- [x] Task 3: Tests d'integration (AC: 2)
  - [x] 3.1: Verifier que les tests d'integration backend (s'il en existe) utilisent la config Oracle (.env ou variables) et passent contre le container.
  - [x] 3.2: Si aucun test d'integration CRUD : ajouter un test minimal (connexion + INSERT/SELECT sur une table existante) pour valider le setup.
  - [x] 3.3: Documenter dans README comment lancer les tests avec Oracle Docker (ex: `docker-compose up -d oracle && pytest backend/tests/integration/ ...`).

- [x] Task 4: README et .env (AC: 4)
  - [x] 4.1: Mettre a jour `idp-portal/README.md` avec une section "Environnement de developpement" : demarrage Oracle (docker-compose), backend (fastapi dev), frontend (npm run dev), et migrations.
  - [x] 4.2: Indiquer les valeurs .env typiques pour Oracle local (ex: ORACLE_DSN=localhost:1521/FREEPDB1 ou selon image, ORACLE_USER, ORACLE_PASSWORD).
  - [x] 4.3: Rappeler que .env ne doit pas etre commit (deja dans .gitignore); .env.example peut lister les cles sans valeurs sensibles.

## Developer Context

- **Contexte** : Story technique (tech debt / setup dev). Pas de changement de code applicatif frontend/backend API; uniquement infrastructure locale (Docker Oracle + doc + tests integration).
- **Livrables attendus** : `idp-portal/docker-compose.yml` avec service Oracle + volume; README mis a jour (setup dev, commandes Oracle/backend/frontend/migrations); .env.example a jour si besoin; tests d'integration passant contre Oracle Docker.
- **Risques** : Image Oracle lourde et lente au premier pull; selon l'image, le service name (FREEPDB1, XEPDB1) et le compte system peuvent varier — documenter clairement les valeurs pour idp_app.

### Technical Requirements

- **Docker** : Utiliser Docker Compose v2 syntax (`services:`, `volumes:`). Exposer le port 1521 sur l'hote pour que le backend et run_migrations.sh (sur l'hote) puissent se connecter.
- **Oracle** : Image compatible dev (Oracle Free ou oracle-xe). Creer si besoin un utilisateur/schema `idp_app` avec droits sur les tables du portail (ou utiliser un utilisateur existant selon l'image); run_migrations.sh cree les objets.
- **Migrations** : Ne pas modifier `scripts/run_migrations.sh` ni les fichiers dans `database/migrations/`. Soit appeler run_migrations.sh depuis l'hote apres demarrage du container, soit depuis un script d'entrypoint dans un second service ou dans l'image Oracle si l'image le permet.
- **Config** : Backend utilise `oracle_dsn`, `oracle_user`, `oracle_password` (config.py). ORACLE_DSN format typique : `localhost:1521/FREEPDB1` ou `localhost:1521/XEPDB1`. Documenter dans README et .env.example.

### Architecture Compliance

- **Structure** : Conserver `idp-portal/` comme racine (frontend/, backend/, database/, scripts/). Ajouter `docker-compose.yml` a la racine de idp-portal. Architecture doc mentionne "docker-compose.yml — Dev environment".
- **Migrations** : Scripts SQL versionnes dans `database/migrations/` (V000–V013); execution via run_migrations.sh; pas d'Alembic. Story 2.20 introduira Flyway plus tard.
- **Conventions** : Pas de changement aux patterns API/backend/frontend; uniquement ajout d'infra et doc.

### Library / Framework Requirements

- **Docker** : Docker Engine et Docker Compose (v2) sur la machine dev. Aucune librairie applicative nouvelle (Python/Node) pour cette story.
- **Oracle** : python-oracledb (mode Thin) deja utilise par le backend; pas de changement de version pour cette story.

### File Structure Requirements

- **Fichiers a creer/modifier** :
  - `idp-portal/docker-compose.yml` (creer ou completer avec service oracle + volume).
  - `idp-portal/README.md` (section "Environnement de developpement" ou "Demarrage rapide" etendue).
  - `idp-portal/.env.example` (mettre a jour avec ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD si absent).
- **Ne pas deplacer** : database/migrations/, scripts/run_migrations.sh, backend/app/core/config.py (uniquement doc/configuration externe).

### Testing Requirements

- **Tests d'integration** : S'assurer que les tests backend qui touchent Oracle peuvent s'executer contre le container (variables d'environnement pointant vers localhost:1521). Si aucun test d'integration existant : ajouter un test minimal (connexion + une requete SELECT ou INSERT/SELECT) pour valider le setup.
- **Pas de tests unitaires** pour docker-compose ou README; focus sur un test d'integration CRUD ou connexion.

### Previous Story Intelligence (2-18)

- Story 2-18 (Editeur visuel des regles d'impact) a modifie le frontend admin (ImpactRulesEditor, ActionForm, AdminPreview). Aucun impact direct sur 2-19 : 2-19 est purement infra (Docker Oracle + doc + tests). Les migrations existantes (V000–V013) incluent deja les tables necessaires au catalogue et RBAC; run_migrations.sh reste le point d'entree unique pour appliquer les migrations.

### Project Context Reference

- **Projet** : IDP Portal — Internal Developer Platform pour operations base de donnees. Stack : React 19 + Vite + Ant Design 6 (frontend), FastAPI + python-oracledb + Pydantic v2 (backend), Oracle DB.
- **Emplacement** : Monorepo sous `idp-portal/`. README actuel decrit demarrage frontend/backend mais pas Oracle; cette story comble le manque pour le dev local.

### Story Completion Status

- **Status** : done.
- **Definition of Done** : docker-compose up -d oracle demarre Oracle et les migrations sont applicables (automatiquement ou via README); tests d'integration passent contre le container; README et .env.example documentent le setup dev. Aucune regression sur l'app existante.

---

## Dev Notes

- **Objectif** : Permettre aux developpeurs de faire tourner Oracle en local via Docker pour dev et tests sans dependre d'une instance partagee.
- **Images Oracle** : Oracle Database Free (container-registry.oracle.com) ou alternatives communautaires (ex: gvenzl/oracle-xe). Choisir une image avec licence compatible (Free = usage dev/test). Port standard 1521; service name souvent XEPDB1 ou FREEPDB1 selon l'image.
- **Migrations existantes** : `idp-portal/scripts/run_migrations.sh` execute tous les `.sql` dans `database/migrations/` dans l'ordre; il attend ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD. Ne pas modifier la logique des migrations; uniquement fournir un moyen de les lancer contre le container.
- **Config backend** : `backend/app/core/config.py` lit `oracle_dsn`, `oracle_user`, `oracle_password` (pydantic-settings, prefix vide). Valeurs par defaut : localhost:1521/FREEPDB1, idp_app, changeme. Le .env doit permettre de surcharger pour pointer vers le container (host = localhost si Docker sur la meme machine, port 1521 mappe).
- **Pas de Flyway** : La story 2.20 introduira le refactoring Flyway et identity columns. Pour 2.19, conserver le mecanisme actuel (run_migrations.sh + scripts SQL existants).

### Project Structure Notes

- **docker-compose.yml** : a la racine de `idp-portal/` (conforme a la structure Architecture : "docker-compose.yml — Dev environment").
- **database/migrations/** : deja en place (V000 à V013); aucun nouveau fichier de migration requis pour cette story.
- **scripts/run_migrations.sh** : inchange en logique; peut etre invoque depuis l'hote ou depuis un container d'init.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md] Starter Template, Database (Oracle python-oracledb), Project Structure (docker-compose.yml Dev environment), Development Workflow.
- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.19 — Setup environnement Oracle dev avec Docker (critères d'acceptation).
- [Source: idp-portal/scripts/run_migrations.sh] Variables ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD; execution sequentielle des SQL dans database/migrations/.
- [Source: idp-portal/backend/app/core/config.py] oracle_dsn, oracle_user, oracle_password (valeurs par defaut dev).

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- **Task 1** : `docker-compose.yml` cree avec service `oracle` (gvenzl/oracle-xe:21-slim), port 1521, volume nomme `oracle_data`, montage `database/init` vers `/container-entrypoint-initdb.d` pour creer l'utilisateur `idp_app` au premier demarrage. Variables documentees dans README et .env.example (ORACLE_DSN=localhost:1521/XEPDB1 pour Docker).
- **Task 2** : Strategie README : demarrage Oracle, attente 1–2 min, puis `run_migrations.sh` depuis l'hote avec ORACLE_DSN/USER/PASSWORD. `run_migrations.sh` inchange.
- **Task 3** : Tests d'integration dans `backend/tests/integration/test_oracle_crud.py` : connexion + SELECT DUAL, SELECT SCHEMA_VERSION, INSERT/UPDATE/SELECT/DELETE USERS, INSERT/UPDATE/SELECT/DELETE PROFILES. Fixture `skip_if_no_oracle` centralisee dans conftest.py. Nettoyage garanti en finally pour eviter donnees residuelles.
- **Task 4** : README mis a jour avec section "Environnement de developpement" (Oracle Docker, migrations, backend, frontend, variables .env, tests avec Oracle). Section Backend : rappel ORACLE_DSN=XEPDB1 pour Docker et reference .env.example. Commande pytest precisee (depuis racine idp-portal/ : cd backend && ...).
- **Code Review (AI)** : Correctifs appliques — AC2 assoupli « tables representatives » (USERS + PROFILES) ; test USERS etendu avec UPDATE et nettoyage en finally ; test CRUD PROFILES ajoute ; fixture duplicate supprimee (conftest uniquement) ; .env.example mis a jour (ORACLE_DSN=XEPDB1) ; README Backend + hint XEPDB1 et chemin pytest.

### File List

- idp-portal/docker-compose.yml
- idp-portal/database/init/01-create-idp-app-user.sql
- idp-portal/README.md
- idp-portal/backend/tests/integration/conftest.py
- idp-portal/backend/tests/integration/test_oracle_crud.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-19-setup-environnement-oracle-dev-avec-docker.md
