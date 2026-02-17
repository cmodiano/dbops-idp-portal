# Architecture Observabilité - Django Backend

Story M.8 - Middleware, Logging, Observabilité

## Vue d'ensemble

Le backend Django implémente une architecture de logging structuré JSON alignée sur les standards de la plateforme hébergeuse et compatible avec Splunk pour l'analyse centralisée des logs.

```
Django Backend → structlog JSON → Fichiers logs → Splunk Universal Forwarder → Splunk
```

## Format de log JSON standardisé

Chaque entrée de log suit un format JSON structuré avec des champs standardisés :

```json
{
  "timestamp": "2026-02-05T14:30:05.123456Z",
  "level": "info",
  "event": "request_completed",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "42",
  "path": "/api/v1/catalog/actions",
  "method": "GET",
  "status_code": 200,
  "duration_ms": 45
}
```

### Champs obligatoires

| Champ | Description | Exemple |
|-------|-------------|---------|
| `timestamp` | Date/heure ISO8601 UTC | `2026-02-05T14:30:05.123456Z` |
| `level` | Niveau de log (debug/info/warning/error/critical) | `info` |
| `event` | Nom sémantique de l'événement | `request_completed` |
| `correlation_id` | ID unique de requête pour traçabilité | `uuid-format` |

### Champs contextuels

| Champ | Description | Quand présent |
|-------|-------------|---------------|
| `user_id` | ID utilisateur authentifié | Requêtes authentifiées |
| `path` | Chemin de la requête HTTP | Logs de requête |
| `method` | Méthode HTTP | Logs de requête |
| `status_code` | Code de réponse HTTP | request_completed |
| `duration_ms` | Durée de traitement en ms | request_completed |
| `exception` | Message d'exception | request_failed |
| `service` | Service externe testé | health_check_failed |

## Événements de log

### Requêtes HTTP

| Événement | Niveau | Description |
|-----------|--------|-------------|
| `request_received` | INFO | Requête entrante |
| `request_completed` | INFO/WARNING/ERROR | Requête terminée (niveau selon status_code) |
| `request_failed` | ERROR | Exception non gérée |

### Authentification

| Événement | Niveau | Description |
|-----------|--------|-------------|
| `auth_dev_bypass_login` | INFO | Login bypass mode dev |
| `saml_login_redirect` | INFO | Redirection vers IdP |
| `saml_callback_success` | INFO | SAML assertion validée |
| `saml_callback_error` | ERROR | Erreur validation SAML |
| `saml_callback_no_profile` | WARNING | Aucun profil trouvé |
| `auth_unauthorized_access` | WARNING | Accès non autorisé 401 |

### Health Check

| Événement | Niveau | Description |
|-----------|--------|-------------|
| `health_check_failed` | ERROR/WARNING | Service externe en échec |

### Exceptions

| Événement | Niveau | Description |
|-----------|--------|-------------|
| `handled_exception` | WARNING | Exception métier gérée |
| `unhandled_exception` | ERROR | Exception non gérée |

## Niveaux de log

Suivant les conventions de l'architecture :

| Niveau | Usage | Exemples |
|--------|-------|----------|
| `DEBUG` | Détails techniques (pas en production) | Queries SQL, variables |
| `INFO` | Événements normaux | Requêtes, actions utilisateur |
| `WARNING` | Situations anormales mais non bloquantes | Timeout récupéré, auth failure |
| `ERROR` | Erreurs bloquantes | Exceptions, appels API échoués |
| `CRITICAL` | Défaillances système | DB down, Vault inaccessible |

## Propagation du Correlation ID

Le `correlation_id` est propagé à travers toutes les couches :

```
                            X-Idp-Request-Id
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CorrelationIdMiddleware                       │
│  • Génère UUID si absent                                        │
│  • Stocke dans thread-local (get_correlation_id())              │
│  • Bind dans structlog contextvars                              │
│  • Ajoute au header de réponse                                  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│              RequestResponseLoggingMiddleware                    │
│  • Log request_received avec correlation_id                     │
│  • Log request_completed avec correlation_id                    │
│  • Log request_failed avec correlation_id                       │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Views / Services                          │
│  • Logging avec correlation_id = get_correlation_id()           │
│  • AuditService.create_entry() avec correlation_id              │
│  • Appels externes avec header X-Idp-Request-Id                 │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `LOG_LEVEL` | Niveau de log minimum | `INFO` |
| `VAULT_ADDR` | URL du serveur Vault | `http://localhost:8200` |
| `SERVICENOW_INSTANCE_URL` | URL ServiceNow | `https://instance.service-now.com` |

### structlog

Configuration dans `core/logging.py` :

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # Correlation ID auto
        structlog.stdlib.filter_by_level,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
```

## Health Check

Endpoint: `GET /api/v1/health`

### Services vérifiés

| Service | Méthode | Timeout |
|---------|---------|---------|
| Oracle | `SELECT 1 FROM DUAL` | Default |
| Vault | `GET /v1/sys/health` | 5s |
| ServiceNow | `GET /api/now/table/sys_metadata` | 5s |

### Format de réponse

```json
{
  "data": {
    "status": "healthy",
    "timestamp": "2026-02-05T14:30:05.123Z",
    "oracle": "connected",
    "vault": "reachable",
    "servicenow": "reachable"
  }
}
```

### Codes HTTP

| Code | Status | Description |
|------|--------|-------------|
| 200 | `healthy` | Tous les services OK |
| 503 | `degraded` | Au moins un service KO |

## Middleware Stack

Ordre d'exécution dans `settings.py` :

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CorrelationIdMiddleware',      # 1. Génère/propage correlation_id
    'core.middleware.RequestResponseLoggingMiddleware',  # 2. Log requêtes/réponses
    'core.middleware.SecurityHeadersMiddleware',    # 3. Headers sécurité
    # ... autres middleware Django ...
    'idp_auth.middleware.AuditAuthMiddleware',      # Dernier: audit auth
]
```

## Parité avec FastAPI

Le format de logging Django est identique au backend FastAPI pour permettre l'analyse unifiée dans Splunk :

| Aspect | Django | FastAPI |
|--------|--------|---------|
| Librairie | structlog | structlog |
| Format | JSON | JSON |
| Timestamp | ISO8601 UTC | ISO8601 UTC |
| Correlation Header | X-Idp-Request-Id | X-Idp-Request-Id |
| Events | request_received, request_completed, request_failed | request_completed |
| Health Check Format | Identique | Identique |
