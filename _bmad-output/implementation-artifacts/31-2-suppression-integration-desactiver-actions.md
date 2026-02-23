# Story 31.2 : Suppression d'intégration — désactiver les actions qui l'utilisent

Status: done

## Story

En tant que DBOPS,
je veux que lorsqu'une intégration est supprimée, toutes les actions qui référencent cette intégration passent en statut **désactivé** (disabled),
afin de ne pas laisser des actions « orphelines » encore publiées alors qu'elles ne peuvent plus s'exécuter.

## Acceptance Criteria

1. **Given** une intégration I est utilisée par au moins une action (`action.integration_id = I`)
   **When** un DBOPS supprime l'intégration I (`DELETE /api/v1/admin/integrations/{id}/`)
   **Then** avant la suppression effective, toutes les actions dont `integration_id = I` passent en statut `disabled`

2. **And** une entrée d'audit est créée pour chaque action désactivée (type `ACTION_DISABLED` ou équivalent), indiquant la raison : suppression de l'intégration

3. **And** la réponse de l'API de suppression inclut un champ informatif (`disabled_actions_count`) indiquant le nombre d'actions désactivées (0 si aucune)

4. **And** si aucune action n'utilise l'intégration, la suppression se comporte comme aujourd'hui (suppression directe, pas d'erreur)

5. **And** des tests backend (et optionnellement frontend) valident le scénario : suppression intégration utilisée → actions concernées en `disabled`, `integration_id` mis à NULL via `SET_NULL`

6. **And** l'audit trail de suppression de l'intégration (`INTEGRATION_DELETED`) inclut dans ses `details` le nombre d'actions désactivées (ex. `{'name': '...', 'disabled_actions_count': N}`)

## Tasks / Subtasks

- [x] Task 1 — Ajouter l'AuditActionType manquant si nécessaire (AC: #2)
  - [x] 1.1 Vérifier si `ACTION_DISABLED` (ou `ACTION_DISABLED_INTEGRATION_DELETED`) existe dans `core/models.py` → `AuditActionType`
  - [x] 1.2 Si absent, ajouter `ACTION_DISABLED_INTEGRATION_DELETED = 'ACTION_DISABLED_INTEGRATION_DELETED', 'Action Disabled - Integration Deleted'`

