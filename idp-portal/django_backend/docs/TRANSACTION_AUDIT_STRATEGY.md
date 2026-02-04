# Stratégie de Gestion des Transactions et de l'Audit

## Vue d'ensemble

Ce document décrit la stratégie adoptée pour gérer les transactions atomiques et l'audit dans la migration de FastAPI vers Django ORM.

## 1. Transactions Atomiques

### Stratégie : `@transaction.atomic` sur les méthodes de service

**Approche choisie :** Utilisation du décorateur `@transaction.atomic` de Django sur les méthodes de service qui effectuent des opérations multi-tables.

**Rationale :**
- **Simplicité** : Le décorateur Django est simple à utiliser et bien intégré avec l'ORM
- **Rollback automatique** : En cas d'exception, la transaction est automatiquement annulée
- **Nested transactions** : Support des transactions imbriquées si nécessaire
- **Performance** : Pas de surcharge significative, transactions gérées efficacement par Oracle

**Exemples d'utilisation :**

```python
@transaction.atomic
def create_execution_with_steps(self, user, action, environment, parameters, steps_data):
    """Create execution and steps atomically."""
    execution = Execution.objects.create(...)
    for step_data in steps_data:
        ExecutionStep.objects.create(execution=execution, ...)
    return execution
```

**Opérations multi-tables protégées :**
- `create_execution_with_steps()` : Execution + ExecutionStep
- `create_scheduled_execution()` : ScheduledExecution + RecurringPattern
- `create_action()` : Action + ActionTag (tags)
- `create_profile()` : Profile + ProfileActionPermission/ProfileTargetPermission
- `update_action()` : Action + ActionTag (sync tags)
- Toutes les opérations de mise à jour avec audit

## 2. Audit Logging

### Stratégie : Appels explicites à `AuditService.create_entry()`

**Approche choisie :** Appels explicites à `AuditService.create_entry()` dans les méthodes de service après chaque opération sensible.

**Rationale :**

#### ✅ Avantages des appels explicites :

1. **Contrôle précis** : Chaque service décide exactement quand et comment auditer
2. **Contexte enrichi** : Les services peuvent enrichir les détails d'audit avec des informations métier spécifiques
3. **Performance** : Pas de surcharge liée aux signals Django (appels supplémentaires)
4. **Debuggabilité** : Facile de tracer d'où vient l'entrée d'audit en lisant le code
5. **Flexibilité** : Possibilité d'auditer conditionnellement selon la logique métier
6. **Testabilité** : Facile de mocker `AuditService` dans les tests

#### ❌ Inconvénients des signals Django (non choisis) :

1. **Couplage implicite** : Les signals créent des dépendances cachées difficiles à tracer
2. **Ordre d'exécution** : Difficile de contrôler l'ordre d'exécution des signals
3. **Performance** : Tous les signals sont exécutés même si l'audit n'est pas nécessaire
4. **Contexte limité** : Les signals ont accès limité au contexte de la requête/utilisateur
5. **Debugging difficile** : Plus difficile de comprendre pourquoi un audit a été créé

**Exemple d'utilisation :**

```python
@transaction.atomic
def create_action(self, action_data, created_by_user):
    """Create action with audit."""
    action = Action.objects.create(...)
    
    # Audit avec contexte enrichi
    AuditService.create_entry(
        user_id=str(created_by_user.id),
        action_type='ACTION_CREATED',
        entity_type='action',
        entity_id=action.id,
        details={
            'name': action.name,
            'status': action.status,
            'engine': action.engine,
        }
    )
    
    return action
```

**Opérations auditées :**
- Création : `ACTION_CREATED`, `EXECUTION_SUBMITTED`, `SCHEDULED_EXECUTION_CREATED`, `USER_CREATED`, `PROFILE_CREATED`, `INTEGRATION_CREATED`
- Mise à jour : `ACTION_UPDATED`, `EXECUTION_{STATUS}`, `USER_UPDATED`, `PROFILE_UPDATED`, `INTEGRATION_UPDATED`
- Transitions : `ACTION_PUBLISHED`, `ACTION_DISABLED`, `ACTION_ENABLED`
- Suppression : `ACTION_DELETED`, `PROFILE_DELETED`, `INTEGRATION_DELETED`
- Favoris : `FAVORITE_ADDED`, `FAVORITE_REMOVED`
- Scheduled executions : `SCHEDULED_EXECUTION_CANCELLED`, `SCHEDULED_EXECUTION_RECURRING_CREATED`, etc.

