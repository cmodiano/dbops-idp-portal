# Story 30.6: Incohérences API (format de réponse)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur frontend,
Je veux un format de réponse API cohérent (ex. `{"data": ...}`, pagination quand attendue),
Afin d'éviter les `undefined` et les branches de code compensatoires.

## Acceptance Criteria

1. **Given** les endpoints `validateIntegration` et `validateAllIntegrations`
   **When** le backend répond
   **Then** le frontend reçoit l'objet attendu (soit backend wrap dans `{"data": ...}`, soit frontend utilise `apiFetchRaw` et les deux sont alignés)

2. **Given** les endpoints `/reference/*` retournent des données
   **When** le backend répond
   **Then** le format est aligné avec le reste de l'API (ex. `{"data": [...]}`)

3. **Given** la liste catalogue retourne des actions paginées
   **When** le backend répond
   **Then** la réponse retourne `pagination` lorsque applicable (aligné avec les autres listes)

4. **Given** le développeur frontend utilise l'API
   **When** il consomme les endpoints
   **Then** il n'a pas besoin de branches de code compensatoires pour gérer des formats incohérents

## Tasks / Subtasks

- [x] Task 1: Corriger APIFMT-1 et APIFMT-2 - validateIntegration et validateAllIntegrations (AC: #1)
  - [x] Subtask 1.1: Analyser le problème - `apiFetch` extrait `body.data` mais backend retourne objet nu
  - [x] Subtask 1.2: Décision d'implémentation - wrapper backend dans `{"data": ...}` OU utiliser `apiFetchRaw` frontend
  - [x] Subtask 1.3: Implémenter la correction choisie pour `validateIntegration` (integrations/views.py:261)
  - [x] Subtask 1.4: Implémenter la correction choisie pour `validateAllIntegrations` (integrations/views.py:298)
  - [x] Subtask 1.5: Mettre à jour le code frontend si nécessaire (integrations_service.ts:59-68)
  - [x] Subtask 1.6: Écrire des tests unitaires pour validation du format de réponse

- [x] Task 2: Corriger APIFMT-3 - Endpoints /reference/* retournent des arrays nus (AC: #2)
  - [x] Subtask 2.1: Wrapper les réponses de `list_engines` dans `{"data": [...]}`
  - [x] Subtask 2.2: Wrapper les réponses de `list_platforms` dans `{"data": [...]}`
  - [x] Subtask 2.3: Wrapper les réponses de `list_categories` dans `{"data": [...]}`
  - [x] Subtask 2.4: Mettre à jour le frontend pour utiliser `apiFetch` au lieu de `apiFetchRaw`
  - [x] Subtask 2.5: Écrire des tests pour vérifier le format cohérent

- [x] Task 3: Corriger APIFMT-4 - Catalogue list sans info de pagination (AC: #3)
  - [x] Subtask 3.1: Analyser le code actuel dans catalog/views.py:862-876
  - [x] Subtask 3.2: Vérifier que `get_paginated_response` retourne bien `{"data": [...], "pagination": {...}}`
  - [x] Subtask 3.3: S'assurer que le cache retourne le même format avec pagination
  - [x] Subtask 3.4: Écrire des tests pour valider la présence de `pagination` dans la réponse

- [x] Task 4: Tests d'intégration end-to-end (AC: #4)
  - [x] Subtask 4.1: Créer des tests vérifiant le format cohérent sur tous les endpoints modifiés
  - [x] Subtask 4.2: Vérifier qu'aucune branche compensatoire n'est nécessaire côté frontend
  - [x] Subtask 4.3: Valider avec les tests existants qu'aucune régression n'est introduite

## Dev Notes

### Contexte Epic 30
Cette story fait partie de l'Epic 30 "Corrections exhaustives — Codebase Review IDP Portal" qui adresse 65 findings identifiés dans CODEBASE-REVIEW.md (16 février 2026). Story 30.6 cible spécifiquement les incohérences de format d'API (APIFMT-1 à APIFMT-4).

### Issues APIFMT identifiées

**APIFMT-1 [HIGH]** — `validateIntegration` : `apiFetch` unwrap `.data` mais backend retourne objet nu
- Fichier frontend: `integrations_service.ts:59`
- Fichier backend: `integrations/views.py:261`
- Problème: `apiFetch` extrait `body.data` → retourne `undefined` car le backend retourne l'objet directement
- Fix: Utiliser `apiFetchRaw` côté frontend OU wrapper dans `{"data": ...}` côté backend

**APIFMT-2 [HIGH]** — `validateAllIntegrations` : même problème
- Fichier frontend: `integrations_service.ts:64`
- Fichier backend: `integrations/views.py:298`

**APIFMT-3 [MEDIUM]** — Endpoints `/reference/*` retournent des arrays nus
- Fichier: `reference/views.py:57,90,117`
- Tous les endpoints reference retournent `Response(serializer.data)` (array direct) au lieu du format `{"data": [...]}` utilisé partout ailleurs
- Le frontend utilise `apiFetchRaw` pour compenser — ça fonctionne mais c'est incohérent

**APIFMT-4 [MEDIUM]** — Catalogue list retourne `{"data": [...]}` sans info de pagination
- Fichier: `catalog/views.py:862-876`
- Les autres endpoints list retournent `{"data": [...], "pagination": {...}}`

### Standards API du projet

D'après l'analyse du codebase:

**Format standard pour les endpoints list:**
```python
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

**Format standard pour les endpoints detail/action:**
```python
{
  "data": {
    "id": 1,
    "name": "...",
    ...
  }
}
```

**Fonctions frontend:**
- `apiFetch<T>()`: Extrait automatiquement `body.data` et retourne le type `T`
- `apiFetchRaw<T>()`: Retourne le body complet sans extraction

### Architecture technique

**Backend:**
- Django 5.2 + Django REST Framework 3.16
- Base de données: Oracle
- Endpoints dans: `integrations/views.py`, `reference/views.py`, `catalog/views.py`
- Pagination DRF avec `get_paginated_response()`

**Frontend:**
- React + TypeScript + Ant Design
- Client API: `api_client.ts` avec `apiFetch` et `apiFetchRaw`
- Services: `integrations_service.ts`, etc.

### Stratégie de correction recommandée

**Option 1 (Recommandée): Standardiser le backend**
- Wrapper tous les endpoints dans `{"data": ...}` côté backend
- Permet d'utiliser `apiFetch` partout côté frontend (plus cohérent)
- Change minimale côté frontend

**Option 2: Adapter le frontend**
- Utiliser `apiFetchRaw` pour les endpoints non-conformes
- Aucun changement backend
- Moins cohérent, branches compensatoires

→ **Choisir Option 1** pour cohérence maximale

### Fichiers à modifier

**Backend:**
- `idp-portal/django_backend/integrations/views.py` (lignes 261, 298)
- `idp-portal/django_backend/reference/views.py` (lignes 57, 90, 117)
- `idp-portal/django_backend/catalog/views.py` (vérification pagination lignes 862-876)

**Frontend (si nécessaire):**
- `idp-portal/frontend/src/services/integrations_service.ts` (lignes 59-68)
- `idp-portal/frontend/src/services/reference_service.ts` (potentiellement)

**Tests:**
- Tests unitaires backend pour chaque endpoint modifié
- Tests d'intégration frontend pour validation du format

### Travaux précédents de l'Epic 30

Stories déjà complétées dans cet epic:
- **30.1**: Endpoints approve/reject + bug filtres catalogue + config sécurité (CRITICAL) ✅
- **30.2**: Endpoints remediation et export dashboard (HIGH) ✅
- **30.3**: Bugs logiques backend (BUG-BE-2 à BE-7) ✅
- **30.4**: Bugs logiques frontend (notifications, Alert, rowKey, hooks) ✅
- **30.5**: Sécurité auth, uploads, dev bypass, CORS, Celery ✅

Learnings des stories précédentes:
- Story 30.1: Importance de la cohérence dans le format des réponses API
- Story 30.4: Les changements d'API nécessitent une mise à jour coordonnée frontend/backend
- Tests systématiques pour éviter les régressions

### Patterns de code établis

**Backend - Format de réponse standard:**
```python
# Pour les listes paginées (via DRF pagination)
page = self.paginate_queryset(queryset)
if page is not None:
    serializer = self.get_serializer(page, many=True)
    return self.get_paginated_response(serializer.data)

# Pour les actions/endpoints custom
return Response({"data": result})
```

**Frontend - Consommation API:**
```typescript
// Utiliser apiFetch pour les endpoints conformes (body.data extraction automatique)
export async function getItems(): Promise<Item[]> {
  return apiFetch<Item[]>('/items/');
}

// Utiliser apiFetchRaw uniquement si besoin du body complet
export async function getItemsWithMeta(): Promise<{data: Item[], meta: Meta}> {
  return apiFetchRaw<{data: Item[], meta: Meta}>('/items/');
}
```

### Testing requirements

**Backend:**
- Tests unitaires pour chaque endpoint modifié
- Vérifier le format `{"data": ...}` ou `{"data": [...], "pagination": {...}}`
- Vérifier la cohérence avec les autres endpoints

**Frontend:**
- Tests de service vérifiant que les appels retournent les bonnes données
- Tests d'intégration pour valider qu'aucune branche compensatoire n'est nécessaire
- Pas de régression sur les fonctionnalités existantes

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#Section 5 - Incohérences API]
- [Source: _bmad-output/planning-artifacts/epic-30-codebase-review-corrections-fev-2026.md#Story 30.6]
- [Source: idp-portal/frontend/src/services/api_client.ts:192-205 - apiFetch implementation]
- [Source: idp-portal/django_backend/integrations/views.py:261-298 - validate endpoints]
- [Source: idp-portal/django_backend/reference/views.py:57,90,117 - reference endpoints]
- [Source: idp-portal/django_backend/catalog/views.py:862-876 - catalog list endpoint]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- **APIFMT-1/APIFMT-2**: Backend `integrations/views.py` — réponses `validate` et `validate_all` wrappées dans `{"data": ...}`. Frontend `integrations_service.ts` utilise déjà `apiFetch` → fonctionne correctement sans changement.
- **APIFMT-3**: Backend `reference/views.py` — `list_engines`, `list_platforms`, `list_categories`, `create_category`, `update_category` wrappés dans `{"data": ...}`. Frontend `reference_service.ts` et `categories_service.ts` migrés de `apiFetchRaw` vers `apiFetch`.
- **APIFMT-4**: Backend `catalog/views.py` — cas non-paginé ajouté pagination info `{"data": [...], "pagination": {...}}`. Correction bug cache hit (`self.get_paginated_response()` sans `self.page`) — cache stocke maintenant le dict complet au lieu des données brutes.
- **Option 1 choisie**: Standardisation backend (wrapper `{"data": ...}`) — permet l'utilisation uniforme de `apiFetch` côté frontend.
- **Tests**: 10 tests E2E format API (nouveau test cache hit) + 47 tests reference/validation + 15 tests catalog + 6 tests frontend categories = 130 backend tests pass, 6 frontend tests pass, 0 régression.
- **Code Review Fixes (16 fév 2026)**:
  - FIX CRITICAL-1: Type hint `_catalog_cache` corrigé de `list[dict]` → `dict[str, Any]` (views.py:726)
  - FIX MEDIUM-2: Documentation ajoutée sur changement format cache (views.py:725-726)
  - FIX MEDIUM-3: Test cache hit ajouté `test_catalog_list_cache_hit_preserves_format` (test_api_response_format.py)
  - DOC MEDIUM-1: Commentaire ajouté sur `/feature-flags/` format exception (feature_flag_views.py:66-69)

### File List

**Backend modifié:**
- `idp-portal/django_backend/integrations/views.py` — wrapper `{"data": ...}` sur validate et validate_all
- `idp-portal/django_backend/reference/views.py` — wrapper `{"data": ...}` sur list_engines, list_platforms, list_categories, create_category, update_category
- `idp-portal/django_backend/catalog/views.py` — pagination info cas non-paginé + fix cache hit format + **review fix:** type hint cache + doc
- `idp-portal/django_backend/core/feature_flag_views.py` — **review fix:** doc format exception

**Frontend modifié:**
- `idp-portal/frontend/src/services/reference_service.ts` — `apiFetchRaw` → `apiFetch` pour engines/platforms
- `idp-portal/frontend/src/services/categories_service.ts` — `apiFetchRaw` → `apiFetch` pour categories/create/update

**Tests modifié/créé:**
- `idp-portal/django_backend/reference/tests/test_views.py` — mis à jour pour format `{"data": [...]}`
- `idp-portal/django_backend/reference/tests/test_categories.py` — mis à jour pour format `{"data": ...}`
- `idp-portal/django_backend/integrations/tests/test_validation_views.py` — mis à jour pour format `{"data": ...}`
- `idp-portal/django_backend/core/tests/test_api_response_format.py` — **NOUVEAU** — 10 tests E2E format API cohérent + **review fix:** test cache hit
- `idp-portal/frontend/src/services/categories_service.test.ts` — mis à jour `apiFetchRaw` → `apiFetch`

## Change Log

- 2026-02-16 10:00: Story 30.6 implémentation complétée — APIFMT-1 à APIFMT-4 corrigés, Option 1 (standardisation backend) appliquée, 129 backend + 6 frontend tests pass, 0 régression
- 2026-02-16 12:02: Code review adversarial complétée — 6 issues trouvées (1 CRITICAL, 3 MEDIUM, 2 LOW), 4 fixes appliqués automatiquement, 130 backend + 6 frontend tests pass
