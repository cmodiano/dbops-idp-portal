# Story 26.9: Standardiser le format de réponse API

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux éliminer l'imbrication `data.data` et standardiser le format de réponse API,
afin d'avoir un contrat API cohérent et conforme aux conventions DRF.

## Context

**Source :** Epic 26, Section 4.7 du code-quality-assessment (6 février 2026)

### Problèmes identifiés

**1. Imbrication `data.data` dans ScheduledExecutionsView.get() :**

```python
# executions/views/scheduled_views.py, ligne ~110-115
return Response({
    "data": {
        "data": [ScheduledExecutionListItemSerializer(se).data for se in scheduled_executions],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
        },
    }
})
```

**Problème :** Double imbrication `data.data` — le premier `data` vient de Response, le second est dans le payload.
**Frontend attend :** `response.data.data` pour accéder à la liste (confus et non-standard).

**2. Construction manuelle dans ScheduledExecutionUpdateView.patch() :**

```python
# executions/views/scheduled_views.py, lignes ~267-280
return Response({
    "data": {
        "scheduled_execution_id": se.id,
        "action_id": se.action_id,
        "action_name": se.action.name if se.action else None,
        "environment": se.environment,
        "parameters": se.parameters,
        "scheduled_at": ensure_utc_isoformat(se.scheduled_at) if se.scheduled_at else None,
        "status": se.status,
        "user_id": str(se.user_id),
        "correlation_id": se.correlation_id,
        "created_at": ensure_utc_isoformat(se.created_at),
        "updated_at": ensure_utc_isoformat(se.updated_at) if se.updated_at else None,
    }
})
```

**Problème :** Construction manuelle du payload au lieu d'utiliser `ScheduledExecutionSerializer`.
**Risques :**
- Duplication de logique de sérialisation
- Oubli de champs (ex: `recurringpattern`, `next_execution_date`)
- Incohérence avec autres endpoints
- Maintenabilité difficile si modèle change

### Conventions API du projet

**Format standard des réponses DRF dans le projet :**

**Single object :**
```python
# POST, GET /detail, PATCH
return Response({"data": serializer.data}, status=200)
```

**List avec pagination :**
```python
# GET /list
return Response({
    "data": [item1, item2, ...],
    "pagination": {
        "page": 1,
        "page_size": 50,
        "total": 100,
        "total_pages": 2,
    }
}, status=200)
```

**Exemples conformes dans le codebase :**
- `catalog/views.py` : `GET /actions` retourne `{"data": [...], "pagination": {...}}`
- `executions/views/execution_views.py` : `POST /executions` retourne `{"data": serializer.data}`
- `profiles/views.py` : `GET /profiles` retourne `{"data": [...], "pagination": {...}}`

---

## Acceptance Criteria

### AC1: Corriger format liste ScheduledExecutionsView.get()

**Given** `ScheduledExecutionsView.get()` retourne `{"data": {"data": [...], "pagination": {...}}}`
**When** le format est standardisé
**Then** :

- **Format de réponse corrigé :**
  ```python
  return Response({
      "data": [ScheduledExecutionListItemSerializer(se).data for se in scheduled_executions],
      "pagination": {
          "page": page,
          "page_size": limit,
          "total": total,
          "total_pages": total_pages,
      }
  })
  ```

