# Guide de contribution – test (idp-portal)

**Date :** 2026-02-26

---

Le guide principal est **CONTRIBUTING.md** à la racine du dépôt (hors documentation). Résumé ci‑dessous.

---

## Démarrage

1. Lire le [guide d'onboarding](../backend/onboarding/README.md).
2. Se familiariser avec la [structure du projet Django](../backend/onboarding/django-migration-guide.md#3-structure-du-projet-django-idp).

---

## Standards

- **Avant de coder :** consulter les [ADRs](../backend/decisions/README.md), suivre les patterns existants (services, serializers, vues).
- **Nouvel endpoint :** suivre la [checklist endpoints DRF](../backend/standards/endpoint-checklist.md).
- **Sécurité :** [pièges courants](../backend/security-django/common-pitfalls.md), [checklist pré-PR](../backend/security-django/pre-pr-checklist.md).
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
- Remplir le template PR (`.github/pull_request_template.md` à la racine) si présent.

---

*Référence : CONTRIBUTING.md. Généré par le workflow document-project (étape 6).*
