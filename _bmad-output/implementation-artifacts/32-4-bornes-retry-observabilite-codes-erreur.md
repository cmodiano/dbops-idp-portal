# Story 32.4 : Bornes retry, observabilité et codes d'erreur explicites

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'opérateur ou développeur,
je veux que les retries soient bornés (nombre max, fenêtre temporelle), que les erreurs soient explicites et que les événements soient tracés (logs / métriques),
afin d'éviter des attentes infinies et de pouvoir diagnostiquer les incidents liés à la base.

## Acceptance Criteria

1. **Given** la politique de retry (32.1 / 32.2)
   **Then** le **nombre maximum de retries** et une **fenêtre temporelle** (ex. 2 min) sont configurables et documentés

2. **And** après épuisement, l'API retourne un **code d'erreur explicite** (ex. 503 Service Unavailable ou code métier dédié) avec un message clair (ex. « Base temporairement indisponible après bascule ; veuillez réessayer »)

3. **And** les événements (perte connexion, reconnexion, retry, échec après N retries) sont **loggés** (structlog ou équivalent) avec correlation_id si disponible

4. **And** optionnel : métriques (compteur reconnexions, retries, échecs) pour surveillance

5. **And** des tests vérifient les bornes et le format de réponse d'erreur

## Tasks / Subtasks

