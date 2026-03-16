# Architecture des Workflows - IDP Portal

## Vue d'ensemble

L'IDP Portal est un portail interne de développeur (Internal Developer Platform) conçu pour orchestrer des opérations de bases de données à travers un système de workflows. Il permet aux équipes de déclencher, planifier, approuver et surveiller des actions automatisées sur l'infrastructure de bases de données.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React SPA)                           │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Catalogue │ │ Exécutions│ │Calendrier│ │Dashboard │ │Administration│ │
│  │ Actions   │ │ & Logs    │ │Planifié  │ │Analytics │ │  & Audit    │ │
│  └─────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬──────┘ │
│        │              │            │             │              │        │
│        └──────────────┴────────────┴─────────────┴──────────────┘        │
│                                    │                                     │
│                          API Client (Axios)                              │
│                          WebSocket Client                                │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ HTTPS / WSS
┌────────────────────────────────────┼─────────────────────────────────────┐
│                          BACKEND (Django/DRF)                            │
│                                    │                                     │
│  ┌─────────────────────────────────┴──────────────────────────────────┐  │
│  │                        API REST (DRF)                              │  │
│  │  /api/v1/catalog/  /api/v1/executions/  /api/v1/integrations/     │  │
│  │  /api/v1/admin/    /api/v1/auth/        /api/v1/webhooks/         │  │
│  └────────────┬───────────────────────────────────────────────────────┘  │
│               │                                                          │
│  ┌────────────┴────────────────────────────────────────────────────────┐ │
│  │                     COUCHE SERVICES                                 │ │
│  │  ┌───────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────────┐  │ │
│  │  │ Catalog   │ │  Execution   │ │Integration │ │   Profile     │  │ │
│  │  │ Service   │ │  Service     │ │  Service   │ │   Service     │  │ │
│  │  └───────────┘ └──────┬───────┘ └────────────┘ └───────────────┘  │ │
│  │                       │                                            │ │
│  │  ┌────────────────────┴──────────────────────────────────────────┐ │ │
│  │  │            CONTAINER WORKFLOW RUNTIME                         │ │ │
│  │  │                                                               │ │ │
│  │  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐  │ │ │
│  │  │  │ Step        │  │ Gate         │  │ State Machine       │  │ │ │
│  │  │  │ Handlers    │  │ Strategies   │  │ (transitions)       │  │ │ │
│  │  │  ├─────────────┤  ├──────────────┤  └─────────────────────┘  │ │ │
│  │  │  │ Platform    │  │ Approval     │                           │ │ │
│  │  │  │ ServiceCall │  │ Condition    │  ┌─────────────────────┐  │ │ │
│  │  │  │ HttpRequest │  │ Sensor       │  │ Template Resolver   │  │ │ │
│  │  │  │ Evaluation  │  └──────────────┘  │ (Jinja2 mappings)   │  │ │ │
│  │  │  │ Gate        │                    └─────────────────────┘  │ │ │
│  │  │  │ SchedExec   │                                             │ │ │
│  │  │  └─────────────┘                                             │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                     CELERY (Workers Async)                        │  │
│  │  ┌────────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐ │  │
│  │  │ trigger_   │ │ evaluate_    │ │ poll_     │ │ reconcile_   │ │  │
│  │  │ action     │ │ waiting_     │ │ execution │ │ workflow     │ │  │
│  │  │ execution  │ │ gates (60s)  │ │ _status   │ │              │ │  │
│  │  └────────────┘ └──────────────┘ └───────────┘ └──────────────┘ │  │
│  │  ┌────────────┐ ┌──────────────┐ ┌───────────────────────────┐  │  │
│  │  │ process_   │ │ dispatch_    │ │ health_check_             │  │  │
│  │  │ scheduled  │ │ outbox       │ │ all_integrations          │  │  │
│  │  │ executions │ │ _events      │ │                           │  │  │
│  │  └────────────┘ └──────────────┘ └───────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐   │
│  │ Django Channels │  │ SAML 2.0 / JWT │  │ Structured Logging     │   │
│  │ (WebSocket)     │  │ Authentication │  │ (structlog → Splunk)   │   │
│  └────────────────┘  └────────────────┘  └────────────────────────┘   │
└────────────┬──────────────────┬──────────────────┬────────────────────┘
             │                  │                  │
