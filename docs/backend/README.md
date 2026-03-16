# Backend Django - IDP Portal

**Stack** : Django 5.2, Django REST Framework, Celery 5.6, Oracle 19c+, Redis

## Index

### Architecture et modèles

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Structure des packages d'intégration |
| [database-schema.md](database-schema.md) | Schéma BD complet, 28 tables, relations ER |
| [services.md](services.md) | Couche services et logique métier |
| [api-reference.md](api-reference.md) | Endpoints API, serializers, pagination |
| [oracle-json-fields.md](oracle-json-fields.md) | OracleJSONField pour colonnes JSON/CLOB |
| [partitioning-retention.md](partitioning-retention.md) | Partitionnement Oracle et politique de rétention |

### Authentification et RBAC

| Document | Description |
|----------|-------------|
| [authentication.md](authentication.md) | SAML 2.0, JWT, API Keys |
| [sso.md](sso.md) | Architecture SSO et runbook de dépannage |
| [rbac.md](rbac.md) | Système RBAC et permissions |
| [rbac-filter-by-attribute.md](rbac-filter-by-attribute.md) | Filtres RBAC par attribut d'inventaire |
| [ldap-configuration.md](ldap-configuration.md) | LDAP pour comptes de service |

### Workflows et exécutions

| Document | Description |
|----------|-------------|
| [condition-gates.md](condition-gates.md) | Préconditions et gates sur les étapes |
| [workflow-retry-celery.md](workflow-retry-celery.md) | Retry avec Celery (backoff exponentiel) |
| [workflow-schedule-step-implementation.md](workflow-schedule-step-implementation.md) | Steps de planification dans un workflow |
| [simulation-mode.md](simulation-mode.md) | Mode simulation pour le développement |
| [change-type-config.md](change-type-config.md) | Configuration change_type par environnement |

### Intégrations et plateformes

| Document | Description |
|----------|-------------|
| [integration-type-catalogue.md](integration-type-catalogue.md) | Catalogue des types d'intégration |
| [integration-status-validation.md](integration-status-validation.md) | Validation statut valid/invalid/deprecated |
| [platform-integration-mapping.md](platform-integration-mapping.md) | Mapping REF_PLATFORMS ↔ IntegrationTypeCatalogue |
| [vault-integration.md](vault-integration.md) | HashiCorp Vault : analyse et troubleshooting |
| [vault-bootstrap-guide.md](vault-bootstrap-guide.md) | Bootstrap Vault (Secret 0) |
| [splunk-integration.md](splunk-integration.md) | Splunk HEC : logs structurés et gestion d'indisponibilité |
| [jira-integration.md](jira-integration.md) | JiraService |

### Observabilité et logging

| Document | Description |
|----------|-------------|
| [observability.md](observability.md) | Middleware, logging, monitoring |
| [logging-conventions.md](logging-conventions.md) | Standards de logging structuré |
| [audit-correlation-id-search.md](audit-correlation-id-search.md) | Recherche par correlation ID |

### Qualité et standards

| Document | Description |
|----------|-------------|
| [testing.md](testing.md) | Tests, fixtures, couverture |
| [contributing.md](contributing.md) | Guide de contribution backend |
| [mypy-developer-guide.md](mypy-developer-guide.md) | Guide mypy strict |
| [solid-guidelines.md](solid-guidelines.md) | Conformité SOLID |
| [endpoint-checklist.md](endpoint-checklist.md) | Checklist nouvel endpoint DRF |
| [backend-best-practices.md](backend-best-practices.md) | Bonnes pratiques Oracle/RBAC |

### Sécurité

| Document | Description |
|----------|-------------|
| [secrets-configuration.md](secrets-configuration.md) | Configuration sécurisée des secrets |
| [security-common-pitfalls.md](security-common-pitfalls.md) | Patterns de sécurité critiques |
| [security-pre-pr-checklist.md](security-pre-pr-checklist.md) | Self-checklist sécurité pré-PR |

### Infrastructure

| Document | Description |
|----------|-------------|
| [db-resilience.md](db-resilience.md) | Résilience Data Guard failover/switchover |
| [ci-cd-django-deployment.md](ci-cd-django-deployment.md) | CI/CD et déploiement Django |
| [reference-data.md](reference-data.md) | Reproductibilité des données de référence |

### Aide contextuelle

| Document | Description |
|----------|-------------|
| [help-contextual-design.md](help-contextual-design.md) | Design de l'aide contextuelle (tooltips/popovers) |
| [help/](help/) | Contenus d'aide pour les formulaires d'action |
