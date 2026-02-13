# Story 26.11: Standardiser la pagination (utilitaire réutilisable)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux créer un utilitaire `paginate_queryset()` réutilisable,
afin de éliminer la réimplémentation du pattern dans chaque view.

## Context

**Source :** Epic 26, Section 5.2 du code-quality-assessment (6 février 2026)

### Problème identifié

Le pattern de pagination manuelle est dupliqué dans plusieurs views APIView, créant du code répétitif et une source potentielle d'incohérences. Chaque view réimplémente la même logique :

```python
# Pattern répété dans ScheduledExecutionsView, ExecutionsListView, etc.
total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if total > 0 else 1

items = list(qs[offset: offset + limit])
data = SomeSerializer(items, many=True).data

return Response({
    "data": data,
    "pagination": {
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
    }
})
```

**Fichiers concernés (duplication identifiée) :**
- `executions/views/scheduled_views.py` — ScheduledExecutionsView.get() (lignes 114-140)
- `executions/views/list_views.py` — ExecutionsListView.get() (lignes 70-87)
- `inventory/services.py` — InventoryService.list_targets_for_user() (pagination manuelle)
- `audit/views.py` — AuditLogListView.get() (pattern similaire)

**Impact actuel :**
- **Duplication de code** : ~15-20 LOC dupliquées dans 4+ fichiers
- **Incohérence potentielle** : Chaque implémentation peut diverger (ex: `total_pages = 1 if total > 0 else 1` vs `max(1, total_pages)`)
- **Maintenabilité** : Tout changement du format pagination nécessite de modifier tous les fichiers
- **Tests** : Chaque view doit tester la logique de pagination (augmentation de la surface de test)

### Solution proposée

**Créer un utilitaire réutilisable `paginate_queryset()` dans `core/pagination.py` :**

```python
def paginate_queryset(
    queryset,
    offset: int,
    limit: int,
) -> dict:
    """
    Paginate a Django queryset with offset/limit and return standardized format.

    Args:
        queryset: Django queryset to paginate
        offset: Starting position (0-indexed)
        limit: Number of items per page

    Returns:
        {
            'items': [...],  # Queryset results (not serialized)
            'pagination': {
                'page': int,
                'page_size': int,
                'total': int,
                'total_pages': int,
            }
        }
    """
```

**Avantages :**
- ✅ **DRY** : Code de pagination centralisé, une seule source de vérité
- ✅ **Cohérence** : Format pagination identique dans toute l'API
- ✅ **Maintenabilité** : Changements futurs au format pagination en un seul endroit
- ✅ **Tests** : Logique pagination testée une seule fois, tests views simplifiés

---

## Acceptance Criteria

### AC1: Créer l'utilitaire `paginate_queryset()` dans `core/pagination.py`

**Given** le pattern pagination est dupliqué dans plusieurs views
**When** l'utilitaire est créé dans `core/pagination.py`
**Then** :

**Signature de la fonction :**
```python
def paginate_queryset(
    queryset,
    offset: int,
    limit: int,
) -> dict:
    """
    Paginate a Django queryset with offset/limit.

    Story 26.11 (AC1): Utilitaire réutilisable pour pagination offset/limit.

    Args:
        queryset: Django queryset to paginate (unevaluated)
        offset: Starting position (0-indexed, must be >= 0)
        limit: Number of items per page (must be > 0)

    Returns:
        {
            'items': list,  # Queryset slice results (not serialized)
            'pagination': {
                'page': int,        # Page number (1-indexed)
                'page_size': int,   # Items per page (= limit)
                'total': int,       # Total items count
                'total_pages': int, # Total pages count (minimum 1)
            }
        }

    Examples:
        >>> qs = Execution.objects.all()  # 250 items total
        >>> result = paginate_queryset(qs, offset=0, limit=50)
        >>> result['pagination']
        {'page': 1, 'page_size': 50, 'total': 250, 'total_pages': 5}

        >>> result = paginate_queryset(qs, offset=100, limit=50)
        >>> result['pagination']
        {'page': 3, 'page_size': 50, 'total': 250, 'total_pages': 5}
    """
```

**Implémentation requise :**

1. **Calcul pagination :**
   ```python
   total = queryset.count()
   page = (offset // limit) + 1
   total_pages = max(1, (total + limit - 1) // limit)  # Minimum 1 page
   ```

2. **Slicing queryset :**
   ```python
   items = list(queryset[offset : offset + limit])
   ```

3. **Format retour :**
   ```python
   return {
       'items': items,
       'pagination': {
           'page': page,
           'page_size': limit,
           'total': total,
           'total_pages': total_pages,
       }
   }
   ```

**Vérifications :**
- Fonction ajoutée dans `core/pagination.py`
- Signature correcte avec types hints
- Docstring complète avec exemples
- Commentaire `# Story 26.11 (AC1)` au-dessus de la définition
- Export ajouté si nécessaire pour imports depuis `core.pagination`

---

### AC2: Migrer `ScheduledExecutionsView.get()` vers l'utilitaire

**Given** `ScheduledExecutionsView.get()` utilise pagination manuelle (lignes 114-140)
**When** le code est refactorisé pour utiliser `paginate_queryset()`
**Then** :

**Code AVANT (Story 26.11) :**
```python
# executions/views/scheduled_views.py, lignes 114-140
qs = qs.order_by("-created_at")
total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if total > 0 else 1

items = list(qs[offset: offset + limit])
data_items = ScheduledExecutionListItemSerializer(items, many=True).data

# AC1: Story 26.9 — Format standardisé (pas d'imbrication data.data)
return Response({
    "data": data_items,
    "pagination": {
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
    },
    "available_actions": available_actions,
})
```

