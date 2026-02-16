# Story 30.12: Incohérences modèles et serializers (tags, audit, champs)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **développeur backend**,
je veux une normalisation des tags unique, un audit fiable (hash, user_id), et des conventions de champs claires,
afin d'éviter les bugs subtils, les collisions d'audit, et les incohérences de données.

## Acceptance Criteria

**Issues couvertes :** INCON-1, INCON-2, INCON-3, INCON-4, INCON-5 (CODEBASE-REVIEW.md)

### AC1: Normalisation de tags unifiée (INCON-1 MEDIUM)

**Given** la création ou mise à jour de tags via n'importe quel chemin d'exécution
**When** des espaces sont présents dans le nom du tag
**Then** la même règle de normalisation s'applique partout (espaces → underscore)
**And** `catalog/models.py:normalize_tag_name()` et `catalog/services.py:_sync_tags()` utilisent la même logique
**And** aucun tag créé avec des espaces éliminés différemment selon le chemin

**Fichiers :**
- `django_backend/catalog/models.py:51-58`
- `django_backend/catalog/services.py:173-192`

**Problème actuel :**
- `models.py:55` : `name.strip().lower().replace(" ", "_")` — **OK, espaces → underscore**
- `services.py:187` : `tag_name.lower().strip().replace(' ', '_')` — **OK, espaces → underscore**

**Note :** Après investigation, les deux méthodes utilisent déjà la même normalisation (espaces → underscore). Cependant, la story reste valide pour :
1. Valider que c'est bien le cas partout dans le code
2. Ajouter des tests pour garantir la cohérence
3. Documenter la convention de normalisation

### AC2: Hash MD5 pour audit fiabilisé ou documenté (INCON-2 MEDIUM)

**Given** les signals d'audit pour `IntegrationTypeCatalogue` et `IntegrationAction`
**When** un hash MD5 tronqué est utilisé comme `entity_id` pour des clés primaires string
**Then** soit :
  - **Option A (préférée)** : Utiliser un compteur séquentiel ou un UUID pour `entity_id` (pas de collision)
  - **Option B** : Documenter que le hash MD5 tronqué à 8 caractères hex modulo 10^9 est acceptable car le volume de catalogues est faible (<1000) et les collisions sont statistiquement improbables
**And** si Option B, ajouter un test de détection de collision en développement
**And** si Option A, migrer les `entity_id` existants sans casser les références d'audit

**Fichiers :**
- `django_backend/integrations/signals.py:39-40`
- `django_backend/integrations/signals.py:78-79` (IntegrationAction)

**Problème actuel :**
```python
# integrations/signals.py:39-40
entity_id = int(hashlib.md5(instance.code.encode()).hexdigest()[:8], 16) % (10**9)
```
→ Collisions possibles entre différents codes → requêtes d'audit peu fiables.

**Solution recommandée (Option A) :**
```python
# Utiliser un compteur séquentiel basé sur l'ID du modèle ou un UUID
# Si IntegrationTypeCatalogue a un ID numérique secondaire, l'utiliser
# Sinon, créer un mapping code → entity_id dans une table dédiée
entity_id = instance.id  # Si un champ id existe
# OU
entity_id = hash(instance.code) % (10**18)  # hash() Python (plus robuste que MD5 tronqué)
```

### AC3: Audit signals capturent le user_id réel (INCON-3 MEDIUM)

**Given** les signals d'audit pour les catalogues d'intégration
**When** une modification est effectuée par un utilisateur authentifié
**Then** le `user_id` réel est capturé dans l'audit trail
**And** plus de TODO "system" uniquement
**And** si aucun utilisateur n'est disponible (migration, fixture), alors `user_id='system'` est acceptable

**Fichier :** `django_backend/integrations/signals.py:18-26`

**Problème actuel :**
```python
# integrations/signals.py:23-26
# TODO Story 24.2: Implement thread-local request context to capture actual user
# For now, signals don't have direct access to request, so we use 'system'
return 'system'
```
→ Impossible de tracer quel utilisateur a modifié les catalogues d'intégration.

