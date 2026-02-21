# Résilience Base de Données — Data Guard Failover/Switchover

> Story 32.1 — Détection et reconnexion automatique après failover

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

### 3. `DatabaseResilienceMiddleware` (filet de sécurité)

Si une erreur de connexion passe malgré le health check, le middleware :
1. Détecte l'erreur via les codes ORA et types d'exception
2. Ferme les connexions mortes (`close_old_connections()`)
3. Retente la requête **une seule fois**
4. Logge les événements en structlog

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DB_CONN_MAX_AGE` | `600` | Durée de vie max d'une connexion (secondes) |
| `DB_CONN_HEALTH_CHECKS` | `True` | Validation des connexions avant réutilisation |

### Middleware

Le middleware `DatabaseResilienceMiddleware` est placé après `CorrelationIdMiddleware` dans la stack middleware :

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CorrelationIdMiddleware',
    'core.db_resilience.DatabaseResilienceMiddleware',  # Story 32.1
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
| `db_connection_lost` | WARNING | Connexion DB perdue, tentative de reconnexion |
| `db_connection_restored` | INFO | Reconnexion réussie après purge |
| `db_connection_retry_failed` | ERROR | Échec de la reconnexion |

Chaque événement inclut : `correlation_id`, `error_type`, `error_code`, `method`, `path`.

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
- Le middleware intercepte les erreurs qui passent et retente une fois
- Les requêtes pendant la fenêtre peuvent recevoir une erreur 500 si la base n'est pas encore disponible (Story 32.2 ajoutera le retry transactionnel)