- [x] Task 1 — Ajouter la borne temporelle (time window) et documenter toutes les bornes (AC #1)
  - [x] 1.1 Ajouter `DB_RETRY_TIME_WINDOW_SECONDS` dans `settings.py` (défaut 120s = 2 min) avec commentaire
  - [x] 1.2 Implémenter la vérification dans `db_resilience.py` : si `total_duration_ms > DB_RETRY_TIME_WINDOW_SECONDS * 1000`, arrêter les retries et retourner 503 (même format que retry exhaustion)
  - [x] 1.3 Logger l'événement `db_retry_time_window_exceeded` avec `total_duration_ms`, `time_window_seconds`, `correlation_id`
  - [x] 1.4 Vérifier que `docs/db-resilience.md` mentionne `DB_RETRY_TIME_WINDOW_SECONDS` dans la table de configuration et dans la section "politique de retry"

- [x] Task 2 — Ajouter le champ `reason` dans la réponse 503 (AC #2)
  - [x] 2.1 Dans `_build_503_response()` (db_resilience.py), ajouter un paramètre `reason` (str) avec valeurs: `"retry_exhausted"`, `"time_window_exceeded"`, `"mid_commit_error"`
  - [x] 2.2 Enrichir la réponse JSON : `{"error": {"code": "DB_UNAVAILABLE", "reason": "<reason>", "message": "...", "correlation_id": "..."}}`
  - [x] 2.3 S'assurer que le message français est distinct selon la raison (voir section Dev Notes ci-dessous)

- [x] Task 3 — Vérifier et compléter les logs structurés (AC #3)
  - [x] 3.1 Vérifier que `db_retry_attempt` inclut bien `correlation_id`, `attempt_number`, `max_attempts`, `backoff_seconds`
  - [x] 3.2 Vérifier que `db_retry_exhausted` inclut `correlation_id`, `total_attempts`, `total_duration_ms`
  - [x] 3.3 Ajouter l'événement `db_retry_time_window_exceeded` si Task 1.3 non couvert
  - [x] 3.4 Vérifier que `db_connection_restored` log `total_duration_ms` et `attempt_number`

- [x] Task 4 — (Optionnel) Métriques Django/structlog pour surveillance (AC #4)
  - [ ] 4.1 ~~Dans `db_resilience.py`, ajouter des compteurs simples en mémoire (thread-safe via `threading.local` ou module-level `Counter`) si Prometheus n'est pas disponible~~ (alternative non retenue — option 4.3 choisie)
  - [ ] 4.2 ~~Exposer un endpoint `GET /api/v1/health/db-resilience-stats/` (admin only) retournant les compteurs en-session : `retry_total`, `success_total`, `failure_total`, `mid_commit_total`~~ (alternative non retenue — option 4.3 choisie)
  - [x] 4.3 OU : Utiliser le structlog pour les agrégations (moins intrusif — juste vérifier que les événements sont correctement émis et que le log aggregator peut les compter)
  - [x] 4.4 Si Prometheus présent (`prometheus_client` installé) : intégrer des Counter/Histogram (voir section Dev Notes)

- [x] Task 5 — Tests des bornes et du format de réponse d'erreur (AC #5)
  - [x] 5.1 Créer `core/tests/test_db_resilience_bounds.py` (nouveau fichier dédié)
  - [x] 5.2 Test borne max retries : mock N+1 erreurs → vérifie HTTP 503 + `error.code == "DB_UNAVAILABLE"` + `error.reason == "retry_exhausted"`
  - [x] 5.3 Test borne time window : mock 1 erreur + patch `time.time()` pour simuler dépassement du time window → vérifie HTTP 503 + `error.reason == "time_window_exceeded"`
  - [x] 5.4 Test mid-commit : mock OperationalError + `in_atomic_block=False` → vérifie HTTP 503 + `error.reason == "mid_commit_error"` (pas de retry)
  - [x] 5.5 Test format réponse : vérifier structure JSON exacte `{"error": {"code": ..., "reason": ..., "message": ..., "correlation_id": ...}}` + header `Retry-After: 30`
  - [x] 5.6 Test succès avant épuisement : mock 2 erreurs + succès → vérifie HTTP 200 (pas de 503)
  - [x] 5.7 Vérifier que `DB_RETRY_TIME_WINDOW_SECONDS` est respecté (via `override_settings`)

## Dev Notes

### État actuel — Ce qui EXISTE déjà (Stories 32.1, 32.2, 32.3)

**`core/db_resilience.py`** (≈310 lignes) — middleware central :

```python
# Settings actuels (idp_backend/settings.py lignes 131-134)
DB_RETRY_MAX_ATTEMPTS = env.int('DB_RETRY_MAX_ATTEMPTS', default=3)
DB_RETRY_BACKOFF_BASE = env.float('DB_RETRY_BACKOFF_BASE', default=0.5)
# DB_RETRY_TIME_WINDOW_SECONDS → MANQUANT → à ajouter (Task 1.1)
```

**Backoff actuel** dans `_calculate_backoff()` :
- Tentative 1 : 0s (immédiat)
- Tentative 2 : 0.5s
- Tentative 3 : 1.0s
- Plafond : 5s max

**Logs structlog DÉJÀ émis** (à ne PAS recréer, juste vérifier/enrichir) :
| Event | Level | Fields clés |
|-------|-------|-------------|
| `db_connection_lost` | WARNING | `correlation_id`, `error_type`, `error_code` (ORA), `method`, `path` |
| `db_retry_attempt` | WARNING | `correlation_id`, `attempt_number`, `max_attempts`, `backoff_seconds` |
| `db_reconnect_failed` | WARNING | `correlation_id`, `attempt_number`, `error` |
| `db_connection_restored` | INFO | `correlation_id`, `attempt_number`, `total_duration_ms` |
| `db_retry_exhausted` | ERROR | `correlation_id`, `total_attempts`, `total_duration_ms`, `error_code` |
| `db_retry_unsafe_write` | ERROR | `correlation_id`, `error_code`, `reason`, `attempt_number` |

**Réponse 503 actuelle** (dans `_build_503_response()`) :
```json
{
  "error": {
    "code": "DB_UNAVAILABLE",
    "message": "Base de données temporairement indisponible...",
    "correlation_id": "abc-123"
  }
}
```
Header : `Retry-After: 30` (constant, pas de variable de config)

**CE QUI MANQUE** :
- `DB_RETRY_TIME_WINDOW_SECONDS` : la borne temporelle totale n'est pas implémentée (le middleware ne limite que par nombre d'essais, pas par durée totale)
- Champ `reason` dans la réponse 503 pour distinguer les causes
- Événement `db_retry_time_window_exceeded`
- Tests dédiés aux bornes et au format de réponse (les tests existants valident le comportement général mais pas les bornes configurables)

### Localisation du code clé

```
idp-portal/django_backend/
├── core/
│   ├── db_resilience.py          ← MODIFIER (Tasks 1, 2, 3)
│   └── tests/
│       ├── test_db_resilience.py           ← 69 tests unitaires (NE PAS CASSER)
│       ├── test_db_resilience_integration.py ← 13 tests intégration (NE PAS CASSER)
│       └── test_db_resilience_bounds.py    ← CRÉER (Task 5)
└── idp_backend/
    └── settings.py               ← MODIFIER (Task 1.1)
docs/
└── db-resilience.md              ← MODIFIER (Task 1.4)
```

### Implémentation de la borne temporelle (Task 1.2)

**Pattern à suivre** dans `core/db_resilience.py` méthode `__call__()` :

```python
import time

# Dans __call__() avant la boucle retry :
start_time = time.time()
time_window = getattr(settings, 'DB_RETRY_TIME_WINDOW_SECONDS', 120)

# Dans la boucle retry, AVANT le backoff sleep :
elapsed_seconds = time.time() - start_time
if elapsed_seconds >= time_window:
    logger.error(
        "db_retry_time_window_exceeded",
        correlation_id=correlation_id,
        total_duration_ms=int(elapsed_seconds * 1000),
        time_window_seconds=time_window,
        method=request.method,
        path=request.path,
    )
    return self._build_503_response(correlation_id, reason="time_window_exceeded")
```

### Enrichissement de `_build_503_response()` (Task 2)

**Modification minimale** pour ajouter `reason` sans casser le format existant :

```python
def _build_503_response(self, correlation_id: str, reason: str = "retry_exhausted") -> JsonResponse:
    messages = {
        "retry_exhausted": "Base temporairement indisponible après bascule. Veuillez réessayer dans quelques instants.",
        "time_window_exceeded": "Dépassement de la fenêtre de bascule (> 2 min). Veuillez réessayer.",
        "mid_commit_error": "Erreur de base détectée en cours de transaction. Veuillez vérifier l'état de l'opération.",
    }
    return JsonResponse(
        {
            "error": {
                "code": "DB_UNAVAILABLE",
                "reason": reason,
                "message": messages.get(reason, messages["retry_exhausted"]),
                "correlation_id": correlation_id,
            }
        },
        status=503,
        headers={"Retry-After": "30"},
    )
```

**Impact frontend** : `api_client.ts` vérifie déjà `error.code === 'DB_UNAVAILABLE'` via `isDbUnavailable503()`. L'ajout de `reason` est **backward compatible** — ne pas toucher `api_client.ts` pour cette story.

### Structure de test (Task 5)

**Utiliser** `APIClient` DRF (pas `RequestFactory`) pour traverser le middleware complet :

```python
# core/tests/test_db_resilience_bounds.py

from django.test import TestCase, override_settings
from unittest.mock import patch, call
from rest_framework.test import APIClient
from django.db import OperationalError, InterfaceError

class TestRetryBounds(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Authentification minimale (header JWT mock ou skip)

    @override_settings(DB_RETRY_MAX_ATTEMPTS=2)
    def test_503_after_max_retries(self):
        """AC #1 + AC #2 : 503 après épuisement des retries configurés"""
        with patch('django.db.connection.cursor') as mock_cursor:
            mock_cursor.side_effect = OperationalError("ORA-03113")
            response = self.client.get('/api/v1/health/')
            self.assertEqual(response.status_code, 503)
            body = response.json()
            self.assertEqual(body['error']['code'], 'DB_UNAVAILABLE')
            self.assertEqual(body['error']['reason'], 'retry_exhausted')
            self.assertIn('correlation_id', body['error'])
            self.assertEqual(response.headers.get('Retry-After'), '30')

    @override_settings(DB_RETRY_TIME_WINDOW_SECONDS=1)
    def test_503_after_time_window(self):
        """AC #1 : 503 si durée totale > fenêtre temporelle"""
        # Mock time.sleep pour accélérer, patch time.time pour simuler dépassement
        ...

    def test_mid_commit_503_no_retry(self):
        """AC #2 : 503 immédiat mid-commit (reason = mid_commit_error)"""
        ...
```

**Attention** : `SimpleRateThrottle.THROTTLE_RATES` est une class attribute — pour `override_settings(REST_FRAMEWORK=...)`, utiliser `patch.object(SimpleRateThrottle, 'THROTTLE_RATES', new_rates)` (pattern connu du projet, voir MEMORY.md).

### Anti-patterns — NE PAS FAIRE

- **NE PAS** modifier la logique retry existante dans `test_db_resilience.py` (69 tests) — ajouter uniquement dans `test_db_resilience_bounds.py`
- **NE PAS** changer le code `error.code = "DB_UNAVAILABLE"` — c'est la valeur utilisée par `api_client.ts` (`isDbUnavailable503()`)
- **NE PAS** rendre la borne temporelle bloquante avant que le max retries soit atteint — les deux conditions sont indépendantes (court-circuit sur la PREMIÈRE condition remplie)
- **NE PAS** utiliser `time.sleep` réel dans les tests — utiliser `unittest.mock.patch('time.sleep')`
- **NE PAS** dupliquer les tests d'intégration de `test_db_resilience_integration.py` — les tests 32.4 ciblent spécifiquement la configuration des bornes et le format de réponse enrichi
- **NE PAS** modifier `api_client.ts` — le champ `reason` est purement informatif pour logging/debug, `isDbUnavailable503()` vérifie uniquement `error.code`
- **NE PAS** implémenter Prometheus si non installé — AC #4 est optionnel ; vérifier d'abord `'prometheus_client' in sys.modules`

### Configuration des bornes — Documentation (Task 1.4)

Ajouter dans `docs/db-resilience.md` la table de configuration enrichie :

| Variable d'environnement | Défaut | Description |
|--------------------------|--------|-------------|
| `DB_RETRY_MAX_ATTEMPTS` | `3` | Nombre max de tentatives avant 503 |
| `DB_RETRY_BACKOFF_BASE` | `0.5` | Base du backoff exponentiel (secondes) |
| `DB_RETRY_TIME_WINDOW_SECONDS` | `120` | Fenêtre temporelle max pour les retries (2 min, alignée sur FSFO < 1 min) |

### Dépendances

- **Dépend de** Story 32.1 (détection + reconnexion) — DONE ✅ (`core/db_resilience.py` existant)
- **Dépend de** Story 32.2 (retry borné + backoff + idempotence) — DONE ✅
- **Dépend de** Story 32.3 (validation flux portail + API) — DONE ✅
- Aucune nouvelle dépendance Python ou npm

### Commits récents pertinents

- `68f9464` — feat(32-3): résilience portail et API consommateurs — tests d'intégration et gestion 503 frontend
- `cb18693` — feat(32-2): retry borné avec backoff exponentiel et protection idempotence après reconnexion DB
- `4ccfd09` — feat(32-1): détection et reconnexion base de données lors d'un failover Data Guard

### Environnement de test

- Backend : `.venv/bin/python -m pytest` depuis `idp-portal/django_backend/`
- Settings tests : `idp_backend.test_settings` (via `pytest.ini`)
- Frontend : `npm test` (vitest) depuis `idp-portal/frontend/`
- Pattern `override_settings` pour bornes configurables

### References

- [Source: planning-artifacts/epic-32-resilience-dataguard.md — Story 32.4]
- [Source: core/db_resilience.py — Middleware (310 lignes), fonctions `_calculate_backoff()`, `_build_503_response()`, `__call__()`]
- [Source: idp_backend/settings.py lignes 131-134 — Configuration retry]
- [Source: core/tests/test_db_resilience.py — 69 tests unitaires (patterns à suivre)]
- [Source: core/tests/test_db_resilience_integration.py — 13 tests intégration]
- [Source: docs/db-resilience.md — Documentation existante à enrichir]
- [Source: 32-3-resilience-portail-et-api-consommateurs.md — Story précédente, patterns testés]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Deux tests corrigés après analyse : `call_count` attendu mis à jour (1 appel initial dans `__call__` + N retries dans la boucle = N+1 total)

### Completion Notes List

- **Task 1** : `DB_RETRY_TIME_WINDOW_SECONDS=120` ajouté dans `settings.py`. Vérification time window dans `_handle_connection_error()` AVANT le backoff sleep (prevent unnecessary wait). Log `db_retry_time_window_exceeded` avec `total_duration_ms`, `time_window_seconds`, `correlation_id`.
- **Task 2** : `_build_503_response()` refactorisé — signature `reason: str = "retry_exhausted"`, dict de messages distincts par raison, champ `reason` dans le JSON. Backward compatible : `error.code == "DB_UNAVAILABLE"` inchangé.
- **Task 3** : Tous les logs structlog vérifiés et conformes. `db_retry_time_window_exceeded` ajouté (Task 1.3). Champs requis confirmés présents dans chaque événement.
- **Task 4** : AC #4 satisfait via option 4.3 (structlog events correctement émis — `db_retry_attempt`, `db_retry_exhausted`, `db_retry_time_window_exceeded`, `db_connection_restored`). Prometheus non présent.
- **Task 5** : 20 tests créés dans `test_db_resilience_bounds.py`. 103/103 tests passent (69 unitaires + 13 intégration + 20 nouveaux), zéro régression.
- **docs/db-resilience.md** : Table configuration enrichie avec `DB_RETRY_TIME_WINDOW_SECONDS`, section "Borne temporelle" ajoutée, réponse 503 enrichie avec champ `reason`, table événements structlog mise à jour.

### File List

- `idp-portal/django_backend/core/db_resilience.py` — MODIFIÉ (Tasks 1.2, 1.3, 2, 3)
- `idp-portal/django_backend/idp_backend/settings.py` — MODIFIÉ (Task 1.1)
- `idp-portal/django_backend/core/tests/test_db_resilience_bounds.py` — CRÉÉ (Task 5) — 20 tests
- `idp-portal/django_backend/docs/db-resilience.md` — MODIFIÉ (Task 1.4)

### Change Log

- 2026-02-21 : Implémentation Story 32.4 — borne temporelle `DB_RETRY_TIME_WINDOW_SECONDS`, champ `reason` dans 503, event `db_retry_time_window_exceeded`, 20 tests bornes et format réponse. 103/103 tests pass.
- 2026-02-21 : Code review — 4 fixes MEDIUM + 1 fix LOW : (1) message time_window_exceeded sans hardcode "2 min", (2) time window check réordonné avant db_retry_attempt log, (3) tasks 4.1/4.2 corrigées en [ ] (alternative non retenue), (4) doc API consommateur mise à jour avec champ reason, (5) assertion reason ajoutée dans test_mid_commit_503_no_retry. 103/103 tests pass.
