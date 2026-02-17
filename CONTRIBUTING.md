# Guide de contribution — IDP Portal

## Démarrage

1. Lire le [guide d'onboarding](idp-portal/django_backend/docs/onboarding/README.md)
2. Se familiariser avec la [structure du projet](idp-portal/django_backend/docs/onboarding/django-migration-guide.md#3-structure-du-projet-django-idp)

## Standards de développement

### Avant de coder

- Consulter les [ADRs (Architecture Decision Records)](idp-portal/django_backend/docs/decisions/README.md) pour comprendre les choix architecturaux
- Suivre les patterns existants : services, serializers, vues (voir [guide migration](idp-portal/django_backend/docs/onboarding/django-migration-guide.md))

### Pendant le développement

- **Nouvel endpoint** : suivre la [checklist endpoints DRF](idp-portal/django_backend/docs/standards/endpoint-checklist.md)
- **Sécurité** : consulter les [pièges courants](idp-portal/django_backend/docs/security/common-pitfalls.md)
- **Tests** : écrire les tests en parallèle du code, viser ≥80% de couverture

### Avant la PR

- Passer la [checklist sécurité pré-PR](idp-portal/django_backend/docs/security/pre-pr-checklist.md)
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

- [Documentation onboarding](idp-portal/django_backend/docs/onboarding/README.md)
- [ADRs](idp-portal/django_backend/docs/decisions/README.md)
- [Checklist endpoints](idp-portal/django_backend/docs/standards/endpoint-checklist.md)
- [Sécurité](idp-portal/django_backend/docs/security/)
- [Architecture observabilité](idp-portal/django_backend/docs/observability-architecture.md)