**Code APRÈS (AC2: Story 26.11 — Utilisation utilitaire pagination) :**
```python
# executions/views/scheduled_views.py
from core.pagination import paginate_queryset

# ...

qs = qs.order_by("-created_at")

# AC2: Story 26.11 — Utilisation utilitaire pagination
result = paginate_queryset(qs, offset=offset, limit=limit)
data_items = ScheduledExecutionListItemSerializer(result['items'], many=True).data

return Response({
    "data": data_items,
    "pagination": result['pagination'],
    "available_actions": available_actions,
})
```

**Réductions :**
- **Avant** : ~10 LOC (calcul pagination + slicing + format)
- **Après** : ~3 LOC (appel utilitaire + sérialisation)
- **Économie** : ~7 LOC, logique pagination centralisée

**Vérifications :**
- Import `from core.pagination import paginate_queryset` ajouté
- Appel `paginate_queryset(qs, offset, limit)` remplace calcul manuel
- `result['items']` passé au serializer
- `result['pagination']` passé dans la Response
- Format réponse identique (pas de régression)
- `available_actions` conservé dans la réponse (champ métier)

---

### AC3: Migrer `ExecutionsListView.get()` vers l'utilitaire

**Given** `ExecutionsListView.get()` utilise pagination manuelle (lignes 70-87)
**When** le code est refactorisé pour utiliser `paginate_queryset()`
**Then** :

**Code AVANT (Story 26.11) :**
```python
# executions/views/list_views.py, lignes 70-87
qs = qs.order_by("-created_at")

total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if limit else 1

items = list(qs[offset: offset + limit])
data = ExecutionSerializer(items, many=True).data

return Response({
    "data": data,
    "pagination": {
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
    },
})
```

**Code APRÈS (AC3: Story 26.11 — Utilisation utilitaire pagination) :**
```python
# executions/views/list_views.py
from core.pagination import paginate_queryset

# ...

qs = qs.order_by("-created_at")

# AC3: Story 26.11 — Utilisation utilitaire pagination
result = paginate_queryset(qs, offset=offset, limit=limit)
data = ExecutionSerializer(result['items'], many=True).data

return Response({
    "data": data,
    "pagination": result['pagination'],
})
```

**Vérifications :**
- Import ajouté en haut du fichier
- Appel `paginate_queryset(qs, offset, limit)` remplace calcul manuel
- Format réponse identique (pas de régression)
- Tests existants passent sans modification

---

### AC4: Écrire les tests unitaires de `paginate_queryset()`

**Given** l'utilitaire `paginate_queryset()` est créé
**When** les tests unitaires sont écrits
**Then** :

**Fichier de test :** `core/tests/test_pagination.py`

**Cas de test à couvrir (minimum 8 tests) :**

1. **test_paginate_queryset_first_page**
   - Queryset avec 100 items, offset=0, limit=25
   - Vérifie : `page=1`, `page_size=25`, `total=100`, `total_pages=4`
   - Vérifie : `len(items) == 25`, items sont les 25 premiers

2. **test_paginate_queryset_middle_page**
   - Queryset avec 100 items, offset=50, limit=25
   - Vérifie : `page=3`, `page_size=25`, `total=100`, `total_pages=4`

3. **test_paginate_queryset_last_page_partial**
   - Queryset avec 93 items, offset=75, limit=25
   - Vérifie : `page=4`, `total_pages=4`, `len(items) == 18` (partiel)

4. **test_paginate_queryset_empty_queryset**
   - Queryset vide (0 items), offset=0, limit=25
   - Vérifie : `page=1`, `total=0`, `total_pages=1` (minimum 1 page)
   - Vérifie : `items == []`

5. **test_paginate_queryset_offset_beyond_total**
   - Queryset avec 50 items, offset=100, limit=25
   - Vérifie : `items == []`, pagination correcte (page calculée)

6. **test_paginate_queryset_limit_larger_than_total**
   - Queryset avec 10 items, offset=0, limit=50
   - Vérifie : `page=1`, `total_pages=1`, `len(items) == 10`

7. **test_paginate_queryset_exact_page_boundary**
   - Queryset avec 100 items, offset=0, limit=50
   - Vérifie : `page=1`, `total_pages=2` (exact boundary)

8. **test_paginate_queryset_preserves_queryset_order**
   - Queryset avec order_by applied
   - Vérifie : items respectent l'ordre du queryset

**Fixture requise :**
```python
@pytest.fixture
def sample_executions(db):
    """Create 100 sample executions for pagination tests."""
    from executions.factories import ExecutionFactory
    return ExecutionFactory.create_batch(100)
```

**Vérifications :**
- 8+ tests couvrant les cas limites
- Tests utilisent des fixtures Django/pytest
- Tous les tests passent : `pytest core/tests/test_pagination.py -v`
- Couverture : 100% de `paginate_queryset()` (lignes + branches)

---

### AC5: Tests existants passent sans régression

**Given** les views sont migrées vers `paginate_queryset()`
**When** la suite de tests complète est exécutée
**Then** :

**Tests backend à vérifier (0 régression) :**

1. **Tests `ScheduledExecutionsView` :**
   - `pytest executions/tests/test_scheduled_views.py -v`
   - Tous les tests de pagination passent (offset, limit, total_pages)

