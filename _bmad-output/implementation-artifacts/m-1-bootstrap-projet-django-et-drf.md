# Story m.1: Bootstrap projet Django et Django REST Framework

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur de l'équipe IDP,
I want un projet Django initial avec DRF, structure d'apps et configuration de base,
So that nous avons une base saine pour migrer les endpoints et la logique métier.

## Acceptance Criteria

1. **Given** un environnement Python dédié à la migration (venv ou équivalent)
   **When** on installe Django, djangorestframework, djangocorsheaders, et les dépendances Oracle (cx_Oracle ou oracledb)
   **Then** un projet Django `idp_backend` est créé avec une structure d'apps : `catalog`, `profiles`, `auth`, `integrations`, `core`

2. **Given** le projet Django
   **When** on configure `settings.py` (DEBUG, ALLOWED_HOSTS, DATABASES Oracle, INSTALLED_APPS avec rest_framework, CORS)
   **Then** `python manage.py runserver` démarre sans erreur
   **And** la structure respecte les conventions du projet hébergeur si documentées (nommage, place des configs)
   **And** un fichier `requirements.txt` ou `pyproject.toml` liste toutes les dépendances avec versions

3. **Given** DRF est installé
   **When** on configure REST_FRAMEWORK dans settings (auth, pagination, format JSON, throttle si requis)
   **Then** une route de test GET /api/v1/health (ou équivalent) renvoie 200 avec un payload minimal
   **And** le format de réponse (enveloppe data/error, snake_case) est aligné avec l'API actuelle pour compatibilité frontend

## Tasks / Subtasks

- [x] Task 1 : Créer l'environnement Python et installer les dépendances (AC: #1)
  - [x] Subtask 1.1 : Créer un venv Python 3.12+ dédié à la migration Django
  - [x] Subtask 1.2 : Installer Django (version stable 2026), djangorestframework, djangocorsheaders
  - [x] Subtask 1.3 : Installer le driver Oracle (cx_Oracle ou oracledb) compatible avec Django
  - [x] Subtask 1.4 : Créer requirements.txt ou pyproject.toml avec toutes les dépendances et versions

- [x] Task 2 : Initialiser le projet Django et la structure d'apps (AC: #1, #2)
  - [x] Subtask 2.1 : Créer le projet Django `idp_backend` via `django-admin startproject`
  - [x] Subtask 2.2 : Créer les apps Django : `catalog`, `profiles`, `idp_auth`, `integrations`, `core`
  - [x] Subtask 2.3 : Enregistrer les apps dans INSTALLED_APPS de settings.py
  - [x] Subtask 2.4 : Vérifier que la structure respecte les conventions du projet hébergeur (si documentées)

