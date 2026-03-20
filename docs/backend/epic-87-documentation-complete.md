# Epic 87 — Documentation complète de la solution IDP Portal

**Date :** 2026-03-16  
**Statut :** Backlog  
**Objectif :** Revoir et compléter toute la documentation de la solution IDP Portal en français, structurée dans MkDocs.

---

## Contexte

Le projet utilise MkDocs Material pour la documentation technique. La documentation actuelle est dispersée, partiellement obsolète ou incomplète. Cet epic vise à produire une documentation exhaustive, en français, couvrant l'architecture, le développement et l'exploitation.

**Contraintes :**
- Toute la documentation doit être en **français**
- Documentation **complète** et à jour
- Intégration dans la structure MkDocs existante (`docs/`, `mkdocs.yml`)

---

## Stories

### Story 87-1 : Documentation détaillée de l'architecture des workflows

**Objectif :** Documenter le flow complet des workflows, de la soumission à la complétion, avec le détail des opérations de base de données.

**Contenu à documenter :**
- **Mise en queue des jobs :** Comment une exécution est créée, validée (RBAC, mutex, cibles), et dispatchée vers Celery
- **Traitement asynchrone :** `trigger_platform_job`, `poll_platform_job_status`, résolution des adapters via `AdapterRegistry`
- **Évaluation des gates :** `evaluate_waiting_gates` (Celery Beat 60s), stratégies (approval, maintenance_window), reprise manuelle vs auto
- **Flow complet :** Diagrammes de séquence détaillés (POST /executions → trigger → poll → gate → completion)
- **Opérations BD :** Tables impliquées à chaque étape (EXECUTIONS, EXECUTION_STEPS, RUNNABLE_STEPS, EXECUTION_OUTBOX, WORKFLOW_EVENTS)
- **Patterns :** Transactional Outbox, Work Queue distribué (RUNNABLE_STEPS + lease), Event Sourcing (WORKFLOW_EVENTS)
- **Exécutions planifiées :** `process_pending_scheduled_executions`, RECURRING_PATTERNS, SCHEDULED_EXECUTIONS

**Livrables :**
- `docs/architecture/workflow-execution-flow.md` — Flow détaillé avec diagrammes Mermaid
- Mise à jour de `docs/architecture/workflow-architecture.md` — Enrichir avec les détails manquants

**Critères d'acceptation :**
- [ ] Un développeur peut comprendre le parcours complet d'une exécution sans lire le code
- [ ] Chaque opération BD significative est documentée avec la table et le moment
- [ ] Les diagrammes sont à jour et cohérents avec le code

---

### Story 87-2 : Documentation structure frontend et consommation backend

**Objectif :** Décrire la structure du frontend, comment il consomme le backend, et le fonctionnement des JSON Schemas.

**Contenu à documenter :**
- **Structure du frontend :** Arborescence `src/` (components, pages, services, hooks, types), conventions de nommage
- **Consommation backend :** `api_client.ts` (apiFetch, apiFetchRaw, handleAuthenticatedFetch, retry 401), services par domaine (catalog_service, execution_service, etc.)
- **JSON Schemas :**
  - `parameters_schema` sur ACTIONS_CATALOG — définition des paramètres d'action (draft-07)
  - `useDynamicForm` — génération de formulaires dynamiques depuis le schéma
  - `parametersSchema.ts` — conversion schema ↔ ParameterDefinition pour l'éditeur visuel
  - Validation backend (catalog, integrations) via jsonschema
- **WebSocket :** Connexion temps réel (Django Channels), événements (step_update, execution_complete)
- **Types API :** `src/types/api.ts`, contrats frontend/backend
- **Workflow builder (admin) :** Construction visuelle des workflows, types d'étapes, edges, validation
- **API :** Accès OpenAPI/Swagger, versioning `/api/v1/`, format des erreurs

