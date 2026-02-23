# Story 34.1 : Quick wins Backend — DI, queryset, validation

Status: done

<!-- Réf: CODEBASE-REVIEW.md §14 SOLID-BE-8, NEW-1, SOLID-BE-11 -->

## Story

En tant que développeur backend,
je veux corriger trois dettes techniques ciblées (DIP, queryset, DRY serializers),
afin d'améliorer la maintenabilité, la testabilité et la cohérence du module catalog.

## Contexte

Cette story couvre les **quick wins backend prioritaires** (epic 34, issues haute/moyenne) identifiés dans le CODEBASE-REVIEW du 2026-02-21 :

- **SOLID-BE-8 [MEDIUM]** — `destroy()`, `deactivate()`, `reactivate()` dans `catalog/views/action_views.py` instancient `CatalogService()` directement, contournant le mécanisme DI introduit à la Story 33.4.
- **NEW-1 [MEDIUM]** — `CatalogActionViewSet.get_queryset()` : vérifier si le queryset est encore recréé au lieu d'être chaîné pour les filtres `tags` et `category` (peut avoir été partiellement corrigé par Story 33.3 — **lire le fichier actuel avant de toucher quoi que ce soit**).
- **SOLID-BE-11 [LOW]** — `ActionSerializer` et `ActionCreateSerializer` dupliquent les méthodes `validate_engine`, `validate_platform`, `validate_category` — DRY violation.

## Acceptance Criteria

### AC1 — SOLID-BE-8 : DI dans destroy/deactivate/reactivate
- `destroy()`, `deactivate()`, `reactivate()` utilisent `self.get_catalog_service()` et non `CatalogService()`
- 0 occurrence de `CatalogService()` hors `get_catalog_service()` dans `action_views.py`
- Tests unitaires des 3 méthodes mockables via `_catalog_service_class` (pattern existant)

### AC2 — NEW-1 : Correction queryset get_queryset()
- Localiser `CatalogActionViewSet.get_queryset()` dans le fichier actuel (probablement `catalog/views/catalog_views.py` après refactoring)
- Si le bug est encore présent : `tags_filter` ET `category` chaînent sur le queryset existant (pas de recréation `Action.objects.search_by_tags()`)
- Si les deux filtres sont fournis simultanément, les deux s'appliquent (AND logique)
- Test de non-régression : `?tags=X&category=Y` → les deux filtres sont actifs

### AC3 — SOLID-BE-11 : Mixin de validation DRY
- `ActionFieldValidationMixin` créé dans `catalog/serializers.py` (ou `catalog/serializer_mixins.py`)
- Le mixin contient : `validate_engine`, `validate_platform`, version commune de `validate_category`
- `ActionSerializer` hérite du mixin et supprime ses copies dupliquées
- `ActionCreateSerializer` hérite du mixin ; conserve un override `validate_category` pour gérer blank string → None
- Tous les tests de validation existants passent sans modification

### AC4 — Tests
- `pytest django_backend/catalog/` : 0 régression
- `mypy django_backend/catalog/` : 0 erreur nouvelle
- `ruff check django_backend/catalog/` : 0 violation nouvelle

## Tasks / Subtasks

