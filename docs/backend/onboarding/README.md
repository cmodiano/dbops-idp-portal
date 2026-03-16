# Onboarding Développeur — IDP Portal

Bienvenue dans le projet IDP Portal ! Ce guide couvre tout ce qu'un nouveau développeur doit savoir pour être productif rapidement.

## Par où commencer

1. Lire l'[Architecture des workflows](../../architecture/workflow-architecture.md) pour comprendre le système
2. Consulter le [Guide développeur](../../architecture/developer-guide.md) pour la référence technique complète
3. Lire le [Guide de développement](../../reference/development-guide.md) pour le setup local

## Documentation clé

### Architecture

- [Architecture SSO](../sso.md) — Authentification SAML 2.0 + JWT
- [RBAC](../rbac.md) — Permissions et contrôle d'accès
- [Observabilité](../observability.md) — Logging structuré, corrélation

### Standards de développement

- [Checklist nouveaux endpoints](../endpoint-checklist.md) — Checklist PR pour tout nouvel endpoint DRF
- [Pièges sécurité courants](../security-common-pitfalls.md) — Erreurs fréquentes et solutions
- [Checklist sécurité pré-PR](../security-pre-pr-checklist.md) — Auto-review sécurité avant PR
- [Conventions de logging](../logging-conventions.md) — structlog et format des logs
- [Guide mypy](../mypy-developer-guide.md) — Typage strict

## Démarrage rapide

```bash
# 1. Cloner le repo et entrer dans le projet
cd idp-portal/django_backend

# 2. Créer l'environnement virtuel
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Lancer les tests
.venv/bin/python -m pytest

# 5. Lancer le serveur de développement
.venv/bin/python manage.py runserver
```
