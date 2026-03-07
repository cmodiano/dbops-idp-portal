# Documentation technique — IDP Portal (Backend Django)

## Table des matières

### Fondamentaux

- [**Glossaire**](glossary.md) — Définitions des concepts clés : Moteur (Engine), Plateforme, Service, engine_type, adapters, factories
- [Architecture](architecture.md) — Architecture générale du backend
- [SSO / Authentification SAML](sso-runbook.md) — Runbook opérationnel SSO
- [Sécurité](security-architecture.md) — Architecture de sécurité (TODO)

### API et intégrations

- [Catalogue d'intégrations](integration-type-catalogue.md) — Types d'intégration supportés (plateformes et services)
- [Migration d'intégrations](integration-migration-guide.md) — Guide de migration des intégrations
- [Validation statut intégrations](integration-status-validation.md) — Validation de l'état des intégrations
- [Jira](jira-integration.md) — Intégration Jira
- [Splunk](splunk-integration.md) — Intégration Splunk

### Observabilité et audit

- [Observabilité](observability-architecture.md) — Architecture d'observabilité
- [Audit et correlation_id](audit-correlation-id-search.md) — Recherche par correlation_id
- [Logging](logging-conventions.md) — Conventions de logging
- [Stratégie d'audit transactionnel](TRANSACTION_AUDIT_STRATEGY.md)

### RBAC et permissions

- [RBAC filtrage par attribut](rbac-filter-by-attribute.md) — Filtrage RBAC par attributs de cibles

### Qualité du code

- [Conformité SOLID](solid-guidelines.md) — Patterns SRP/OCP/LSP/ISP/DIP avec exemples du code réel (Epic 33)
- [mypy](mypy-developer-guide.md) — Guide développeur mypy
- [Gestion des dépendances](dependency-management.md) — Gestion des dépendances Python
- [Feature flags](feature-flags-redis-upgrade.md) — Feature flags et Redis

### Migration

- [Notes migration Django ORM](django-orm-migration-notes.md)
- [Notes migration DRF API](drf-api-migration-notes.md)
- [CI/CD déploiement Django](ci-cd-django-deployment.md)

### Exploitation

- [Mode simulation](simulation-mode.md) — Mode simulation pour développement
- [SSO Runbook](sso-runbook.md) — Guide opérationnel SSO
- [Observabilité Runbook](observability-runbook.md)

## Liens transverses

- [Documentation projet (racine)](../../docs/) — Rapports, analyses, conformité
- [Rapport bases/moteurs/technologies/intégrations](../../docs/rapport-bases-moteurs-technologies-integrations.md) — Analyse exhaustive des 4 concepts (Engine, Platform, IntegrationTypeCatalogue, engine_type)
