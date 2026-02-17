# Story 4.11 : Délégation d’autorisation pour exécution de workflows (actions référencées)
 
Status: done
 
<!-- Note: Validation est optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->
 
## Story
 
En tant que **système**,
je veux **permettre l’exécution de workflows contenant des actions référencées même si l’utilisateur n’a pas accès direct à ces actions**,
afin que **des workflows multi-technologies puissent être exécutés via une délégation d’autorisation portée par le workflow**.
 
## Acceptance Criteria
 
### AC1 — Validation “délégation” lors de la soumission d’exécution
 
**Given** un utilisateur tente d’exécuter un workflow,
**When** l’exécution est soumise (`POST /api/v1/executions`),
**Then** le backend charge les étapes du workflow (depuis `execution_steps` du workflow : `referenced_action_id`)
**And** pour chaque action référencée, le backend vérifie seulement :
- que l’action existe (sinon **HTTP 404**)
- que l’action est publiée (sinon **HTTP 400** si `status != "published"`)
**And** **aucune vérification RBAC individuelle** n’est effectuée sur les actions référencées (délégation).
 
### AC2 — Exécution effective avec délégation
 
**Given** un utilisateur exécute un workflow multi-technologies,
**When** l’utilisateur a accès au workflow (mais pas aux actions référencées individuellement),
**Then** l’exécution est acceptée et se déroule normalement
**And** chaque action référencée est exécutée **avec la délégation du workflow** (pas de check RBAC supplémentaire au runtime).
 
### AC3 — Catalogue: pas d’avertissement / pas de check additionnel
 
**Given** un utilisateur consulte un workflow dans le catalogue,
**When** il a accès au workflow,
**Then** aucun avertissement n’est affiché concernant l’accès aux actions référencées
**And** aucune vérification supplémentaire n’est faite sur les actions référencées au moment de l’affichage.
 
### AC4 — Erreurs explicites
 
**Given** un utilisateur tente d’exécuter un workflow,
**When** une action référencée n’existe plus,
**Then** la requête est rejetée avec **HTTP 404**
**And** le message d’erreur indique : `L'action référencée '{action_id}' n'existe plus ou n'est plus disponible`.
 
**Given** un utilisateur tente d’exécuter un workflow,
**When** une action référencée n’est plus publiée (`status != "published"`),
**Then** la requête est rejetée avec **HTTP 400**
**And** le message d’erreur indique : `L'action référencée '{action_name}' n'est plus publiée (statut: {status})`.
 
### AC5 — Audit trail (SOC1)
 
**Given** un utilisateur tente d’exécuter un workflow,
**When** la validation des actions référencées réussit ou échoue,
**Then** l’audit log enregistre la tentative (succès ou échec avec raison)
**And** l’audit log indique explicitement que l’exécution des actions référencées se fait par **délégation du workflow**.
 
## Tasks / Subtasks
 
- [x] Task 1 (AC: 1, 4) — Charger et valider les actions référencées
  - [x] 1.1 : Identifier le format “workflow” côté backend (champ `Action.item_type == "workflow"`).
  - [x] 1.2 : Extraire `execution_steps` du workflow (JSON) et obtenir la liste des `referenced_action_id` dans l’ordre.
  - [x] 1.3 : Pour chaque `referenced_action_id`, charger l’action référencée et valider :
    - [x] existence → sinon 404 (avec message explicite)
    - [x] `status == "published"` → sinon 400 (avec message explicite)
  - [x] 1.4 : **Ne pas** appliquer de validation RBAC “action-level” sur les actions référencées (délégation).
 
- [x] Task 2 (AC: 2) — Garantir l’absence de RBAC check au runtime sur actions référencées
  - [x] 2.1 : Vérifier que la validation RBAC lors de `POST /api/v1/executions` ne filtre pas/ n’échoue pas sur les actions référencées.
  - [x] 2.2 : S’assurer que l’exécution (création des steps / orchestration) n’introduit pas de check RBAC additionnel par action référencée.
 
