# ADR-003 : Migration Repositories FastAPI vers Services Django

**Date :** 2026-02-08
**Statut :** Accepté
**Décideurs :** Équipe IDP — Migration Epic M

## Contexte

Le backend FastAPI utilisait le pattern **Repository** : chaque domaine métier avait un repository encapsulant les requêtes SQL brutes (`catalog_repository.py`, `profile_repository.py`, etc.). Ces repositories :
- Contenaient du SQL brut Oracle avec `python-oracledb`
- Géraient manuellement les connexions et transactions
- Mélangeaient parfois logique métier et accès données

La migration vers Django nécessitait de décider comment structurer la couche métier.

## Décision

**Remplacer les Repositories FastAPI par des Services Django** (`catalog_service.py`, `profile_service.py`, etc.) qui :
1. Encapsulent la logique métier (validation, règles, calculs)
2. Utilisent Django ORM pour l'accès aux données (pas de SQL brut sauf cas Oracle-specific)
3. Gèrent les transactions via `@transaction.atomic`
4. Intègrent l'audit trail via `AuditService`
5. Sont appelés exclusivement par les ViewSets DRF (pas d'accès direct aux modèles depuis les vues)

**Pattern type :**
```python
# catalog/services.py
class CatalogService:
    @staticmethod
    @transaction.atomic
    def create_action(data: dict, user) -> Action:
        action = Action.objects.create(**data, created_by=user)
        AuditService.log(AuditActionType.ACTION_CREATED, user, action)
        return action
```

**Conventions :**
- Un service par app : `catalog/services.py`, `profiles/services.py`, `executions/services.py`
- Méthodes statiques ou de classe (pas d'instance state)
- Le service est le seul point d'entrée pour la logique métier
- Les ViewSets appellent les services, jamais l'ORM directement

## Conséquences

### Positives
- Cohérence avec l'écosystème Django — pas de pattern Repository non-standard
- Logique métier centralisée et testable unitairement
- Transactions automatiques via `@transaction.atomic`
- Réutilisabilité : un service peut être appelé par plusieurs vues, commandes management, ou tâches Celery

### Négatives
- Fichiers `services.py` peuvent devenir volumineux (résolu par extraction en sous-modules si nécessaire, ex: `services_export_import.py`)
- Pas de séparation stricte accès données / logique métier (le service fait les deux)

### Neutres
- Le mapping Repository → Service est direct : les méthodes ont les mêmes signatures
- Les tests existants sont adaptés (mock du service au lieu du repository)

## Alternatives Considérées

### Alternative 1 : Conserver le pattern Repository sous Django
- **Description :** Repositories Django encapsulant des QuerySets au lieu de SQL brut
- **Raison du rejet :** Duplication avec Django ORM — un Repository qui appelle `Model.objects.filter()` n'apporte pas de valeur ajoutée par rapport à un Service

### Alternative 2 : Fat Models (logique dans les modèles)
- **Description :** Placer la logique métier dans les méthodes des modèles Django
- **Raison du rejet :** Viole le Single Responsibility Principle — les modèles deviennent trop gros, mélangent schéma et logique, difficiles à tester isolément

## Références

- [Notes migration DRF](../drf-api-migration-notes.md)
- Stories M-3, M-4, M-5 — Migration couche données et APIs