┌────────────┴───┐  ┌──────────┴───┐  ┌───────────┴──────────────────┐
│  Oracle 19c+   │  │    Redis     │  │  Plateformes Externes        │
│                │  │              │  │  ┌─────┐ ┌──────────────────┐ │
│ EXECUTIONS     │  │ Cache        │  │  │ AAP │ │ ServiceNow       │ │
│ EXECUTION_STEPS│  │ Broker Celery│  │  └─────┘ └──────────────────┘ │
│ WORKFLOW_*     │  │ WebSocket    │  │  ┌─────────────┐ ┌──────────┐ │
│ AUDIT_LOG      │  │ Feature Flags│  │  │ Terraform   │ │ GitHub   │ │
│ ACTIONS_CATALOG│  │ Sessions     │  │  │ Cloud       │ │ Actions  │ │
│ INTEGRATIONS   │  │              │  │  └─────────────┘ └──────────┘ │
│ PROFILES       │  │              │  │  ┌───────┐ ┌────────────────┐ │
│ USERS          │  │              │  │  │ Vault │ │ Azure DevOps   │ │
└────────────────┘  └──────────────┘  │  └───────┘ └────────────────┘ │
                                      └──────────────────────────────┘
```

---

## Composants principaux

### 1. Frontend (React SPA)

| Composant | Rôle |
|-----------|------|
| **Catalogue** | Navigation, recherche et filtrage des actions disponibles |
| **Exécutions** | Suivi en temps réel des exécutions, logs par étape, approbations |
| **Calendrier** | Vue calendrier des exécutions planifiées (FullCalendar) |
| **Dashboard** | Analytiques, tendances et statistiques (Recharts) |
| **Administration** | Gestion des actions, profils, intégrations (admin seulement) |
| **Audit** | Consultation et export du journal d'audit (auditeur+) |
| **Workflow Visualizer** | Diagramme interactif du DAG de workflow (XYFlow) |

Technologies : React 19, TypeScript 5.9, Vite 7, Ant Design 6

### 2. Backend (Django REST Framework)

| Module | Rôle |
|--------|------|
| **catalog** | Gestion du catalogue d'actions et définitions de workflows |
| **executions** | Moteur d'exécution, runtime de workflows, gates, step handlers |
| **integrations** | Connexions aux plateformes externes (AAP, ServiceNow, Terraform, etc.) |
| **profiles** | Gestion des profils RBAC et permissions |
| **idp_auth** | Authentification SAML 2.0, JWT, clés API |
| **inventory** | Synchronisation et validation des cibles/hôtes |
| **core** | Audit, feature flags, middleware, injection de dépendances |

Technologies : Django 5.2, DRF, Celery 5.6, Django Channels 4.3

### 3. Base de données (Oracle 19c+)

Migrations gérées par Flyway (V000 à V136). Tables partitionnées mensuellement pour les données volumineuses.

---

## Schéma de la base de données

### Tables principales et leurs relations

```
┌──────────────────────┐       ┌──────────────────────────┐
│       USERS          │       │       PROFILES            │
│──────────────────────│       │──────────────────────────│
│ ID (PK)              │◄──┐   │ ID (PK)                  │
│ USERNAME             │   │   │ NAME                     │
│ EMAIL                │   │   │ IS_ADMIN                 │
│ SAML_NAME_ID         │   │   │ IS_AUDITOR               │
│ IS_ACTIVE            │   │   │ IS_APPROVER              │
│ LAST_LOGIN           │   │   │ NAVIGATION_TABS (JSON)   │
└──────────────────────┘   │   └────────────┬─────────────┘
                           │                │
                           │   ┌────────────┴──────────────┐
                           │   │PROFILE_ACTION_PERMISSIONS  │
                           │   │───────────────────────────│
                           │   │ PROFILE_ID (FK→PROFILES)  │
                           │   │ ACTION_ID (FK→ACTIONS)    │
                           │   │ PERMISSION (ALLOW/DENY)   │
                           │   └───────────────────────────┘
                           │
                           │   ┌────────────────────────────┐
                           │   │PROFILE_TARGET_PERMISSIONS   │
                           │   │────────────────────────────│
                           │   │ PROFILE_ID (FK→PROFILES)   │
                           │   │ TARGET_PATTERN             │
                           │   │ PERMISSION (ALLOW/DENY)    │
                           │   └────────────────────────────┘
                           │