- [x] Task 3 (AC: 5) — Audit trail délégation
  - [x] 3.1 : Ajouter un audit “workflow delegation” au moment de la soumission (succès) et/ou en cas d’échec de validation.
  - [x] 3.2 : Inclure dans `details` : `workflow_action_id`, `workflow_action_name`, `referenced_action_ids`, et un flag clair `delegated: true`.
 
- [x] Task 4 (AC: 1-5) — Tests
  - [x] 4.1 : Test “workflow multi-technologies avec délégation” : user autorisé au workflow, pas aux actions référencées → 201 attendu.
  - [x] 4.2 : Test “action référencée supprimée” → 404 + message.
  - [x] 4.3 : Test “action référencée non publiée” → 400 + message.
  - [x] 4.4 : Test audit : entrée créée avec `delegated: true` et liste des referenced actions (succès + échec).
 
## Dev Notes
 
- **Modèle** :
  - `idp-portal/django_backend/catalog/models.py` : `Action.item_type` (`action|workflow`) et `ActionStatus` (`published|draft|disabled`).
  - `execution_steps` d’un workflow contient des steps avec `referenced_action_id` (cf. conversion `workflow_steps` dans `catalog/serializers.py`).
 
- **API d’exécution** :
  - `idp-portal/django_backend/executions/views.py` : `ExecutionsView.post()` implémente `POST /api/v1/executions`.
  - Aujourd’hui, `ExecutionsView.post()` charge l’action demandée via `Action.objects.get(id=int(action_id), status="published")` et gère fortement la validation `target_names` (Stories 13.x). La logique workflow/délégation doit s’insérer sans casser cette validation existante.
 
- **Audit** :
  - `idp-portal/django_backend/executions/services.py` utilise `AuditService.create_entry(...)` et `AuditActionType.EXECUTION_SUBMITTED`. La story 4.11 nécessite une entrée qui explicite la **délégation** et le résultat de la validation des actions référencées.
  - La base a des tests SOC1/security qui surveillent des patterns d’audit: rester cohérent avec les enums (`core/models.py`).
 
### Guardrails (anti-erreurs LLM / dev)
 
- **Ne pas confondre “visibilité catalogue” et “autorisation d’exécuter”**: la story ne change pas la visibilité d’un workflow dans le catalogue.
- **Ne pas implémenter une “union” RBAC sur actions référencées**: la règle est une délégation simple (accès au workflow ⇒ exécution des actions référencées).
- **Ne pas exécuter une action référencée non publiée**: c’est une erreur 400 et doit être détectée avant création de l’exécution.
- **Ne pas créer d’exécution partielle**: la validation des referenced actions doit être effectuée **avant** la création/écriture de l’exécution.
- **Messages d’erreur stables**: nécessaires pour les tests (et pour UX).
 
## References
 
- `_bmad-output/planning-artifacts/epics.md` — “Epic 4 : Execution & Suivi Temps Réel” → “Story 4.11 : Délégation d’autorisation …” (AC et règles métier).
- `idp-portal/django_backend/catalog/serializers.py` — `get_workflow_steps()` (format `referenced_action_id`).
- `idp-portal/django_backend/executions/views.py` — `ExecutionsView.post()` (point d’entrée `POST /api/v1/executions`).
 
## Dev Agent Record
 
### Agent Model Used
 
GPT-5.2
 
### Debug Log References
 
### Completion Notes List
 
- Implémenté validation “délégation” sur `POST /api/v1/executions` pour workflows: existence + `published` uniquement, sans RBAC par action référencée.
- Ajout audit explicite `delegated: true` (succès + échec avant création exécution).
- Tests ajoutés et passants avec `DJANGO_SETTINGS_MODULE=idp_backend.test_settings` (SQLite): `executions/tests/test_story_4_11.py`.
- **Code review 2026-02-06**: 5 fixes appliqués — (1) NameError correlation_id dans services.update_status, (2) AC4 messages multiples actions invalides (liste complète), (3) suppression duplication audit workflow via delegated_referenced_action_ids, (4) rejet workflow vide (400 WORKFLOW_EMPTY), (5) tests DRF robustes + 3 nouveaux tests (multi-missing, multi-not-published, workflow vide). 6/6 Story 4.11 + 3/3 services tests pass.
 