**Solution attendue :**
```python
from core.middleware import get_current_user  # ou crum, django-crum

def _get_user_id_from_context():
    """Extract user_id from thread-local request context."""
    user = get_current_user()  # Récupère l'utilisateur via middleware
    if user and user.is_authenticated:
        return str(user.user_id)
    # Fallback pour fixtures, migrations, tâches Celery
    return 'system'
```

**Alternative :** Si `get_current_user()` n'existe pas encore, utiliser `django-crum` :
```bash
pip install django-crum
```
```python
# settings.py
MIDDLEWARE = [
    ...
    'crum.CurrentRequestUserMiddleware',
    ...
]

# signals.py
from crum import get_current_user

def _get_user_id_from_context():
    user = get_current_user()
    if user and user.is_authenticated:
        return str(user.user_id)
    return 'system'
```

### AC4: IntegerField pour booléens documenté (INCON-4 LOW)

**Given** les champs `is_admin`, `is_auditor`, `is_active` définis comme `IntegerField`
**When** un développeur consulte les modèles
**Then** un commentaire ou documentation explique que c'est un choix intentionnel pour Oracle
**And** la convention `0 = False, 1 = True` est claire
**And** un helper method `.is_admin_bool()` ou `.is_active_bool()` est optionnellement fourni pour faciliter l'usage

**Fichiers :**
- `django_backend/profiles/models.py:106-107` (`is_admin`, `is_auditor`)
- `django_backend/executions/models.py:469` (`is_active`)

**Problème actuel :**
```python
# profiles/models.py:106-107
is_admin = models.IntegerField(default=0, db_column='IS_ADMIN')  # Oracle NUMBER(1) CHECK: 0, 1
is_auditor = models.IntegerField(default=0, db_column='IS_AUDITOR')  # Oracle NUMBER(1) CHECK: 0, 1
```
→ Les commentaires existent déjà, mais le code doit utiliser `== 1` au lieu de truthiness.

**Solution attendue :**
```python
# Ajouter des helper methods pour faciliter l'usage
class Profile(models.Model):
    is_admin = models.IntegerField(default=0, db_column='IS_ADMIN')  # Oracle NUMBER(1) CHECK: 0, 1
    is_auditor = models.IntegerField(default=0, db_column='IS_AUDITOR')  # Oracle NUMBER(1) CHECK: 0, 1

    @property
    def is_admin_bool(self) -> bool:
        """Return boolean representation of is_admin (1 = True, 0 = False)."""
        return self.is_admin == 1

    @property
    def is_auditor_bool(self) -> bool:
        """Return boolean representation of is_auditor (1 = True, 0 = False)."""
        return self.is_auditor == 1
```

**Alternative :** Auditer le code pour s'assurer que tous les usages de `is_admin`, `is_auditor`, `is_active` utilisent bien `== 1` ou `== 0` et non la truthiness Python.

### AC5: User.is_authenticated documenté (INCON-5 LOW)

**Given** le modèle `User` avec `is_authenticated = True` en attribut de classe
**When** un développeur consulte le modèle
**Then** un commentaire explique pourquoi c'est un attribut de classe et non une méthode
**And** la différence avec le modèle User Django natif est documentée
**And** le comportement pour les users soft-deleted est clarifié (est-ce intentionnel ?)

**Fichier :** `django_backend/idp_auth/models.py:65-67`

**Problème actuel :**
```python
# idp_auth/models.py:65-67
# Compatibility with middleware and exception handler (request.user.is_authenticated).
# AnonymousUser has is_authenticated = False; our User instances are always authenticated.
is_authenticated = True
```
→ Le commentaire existe déjà et explique le choix. Cependant, il faut valider que les users soft-deleted ne posent pas problème.

**Solution attendue :**
- Vérifier que les users soft-deleted sont bien filtrés avant l'authentification (via middleware ou queryset)
- Si nécessaire, transformer `is_authenticated` en propriété :
```python
@property
def is_authenticated(self) -> bool:
    """
    Return True if user is authenticated and not soft-deleted.
    Compatibility with Django's User.is_authenticated.
    """
    return not self.is_deleted  # Si un champ is_deleted existe
```

