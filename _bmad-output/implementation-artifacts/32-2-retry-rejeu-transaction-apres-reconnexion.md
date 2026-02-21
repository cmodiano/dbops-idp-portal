# Story 32.2 : Retry et rejeu de transaction après reconnexion

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que backend,
je veux après une reconnexion DB retenter l'opération métier (ou rejouer la transaction) de manière bornée,
afin que l'appelant (portail ou API) obtienne un succès sans avoir à rejouer la requête manuellement.

## Acceptance Criteria

1. **Given** une requête métier en cours (transaction ou opération service)
   **When** la connexion DB est perdue puis rétablie
   **Then** le backend retente l'opération selon une politique configurée (nombre max de retries, backoff exponentiel)

2. **Given** une opération en écriture (POST, PUT, PATCH, DELETE)
   **When** elle est retentée après coupure
   **Then** elle est conçue pour être **idempotente** : pas de double écriture, pas de double audit, pas de double notification
   **And** les opérations en lecture (GET, HEAD, OPTIONS) sont toujours retentables sans risque

3. **Given** les retries épuisés (nombre max atteint OU fenêtre temporelle dépassée)
   **Then** une erreur explicite est retournée : **HTTP 503** avec code `DB_UNAVAILABLE`, message clair en français, et header `Retry-After`
   **And** l'appel n'est jamais laissé en attente indéfinie

4. **Given** la politique de retry
   **Then** les paramètres sont configurables via variables d'environnement : `DB_RETRY_MAX_ATTEMPTS`, `DB_RETRY_BACKOFF_BASE`
   **And** les valeurs par défaut sont documentées

5. **Given** les tests
   **Then** ils valident : succès après retry (reconnexion au 2ème essai), échec après N retries épuisés, idempotence d'un POST retenté, logging structuré des events retry

## Tasks / Subtasks