### File List
 
- `_bmad-output/implementation-artifacts/4-11-validation-rbac-execution-workflows-actions-referencees.md`
- `idp-portal/django_backend/executions/views.py`
- `idp-portal/django_backend/catalog/models.py`
- `idp-portal/django_backend/catalog/serializers.py`
- `idp-portal/django_backend/executions/services.py`
- `idp-portal/django_backend/executions/tests/test_story_4_11.py`
# Story 4.11 : Délégation d'autorisation pour exécution de workflows (actions référencées)

Status: backlog

## Story

As a système,
I want permettre l'exécution de workflows contenant des actions référencées même si l'utilisateur n'a pas accès direct à ces actions,
So que les workflows multitechnologies puissent être exécutés par délégation d'autorisation.

## Contexte

**Contexte Epic 4 — Execution & Suivi Temps Reel :**

Les workflows peuvent contenir des actions de plusieurs technologies (Oracle, SQL Server, DB2, etc.). Un utilisateur peut voir un workflow s'il a accès au workflow lui-même (via tags/ID). **Lors de l'exécution, le workflow délègue l'autorisation d'exécuter les actions référencées** : si l'utilisateur a accès au workflow, il peut exécuter toutes les actions référencées même s'il n'a pas accès direct à ces actions.

**Règles métier définies :**

1. **Visibilité** : Un utilisateur voit un workflow s'il a accès au workflow lui-même (comportement actuel, pas de changement)
2. **Exécution** : Un utilisateur peut exécuter un workflow s'il a accès au workflow. Les actions référencées sont exécutées avec les permissions du workflow (délégation d'autorisation). **Pas besoin de vérifier les permissions individuelles sur chaque action référencée.**
3. **Affichage** : Pas d'avertissement dans le catalogue si l'utilisateur n'a pas accès à toutes les actions référencées

**Cas d'usage :**

- Un utilisateur Oracle peut exécuter un workflow contenant des actions SQL Server s'il a accès au workflow
- Un workflow multitechnologie peut être exécuté par un utilisateur ayant accès au workflow, même s'il n'a pas accès à toutes les technologies individuelles
- C'est une délégation : le workflow "délègue" l'autorisation d'exécuter les actions référencées

**État actuel :**

- Les workflows sont filtrés dans le catalogue comme des actions normales (via tags/ID)
- La validation RBAC lors de l'exécution vérifie seulement l'accès au workflow lui-même
- Story 5.7 a créé le modèle de données pour les workflows mais l'exécution n'est pas encore implémentée (Task 3 non complétée)

**Objectif de cette story :**

Implémenter la délégation d'autorisation lors de l'exécution des workflows : valider seulement l'existence et le statut publié des actions référencées, sans vérifier les permissions RBAC individuelles sur ces actions.

## Acceptance Criteria

### AC1 — Validation de l'existence et du statut des actions référencées

**Given** un utilisateur tente d'exécuter un workflow (POST /api/v1/executions avec action_id d'un workflow),
**When** l'execution est soumise,
**Then** le backend charge les étapes du workflow depuis `workflow_steps` (ou `execution_steps` si workflow)
**And** pour chaque étape avec `referenced_action_id`, le backend charge l'action référencée
**And** pour chaque action référencée, le backend vérifie seulement :
  - Que l'action existe (404 si non trouvée)
  - Que l'action est publiée (400 si status != 'published')
**And** **PAS de vérification des permissions RBAC individuelles** sur les actions référencées

**Given** le backend valide les actions référencées,
**When** toutes les validations passent (existence + statut publié),
**Then** l'exécution du workflow peut procéder normalement
**And** les actions référencées sont exécutées avec les permissions du workflow (délégation)

### AC2 — Rejet si action référencée n'existe plus