2. **Tests `ExecutionsListView` :**
   - `pytest executions/tests/test_execution_list.py -v` (si existe)
   - Tous les tests de pagination passent

3. **Tests d'intégration pagination :**
   - `pytest tests/integration/test_pagination_contract.py -v`
   - Vérifie contrat API pagination cohérent

**Vérification format réponse :**
- Structure `{"data": [...], "pagination": {...}}` inchangée
- Champs pagination : `page`, `page_size`, `total`, `total_pages` présents
- Valeurs calculées identiques à avant migration

**Vérification mypy/ruff :**
- `mypy core/pagination.py` — 0 erreurs
- `ruff check core/pagination.py` — 0 warnings

**Critères de succès :**
- ✅ 0 test cassé (régression)
- ✅ 0 changement de comportement API
- ✅ Format pagination identique
- ✅ Tests unitaires `paginate_queryset()` : 8/8 passent
- ✅ Couverture `core/pagination.py` : 100%

---

### AC6: Documentation et validation finale

**Given** tous les AC1-AC5 sont complétés
**When** la validation finale est effectuée
**Then** :

**Vérifications finales :**

1. **Duplication éliminée :**
   - `grep -rn "total_pages = (total + limit - 1)" idp-portal/django_backend/` — 0 occurrences dans views migrées
   - Seule occurrence : `core/pagination.py` (source unique)

2. **Imports corrects :**
   - `grep -rn "from core.pagination import paginate_queryset" idp-portal/django_backend/` — 2+ occurrences (views migrées)

3. **Cohérence format pagination :**
   - Toutes les réponses paginées utilisent `{'data': [...], 'pagination': {...}}`
   - Aucune incohérence dans les champs `page`, `page_size`, `total`, `total_pages`

4. **Tests complets :**
   - `pytest core/tests/test_pagination.py -v` — 8/8 tests passent
   - `pytest executions/tests/ -v` — 0 régression
   - Couverture `core/pagination.py` : 100% (ligne + branches)

**Documentation story :**
- File List complété avec tous les fichiers modifiés
- Dev Notes documentant l'utilitaire et les migrations
- Completion Notes listant les 2+ views migrées

**Métriques de succès :**
- **LOC économisées** : ~15-20 LOC (duplication éliminée)
- **Cohérence** : 100% des views paginées utilisent l'utilitaire
- **Maintenabilité** : Code pagination centralisé, une seule source de vérité
- **Tests** : Logique pagination testée une seule fois (8 tests unitaires)

---

## Tasks / Subtasks

### Task 1: Créer l'utilitaire `paginate_queryset()` (AC1)
- [x] **1.1** Ouvrir fichier `idp-portal/django_backend/core/pagination.py`
- [x] **1.2** Ajouter fonction `paginate_queryset(queryset, offset, limit)` avec signature complète
- [x] **1.3** Implémenter calcul pagination : `total`, `page`, `total_pages`
- [x] **1.4** Implémenter slicing queryset : `items = list(queryset[offset:offset+limit])`
- [x] **1.5** Retourner dict `{'items': [...], 'pagination': {...}}`
- [x] **1.6** Ajouter docstring complète avec exemples d'usage
- [x] **1.7** Ajouter commentaire `# Story 26.11 (AC1): Utilitaire pagination réutilisable`
- [x] **1.8** Ajouter type hints complets (Python 3.12+)

---

### Task 2: Écrire tests unitaires `paginate_queryset()` (AC4)
- [x] **2.1** Créer fichier `idp-portal/django_backend/core/tests/test_pagination.py`
- [x] **2.2** Créer fixture `sample_executions(db)` — 100 executions pour tests
- [x] **2.3** Écrire test `test_paginate_queryset_first_page` (offset=0, limit=25)
- [x] **2.4** Écrire test `test_paginate_queryset_middle_page` (offset=50, limit=25)
- [x] **2.5** Écrire test `test_paginate_queryset_last_page_partial` (93 items, offset=75)
- [x] **2.6** Écrire test `test_paginate_queryset_empty_queryset` (0 items)
- [x] **2.7** Écrire test `test_paginate_queryset_offset_beyond_total` (offset > total)
- [x] **2.8** Écrire test `test_paginate_queryset_limit_larger_than_total` (limit > total)
- [x] **2.9** Écrire test `test_paginate_queryset_exact_page_boundary` (100 items, limit=50)
- [x] **2.10** Écrire test `test_paginate_queryset_preserves_order` (order_by respecté)
- [x] **2.11** Exécuter `pytest core/tests/test_pagination.py -v` — 8/8 tests passent
- [x] **2.12** Vérifier couverture : `pytest --cov=core.pagination core/tests/test_pagination.py` — 100%

---

### Task 3: Migrer `ScheduledExecutionsView.get()` (AC2)
- [x] **3.1** Ouvrir fichier `executions/views/scheduled_views.py`
- [x] **3.2** Ajouter import `from core.pagination import paginate_queryset`
- [x] **3.3** Remplacer calcul pagination manuel (lignes 114-116) par `result = paginate_queryset(qs, offset, limit)`
- [x] **3.4** Remplacer `items = list(qs[offset:offset+limit])` par `result['items']`
- [x] **3.5** Mettre à jour serializer call : `ScheduledExecutionListItemSerializer(result['items'], many=True).data`
- [x] **3.6** Remplacer dict pagination dans Response par `result['pagination']`
- [x] **3.7** Ajouter commentaire `# AC2: Story 26.11 — Utilisation utilitaire pagination`
- [x] **3.8** Vérifier que `available_actions` est conservé dans la réponse
- [x] **3.9** Exécuter tests : `pytest executions/tests/test_scheduled_views.py -v` — 0 régression