┌──────────────────────┐   │   ┌──────────────────────────┐
│   ACTIONS_CATALOG    │   │   │   INTEGRATIONS           │
│──────────────────────│   │   │──────────────────────────│
│ ID (PK)              │   │   │ ID (PK)                  │
│ NAME                 │   │   │ NAME                     │
│ DESCRIPTION          │   │   │ INTEGRATION_TYPE         │
│ ITEM_TYPE            │   │   │ BASE_URL                 │
│ STATUS (DRAFT/PUB.)  │   │   │ CREDENTIALS (encrypted)  │
│ IS_CONTAINER         │   │   │ HEALTH_STATUS            │
│ INTEGRATION_ID (FK)──┼───┼──►│ LAST_HEALTH_CHECK        │
│ WORKFLOW_TEMPLATE    │   │   └──────────────────────────┘
│ CREATED_BY (FK)──────┼───┘
└───────────┬──────────┘
            │
            │ 1:1
┌───────────┴──────────────┐
│  WORKFLOW_DEFINITIONS    │
│──────────────────────────│
│ ID (PK)                  │
│ ACTION_ID (FK, UNIQUE)   │
│ VERSION                  │
│ CREATED_AT               │
└───────────┬──────────────┘
            │ 1:N
┌───────────┴──────────────┐
│    WORKFLOW_STEPS        │
│──────────────────────────│
│ ID (PK)                  │
│ WORKFLOW_DEFINITION_ID   │
│ STEP_ID (unique/wf)     │
│ STEP_ORDER               │
│ STEP_NAME                │
│ STEP_TYPE                │──── platform | service_call | http_request
│ REFERENCED_ACTION_ID     │     evaluation | gate | schedule_execution
│ INTEGRATION_TYPE         │
│ OPERATION                │
│ INPUT_MAPPING (JSON)     │
│ OUTPUT_MAPPING (JSON)    │
│ CONDITION                │
│ RETRY_ENABLED            │
│ RETRY_MAX_ATTEMPTS       │
│ RETRY_INTERVAL_SECONDS   │
│ RETRY_BACKOFF_MULTIPLIER │
│ JOIN_POLICY              │
└───────────┬──────────────┘
            │ N:M (via edges)
┌───────────┴──────────────┐
│  WORKFLOW_STEP_EDGES     │
│──────────────────────────│
│ ID (PK)                  │
│ FROM_STEP_ID (FK)        │
│ TO_STEP_ID (FK)          │
│ EDGE_TYPE ───────────────┤── success | error
└──────────────────────────┘

┌──────────────────────────┐
│      EXECUTIONS          │  ◄── Partitionné par CREATED_AT (mensuel)
│──────────────────────────│
│ ID (PK)                  │
│ ACTION_ID (FK)           │
│ USER_ID (FK)             │
│ STATUS                   │──── SUBMITTED | RUNNING | COMPLETED
│ PARENT_EXECUTION_ID      │     FAILED | CANCELLED | REJECTED
│ PARAMETERS (JSON)        │     INTEGRATION_ERROR
│ CORRELATION_ID           │
│ CREATED_AT               │
│ UPDATED_AT               │
└───────────┬──────────────┘
            │ 1:N
