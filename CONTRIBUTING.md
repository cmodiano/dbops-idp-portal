# Guide de contribution — IDP Portal

## Démarrage

1. Lire le [guide d'onboarding](docs/backend/onboarding/README.md)
2. Se familiariser avec la [structure du projet](docs/backend/onboarding/django-migration-guide.md#3-structure-du-projet-django-idp)

## Standards de développement

### Avant de coder

- Consulter les [ADRs (Architecture Decision Records)](docs/backend/decisions/README.md) pour comprendre les choix architecturaux
- Suivre les patterns existants : services, serializers, vues (voir [guide migration](docs/backend/onboarding/django-migration-guide.md))

### Pendant le développement

- **Nouvel endpoint** : suivre la [checklist endpoints DRF](docs/backend/standards/endpoint-checklist.md)
- **Sécurité** : consulter les [pièges courants](docs/backend/security-django/common-pitfalls.md)
- **Tests** : écrire les tests en parallèle du code, viser ≥80% de couverture

### Avant la PR

- Passer la [checklist sécurité pré-PR](docs/backend/security-django/pre-pr-checklist.md)
- Vérifier les tests : `cd idp-portal/django_backend && .venv/bin/python -m pytest`
- Remplir le [template PR](/.github/pull_request_template.md)

## Conventions

| Convention | Détail |
|-----------|--------|
| Logique métier | `services.py` (jamais dans les vues) |
| Validation | DRF Serializers |
| Erreurs | `core/exceptions.py` (NotFoundError, InvalidStateError, etc.) |
| Audit | `AuditService.create_entry()` dans les services |
| Tests | pytest-django + factory_boy, fichiers dans `app/tests/` |
| Nommage tests | `test_<action>_<scenario>` (ex: `test_create_action_duplicate_name`) |

## Ressources

- [Documentation onboarding](docs/backend/onboarding/README.md)
- [ADRs](docs/backend/decisions/README.md)
- [Checklist endpoints](docs/backend/standards/endpoint-checklist.md)
- [Sécurité](docs/backend/security-django/)
- [Architecture observabilité](docs/backend/observability-architecture.md)