### AC6: Tests de cohérence ajoutés

**Given** les corrections des AC1 à AC5
**When** les tests sont exécutés
**Then** des tests unitaires valident :
- La normalisation de tags est identique dans `models.py` et `services.py` (AC1)
- L'audit capture le `user_id` réel quand un utilisateur est présent (AC3)
- Les helper methods `is_admin_bool()`, `is_auditor_bool()` fonctionnent (AC4)
- Les collisions de hash MD5 sont détectées en développement (AC2, si Option B)

## Tasks / Subtasks

- [x] Task 1: Valider et tester la normalisation de tags (AC1)
  - [x] 1.1 Auditer tous les usages de `normalize_tag_name()` dans le code
  - [x] 1.2 Vérifier que `_sync_tags()` utilise la même logique — remplacé par appel à `normalize_tag_name()`
  - [x] 1.3 Ajouter un test unitaire pour garantir la cohérence (espaces → underscore)
  - [x] 1.4 Documenter la convention de normalisation dans `catalog/models.py` (docstring existante)

- [x] Task 2: Fiabiliser ou documenter le hash MD5 pour audit (AC2)
  - [x] 2.1 Analyser le volume de catalogues et la probabilité de collision — <1000 codes, ~0.0005%
  - [x] 2.2 Décider entre Option A (compteur/UUID) et Option B (documenter) — Option B retenue
  - [x] 2.3 N/A (Option B choisie)
  - [x] 2.4 Option B : documenté dans `signals.py` + test détection collision ajouté
  - [x] 2.5 Commentaire enrichi dans `integrations/signals.py:39-44`

- [x] Task 3: Capturer le user_id réel dans les signals d'audit (AC3)
  - [x] 3.1 Pas besoin de `django-crum` — implémenté via thread-local dans `core/middleware.py`
  - [x] 3.2 `CorrelationIdMiddleware` enrichi pour stocker `current_user` dans thread-local
  - [x] 3.3 `_get_user_id_from_context()` utilise désormais `get_current_user()` du middleware
  - [x] 3.4 Test : `TestAuditUserIdCapture.test_returns_user_id_when_authenticated`
  - [x] 3.5 Test : `TestAuditUserIdCapture.test_returns_system_when_no_user`

- [x] Task 4: Ajouter helper methods pour IntegerField booléens (AC4)
  - [x] 4.1 Ajouté `@property is_admin_bool(self)` dans `Profile`
  - [x] 4.2 Ajouté `@property is_auditor_bool(self)` dans `Profile`
  - [x] 4.3 Ajouté `@property is_active_bool(self)` dans `RecurringPattern`
  - [x] 4.4 Corrigé truthiness → `== 1` dans `executions/services.py:937` et `executions/views/scheduled_views.py:289`
  - [x] 4.5 Tests unitaires ajoutés : `TestProfileBooleanHelpers` + `TestRecurringPatternBooleanHelper`

- [x] Task 5: Documenter User.is_authenticated (AC5)
  - [x] 5.1 Vérifié : aucun soft-delete sur User, désactivation gérée au niveau AD/SAML
  - [x] 5.2 Non nécessaire — pas de soft-delete, attribut de classe reste correct
  - [x] 5.3 Commentaire enrichi : explique SAML 2.0, AnonymousUser, absence soft-delete
  - [x] 5.4 Tests ajoutés : `TestUserIsAuthenticated` (class attr, instance, no soft-delete field)

- [x] Task 6: Ajouter tests de cohérence (AC6)
  - [x] 6.1 Test : normalisation tags identique dans models et services (`TestSyncTagsUsesNormalization`)
  - [x] 6.2 Test : audit capture user_id réel (`TestAuditUserIdCapture.test_returns_user_id_when_authenticated`)
  - [x] 6.3 Test : audit fallback 'system' (`TestAuditUserIdCapture.test_returns_system_when_no_user`)
  - [x] 6.4 Test : helper methods booléens (`TestProfileBooleanHelpers` + `TestRecurringPatternBooleanHelper`)
  - [x] 6.5 Test : détection collision hash MD5 (`TestMD5HashCollisionDetection`)