┌───────────┴──────────────┐
│   EXECUTION_STEPS        │  ◄── Ref-partitionné sur EXECUTIONS
│──────────────────────────│
│ ID (PK)                  │
│ EXECUTION_ID (FK)        │
│ STEP_ID                  │
│ STEP_TYPE                │
│ STATUS                   │
│ STARTED_AT               │
│ COMPLETED_AT             │
│ OUTPUT (JSON)            │
│ ERROR_MESSAGE            │
│ ATTEMPT_NUMBER           │
└──────────────────────────┘

┌──────────────────────────┐    ┌──────────────────────────┐
│   WORKFLOW_EVENTS        │    │     RUNNABLE_STEPS       │
│──────────────────────────│    │──────────────────────────│
│ ID (PK)                  │    │ ID (PK)                  │
│ EXECUTION_ID (FK)        │    │ EXECUTION_ID (FK)        │
│ EVENT_TYPE               │    │ STEP_ID                  │
│ STEP_ID                  │    │ CLAIMED_UNTIL            │
│ PAYLOAD (JSON)           │    │ ATTEMPT_NO               │
│ SEQ_NO                   │    │ MAX_ATTEMPTS             │
│ CREATED_AT               │    │ CREATED_AT               │
└──────────────────────────┘    └──────────────────────────┘

┌──────────────────────────┐    ┌──────────────────────────┐
│   EXECUTION_OUTBOX       │    │      AUDIT_LOG           │
│──────────────────────────│    │──────────────────────────│
│ ID (PK)                  │    │ ID (PK)                  │  ◄── Partitionné
│ EXECUTION_ID (FK)        │    │ USER_ID                  │      mensuel
│ EVENT_TYPE               │    │ ACTION_TYPE              │
│ PAYLOAD (JSON)           │    │ ENTITY_TYPE              │
│ PROCESSED_AT             │    │ ENTITY_ID                │
│ CREATED_AT               │    │ CHANGES (JSON)           │
└──────────────────────────┘    │ CORRELATION_ID           │
                                │ TIMESTAMP                │
┌──────────────────────────┐    └──────────────────────────┘
│ SCHEDULED_EXECUTIONS     │
│──────────────────────────│    ┌──────────────────────────┐
│ ID (PK)                  │    │   CORE_FEATURE_FLAGS     │
│ ACTION_ID (FK)           │    │──────────────────────────│
│ USER_ID (FK)             │    │ KEY (PK)                 │
│ PARAMETERS (JSON)        │    │ IS_ENABLED               │
│ SCHEDULED_AT             │    │ DESCRIPTION              │
│ STATUS                   │    └──────────────────────────┘
│ RECURRING_PATTERN_ID     │
└──────────────────────────┘
```

---

## Cycle de vie d'un workflow

### Processus complet : de la demande à la complétion

```
  Utilisateur                    Frontend                      Backend (API)
      │                             │                              │
      │  1. Sélectionne une action  │                              │
      ├────────────────────────────►│                              │
      │                             │  2. POST /executions/        │
      │                             ├─────────────────────────────►│
      │                             │                              │
      │                             │         3. Validation        │
      │                             │     ┌────────────────────┐   │
      │                             │     │ • Permissions RBAC │   │
      │                             │     │ • Paramètres       │   │
      │                             │     │ • Mutex check      │   │
      │                             │     │ • Cibles valides   │   │
      │                             │     └────────────────────┘   │
      │                             │                              │
      │                             │  4. Crée EXECUTION           │
      │                             │     (status=SUBMITTED)       │
      │                             │                              │
      │                             │  5. Dispatch Celery Task     │
      │                             │     trigger_action_execution │
      │                             │◄─────────────────────────────┤
      │                             │                              │
      │                             │                     ┌────────┴────────┐
      │                             │                     │  Celery Worker  │
      │                             │                     │                 │
      │                             │                     │ 6. Résout le    │
      │                             │                     │    workflow DAG │
      │                             │                     │                 │
      │                             │                     │ 7. Pour chaque  │
      │                             │                     │    étape :      │
      │                             │                     │                 │
      │                             │                     │  ┌────────────┐ │
      │                             │                     │  │ PLATFORM   │ │
      │                             │                     │  │ Soumet job │ │
      │                             │                     │  │ à AAP/TF   │ │
      │                             │                     │  └────────────┘ │
      │                             │                     │        │        │
      │          WebSocket          │                     │  ┌─────┴──────┐ │
      │◄─── step_update ───────────│◄── broadcast ───────│  │ Poll status│ │
      │                             │                     │  │ toutes les │ │
      │                             │                     │  │ 5 secondes │ │
      │                             │                     │  └─────┬──────┘ │
      │                             │                     │        │        │
      │                             │                     │  ┌─────┴──────┐ │
      │                             │                     │  │ GATE       │ │
      │  8. Approbation requise     │                     │  │ En attente │ │
      │◄─── notification ──────────│◄─────────────────────│  │ approbation│ │
      │                             │                     │  └─────┬──────┘ │
      │  9. Approuve                │                     │        │        │
      ├────────────────────────────►│  POST /steps/{id}/  │        │        │
      │                             │  approve/           │  ┌─────┴──────┐ │
      │                             ├────────────────────►│  │ Continue   │ │
      │                             │                     │  │ workflow   │ │
      │                             │                     │  └─────┬──────┘ │
      │                             │                     │        │        │
      │                             │                     │  ┌─────┴──────┐ │
      │          WebSocket          │                     │  │ COMPLETED  │ │
      │◄─── execution_complete ────│◄── broadcast ───────│  │            │ │
      │                             │                     │  └────────────┘ │
      │                             │                     └────────────────┘