**Livrables :**
- `docs/frontend/architecture-consumption.md` — Structure + consommation API
- `docs/frontend/json-schemas-guide.md` — Guide des JSON Schemas (paramètres, config intégrations, validation)
- Mise à jour de `docs/api/contracts-frontend.md` et `docs/frontend/api-integration.md`

**Critères d'acceptation :**
- [ ] Un nouveau développeur sait où trouver les services API et comment les appeler
- [ ] Le flux parameters_schema → formulaire dynamique est documenté
- [ ] Les contrats API sont alignés avec le code actuel

---

### Story 87-3 : Documentation architecture des conteneurs Docker

**Objectif :** Documenter à quoi sert chaque conteneur Docker et comment ils interagissent.

**Contenu à documenter :**
- **Conteneurs :**
  - `redis` — Broker Celery, cache applicatif, feature flags, sessions, couche WebSocket
  - `oracle-db` — Base de données (dev/staging uniquement ; prod = DataGuard externe)
  - `backend` — Django + Gunicorn, API REST, WebSocket (Daphne/Channels)
  - `celery-worker` — Exécution asynchrone, queues (aap, azure, github, terraform, default)
  - `celery-beat` — Planificateur (evaluate gates 60s, scheduled executions 60s, health check 3600s)
  - `frontend` — Nginx + React SPA, proxy vers backend
- **Flux réseau :** Diagramme des connexions (utilisateur → LB → frontend → backend → Oracle/Redis ; workers → Redis → plateformes externes)
- **Volumes et persistance :** oracle-data, celery-beat-data, bind mounts (migrations, staticfiles)
- **Différence dev vs prod :** Oracle conteneur vs DataGuard
- **Variables d'environnement par conteneur :** Référence croisée vers la doc dédiée (Story 87-6)

**Livrables :**
- Mise à jour complète de `docs/architecture/container-architecture.md` — Enrichir avec le rôle détaillé de chaque conteneur
- `docs/operations/docker-compose-reference.md` — Référence des services docker-compose (optionnel, ou intégré au doc existant)

**Critères d'acceptation :**
- [ ] Un ops peut expliquer le rôle de chaque conteneur sans lire le docker-compose
- [ ] Les flux réseau sont clairs (qui parle à qui, sur quel port)

---

### Story 87-4 : Documentation de développement — architecture et extensibilité

**Objectif :** Documenter comment l'architecture fonctionne, les registries, et comment ajouter des composants (gates, services, adapters, integrations, platforms).

**Contenu à documenter :**
- **Registries :**
  - `AdapterRegistry` (adapters/registry.py) — platform_type → factory, queue Celery
  - `PlatformRegistry` (platforms/registry.py) — définitions de plateformes, aliases
  - `ServiceRegistry` (services/registry.py) — service_type → factory (Vault, ServiceNow, etc.)
  - `GateDefinitionRegistry` (executions/gates/registry.py) — gate_type → GateDefinition
  - `StepHandlerRegistry` (executions/app/handlers/registry.py) — step_type → handler
- **JSON Schemas :** Où ils sont utilisés (ACTIONS_CATALOG.PARAMETERS_SCHEMA, INTEGRATIONS.CONFIG, INTEGRATION_ACTIONS)
- **Comment ajouter :**
  - Un **adapter** (nouvelle plateforme) — créer classe BaseAdapter, enregistrer dans adapters/__init__.py
  - Un **service** — créer client, enregistrer dans services/__init__.py
  - Un **gate** — GateDefinition + stratégie d'évaluation, enregistrer dans gates/registry.py
  - Une **intégration** — type dans INTEGRATION_TYPE_CATALOGUE, actions dans INTEGRATION_ACTIONS
  - Une **plateforme** — PlatformDefinition, enregistrer dans platforms/__init__.py
- **Injection de dépendances :** core/di.py, utilisation dans les services

**Livrables :**
- `docs/backend/development-extensibility.md` — Guide complet d'extensibilité
- Mise à jour de `docs/reference/development-guide.md` — Lien vers ce guide
- `docs/backend/registry-reference.md` — Référence des registries (ou section dans development-extensibility)

