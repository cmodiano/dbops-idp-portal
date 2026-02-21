# Architecture – Django Backend (idp-portal/django_backend)

**Date :** 2026-02-21

---

## Résumé

API REST Django 5.1 + Django REST Framework, Python 3.12. Base Oracle, Redis pour cache et Celery, Channels pour WebSockets. Auth JWT + SAML. Apps par domaine (catalog, executions, profiles, integrations, reference, inventory, audit, dashboard, help, etc.).

---

## Stack technique

Voir **[technology-stack.md](./technology-stack.md)** (section Django Backend). Principaux éléments : Django 5.1, DRF 3.15+, Gunicorn, Daphne/Channels, oracledb, Celery, Redis, python-jose, python3-saml, drf-spectacular, pytest, mypy, ruff.

---

## Pattern d’architecture

- **Type :** API REST **centrée services** : couche HTTP (DRF ViewSets/APIViews), couche métier dans `services.py` (ou modules dédiés), modèles Django/ORM, adapters pour intégrations externes (Ansible Tower, GitHub, Terraform Cloud, Jira, ServiceNow).
- **Apps :** core, catalog, executions, dashboard, audit, idp_auth, integrations, profiles, inventory, reference, help, admin_analytics ; adapters et services partagés.

---

## Modèles de données

Voir **[data-models-django_backend.md](./data-models-django_backend.md)**. Modèles principaux : Execution, ExecutionStep, ScheduledExecution, Action, Tag, Profile, Integration, RefEngine, RefCategory, User, AuditLog, FeatureFlag, etc. Migrations Django dans `*/migrations/` ; scripts SQL Flyway dans `idp-portal/database/migrations/`.

---

## API REST

- Racine URL : `idp_backend/urls.py` ; préfixe `/api/v1/`. OpenAPI : `/api/schema/`, `/api/schema/swagger-ui/`, `/api/schema/redoc/`.
- Catalogue des endpoints : **[api-contracts-django_backend.md](./api-contracts-django_backend.md)** (core, catalog, executions, dashboard, audit, auth, integrations, profiles, inventory, reference, help, webhooks).

---

## Arbre des sources

Voir **[source-tree-analysis.md](./source-tree-analysis.md)** (section Django Backend). Entrées : `manage.py`, `idp_backend/urls.py`, `idp_backend/asgi.py`, `idp_backend/celery.py`. Dossiers clés : apps par domaine, `adapters/`, `services/`, `idp_backend/`.

---

## Développement

- **Prérequis :** Python 3.12+, Oracle (Docker possible), Redis.
- **Installation :** venv + `uv pip install -r requirements-dev.lock` (ou pip).
- **Commandes :** `python manage.py runserver`, `pytest`, `ruff check .`, `mypy .`, pre-commit. Voir **[development-guide.md](./development-guide.md)** et **[contribution-guide.md](./contribution-guide.md)**.

---

## Déploiement

- Gunicorn/Daphne en production ; Dockerfile présent. CI/CD : `.github/workflows/`. Voir **[deployment-configuration.md](./deployment-configuration.md)**.

---

## Tests

- **Framework :** pytest, pytest-django, pytest-cov, factory_boy. Tests dans `*/tests/`, `tests/`.
- **Qualité :** mypy (strict sur modules principaux), ruff, bandit, pip-audit (CI).

---

*Généré par le workflow document-project (étape 8).*