**Given** un utilisateur tente d'exécuter un workflow contenant des actions référencées,
**When** une action référencée n'existe plus (supprimée de la base de données),
**Then** l'exécution est rejetée avec HTTP 404 Not Found
**And** le message d'erreur indique : "L'action référencée '{action_id}' n'existe plus ou n'est plus disponible"
**And** les détails de l'erreur incluent : `referenced_action_id`, `workflow_id`, `workflow_name`

**Given** plusieurs actions référencées n'existent plus,
**When** le backend valide les actions référencées,
**Then** toutes les actions manquantes sont listées dans le message d'erreur
**And** le format est : "Les actions référencées suivantes n'existent plus : '{action_id_1}', '{action_id_2}'"

### AC3 — Rejet si action référencée non publiée

**Given** un utilisateur tente d'exécuter un workflow,
**When** une action référencée n'est plus publiée (`status != 'published'`),
**Then** l'exécution est rejetée avec HTTP 400 Bad Request
**And** le message d'erreur indique : "L'action référencée '{action_name}' n'est plus publiée (statut: {status})"
**And** les détails incluent : `referenced_action_id`, `action_name`, `status`, `workflow_id`, `workflow_name`

**Given** un utilisateur tente d'exécuter un workflow,
**When** une action référencée est désactivée (`status == 'disabled'`),
**Then** l'exécution est rejetée avec HTTP 400 Bad Request
**And** le message d'erreur indique : "L'action référencée '{action_name}' est désactivée"

**Given** plusieurs actions référencées ne sont pas publiées,
**When** le backend valide les actions référencées,
**Then** toutes les actions non publiées sont listées dans le message d'erreur
**And** le format est : "Les actions référencées suivantes ne sont plus publiées : '{action_name_1}' (statut: {status_1}), '{action_name_2}' (statut: {status_2})"

### AC4 — Exécution avec délégation d'autorisation

**Given** un utilisateur tente d'exécuter un workflow,
**When** toutes les actions référencées sont validées avec succès (existence + statut publié),
**Then** l'exécution du workflow peut procéder normalement
**And** chaque action référencée est exécutée dans l'ordre **avec les permissions du workflow** (délégation)
**And** **aucune vérification RBAC supplémentaire** n'est effectuée lors de l'exécution de chaque action référencée
**And** le système considère que l'accès au workflow autorise l'exécution de toutes ses actions référencées

**Given** un utilisateur Oracle exécute un workflow contenant des actions SQL Server,
**When** l'utilisateur a accès au workflow (mais pas aux actions SQL Server individuelles),
**Then** le workflow peut être exécuté avec succès
**And** les actions SQL Server référencées sont exécutées grâce à la délégation du workflow

### AC5 — Pas de changement pour la visibilité dans le catalogue

**Given** un utilisateur consulte un workflow dans le catalogue,
**When** il voit le workflow (accès via tags/ID du workflow),
**Then** aucune vérification supplémentaire n'est effectuée sur les actions référencées
**And** aucun avertissement n'est affiché concernant les permissions sur les actions référencées
**And** le comportement actuel du filtrage RBAC dans le catalogue reste inchangé

### AC6 — Audit et traçabilité

**Given** un utilisateur tente d'exécuter un workflow,
**When** la validation est effectuée,
**Then** l'audit log enregistre la tentative d'exécution avec :
- Type : `EXECUTION_SUBMITTED` si succès, `EXECUTION_DENIED` si échec
- Détails : liste des actions référencées validées, ou liste des actions invalides en cas d'échec
- Raison du refus : si échec, la raison (action supprimée, action non publiée)
- **Note de délégation** : indication que les actions référencées sont exécutées avec les permissions du workflow

**Given** une exécution de workflow est rejetée pour action référencée invalide,
**When** l'audit log est créé,
**Then** le type d'action est `EXECUTION_DENIED`
**And** les détails incluent : `workflow_id`, `workflow_name`, `invalid_actions` (liste des actions invalides avec raison)

## Implementation Tasks

### Task 1: Ajouter la validation des actions référencées dans ExecutionsView.post

