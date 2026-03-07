# Onboarding Développeur — IDP Portal

Bienvenue dans le projet IDP Portal ! Ce guide couvre tout ce qu'un nouveau développeur doit savoir pour être productif rapidement.

## Documents d'onboarding

| Document | Description |
|----------|-------------|
| [Guide de migration FastAPI → Django](./django-migration-guide.md) | Différences clés, patterns équivalents, structure projet, conventions tests |

## Documentation complémentaire

### Architecture et décisions

- [ADRs (Architecture Decision Records)](../decisions/README.md) — Décisions architecturales documentées
- [Notes migration DRF](../drf-api-migration-notes.md) — Notes détaillées de la migration API
- [Architecture SSO](../sso-architecture.md) — Authentification SAML 2.0 + JWT

### Standards de développement

- [Checklist nouveaux endpoints](../standards/endpoint-checklist.md) — Checklist PR pour tout nouvel endpoint DRF
- [Pièges sécurité courants](../security-django/common-pitfalls.md) — Erreurs fréquentes et solutions
- [Checklist sécurité pré-PR](../security-django/pre-pr-checklist.md) — Auto-review sécurité avant PR

### Tests

- README Tests — `idp-portal/django_backend/tests/README.md` (dépôt)
- Issues connues — `idp-portal/django_backend/tests/KNOWN_ISSUES.md` (dépôt)

### Observabilité

- [Architecture observabilité](../observability-architecture.md) — Logging structuré, corrélation
- [Runbook observabilité](../observability-runbook.md) — Guide opérationnel
- [Conventions de logging](../logging-conventions.md) — Structlog et format des logs

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

## Contacts

- **Epic 12** : Documentation technique complète (en cours)
- **Epic M** : Migration FastAPI → Django (terminée)