- [x] Task 1 — Ajouter paramètres retry configurables dans settings.py (AC #4)
  - [x] 1.1 Ajouter `DB_RETRY_MAX_ATTEMPTS` (défaut 3) et `DB_RETRY_BACKOFF_BASE` (défaut 0.5s) dans settings.py via `os.getenv()`
  - [x] 1.2 Mettre à jour `.env.example` et `.env.production.template`
  - [x] 1.3 Documenter dans `docs/db-resilience.md` (section retry)

- [x] Task 2 — Enrichir `DatabaseResilienceMiddleware` avec retry borné et backoff (AC #1, #3)
  - [x] 2.1 Remplacer le retry unique actuel par une boucle bornée (max `DB_RETRY_MAX_ATTEMPTS`)
  - [x] 2.2 Appliquer backoff exponentiel entre tentatives : `DB_RETRY_BACKOFF_BASE * 2^attempt` (cap à 5s)
  - [x] 2.3 Sur épuisement des retries, retourner `HttpResponse` 503 avec body JSON `{"error": {"code": "DB_UNAVAILABLE", "message": "Base de données temporairement indisponible après bascule. Veuillez réessayer."}}` et header `Retry-After: 30`
  - [x] 2.4 Logger chaque tentative : event `db_retry_attempt` avec `attempt_number`, `max_attempts`, `backoff_seconds`
  - [x] 2.5 Logger l'épuisement : event `db_retry_exhausted` avec `total_attempts`, `total_duration_ms`

- [x] Task 3 — Idempotence pour les requêtes en écriture (AC #2)
  - [x] 3.1 Distinguer requêtes lecture (GET, HEAD, OPTIONS) vs écriture (POST, PUT, PATCH, DELETE) dans le middleware
  - [x] 3.2 Pour les lectures : retry toujours autorisé (aucun effet de bord)
  - [x] 3.3 Pour les écritures : retry autorisé UNIQUEMENT si l'erreur survient AVANT le commit (la transaction est rollback automatiquement par Django)
  - [x] 3.4 Ajouter un check dans le middleware : si l'erreur est `InterfaceError` ou réseau (pas de réponse DB), la transaction n'a pas été commitée → retry safe
  - [x] 3.5 Si l'erreur survient pendant ou après un `COMMIT` (ORA-03113 mid-commit), NE PAS retenter → retourner 503 avec message « résultat incertain, vérifiez l'état »

- [x] Task 4 — Tests (AC #5)
  - [x] 4.1 Test succès au 2ème essai : mock 1 `OperationalError` puis succès
  - [x] 4.2 Test succès au 3ème essai : mock 2 erreurs puis succès
  - [x] 4.3 Test échec après N retries épuisés : mock N+1 erreurs → vérifie 503 + body JSON + Retry-After
  - [x] 4.4 Test backoff : vérifier les `time.sleep` appelés avec les bons intervalles
  - [x] 4.5 Test idempotence lecture : GET retenté sans condition
  - [x] 4.6 Test idempotence écriture : POST retenté si erreur pré-commit
  - [x] 4.7 Test écriture mid-commit : POST avec ORA-03113 mid-commit → pas de retry → 503
  - [x] 4.8 Test logging : vérifier events `db_retry_attempt`, `db_retry_exhausted` avec bons attributs
  - [x] 4.9 Test settings : vérifier que `DB_RETRY_MAX_ATTEMPTS` et `DB_RETRY_BACKOFF_BASE` sont lus depuis settings
  - [x] 4.10 Test rétrocompatibilité : vérifier que les tests existants de 32.1 passent toujours

- [x] Task 5 — Mise à jour documentation (AC #4)
  - [x] 5.1 Enrichir `docs/db-resilience.md` : section retry (politique, backoff, idempotence, bornes)
  - [x] 5.2 Ajouter diagramme de séquence (texte) : requête → erreur → retry → succès/503

## Dev Notes

### Contexte critique — Ce qui existe déjà (Story 32.1)

**Middleware actuel** `core/db_resilience.py` :
- `DatabaseResilienceMiddleware` intercepte `OperationalError`, `InterfaceError`, `DatabaseError`
- `_is_connection_error()` vérifie 11 codes ORA + 5 patterns textuels
- Actuellement : **retry unique** (1 seule tentative après `close_old_connections()`)
- Le commentaire ligne 129 mentionne explicitement que Story 32.2 ajoute le retry transactionnel avec idempotence
- Position middleware : après `CorrelationIdMiddleware`, avant `RequestResponseLoggingMiddleware`

**Ce qu'il faut modifier vs créer :**
- `core/db_resilience.py` : MODIFIER — enrichir le middleware existant (pas créer un nouveau)
- `idp_backend/settings.py` : MODIFIER — ajouter 2 settings
- `core/tests/test_db_resilience.py` : MODIFIER — ajouter tests retry (37 tests existants à préserver)

### Architecture du retry — Approche middleware (PAS décorateur)

Le retry doit rester **dans le middleware existant**, pas dans un décorateur applicatif. Raisons :
1. Le middleware intercède déjà les erreurs DB (Story 32.1) — on étend sa logique
2. Couverture universelle : TOUTES les vues sont protégées automatiquement
3. Le retry applicatif (ex. Celery `retry_workflow_step`) est un niveau différent (retry métier, pas retry DB)
4. NE PAS utiliser `tenacity` ou `backoff` — `time.sleep()` simple suffit dans le middleware

### Idempotence — Approche pragmatique

Django utilise `@transaction.atomic()` dans les vues DRF. Si une erreur DB survient :
- **Avant le COMMIT** : la transaction est rollback automatiquement → le retry est safe car rien n'a été persisté
- **Pendant le COMMIT** (rare) : état incertain → NE PAS retenter, retourner 503
- **Après le COMMIT** : la requête a réussi côté DB, l'erreur est dans le retour → le retry serait une double écriture → NE PAS retenter

Détection pratique :
- `InterfaceError` = connexion morte = pré-commit → retry safe
- `OperationalError` avec ORA-03113/03114 = peut être mid-commit → vérifier si `connection.in_atomic_block` est True
- Si `connection.in_atomic_block` est False après l'erreur = l'atomic block a été nettoyé = pré-commit → retry safe

### Réponse 503 — Format standardisé

Utiliser le même format d'erreur que `custom_exception_handler` dans `core/exceptions.py` :
```json
{
  "error": {
    "code": "DB_UNAVAILABLE",
    "message": "Base de données temporairement indisponible après bascule. Veuillez réessayer dans quelques instants.",
    "correlation_id": "abc-123"
  }
}
```
Header `Retry-After: 30` (30 secondes — typique pour Data Guard FSFO < 1 min).

**ATTENTION** : Le middleware retourne un `HttpResponse` brut (pas `Response` DRF) car il est avant DRF dans la pile. Utiliser `django.http.JsonResponse` avec `status=503`.

### Backoff exponentiel

- Tentative 1 : immédiate (comme actuellement)
- Tentative 2 : `sleep(0.5s)` (DB_RETRY_BACKOFF_BASE)
- Tentative 3 : `sleep(1.0s)` (0.5 * 2^1)
- Cap à 5s pour éviter les timeouts gunicorn (30s par défaut)

### Fichiers à modifier

| Fichier | Action | Détails |
|---------|--------|---------|
| `core/db_resilience.py` | MODIFIER | Boucle retry, backoff, idempotence, réponse 503 |
| `idp_backend/settings.py` | MODIFIER | Ajouter `DB_RETRY_MAX_ATTEMPTS`, `DB_RETRY_BACKOFF_BASE` |
| `core/tests/test_db_resilience.py` | MODIFIER | Ajouter ~10 tests retry (préserver les 37 existants) |
| `docs/db-resilience.md` | MODIFIER | Section retry, backoff, idempotence |
| `.env.example` | MODIFIER | Ajouter 2 variables |
| `.env.production.template` | MODIFIER | Ajouter 2 variables |

### Patterns à suivre

**Logging structlog** (conventions `docs/logging-conventions.md`) :
- Event names snake_case : `db_retry_attempt`, `db_retry_exhausted`
- Inclure `correlation_id`, `method`, `path`, `attempt_number`, `max_attempts`
- WARNING pour tentative, ERROR pour épuisement

**Settings pattern** (existant dans settings.py) :
```python
DB_RETRY_MAX_ATTEMPTS = int(os.getenv('DB_RETRY_MAX_ATTEMPTS', '3'))
DB_RETRY_BACKOFF_BASE = float(os.getenv('DB_RETRY_BACKOFF_BASE', '0.5'))
```

**Tests pattern** (existant dans test_db_resilience.py) :
- Classe `TestDatabaseResilienceMiddleware` avec `setUp` créant middleware + mock get_response
- Mock `close_old_connections`, `connection.ensure_connection`
- Assertions sur response status, structlog events

### Anti-patterns — NE PAS FAIRE

- **NE PAS** créer un décorateur `@db_retry` séparé — le retry est dans le middleware
- **NE PAS** utiliser `tenacity` ou `backoff` — surcharge inutile pour 3 retries
- **NE PAS** retenter les erreurs de logique SQL (constraint violation, syntax error) — seules les erreurs de connexion sont retentables
- **NE PAS** retenter si le request body a déjà été consommé et n'est plus lisible — Django bufferise le body donc ce n'est pas un problème
- **NE PAS** confondre retry DB (cette story) avec retry Celery (`executions/tasks.py:retry_workflow_step`) — ce sont deux niveaux différents
- **NE PAS** ajouter de `time.sleep()` pour la première tentative — elle est immédiate

### Dépendances

- **Dépend de** Story 32.1 (détection + reconnexion) — DONE ✅
- **Aucune nouvelle dépendance Python** — tout est natif Django + time.sleep
- Stories 32.3 et 32.4 étendent le comportement défini ici

### Project Structure Notes

- Backend Django : `idp-portal/django_backend/`
- Settings : `idp_backend/settings.py` (lignes 123-129 pour DB resilience config)
- Middleware stack : `idp_backend/settings.py` (ligne 76 pour DatabaseResilienceMiddleware)
- Core app : `core/` — db_resilience.py, exceptions.py, middleware.py
- Tests runner : `.venv/bin/python -m pytest` avec `idp_backend.test_settings`
- Tests existants : `core/tests/test_db_resilience.py` (37 tests, tous passent)

### References

- [Source: planning-artifacts/epic-32-resilience-dataguard.md — Story 32.2]
- [Source: core/db_resilience.py — Middleware actuel (152 lignes), retry unique à enrichir]
- [Source: core/db_resilience.py:127-131 — Commentaire explicitant que Story 32.2 ajoute le retry transactionnel]
- [Source: idp_backend/settings.py:123-129 — Settings DB resilience (CONN_MAX_AGE, CONN_HEALTH_CHECKS)]
- [Source: core/exceptions.py — ServiceUnavailableError, custom_exception_handler, format d'erreur standard]
- [Source: core/tests/test_db_resilience.py — 37 tests existants à préserver]
- [Source: docs/db-resilience.md — Documentation résilience DB à enrichir]
- [Source: 32-1-detection-reconnexion-base-donnees-failover.md — Story précédente, insights et patterns établis]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- ✅ Task 1 : Settings `DB_RETRY_MAX_ATTEMPTS` (défaut 3) et `DB_RETRY_BACKOFF_BASE` (défaut 0.5) ajoutés dans settings.py, .env.example, .env.production.template
- ✅ Task 2 : Middleware enrichi — boucle retry bornée avec backoff exponentiel (cap 5s), réponse 503 JsonResponse avec `DB_UNAVAILABLE`, `Retry-After: 30`, et `correlation_id`
- ✅ Task 3 : Idempotence implémentée — `_is_mid_commit_error()` et `_is_retry_safe()` distinguent lecture (toujours safe), écriture pré-commit (safe via InterfaceError ou in_atomic_block=True), écriture mid-commit (503 immédiat avec message « résultat incertain »)
- ✅ Task 4 : 66 tests passent (37 existants mis à jour + 29 nouveaux) couvrant : succès 2ème/3ème essai, épuisement retries → 503, backoff timing, idempotence GET/POST, mid-commit POST → 503, logging db_retry_attempt/db_retry_exhausted, settings configurables, rétrocompatibilité 32.1
- ✅ Task 5 : Documentation `docs/db-resilience.md` enrichie — section retry (politique, backoff, idempotence), diagramme de séquence texte, tableau événements structlog, variables d'environnement documentées

### File List

- `idp-portal/django_backend/core/db_resilience.py` — MODIFIED: boucle retry bornée, backoff exponentiel, idempotence, réponse 503
- `idp-portal/django_backend/idp_backend/settings.py` — MODIFIED: ajout DB_RETRY_MAX_ATTEMPTS et DB_RETRY_BACKOFF_BASE
- `idp-portal/django_backend/core/tests/test_db_resilience.py` — MODIFIED: 37→69 tests (32 nouveaux pour retry, backoff, idempotence, logging, settings, PATCH, mid-commit during retry)
- `idp-portal/django_backend/docs/db-resilience.md` — MODIFIED: section retry, diagramme séquence, variables d'environnement
- `idp-portal/django_backend/.env.example` — MODIFIED: ajout DB_RETRY_MAX_ATTEMPTS, DB_RETRY_BACKOFF_BASE
- `idp-portal/django_backend/.env.production.template` — MODIFIED: ajout DB_RETRY_MAX_ATTEMPTS, DB_RETRY_BACKOFF_BASE

## Change Log

- 2026-02-21: Story 32.2 implémentée — retry borné avec backoff exponentiel, idempotence écriture, réponse 503 structurée, 66 tests passent
- 2026-02-21: Code review adversarial — 7 issues (1 HIGH + 4 MEDIUM + 2 LOW), 5 auto-fixées (H1: ora_code périmé dans db_retry_exhausted, M1: log ensure_connection failure, M2: duplication log db_retry_attempt, M3: test PATCH retry, M4: test mid-commit during retry), 69 tests passent