- [ ] Subtask 1.1: Détecter si l'action est un workflow
  - [ ] Dans `ExecutionsView.post`, après avoir chargé l'action, vérifier `action.item_type == 'workflow'`
  - [ ] Si workflow, charger les étapes workflow (`workflow_steps` ou `execution_steps`)

- [ ] Subtask 1.2: Valider les actions référencées pour un workflow (existence + statut seulement)
  - [ ] Créer fonction `_validate_workflow_referenced_actions(user, workflow_action)`
  - [ ] Pour chaque étape avec `referenced_action_id`, charger l'action référencée
  - [ ] Vérifier que l'action existe (404 si non trouvée)
  - [ ] Vérifier que l'action est publiée (400 si status != 'published')
  - [ ] **NE PAS vérifier les permissions RBAC** sur les actions référencées (délégation)
  - [ ] Collecter toutes les erreurs avant de rejeter (pour afficher toutes les actions invalides)

- [ ] Subtask 1.3: Rejeter avec message d'erreur approprié
  - [ ] Si action supprimée : HTTP 404 avec message
  - [ ] Si action non publiée : HTTP 400 avec message incluant le statut

### Task 2: Créer fonction de validation workflow (sans RBAC)

- [ ] Subtask 2.1: Créer `_validate_workflow_referenced_actions` dans `executions/views.py`
  - [ ] Signature : `_validate_workflow_referenced_actions(user: User, workflow_action: Action) -> None`
  - [ ] Lève `NotFoundError` si action référencée n'existe plus
  - [ ] Lève `BadRequestError` si action référencée non publiée
  - [ ] **Ne prend PAS `cumulative_permissions` en paramètre** (pas de validation RBAC)

- [ ] Subtask 2.2: Charger les étapes workflow
  - [ ] Utiliser `workflow_action.get_workflow_steps()` ou parser `execution_steps` si workflow
  - [ ] Extraire les `referenced_action_id` de chaque étape
  - [ ] Dédupliquer les IDs (une action peut être référencée plusieurs fois)