- [x] **Task 1 — SOLID-BE-8 : corriger DI** (AC: #1)
  - [x] 1.1 Lire `catalog/views/action_views.py` lignes 430–510 (destroy/deactivate/reactivate)
  - [x] 1.2 Remplacer `service = CatalogService()` par `service = self.get_catalog_service()` dans `destroy()` (~l.437)
  - [x] 1.3 Remplacer dans `deactivate()` (~l.454)
  - [x] 1.4 Remplacer dans `reactivate()` (~l.493)
  - [x] 1.5 Vérifier grep : `grep -n "CatalogService()" catalog/views/action_views.py` → 0 résultat ✅
  - [x] 1.6 Ajouter/adapter tests unitaires avec mock `_catalog_service_class` pour les 3 méthodes

- [x] **Task 2 — NEW-1 : vérifier et corriger queryset** (AC: #2)
  - [x] 2.1 Localiser `CatalogActionViewSet.get_queryset()` — chercher dans `catalog/views/catalog_views.py`
  - [x] 2.2 Lire le code actuel ; vérifier si `Action.objects.search_by_tags()` est encore présent (recréation) vs `queryset.search_by_tags()` (chaîne)
  - [x] 2.3 Si bug présent : remplacer la/les recréation(s) par chaînage sur le queryset courant
  - [x] 2.4 Si déjà corrigé : ajouter un commentaire explicatif + test de non-régression `?tags=X&category=Y` (test existant `test_filter_by_tags_and_category` couvre ce cas)

- [x] **Task 3 — SOLID-BE-11 : mixin validation** (AC: #3)
  - [x] 3.1 Lire `catalog/serializers.py` lignes 246–295 et 481–520
  - [x] 3.2 Identifier les 3 méthodes identiques : `validate_engine`, `validate_platform`, `validate_category`
  - [x] 3.3 Créer `ActionFieldValidationMixin` avec les 3 méthodes (version stricte de `validate_category`)
  - [x] 3.4 `ActionCreateSerializer` : garder un override `validate_category` pour gérer blank string → None
  - [x] 3.5 Faire hériter les deux serializers du mixin ; supprimer les méthodes dupliquées
  - [x] 3.6 Lancer tests serializers → 0 régression ✅

- [x] **Task 4 — Validation finale** (AC: #4)
  - [x] 4.1 `pytest catalog/tests/ -x` → passe (7 failures pré-existantes, 0 régression introduite)
  - [x] 4.2 `mypy catalog/` → 0 nouvelle erreur (9 erreurs pré-existantes inchangées)
  - [x] 4.3 `ruff check catalog/` → 0 nouvelle violation (17 violations vs 19 baseline, -2)

## Dev Notes

### ⚠️ Pattern DI EXISTANT — À utiliser tel quel (Story 33.4)

Le mécanisme DI est déjà en place dans `catalog/views/action_views.py`. Ne pas en créer un nouveau :

```python
# Lignes 60–69 (existant)
_catalog_service_class: type[CatalogService] = CatalogService

@classmethod
def _override_catalog_service(cls, service_class: type[CatalogService]) -> None:
    cls._catalog_service_class = service_class

def get_catalog_service(self) -> CatalogService:
    """Return a CatalogService instance (overridable in tests)."""
    return self._catalog_service_class()
```

**La correction SOLID-BE-8 est un simple remplacement de 3 lignes.** Rien d'autre à faire.

### ⚠️ NEW-1 — Vérification obligatoire avant modification

Le CODEBASE-REVIEW du 2026-02-21 signale une recréation de queryset. Cependant, l'analyse du code révèle que la Story 33.3 a peut-être déjà corrigé ce point. Le code vu en `catalog/views/catalog_views.py` utilise `queryset.search_by_tags()` (chaînage correct).

**Ne jamais "corriger" du code déjà correct.** Lire le fichier, vérifier si `Action.objects.search_by_tags()` existe encore. Si non → ajouter commentaire + test seulement.

### ⚠️ SOLID-BE-11 — Différence subtile validate_category à préserver

`ActionSerializer.validate_category` (version STRICTE dans le mixin) :
```python
def validate_category(self, value: str | None) -> str | None:
    if value is None:
        return value
    if not RefCategory.objects.filter(code=value, is_active=1).exists():
        ...raise ValidationError
    return value
```

`ActionCreateSerializer.validate_category` (OVERRIDE local à conserver) :
```python
def validate_category(self, value: str | None) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None  # ← DIFFÉRENCE : blank string accepté → None
    if not RefCategory.objects.filter(code=value, is_active=1).exists():
        ...raise ValidationError
    return value
```

Le mixin prend la version stricte. `ActionCreateSerializer` garde son override.

### Structure des fichiers concernés

```
django_backend/catalog/
  views/
    action_views.py      ← SOLID-BE-8 — destroy/deactivate/reactivate (l.434–506)
    catalog_views.py     ← NEW-1 — get_queryset() à vérifier
    __init__.py
  serializers.py         ← SOLID-BE-11 — ActionSerializer (l.246–295), ActionCreateSerializer (l.481–520)
  models/
    action.py            ← Manager Action avec search_by_tags()
  tests/
    test_action_views.py
    test_catalog_views.py
    test_serializers.py
```

**Ne pas chercher `catalog/views.py` monolithique** — éclaté par Stories 26.3 et 33.3.

### Tech stack et contraintes

- Django 5.2, DRF 3.16 — [Source: docs/backend-implementation.md]
- Oracle DB — ne pas utiliser `distinct()` sur CLOB, éviter les subqueries complexes
- `search_by_tags()` est définie sur le `Manager`/`QuerySet` custom de `Action` — vérifier `catalog/models/action.py` avant d'appeler cette méthode en chaîne
- `_PLATFORM_ALIAS` : dict de normalisation plateforme, déjà défini dans `catalog/serializers.py` — le mixin y a accès

### Contexte git récent (commits pertinents)

- `ec7a77b feat(33-4): DIP — injection de dépendances pour les services principaux` — Pattern DI établi
- `fa39f92 feat(33-5): SRP — découper ActionForm et ActionWizard` — non pertinent pour cette story
- `aa560db docs(33-6): documentation et checklist conformité SOLID` — référence de conformité

### Commandes de test recommandées

```bash
# Depuis le répertoire django_backend
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Tests ciblés (rapides)
.venv/bin/python -m pytest catalog/tests/test_action_views.py catalog/tests/test_catalog_views.py catalog/tests/test_serializers.py -v

# Vérification complète catalog
.venv/bin/python -m pytest catalog/ -x

# Type checking
.venv/bin/python -m mypy catalog/

# Linter
.venv/bin/python -m ruff check catalog/
```

> ⚠️ Problème connu : `pytest` peut échouer si `tests.py` et `tests/` coexistent. Utiliser `--ignore=*/tests.py` si nécessaire.

### Project Structure Notes

- Tous les fichiers modifiés sont dans `catalog/` — scope étroit, risque de régression limité
- Aucune migration DB requise (aucun changement de modèle)
- Aucun changement d'API publique (changement interne uniquement)
- Conformité avec le pattern DI établi en Story 33.4 [Source: _bmad-output/implementation-artifacts/33-4-dip-injection-dependances-services.md]

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-8] — DIP catalog views
- [Source: idp-portal/CODEBASE-REVIEW.md#NEW-1] — Queryset recreation
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-11] — Serializer duplication
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.1]
- [Source: _bmad-output/implementation-artifacts/33-4-dip-injection-dependances-services.md] — Pattern DI de référence
- [Source: django_backend/catalog/views/action_views.py] — Lignes 60–70 (get_catalog_service), 434–506 (destroy/deactivate/reactivate)
- [Source: django_backend/catalog/serializers.py] — Lignes 248–281 (ActionSerializer), 481–509 (ActionCreateSerializer)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_Aucun problème bloquant rencontré._

### Completion Notes List

- **SOLID-BE-8 (AC1)** : 3 remplacements `CatalogService()` → `self.get_catalog_service()` dans `destroy()`, `deactivate()`, `reactivate()`. 3 tests DI ajoutés dans `test_action_views_di.py` (5/5 passent).
- **NEW-1 (AC2)** : Bug déjà corrigé (Story 33.3). `queryset.search_by_tags()` chaîne correctement pour `tags` et `category`. Commentaire explicatif ajouté dans `catalog_views.py`. Test `test_filter_by_tags_and_category` existant couvre le cas `?tags=X&category=Y`.
- **SOLID-BE-11 (AC3)** : `ActionFieldValidationMixin` créé dans `catalog/serializers.py`. `ActionSerializer` et `ActionCreateSerializer` en héritent. `ActionCreateSerializer` conserve son override `validate_category` (blank string → None). 6 méthodes dupliquées supprimées.
- **Tests (AC4)** : 0 régression (7 failures pré-existantes confirmées par vérification git stash). mypy : 0 nouvelle erreur. ruff : 0 nouvelle violation (-2 vs baseline).

### File List

- `idp-portal/django_backend/catalog/views/action_views.py`
- `idp-portal/django_backend/catalog/views/catalog_views.py`
- `idp-portal/django_backend/catalog/serializers.py`
- `idp-portal/django_backend/catalog/tests/test_action_views_di.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`


## Change Log

| Date | Description |
|------|-------------|
| 2026-02-22 | Implémentation complète : SOLID-BE-8 (DI), NEW-1 (queryset commentaire), SOLID-BE-11 (ActionFieldValidationMixin). 3 fichiers modifiés, 1 fichier tests enrichi. 0 régression. |
| 2026-02-22 | Code review : 3 issues MEDIUM corrigées — test_deactivate uniformisé (APIRequestFactory), assertions response codes ajoutées (204/200), sprint-status.yaml ajouté à la File List. |
