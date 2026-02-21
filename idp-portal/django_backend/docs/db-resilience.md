# Résilience Base de Données — Data Guard Failover/Switchover

> Stories 32.1 et 32.2 — Détection, reconnexion, retry borné et idempotence

## Vue d'ensemble

Le portail IDP utilise Oracle Data Guard avec FSFO (Fast-Start Failover) en production. Lors d'un failover/switchover, les connexions DB existantes deviennent invalides. Cette couche de résilience assure la continuité de service automatique.

## Mécanismes de protection

### 1. `CONN_HEALTH_CHECKS` (mécanisme principal)

Django 4.1+ valide chaque connexion réutilisée avant de l'utiliser. Si la connexion est morte (post-failover), Django la recrée silencieusement.

```
DATABASES['default']['CONN_HEALTH_CHECKS'] = True
```

### 2. `CONN_MAX_AGE` (expiration naturelle)

Les connexions expirent après 600 secondes (10 min). Après un failover, les nouvelles requêtes obtiennent automatiquement des connexions fraîches à mesure que les anciennes expirent.

```
DATABASES['default']['CONN_MAX_AGE'] = 600  # secondes
```

### 3. `DatabaseResilienceMiddleware` (filet de sécurité + retry borné)

Si une erreur de connexion passe malgré le health check, le middleware :
1. Détecte l'erreur via les codes ORA et types d'exception
2. Vérifie l'idempotence pour les requêtes en écriture
3. Retente l'opération avec **backoff exponentiel** (jusqu'à `DB_RETRY_MAX_ATTEMPTS` tentatives)
4. Retourne une **réponse 503 structurée** si tous les retries sont épuisés
5. Logge les événements en structlog à chaque étape

## Politique de retry (Story 32.2)

### Backoff exponentiel

| Tentative | Délai avant retry |
|-----------|-------------------|
| 1 | Immédiate (0s) |
| 2 | `DB_RETRY_BACKOFF_BASE` (0.5s par défaut) |
| 3 | `DB_RETRY_BACKOFF_BASE × 2` (1.0s par défaut) |
| N | `DB_RETRY_BACKOFF_BASE × 2^(N-2)`, cap à **5s** |

Le cap à 5s protège contre les timeouts gunicorn (30s par défaut).

### Idempotence des requêtes

| Type de requête | Comportement |
|-----------------|-------------|
| **GET, HEAD, OPTIONS** | Toujours retentées (aucun effet de bord) |
| **POST, PUT, PATCH, DELETE** (pré-commit) | Retentées si l'erreur survient **avant le COMMIT** (transaction rollback automatique par Django) |
| **POST, PUT, PATCH, DELETE** (mid-commit) | **Jamais retentées** → 503 avec message « résultat incertain » |

**Détection pré-commit vs mid-commit :**
- `InterfaceError` = connexion morte = toujours pré-commit → retry safe
- `OperationalError` ORA-03113/03114 = vérification de `connection.in_atomic_block` :
  - `True` → transaction encore active → pré-commit → retry safe
  - `False` → Django a nettoyé l'atomic block → état incertain → pas de retry

### Réponse 503 (retries épuisés)

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

Pour les erreurs mid-commit :
```json
{
  "error": {
    "code": "DB_UNAVAILABLE",
    "message": "Résultat incertain après coupure réseau pendant le commit. Veuillez vérifier l'état de l'opération.",
    "correlation_id": "abc-123"
  }
}
```

## Diagramme de séquence

```
Client          Middleware              Django/View         Base de données
  |                  |                      |                     |
  |--- requête ----->|                      |                     |
  |                  |--- get_response() -->|                     |
  |                  |                      |--- query ---------->|
  |                  |                      |   ❌ connexion perdue|
  |                  |<-- OperationalError -|                     |
  |                  |                      |                     |
  |                  | (1) Log db_connection_lost                 |
  |                  | (2) Vérif idempotence (write → mid-commit?)|
  |                  | (3) Si mid-commit → 503 immédiat           |
  |                  |                      |                     |
  |                  | RETRY tentative 1 (immédiate)              |
  |                  |--- close_old_connections() + ensure_connection()
  |                  |--- get_response() -->|                     |
  |                  |                      |--- query ---------->|
  |                  |                      |   ❌ encore en erreur|
  |                  |<-- OperationalError -|                     |
  |                  |                      |                     |
  |                  | RETRY tentative 2 (sleep 0.5s)             |
  |                  |--- close_old_connections() + ensure_connection()
  |                  |--- get_response() -->|                     |
  |                  |                      |--- query ---------->|
  |                  |                      |<-- ✅ succès --------|
  |                  |<-- HttpResponse 200 -|                     |
  |                  | Log db_connection_restored                 |
  |<-- réponse 200 --|                      |                     |
  |                  |                      |                     |
  | OU si tous les retries échouent :                             |
  |<-- 503 DB_UNAVAILABLE + Retry-After: 30                      |
```

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DB_CONN_MAX_AGE` | `600` | Durée de vie max d'une connexion (secondes) |
| `DB_CONN_HEALTH_CHECKS` | `True` | Validation des connexions avant réutilisation |
| `DB_RETRY_MAX_ATTEMPTS` | `3` | Nombre max de tentatives de retry après erreur de connexion |
| `DB_RETRY_BACKOFF_BASE` | `0.5` | Délai de base (secondes) pour le backoff exponentiel entre tentatives |

### Middleware

Le middleware `DatabaseResilienceMiddleware` est placé après `CorrelationIdMiddleware` dans la stack middleware :

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CorrelationIdMiddleware',
    'core.db_resilience.DatabaseResilienceMiddleware',  # Stories 32.1, 32.2
    ...
]
```