**Critères d'acceptation :**
- [ ] Un développeur peut ajouter un nouveau gate ou adapter en suivant la doc
- [ ] Chaque registry est documentée avec son rôle et son point d'enregistrement

---

### Story 87-5 : Documentation schéma de base de données

**Objectif :** Documenter le schéma BD avec toutes les tables et leurs descriptions.

**Contenu à documenter :**
- **Vue d'ensemble :** 28+ tables, 6 domaines fonctionnels, Flyway migrations
- **Par table :** Nom, colonnes (type, contraintes), description, relations (FK), index, requêtes courantes
- **Domaines :** Utilisateurs (USERS), Profils (PROFILES, PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS), Catalogue (ACTIONS_CATALOG, TAGS, ACTION_TAGS), Exécutions (EXECUTIONS, EXECUTION_STEPS, EXECUTION_TARGETS, SCHEDULED_EXECUTIONS, RECURRING_PATTERNS), Intégrations (INTEGRATIONS, INTEGRATION_TYPE_CATALOGUE, INTEGRATION_ACTIONS), Audit (AUDIT_LOG)
- **Tables techniques :** RUNNABLE_STEPS, EXECUTION_OUTBOX, WORKFLOW_EVENTS, CORE_FEATURE_FLAGS
- **Contraintes métier :** RBAC cumul multi-profils, AUDIT_LOG append-only, transitions d'état EXECUTIONS
- **Diagramme ER :** Complet et à jour

**Livrables :**
- Mise à jour complète de `docs/backend/database-schema.md` — Vérifier exhaustivité, ajouter tables manquantes, traduire en français si besoin
- `docs/backend/database-tables-reference.md` — Référence table par table (ou intégré au database-schema.md)

**Critères d'acceptation :**
- [ ] Toutes les tables du schéma sont documentées
- [ ] Chaque colonne importante a une description
- [ ] Le diagramme ER reflète l'état actuel (V137+)

---

### Story 87-6 : Référence des variables d'environnement

**Objectif :** Documenter l'ensemble des variables d'environnement nécessaires au bon fonctionnement, par composant et par contexte (dev / staging / prod).

**Contenu à documenter :**
- **Backend (Django) :** SECRET_KEY, JWT_SECRET_KEY, ORACLE_DSN/USER/PASSWORD, REDIS_URL, CELERY_BROKER_URL, CACHE_BACKEND, CORS_ORIGIN, WEBSOCKET_ALLOWED_ORIGINS, DEBUG, AUTH_DEV_BYPASS, ALLOWED_HOSTS
- **Authentification :** SAML_*, JWT_*, LDAP_*, PORTAL_AUTH_METHODS, PORTAL_REQUIRED_GROUPS
- **Services externes :** VAULT_ADDR, SERVICENOW_INSTANCE_URL, AAP_*, etc.
- **Celery :** CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_ALWAYS_EAGER
- **Celery Beat :** CELERY_BEAT_EVALUATE_GATES_INTERVAL, CELERY_BEAT_PROCESS_SCHEDULED_EXECUTIONS_INTERVAL, CELERY_BEAT_HEALTH_CHECK_INTERVAL, CELERY_BEAT_*_CRONTAB, CELERY_BEAT_PURGE_*, etc.
- **Channels/WebSocket :** CHANNEL_LAYER_BACKEND, CHANNEL_REDIS_URL
- **Feature flags :** FEATURE_FLAGS_SOURCE, FEATURE_FLAGS_ENABLED, FEATURE_FLAGS_CACHE_TTL, FEATURE_FLAGS
- **Rate limiting :** RATELIMIT_ENABLED, THROTTLE_*_RATE
- **Résilience :** DB_CONN_MAX_AGE, DB_RETRY_*, AAP_SOCKET_TIMEOUT, TOWER_SOCKET_TIMEOUT, etc.
- **Simulation dev :** SIMULATE_EXECUTION_DEV, SIMULATE_EXECUTION_STEP_DURATION
- **Frontend :** VITE_* (mode, API URL si applicable)
- **Docker Compose :** ORACLE_PASSWORD, ORACLE_IMAGE_TAG, variables injectées par conteneur
- **Observabilité :** LOG_LEVEL, LOG_FORMAT, SPLUNK_*, variables structlog

