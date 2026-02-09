# Story 22.16: Corriger MED-3/MED-4 — Cache feature flags (thundering herd + clé source)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux renforcer le cache des feature flags avec lock anti-thundering herd et clé incluant la source,
afin d'éviter les pics de charge DB et les incohérences lors du changement de source.

## Acceptance Criteria

1. **Given** le cache des feature flags expire
   **When** plusieurs requêtes concurrentes tentent de charger depuis la DB
   **Then** un lock/mutex empêche les chargements multiples simultanés
   **And** seule la première requête charge depuis la DB, les autres attendent

2. **Given** le cache utilise une clé unique
   **When** la configuration est inspectée
   **Then** la clé de cache inclut la source (`env` ou `database`)
   **And** `'feature_flags:all'` devient `'feature_flags:all:env'` ou `'feature_flags:all:database'`

3. **Given** un changement de `FEATURE_FLAGS_SOURCE` survient
   **When** l'application redémarre ou la configuration change
   **Then** le cache de l'ancienne source n'est pas retourné
   **And** les anciennes valeurs sont automatiquement invalidées ou ignorées

4. **Given** plusieurs requêtes concurrentes arrivent pendant un cache miss
   **When** `_get_all_flags()` est appelé simultanément
   **Then** un seul chargement DB est effectué (verrou bloque les autres)
   **And** les autres requêtes reçoivent le résultat du premier chargement

5. **Given** le timeout du lock est configuré
   **When** une requête bloque trop longtemps
   **Then** un timeout de 5 secondes (configurable) permet aux autres de continuer
   **And** un log WARNING est émis si le timeout est atteint

6. **Given** les tests de charge simulent des requêtes concurrentes
   **When** 20 requêtes concurrentes arrivent pendant un cache miss
   **Then** exactement 1 appel DB est effectué (vérifié par mock ou compteur)
   **And** les 20 requêtes reçoivent le même résultat
   **And** le temps total est < 200ms (pas de cascade de chargements)

7. **Given** la source change de `database` vers `env`
   **When** `_get_all_flags()` est appelé après le changement
   **Then** les flags de l'ancienne source (`database`) ne sont pas retournés
   **And** les nouveaux flags de `env` sont chargés et mis en cache avec la nouvelle clé

## Tasks / Subtasks