## Erreurs Oracle détectées

Le middleware reconnaît les codes ORA suivants comme erreurs de connexion :

| Code | Description |
|------|-------------|
| ORA-03113 | End-of-file on communication channel |
| ORA-03114 | Not connected to ORACLE |
| ORA-03135 | Connection lost contact |
| ORA-01033 | ORACLE initialization or shutdown in progress |
| ORA-12541 | TNS: no listener |
| ORA-12543 | TNS: destination host unreachable |
| ORA-12571 | TNS: packet writer failure |
| ORA-00028 | Session killed |
| ORA-01012 | Not logged on |
| ORA-12170 | TNS: connect timeout occurred |
| ORA-12514 | TNS: listener does not currently know of service |

Les `InterfaceError` sont toujours traités comme des erreurs de connexion.

## Événements structlog

| Événement | Niveau | Description |
|-----------|--------|-------------|
| `db_connection_lost` | WARNING | Connexion DB perdue, début du processus de retry |
| `db_retry_attempt` | WARNING | Tentative de retry N/max (inclut `attempt_number`, `max_attempts`, `backoff_seconds`) |
| `db_reconnect_failed` | WARNING | Échec de `ensure_connection()` lors d'une tentative de reconnexion (inclut `attempt_number`, `error`) |
| `db_connection_restored` | INFO | Reconnexion réussie après retry (inclut `attempt_number`, `total_duration_ms`) |
| `db_retry_exhausted` | ERROR | Tous les retries épuisés (inclut `total_attempts`, `total_duration_ms`) |
| `db_retry_unsafe_write` | ERROR | Écriture mid-commit détectée, retry refusé |

Chaque événement inclut : `correlation_id`, `method`, `path`.

## Health Check

L'endpoint `GET /api/v1/health/` inclut un champ `db_pool_status` :

```json
{
  "data": {
    "status": "healthy",
    "oracle": "connected",
    "db_pool_status": {
      "conn_max_age": 600,
      "conn_health_checks": true,
      "connection_usable": true
    }
  }
}
```

## Comportement connu : double logging lors d'un retry réussi

Quand le middleware retente une requête avec succès, `RequestResponseLoggingMiddleware` (en aval dans la chaîne) logge `request_received` et `request_completed` deux fois pour la même requête. Les deux entrées partagent le même `correlation_id`, ce qui permet de les corréler. Ce comportement est inhérent à l'architecture middleware Django et n'affecte pas le fonctionnement.

## Fenêtre de bascule typique

Data Guard FSFO : **< 1 minute**. Pendant cette fenêtre :
- `CONN_HEALTH_CHECKS` détecte les connexions mortes et les recrée
- Le middleware intercepte les erreurs et retente avec backoff exponentiel
- Après 3 tentatives (par défaut), retourne 503 avec header `Retry-After: 30`
- Les requêtes en lecture sont toujours retentées
- Les requêtes en écriture sont retentées uniquement si l'erreur est pré-commit (idempotence protégée)

---

## Comportement pendant un failover Data Guard

> Story 32.3 — NFR/Runbook : impact utilisateur et consommateurs API pendant un failover/switchover

### Du point de vue du portail (utilisateur humain)

Lors d'un failover Data Guard, un utilisateur du portail peut observer :

**Timeline typique (fenêtre < 1 min) :**

```
t=0s   Bascule Data Guard FSFO déclenche (automatique)
t=0-5s Connexions DB existantes invalidées — prochaines requêtes échouent
t=5s   DatabaseResilienceMiddleware intercepte OperationalError/InterfaceError
t=5s   Tentative 1 (immédiate) : close_old_connections() + ensure_connection()
       → échoue si le nouveau primary n'est pas encore prêt
t=5.5s Tentative 2 (0.5s backoff)
t=6.5s Tentative 3 (1.0s backoff)
       → en général, le primary est prêt — reconnexion réussie → HTTP 200/201 normal
t=6.5s Si toutes les tentatives échouent : HTTP 503 DB_UNAVAILABLE + Retry-After: 30
       → le frontend React affiche un avertissement et retente automatiquement (×2, délai 30s)
t=~60s La bascule est complète ; toutes les nouvelles requêtes réussissent normalement
```