```

---

## Types d'étapes de workflow

| Type | Description | Exemple |
|------|-------------|---------|
| **platform** | Soumet un job à une plateforme d'automatisation (AAP, Tower, Terraform) | Exécuter un playbook Ansible |
| **service_call** | Invoque une autre action du catalogue (crée une exécution enfant) | Appeler un sous-workflow |
| **http_request** | Effectue un appel HTTP/HTTPS externe | Notifier un webhook |
| **evaluation** | Évalue une expression Jinja2 pour calcul ou transformation | Filtrer des résultats |
| **gate** | Pause l'exécution jusqu'à satisfaction d'une condition | Approbation manuelle |
| **schedule_execution** | Planifie une exécution future | Maintenance planifiée |

---

## Système de Gates (approbations et conditions)

Les gates sont des points de contrôle dans un workflow qui pausent l'exécution :

| Type de Gate | Déclencheur de reprise | Cas d'usage |
|-------------|------------------------|-------------|
| **APPROVAL** | Action humaine (approver clique « Approuver ») | Validation DBA avant migration |
| **CONDITION** | Évaluation automatique toutes les 60s | Attendre qu'un créneau de maintenance soit atteint |
| **SENSOR** | Événement externe (webhook, poll) | Attendre un déploiement CI/CD terminé |

Le Celery Beat évalue les gates en attente toutes les 60 secondes via la tâche `evaluate_waiting_gates`.

---

## Mécanisme de retry

Chaque étape de workflow peut être configurée avec un mécanisme de retry :

```
Tentative 1 → Échec → Attente (interval × backoff^0) → Tentative 2
                                                           │
                                                        Échec
                                                           │
                                            Attente (interval × backoff^1)
                                                           │
                                                      Tentative 3
                                                           │
                                              Succès ou max_attempts atteint
```

- **retry_max_attempts** : nombre maximum de tentatives
- **retry_interval_seconds** : délai initial entre les tentatives
- **retry_backoff_multiplier** : multiplicateur exponentiel

---

## Exécutions planifiées

Les exécutions peuvent être planifiées pour un moment futur ou de façon récurrente :

```
┌─────────────────────┐         ┌─────────────────────┐
│ SCHEDULED_EXECUTIONS│────────►│  RECURRING_PATTERNS  │
│                     │  0..1   │                      │
│ action_id           │         │ cron_expression      │
│ scheduled_at        │         │ timezone             │
│ parameters          │         │ next_run_at          │
│ status              │         │ end_date             │
└─────────────────────┘         └──────────────────────┘

