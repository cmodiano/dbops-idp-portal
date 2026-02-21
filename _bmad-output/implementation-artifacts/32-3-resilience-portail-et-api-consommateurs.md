# Story 32.3 : Résilience pour le portail et les consommateurs API

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'utilisateur du portail ou consommateur de l'API,
je veux que la résilience (détection, reconnexion, retry) s'applique à tous les flux : requêtes issues du portail et appels API externes,
afin de ne pas subir d'échecs évitables pendant un failover/switchover Data Guard.

## Acceptance Criteria

1. **Given** la résilience implémentée en 32.1 et 32.2
   **When** une requête provient du **portail** (utilisateur humain) ou d'un **consommateur API** (système externe)
   **Then** la même logique de détection, reconnexion et retry s'applique
   **And** le middleware `DatabaseResilienceMiddleware` protège universellement toutes les vues Django sans distinction d'origine

2. **Given** une requête du **portail** (ex. chargement catalogue via `GET /api/v1/catalog/actions/`, soumission d'exécution via `POST /api/v1/executions/`)
   **When** un failover DB survient pendant le traitement
   **Then** le middleware retente l'opération (retry borné avec backoff, Story 32.2)
   **And** un test d'intégration valide le scénario catalogue (lecture) et un test valide le scénario exécution (écriture)

3. **Given** une requête d'un **consommateur API externe** (ex. `POST /api/v1/executions/` avec header `Authorization: Bearer <token>`, `GET /api/v1/scheduled-executions/pending` pour scheduler externe)
   **When** un failover DB survient pendant le traitement
   **Then** le middleware retente l'opération de la même façon
   **And** un test d'intégration valide le scénario API externe (lecture et écriture)

4. **Given** le frontend du portail (`api_client.ts`)
   **When** le backend retourne un **HTTP 503** avec code `DB_UNAVAILABLE` et header `Retry-After`
   **Then** le client API retente automatiquement la requête après le délai `Retry-After` (ou backoff par défaut 5s)
   **And** maximum `MAX_503_RETRIES = 2` tentatives (total 3 avec la requête initiale)
   **And** une notification utilisateur informe que le service est temporairement indisponible

5. **Given** la documentation
   **Then** `docs/db-resilience.md` contient une section NFR/runbook décrivant le comportement attendu pendant et après un failover (< 1 min) pour le portail ET les consommateurs API

## Tasks / Subtasks

- [x] Task 1 — Tests d'intégration scénarios portail (AC #1, #2)
  - [x] 1.1 Créer `core/tests/test_db_resilience_integration.py` avec tests sur endpoints réels
  - [x] 1.2 Test scénario portail lecture : `GET /api/v1/catalog/actions/` — mock `OperationalError` au 1er appel, succès au 2ème → vérifie HTTP 200 + body JSON valide
  - [x] 1.3 Test scénario portail écriture : `POST /api/v1/executions/` — mock `InterfaceError` au 1er appel (pré-commit), succès au 2ème → vérifie HTTP 201 ou équivalent
  - [x] 1.4 Test scénario portail échec : `GET /api/v1/catalog/actions/` — mock N+1 erreurs → vérifie HTTP 503 + body JSON `DB_UNAVAILABLE` + header `Retry-After: 30`
  - [x] 1.5 Chaque test vérifie que le `correlation_id` est présent dans la réponse et les logs

- [x] Task 2 — Tests d'intégration scénarios API consommateurs (AC #1, #3)
  - [x] 2.1 Test API externe lecture : `GET /api/v1/scheduled-executions/pending` avec auth JWT — même pattern retry que Task 1.2
  - [x] 2.2 Test API externe écriture : `POST /api/v1/executions/` avec auth JWT — même pattern retry que Task 1.3
  - [x] 2.3 Test API externe échec : retries épuisés → 503 avec body standardisé
  - [x] 2.4 Vérifier que les headers de réponse sont identiques pour portail et API (même format 503, même `Retry-After`)

- [x] Task 3 — Gestion 503 `DB_UNAVAILABLE` dans le frontend (AC #4)
  - [x] 3.1 Dans `api_client.ts`, ajouter une branche 503 dans `apiFetch()` similaire au pattern 429 existant
  - [x] 3.2 Lire le header `Retry-After` de la réponse 503 (comme pour 429)
  - [x] 3.3 Retry jusqu'à `MAX_503_RETRIES = 2` avec backoff basé sur `Retry-After` (défaut 5s si absent)
  - [x] 3.4 Logger chaque retry : `api_503_retry` avec `attempt`, `max_retries`, `retry_after_seconds`, `correlation_id`
  - [x] 3.5 Après épuisement des retries 503, laisser l'`ApiError` remonter normalement (message français du backend)

- [x] Task 4 — Notification utilisateur pour 503 DB (AC #4)
  - [x] 4.1 Dans `parseErrorResponse()` ou appelant, détecter `status === 503` et `body.error.code === 'DB_UNAVAILABLE'`
  - [x] 4.2 Afficher une notification Ant Design `notification.warning()` avec message : « Service temporairement indisponible. Nouvelle tentative en cours... »
  - [x] 4.3 Si retries épuisés, afficher `notification.error()` : « Base de données temporairement indisponible après bascule. Veuillez réessayer dans quelques instants. »
  - [x] 4.4 Ne pas afficher la notification si le retry réussit (seul le retry initial affiche le warning)

- [x] Task 5 — Tests frontend (AC #4)
  - [x] 5.1 Tests unitaires `api_client.test.ts` : mock fetch 503 avec header `Retry-After: 30` → vérifie retry après 30s (ou mocked timer), succès au 2ème appel
  - [x] 5.2 Test retry 503 épuisé : 3× 503 → vérifie `ApiError` avec status 503
  - [x] 5.3 Test 503 sans `Retry-After` header → utilise backoff par défaut 5s
  - [x] 5.4 Test que le body `DB_UNAVAILABLE` est correctement parsé comme message français
  - [x] 5.5 Test notification : mock `notification.warning()` lors du retry, `notification.error()` si épuisé

- [x] Task 6 — Documentation NFR/runbook (AC #5)
  - [x] 6.1 Ajouter section « ## Comportement pendant un failover Data Guard » dans `docs/db-resilience.md`
  - [x] 6.2 Sous-section « ### Du point de vue du portail (utilisateur humain) »
  - [x] 6.3 Sous-section « ### Du point de vue d'un consommateur API (système externe) »
  - [x] 6.4 Sous-section « ### Fenêtre de bascule et impact utilisateur »
  - [x] 6.5 Inclure : timeline typique (perte DB → détection middleware → retry → reconnexion < 1 min), codes d'erreur possibles (503 DB_UNAVAILABLE), headers (Retry-After), recommandations pour consommateurs API (implémenter retry avec backoff)

## Dev Notes

### Contexte critique — Ce qui existe déjà (Stories 32.1 + 32.2)

**Middleware `DatabaseResilienceMiddleware`** dans `core/db_resilience.py` (310 lignes) :
- Intercepte `OperationalError`, `InterfaceError`, `DatabaseError` dans `__call__()`
- `_is_connection_error()` vérifie 11 codes ORA + 5 patterns textuels
- Retry borné : `DB_RETRY_MAX_ATTEMPTS` (défaut 3) avec backoff exponentiel (`DB_RETRY_BACKOFF_BASE` × 2^attempt, cap 5s)
- Idempotence : `_is_retry_safe()` distingue lectures (toujours safe), écritures pré-commit (safe), écritures mid-commit (503 immédiat)
- Réponse 503 : `JsonResponse` avec `{"error": {"code": "DB_UNAVAILABLE", "message": "...", "correlation_id": "..."}}` + header `Retry-After: 30`
- Position dans la stack middleware : après `CorrelationIdMiddleware`, avant `RequestResponseLoggingMiddleware`

**Point clé** : Le middleware est **universellement appliqué** à toutes les requêtes HTTP Django. Que la requête vienne du portail ou d'un consommateur API, elle passe par le même middleware. L'AC #1 est **architecturalement satisfait** — cette story le valide par des tests ciblés et ajoute la couche frontend + documentation.

### Client API frontend — Pattern 429 existant à réutiliser

`frontend/src/services/api_client.ts` gère déjà les 429 (throttling) avec retry :
```typescript
// Pattern existant pour 429 — reproduire pour 503 :
if (response.status === 429) {
  const retryAfter = response.headers.get('Retry-After');
  // ... retry avec backoff
}
```

**Appliquer le MÊME pattern pour 503** :
- Lire `Retry-After` du header
- Retry borné (MAX_503_RETRIES = 2)
- Log structuré `api_503_retry`

**Fonctions à modifier** : `apiFetch()`, `apiFetchRaw()`, `apiFetchBlob()` — le pattern retry doit être dans la fonction interne commune.

### Gap frontend actuel — Aucune gestion 503 DB_UNAVAILABLE

Actuellement dans `api_client.ts` :
- **429** : retry automatique avec `Retry-After` ✅
- **401** : retry après refresh token ✅
- **503** : aucun traitement spécial ❌ → tombe dans le chemin générique `parseErrorResponse()` → `ApiError`

Le seul code existant qui gère le 503 est dans `execution_service.ts` (fallback cache inventaire, utilise `message.includes('503')` — fragile et spécifique).

### Exception handler DRF vs middleware

Le middleware retourne un `django.http.JsonResponse` (pas `rest_framework.response.Response`) car il agit **avant** DRF dans la pile. Le `custom_exception_handler()` dans `core/exceptions.py` gère les exceptions DRF (`ServiceUnavailableError` → 503) mais le middleware est un niveau en dessous. Les deux coexistent sans conflit.

### Tests d'intégration — Approche

Utiliser le `APIClient` de DRF (pas `RequestFactory`) pour traverser la stack middleware complète :
```python
from rest_framework.test import APIClient, APITestCase

class TestPortalResilience(APITestCase):
    def test_catalog_retry_on_db_failure(self):
        client = APIClient()
        # Mock OperationalError au niveau DB
        # Vérifie que le middleware retente et retourne 200
```

**Attention** : Les tests existants (`test_db_resilience.py`) utilisent `RequestFactory` + appel direct au middleware. Les tests 32.3 doivent passer par `APIClient` pour valider le flux complet.

**Mock stratégie** : Mocker au niveau du queryset ou de la connexion DB pour simuler une erreur au premier appel, puis succès. NE PAS modifier les modèles ou fixtures réels.

### Fichiers à modifier / créer

| Fichier | Action | Détails |
|---------|--------|---------|
| `core/tests/test_db_resilience_integration.py` | CRÉER | Tests intégration portail + API (Tasks 1, 2) |
| `frontend/src/services/api_client.ts` | MODIFIER | Gestion 503 retry (Task 3) |
| `frontend/src/services/__tests__/api_client.test.ts` | MODIFIER ou CRÉER | Tests retry 503 (Task 5) |
| `docs/db-resilience.md` | MODIFIER | Section NFR/runbook (Task 6) |

### Anti-patterns — NE PAS FAIRE

- **NE PAS** modifier `db_resilience.py` — le middleware est déjà universel, aucune modification nécessaire
- **NE PAS** utiliser `message.includes('503')` pour détecter le 503 côté frontend — utiliser `response.status === 503`
- **NE PAS** ajouter un retry infini côté frontend — max 2 retries pour éviter les boucles si la DB est vraiment down
- **NE PAS** retenter les 503 qui ne sont PAS `DB_UNAVAILABLE` — vérifier le body `error.code` avant de retry
- **NE PAS** afficher une notification à chaque retry 503 — un seul warning au 1er retry, puis error si épuisé
- **NE PAS** dupliquer le pattern 429 — factoriser la logique retry commune si possible
- **NE PAS** utiliser `APITestCase` avec fixtures lourdes pour les tests d'intégration — mocker le niveau DB uniquement
- **NE PAS** créer un nouveau middleware — utiliser le middleware existant qui couvre déjà tout

### Dépendances

- **Dépend de** Stories 32.1 (détection + reconnexion) — DONE ✅
- **Dépend de** Story 32.2 (retry borné + backoff + idempotence) — DONE ✅
- **Aucune nouvelle dépendance Python ou npm**
- Story 32.4 (bornes, observabilité, codes d'erreur) étend le comportement validé ici

### Commits récents pertinents

- `cb18693` — feat(32-2): retry borné avec backoff exponentiel et protection idempotence après reconnexion DB
- `4ccfd09` — feat(32-1): détection et reconnexion base de données lors d'un failover Data Guard
- Pattern retry 429 dans `api_client.ts` — modèle exact à reproduire pour 503

### Project Structure Notes

- Backend Django : `idp-portal/django_backend/`
- Frontend React : `idp-portal/frontend/`
- Middleware stack : `idp_backend/settings.py` (DatabaseResilienceMiddleware en position 3)
- Client API : `frontend/src/services/api_client.ts` (fonctions `apiFetch`, `apiFetchRaw`, `apiFetchBlob`)
- Tests backend runner : `.venv/bin/python -m pytest` avec `idp_backend.test_settings`
- Tests frontend runner : `npm test` (vitest) depuis `idp-portal/frontend/`

### References

- [Source: planning-artifacts/epic-32-resilience-dataguard.md — Story 32.3]
- [Source: core/db_resilience.py — Middleware universel (310 lignes), déjà fonctionnel pour toutes les requêtes]
- [Source: core/tests/test_db_resilience.py — 69 tests existants (32.1 + 32.2), pattern à suivre]
- [Source: core/exceptions.py — ServiceUnavailableError, custom_exception_handler, format d'erreur standard]
- [Source: frontend/src/services/api_client.ts — Pattern retry 429 existant à reproduire pour 503]
- [Source: docs/db-resilience.md — Documentation existante à enrichir avec NFR/runbook]
- [Source: 32-1-detection-reconnexion-base-donnees-failover.md — Story précédente]
- [Source: 32-2-retry-rejeu-transaction-apres-reconnexion.md — Story précédente, insights retry + idempotence]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage — implémentation directe sur la base des patterns 32.1 et 32.2.

### Completion Notes List

- **Tasks 1 & 2 (backend)** : `test_db_resilience_integration.py` créé (13 tests) — déjà présent en fichier non-tracké. Valide la couverture universelle du middleware pour portail et API consumers. 82 tests backend passent.
- **Tasks 3 & 4 (frontend)** : `api_client.ts` avait déjà la logique 503 retry + notifications mais manquait la fonction `isDbUnavailable503`. Ajout de cette fonction helper (clone response, parse JSON, check `error.code === 'DB_UNAVAILABLE'`). Pattern 429 reproduit exactement pour 503.
- **Task 5 (tests frontend)** : 12 nouveaux tests ajoutés dans `api_client.test.ts` (isDbUnavailable503 × 4 + retry 503 × 8). Total 50 tests frontend passent.
- **Task 6 (docs)** : Section NFR/runbook ajoutée dans `docs/db-resilience.md` avec timeline failover, comportements portail/API, codes d'erreur Oracle, recommandations Python pour consommateurs API.
- **AC #1** : Validé architecturalement (middleware universel) + tests `TestMiddlewareUniversality`.
- **AC #2** : Validé par `TestPortalResilience` (GET catalog, POST executions, 503 exhaustion, correlation_id).
- **AC #3** : Validé par `TestAPIConsumerResilience` (même patterns avec header JWT Bearer).
- **AC #4** : Validé par tests frontend 503 retry + notification tests.
- **AC #5** : Section NFR/runbook complète dans `docs/db-resilience.md`.

### File List

- `idp-portal/django_backend/core/tests/test_db_resilience_integration.py` — CRÉÉ (13 tests intégration portail + API)
- `idp-portal/frontend/src/services/api_client.ts` — MODIFIÉ (ajout helper `isDbUnavailable503`)
- `idp-portal/frontend/src/services/api_client.test.ts` — MODIFIÉ (12 nouveaux tests 503)
- `idp-portal/django_backend/docs/db-resilience.md` — MODIFIÉ (section NFR/runbook Story 32.3)

### Change Log

- 2026-02-21 : Story 32.3 implémentée — tests intégration backend (13), helper `isDbUnavailable503`, tests frontend 503 (12), documentation NFR/runbook Data Guard failover
- 2026-02-21 : Code review adversariale — 6 issues corrigés :
  - [H2] `test_correlation_id_in_logs` : assertion `total_duration_ms` auto-référencée remplacée par vérification structurée (isinstance + valeurs exactes)
  - [M1] Boucle retry 503 : re-vérification `isDbUnavailable503` après chaque retry pour éviter de traiter un 503 MAINTENANCE comme un DB_UNAVAILABLE
  - [M2] Log `api_503_exhausted` : clé renommée pour cohérence structlog + `endpoint` confirmé présent
  - [M3] Calcul délai 503 : uniformisé avec logique `calculateRetryDelay` (vérification `> 0` explicite, suppression du `||` falsy ambigu)
  - [M4] Nouveau test `test_execution_write_mid_commit_no_retry` : valide le 503 immédiat sans retry pour POST mid-commit (ORA-03113 + `in_atomic_block=False`)