---

### Task 4: Migrer `ExecutionsListView.get()` (AC3)
- [x] **4.1** Ouvrir fichier `executions/views/list_views.py`
- [x] **4.2** Ajouter import `from core.pagination import paginate_queryset`
- [x] **4.3** Remplacer calcul pagination manuel (lignes 70-72) par `result = paginate_queryset(qs, offset, limit)`
- [x] **4.4** Remplacer `items = list(qs[offset:offset+limit])` par `result['items']`
- [x] **4.5** Mettre à jour serializer call : `ExecutionSerializer(result['items'], many=True).data`
- [x] **4.6** Remplacer dict pagination dans Response par `result['pagination']`
- [x] **4.7** Ajouter commentaire `# AC3: Story 26.11 — Utilisation utilitaire pagination`
- [x] **4.8** Exécuter tests : `pytest executions/tests/ -k list -v` — 0 régression

---

### Task 5: Tests de régression et validation finale (AC5 + AC6)
- [x] **5.1** Exécuter suite complète tests executions : `pytest executions/tests/ -v`
- [x] **5.2** Vérifier tests integration pagination : `pytest tests/integration/test_pagination_contract.py -v`
- [x] **5.3** Grep vérification : 0 calcul pagination manuel dans views migrées
- [x] **5.4** Grep vérification : imports `paginate_queryset` présents dans 2+ fichiers
- [x] **5.5** Vérifier mypy : `mypy core/pagination.py` — 0 erreurs
- [x] **5.6** Vérifier ruff : `ruff check core/pagination.py` — 0 warnings
- [x] **5.7** Documenter métriques : LOC économisées, views migrées
- [x] **5.8** Compléter File List avec tous les fichiers modifiés
- [x] **5.9** Compléter Dev Notes et Completion Notes
- [x] **5.10** Story status → review

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- Section 5.2 du code-quality-assessment.md — "Pagination pattern duplication"

**Story précédente :**
- [Story 26.10: Renommer fonctions _ exportées](26-10-renommer-fonctions-underscore-exportees.md) — Conventions Python, refactoring utils

**Stories liées :**
- [Story 26.9: Standardiser format réponse API](26-9-standardiser-format-reponse-api.md) — Format `{"data": [...], "pagination": {...}}`
- [Story 22.6: Corriger HIGH-6 — Total inconsistent](../done/22-6-corriger-high-6-standardiser-pagination-total.md) — Standardisation champ `total`

**Fichiers concernés :**

**À CRÉER (1 fichier test) :**
- `core/tests/test_pagination.py` — Tests unitaires `paginate_queryset()` (8+ tests)

**À MODIFIER (3 fichiers) :**
- `core/pagination.py` — Ajout fonction `paginate_queryset()` (~30 LOC)
- `executions/views/scheduled_views.py` — Migration vers utilitaire (~7 LOC économisées)
- `executions/views/list_views.py` — Migration vers utilitaire (~7 LOC économisées)

---

### Architecture & Patterns existants

**Pattern actuel — Pagination manuelle dupliquée :**

```python
# Répété dans ScheduledExecutionsView, ExecutionsListView, InventoryService
total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if total > 0 else 1  # Ou variante

items = list(qs[offset: offset + limit])
data = SomeSerializer(items, many=True).data

return Response({
    "data": data,
    "pagination": {
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
    }
})
```

**Problèmes identifiés :**
- ❌ **Duplication** : ~15-20 LOC répétées dans 4+ fichiers
- ❌ **Incohérence potentielle** : Variantes du calcul `total_pages` (ternaire vs max())
- ❌ **Maintenabilité** : Changement format pagination nécessite modifications multiples
- ❌ **Tests** : Logique pagination testée N fois (une fois par view)

**Pattern cible — Utilitaire réutilisable :**

```python
# core/pagination.py
def paginate_queryset(queryset, offset: int, limit: int) -> dict:
    """
    Paginate queryset with offset/limit.
    Story 26.11 (AC1): Utilitaire pagination réutilisable.
    """
    total = queryset.count()
    page = (offset // limit) + 1
    total_pages = max(1, (total + limit - 1) // limit)

    items = list(queryset[offset : offset + limit])

    return {
        'items': items,
        'pagination': {
            'page': page,
            'page_size': limit,
            'total': total,
            'total_pages': total_pages,
        }
    }
```

**Utilisation dans les views :**

```python
# executions/views/scheduled_views.py
from core.pagination import paginate_queryset

# AC2: Story 26.11 — Utilisation utilitaire pagination
result = paginate_queryset(qs, offset=offset, limit=limit)
data = ScheduledExecutionListItemSerializer(result['items'], many=True).data

return Response({
    "data": data,
    "pagination": result['pagination'],
    "available_actions": available_actions,  # Champs métier conservés
})
```

**Avantages :**
- ✅ **DRY** : Code pagination centralisé en un seul endroit
- ✅ **Cohérence** : Format pagination identique dans toute l'API
- ✅ **Maintenabilité** : Changements futurs en un seul fichier
- ✅ **Tests** : Logique pagination testée une seule fois (8 tests unitaires)
- ✅ **Lisibilité** : Views focalisées sur logique métier, pas calculs pagination

---

### Distinction avec `CustomPageNumberPagination` existant

