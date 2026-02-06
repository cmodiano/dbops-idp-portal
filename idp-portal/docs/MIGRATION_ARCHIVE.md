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

- [fastapi-to-django-migration.md](fastapi-to-django-migration.md) — Récapitulatif complet de la migration
- [migration-switchover-plan.md](migration-switchover-plan.md) — Plan de bascule production
- [epic-m-final-report.md](epic-m-final-report.md) — Rapport final de l'Epic M

## Note importante

**Ne pas supprimer** la branche `legacy/fastapi-final` ni le tag `v1.0.0-fastapi`. Ils sont conservés pour :
- Audit et référence historique
- Consultation en cas de besoin de comparaison
- Traçabilité de la migration

Pour tout nouveau développement, utiliser uniquement le backend Django (`django_backend/`).