- [x] Task 2 — Modifier `IntegrationService.delete_integration()` (AC: #1, #2, #3, #4, #6)
  - [x] 2.1 Dans `integrations/services.py`, méthode `delete_integration()` (lignes 283-322) : **supprimer** le bloc qui lève `ValueError` si `linked_actions` existe
  - [x] 2.2 Avant l'appel à `integration.delete()`, récupérer toutes les actions liées
  - [x] 2.3 Pour chaque action liée, passer le statut à `disabled` avec soft-delete fields et audit par action
  - [x] 2.4 Supprimer l'intégration (`integration.delete()`) — la FK `SET_NULL` met automatiquement `integration_id` à NULL sur les actions
  - [x] 2.5 Modifier l'audit `INTEGRATION_DELETED` pour inclure `disabled_actions_count` dans `details`
  - [x] 2.6 Retourner un dict (ou un objet) avec `{'deleted': True, 'disabled_actions_count': disabled_count}` au lieu de `True`

- [x] Task 3 — Adapter la vue `IntegrationViewSet.destroy()` (AC: #3)
  - [x] 3.1 Dans `integrations/views.py`, méthode `destroy()` : adapter la réponse pour inclure `disabled_actions_count`
  - [x] 3.2 Remplacer le bloc `try/except ValueError` (logique d'erreur DEPENDENCY_ERROR) qui bloquait la suppression
  - [x] 3.3 Retourner un `Response({'disabled_actions_count': result['disabled_actions_count']}, status=status.HTTP_200_OK)` si des actions ont été désactivées, sinon `204 No Content`

- [x] Task 4 — Écrire les tests backend (AC: #5)
  - [x] 4.1 Créer ou enrichir les tests dans `integrations/tests/` (ex. `test_integration_service.py` ou `test_integration_views.py`)
  - [x] 4.2 Test : suppression intégration **sans** actions liées → `204` ou `200 {disabled_actions_count: 0}`, intégration supprimée
  - [x] 4.3 Test : suppression intégration **avec** N actions liées → `200 {disabled_actions_count: N}`, actions passées en `disabled`, `integration_id = NULL` sur les actions
  - [x] 4.4 Test : vérifier l'audit trail créé pour chaque action désactivée
  - [x] 4.5 Test : vérifier l'audit `INTEGRATION_DELETED` inclut `disabled_actions_count` dans `details`
  - [x] 4.6 Test : les actions déjà `disabled` avant la suppression ne sont pas ré-auditées inutilement (comportement acceptable : les désactiver à nouveau ne pose pas de problème, mais les compter dans `disabled_count` reste OK)

- [x] Task 5 — Adaptation frontend (optionnel — message post-suppression) (AC: #3)
  - [x] 5.1 Dans le composant Admin Intégrations (probablement `AdminPage.tsx` ou `IntegrationsPanel.tsx`), après l'appel DELETE, inspecter la réponse
  - [x] 5.2 Si `disabled_actions_count > 0`, afficher un message (notification ou Alert) : « Intégration supprimée. N action(s) associée(s) ont été désactivées. »
  - [x] 5.3 Si `disabled_actions_count === 0`, comportement actuel (notification simple de succès)

## Dev Notes

### Contexte et état actuel (après Story 31.1)

Après Story 31.1, le formulaire d'action utilise `integration_id` (FK vers `Integration`) comme champ central. Il est donc critique que la suppression d'une intégration ne laisse pas des actions publiées orphelines.

**Comportement actuel (à modifier) :**
```python
# integrations/services.py - delete_integration()
linked_actions = Action.objects.filter(integration_id=integration_id).exists()
if linked_actions:
    raise ValueError("Impossible de supprimer une intégration avec des actions liées")
# → L'API retourne 409 DEPENDENCY_ERROR → BLOQUER la suppression
```

**Comportement cible :**
- Désactiver les actions liées **avant** la suppression de l'intégration
- Supprimer l'intégration (la FK `SET_NULL` met `integration_id = NULL` automatiquement)
- Retourner le nombre d'actions désactivées dans la réponse

### Modèle Action — champs de désactivation (Story 18.1)

```python
# catalog/models.py
class Action(models.Model):
    status = models.CharField(choices=ActionStatus.choices, default=ActionStatus.DRAFT)
    deleted_at = models.DateTimeField(null=True, blank=True)     # soft-delete timestamp
    deleted_by = models.ForeignKey(User, null=True, blank=True, related_name='disabled_actions', ...)
    deletion_reason = models.CharField(max_length=500, null=True, blank=True)

    integration = models.ForeignKey(
        Integration,
        on_delete=models.SET_NULL,  # ← la FK devient NULL automatiquement
        null=True, blank=True,
        db_column='INTEGRATION_ID'
    )
```

Le champ `deleted_by` est une FK vers User — vérifier son `null=True` avant de l'assigner. Si le user n'est pas disponible (suppression programmatique), laisser NULL.

### AuditActionType existants liés aux intégrations

```python
# core/models.py
INTEGRATION_CREATED = 'INTEGRATION_CREATED'
INTEGRATION_UPDATED = 'INTEGRATION_UPDATED'
INTEGRATION_DELETED = 'INTEGRATION_DELETED'
INTEGRATION_STATUS_UPDATED = 'INTEGRATION_STATUS_UPDATED'
EXECUTION_BLOCKED_INVALID_INTEGRATION = 'EXECUTION_BLOCKED_INVALID_INTEGRATION'
```

À ajouter si absent :
```python
ACTION_DISABLED_INTEGRATION_DELETED = 'ACTION_DISABLED_INTEGRATION_DELETED', 'Action Disabled - Integration Deleted'
```

Alternativement, utiliser `ACTION_DISABLED` si ce type existe déjà (vérifier `AuditActionType` dans `core/models.py`).

### Service delete_integration — implémentation cible

```python
@transaction.atomic
def delete_integration(self, integration_id: int, user=None):
    """Delete integration and disable all linked actions."""
    try:
        integration = Integration.objects.get(id=integration_id)
    except Integration.DoesNotExist:
        return False

    integration_name = integration.name

    # 1. Désactiver les actions liées avant suppression
    linked_actions = list(Action.objects.filter(integration_id=integration_id))
    now = timezone.now()
    disabled_count = 0

    for action in linked_actions:
        action.status = ActionStatus.DISABLED
        action.deleted_at = now
        action.deletion_reason = f"Intégration supprimée : {integration_name}"
        fields = ['status', 'deleted_at', 'deletion_reason']
        if user and hasattr(action, 'deleted_by_id'):
            action.deleted_by = user
            fields.append('deleted_by')
        action.save(update_fields=fields)
        disabled_count += 1

        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.ACTION_DISABLED_INTEGRATION_DELETED,
                entity_type=AuditEntityType.ACTION,
                entity_id=action.id,
                details={
                    'action_name': action.name,
                    'integration_id': integration_id,
                    'integration_name': integration_name,
                    'reason': 'integration_deleted'
                }
            )

    # 2. Supprimer l'intégration (SET_NULL met integration_id=NULL sur les actions)
    integration.delete()

    # 3. Audit de la suppression avec le count
    if user:
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.INTEGRATION_DELETED,
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration_id,
            details={
                'name': integration_name,
                'disabled_actions_count': disabled_count
            }
        )

    return {'deleted': True, 'disabled_actions_count': disabled_count}
```

### Vue destroy — adaptation

```python
def destroy(self, request, pk=None):
    """DELETE /admin/integrations/{id}/ - Delete integration and disable linked actions."""
    try:
        integration_id = int(pk)
    except (TypeError, ValueError):
        raise ValidationError({'detail': 'ID invalide'})

    service = IntegrationService()
    result = service.delete_integration(integration_id, user=request.user)

    if not result:
        return Response({'detail': 'Integration introuvable'}, status=status.HTTP_404_NOT_FOUND)
    if result['disabled_actions_count'] > 0:
        return Response(
            {'disabled_actions_count': result['disabled_actions_count']},
            status=status.HTTP_200_OK
        )
    return Response(status=status.HTTP_204_NO_CONTENT)
```

**Attention :** Vérifier si l'appel à `destroy()` contient encore un bloc `try/except ValueError` hérité de la logique DEPENDENCY_ERROR — le supprimer ou l'adapter.

### Frontend — message post-suppression

Chercher dans `frontend/src/components/admin/` le composant qui affiche la liste des intégrations et effectue l'appel DELETE. Il s'agit probablement de l'onglet « Intégrations » de `AdminPage.tsx` ou d'un composant `IntegrationsPanel.tsx`.

Adapter le callback de succès :
```typescript
const onDeleteSuccess = (response: any) => {
  const count = response?.disabled_actions_count ?? 0;
  if (count > 0) {
    notification.warning({
      message: 'Intégration supprimée',
      description: `${count} action(s) associée(s) ont été désactivées.`,
    });
  } else {
    notification.success({
      message: 'Intégration supprimée avec succès',
    });
  }
  // Rafraîchir la liste
};
```

### Pattern de transaction atomique

La méthode `delete_integration` est déjà `@transaction.atomic`. Si la désactivation d'une action ou l'audit échoue, la transaction entière sera annulée (y compris la suppression de l'intégration). C'est le comportement souhaité pour garantir la cohérence.

### Points de vigilance

1. **`deleted_by` peut être une FK non-nullable** : vérifier `catalog/models.py` avant d'assigner. Utiliser `getattr(action, 'deleted_by_id', None) is not None` pour tester la présence du champ.
2. **Actions déjà disabled** : les désactiver à nouveau (idempotent) est OK — elles seront comptées dans `disabled_count`.
3. **`SET_NULL` est automatique** : après `integration.delete()`, les actions désactivées auront `integration_id = NULL` sans intervention manuelle.
4. **Ne pas modifier le backend de validation de l'exécution** : la validation `EXECUTION_BLOCKED_INVALID_INTEGRATION` (Story 24.3) couvre déjà le cas d'intégration invalide/supprimée. La désactivation des actions est complémentaire.
5. **Cohérence avec Story 18.1** : utiliser exactement le même pattern de soft-delete que Story 18.1 (champs `deleted_at`, `deletion_reason`, `deleted_by`).

### Project Structure Notes

- Service : `integrations/services.py` — classe `IntegrationService`, méthode `delete_integration()`
- Vue : `integrations/views.py` — classe `IntegrationViewSet`, méthode `destroy()`
- Audit types : `core/models.py` — classe `AuditActionType`
- Modèle Action : `catalog/models.py` — champs `status`, `deleted_at`, `deleted_by`, `deletion_reason`, `integration`
- Tests : `integrations/tests/test_integration_service.py` ou `test_integration_views.py`
- Frontend : `frontend/src/components/admin/AdminPage.tsx` (onglet intégrations) ou composant dédié

### References

- [Source: _bmad-output/planning-artifacts/epic-31-admin-catalogue-integrations-et-icones-moteurs.md#Story 31.2]
- [Source: django_backend/integrations/services.py#L283-322] — méthode `delete_integration()` à modifier
- [Source: django_backend/integrations/views.py#L160-199] — vue `destroy()` à adapter
- [Source: django_backend/catalog/models.py#L38-42] — `ActionStatus` (DRAFT, PUBLISHED, DISABLED)
- [Source: django_backend/catalog/models.py#L248-275] — champs soft-delete (`deleted_at`, `deleted_by`, `deletion_reason`) et FK `integration`
- [Source: django_backend/core/models.py#L29-31, L74-82] — `AuditActionType` existants
- [Source: _bmad-output/implementation-artifacts/31-1-formulaire-action-liste-integrations-label-integration.md] — Story précédente (contexte `integration_id` sur Action)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

- ✅ Task 1: `ACTION_DISABLED_INTEGRATION_DELETED` ajouté à `AuditActionType` (core/models.py)
- ✅ Task 2: `delete_integration()` refactoré — désactive les actions liées (soft-delete: status=disabled, deleted_at, deletion_reason, deleted_by), audit par action, retourne `{'deleted': True, 'disabled_actions_count': N}`
- ✅ Task 3: `destroy()` vue adaptée — 200 avec `disabled_actions_count` si actions désactivées, 204 sinon. Suppression du bloc DEPENDENCY_ERROR
- ✅ Task 4: 7 tests service + 4 tests vue ajoutés/modifiés (31 tests intégrations passent, 376 total pass, 8 fails pré-existants fixtures)
- ✅ Task 5: Frontend — `deleteIntegration()` retourne `disabled_actions_count`, notification warning si actions désactivées, success sinon

### Senior Developer Review (AI)

**Date :** 2026-02-19 | **Reviewer :** Cyrille (claude-sonnet-4-6)
**Résultat :** ✅ APPROUVÉ après corrections automatiques

**Problèmes trouvés et corrigés (3 fixes) :**
- 🔴 [HIGH] `updated_at` non mis à jour lors de la désactivation des actions — `services.py:314` : `Action.updated_at` est `DateTimeField(null=True)` (pas `auto_now`), absent de `update_fields`. Fix : ajout de `action.updated_at = now` et `'updated_at'` dans `update_fields`. ✅ Corrigé
- 🟡 [MEDIUM] Code mort — `except ValueError` dans `destroy()` — `views.py:176-183` : `delete_integration()` ne lève plus `ValueError` depuis Story 31.2. Bloc jamais déclenché. ✅ Supprimé
- 🟡 [MEDIUM] Assertion manquante sur `updated_at` dans `test_delete_integration_with_linked_actions_disables_them` — `test_services.py:285`. ✅ Ajoutée

**Problèmes non bloquants (2 LOW, non corrigés) :**
- 🟢 [LOW] `hasattr(action, 'deleted_by_id')` check défensif absent — Dev Notes le recommandaient ; intégré dans le fix HIGH-1 finalement
- 🟢 [LOW] `title` au lieu de `message` dans notifications Ant Design — pattern pré-existant tout le fichier, hors scope Story 31.2

**Tests :** 13/13 tests delete passent après corrections ✅

### Change Log

- 2026-02-19: Story 31.2 implémentée — suppression intégration désactive actions liées (AC1-AC6)
- 2026-02-19: Code review adversarial — 1 HIGH + 2 MEDIUM fixes auto-appliqués (updated_at actions, code mort view, assertion test)

### File List

- `idp-portal/django_backend/core/models.py` — ajout `ACTION_DISABLED_INTEGRATION_DELETED`
- `idp-portal/django_backend/integrations/services.py` — refactoring `delete_integration()`
- `idp-portal/django_backend/integrations/views.py` — adaptation `destroy()` réponse 200/204
- `idp-portal/django_backend/integrations/tests/test_services.py` — 7 tests delete (réécrits + nouveaux)
- `idp-portal/django_backend/integrations/tests/test_integration_views.py` — 4 tests delete (réécrits + nouveaux)
- `idp-portal/frontend/src/services/integrations_service.ts` — `deleteIntegration()` retourne `disabled_actions_count`
- `idp-portal/frontend/src/pages/admin/IntegrationsAdminPanel.tsx` — notification warning/success conditionnelle
