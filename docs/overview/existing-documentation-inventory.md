# Inventaire de la documentation existante

**Date :** 2026-02-26  
**Projet :** test (idp-portal – frontend + django_backend)

> **Migration (2026-03) :** La documentation a été consolidée dans `docs/` (racine projet, ~187 fichiers). Les anciens répertoires `idp-portal/docs/architecture/` (vide) et `idp-portal/frontend/docs/` ont été supprimés. **Exception :** `idp-portal/django_backend/docs/` conserve 2 fichiers spécifiques : `parallel-group.md` et `workflow-output-schemas.md` (voir [docs/architecture/parallel-workflow-actions-analysis.md](../architecture/parallel-workflow-actions-analysis.md)).
> **Note (2026-03-09, Story 66-26) :** L'inventaire ci-dessous reflète l'état **antérieur à la migration** et est conservé à titre **historique uniquement**. De nombreux chemins listés (`idp-portal/django_backend/docs/README.md`, `decisions/`, etc.) ne correspondent plus à des fichiers existants — ils ont été consolidés dans `docs/backend/`. Pour l'état actuel de la documentation, consulter [docs/index.md](../index.md).

---

## Partie : Frontend (idp-portal/frontend)

| Fichier | Type | Notes |
|---------|------|--------|
| idp-portal/frontend/README.md | readme | Vue d'ensemble frontend |
| idp-portal/frontend/FRONTEND-STANDARDS.md | standards | Standards de code frontend |
| idp-portal/frontend/TESTING.md | tests | Tests frontend |
| idp-portal/frontend/docs/story-17-7-logging-refactor-report.md | rapport | Logging refactor |
| idp-portal/frontend/docs/logging-conventions.md | conventions | Conventions de logging |
| idp-portal/docs/frontend/README.md | readme | Doc frontend centralisée |
| idp-portal/docs/frontend/contributing.md | contributing | Contribution frontend |
| idp-portal/docs/frontend/api-integration.md | api | Intégration API |
| idp-portal/docs/frontend/testing.md | tests | Tests frontend |
| idp-portal/docs/frontend/state-management.md | architecture | Gestion d'état |
| idp-portal/docs/frontend/routing.md | architecture | Routage |
| idp-portal/docs/frontend/api-client-architecture.md | architecture | Architecture client API |
| idp-portal/docs/frontend/folder-structure.md | structure | Structure des dossiers |

---

## Partie : Django Backend (idp-portal/django_backend)

| Fichier | Type | Notes |
|---------|------|--------|
| idp-portal/django_backend/README.md | readme | Vue d'ensemble backend |
| idp-portal/django_backend/docs/README.md | readme | Index doc backend |
| idp-portal/django_backend/docs/architecture.md | architecture | Architecture backend |
| idp-portal/django_backend/docs/decisions/README.md | adr | Index ADR |
| idp-portal/django_backend/docs/decisions/adr-001-django-orm-vs-sql-brut.md | adr | ORM vs SQL |
| idp-portal/django_backend/docs/decisions/adr-002-structure-apps-django.md | adr | Structure apps |
| idp-portal/django_backend/docs/decisions/adr-003-migration-repositories-vers-services.md | adr | Migration repos |
| idp-portal/django_backend/docs/decisions/adr-004-gestion-champs-json-oracle.md | adr | JSON/Oracle |
| idp-portal/django_backend/docs/decisions/adr-005-strategie-tests-pytest-django.md | adr | Stratégie tests |
| idp-portal/django_backend/docs/db-resilience.md | resilience | Résilience DB |
| idp-portal/django_backend/docs/observability-architecture.md | observability | Observabilité |
| idp-portal/django_backend/docs/observability-runbook.md | runbook | Runbook observabilité |
| idp-portal/django_backend/docs/security-architecture.md | security | Sécurité |
| idp-portal/django_backend/docs/sso-architecture.md | auth | SSO |
| idp-portal/django_backend/docs/vault-integration-analysis.md | security | Vault |
| idp-portal/django_backend/services/README.md | readme | Services |
| idp-portal/django_backend/adapters/README.md | readme | Adapters |
| idp-portal/django_backend/tests/README.md | readme | Tests |
| idp-portal/django_backend/MIGRATION_STRATEGY.md | migration | Stratégie migration |
| idp-portal/docs/backend/README.md | readme | Doc backend centralisée |
| idp-portal/docs/backend/contributing.md | contributing | Contribution backend |
| idp-portal/docs/backend/authentication.md | auth | Authentification |
| idp-portal/docs/backend/api-reference.md | api | Référence API |
| idp-portal/docs/backend/services.md | services | Services |
| idp-portal/docs/backend/apps-structure.md | structure | Structure apps |
| idp-portal/docs/backend/rbac.md | security | RBAC |

---

## Documentation transverse (idp-portal / racine)

| Fichier | Type | Notes |
|---------|------|--------|
| README.md | readme | Vue d'ensemble projet (racine) |
| CONTRIBUTING.md | contributing | Contribution (racine) |
| idp-portal/README.md | readme | Vue d'ensemble idp-portal |
| idp-portal/CONTRIBUTING.md | contributing | Contribution idp-portal |
| idp-portal/CODEBASE-REVIEW.md | review | Revue codebase |
| idp-portal/docs/security-architecture.md | security | Sécurité globale |
| idp-portal/docs/security-audit-report.md | security | Audit sécurité |
| idp-portal/docs/security-remediation-plan.md | security | Plan de remédiation |
| idp-portal/docs/soc1-compliance-report.md | compliance | SOC1 |
| idp-portal/docs/api-self-service.md | api | API self-service |
| idp-portal/docs/architecture/caching-strategy.md | architecture | Cache |
| idp-portal/docs/operations/polling-tasks.md | operations | Polling |
| idp-portal/docs/inventory-mapping-guide.md | guide | Mapping inventaire |
| idp-portal/docs/business-rule-policies.md | feature | Règles métier |
| idp-portal/docs/feature-flags.md | feature | Feature flags |
| idp-portal/docs/fastapi-decommissioning-validation-report.md | migration | Décommissionnement FastAPI |
| idp-portal/database/baseline/README.md | readme | Baseline schéma DB |
| .github/workflows/ci.yml | ci | Pipeline CI |
| .github/pull_request_template.md | process | Template PR |

*(Liste non exhaustive ; inventaire historique avant migration vers docs/.)*

---

*Généré par le workflow document-project (étape 2).*