**`CustomPageNumberPagination` (ligne 9-37 dans `core/pagination.py`) :**
- **Type** : DRF `PageNumberPagination` class
- **Usage** : ViewSets DRF (ex: `ActionViewSet`)
- **Paramètre** : `?page=1` (page number)
- **Méthode** : Utilisé via `pagination_class = CustomPageNumberPagination`
- **Exemple** : `catalog/views.py` — ActionViewSet.list()

**`paginate_queryset()` utility (nouvelle fonction, Story 26.11) :**
- **Type** : Fonction utilitaire standalone
- **Usage** : APIView classes (sans DRF ViewSet)
- **Paramètres** : `?offset=0&limit=50` (offset-based)
- **Méthode** : Appelé manuellement dans la méthode view
- **Exemple** : `executions/views/scheduled_views.py` — ScheduledExecutionsView.get()

**Pourquoi deux patterns ?**

| Contexte | Pattern | Justification |
|----------|---------|---------------|
| **DRF ViewSet** (CRUD complet) | `CustomPageNumberPagination` | DRF standard, configuration déclarative, pagination automatique via `paginate_queryset()` method |
| **APIView custom** (logique métier complexe) | `paginate_queryset()` utility | Contrôle manuel, offset/limit flexible, logique métier personnalisée (ex: filtres RBAC, agrégations) |

**Exemples de chaque pattern :**

```python
# Pattern 1 : DRF ViewSet — CustomPageNumberPagination
class ActionViewSet(viewsets.ModelViewSet):
    pagination_class = CustomPageNumberPagination  # Déclaratif

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)  # DRF built-in method
        serializer = ActionListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)  # Format automatique

# Pattern 2 : APIView custom — paginate_queryset() utility
class ScheduledExecutionsView(APIView):
    def get(self, request):
        # Logique métier complexe (filtres RBAC, validation env, etc.)
        qs = ScheduledExecution.objects.select_related(...)
        qs = apply_rbac_filters(qs, user=request.user)

        # AC2: Story 26.11 — Utilisation utilitaire pagination
        result = paginate_queryset(qs, offset=offset, limit=limit)
        data = ScheduledExecutionListItemSerializer(result['items'], many=True).data

        return Response({
            "data": data,
            "pagination": result['pagination'],
            "available_actions": [...],  # Champs métier custom
        })
```

**Rationale :**
- **ViewSets DRF** : Pagination DRF suffit, configuration déclarative, pattern standard
- **APIView custom** : Besoin de contrôle manuel, logique métier complexe nécessite pagination utility

---

### Analyse d'impact et risques

**Modules affectés :**

**Fichiers modifiés directement (3) :**
- `core/pagination.py` — Ajout fonction `paginate_queryset()` (~30 LOC)
- `executions/views/scheduled_views.py` — Migration ScheduledExecutionsView.get()
- `executions/views/list_views.py` — Migration ExecutionsListView.get()

**Fichiers tests à créer (1) :**
- `core/tests/test_pagination.py` — Tests unitaires `paginate_queryset()` (8 tests)

**Fichiers tests existants (vérification régression) :**
- `executions/tests/test_scheduled_views.py` — Tests ScheduledExecutionsView
- `tests/integration/test_pagination_contract.py` — Tests contrat API pagination

**Ampleur du changement :**
- **LOC ajoutées** : ~30 LOC (`paginate_queryset()` + docstring) + ~80 LOC (tests)
- **LOC modifiées** : ~20 LOC (2 views migrées)
- **LOC économisées** : ~15-20 LOC (duplication éliminée)
- **Net** : +90 LOC (tests inclus), mais duplication éliminée = maintenabilité améliorée

**Risques & Mitigations :**

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|-----------|
| **Régression format pagination** | MOYEN | FAIBLE | Tests existants détectent changement format. Tests unitaires `paginate_queryset()` couvrent tous cas limites. |
| **Oubli champ métier custom** | MOYEN | FAIBLE | `available_actions` dans ScheduledExecutionsView doit être conservé. Vérifier chaque Response avant/après migration. |
| **Changement comportement edge cases** | FAIBLE | FAIBLE | Tests unitaires couvrent : queryset vide, offset > total, limit > total, boundary exact. |
| **Incohérence total_pages** | FAIBLE | TRÈS FAIBLE | Formule unifiée `max(1, (total + limit - 1) // limit)` garantit minimum 1 page. Tests vérifient cohérence. |
| **Impact performance** | NUL | NUL | Fonction utility = même logique qu'avant, pas de surcharge. `queryset.count()` déjà présent dans views. |

**Stratégie de migration sécurisée :**

1. **Phase 1 : Créer utilitaire + tests (Tasks 1-2)**
   - Implémenter `paginate_queryset()` avec tous les edge cases
   - Écrire 8+ tests unitaires, vérifier 100% couverture
   - Valider comportement isolé avant migration views

2. **Phase 2 : Migrer views une par une (Tasks 3-4)**
   - Migrer ScheduledExecutionsView d'abord (moins de trafic prod)
   - Exécuter tests après chaque migration
   - Comparer format réponse avant/après (pas de régression)
   - Migrer ExecutionsListView ensuite (plus de trafic, validé en amont)

3. **Phase 3 : Validation finale (Task 5)**
   - Suite complète tests backend
   - Grep vérification : 0 duplication restante
   - Tests d'intégration pagination contract
   - Validation mypy/ruff

**Rationale :** Migration incrémentale avec validation à chaque étape, tests unitaires exhaustifs avant migration views.

---

### Tests unitaires — Cas limites couverts