Celery Beat (60s) ──► process_pending_scheduled_executions
                            │
                            ├── Vérifie scheduled_at ≤ now
                            ├── Crée une Execution
                            └── Met à jour next_run_at pour récurrents
```

---

## Patterns d'architecture

### Event Sourcing (Workflow Events)
Chaque changement d'état d'un workflow est enregistré comme un événement immuable dans `WORKFLOW_EVENTS`. Cela permet la reconstruction de l'état et l'audit complet.

### Transactional Outbox
La table `EXECUTION_OUTBOX` garantit la cohérence entre les écritures en base et la publication d'événements. Le dispatcher Celery traite les événements en attente de façon asynchrone.

### Work Queue distribué
La table `RUNNABLE_STEPS` sert de file d'attente distribuée avec un système de bail (lease). Un worker réclame une étape via `CLAIMED_UNTIL`, l'exécute, puis la libère. Si le bail expire (crash du worker), un autre worker peut reprendre l'étape.

### State Machine
Les transitions d'état des exécutions et étapes sont validées par une machine à états stricte (`domain/state_machine.py`), empêchant les transitions invalides.

---

## Intégrations supportées

| Plateforme | Usage | Protocole |
|------------|-------|-----------|
| **AAP / Ansible Tower** | Exécution de playbooks et job templates | REST API + Token |
| **ServiceNow** | Gestion des changements (ITSM) | REST API + OAuth2 |
| **Terraform Cloud** | Infrastructure as Code | REST API + Token |
| **GitHub Actions** | Workflows CI/CD | Webhooks + PAT |
| **Azure DevOps** | Pipelines | REST API + PAT |
| **HashiCorp Vault** | Récupération de secrets | REST API + Token/AppRole |

Chaque intégration dispose d'un health check automatique toutes les 60 minutes.

---

## Authentification et autorisations

### Flux d'authentification

```
Navigateur ──SAML SSO──► IdP Entreprise ──assertion──► IDP Portal ──JWT──► API
                                                                          │
Service Account ──API Key──► /auth/token ──JWT──► API ─────────────────────┘
```

### Modèle RBAC

```
PROFILE ──── a des ────► ACTION_PERMISSIONS (ALLOW/DENY par action)
    │                    TARGET_PERMISSIONS (ALLOW/DENY par cible)
    │
    ├── is_admin     → Accès complet
    ├── is_auditor   → Lecture audit log
    └── is_approver  → Peut approuver les gates
```

---

## Observabilité

| Aspect | Solution |
|--------|----------|
| **Logs structurés** | structlog → format JSON → Splunk |
| **Correlation ID** | UUID propagé de la requête HTTP → Celery → Audit |
| **Audit Trail** | Table AUDIT_LOG partitionnée, immuable, exportable CSV |
| **WebSocket** | Mises à jour temps réel des statuts d'exécution |
| **Health Checks** | Vérification périodique des intégrations |
| **Feature Flags** | Activation/désactivation de fonctionnalités sans déploiement |

---

## Infrastructure

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │ Frontend  │  │ Django   │  │ Celery Worker     │ │
│  │ (Vite)   │  │ (Daphne  │  │ + Celery Beat     │ │
│  │ :8080    │  │  ASGI)   │  │                   │ │
│  │          │  │ :8000    │  │                   │ │
│  └──────────┘  └──────────┘  └───────────────────┘ │
│                                                      │
│  ┌──────────┐  ┌──────────┐                         │
│  │ Oracle   │  │  Redis   │                         │
│  │ 19c      │  │          │                         │
│  │ :1521    │  │ :6379    │                         │
│  └──────────┘  └──────────┘                         │
└─────────────────────────────────────────────────────┘
```

- **Daphne** : Serveur ASGI pour HTTP et WebSocket
- **Celery Worker** : Traitement asynchrone des workflows
- **Celery Beat** : Planificateur de tâches périodiques (gates, schedules)
- **Redis** : Broker Celery, cache, couche WebSocket, feature flags
- **Oracle 19c+** : Base de données principale avec partitionnement et Data Guard