- [x] Task 3 : Configurer settings.py pour Oracle et DRF (AC: #2, #3)
  - [x] Subtask 3.1 : Configurer DATABASES avec Oracle (DSN, USER, PASSWORD depuis variables d'environnement)
  - [x] Subtask 3.2 : Configurer DEBUG, ALLOWED_HOSTS, SECRET_KEY (depuis env vars)
  - [x] Subtask 3.3 : Configurer REST_FRAMEWORK (authentication, pagination, format JSON, throttle si requis)
  - [x] Subtask 3.4 : Configurer CORS via djangocorsheaders (origins autorisées)
  - [x] Subtask 3.5 : Vérifier que `python manage.py runserver` démarre sans erreur

- [x] Task 4 : Créer l'endpoint health check avec format de réponse aligné (AC: #3)
  - [x] Subtask 4.1 : Créer la vue DRF GET /api/v1/health dans l'app `core`
  - [x] Subtask 4.2 : Configurer l'URL routing pour /api/v1/health
  - [x] Subtask 4.3 : Implémenter le format de réponse avec enveloppe data/error en snake_case
  - [x] Subtask 4.4 : Tester que l'endpoint renvoie 200 avec payload minimal

## Dev Notes

### Architecture Compliance

**Contexte de migration :** Cette story initie la migration du backend FastAPI vers Django REST Framework pour faciliter l'arrimage à la plateforme hébergeuse (même stack, mêmes conventions, maintenance mutualisable). Le frontend React reste inchangé et consomme la même API (contrat préservé).

**Contrainte critique :** Parité fonctionnelle et contractuelle avec l'API actuelle (OpenAPI / contrats frontend). Le format de réponse (enveloppe data/error, snake_case) doit être identique pour éviter toute modification frontend.

**Stack actuelle (FastAPI) à migrer :**
- Backend : FastAPI 0.115+, Python 3.12+, python-oracledb 3.4.1 (mode Thin), Pydantic v2.12+
- Base de données : Oracle Database via python-oracledb 3.4.1 mode Thin (pas de dépendance Oracle Client)
- API : REST JSON avec OpenAPI auto-généré, format réponse `{ "data": {...} }` ou `{ "error": {...} }`
- Structure : Repository Pattern avec SQL brut (pas d'ORM actuellement)

**Stack cible (Django) :**
- Backend : Django (version stable 2026), Django REST Framework, Python 3.12+
- Base de données : Oracle Database (même schéma existant, pas de migration de données)
- API : DRF avec serializers, format réponse identique (enveloppe data/error, snake_case)
- Structure : Apps Django (`catalog`, `profiles`, `auth`, `integrations`, `core`)

**Décisions architecturales à respecter :**
- Les conventions de nommage (snake_case pour API, UPPER_SNAKE_CASE pour Oracle) restent identiques
- Le format de réponse API (enveloppe data/error) doit être préservé pour compatibilité frontend
- La structure d'apps Django doit suivre les conventions du projet hébergeur si documentées
- Le schéma Oracle existant n'est pas modifié (migrations Django seront créées en Story M.2)

### Technical Requirements

**Versions à utiliser (recherche janvier 2026) :**
- Django : Version stable LTS ou dernière stable (vérifier compatibilité Python 3.12+)
- Django REST Framework : Version compatible avec Django choisi
- djangocorsheaders : Version compatible
- Driver Oracle : cx_Oracle ou oracledb (vérifier compatibilité avec Django ORM)

**Configuration Oracle :**
- Utiliser les mêmes variables d'environnement que FastAPI : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`
- Configurer le pool de connexions Oracle dans DATABASES settings (min/max si supporté)
- Le schéma Oracle existant (tables V001-V020+) reste inchangé

**Configuration DRF :**
- Authentication : À définir (sera migré depuis FastAPI SAML/JWT en Story M.7)
- Pagination : Alignée avec l'API actuelle (page, page_size, total_count, total_pages)
- Format JSON : snake_case partout (pas de camelCase)
- Throttle : Si requis par la plateforme hébergeuse

**Format de réponse API (CRITIQUE - doit être identique) :**

Succès :
```json
{
  "data": {
    "status": "ok",
    "database": "connected"
  }
}
```

Erreur :
```json
{
  "error": {
    "code": "DATABASE_ERROR",
    "message": "Impossible de se connecter à Oracle",
    "details": {}
  }
}
```

### Library/Framework Requirements

**Dépendances Python requises :**
- Django (version stable 2026)
- djangorestframework (version compatible)
- djangocorsheaders (pour CORS)
- cx_Oracle ou oracledb (driver Oracle compatible Django)
- python-dotenv ou django-environ (pour variables d'environnement)

**Structure de dépendances :**
- Créer `requirements.txt` ou `pyproject.toml` avec toutes les dépendances et versions exactes
- Documenter les versions pour reproductibilité
- Inclure les dépendances de développement si nécessaire (pytest-django, black, etc.)

### File Structure Requirements

**Structure Django cible :**

```
idp_backend/                    # Projet Django racine
├── manage.py
├── idp_backend/                # Settings du projet
│   ├── __init__.py
│   ├── settings.py             # Configuration (DEBUG, DATABASES, INSTALLED_APPS, REST_FRAMEWORK, CORS)
│   ├── urls.py                 # URLs racine
│   ├── wsgi.py
│   └── asgi.py
├── catalog/                    # App Django pour le catalogue d'actions
│   ├── __init__.py
│   ├── models.py               # Vide pour l'instant (Story M.2)
│   ├── views.py                # Vide pour l'instant
│   ├── serializers.py          # Vide pour l'instant
│   ├── urls.py                 # Vide pour l'instant
│   └── admin.py
├── profiles/                   # App Django pour les profils RBAC
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── auth/                       # App Django pour l'authentification
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── integrations/               # App Django pour les intégrations (Vault, ServiceNow, etc.)
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── core/                       # App Django pour core (health, middleware, etc.)
│   ├── __init__.py
│   ├── models.py
│   ├── views.py                # Health check endpoint ici
│   ├── serializers.py
│   ├── urls.py                 # URLs /api/v1/health
│   └── middleware.py           # Middleware custom si nécessaire
└── requirements.txt            # ou pyproject.toml
```

**Conventions de nommage :**
- Apps Django : snake_case (`catalog`, `profiles`, `auth`, `integrations`, `core`)
- Fichiers Python : snake_case (`views.py`, `serializers.py`, `urls.py`)
- Classes : PascalCase (`HealthView`, `HealthSerializer`)
- Variables : snake_case (`database_status`, `connection_pool`)

**URLs structure :**
- Préfixe API : `/api/v1/` (identique à FastAPI)
- Health check : `/api/v1/health` (identique à FastAPI)
- Routing : Utiliser DRF routers ou URL patterns Django standard

### Testing Requirements

**Tests à créer :**
- Test unitaire : Vérifier que le projet Django démarre sans erreur
- Test d'intégration : Vérifier que GET /api/v1/health renvoie 200 avec format correct
- Test de format : Vérifier que la réponse JSON respecte l'enveloppe data/error et snake_case

**Framework de test :**
- Utiliser pytest-django ou unittest Django standard
- Créer les tests dans chaque app (`tests.py` ou `tests/` directory)

**Couverture minimale :**
- Health check endpoint fonctionnel
- Format de réponse validé
- Configuration Oracle testée (connexion réussie)

### Project Structure Notes

**Alignement avec structure existante :**
- Le projet Django sera créé dans un dossier séparé ou à côté du backend FastAPI existant
- La structure doit permettre la cohabitation temporaire FastAPI et Django (même API contract)
- Les variables d'environnement Oracle sont partagées entre FastAPI et Django

**Conventions du projet hébergeur :**
- Si des conventions spécifiques sont documentées (nommage, place des configs), les respecter
- Sinon, suivre les conventions Django standard

**Migration progressive :**
- Cette story crée uniquement le bootstrap Django
- Les endpoints FastAPI restent fonctionnels pendant la migration
- Le frontend continue de pointer vers FastAPI jusqu'à la bascule complète (Story M.10)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic-M] - Epic M : Migration FastAPI vers Django REST
- [Source: _bmad-output/planning-artifacts/architecture.md] - Architecture actuelle FastAPI + Oracle
- [Source: _bmad-output/planning-artifacts/prd.md] - PRD avec contraintes et exigences
- [Source: _bmad-output/implementation-artifacts/1-1-initialisation-monorepo-et-environnement-de-developpement.md] - Story 1.1 avec structure FastAPI de référence

## Dev Agent Record

### Agent Model Used

Auto (Cursor AI)

### Debug Log References

### Completion Notes List

**2026-02-03 - Implémentation complète**

- ✅ Environnement Python 3.13.9 créé avec venv dédié
- ✅ Dépendances installées : Django 5.2.11, djangorestframework 3.16.1, django-cors-headers 4.9.0, oracledb 3.4.2
- ✅ Projet Django `idp_backend` créé avec structure complète
- ✅ Apps Django créées : catalog, profiles, idp_auth (renommé pour éviter conflit avec auth Django), integrations, core
- ✅ Configuration settings.py : Oracle DB, REST_FRAMEWORK, CORS, variables d'environnement
- ✅ Endpoint health check GET /api/v1/health implémenté avec format réponse aligné (enveloppe data/error, snake_case)
- ✅ Tests unitaires créés et passent (5/5) : endpoint existe, format réponse correct, vérification DB, format d'erreur, cas limites
- ✅ `python manage.py check` et `python manage.py runserver` fonctionnent sans erreur
- ✅ Code review fixes appliqués : format réponse FastAPI corrigé, fichiers manquants créés, tests améliorés

**Décisions techniques :**
- App `auth` renommée en `idp_auth` pour éviter conflit avec `django.contrib.auth`
- Utilisation de `oracledb` (mode Thin) au lieu de `cx_Oracle` pour compatibilité
- Format de réponse API préservé (enveloppe data/error, snake_case) pour compatibilité frontend
- Configuration Oracle utilise mêmes variables d'environnement que FastAPI (ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD)

### File List

**Nouveaux fichiers créés :**
- idp-portal/django_backend/requirements.txt
- idp-portal/django_backend/manage.py
- idp-portal/django_backend/pytest.ini
- idp-portal/django_backend/idp_backend/__init__.py
- idp-portal/django_backend/idp_backend/settings.py
- idp-portal/django_backend/idp_backend/urls.py
- idp-portal/django_backend/idp_backend/wsgi.py
- idp-portal/django_backend/idp_backend/asgi.py
- idp-portal/django_backend/core/__init__.py
- idp-portal/django_backend/core/views.py
- idp-portal/django_backend/core/urls.py
- idp-portal/django_backend/core/tests.py
- idp-portal/django_backend/core/admin.py
- idp-portal/django_backend/core/apps.py
- idp-portal/django_backend/core/models.py
- idp-portal/django_backend/catalog/__init__.py
- idp-portal/django_backend/catalog/admin.py
- idp-portal/django_backend/catalog/apps.py
- idp-portal/django_backend/catalog/models.py
- idp-portal/django_backend/catalog/tests.py
- idp-portal/django_backend/catalog/views.py
- idp-portal/django_backend/profiles/__init__.py
- idp-portal/django_backend/profiles/admin.py
- idp-portal/django_backend/profiles/apps.py
- idp-portal/django_backend/profiles/models.py
- idp-portal/django_backend/profiles/tests.py
- idp-portal/django_backend/profiles/views.py
- idp-portal/django_backend/idp_auth/__init__.py
- idp-portal/django_backend/idp_auth/admin.py
- idp-portal/django_backend/idp_auth/apps.py
- idp-portal/django_backend/idp_auth/models.py
- idp-portal/django_backend/idp_auth/tests.py
- idp-portal/django_backend/idp_auth/views.py
- idp-portal/django_backend/integrations/__init__.py
- idp-portal/django_backend/integrations/admin.py
- idp-portal/django_backend/integrations/apps.py
- idp-portal/django_backend/integrations/models.py
- idp-portal/django_backend/integrations/tests.py
- idp-portal/django_backend/integrations/views.py
- idp-portal/django_backend/core/serializers.py
- idp-portal/django_backend/catalog/serializers.py
- idp-portal/django_backend/catalog/urls.py
- idp-portal/django_backend/profiles/serializers.py
- idp-portal/django_backend/profiles/urls.py
- idp-portal/django_backend/idp_auth/serializers.py
- idp-portal/django_backend/idp_auth/urls.py
- idp-portal/django_backend/integrations/serializers.py
- idp-portal/django_backend/integrations/urls.py

## Senior Developer Review (AI)

**Reviewer:** Cyrille  
**Date:** 2026-02-03  
**Status:** Changes Requested → Fixed

### Review Summary

**Issues Found:** 1 CRITICAL, 4 HIGH, 4 MEDIUM, 2 LOW  
**Issues Fixed:** 1 CRITICAL, 4 HIGH, 4 MEDIUM

### Issues Fixed

#### CRITICAL Issues Fixed

1. **Health endpoint response format mismatch** ✅ FIXED
   - **File:** `core/views.py`
   - **Issue:** Format de réponse ne correspondait pas à FastAPI (`database` vs `oracle`, `ok` vs `healthy/degraded`)
   - **Fix:** Modifié pour utiliser `oracle` et `healthy/degraded` comme dans FastAPI
   - **Impact:** Compatibilité frontend restaurée

#### HIGH Issues Fixed

2. **Fichiers serializers.py manquants** ✅ FIXED
   - **Files:** Créé `serializers.py` pour toutes les apps (catalog, profiles, idp_auth, integrations, core)
   - **Fix:** Fichiers créés avec structure de base conforme à la story

3. **Fichiers urls.py manquants** ✅ FIXED
   - **Files:** Créé `urls.py` pour catalog, profiles, idp_auth, integrations
   - **Fix:** Fichiers créés avec structure de base et commentaires indiquant les futures stories

4. **Duplication DEFAULT_RENDERER_CLASSES** ✅ FIXED
   - **File:** `idp_backend/settings.py`
   - **Fix:** Suppression de la duplication, configuration consolidée

5. **Tests améliorés** ✅ FIXED
   - **File:** `core/tests.py`
   - **Fix:** Ajout de tests pour vérifier format d'erreur (503), format FastAPI (`oracle`, `healthy/degraded`), et cas d'erreur DB

#### MEDIUM Issues Fixed

6. **Appels os.getenv() redondants** ✅ FIXED
   - **File:** `idp_backend/settings.py`
   - **Fix:** Simplification des appels redondants

7. **SECRET_KEY documentation** ✅ FIXED
   - **File:** `idp_backend/settings.py`
   - **Fix:** Ajout de commentaire indiquant que la valeur par défaut est pour dev uniquement

8. **CORS configuration documentation** ✅ FIXED
   - **File:** `idp_backend/settings.py`
   - **Fix:** Ajout de commentaire indiquant que la valeur par défaut doit être configurée en production

9. **Tests 503 améliorés** ✅ FIXED
   - **File:** `core/tests.py`
   - **Fix:** Ajout de test explicite pour vérifier le retour 503 en cas d'erreur DB

### Validation Post-Fix

- ✅ Format de réponse health endpoint aligné avec FastAPI (`oracle`, `healthy/degraded`)
- ✅ Tous les fichiers `serializers.py` et `urls.py` créés selon structure requise
- ✅ Configuration DRF nettoyée (duplication supprimée)
- ✅ Tests améliorés avec couverture format d'erreur et cas limites
- ✅ Code qualité améliorée (documentation, simplification)

### Remaining LOW Issues (Non-Blocking)

- **LOW-1:** Répertoire `venv/` devrait être dans `.gitignore` (à faire manuellement)
- **LOW-2:** Docstrings manquantes dans certains fichiers (amélioration future)

### Recommendation

✅ **APPROVED** - Tous les problèmes CRITICAL et HIGH ont été corrigés. La story peut être marquée comme `done` après validation manuelle des tests.
