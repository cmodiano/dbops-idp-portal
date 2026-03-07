# Archive FastAPI — Migration vers Django

**Document d'archivage — Migration terminée (février 2026)**

## Où trouver le code FastAPI archivé

Le code FastAPI du portail IDP a été archivé dans :

- **Branche Git** : `legacy/fastapi-final`
- **Tag Git** : `v1.0.0-fastapi`

Pour consulter le code archivé :

```bash
git checkout legacy/fastapi-final
# ou
git checkout v1.0.0-fastapi
```

## Raison de l'archivage

Le backend du portail IDP a été migré de FastAPI vers Django REST Framework (Epic M, stories M.1–M.10). Le backend Django est maintenant en production et le code FastAPI n'est plus maintenu.

**Migration complétée** : février 2026  
**Backend actuel** : Django REST Framework (dossier `django_backend/`)

## Documentation historique

Pour les détails de la migration et l'historique technique :

- [fastapi-to-django-migration.md](../backend/migration/fastapi-to-django-migration.md) — Récapitulatif complet de la migration
- [migration-switchover-plan.md](../backend/migration/migration-switchover-plan.md) — Plan de bascule production
- [epic-m-final-report.md](../backend/migration/epic-m-final-report.md) — Rapport final de l'Epic M

## Validation finale du décommissionnement (Story 17.1 — 2026-02-06)

Le décommissionnement FastAPI a été **validé exhaustivement** par la story 17.1. Audit complet du dépôt : aucune référence FastAPI active ne subsiste dans le code, la configuration, ou les pipelines CI/CD.

- [Rapport de validation](../backend/migration/fastapi-decommissioning-validation-report.md) — Résultats détaillés de l'audit
- [fastapi-decommissioning-runbook.md](../backend/migration/fastapi-decommissioning-runbook.md) — Runbook de décommissionnement

## Note importante

**Ne pas supprimer** la branche `legacy/fastapi-final` ni le tag `v1.0.0-fastapi`. Ils sont conservés pour :
- Audit et référence historique
- Consultation en cas de besoin de comparaison
- Traçabilité de la migration

Pour tout nouveau développement, utiliser uniquement le backend Django (`django_backend/`).