- [ ] Subtask 2.3: Valider chaque action référencée (existence + statut seulement)
  - [ ] Pour chaque `referenced_action_id`, charger l'action depuis la base
  - [ ] Vérifier existence (Action.DoesNotExist → 404)
  - [ ] Vérifier statut (status != 'published' → 400)
  - [ ] **PAS de vérification RBAC** (`_check_rbac_for_action` n'est PAS appelée)
  - [ ] Collecter les erreurs pour toutes les actions avant de rejeter

### Task 3: Implémenter la délégation lors de l'exécution des actions référencées

- [ ] Subtask 3.1: Modifier le moteur d'exécution pour accepter la délégation
  - [ ] Lors de l'exécution d'une action référencée dans un workflow, utiliser les permissions du workflow
  - [ ] S'assurer que le système ne vérifie pas les permissions individuelles sur les actions référencées
  - [ ] Passer un flag `delegated_from_workflow=True` lors de l'exécution des actions référencées

- [ ] Subtask 3.2: Mettre à jour l'audit log pour indiquer la délégation
  - [ ] Ajouter `delegated_from_workflow` dans les détails d'audit pour les actions référencées
  - [ ] Ajouter `workflow_id` et `workflow_name` dans les détails d'exécution des actions référencées
  - [ ] Indiquer que l'autorisation provient du workflow (délégation)

### Task 4: Tests

- [ ] Subtask 4.1: Tests pour validation workflow (existence + statut)
  - [ ] Test qu'un utilisateur peut exécuter un workflow si toutes les actions référencées existent et sont publiées
  - [ ] Test qu'un utilisateur ne peut pas exécuter un workflow si une action référencée n'existe plus (404)
  - [ ] Test qu'un utilisateur ne peut pas exécuter un workflow si plusieurs actions référencées n'existent plus (404 avec liste)
  - [ ] Test qu'un utilisateur ne peut pas exécuter un workflow si une action référencée n'est plus publiée (400)
  - [ ] Test qu'un utilisateur ne peut pas exécuter un workflow si plusieurs actions référencées ne sont plus publiées (400 avec liste)

- [ ] Subtask 4.2: Tests pour délégation d'autorisation
  - [ ] Test qu'un utilisateur Oracle peut exécuter un workflow contenant des actions SQL Server s'il a accès au workflow
  - [ ] Test qu'un utilisateur peut exécuter un workflow même s'il n'a pas accès direct aux actions référencées
  - [ ] Test qu'un utilisateur DBOPS peut exécuter un workflow multitechnologie
  - [ ] Test que les actions référencées sont exécutées avec succès grâce à la délégation

- [ ] Subtask 4.3: Tests d'audit
  - [ ] Test que l'audit log enregistre les validations réussies avec note de délégation
  - [ ] Test que l'audit log enregistre les refus avec raison appropriée (action supprimée/non publiée)
  - [ ] Test que l'audit log indique que les actions référencées sont exécutées avec délégation

## Notes techniques

### Chargement des étapes workflow

Les workflows stockent leurs étapes dans `execution_steps` (CLOB JSON) avec le format :
```json
[
  {
    "order": 1,
    "name": "Étape 1",
    "referenced_action_id": 5
  },
  {
    "order": 2,
    "name": "Étape 2",
    "referenced_action_id": 8
  }
]
```

Utiliser `action.get_workflow_steps()` ou parser `execution_steps` pour extraire les `referenced_action_id`.

### Délégation d'autorisation

**Principe :** Si un utilisateur a accès à un workflow (via RBAC), il peut exécuter toutes les actions référencées dans ce workflow, même s'il n'a pas accès direct à ces actions.

**Implémentation :**
- Lors de l'exécution d'une action référencée dans un workflow, le système ne vérifie PAS les permissions RBAC individuelles sur cette action
- Le système considère que l'accès au workflow autorise l'exécution de toutes ses actions référencées
- Cette délégation doit être tracée dans l'audit log pour la conformité SOC1

### Ordre de validation

1. Charger le workflow et ses étapes
2. Extraire les `referenced_action_id` (dédupliquer)
3. Pour chaque action référencée :
   - Vérifier existence (404)
   - Vérifier statut publié (400)
   - **PAS de vérification RBAC** (délégation)
4. Si toutes les validations passent, créer l'exécution
5. Si une validation échoue, rejeter avec message approprié

### Messages d'erreur

**404 - Action supprimée :**
```json
{
  "error": {
    "code": "REFERENCED_ACTION_NOT_FOUND",
    "message": "L'action référencée '5' n'existe plus ou n'est plus disponible",
    "details": {
      "workflow_id": 10,
      "workflow_name": "Provisionnement complet",
      "referenced_action_id": 5
    }
  }
}
```

**400 - Action non publiée :**
```json
{
  "error": {
    "code": "REFERENCED_ACTION_NOT_PUBLISHED",
    "message": "L'action référencée 'Créer PDB Oracle' n'est plus publiée (statut: disabled)",
    "details": {
      "workflow_id": 10,
      "workflow_name": "Provisionnement complet",
      "referenced_action_id": 5,
      "action_name": "Créer PDB Oracle",
      "status": "disabled"
    }
  }
}
```

### Audit log pour délégation

Lors de l'exécution d'une action référencée dans un workflow, l'audit log doit inclure :
```json
{
  "action_type": "EXECUTION_SUBMITTED",
  "entity_type": "EXECUTION",
  "details": {
    "action_id": 5,
    "action_name": "Créer PDB Oracle",
    "delegated_from_workflow": true,
    "workflow_id": 10,
    "workflow_name": "Provisionnement complet",
    "delegation_reason": "Action référencée exécutée avec les permissions du workflow"
  }
}
```

## Références

- Story 5.7 : Workflow — conteneur d'actions et icône identifiable dans le catalogue
- Story 4.3 : Moteur d'exécution et facade API
- Story 7.3 : RBAC granulaire par action, profil et environnement
- `django_backend/executions/views.py` : ExecutionsView.post pour ajouter la validation
- `django_backend/catalog/models.py` : Action.get_workflow_steps() pour charger les étapes workflow
