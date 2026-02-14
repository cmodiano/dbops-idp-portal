# Troubleshooting Circuit Breaker — VaultService

## LOW-1 FIX: Circuit Breaker Monitoring en Production

### Symptôme

Les exécutions échouent avec `VaultUnavailableError: Circuit breaker open`.

### Diagnostic

Le circuit breaker VaultService peut être dans 3 états :

| État | Signification | Comportement |
|------|--------------|--------------|
| **closed** | Normal | Requêtes Vault envoyées normalement |
| **open** | Vault indisponible | Requêtes rejetées immédiatement (60s timeout) |
| **half-open** | Test de récupération | 1 requête test autorisée |

### Comment vérifier l'état actuel ?

**Option 1 : Logs structlog (production)**

```bash
# Chercher les événements circuit breaker
kubectl logs -f deployment/idp-backend | grep circuit_breaker
```

Événements possibles :
- `circuit_breaker_open` — Circuit vient de s'ouvrir (5 échecs)
- `circuit_breaker_half_open` — Timeout écoulé, test en cours
- `circuit_breaker_closed` — Récupération réussie

**Option 2 : Health check endpoint (recommandé)**

```bash
curl http://localhost:8000/api/v1/health/vault
```

Réponse attendue :
```json
{
  "status": "healthy",
  "vault": {
    "circuit_breaker_state": "closed",
    "consecutive_failures": 0,
    "last_failure_time": null
  }
}
```

Si circuit ouvert :
```json
{
  "status": "degraded",
  "vault": {
    "circuit_breaker_state": "open",
    "consecutive_failures": 5,
    "last_failure_time": "2026-02-14T10:30:00Z",
    "retry_after_seconds": 45
  }
}
```

### Actions correctives

1. **Vérifier Vault accessible** :
   ```bash
   curl -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_ADDR/v1/sys/health
   ```

2. **Vérifier token valide** :
   ```bash
   vault token lookup
   ```

3. **Forcer reset du circuit breaker** (dev/staging uniquement) :
   ```python
   from core.vault_service import get_vault_service
   get_vault_service().circuit_breaker.reset()
   ```

4. **Attendre 60s** — Le circuit passe automatiquement en "half-open" et tente une récupération.

### Métriques recommandées

Pour monitoring Prometheus/Grafana :

- `vault_circuit_breaker_state{state="open|closed|half-open"}`
- `vault_circuit_breaker_failures_total`
- `vault_request_duration_seconds{status="success|failure"}`

### Prévention

- **Alertes Datadog/PagerDuty** : déclencher alerte si circuit ouvert > 2 min
- **Retry budgets** : limiter le nombre de retries globaux par minute
- **Circuit breaker tuning** : ajuster `failure_threshold` (défaut 5) et `timeout` (défaut 60s)
