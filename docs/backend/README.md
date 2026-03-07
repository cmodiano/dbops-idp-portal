# Documentation Backend Django - IDP Portal

**Version:** Django 5.2.11 + Django REST Framework 3.15+
**Base de données:** Oracle (via python-oracledb mode Thin)
**Dernière mise à jour:** 2026-02-05

## Vue d'ensemble

Le backend IDP Portal est construit avec Django et Django REST Framework (DRF). Il fournit une API REST pour la gestion du catalogue d'actions, des profils utilisateurs, des exécutions et de l'audit.

## Index de la documentation

| Document | Description |
|----------|-------------|
| [apps-structure.md](./apps-structure.md) | Structure des apps Django et leurs responsabilités |
| [models.md](./models.md) | Modèles Django, relations et managers |
| [services.md](./services.md) | Couche services et logique métier |
| [api-reference.md](./api-reference.md) | Endpoints API, serializers et pagination |
| [rbac.md](./rbac.md) | Système RBAC et gestion des permissions |
| [authentication.md](./authentication.md) | Authentification SAML et JWT |
| [observability.md](./observability.md) | Middleware, logging et monitoring |
| [testing.md](./testing.md) | Tests, fixtures et couverture |
| [contributing.md](./contributing.md) | Guide de contribution |

## Architecture en couches

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  ViewSets   │  │ Serializers │  │ Permissions │              │
│  │   (DRF)     │  │   (DRF)     │  │   (RBAC)    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                       Service Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ CatalogSvc  │  │ ProfileSvc  │  │  AuditSvc   │              │
│  │             │  │             │  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                      Data Access Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Managers   │  │   Models    │  │ Migrations  │              │
│  │ (QuerySets) │  │  (Django)   │  │  (Flyway)   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                        Oracle Database                           │
│                  (Tables UPPER_SNAKE_CASE)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Apps Django

| App | Responsabilité |
|-----|----------------|
| `catalog` | Gestion du catalogue d'actions (CRUD, tags, statuts) |
| `profiles` | Gestion des profils utilisateurs et permissions RBAC |
| `idp_auth` | Authentification SAML et gestion des sessions JWT |
| `integrations` | Configuration des plateformes distantes (AAP, Terraform, etc.) |
| `executions` | Gestion des exécutions d'actions et des steps |
| `core` | Fonctionnalités transverses (audit, pagination, exceptions, middleware) |

## Démarrage rapide

### Prérequis

- Python 3.11+
- Oracle Database (ou Docker avec Oracle XE)
- Variables d'environnement configurées

### Installation

```bash
# Cloner et naviguer
cd idp-portal/django_backend

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install uv
uv pip install -r requirements-dev.lock

# Configurer les variables d'environnement
cp .env.template .env
# Éditer .env avec vos valeurs

# Exécuter les tests
pytest

# Lancer le serveur de développement
python manage.py runserver
```

### Variables d'environnement requises

```bash
# Base de données Oracle
ORACLE_DSN=localhost:1521/FREEPDB1
ORACLE_USER=idp_app
ORACLE_PASSWORD=Oracle123!

# Sécurité
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# CORS
CORS_ORIGIN=http://localhost:5173

# Environnement
APP_ENV=development
DEBUG=True
```

## Conventions

### Format de réponse API

Toutes les réponses sont wrappées:

```json
// Succès
{"data": {...}}

// Erreur
{"error": {"code": "NOT_FOUND", "message": "Action non trouvée", "details": {}}}
```

### Codes HTTP

| Code | Usage |
|------|-------|
| 200 | Succès (GET, PUT, PATCH) |
| 201 | Créé (POST) |
| 204 | Supprimé (DELETE) |
| 400 | Erreur de validation ou état invalide |
| 401 | Non authentifié |
| 403 | Non autorisé (RBAC) |
| 404 | Ressource non trouvée |
| 500 | Erreur serveur |

### Conventions de nommage

- **Champs API:** snake_case (pas camelCase)
- **Tables Oracle:** UPPER_SNAKE_CASE
- **Classes Python:** PascalCase
- **Fichiers Python:** snake_case

## Stack technique

| Technologie | Version | Usage |
|-------------|---------|-------|
| Django | 5.2.11 | Framework principal |
| Django REST Framework | 3.15+ | API REST |
| python-oracledb | 3.4.1 | Connexion Oracle (mode Thin) |
| structlog | dernière | Logging JSON structuré |
| pytest-django | dernière | Tests |
| gunicorn | 23.0.0 | Serveur WSGI production |

## Ressources additionnelles

- [Django Documentation](https://docs.djangoproject.com/)
- [DRF Documentation](https://www.django-rest-framework.org/)
- [Logs dans Splunk](#) (interne)