**Format :** Tableau par variable (nom, composant, requis/optionnel, défaut, description, dev vs prod)

**Livrables :**
- `docs/operations/environment-variables-reference.md` — Référence exhaustive (ou `docs/reference/environment-variables.md`)
- Mise à jour de `docs/operations/exploitation-production.md` § 3 — Lien vers la référence, compléter les variables manquantes
- Optionnel : section dans `docs/architecture/container-architecture.md` — Variables par conteneur (résumé + lien)

**Critères d'acceptation :**
- [ ] Toute variable utilisée dans settings.py, celery.py ou docker-compose est documentée
- [ ] Un ops peut configurer un nouvel environnement en suivant la doc
- [ ] Les variables critiques (SECRET_KEY, JWT, Oracle, Vault) sont clairement identifiées

---

### Story 87-7 : Guide d'onboarding et développement local

**Objectif :** Permettre à un nouveau contributeur de démarrer rapidement avec un environnement fonctionnel.

**Contenu à documenter :**
- **Prérequis :** Node.js LTS, Python 3.12+, Oracle 19c+ (ou Docker), Redis, uv (optionnel)
- **Premier lancement :** Étapes pas à pas (clone, .env, migrations Flyway, npm install, docker-compose up)
- **Docker Compose vs natif :** Quand utiliser quoi, différences de config
- **Tests :** Lancer pytest (backend), Vitest (frontend), commandes, structure des tests, factories/fixtures
- **Migrations :** Cohabitation Flyway / Django ORM, comment ajouter une migration, ordre d'exécution en déploiement
- **Conventions :** Pre-commit (mypy, detect-secrets), linters (ruff, ESLint), nommage, branches
- **Problèmes courants :** Oracle lent au démarrage, port 6379 occupé, CORS, etc.

**Livrables :**
- `docs/reference/onboarding-guide.md` — Guide complet d'onboarding
- Mise à jour de `docs/reference/development-guide.md` — Enrichir avec tests, migrations, troubleshooting

**Critères d'acceptation :**
- [ ] Un nouveau contributeur peut avoir l'app qui tourne en < 30 min en suivant la doc
- [ ] Les commandes de test sont documentées et fonctionnelles

---

### Story 87-8 : Documentation RBAC et inventaire

**Objectif :** Documenter le modèle RBAC et le système d'inventaire des cibles en détail.

**Contenu à documenter :**
- **RBAC :** Cumul des permissions multi-profils (ALL / LIST / PATTERN), exemples concrets (profil DBA vs DevOps)
- **ProfileService.get_cumulative_permissions()** — Logique documentée
- **Workflow d'approbation :** Prod vs dev, transitions PENDING_APPROVAL → RUNNING / REJECTED
- **Inventaire :** Sources de données (API, DB), synchronisation, validation des cibles
- **EXECUTION_TARGETS :** Rôle, usage pour mutex et validation RBAC par cible
- **Permissions par cible :** Target patterns (TARGET_NAMES_JSON, TARGET_PATTERNS_JSON), ALL
- **Règles métier :** Impact rules par environnement, mutex sur cibles, règles de remédiation

**Livrables :**
- `docs/backend/rbac-detailed.md` — Modèle RBAC complet avec exemples
- `docs/backend/inventory-and-targets.md` — Inventaire, cibles, EXECUTION_TARGETS
- Mise à jour de `docs/backend/database-schema.md` — Section contraintes métier RBAC

**Critères d'acceptation :**
- [ ] Un admin peut configurer un profil et comprendre l'effet des permissions
- [ ] Le lien inventaire → cibles → mutex → RBAC est clair

---