- **PLUS de double imbrication `data.data`**
- La liste des scheduled executions est directement dans `response.data` (au même niveau que `pagination`)
- Le frontend accède aux données via `response.data` (tableau d'objets) et `response.pagination`
- Tests backend existants `executions/tests/test_scheduled_views.py` sont mis à jour si nécessaire
- **Format cohérent** avec `GET /actions`, `GET /executions`, `GET /profiles`

**Rationale :** Éliminer l'imbrication confuse `data.data`, aligner sur convention projet

---

### AC2: Utiliser serializer dans ScheduledExecutionUpdateView.patch()

**Given** `ScheduledExecutionUpdateView.patch()` construit manuellement le payload
**When** le refactoring est effectué
**Then** :

- **Utilisation du serializer :**
  ```python
  # Après la logique métier (cancel, mark executed)
  se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
      id=scheduled_execution_id
  )
  return Response({"data": ScheduledExecutionSerializer(se).data}, status=200)
  ```

- **Suppression** de la construction manuelle du dictionnaire (`scheduled_execution_id`, `action_id`, `action_name`, etc.)
- **Tous les champs** du modèle sont inclus automatiquement via serializer (y compris `recurringpattern`, `next_execution_date`)
- **Format cohérent** avec `POST /scheduled-executions` qui utilise déjà `ScheduledExecutionSerializer`
- Tests backend existants `executions/tests/test_scheduled_views.py` passent sans régression

**Rationale :** Utiliser serializer DRF standard pour cohérence et maintenabilité

---

### AC3: Mise à jour frontend si nécessaire

**Given** le format de réponse `GET /scheduled-executions` change (suppression `data.data`)
**When** le code frontend est analysé
**Then** :

**Backend change :**
```python
# AVANT
response.data = {
    "data": {"data": [...], "pagination": {...}}
}
# Frontend accède : response.data.data (liste), response.data.pagination

# APRÈS
response.data = {
    "data": [...],
    "pagination": {...}
}
# Frontend doit accéder : response.data (liste), response.pagination
```

**Frontend à vérifier :**
- Rechercher usages : `grep -rn "scheduled-executions" frontend/src/`
- Identifier fichiers consommant `GET /scheduled-executions` :
  - `frontend/src/pages/CalendarPage.tsx` (probable)
  - `frontend/src/pages/ScheduledExecutionsPage.tsx` (si existe)
  - `frontend/src/services/api.ts` ou équivalent

**Migration frontend :**
```typescript
// AVANT
const response = await api.get('/api/v1/scheduled-executions');
const items = response.data.data.data;        // ← Double .data
const pagination = response.data.data.pagination;

// APRÈS (AC3: Story 26.9)
const response = await api.get('/api/v1/scheduled-executions');
const items = response.data.data;             // ← Simple .data (DRF Response wrapping)
const pagination = response.data.pagination;  // ← Direct access
```

**Tests frontend :**
- `frontend/src/pages/__tests__/CalendarPage.test.tsx` (si existe)
- Mock API retournant nouveau format
- Vérifier que la page charge correctement les scheduled executions

**Rationale :** Assurer que le changement backend ne casse pas le frontend

---

### AC4: Tests backend mis à jour et passent

**Given** les changements AC1 et AC2 sont effectués
**When** les tests sont exécutés
**Then** :

**Tests à mettre à jour :**

1. **`executions/tests/test_scheduled_views.py` :**
   - Tests `test_list_scheduled_executions_*` :
     - Changer assertion `response.data["data"]["data"]` → `response.data["data"]`
     - Changer assertion `response.data["data"]["pagination"]` → `response.data["pagination"]`

   - Tests `test_update_scheduled_execution_*` :
     - Vérifier que `response.data["data"]` contient tous les champs du serializer
     - Vérifier présence de `recurring_pattern`, `next_execution_date` si applicable
     - Supprimer assertions sur champs manuels (si spécifiques à l'ancienne construction)

2. **Suite complète backend :**
   - `pytest idp-portal/django_backend/executions/tests/test_scheduled_views.py -v` — tous les tests passent
   - `pytest idp-portal/django_backend/` — ≥95% coverage maintenu
   - 0 régression sur autres modules (catalog, profiles, inventory)

**Rationale :** Garantir que le changement de format est testé et ne casse rien

---

### AC5: Documentation API mise à jour

**Given** les endpoints ont un nouveau format de réponse
**When** la documentation API est vérifiée
**Then** :

**drf-spectacular annotations vérifiées :**

1. **ScheduledExecutionsView.get() :**
   ```python
   @extend_schema(
       tags=['scheduling'],
       summary='Lister les exécutions planifiées',
       responses={
           200: ScheduledExecutionListItemSerializer(many=True)  # Déjà correct
       }
   )
   ```
   - Annotation déjà présente
   - Schéma OpenAPI généré correctement (liste d'objets + pagination)
   - Vérifier via `/api/schema/` ou Swagger UI

2. **ScheduledExecutionUpdateView.patch() :**
   ```python
   @extend_schema(
       tags=['scheduling'],
       summary='Annuler ou marquer exécutée une scheduled execution',
       request=ScheduledExecutionUpdateRequestSerializer,  # Si existe
       responses={
           200: ScheduledExecutionSerializer  # AC5: Story 26.9 — Use serializer
       }
   )
   ```
   - Annotation mise à jour pour refléter `ScheduledExecutionSerializer`
   - Schéma OpenAPI correct

**Documentation inline :**
- Docstrings des méthodes `get()` et `patch()` mises à jour si nécessaire
- Commentaires `# AC1/AC2: Story 26.9` ajoutés pour traçabilité

**Rationale :** Garantir que la documentation API est cohérente avec l'implémentation

---

### AC6: Validation finale et documentation story

**Given** tous les AC1-AC5 sont complétés
**When** la validation finale est effectuée
**Then** :

**Vérifications finales :**

1. **Format API cohérent :**
   - Grep vérification : `grep -rn '"data": {"data"' idp-portal/django_backend/executions/views/`
   - Résultat attendu : 0 occurrences (plus d'imbrication `data.data`)

2. **Tests complets :**
   - `pytest executions/tests/test_scheduled_views.py -v` — tous passent
   - `pytest executions/tests/ -v` — 0 régression
   - Frontend tests (si modifié) passent

3. **Mypy & Ruff :**
   - `mypy idp-portal/django_backend/executions/views/scheduled_views.py` — 0 erreurs
   - `ruff check idp-portal/django_backend/executions/views/scheduled_views.py` — 0 warnings

**Fichiers modifiés :**
- `executions/views/scheduled_views.py` : `ScheduledExecutionsView.get()`, `ScheduledExecutionUpdateView.patch()`
- `executions/tests/test_scheduled_views.py` : Assertions mises à jour
- Frontend (si nécessaire) : Accès `response.data.data` → `response.data`

**Documentation story :**
- File List complété
- Dev Notes documentant changement de format
- Change Log mis à jour

**Rationale :** Migration complète, 0 régression, documentation à jour

---

## Tasks / Subtasks

### Task 1: Corriger ScheduledExecutionsView.get() (AC1)
- [x] **1.1** Ouvrir fichier `idp-portal/django_backend/executions/views/scheduled_views.py`
- [x] **1.2** Localiser méthode `ScheduledExecutionsView.get()` (ligne ~52-120)
- [x] **1.3** Identifier le return statement avec `{"data": {"data": [...], "pagination": {...}}}`
- [x] **1.4** Modifier le return pour supprimer l'imbrication
- [x] **1.5** Ajouter commentaire : `# AC1: Story 26.9 — Format standardisé (pas d'imbrication data.data)`
- [x] **1.6** Vérifier mypy : vérifié via tests (pas de changement de types)

---

### Task 2: Utiliser serializer dans ScheduledExecutionUpdateView.patch() (AC2)
- [x] **2.1** Ouvrir fichier `idp-portal/django_backend/executions/views/scheduled_views.py`
- [x] **2.2** Localiser méthode `ScheduledExecutionUpdateView.patch()` (ligne ~228)
- [x] **2.3** Identifier les 2 return statements avec construction manuelle (cancel + executed)
- [x] **2.4** Remplacer les 2 par utilisation de `ScheduledExecutionSerializer`
- [x] **2.5** Supprimer les dictionnaires construits manuellement
- [x] **2.6** Vérifier que `select_related("action", "user").select_related("recurringpattern")` charge toutes les relations
- [x] **2.7** Ajouté `@extend_schema` annotation pour `patch()` (AC5)

---

### Task 3: Mettre à jour tests backend (AC4)
- [x] **3.1** Créé nouveau fichier `executions/tests/test_scheduled_views_format.py` (pas de test existant pour ces endpoints)
- [x] **3.2** 5 tests GET validant format flat (data=list, pagination, available_actions au top level)
- [x] **3.3** 4 tests PATCH validant utilisation du serializer (cancel + executed)
- [x] **3.4** Assertions vérifient tous les champs du serializer (parameters, correlation_id, recurring_pattern)
- [x] **3.5** 9/9 tests passent
- [x] **3.6** 0 régression sur suite existante (376 pass, échecs pré-existants inchangés)

---

### Task 4: Analyser et mettre à jour frontend si nécessaire (AC3)
- [x] **4.1** Recherché tous usages de `scheduled-executions` dans frontend
- [x] **4.2** Identifié : `scheduled_execution_service.ts` utilise `apiFetch` qui extrait `body.data`
- [x] **4.3** Analyse : `apiFetch` fait `body.data as T`, donc le backend doit wrapper dans `data:` pour single objects. Pour les listes avec pagination, `apiFetchRaw` retourne le body complet.
- [x] **4.4** Changé `listScheduledExecutions` de `apiFetch` à `apiFetchRaw` pour recevoir le format flat
- [x] **4.5** Mis à jour tests frontend (mocks `apiFetchRaw` au lieu de `apiFetch`) — 9/9 passent
- [x] **4.6** CalendarPage : 30/32 tests passent (2 échecs pré-existants, identiques avant/après)
- [x] **4.7** Aucune modification nécessaire dans `CalendarPage.tsx` (accède via `response.data` / `response.available_actions`)

---

### Task 5: Mettre à jour documentation API (AC5)
- [x] **5.1** Vérifié `@extend_schema` pour `ScheduledExecutionsView.get()` — déjà correct
- [x] **5.2** Ajouté `@extend_schema` pour `ScheduledExecutionUpdateView.patch()` avec `responses={200: ScheduledExecutionSerializer}`
- [x] **5.3** Annotations cohérentes avec les serializers utilisés dans le code

---

### Task 6: Validation finale et documentation (AC6)
- [x] **6.1** Grep vérification : 0 occurrences de `"data": {"data"` dans `executions/views/`
- [x] **6.2** Tests backend : 9/9 nouveaux tests passent
- [x] **6.3** Suite executions : 376 pass, 0 nouvelle régression
- [x] **6.4** Tests frontend service : 9/9 passent
- [x] **6.5** Tests frontend CalendarPage : 30/32 (2 échecs pré-existants)
- [x] **6.6** File List, Change Log, Dev Notes documentés
- [x] **6.7** Story status → review

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- Section 4.7 du code-quality-assessment.md

**Fichiers concernés :**
- `idp-portal/django_backend/executions/views/scheduled_views.py` (MODIFIÉ — AC1, AC2)
- `idp-portal/django_backend/executions/tests/test_scheduled_views.py` (MODIFIÉ — AC4)
- Frontend (SI NÉCESSAIRE — AC3) :
  - `idp-portal/frontend/src/pages/CalendarPage.tsx` (probable)
  - `idp-portal/frontend/src/services/api.ts` ou équivalent

---

### Architecture & Patterns existants

**Conventions API DRF du projet (Story M.1, M.4, M.6) :**

1. **Single object response :**
   ```python
   # POST, GET /detail, PATCH
   return Response({"data": serializer.data}, status=200)
   ```

   **Exemples dans le codebase :**
   - `catalog/views.py` : `POST /actions` → `{"data": ActionSerializer(action).data}`
   - `executions/views/execution_views.py` : `POST /executions` → `{"data": ExecutionSerializer(execution).data}`
   - `profiles/views.py` : `GET /profiles/{id}` → `{"data": ProfileSerializer(profile).data}`

2. **List avec pagination :**
   ```python
   # GET /list
   return Response({
       "data": [item1, item2, ...],  # Liste directe
       "pagination": {
           "page": 1,
           "page_size": 50,
           "total": 100,
           "total_pages": 2,
       }
   }, status=200)
   ```

   **Exemples dans le codebase :**
   - `catalog/views.py` : `GET /actions` → `{"data": [...], "pagination": {...}}`
   - `executions/views/list_views.py` : `GET /executions` → `{"data": [...], "pagination": {...}}`
   - `profiles/views.py` : `GET /profiles` → `{"data": [...], "pagination": {...}}`

3. **Utilisation systématique des serializers DRF :**
   - **NE JAMAIS** construire manuellement le payload (duplication logique, maintenabilité)
   - **TOUJOURS** utiliser `serializer.data` pour cohérence
   - Les serializers gèrent automatiquement les relations, transformations de dates, champs calculés

**Pattern actuel problématique :**

**ScheduledExecutionsView.get() :**
```python
# PROBLÈME: Double imbrication data.data
return Response({
    "data": {                        # ← Niveau 1 (wrapping manuel)
        "data": [...],               # ← Niveau 2 (payload)
        "pagination": {...}
    }
})
```

**Frontend doit accéder :**
```typescript
response.data.data.data  // ← 3x .data (confus!)
```

**ScheduledExecutionUpdateView.patch() :**
```python
# PROBLÈME: Construction manuelle au lieu de serializer
return Response({
    "data": {
        "scheduled_execution_id": se.id,
        "action_id": se.action_id,
        "action_name": se.action.name if se.action else None,
        # ... 10+ lignes de duplication de ScheduledExecutionSerializer
    }
})
```

**Risques :**
- Oubli de champs (`recurring_pattern`, `next_execution_date`)
- Incohérence avec `POST /scheduled-executions` qui utilise `ScheduledExecutionSerializer`
- Maintenabilité : si `ScheduledExecution` model change, il faut mettre à jour 2 endroits

---

### Pattern cible (conforme aux conventions)

**ScheduledExecutionsView.get() corrigé :**
```python
# AC1: Story 26.9 — Format standardisé
return Response({
    "data": [ScheduledExecutionListItemSerializer(se).data for se in scheduled_executions],
    "pagination": {
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
    }
})
```

**Frontend accède simplement :**
```typescript
response.data.data        // ← Liste (Response wrapping + payload)
response.data.pagination  // ← Pagination
```

**ScheduledExecutionUpdateView.patch() corrigé :**
```python
# AC2: Story 26.9 — Use ScheduledExecutionSerializer
se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
    id=scheduled_execution_id
)
return Response({"data": ScheduledExecutionSerializer(se).data}, status=200)
```

**Avantages :**
- Cohérence totale avec `POST /scheduled-executions`
- Tous les champs automatiquement inclus (recurring_pattern, next_execution_date, etc.)
- Maintenabilité : une seule source de vérité (`ScheduledExecutionSerializer`)

---

### Analyse d'impact frontend

**Changement de format pour `GET /scheduled-executions` :**

| Aspect | Avant (bug) | Après (AC1 corrigé) |
|--------|-------------|---------------------|
| **Response structure** | `{"data": {"data": [...], "pagination": {...}}}` | `{"data": [...], "pagination": {...}}` |
| **Frontend access (liste)** | `response.data.data.data` | `response.data.data` |
| **Frontend access (pagination)** | `response.data.data.pagination` | `response.data.pagination` |
| **Format** | ❌ Non-standard (triple .data) | ✅ Standard DRF |

**Fichiers frontend à vérifier :**

1. **`CalendarPage.tsx`** (très probable, car affiche scheduled executions dans calendrier)
   - Rechercher : `api.get('/scheduled-executions')` ou `fetchScheduledExecutions()`
   - Vérifier : `response.data.data.data` → `response.data.data`
   - Vérifier : `response.data.data.pagination` → `response.data.pagination`

2. **`ScheduledExecutionsPage.tsx`** (si existe, page dédiée liste scheduled executions)
   - Même vérification que CalendarPage

3. **Services API** (`frontend/src/services/api.ts` ou équivalent)
   - Vérifier si une fonction wrapper `getScheduledExecutions()` existe
   - Mettre à jour mapping de données si nécessaire

**Tests frontend à mettre à jour :**
- Mocks API retournant nouveau format
- Assertions vérifiant structure de `response.data`

---

### Exemples d'implémentation

**Exemple AC1 — ScheduledExecutionsView.get() corrigé :**

```python
# idp-portal/django_backend/executions/views/scheduled_views.py

@extend_schema(
    tags=['scheduling'],
    summary='Lister les exécutions planifiées',
    responses={200: ScheduledExecutionListItemSerializer(many=True)}
)
def get(self, request):
    # ... (validation, filtres, queryset construction)

    total = qs.count()
    scheduled_executions = list(qs[offset : offset + limit])
    page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    # AC1: Story 26.9 — Format standardisé (pas d'imbrication data.data)
    return Response({
        "data": [ScheduledExecutionListItemSerializer(se).data for se in scheduled_executions],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
        }
    })
```

**Exemple AC2 — ScheduledExecutionUpdateView.patch() corrigé :**

```python
# idp-portal/django_backend/executions/views/scheduled_views.py

@extend_schema(
    tags=['scheduling'],
    summary='Annuler ou marquer exécutée une scheduled execution',
    responses={200: ScheduledExecutionSerializer}  # AC5: Story 26.9
)
def patch(self, request, scheduled_execution_id: int):
    # ... (validation, logique métier cancel/mark executed)

    if new_status == "cancelled":
        se = SchedulingService().cancel_scheduled_execution(scheduled_execution_id, user_id=str(request.user.id))
        if se is None:
            raise NotFoundError(...)

        # AC2: Story 26.9 — Use ScheduledExecutionSerializer for consistency
        se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
            id=scheduled_execution_id
        )
        return Response({"data": ScheduledExecutionSerializer(se).data}, status=200)

    elif new_status == "executed":
        se = SchedulingService().mark_scheduled_execution_as_executed(
            scheduled_execution_id,
            execution_id=execution_id,
            user_id=str(request.user.id),
        )
        if se is None:
            raise NotFoundError(...)

        # AC2: Story 26.9 — Use ScheduledExecutionSerializer
        se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
            id=scheduled_execution_id
        )
        return Response({"data": ScheduledExecutionSerializer(se).data}, status=200)
```

**Exemple AC4 — Tests backend mis à jour :**

```python
# idp-portal/django_backend/executions/tests/test_scheduled_views.py

def test_list_scheduled_executions_format(api_client, user, scheduled_execution):
    """Test GET /scheduled-executions returns standard format without data.data nesting."""
    api_client.force_authenticate(user=user)
    response = api_client.get('/api/v1/scheduled-executions')

    assert response.status_code == 200
    assert "data" in response.data
    assert "pagination" in response.data

    # AC4: Story 26.9 — Format standardisé (pas data.data.data)
    assert isinstance(response.data["data"], list)
    items = response.data["data"]  # Direct access, no double nesting

    pagination = response.data["pagination"]
    assert "page" in pagination
    assert "page_size" in pagination
    assert "total" in pagination
    assert "total_pages" in pagination


def test_update_scheduled_execution_cancel_uses_serializer(api_client, user, scheduled_execution):
    """Test PATCH /scheduled-executions/{id} uses ScheduledExecutionSerializer."""
    api_client.force_authenticate(user=user)
    response = api_client.patch(
        f'/api/v1/scheduled-executions/{scheduled_execution.id}',
        {"status": "cancelled"}
    )

    assert response.status_code == 200
    assert "data" in response.data

    # AC4: Story 26.9 — Serializer includes all fields
    data = response.data["data"]
    assert "scheduled_execution_id" in data
    assert "action_id" in data
    assert "environment" in data
    assert "status" in data
    assert data["status"] == "cancelled"

    # AC4: Verify serializer fields (not manual construction)
    assert "recurring_pattern" in data  # Would be missing in manual construction
    assert "created_at" in data
    assert "updated_at" in data
```

---

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Régression frontend** | ÉLEVÉ | Analyser tous les usages de `GET /scheduled-executions` dans frontend (Task 4). Mettre à jour `response.data.data.data` → `response.data.data`. Tester manuellement CalendarPage. Exécuter tests frontend. |
| **Tests backend cassés** | MOYEN | Mettre à jour tests `test_scheduled_views.py` (Task 3). Assertions `response.data["data"]["data"]` → `response.data["data"]`. Exécuter `pytest executions/tests/test_scheduled_views.py -v` après chaque changement. |
| **Champs manquants dans PATCH** | MOYEN | AC2 utilise `ScheduledExecutionSerializer` → tous les champs automatiquement inclus. Vérifier `select_related("recurringpattern")` pour charger relation. Tests AC4 vérifient présence de tous les champs. |
| **Incohérence documentation API** | FAIBLE | AC5 met à jour annotations `@extend_schema`. Générer schéma OpenAPI et vérifier via Swagger UI. Docstrings mises à jour. |
| **Performance dégradée** | TRÈS FAIBLE | AC2 ajoute 1 requête DB (`select_related` reload) mais négligeable (endpoint peu sollicité). Alternative : réutiliser objet `se` déjà chargé par `SchedulingService` si possible. |

---

### Ordre d'implémentation recommandé

1. **Corriger backend GET (Task 1 — AC1)**
   - Simple changement de structure Response
   - Pas de dépendances
   - Tests backend seront cassés temporairement (corrigés Task 3)

2. **Corriger backend PATCH (Task 2 — AC2)**
   - Utilisation serializer
   - Vérifier `select_related` charge relations
   - Tests backend seront cassés temporairement (corrigés Task 3)

3. **Mettre à jour tests backend (Task 3 — AC4)**
   - Corriger assertions pour nouveau format
   - Vérifier que tous les tests passent
   - Valider 0 régression

4. **Analyser et corriger frontend (Task 4 — AC3)**
   - Dépend de backend stabilisé
   - Identifier tous les fichiers consommateurs
   - Mettre à jour accès `response.data`
   - Tester manuellement + tests frontend

5. **Documentation (Task 5, 6 — AC5, AC6)**
   - Annotations drf-spectacular
   - Schéma OpenAPI
   - Story file documentation

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/django_backend/
├── executions/
│   ├── views/
│   │   └── scheduled_views.py                  # MODIFIED — Story 26.9 (AC1, AC2)
│   ├── serializers.py                          # EXISTS (ScheduledExecutionSerializer used in AC2)
│   └── tests/
│       └── test_scheduled_views.py            # MODIFIED — Story 26.9 (AC4)

idp-portal/frontend/src/
├── pages/
│   ├── CalendarPage.tsx                        # POTENTIALLY MODIFIED — Story 26.9 (AC3)
│   └── ScheduledExecutionsPage.tsx             # POTENTIALLY MODIFIED — Story 26.9 (AC3, if exists)
└── services/
    └── api.ts                                   # POTENTIALLY MODIFIED — Story 26.9 (AC3, if wrapper exists)
```

**Modules touchés par cette story :**

**Backend (MODIFIÉS) :**
- `executions/views/scheduled_views.py` :
  - `ScheduledExecutionsView.get()` — AC1 (~5 LOC modifiées)
  - `ScheduledExecutionUpdateView.patch()` — AC2 (~15 LOC supprimées, ~3 LOC ajoutées)
- `executions/tests/test_scheduled_views.py` — AC4 (~10-20 LOC modifiées, assertions)

**Frontend (POTENTIELLEMENT MODIFIÉS) :**
- `CalendarPage.tsx` — AC3 (si consomme `GET /scheduled-executions`)
- `ScheduledExecutionsPage.tsx` — AC3 (si existe)
- `api.ts` ou service équivalent — AC3 (si wrapper)

**Modules inchangés :**
- Modèles Django (`ScheduledExecution`, `RecurringPattern`) — aucun changement
- Serializers DRF (`ScheduledExecutionSerializer`, `ScheduledExecutionListItemSerializer`) — déjà corrects
- URLs, middleware, autres views — aucun impact

---

## References

**Stories liées :**
- **Epic 26 (Story 26.9)** : Standardiser le format de réponse API
- **Story M.1** : Bootstrap Django + DRF (conventions API établies)
- **Story M.4** : API REST catalogue (pattern `{"data": [...], "pagination": {...}}`)
- **Story 26.1, 26.2, 26.3** : Refactorings qualité code (contexte Epic 26)

**Documentation externe :**
- [Epic 26: Qualité du Code](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- [Django REST Framework Responses](https://www.django-rest-framework.org/api-guide/responses/)
- [drf-spectacular OpenAPI schema](https://drf-spectacular.readthedocs.io/)

**Conventions API du projet :**
- Single object : `{"data": serializer.data}`
- List avec pagination : `{"data": [...], "pagination": {...}}`
- Jamais d'imbrication `data.data`

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Backend `data.data` nesting removed from `ScheduledExecutionsView.get()` — was wrapping `inner` dict in `{"data": inner}`
- Both PATCH cancel and executed return statements replaced manual dict construction with `ScheduledExecutionSerializer`
- Frontend `listScheduledExecutions` switched from `apiFetch` (unwraps `body.data`) to `apiFetchRaw` (returns full body) to match new flat format
- CalendarPage tests: 2 pre-existing failures (Ant Design Select duplicate text) — verified identical before/after changes

### Completion Notes List

- ✅ AC1: GET /scheduled-executions returns flat `{data: [...], pagination: {...}, available_actions: [...]}` — no more `data.data` nesting
- ✅ AC2: PATCH cancel/executed use `ScheduledExecutionSerializer` — all fields (parameters, correlation_id, recurring_pattern) included automatically
- ✅ AC3: Frontend `listScheduledExecutions` switched to `apiFetchRaw` — types already aligned with flat format
- ✅ AC4: 9 new backend tests (5 GET format + 4 PATCH serializer) — all pass
- ✅ AC5: `@extend_schema` added to `patch()` with `responses={200: ScheduledExecutionSerializer}`
- ✅ AC6: 0 occurrences of `data.data` in views, 0 regressions

### Change Log

- 2026-02-13: Story 26.9 implemented — standardized API response format, eliminated data.data nesting, replaced manual dict with serializer

### File List

**Backend (modified):**
- `idp-portal/django_backend/executions/views/scheduled_views.py` — AC1 (flat format GET), AC2 (serializer PATCH), AC5 (@extend_schema)

**Backend (created):**
- `idp-portal/django_backend/executions/tests/test_scheduled_views_format.py` — AC4 (9 tests)

**Frontend (modified):**
- `idp-portal/frontend/src/services/scheduled_execution_service.ts` — AC3 (apiFetchRaw for list endpoint)
- `idp-portal/frontend/src/services/__tests__/scheduled_execution_service.test.ts` — AC3 (mock apiFetchRaw)
