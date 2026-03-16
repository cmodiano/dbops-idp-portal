# ADR-002 : Structure en Apps Django Modulaires

**Date :** 2026-02-08
**Statut :** Accepté
**Décideurs :** Équipe IDP — Architecture Epic M

## Contexte

Le passage à Django nécessitait de définir l'organisation du code en apps Django. Le backend FastAPI n'avait pas de séparation formelle en modules — tout était dans un seul package avec des répertoires `routes/`, `repositories/`, `services/`.

Le projet IDP Portal couvre plusieurs domaines métier : catalogue d'actions, profils/permissions, authentification SAML, exécutions, intégrations externes, audit.

## Décision

**Organiser le code en 6 apps Django avec responsabilités clairement séparées :**

```
idp_backend/
├── catalog/        # Catalogue d'actions, tags, CRUD admin
├── profiles/       # Profils dynamiques, permissions (actions, targets, envs), import/export YAML
├── idp_auth/       # Authentification SAML 2.0, JWT, refresh token, logout
├── executions/     # Moteur d'exécution, timeline, historique, scheduling
├── integrations/   # Plateformes externes (AAP, ServiceNow, Terraform), upload icônes
├── core/           # Exceptions, RBAC, database router, middleware, utils partagés
└── idp_backend/    # Settings, URLs, WSGI/ASGI
```

**Conventions :**
- Chaque app contient : `models.py`, `views.py`, `serializers.py`, `services.py`, `urls.py`, `tests/`
- Logique métier dans `services.py` (pas dans les vues ou serializers)
- `core/` est la seule app importable par toutes les autres (utilitaires partagés)
- Imports inter-apps minimisés (via services, pas d'import direct de modèles entre apps si évitable)

## Conséquences

### Positives
- Séparation claire des préoccupations — chaque app est autonome et testable
- Navigation dans le code facilitée — un nouveau développeur sait où chercher
- Tests isolés par app (`pytest profiles/tests/`, `pytest catalog/tests/`)
- Migrations indépendantes par app
- Possibilité de réutiliser une app dans un autre projet Django

### Négatives
- Imports circulaires à éviter (résolu par la convention core → apps, pas apps → apps)
- Certaines entités partagées (User, AuditLog) nécessitent des imports cross-app
- Overhead de boilerplate Django (`admin.py`, `apps.py`) pour chaque app

### Neutres
- 6 apps est un compromis — ni monolithe, ni micro-apps trop granulaires
- La structure peut évoluer (extraction ou fusion d'apps) selon les besoins

## Alternatives Considérées

### Alternative 1 : Monolithe Django (une seule app)
- **Description :** Tout le code dans une seule app Django `api/` avec des sous-répertoires
- **Raison du rejet :** Difficile à naviguer à mesure que le code grandit, migrations monolithiques, pas de séparation des préoccupations

### Alternative 2 : Micro-apps par entité métier
- **Description :** Une app par entité (actions, tags, profiles, permissions, tokens, saml, executions, timeline, integrations, icons, audit, health)
- **Raison du rejet :** Trop granulaire pour un MVP — explosion du nombre d'apps, imports inter-apps constants, overhead de maintenance

## Références

- [Django documentation — Applications](https://docs.djangoproject.com/en/stable/ref/applications/)
- Stories M-1, M-2 — Bootstrap et modèles Django