- [x] Task 1: Analyser le problème thundering herd dans `_get_all_flags()` (AC: #1, #4)
  - [x] 1.1: Reproduire le problème avec un test concurrent (20 threads, cache expiré)
  - [x] 1.2: Vérifier combien d'appels DB sont effectués sans lock (attendu: 20)
  - [x] 1.3: Documenter le risque sur performance DB en production

- [x] Task 2: Implémenter un lock basé sur Django cache pour anti-thundering herd (AC: #1, #4, #5)
  - [x] 2.1: Créer une fonction `_acquire_cache_lock(key, timeout=5)` dans `feature_flags.py`
  - [x] 2.2: Utiliser `cache.add('lock:{key}', True, timeout)` comme mécanisme de lock
  - [x] 2.3: Modifier `_get_all_flags()` pour acquérir le lock avant chargement DB
  - [x] 2.4: Implémenter une boucle de retry avec backoff pour les requêtes bloquées
  - [x] 2.5: Logger un WARNING si le timeout est atteint

- [x] Task 3: Inclure la source dans la clé de cache (AC: #2, #3, #7)
  - [x] 3.1: Modifier `_get_all_flags()`: clé `'feature_flags:all:{source}'` au lieu de `'feature_flags:all'`
  - [x] 3.2: Modifier `_get_flag_config()`: clé `'feature_flag:{flag_key}:{source}'`
  - [x] 3.3: Modifier `invalidate_cache()`: invalider les deux sources si `flag_key is None`

- [x] Task 4: Ajouter tests unitaires pour le lock anti-thundering herd (AC: #4, #6)
  - [x] 4.1: Créer `core/tests/test_feature_flags_cache.py`
  - [x] 4.2: Test `test_thundering_herd_prevention` — 20 threads concurrents, 1 seul appel DB
  - [x] 4.3: Test `test_lock_timeout` — vérifier que le timeout fonctionne
  - [x] 4.4: Test `test_concurrent_requests_same_result` — toutes les requêtes reçoivent le même résultat

- [x] Task 5: Ajouter tests pour la clé de cache incluant la source (AC: #2, #3, #7)
  - [x] 5.1: Test `test_cache_key_includes_source_env` — vérifier clé avec source=env
  - [x] 5.2: Test `test_cache_key_includes_source_database` — vérifier clé avec source=database
  - [x] 5.3: Test `test_source_change_invalidates_old_cache` — changer source, vérifier nouvelle clé
  - [x] 5.4: Mocké `settings.FEATURE_FLAGS_SOURCE` pour chaque test

- [x] Task 6: Documentation et validation finale (AC: tous)
  - [x] 6.1: Documenter le pattern anti-thundering herd dans docstring `_get_all_flags()`
  - [x] 6.2: Ajouter commentaire expliquant le format de clé avec source
  - [x] 6.3: Exécuter tous les tests backend feature flags
  - [x] 6.4: Vérifier que les tests Story 17.12 passent toujours (non-régression)

## Dev Notes

### Contexte du problème (MED-3 et MED-4)

**Diagnostic de l'évaluation qualité de code (2026-02-08):**

**MED-3 — Cache des feature flags : thundering herd**
- **Fichier concerné:** `core/feature_flags.py:67-82` (fonction `_get_all_flags()`)
- **Constat:** Quand le cache expire, toutes les requêtes concurrentes chargent simultanément depuis la base. Pas de lock/mutex.
- **Impact:** Pic de charge DB à chaque expiration de cache en haute charge (toutes les 5 minutes par défaut).
- **Scénario critique:** 50 requêtes HTTP simultanées → 50 requêtes SQL `SELECT * FROM FEATURE_FLAGS` simultanées.
- **Correction:** Utiliser un lock basé sur le cache Django (`cache.add()` atomique) pour n'autoriser qu'un seul chargement.

**MED-4 — Clé de cache feature flags ne tient pas compte de la source**
- **Fichier concerné:** `core/feature_flags.py:26-29, 74-78`
- **Constat:** La clé de cache ne distingue pas les sources `env` et `database`. Un changement de `FEATURE_FLAGS_SOURCE` sans purge de cache renvoie les anciennes valeurs.
- **Scénario problématique:**
  1. Application démarre avec `FEATURE_FLAGS_SOURCE=database`
  2. Flags chargés et mis en cache avec clé `'feature_flags:all'`
  3. Configuration change vers `FEATURE_FLAGS_SOURCE=env` (redémarrage)
  4. Premier appel retourne le cache (flags de l'ancienne source `database`)
  5. Incohérence : flags de la DB alors que la source est `env`
- **Correction:** Inclure la source dans la clé de cache.

### Code actuel problématique

```python
# core/feature_flags.py:88-103 (actuel, PROBLÉMATIQUE)
def _get_all_flags():
    """Get all flags from configured source, with caching."""
    cache_key = 'feature_flags:all'  # ❌ MED-4: Pas de source dans la clé
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    source = _get_flags_source()
    if source == 'database':
        flags = _load_flags_from_database()  # ❌ MED-3: Chargement concurrent sans lock
    else:
        flags = _load_flags_from_env()

    cache.set(cache_key, flags, _get_cache_ttl())
    logger.debug("feature_flag_cache_miss", source=source, flag_count=len(flags))
    return flags
```

**Problème MED-3 (thundering herd):**
- Ligne 90-91: `cache.get()` retourne `None` si expiré
- Lignes 95-98: Chargement depuis DB/env sans protection
- Si 50 requêtes arrivent en même temps pendant un cache miss, les 50 chargent depuis la DB simultanément

**Problème MED-4 (clé sans source):**
- Ligne 89: Clé `'feature_flags:all'` ne distingue pas `env` vs `database`
- Si source change de `database` → `env`, le cache retourne les anciens flags de `database`

### Solution proposée

#### Pattern anti-thundering herd avec Django cache

```python
import time
from django.core.cache import cache

def _acquire_cache_lock(lock_key, timeout=5):
    """
    Acquire a distributed lock using Django cache.

    Args:
        lock_key: Cache key for the lock
        timeout: Lock timeout in seconds (default: 5)

    Returns:
        bool: True if lock acquired, False otherwise
    """
    # cache.add() est atomique et retourne False si la clé existe déjà
    return cache.add(lock_key, True, timeout)


def _get_all_flags():
    """Get all flags from configured source, with caching and lock."""
    source = _get_flags_source()
    cache_key = f'feature_flags:all:{source}'  # ✅ MED-4: Clé inclut la source
    lock_key = f'{cache_key}:lock'

    # Vérifier le cache avant d'acquérir le lock
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # ✅ MED-3: Acquérir le lock pour éviter le thundering herd
    if _acquire_cache_lock(lock_key, timeout=5):
        # Premier thread: charger depuis la source
        try:
            if source == 'database':
                flags = _load_flags_from_database()
            else:
                flags = _load_flags_from_env()

            cache.set(cache_key, flags, _get_cache_ttl())
            logger.debug("feature_flag_cache_miss", source=source, flag_count=len(flags))
            return flags
        finally:
            # Libérer le lock
            cache.delete(lock_key)
    else:
        # Threads suivants: attendre que le premier charge, puis récupérer du cache
        max_wait = 5  # secondes
        start_time = time.time()
        while time.time() - start_time < max_wait:
            time.sleep(0.05)  # 50ms entre chaque tentative
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        # Timeout atteint: log warning et charger quand même
        logger.warning("feature_flag_lock_timeout", cache_key=cache_key)
        # Fallback: charger sans lock (mieux que de fail)
        if source == 'database':
            return _load_flags_from_database()
        else:
            return _load_flags_from_env()
```

**Avantages de cette approche:**
1. **Anti-thundering herd:** Un seul chargement DB même avec 100 requêtes concurrentes
2. **Clé avec source:** Changement de source = nouveau cache, pas d'incohérence
3. **Graceful degradation:** Si lock timeout, on charge quand même (disponibilité > cohérence)
4. **Django-natif:** Pas de dépendance Redis Lock externe, utilise le cache Django configuré

### Architecture et contraintes techniques

**Stack:**
- Backend: Django 5.2 + DRF 3.16, Oracle DB
- Cache: Django cache framework (settings: `django.core.cache.backends.locmem.LocMemCache` en dev, Redis en prod)
- Feature flags: Story 17.12 — Source env ou database, rollout %, cache 5 min

**Contraintes:**
- **Performance:** Réduire les appels DB en haute charge (actuellement: O(n) appels pour n requêtes concurrentes)
- **Cohérence:** Garantir que la source du cache correspond à `FEATURE_FLAGS_SOURCE`
- **Disponibilité:** Si lock échoue, fallback vers chargement (pas de blocage total)

**Configuration actuelle:**
```python
# idp_backend/settings.py
FEATURE_FLAGS_SOURCE = 'env'  # ou 'database'
FEATURE_FLAGS_CACHE_TTL = 300  # 5 minutes
FEATURE_FLAGS_ENABLED = True
```

### Fichiers à modifier

**Backend:**
1. `core/feature_flags.py` — Ajouter `_acquire_cache_lock()`, modifier `_get_all_flags()` et `_get_flag_config()`
2. `core/tests/test_feature_flags_cache.py` — Nouveau fichier de tests

**Tests non-régression:**
3. `core/tests/test_feature_flags.py` — Tests existants de Story 17.12 (doivent tous passer)

### Testing standards

**Tests unitaires à créer:**

1. **test_thundering_herd_prevention** (AC: #4, #6)
   - Simuler 20 threads concurrents appelant `_get_all_flags()`
   - Mock `_load_flags_from_database()` avec compteur d'appels
   - Vider le cache avant le test
   - Assert: exactement 1 appel à `_load_flags_from_database()`

2. **test_cache_key_includes_source_env** (AC: #2)
   - Mock `settings.FEATURE_FLAGS_SOURCE = 'env'`
   - Appeler `_get_all_flags()`
   - Vérifier que la clé est `'feature_flags:all:env'`

3. **test_cache_key_includes_source_database** (AC: #2)
   - Mock `settings.FEATURE_FLAGS_SOURCE = 'database'`
   - Appeler `_get_all_flags()`
   - Vérifier que la clé est `'feature_flags:all:database'`

4. **test_source_change_invalidates_old_cache** (AC: #3, #7)
   - Charger flags avec `source='database'`
   - Vérifier cache avec clé `'feature_flags:all:database'`
   - Changer `settings.FEATURE_FLAGS_SOURCE = 'env'`
   - Appeler `_get_all_flags()`
   - Assert: nouvelle clé `'feature_flags:all:env'`, ancienne clé ignorée

5. **test_lock_timeout** (AC: #5)
   - Acquérir le lock manuellement (bloquer)
   - Appeler `_get_all_flags()` (doit attendre)
   - Assert: timeout de 5 secondes, log WARNING émis

**Commandes de test:**
```bash
cd django_backend
.venv/bin/python -m pytest core/tests/test_feature_flags_cache.py -v
.venv/bin/python -m pytest core/tests/test_feature_flags.py -v  # Non-régression
```

### Learnings from previous stories

**Story 22-15 (Timezone):** Forcer les comportements explicites, ne pas laisser les valeurs implicites.
→ Pour cette story: Rendre la source explicite dans la clé de cache, ne pas assumer qu'elle ne changera pas.

**Story 22-3 (Race condition token refresh):** Pattern mutex avec Promise pour éviter les appels concurrents.
→ Pour cette story: Même pattern, mais côté backend avec `cache.add()` comme verrou atomique.

**Story 17-12 (Feature flags):** Système de cache avec TTL, source env ou database.
→ Pour cette story: Renforcer le cache existant sans casser l'API publique (`is_enabled()`, `get_all_flags_status()`).

**Story 22-11 (Broad exception catches):** Utiliser des exceptions spécifiques, logger les cas d'erreur.
→ Pour cette story: Logger un WARNING si le timeout du lock est atteint, ne pas masquer l'erreur.

### Git intelligence

**Commits récents (derniers 10):**
```
c7ea29d fix(22-15): standardize timezone handling in datetime serialization
db52a6e fix(22-14): resolve stale closure bug in ExecutionsPage filters
407d548 feat(22-13): implement message-based WebSocket authentication
89c1839 fix(22-12): prevent PENDING_APPROVAL to SUBMITTED transition
795a58c refactor(22-11): replace broad exception catches with specific handlers
```

**Patterns observés:**
- Commits Epic 22 préfixés `fix(22-X)` ou `refactor(22-X)`
- Tests inclus dans le même commit
- Code review adversarial systématique
- Corrections appliquées dans le même commit ou un fix séparé

**Pour cette story:**
- Commit principal: `fix(22-16): prevent thundering herd and cache key collision in feature flags`
- Tests inclus dans le même commit
- Documentation inline dans le code

### Project Structure Notes

**Backend structure:**
- `core/feature_flags.py` — Service de feature flags (Story 17.12)
- `core/feature_flag_views.py` — API REST pour admin DBOPS
- `core/models.py` — Modèle `FeatureFlag` (DB source)
- `core/tests/test_feature_flags.py` — Tests existants (53 tests, tous passent)
- `core/tests/test_feature_flags_cache.py` — Nouveau fichier pour tests de cache

**Alignment avec unified project structure:**
- Tests dans `core/tests/` (convention Django)
- Pas de conflit détecté

### References

**Epic 22 — Source principale:**
- [Source: _bmad-output/planning-artifacts/epic-22-amelioration-qualite-code.md#Story 22.16]
  - Lignes 370-389: Acceptance Criteria détaillés
  - Ligne 373: "renforcer le cache des feature flags avec lock anti-thundering herd et clé incluant la source"

**Code Quality Assessment — Diagnostic:**
- [Source: idp-portal/code-quality-assessment-2026-02-08.md#Section 9.3 MED-3]
  - "Quand le cache expire, toutes les requêtes concurrentes chargent simultanément depuis la base. Pas de lock/mutex."
  - "Pic de charge DB à chaque expiration de cache en haute charge."

- [Source: idp-portal/code-quality-assessment-2026-02-08.md#Section 9.3 MED-4]
  - "La clé de cache ne distingue pas les sources `env` et `database`."
  - "Un changement de `FEATURE_FLAGS_SOURCE` sans purge de cache renvoie les anciennes valeurs."

**Feature flags — Implementation actuelle:**
- [Source: idp-portal/django_backend/core/feature_flags.py]
  - Lignes 88-103: `_get_all_flags()` — fonction à corriger
  - Lignes 106-119: `_get_flag_config()` — également affectée par la clé
  - Lignes 215-226: `invalidate_cache()` — à adapter pour les deux sources

**Story 17.12 — Context original:**
- Feature flags créés dans Story 17.12 (2026-02-07)
- 53 tests backend passent (17 unit + 36 integration)
- Système déjà en production avec cache 5 minutes

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 57/57 existing feature flags tests pass after cache key migration
- 14/14 new cache tests pass (7 thundering herd + 7 source key tests)
- 71/71 total feature flags tests pass

### Completion Notes List

- MED-3 fix: Added anti-thundering herd lock via `cache.add()` in `_get_all_flags()`. Lock holder loads from source and populates cache; other concurrent requests wait and read from cache. Timeout (3s, configurable via `FEATURE_FLAGS_LOCK_TIMEOUT`) with WARNING log and fallback load.
- MED-4 fix: Cache keys now include source — `feature_flags:all:env` / `feature_flags:all:database` and `feature_flag:{key}:env` / `feature_flag:{key}:database`. Source change = different key = no stale data.
- `invalidate_cache()` now clears both source variants to prevent stale data after source switch.
- Lock uses `time.monotonic()` (not `time.time()`) for monotonic clock safety.
- Lock released in `finally` block to prevent deadlock on exception.
- Existing test cache key references updated (`feature_flags:all` → `feature_flags:all:env`, etc.)
- No new dependencies introduced.

### Code Review Fixes Applied (2026-02-09)

**HIGH-1: Lock token race condition prevention**
- Lock now uses unique UUID token to prevent deleting another worker's lock
- `cache.delete(lock_key)` only executes if `cache.get(lock_key) == lock_token`
- Prevents race condition where lock expires, another worker acquires it, first worker deletes it

**HIGH-2: Reduced lock timeout from 5s to 3s**
- `DEFAULT_LOCK_TIMEOUT` reduced from 5s to 3s to minimize wait time if lock holder crashes
- Added separate `MAX_LOCK_WAIT` constant for clarity
- Faster recovery in case of worker crash while holding lock

**HIGH-3: Production cache backend validation**
- Added startup check in `core/startup_checks.py:validate_feature_flags_config()`
- Fails with `ImproperlyConfigured` if `FEATURE_FLAGS_SOURCE='database'` AND cache backend is `LocMemCache` in production
- Warns in dev mode about LocMemCache limitations (per-process locking only)
- LocMemCache does NOT provide inter-process locking required for multi-worker setups

**MED-1: Configuration documented and validated**
- Added `FEATURE_FLAGS_LOCK_TIMEOUT` to `settings.py` with documentation
- Added validation in `_get_lock_timeout()` to ensure timeout is positive number
- Added startup validation for `FEATURE_FLAGS_LOCK_TIMEOUT` env var

**MED-2: invalidate_cache() behavior documented**
- Added docstring note explaining that invalidating a specific flag also clears global 'all' cache
- Clarifies performance trade-off: any flag change forces full reload on next cache miss

**MED-3: Enhanced observability/metrics**
- Added structured logging for lock acquisition metrics:
  - `feature_flag_cache_miss_loaded` with `load_duration_ms`
  - `feature_flag_lock_wait_start` when entering wait loop
  - `feature_flag_lock_wait_success` with `wait_duration_ms` on successful wait
  - `feature_flag_lock_timeout` with `wait_duration_ms` on timeout
- Enables production monitoring of lock effectiveness and performance

**MED-4: Documentation improvements**
- Enhanced `_get_all_flags()` docstring with configuration example (Redis setup)
- Added CRITICAL note in module docstring about distributed cache requirement
- Documented lock timeout and cache backend requirements in settings.py

### Change Log

- 2026-02-09: Story 22.16 implemented — anti-thundering herd lock + source-aware cache keys (MED-3/MED-4 fixes)
- 2026-02-09: Code review fixes applied — lock token race condition, reduced timeout, production validation, enhanced observability

### File List

- `idp-portal/django_backend/core/feature_flags.py` — Modified: added lock mechanism with UUID token, source in cache keys, enhanced logging, updated invalidate_cache, reduced lock timeout to 3s
- `idp-portal/django_backend/core/tests/test_feature_flags.py` — Modified: updated cache key references to include source
- `idp-portal/django_backend/core/tests/test_feature_flags_cache.py` — New: 14 tests for thundering herd prevention and source-aware cache keys
- `idp-portal/django_backend/idp_backend/settings.py` — Modified: added FEATURE_FLAGS_LOCK_TIMEOUT configuration with documentation
- `idp-portal/django_backend/core/startup_checks.py` — Modified: added cache backend validation for database source, lock timeout validation
