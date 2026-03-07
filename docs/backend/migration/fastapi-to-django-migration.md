# Migration FastAPI → Django : Récapitulatif

> **📦 Document d'archivage — Migration terminée**  
> Ce document est conservé pour référence historique. La migration FastAPI→Django est complète (février 2026).  
> Voir [MIGRATION_ARCHIVE.md](MIGRATION_ARCHIVE.md) pour accéder au code FastAPI archivé.

**Date de complétion:** 2026-02-05
**Epic:** M - Migration FastAPI vers Django REST Framework
**Durée totale:** 10 stories (M.1 à M.10)

---

## Table des Matières

1. [Motivations](#1-motivations)
2. [Timeline de Migration](#2-timeline-de-migration)
3. [Architecture Avant/Après](#3-architecture-avantaprès)
4. [Défis Techniques](#4-défis-techniques)
5. [Résultats et Métriques](#5-résultats-et-métriques)
6. [Learnings](#6-learnings)
7. [Références](#7-références)

---

## 1. Motivations

### Pourquoi migrer de FastAPI vers Django ?

| Raison | Détail |
|--------|--------|
| **Arrimage plateforme** | La plateforme hébergeuse utilise Django comme standard |
| **Maintenance mutualisée** | Mêmes conventions, outils et patterns que les autres apps |
| **Écosystème Django** | Admin, ORM mature, middleware robuste, communauté large |
| **Support long terme** | Django LTS vs FastAPI (plus récent, moins de recul) |

### Contraintes de la migration

- **Parité fonctionnelle** : Toutes les fonctionnalités FastAPI préservées
- **Contrat API** : Même format de réponse (frontend inchangé)
- **Base de données** : Même schéma Oracle (pas de migration de données)
- **Authentification** : Même flow SAML 2.0 + JWT

---

## 2. Timeline de Migration

### Epic M Stories

| Story | Titre | Dates | Durée | Commits clés |
|-------|-------|-------|-------|--------------|
| M.1 | Bootstrap Django + DRF | 2026-01-27 | 1j | Projet Django initial |
| M.2 | Models & Migrations | 2026-01-28 | 1j | ORM mappé au schéma Oracle |
| M.3 | Data Layer → ORM | 2026-01-29 | 2j | Repositories migrés |
| M.4 | API Catalog/Admin | 2026-02-04 | 2j | Endpoints CRUD actions |
| M.5 | API Profiles/Permissions | 2026-02-04 | 1j | RBAC complet |
| M.6 | API Auth/Health/Integrations | 2026-02-04 | 1j | Auth + health + intégrations |
| M.7 | SAML Auth & Security | 2026-02-04 | 1j | Flow SAML complet |
| M.8 | Middleware & Observability | 2026-02-05 | 1j | Logging structuré |
| M.9 | Tests & Coverage | 2026-02-05 | 1j | 80%+ coverage |
| M.10 | Switchover & Decommission | 2026-02-05 | 1j | Plan de bascule |

**Durée totale estimée:** 12 jours de développement

### Jalons

- ✅ **2026-01-27** : Projet Django bootstrappé
- ✅ **2026-01-29** : Couche données migrée
- ✅ **2026-02-04** : Tous les endpoints API implémentés
- ✅ **2026-02-05** : Tests complets, prêt pour production
- 📅 **J à définir** : Bascule production

---

## 3. Architecture Avant/Après

### Avant : FastAPI

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI                               │
├─────────────────────────────────────────────────────────────┤
│  Routers (endpoints)                                         │
│  ├── actions.py, tags.py, profiles.py, executions.py        │
│  └── auth.py, health.py, integrations.py                    │
├─────────────────────────────────────────────────────────────┤
│  Services (business logic)                                   │
│  └── action_service.py, profile_service.py, etc.            │
├─────────────────────────────────────────────────────────────┤
│  Repositories (SQL brut)                                     │
│  └── action_repository.py → SELECT/INSERT/UPDATE            │
├─────────────────────────────────────────────────────────────┤
│  Database (python-oracledb)                                  │
│  └── Connection pool, raw SQL queries                        │
└─────────────────────────────────────────────────────────────┘
```

### Après : Django REST Framework

```
┌─────────────────────────────────────────────────────────────┐
│                  Django REST Framework                       │
├─────────────────────────────────────────────────────────────┤
│  Apps (modules Django)                                       │
│  ├── catalog/   → Actions, Tags, UserFavorites              │
│  ├── profiles/  → Profiles, Permissions                      │
│  ├── executions/ → Executions, Steps, Scheduled             │
│  ├── integrations/ → Integrations                            │
│  ├── idp_auth/  → Users, Auth, SAML                         │
│  └── core/      → AuditLog, shared utilities                │
├─────────────────────────────────────────────────────────────┤
│  ViewSets + Serializers (DRF)                                │
│  └── ModelViewSet, custom actions, nested routes            │
├─────────────────────────────────────────────────────────────┤
│  Models + Managers (ORM)                                     │
│  └── Django ORM with custom managers                         │
├─────────────────────────────────────────────────────────────┤
│  Database (Django ORM + oracledb)                            │
│  └── Managed connections, QuerySets                          │
└─────────────────────────────────────────────────────────────┘
```

### Comparaison des stacks

| Composant | FastAPI | Django |
|-----------|---------|--------|
| Framework | FastAPI 0.115+ | Django 5.1+, DRF 3.15+ |
| ORM | SQL brut | Django ORM |
| Driver Oracle | python-oracledb 3.4.1 | oracledb 3.4.1 (via Django) |
| Auth | python3-saml + python-jose | python3-saml + python-jose |
| Validation | Pydantic | DRF Serializers |
| Server | Uvicorn | Gunicorn |
| Logging | Custom JSON | structlog |

---

## 4. Défis Techniques

### Défi 1 : Mapping Oracle → Django ORM

**Problème:** Django ORM attend des conventions différentes (noms, types)

**Solution:**
- `db_table = 'ACTIONS_CATALOG'` pour mapper aux tables existantes
- `db_column = 'COLUMN_NAME'` pour chaque champ
- Pas de migrations Django pour créer/modifier les tables (Flyway existant)

```python
class Action(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, db_column='NAME')
    # ...

    class Meta:
        db_table = 'ACTIONS_CATALOG'
```

### Défi 2 : CLOB fields et JSON

**Problème:** Django TextField pour CLOB, mais pas de JSONField natif pour Oracle

**Solution:** Helpers de sérialisation/désérialisation sur chaque modèle

```python
def get_parameters_schema(self):
    if self.parameters_schema:
        return json.loads(self.parameters_schema)
    return None

def set_parameters_schema(self, value):
    self.parameters_schema = json.dumps(value) if value else None
```

### Défi 3 : Parité du format de réponse API

**Problème:** Frontend attend le même format JSON

**Solution:** Serializers DRF configurés pour reproduire exactement le format FastAPI

```python
class ActionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ['id', 'name', 'description', 'category', ...]

# Response format: {"data": [...], "total": N}
```

### Défi 4 : SAML 2.0 avec python3-saml

**Problème:** python3-saml attend Flask/Django, pas FastAPI

**Solution:** Même bibliothèque, configuration Django native

```python
# settings.py
SAML_CONFIG = {
    'sp': {...},
    'idp': {...},
}
```

### Défi 5 : Connection pool Oracle

**Problème:** Django et FastAPI ont des approches différentes

**Solution:** `CONN_MAX_AGE=600` + options `threaded=True`

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'CONN_MAX_AGE': 600,
        'OPTIONS': {'threaded': True},
    }
}
```

---

## 5. Résultats et Métriques

### Couverture de tests

| Module | Coverage M.9 | Cible |
|--------|--------------|-------|
| catalog | 85% | 80% |
| profiles | 82% | 80% |
| executions | 80% | 80% |
| idp_auth | 78% | 80% |
| integrations | 81% | 80% |
| core | 90% | 80% |
| **Global** | **82%** | **80%** |

### Performance (benchmarks M.9)

| Endpoint | FastAPI p95 | Django p95 | Delta |
|----------|-------------|------------|-------|
| GET /health | 15ms | 18ms | +3ms |
| GET /catalog/actions | 120ms | 125ms | +5ms |
| GET /catalog/actions/{id} | 45ms | 48ms | +3ms |
| GET /profiles | 80ms | 85ms | +5ms |
| GET /executions | 150ms | 155ms | +5ms |

**Conclusion:** Performance équivalente (delta < 10ms acceptable)

### Lignes de code

| Composant | FastAPI | Django | Delta |
|-----------|---------|--------|-------|
| Backend | ~8,500 | ~7,200 | -15% |
| Tests | ~3,200 | ~4,500 | +40% |
| Total | ~11,700 | ~11,700 | 0% |

**Note:** Django plus concis (ORM vs SQL brut), plus de tests (meilleure couverture)

---

## 6. Learnings

### Ce qui a bien fonctionné

1. **Mapping ORM existant** : `db_table` et `db_column` permettent de réutiliser le schéma
2. **DRF ViewSets** : Réduction du boilerplate vs routers FastAPI
3. **Managers Django** : Encapsulation des requêtes complexes
4. **structlog** : Logging structuré plus propre que custom JSON

### Ce qui était difficile

1. **Format de réponse** : Reproduire exactement le format FastAPI demande attention
2. **CLOB/JSON** : Pas de JSONField Oracle natif → helpers manuels
3. **Tests Oracle** : SQLite en CI, Oracle en local → comportements différents

### Recommandations pour futures migrations

1. **Commencer par les modèles** : Le mapping ORM est la fondation
2. **Tests tôt** : Écrire les tests d'intégration avant de coder les endpoints
3. **Format de réponse** : Documenter le contrat API (OpenAPI) avant de migrer
4. **Staging** : Toujours tester la bascule en staging d'abord

---

## 7. Références

### Commits clés

- `feat(m-1): Bootstrap Django + DRF` - Projet initial
- `feat(m-2): Models Django mappés au schéma Oracle` - ORM
- `feat(m-3): Couche données migrée vers ORM` - Repositories
- `feat(m-4 à m-6): API endpoints complets` - CRUD
- `feat(m-7): Authentification SAML` - Sécurité
- `feat(m-8): Middleware et observabilité` - Logging
- `feat(m-9): Tests et coverage 80%+` - Qualité
- `feat(m-10): Plan de bascule et décommissionnement` - Production

### Documentation

- [Plan de bascule](migration-switchover-plan.md)
- [Parité de schéma](schema-differences.md)
- [Templates de communication](communication-templates.md)
- [Checklist dry run staging](staging-dry-run-checklist.md)

### Code

- Backend Django : `idp-portal/django_backend/`
- Backend FastAPI (legacy) : `idp-portal/backend/` (branche `legacy/fastapi-final`)
- Frontend : `idp-portal/frontend/` (inchangé)

---

**Document rédigé par:** Équipe IDP Backend
**Date:** 2026-02-05