**Ce que voit l'utilisateur :**

- **Cas nominal (tentative réussit < 6.5s)** : aucun impact visible — la réponse est légèrement plus lente mais renvoie le résultat correct (HTTP 200/201).
- **Cas 503 (bascule lente ou surcharge)** : une notification Ant Design apparaît en haut à droite :
  - Premier retry : `⚠️ Service temporairement indisponible. Nouvelle tentative en cours...`
  - Après épuisement des retries : `❌ Base de données temporairement indisponible après bascule. Veuillez réessayer dans quelques instants.`
  - L'utilisateur peut réessayer manuellement après ~30 secondes.

**Endpoints protégés (exemples) :**

| Endpoint | Méthode | Protection |
|----------|---------|------------|
| `/api/v1/catalog/actions/` | GET | Retry automatique, toujours safe |
| `/api/v1/executions/` | POST | Retry si erreur pré-commit (idempotence) |
| `/api/v1/scheduled-executions/` | GET | Retry automatique, toujours safe |

### Du point de vue d'un consommateur API (système externe)

Un consommateur API (Control-M, script Python, autre système) utilise le même endpoint HTTP avec un header `Authorization: Bearer <token>`. Le middleware `DatabaseResilienceMiddleware` s'applique **identiquement** — il n'y a aucune distinction entre une requête portail et une requête API.

**Comportement attendu :**

1. **Tentatives internes (backend)** : le middleware retente l'opération jusqu'à `DB_RETRY_MAX_ATTEMPTS` fois (défaut : 3) avec backoff exponentiel. Le consommateur ne voit rien pendant cette phase — il attend simplement la réponse.
2. **Réponse 503** (si toutes les tentatives backend échouent) :

```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
Retry-After: 30

{
  "error": {
    "code": "DB_UNAVAILABLE",
    "message": "Base de données temporairement indisponible après bascule. Veuillez réessayer dans quelques instants.",
    "correlation_id": "abc-123-def-456"
  }
}
```

**Recommandations pour les consommateurs API :**

- Implémenter un retry avec backoff en cas de réception d'un HTTP 503 avec `"code": "DB_UNAVAILABLE"`.
- Lire le header `Retry-After` et attendre la durée indiquée (30 secondes) avant de réessayer.
- Limiter les retries à 2-3 tentatives supplémentaires maximum pour éviter les boucles si la DB reste indisponible.
- Tracer le `correlation_id` de la réponse 503 pour faciliter le diagnostic côté ops.
- **Ne pas** retenter les 503 sans vérifier `error.code === "DB_UNAVAILABLE"` — d'autres 503 (maintenance planifiée, surcharge) ne doivent pas être retentés automatiquement.

**Exemple Python (client API externe) :**

```python
import time
import requests

MAX_503_RETRIES = 2

def api_call_with_resilience(url, headers, data=None):
    for attempt in range(MAX_503_RETRIES + 1):
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        if resp.status_code != 503:
            return resp
        body = resp.json()
        if body.get("error", {}).get("code") != "DB_UNAVAILABLE":
            resp.raise_for_status()  # Autre 503 — ne pas retenter
        retry_after = int(resp.headers.get("Retry-After", 30))
        if attempt < MAX_503_RETRIES:
            time.sleep(retry_after)
    resp.raise_for_status()
```

### Fenêtre de bascule et impact utilisateur

| Phase | Durée typique | Comportement observé |
|-------|--------------|----------------------|
| Déclenchement failover | t=0 | Connexions DB invalides |
| Retry backend (tentatives 1-3) | 0–6.5s | Réponse plus lente, mais transparente si succès |
| 503 renvoyé au client | t=6.5s+ | HTTP 503 + Retry-After: 30 |
| Retry frontend (portail) | +0–60s | Notification warning, re-tentative automatique ×2 |
| Bascule complète | < 60s | Toutes les requêtes réussissent normalement |
| Reconnexion complète | < 90s | Pool de connexions reconstitué |

**Codes d'erreur possibles pendant un failover :**

| Code d'erreur | Source | Description |
|--------------|--------|-------------|
| `DB_UNAVAILABLE` | Backend middleware | Retries épuisés — DB non joignable |
| ORA-03113 | Oracle | End-of-file on communication channel |
| ORA-03135 | Oracle | Connection lost contact |
| ORA-12541 | Oracle | TNS: no listener (primary pas encore prêt) |
| ORA-01033 | Oracle | ORACLE initialization or shutdown in progress |

**SLO cible :** < 1 minute d'indisponibilité observable (Data Guard FSFO). Les requêtes en lecture et en écriture pré-commit sont récupérées automatiquement dans la grande majorité des cas.