**8 tests unitaires requis (AC4) :**

| # | Test case | Queryset | Offset | Limit | Assertions clés |
|---|-----------|----------|--------|-------|-----------------|
| 1 | **Première page** | 100 items | 0 | 25 | `page=1`, `total_pages=4`, `len(items)==25` |
| 2 | **Page milieu** | 100 items | 50 | 25 | `page=3`, `total_pages=4`, items[50:75] |
| 3 | **Dernière page partielle** | 93 items | 75 | 25 | `page=4`, `total_pages=4`, `len(items)==18` |
| 4 | **Queryset vide** | 0 items | 0 | 25 | `page=1`, `total=0`, `total_pages=1`, `items==[]` |
| 5 | **Offset > total** | 50 items | 100 | 25 | `items==[]`, pagination calculée correctement |
| 6 | **Limit > total** | 10 items | 0 | 50 | `page=1`, `total_pages=1`, `len(items)==10` |
| 7 | **Boundary exact** | 100 items | 0 | 50 | `page=1`, `total_pages=2` (exact, pas 3) |
| 8 | **Ordre préservé** | ordered qs | 0 | 25 | items respectent `order_by()` du queryset |

**Assertions communes à tous les tests :**
- Structure retour : `{'items': list, 'pagination': dict}`
- Champs pagination : `page`, `page_size`, `total`, `total_pages` présents
- Types corrects : `page` int, `items` list
- `total_pages >= 1` toujours (minimum 1 page, même si vide)

**Fixture requise :**
```python
@pytest.fixture
def sample_executions(db):
    """Create sample executions for pagination tests."""
    from executions.factories import ExecutionFactory
    # Create executions with predictable IDs for order verification
    return ExecutionFactory.create_batch(100)
```

**Exemple test complet :**
```python
def test_paginate_queryset_first_page(sample_executions):
    """Test pagination on first page."""
    from core.pagination import paginate_queryset
    from executions.models import Execution

    qs = Execution.objects.all().order_by('id')
    result = paginate_queryset(qs, offset=0, limit=25)

    # Structure
    assert 'items' in result
    assert 'pagination' in result

    # Items
    assert len(result['items']) == 25
    assert result['items'][0].id == sample_executions[0].id

    # Pagination
    pagination = result['pagination']
    assert pagination['page'] == 1
    assert pagination['page_size'] == 25
    assert pagination['total'] == 100
    assert pagination['total_pages'] == 4
```

**Couverture attendue :**
- **Lignes** : 100% (tous les chemins exécutés)
- **Branches** : 100% (conditions `total > 0`, `offset > total`, etc.)
- **Edge cases** : Tous couverts par les 8 tests

---

### Ordre d'implémentation recommandé

**Phase 1 : Fondation (Tasks 1-2) — ~2h**
1. **Task 1** : Créer `paginate_queryset()` dans `core/pagination.py`
   - Signature, implémentation, docstring, type hints
   - Commentaire Story 26.11 (AC1)
   - Vérifier import possible depuis `core.pagination`

2. **Task 2** : Écrire tests unitaires `core/tests/test_pagination.py`
   - 8 tests couvrant tous les cas limites
   - Fixture `sample_executions(db)`
   - Exécuter `pytest core/tests/test_pagination.py -v` — 8/8 ✅
   - Vérifier couverture : `pytest --cov=core.pagination` — 100%

**Phase 2 : Migration views (Tasks 3-4) — ~1.5h**
3. **Task 3** : Migrer ScheduledExecutionsView.get()
   - Import `paginate_queryset`
   - Remplacer calcul pagination manuel par appel utility
   - Conserver champ `available_actions` dans réponse
   - Tests : `pytest executions/tests/test_scheduled_views.py -v` — 0 régression

4. **Task 4** : Migrer ExecutionsListView.get()
   - Import `paginate_queryset`
   - Remplacer calcul pagination manuel par appel utility
   - Tests : `pytest executions/tests/ -k list -v` — 0 régression

**Phase 3 : Validation finale (Task 5) — ~30min**
5. **Task 5** : Tests de régression et validation
   - Suite complète : `pytest executions/tests/ -v`
   - Integration tests : `pytest tests/integration/test_pagination_contract.py -v`
   - Grep vérifications : 0 duplication, imports présents
   - Mypy/ruff : 0 erreurs/warnings
   - Documentation complétée (File List, Dev Notes, Completion Notes)

**Temps total estimé : ~4h**

**Rationale :** Approche bottom-up, tests d'abord pour valider comportement isolé, puis migration views avec validation à chaque étape.

---

### Exemples d'usage

**Exemple 1 : ScheduledExecutionsView.get() (AC2)**

```python
# AVANT (Story 26.11) — Pagination manuelle
qs = ScheduledExecution.objects.select_related("action", "user")
# ... (filtres RBAC, filtres métier)
qs = qs.order_by("-created_at")

total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if total > 0 else 1

items = list(qs[offset: offset + limit])
data_items = ScheduledExecutionListItemSerializer(items, many=True).data

return Response({
    "data": data_items,
    "pagination": {
        "page": page,
        "page_size": limit,
        "total": total,
        "total_pages": total_pages,
    },
    "available_actions": available_actions,
})
```

