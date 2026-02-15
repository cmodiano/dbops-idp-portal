# VaultService — Known Limitations (Story 27.6)

Ce document liste les limitations identifiées lors du code review adversarial qui ne sont PAS corrigées dans Story 27.6. Ces limitations ne bloquent PAS la story "done", mais doivent être suivies pour amélioration future.

## HIGH-2: Singleton non-réactif aux changements d'env vars

**Fichier:** `services/vault_service.py:456-463`

**Problème:**
Le singleton `get_vault_service()` initialise VaultService **une seule fois** au démarrage. Si `VAULT_TOKEN`, `VAULT_NAMESPACE`, ou autres env vars changent pendant le runtime (via feature flags, configuration reload, Kubernetes ConfigMap reload, etc.), le singleton continue d'utiliser les **anciennes valeurs**.

**Impact:**
Credentials rotation impossible sans redémarrage complet du backend Django (downtime requis).

**Workaround actuel:**
Redémarrer les workers Gunicorn après rotation des credentials :
```bash
kubectl rollout restart deployment/idp-backend
```

**Solution recommandée (Phase 3):**
Implémenter un mécanisme de refresh :
```python
def get_vault_service(force_refresh: bool = False) -> VaultService:
    global _vault_service
    if force_refresh or _vault_service is None:
        with _vault_service_lock:
            if force_refresh or _vault_service is None:
                _vault_service = VaultService()
    return _vault_service
```

Exposer endpoint admin `/api/v1/admin/vault/refresh` (RBAC DBOPS only) :
```python
@api_view(['POST'])
@permission_classes([IsDBAOrDBOPS])
def refresh_vault_service(request):
    from services.vault_service import get_vault_service
    get_vault_service(force_refresh=True)
    return Response({"status": "refreshed"})
```

**Criticité:** MEDIUM (workaround acceptable pour Phase 2).

---

## HIGH-4: Singleton global vulnérable aux tests parallèles

**Fichier:** `services/vault_service.py:452-463`

**Problème:**
Le singleton module-level `_vault_service` est partagé entre TOUS les tests pytest si exécutés avec `pytest -n auto` (parallelisation). Un test qui modifie `svc.circuit_breaker.reset()` ou `svc.clear_cache()` affecte TOUS les autres tests en parallèle.

**Impact:**
Tests flaky, faux positifs/négatifs, couverture non fiable. Actuellement non observé car tests Story 27.6 utilisent `VaultService(...)` directement (pas le singleton), mais risque pour tests futurs.

**Workaround actuel:**
Ne PAS utiliser `get_vault_service()` dans les tests — toujours créer une instance isolée :
```python
# ✅ GOOD
svc = VaultService(vault_addr="http://vault:8200", vault_token="test")

# ❌ BAD (shared singleton)
svc = get_vault_service()
```

**Solution recommandée (Phase 3):**
Créer une fixture pytest avec scope="function" et autouse pour reset le singleton :
```python
# conftest.py
@pytest.fixture(autouse=True)
def reset_vault_singleton():
    import services.vault_service as vs
    vs._vault_service = None
    yield
    vs._vault_service = None
```

Alternative : Implémenter un registry par thread/contexte (thread-local storage) :
```python
import threading

_vault_service_registry = threading.local()

def get_vault_service() -> VaultService:
    if not hasattr(_vault_service_registry, 'instance'):
        _vault_service_registry.instance = VaultService()
    return _vault_service_registry.instance
```

**Criticité:** MEDIUM (pas de tests parallèles actuellement, mais à anticiper).

---

## MED-3: Retry backoff time.sleep() bloque le thread Gunicorn

**Fichier:** `services/vault_service.py:339, 349, 361`

**Problème:**
`time.sleep(backoff)` bloque le thread Gunicorn worker pendant jusqu'à **4 secondes** (2^2). Avec 4 workers Gunicorn et 100 requêtes simultanées vers Vault en erreur 500 :
- Les 4 workers sont BLOQUÉS pendant 4s
- Nouveau requests HTTP arrivent → en attente (queue)
- Backend non-réactif pendant le retry

**Impact:**
Latence P99 violée (> 5s), UX dégradée, violation NFR performance.

**Workaround actuel:**
Acceptable pour Phase 2 car :
1. Vault haute disponibilité (3+ replicas) réduit probabilité erreur 500
2. Circuit breaker ouvre après 5 échecs → limite dégâts
3. Max 3 retries = 1s + 2s + 4s = 7s total (tolérable pour ops backend)

**Solution recommandée (Phase 3 — Story 20-3 déjà créée):**
Migrer appels Vault vers **Celery tasks asynchrones** :
```python
# executions/tasks.py
@shared_task(bind=True, max_retries=3)
def fetch_vault_secret(self, credential_ref: str):
    from services.vault_service import get_vault_service
    try:
        return get_vault_service().get_secret(credential_ref)
    except VaultUnavailableError as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

Usage dans adapter :
```python
# adapters/utils.py
def build_auth_headers(integration: Integration, correlation_id: str | None = None) -> dict:
    if credential_ref.startswith("vault:"):
        # Async fetch via Celery
        task = fetch_vault_secret.delay(credential_ref)
        resolved = task.get(timeout=10)
        return {"Authorization": f"Bearer {resolved}"}
```

**Criticité:** LOW pour Phase 2 (workaround acceptable), HIGH pour Phase 3 (scaling > 100 req/s).

---

## Recommandation globale

Ces 3 limitations ne bloquent PAS le passage de Story 27.6 en **done** car :
1. HIGH-2 (env vars) : workaround viable (restart workers)
2. HIGH-4 (tests parallèles) : tests actuels isolés correctement
3. MED-3 (blocking sleep) : acceptable pour charge actuelle (< 50 req/s)

**Action recommandée :** Créer Epic 28 "VaultService Phase 3 — Production Hardening" avec stories :
- 28.1 : Singleton refresh endpoint (HIGH-2)
- 28.2 : Thread-local registry pour tests parallèles (HIGH-4)
- 28.3 : Migration Celery async (MED-3) — dépend Story 20-3

**Acceptation criteria Story 27.6 :** TOUTES les AC1-AC8 sont MET. Ces limitations sont documentées comme "Known Limitations" et n'affectent PAS la fonctionnalité core (résolution credential_ref, retry, circuit breaker, cache, auth, namespaces).