## Dev Notes

### Contexte architecture

**Base de données Oracle :**
- Les champs booléens natifs n'existent pas en Oracle → `IntegerField` avec CHECK constraint (0, 1)
- Les migrations utilisent Flyway (voir `django_backend/migrations/`)
- Le projet utilise Django ORM avec Oracle backend

**Audit trail SOC1 :**
- Tous les changements critiques doivent être audités avec `user_id`, `correlation_id`, `entity_id`
- L'audit est append-only (immutable) pour la conformité
- Les signals Django (`post_save`) sont utilisés pour capturer les changements

**Normalisation des tags :**
- Convention actuelle : lowercase, strip, espaces → underscore
- Utilisée pour la recherche et le filtrage par tags dans le catalogue
- Les tags sont stockés dans une table dédiée `TAG` avec relation M2M via `ACTION_TAG`

### Fichiers impactés

**Backend Django :**
- `catalog/models.py` — Modèle Tag, normalize_tag_name()
- `catalog/services.py` — CatalogService._sync_tags()
- `integrations/signals.py` — Audit signals avec hash MD5
- `profiles/models.py` — Profile (is_admin, is_auditor IntegerField)
- `executions/models.py` — RecurringPattern (is_active IntegerField)
- `idp_auth/models.py` — User (is_authenticated class attribute)

**Migrations potentielles :**
- Si AC2 Option A : migration pour changer `entity_id` des audit logs existants
- Si AC4 : pas de migration nécessaire (helper methods uniquement)

### Testing standards

**Tests unitaires :**
- `catalog/tests/test_models.py` — Test normalize_tag_name()
- `catalog/tests/test_services.py` — Test _sync_tags()
- `integrations/tests/test_signals.py` — Test audit user_id capture
- `profiles/tests/test_models.py` — Test helper methods booléens
- `executions/tests/test_models.py` — Test is_active_bool

**Tests d'intégration :**
- Créer un tag via API admin → vérifier normalisation
- Modifier un catalogue via admin authentifié → vérifier user_id dans audit
- Requête avec user soft-deleted → vérifier is_authenticated

**Couverture minimale attendue :** 90%+ pour les nouveaux helper methods et validations

### Références techniques

**Django-crum (Current Request User Middleware) :**
- Documentation : https://github.com/ninemoreminutes/django-crum
- Permet de récupérer l'utilisateur courant dans n'importe quel contexte (signals, services)

**Oracle IntegerField pour booléens :**
- Pattern courant pour Oracle : https://docs.djangoproject.com/en/5.0/ref/databases/#using-a-custom-manager-with-an-integer-field
- Alternative : `django.db.models.BooleanField` avec backend Oracle traduit en NUMBER(1)

**Hash MD5 collisions :**
- Probabilité de collision pour N=1000 codes avec hash tronqué 8 hex modulo 10^9 : ~0.0005%
- Si le volume reste faible (<10,000), acceptable avec documentation
- Au-delà, recommandé de migrer vers UUID ou compteur séquentiel

### Learnings from previous stories

**Story 30.10 (Code mort) :**
- Les imports backward-compatibilité doivent être documentés explicitement
- Les dépréciations doivent être retirées progressivement avec migration path claire

**Story 30.3 (Bugs backend) :**
- Les validations silencieuses (pass sans raise) causent des bugs subtils
- Préférer lever des exceptions explicites avec logging structlog

**Story 22.1 (CRIT-1 get_profiles_by_ad_groups) :**
- Les usages de `filter()` avec Q objects doivent être testés pour case-insensitivity
- Les tests doivent couvrir les edge cases (DN, short name, profile code)

### Project Structure Notes

**Alignment avec structure unifiée :**
- Les tests sont dans `<app>/tests/test_<module>.py`
- Les migrations sont gérées par Flyway (pas Django migrations natives)
- Les services métier sont dans `<app>/services.py`
- Les signals d'audit sont dans `<app>/signals.py`