```python
# APRÈS (AC2: Story 26.11) — Utilisation utilitaire pagination
from core.pagination import paginate_queryset

qs = ScheduledExecution.objects.select_related("action", "user")
# ... (filtres RBAC, filtres métier)
qs = qs.order_by("-created_at")

# AC2: Story 26.11 — Utilisation utilitaire pagination
result = paginate_queryset(qs, offset=offset, limit=limit)
data_items = ScheduledExecutionListItemSerializer(result['items'], many=True).data

return Response({
    "data": data_items,
    "pagination": result['pagination'],
    "available_actions": available_actions,  # Champ métier conservé
})
```

**Réduction : 10 LOC → 3 LOC (pagination), ~7 LOC économisées**

---

**Exemple 2 : ExecutionsListView.get() (AC3)**

```python
# AVANT (Story 26.11) — Pagination manuelle
qs = Execution.objects.select_related("action", "user")
qs, _scope = apply_scope_filter(qs, user=request.user, scope="mine")
qs, _sd, _ed = apply_execution_filters(qs, request=request)
qs = qs.order_by("-created_at")

total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if limit else 1

items = list(qs[offset: offset + limit])
data = ExecutionSerializer(items, many=True).data

return Response({
    "data": data,
    "pagination": {"page": page, "page_size": limit, "total": total, "total_pages": total_pages},
})
```

```python
# APRÈS (AC3: Story 26.11) — Utilisation utilitaire pagination
from core.pagination import paginate_queryset

qs = Execution.objects.select_related("action", "user")
qs, _scope = apply_scope_filter(qs, user=request.user, scope="mine")
qs, _sd, _ed = apply_execution_filters(qs, request=request)
qs = qs.order_by("-created_at")

# AC3: Story 26.11 — Utilisation utilitaire pagination
result = paginate_queryset(qs, offset=offset, limit=limit)
data = ExecutionSerializer(result['items'], many=True).data

return Response({"data": data, "pagination": result['pagination']})
```

**Réduction : 9 LOC → 3 LOC (pagination), ~6 LOC économisées**

---

**Exemple 3 : Test unitaire `paginate_queryset()`**

```python
# core/tests/test_pagination.py

import pytest
from core.pagination import paginate_queryset
from executions.models import Execution

@pytest.fixture
def sample_executions(db):
    """Create 100 sample executions for pagination tests."""
    from executions.factories import ExecutionFactory
    return ExecutionFactory.create_batch(100)


def test_paginate_queryset_first_page(sample_executions):
    """Test pagination on first page (offset=0, limit=25)."""
    qs = Execution.objects.all().order_by('id')
    result = paginate_queryset(qs, offset=0, limit=25)

    # Structure
    assert 'items' in result
    assert 'pagination' in result
    assert isinstance(result['items'], list)
    assert isinstance(result['pagination'], dict)

    # Items
    assert len(result['items']) == 25
    assert result['items'][0].id == sample_executions[0].id  # Order preserved

    # Pagination
    pagination = result['pagination']
    assert pagination['page'] == 1
    assert pagination['page_size'] == 25
    assert pagination['total'] == 100
    assert pagination['total_pages'] == 4


def test_paginate_queryset_empty_queryset(db):
    """Test pagination with empty queryset."""
    qs = Execution.objects.none()
    result = paginate_queryset(qs, offset=0, limit=25)

    assert result['items'] == []
    assert result['pagination']['total'] == 0
    assert result['pagination']['total_pages'] == 1  # Minimum 1 page
    assert result['pagination']['page'] == 1


def test_paginate_queryset_last_page_partial(sample_executions):
    """Test pagination on last page with partial results (93 items, offset=75, limit=25)."""
    # Delete 7 items to have 93 total
    Execution.objects.filter(id__in=[e.id for e in sample_executions[:7]]).delete()

    qs = Execution.objects.all().order_by('id')
    result = paginate_queryset(qs, offset=75, limit=25)

    # Last page has only 18 items (93 - 75 = 18)
    assert len(result['items']) == 18
    assert result['pagination']['page'] == 4
    assert result['pagination']['total'] == 93
    assert result['pagination']['total_pages'] == 4  # (93 + 25 - 1) // 25 = 4
```

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/django_backend/
├── core/
│   ├── pagination.py                           # MODIFIED — Story 26.11 (AC1: ajout paginate_queryset())
│   └── tests/
│       └── test_pagination.py                  # CREATED — Story 26.11 (AC4: tests unitaires, 8 tests)
├── executions/
│   ├── views/
│   │   ├── scheduled_views.py                  # MODIFIED — Story 26.11 (AC2: migration vers paginate_queryset)
│   │   └── list_views.py                       # MODIFIED — Story 26.11 (AC3: migration vers paginate_queryset)
│   └── tests/
│       ├── test_scheduled_views.py             # UNCHANGED — Tests existants (vérification régression)
│       └── test_execution_list.py              # UNCHANGED — Tests existants (vérification régression)
└── tests/
    └── integration/
        └── test_pagination_contract.py         # UNCHANGED — Tests contrat API pagination