### Story 87-9 : Documentation intégrations externes (flow métier)

**Objectif :** Documenter le flow métier de chaque intégration avec les plateformes externes.

**Contenu à documenter :**
- **AAP / Ansible Tower :** Trigger job → poll status → récupération outputs, resource_type (job_template vs workflow_job)
- **ServiceNow :** Création changement, états, approbation, code modèle par environnement
- **Vault :** Résolution des secrets (credential_ref), cache, circuit breaker, secret 0 (bootstrap)
- **Terraform Cloud :** Trigger run → poll → outputs
- **GitHub Actions, Azure DevOps :** Flow spécifique (webhook, API)
- **Tableau récapitulatif :** Plateforme, protocole, timeout, variables d'environnement

**Livrables :**
- `docs/integrations/flows-by-platform.md` — Flow métier par plateforme
- Mise à jour de `docs/integrations/index.md` — Lien vers les flows détaillés

**Critères d'acceptation :**
- [ ] Un développeur comprend comment une exécution interagit avec chaque plateforme
- [ ] Les timeouts et points de défaillance sont documentés

---

### Story 87-10 : Documentation observabilité et runbooks

**Objectif :** Documenter l'observabilité (logs, audit, health) et les runbooks de dépannage.

**Contenu à documenter :**
- **Logging :** Structlog, format JSON, propagation correlation_id, variables LOG_LEVEL, LOG_FORMAT
- **Splunk :** HEC endpoint, configuration, variables SPLUNK_*
- **Audit trail :** AUDIT_LOG, types d'événements, immutabilité, export
- **Health checks :** Endpoints (`/api/v1/health/`), ce qu'ils vérifient (DB, Redis, Vault), seuils
- **Checklist secrets avant déploiement :** SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD, VAULT_*, certificats SAML
- **Runbooks :** Exécution bloquée (diagnostic), Celery worker inactif, Oracle connexion, Vault indisponible
- **CI/CD :** Structure des pipelines (.github/workflows), étapes (build, test, deploy)

**Livrables :**
- `docs/operations/observability.md` — Logging, Splunk, audit, health checks
- `docs/operations/runbooks-troubleshooting.md` — Runbooks de dépannage
- `docs/operations/pre-deployment-checklist.md` — Checklist secrets et config
- Mise à jour de `docs/operations/exploitation-production.md` — Liens vers ces docs

**Critères d'acceptation :**
- [ ] Un ops peut tracer une exécution de bout en bout via les logs
- [ ] Les incidents courants ont un runbook documenté

---

## Ordre de priorité suggéré

1. **87-5** (Schéma BD) — Base de référence pour les autres docs
2. **87-6** (Variables d'environnement) — Critique pour déploiement et onboarding
3. **87-7** (Onboarding) — Réduit le time-to-first-contribution
4. **87-1** (Workflows) — Cœur métier, le plus complexe
5. **87-3** (Conteneurs) — Indépendant, utile pour le déploiement
6. **87-2** (Frontend) — Dépend du backend mais peut être fait en parallèle
7. **87-8** (RBAC et inventaire) — Cœur métier permissions
8. **87-4** (Extensibilité) — Synthèse des registries
9. **87-9** (Intégrations) — Flow métier plateformes
10. **87-10** (Observabilité et runbooks) — Support et exploitation

---

## Références

- `docs/architecture/workflow-architecture.md` — Existant
- `docs/architecture/container-architecture.md` — Existant
- `docs/backend/database-schema.md` — Existant
- `docs/frontend/api-integration.md` — Existant
- `docs/api/contracts-frontend.md` — Existant
- `idp-portal/docker-compose.yml` — Définition des services
- `idp-portal/django_backend/adapters/registry.py` — AdapterRegistry
- `idp-portal/django_backend/executions/gates/registry.py` — GateRegistry
- `idp-portal/django_backend/services/registry.py` — ServiceRegistry
- `idp-portal/django_backend/platforms/registry.py` — PlatformRegistry
