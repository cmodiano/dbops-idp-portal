# Guide de contribution – test (idp-portal)

**Date :** 2026-02-21

---

Le guide principal est **[CONTRIBUTING.md](../CONTRIBUTING.md)** à la racine du dépôt. Résumé ci‑dessous.

---

## Démarrage

1. Lire le [guide d'onboarding](idp-portal/django_backend/docs/onboarding/README.md).
2. Se familiariser avec la [structure du projet Django](idp-portal/django_backend/docs/onboarding/django-migration-guide.md#3-structure-du-projet-django-idp).

---

## Standards

- **Avant de coder :** consulter les [ADRs](idp-portal/django_backend/docs/decisions/README.md), suivre les patterns existants (services, serializers, vues).
- **Nouvel endpoint :** suivre la [checklist endpoints DRF](idp-portal/django_backend/docs/standards/endpoint-checklist.md).
- **Sécurité :** [pièges courants](idp-portal/django_backend/docs/security/common-pitfalls.md), [checklist pré-PR](idp-portal/django_backend/docs/security/pre-pr-checklist.md).
- **Tests :** en parallèle du code, ≥80% de couverture ; pytest-django, factory_boy ; nommage `test_<action>_<scenario>`.

---

## Conventions (backend)

| Convention | Détail |
|------------|--------|
| Logique métier | Dans `services.py`, pas dans les vues |
| Validation | DRF Serializers |
| Erreurs | `core/exceptions.py` |
| Audit | `AuditService.create_entry()` dans les services |
| Tests | Fichiers dans `app/tests/` |

---

## PR

- Exécuter les tests : `cd idp-portal/django_backend && .venv/bin/python -m pytest`
- Remplir le [template PR](.github/pull_request_template.md) si présent.

---

*Référence : CONTRIBUTING.md. Généré par le workflow document-project (étape 6).*