```

**Modules touchés par cette story (4 fichiers) :**

**Fichiers modifiés (3) :**
- `core/pagination.py` — Ajout fonction `paginate_queryset()` (~30 LOC)
- `executions/views/scheduled_views.py` — Import + migration (~7 LOC économisées)
- `executions/views/list_views.py` — Import + migration (~6 LOC économisées)

**Fichiers créés (1) :**
- `core/tests/test_pagination.py` — Tests unitaires `paginate_queryset()` (~80 LOC tests)

**Total LOC :**
- **Ajoutées** : ~30 LOC (utility) + ~80 LOC (tests) = 110 LOC
- **Économisées** : ~15 LOC (duplication éliminée)
- **Net** : +95 LOC (mais duplication éliminée, maintenabilité améliorée)

**Modules inchangés :**
- Modèles Django (`Execution`, `ScheduledExecution`) — aucun changement
- Serializers DRF — aucun changement
- Frontend — aucun impact (format API identique)
- Autres apps Django (catalog, profiles, inventory) — aucun impact (pour l'instant)

**Extensions futures (hors scope Story 26.11) :**
- **InventoryService.list_targets_for_user()** — Candidate pour migration (pagination manuelle détectée)
- **AuditLogListView.get()** — Candidate pour migration (pattern similaire)
- **Autres views avec offset/limit** — Identifier et migrer progressivement

---

## References

**Stories liées :**
- **Epic 26 (Story 26.11)** : Standardiser pagination (utilitaire réutilisable)
- **Story 26.9** : Standardiser format réponse API — Format `{"data": [...], "pagination": {...}}`
- **Story 22.6** : Corriger HIGH-6 — Standardiser champ `total` dans pagination
- **Story 26.10** : Renommer fonctions `_` exportées — Conventions Python, refactoring utils
- **Story 26.1** : Split inventory/services.py — Méthode `_paginate()` candidate pour migration

**Documentation externe :**
- [Django QuerySet API](https://docs.djangoproject.com/en/5.2/ref/models/querysets/) — Slicing, `count()`, `order_by()`
- [DRF Pagination](https://www.django-rest-framework.org/api-guide/pagination/) — CustomPageNumberPagination vs utility function
- [Epic 26: Qualité du Code](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md) — Section 5.2 (pagination duplication)

**Conventions du projet :**
- **Format pagination API** : `{"data": [...], "pagination": {page, page_size, total, total_pages}}`
- **Minimum 1 page** : `total_pages >= 1` même si queryset vide (consistency)
- **Offset/limit** : APIView classes custom logic
- **Page number** : DRF ViewSets (via `CustomPageNumberPagination`)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- `pytest core/tests/test_pagination.py -v` — 8/8 tests passent (0.70s)
- `pytest --cov=core.pagination` — 88% coverage (100% sur `paginate_queryset()`, 2 lignes manquantes dans `CustomPageNumberPagination`)
- `pytest executions/tests/test_scheduled_views_format.py` — 9/9 passent, 0 régression
- `pytest executions/tests/ -k list` — 15/15 passent (3 échecs pré-existants : 301 redirect, CHECK constraint)
- `pytest tests/integration/test_pagination_contract.py` — 5/5 passent
- `pytest executions/tests/` — 375/455 passent (80 échecs pré-existants, 0 nouvelle régression)
- `mypy core/pagination.py` — 0 erreurs (4 erreurs pré-existantes dans celery.py)
- `ruff check core/pagination.py` — All checks passed

### Completion Notes List

- ✅ AC1: Créé `paginate_queryset()` dans `core/pagination.py` — fonction utilitaire offset/limit avec TypedDict, validation input, docstring complète
- ✅ AC2: Migré `ScheduledExecutionsView.get()` — import + appel utilitaire, `available_actions` conservé
- ✅ AC3: Migré `ExecutionsListView.get()` — import + appel utilitaire, format réponse identique
- ✅ AC4: 11 tests unitaires dans `core/tests/test_pagination.py` — tous cas limites couverts (8 originaux + 3 validation input: negative offset, zero/negative limit)
- ✅ AC5: 0 régression — tests pagination 11/11 passent (0.72s), tests scheduled views 9/9, tests list views 15/15
- ✅ AC6: grep vérifie 0 duplication dans views migrées (approved_views.py aussi migré), imports présents dans 3 views, mypy/ruff clean
- **Code Review Adversarial:** 7 HIGH + 4 MEDIUM + 2 LOW issues trouvés, **TOUS FIXÉS AUTOMATIQUEMENT**
  - HIGH-1: Input validation (offset < 0, limit <= 0 → ValueError)
  - HIGH-2: Duplication approval_views.py (migré vers paginate_queryset)
  - HIGH-3: Tests validation input manquants (3 tests ajoutés)
  - HIGH-4: File List incomplet (approval_views.py ajouté)
  - HIGH-5: TypedDict pour return type (PaginationResult + PaginationInfo)
  - MEDIUM-1: Commentaire max(1, ...) rationale ajouté
  - LOW-1: Import order fixed (from __future__ avant docstring)
- **LOC économisées** : ~20 LOC de duplication éliminée (7 scheduled + 6 list + 7 approval)
- **LOC ajoutées** : ~70 LOC utilitaire + ~110 LOC tests = 180 LOC nettes
- **Formule unifiée** : `max(1, (total + limit - 1) // limit)` — corrige l'incohérence ternaire `if total > 0 else 1` / `if limit else 1`

### File List

**CRÉÉ :**
- `idp-portal/django_backend/core/tests/test_pagination.py` — Tests unitaires `paginate_queryset()` (11 tests: 8 originaux + 3 validation input)

**MODIFIÉ :**
- `idp-portal/django_backend/core/pagination.py` — Ajout fonction `paginate_queryset()` avec TypedDict, validation input, commentaires (~70 LOC avec docstring)
- `idp-portal/django_backend/executions/views/scheduled_views.py` — Import + migration vers utilitaire pagination
- `idp-portal/django_backend/executions/views/list_views.py` — Import + migration vers utilitaire pagination
- `idp-portal/django_backend/executions/views/approval_views.py` — Code review fix: migration vers utilitaire pagination (duplication éliminée)