## 3. Couverture des AuditActionType

### Types d'audit définis dans `AuditActionType` (core/models.py) :

**Base types (V004) :**
- `ACTION_CREATED` ✅ Utilisé dans `CatalogService.create_action()`
- `ACTION_UPDATED` ✅ Utilisé dans `CatalogService.update_action()`
- `ACTION_PUBLISHED` ✅ Utilisé dans `CatalogService.update_status(transition='publish')`
- `ACTION_DISABLED` ✅ Utilisé dans `CatalogService.update_status(transition='disable')`
- `ACTION_ENABLED` ✅ Utilisé dans `CatalogService.update_status(transition='enable')`

### Types d'audit utilisés mais non définis dans l'enum (strings) :

**Note :** Ces types sont utilisés comme strings dans les services mais ne sont pas encore dans l'enum `AuditActionType`. Ils devront être ajoutés via migration si nécessaire :

- `EXECUTION_SUBMITTED` ✅ Utilisé dans `ExecutionService.create_execution()`
- `EXECUTION_RUNNING` ✅ Utilisé dans `ExecutionService.update_status()`
- `EXECUTION_COMPLETED` ✅ Utilisé dans `ExecutionService.update_status()`
- `EXECUTION_FAILED` ✅ Utilisé dans `ExecutionService.update_status()`
- `EXECUTION_CANCELLED` ✅ Utilisé dans `ExecutionService.update_status()`
- `SCHEDULED_EXECUTION_CREATED` ✅ Utilisé dans `SchedulingService.create_scheduled_execution()`
- `SCHEDULED_EXECUTION_RECURRING_CREATED` ✅ Utilisé dans `SchedulingService.create_scheduled_execution()`
- `SCHEDULED_EXECUTION_CANCELLED` ✅ Utilisé dans `SchedulingService.cancel_scheduled_execution()`
- `SCHEDULED_EXECUTION_RECURRING_DISABLED` ✅ Utilisé dans `SchedulingService.cancel_scheduled_execution()`
- `USER_CREATED` ✅ Utilisé dans `AuthService.create_or_update_user()`
- `USER_UPDATED` ✅ Utilisé dans `AuthService.create_or_update_user()`
- `FAVORITE_ADDED` ✅ Utilisé dans `AuthService.add_favorite()`
- `FAVORITE_REMOVED` ✅ Utilisé dans `AuthService.remove_favorite()`
- `PROFILE_CREATED` ✅ Utilisé dans `ProfileService.create_profile()`
- `PROFILE_UPDATED` ✅ Utilisé dans `ProfileService.update_profile()`
- `PROFILE_DELETED` ✅ Utilisé dans `ProfileService.delete_profile()`
- `INTEGRATION_CREATED` ✅ Utilisé dans `IntegrationService.create_integration()`
- `INTEGRATION_UPDATED` ✅ Utilisé dans `IntegrationService.update_integration()`
- `INTEGRATION_DELETED` ✅ Utilisé dans `IntegrationService.delete_integration()`

**Recommandation :** Étendre l'enum `AuditActionType` dans une migration future pour inclure tous ces types, ou utiliser un système plus flexible (CharField sans enum strict).

## 4. Bonnes Pratiques

### Transactions

1. **Toujours utiliser `@transaction.atomic`** pour les opérations multi-tables
2. **Grouper les opérations liées** dans la même transaction
3. **Gérer les exceptions** : Django rollback automatiquement, mais logger les erreurs
4. **Éviter les transactions longues** : Ne pas faire d'appels HTTP/externes dans une transaction

### Audit

1. **Auditer toutes les mutations sensibles** : CREATE, UPDATE, DELETE
2. **Enrichir le contexte** : Inclure des détails métier pertinents dans `details`
3. **Utiliser des types cohérents** : Respecter la convention de nommage `ENTITY_ACTION`
4. **Inclure user_id** : Toujours passer l'ID de l'utilisateur qui effectue l'action
5. **Inclure entity_id** : Toujours passer l'ID de l'entité modifiée

## 5. Migration depuis FastAPI

**Avant (FastAPI) :**
- Transactions gérées manuellement avec `connection.commit()` / `connection.rollback()`
- Audit via `audit_repository.create_entry()` avec SQL direct

**Après (Django ORM) :**
- Transactions via `@transaction.atomic` (gestion automatique)
- Audit via `AuditService.create_entry()` (abstraction ORM)

**Parité fonctionnelle :** ✅ Maintenue - toutes les opérations critiques sont auditées et transactionnelles.