**Detected conflicts ou variances :**
- Aucune variance détectée pour cette story
- La structure du projet est respectée

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#12-incohérences-modèles-&-serializers]
- [Source: _bmad-output/planning-artifacts/epic-30-codebase-review-corrections-fev-2026.md#story-30.12]
- [Source: django_backend/catalog/models.py:51-58]
- [Source: django_backend/catalog/services.py:173-192]
- [Source: django_backend/integrations/signals.py:18-26, 39-40]
- [Source: django_backend/profiles/models.py:106-107]
- [Source: django_backend/executions/models.py:469]
- [Source: django_backend/idp_auth/models.py:65-67]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- 30/30 tests story passent
- 24/24 tests régression (catalog/models, integrations/signals, profiles/models) passent
- 316/318 core tests passent (2 échecs pré-existants dans test_bug_be3_integration_logs.py — redirect 301, non liés)

### Completion Notes List

- **AC1** : `_sync_tags()`, `add_tags()`, `remove_tags()` dans `catalog/services.py` utilisent désormais `normalize_tag_name()` au lieu de dupliquer la logique. 12 tests valident la cohérence.
- **AC2** : Option B retenue — hash MD5 tronqué documenté dans `signals.py` avec justification probabiliste. Test de détection de collision sur les 9 codes connus (aucune collision).
- **AC3** : Implémenté sans dépendance externe (pas de `django-crum`). `get_current_user()` / `set_current_user()` ajoutés dans `core/middleware.py` avec thread-local. `CorrelationIdMiddleware` stocke l'utilisateur authentifié. `_get_user_id_from_context()` dans `signals.py` récupère le user réel, fallback 'system' pour fixtures/Celery.
- **AC4** : `is_admin_bool`, `is_auditor_bool` (Profile) et `is_active_bool` (RecurringPattern) ajoutés. Corrigé 2 usages truthiness dans `executions/services.py` et `executions/views/scheduled_views.py`.
- **AC5** : Commentaire enrichi sur `User.is_authenticated` — explique SAML 2.0, AnonymousUser, absence de soft-delete. Confirmé : aucun champ `is_deleted`/`deleted_at` sur User. Test validé.
- **AC6** : 30 tests consolidés dans `tests/test_story_30_12_inconsistencies.py`.

### Change Log

- 2026-02-16: Story 30.12 — INCON-1 à INCON-5 corrigés, 30 tests ajoutés, 0 régression
- 2026-02-16: Code review — 7 issues fixés (3 HIGH + 3 MEDIUM + 1 LOW), 122 tests passent

### File List

- `idp-portal/django_backend/catalog/services.py` — Remplacé normalisation inline par `normalize_tag_name()` (3 endroits)
- `idp-portal/django_backend/integrations/signals.py` — `_get_user_id_from_context()` utilise `get_current_user()`, documentation hash MD5 enrichie (MEDIUM-2)
- `idp-portal/django_backend/core/middleware.py` — Ajouté `get_current_user()`, `set_current_user()`, stockage user dans `CorrelationIdMiddleware`
- `idp-portal/django_backend/profiles/models.py` — Ajouté `is_admin_bool`, `is_auditor_bool` properties
- `idp-portal/django_backend/executions/models.py` — Ajouté `is_active_bool` property sur `RecurringPattern`
- `idp-portal/django_backend/executions/services.py` — Corrigé truthiness `pattern.is_active` → `== 1`
- `idp-portal/django_backend/executions/views/scheduled_views.py` — Corrigé `bool(rp.is_active)` → `== 1`
- `idp-portal/django_backend/idp_auth/models.py` — Commentaire enrichi `is_authenticated` (LOW-1)
- `idp-portal/django_backend/idp_auth/views.py` — **Code review HIGH-1** : Corrigé `is_auditor` truthiness → `== 1`
- `idp-portal/django_backend/tests/test_story_30_12_inconsistencies.py` — **Nouveau** : 30 tests (AC1-AC6), import `patch` supprimé (HIGH-2)
