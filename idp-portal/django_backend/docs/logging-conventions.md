# Conventions de Logging - Django Backend

Story M.8 - Standards de logging pour le code Django

## Librairie

Utiliser `structlog` pour tous les logs. Import standard :

```python
import structlog
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)
```

## Format d'appel

Utiliser des keyword arguments (pas de `extra={}` comme avec logging standard) :

```python
# Correct - structlog
logger.info(
    "event_name",
    user_id=user.id,
    action_id=action.id,
    correlation_id=get_correlation_id()
)

# Incorrect - ancien format logging standard
logger.info("event_name", extra={"user_id": user.id})
```

## Noms d'événements

Utiliser des noms sémantiques en snake_case décrivant l'action :

```python
# Correct
logger.info("user_created", username=username)
logger.info("action_published", action_id=action.id)
logger.warning("saml_callback_no_profile", ad_groups=groups)
logger.error("vault_connection_failed", error=str(e))

# Incorrect
logger.info("Created user")
logger.info(f"Action {action_id} published")
```

## Niveaux de log

| Niveau | Usage | Exemple |
|--------|-------|---------|
| `DEBUG` | Détails techniques pour debug | Queries SQL, variables intermédiaires |
| `INFO` | Événements normaux attendus | Requêtes réussies, actions métier |
| `WARNING` | Situations anormales récupérables | Auth échec, timeout récupéré |
| `ERROR` | Erreurs nécessitant attention | Exceptions, appels API échoués |
| `CRITICAL` | Défaillances système | DB down, services critiques inaccessibles |

### Règles de niveau

```python
# INFO: Opérations normales
logger.info("execution_created", execution_id=exec.id)
logger.info("user_login_success", username=user.username)

# WARNING: Anormal mais géré
logger.warning("rate_limit_exceeded", user_id=user.id)
logger.warning("cache_miss", key=cache_key)

# ERROR: Échec nécessitant investigation
logger.error("external_api_failed", service="vault", error=str(e))
logger.error("database_query_failed", query=query, exc_info=True)

# CRITICAL: Système en danger
logger.critical("database_connection_lost", dsn=dsn)
logger.critical("all_health_checks_failed")
```

## Correlation ID

Toujours inclure le `correlation_id` pour la traçabilité :

```python
from core.middleware import get_correlation_id

correlation_id = get_correlation_id()
logger.info(
    "action_executed",
    action_id=action.id,
    user_id=user.id,
    correlation_id=correlation_id
)
```

Note: Le `correlation_id` est aussi auto-injecté via `structlog.contextvars.merge_contextvars` si bindé dans le middleware. L'inclure explicitement garantit sa présence.

## Exceptions

Pour les exceptions, utiliser `exc_info=True` pour capturer le traceback :

```python
try:
    result = external_api.call()
except Exception as e:
    logger.error(
        "external_api_call_failed",
        service="vault",
        endpoint="/v1/secret/data",
        error=str(e),
        correlation_id=get_correlation_id(),
        exc_info=True  # Capture le traceback
    )
    raise
```

## Gestion des exceptions (Story 17.6)

### Règle : Éviter les `except Exception` trop larges

**Mauvais :**

```python
try:
    result = api.call()
except Exception:
    return None  # Masque toutes les erreurs silencieusement
```

**Bon - Exceptions spécifiques :**

```python
try:
    result = api.call()
except (requests.HTTPError, requests.Timeout) as e:
    logger.error("api_call_failed", service="api", error=str(e), exc_info=True)
    raise
```

**Acceptable - Broad catch justifié :**

```python
try:
    result = dynamic_plugin.execute()
except Exception as e:
    # Story 17.6: Justified broad catch - Plugin can raise any exception
    logger.error(
        "plugin_execution_failed",
        plugin=plugin_name,
        error=str(e),
        error_type=type(e).__name__,
        correlation_id=get_correlation_id(),
        exc_info=True,
    )
    return {"status": "failed", "error": str(e)}
```

### Pattern de gestion d'erreur standard

1. **Exceptions spécifiques d'abord** (ex: `ValueError`, `KeyError`, `requests.HTTPError`)
2. **Broad catch seulement si justifié** avec commentaire `# Story 17.6: Justified broad catch - [raison]`
3. **Toujours capturer `as e`** pour permettre le logging
4. **Logging obligatoire** avec `exc_info=True` pour erreurs inattendues
5. **Toujours inclure `correlation_id`** pour traçabilité

### Exceptions par domaine

| Domaine | Exceptions spécifiques |
|---------|----------------------|
| Django ORM | `ObjectDoesNotExist`, `MultipleObjectsReturned`, `IntegrityError`, `ValidationError`, `DatabaseError`, `OperationalError` |
| API externes | `requests.HTTPError`, `requests.Timeout`, `requests.ConnectionError` |
| Validation données | `ValueError`, `KeyError`, `TypeError`, `AttributeError` |
| Celery | `Retry`, `MaxRetriesExceededError`, `SoftTimeLimitExceeded` |
| Croniter | `CroniterBadCronError`, `CroniterBadDateError` |

### Story 22.11 — Complétion audit exception handling

**Règles complémentaires Story 22.11 :**

1. **OBLIGATOIRE :** Tous les `except Exception:` doivent avoir `as e` pour capturer la variable
2. **OBLIGATOIRE :** Logging avec `exc_info=True` pour exceptions inattendues
3. **OBLIGATOIRE :** Ajouter `error_type=type(e).__name__` dans tous les logs d'exception
4. **OBLIGATOIRE :** Commentaire justification `# Story 22.11: Justified broad catch - [raison]` si broad catch nécessaire
5. **OBLIGATOIRE :** Commentaire `# Story 17.6: Justified broad catch - [raison]` reste valide pour les broad catches existants

**Exceptions ORM Django préférées :**

```python
from django.db import DatabaseError, IntegrityError, OperationalError
from django.core.exceptions import ValidationError
```

Plus spécifiques que `Exception` pour erreurs DB.

**Pattern Celery tasks :**

```python
from core.middleware import get_correlation_id

try:
    # ... task logic ...
except (DatabaseError, IntegrityError) as e:
    logger.error(
        "task_db_error",
        error=str(e),
        error_type=type(e).__name__,
        exc_info=True,
        correlation_id=get_correlation_id(),  # OBLIGATOIRE pour traçabilité
    )
    raise  # Re-raise pour retry Celery
except Exception as e:
    # Story 22.11: Justified broad catch - Task must handle all failure modes
    logger.error(
        "task_unexpected_error",
        error=str(e),
        error_type=type(e).__name__,
        exc_info=True,
        correlation_id=get_correlation_id(),  # OBLIGATOIRE pour traçabilité
    )
    raise
```

## Données sensibles

**Ne jamais logger** :
- Mots de passe
- Tokens JWT complets
- Clés API
- Données personnelles (PII) non nécessaires

```python
# Incorrect
logger.info("user_login", password=password, token=access_token)

# Correct - logger seulement ce qui est nécessaire
logger.info("user_login", username=username, user_id=user.id)
```

## Exemples par domaine

### Authentification

```python
logger.info("saml_login_redirect", sso_url=sso_url, correlation_id=cid)
logger.info("saml_callback_success", username=username, profile=profile, correlation_id=cid)
logger.warning("auth_token_expired", user_id=user_id, correlation_id=cid)
logger.error("saml_validation_failed", errors=errors, correlation_id=cid)
```

### Catalogue

```python
logger.info("action_created", action_id=action.id, name=action.name, correlation_id=cid)
logger.info("action_published", action_id=action.id, user_id=user.id, correlation_id=cid)
logger.warning("action_transition_invalid", action_id=action.id, from_status=status, correlation_id=cid)
```

### Exécutions

```python
logger.info("execution_started", execution_id=exec.id, action_id=action.id, correlation_id=cid)
logger.info("execution_completed", execution_id=exec.id, status="success", duration_ms=duration, correlation_id=cid)
logger.error("execution_failed", execution_id=exec.id, error=error, correlation_id=cid)
```

### Intégrations externes

```python
logger.info("vault_secret_retrieved", path=secret_path, correlation_id=cid)
logger.warning("servicenow_timeout", instance=instance, timeout_ms=timeout, correlation_id=cid)
logger.error("aap_job_launch_failed", job_template=template, error=error, correlation_id=cid)
```

## Tests et debugging

En mode DEBUG, des logs supplémentaires peuvent être ajoutés :

```python
import os

if os.getenv('LOG_LEVEL', 'INFO').upper() == 'DEBUG':
    logger.debug("query_parameters", params=params)
```

## Migration depuis logging standard

Si vous migrez du code existant :

```python
# Avant (logging standard)
import logging
logger = logging.getLogger(__name__)
logger.info("event", extra={"key": "value"})

# Après (structlog)
import structlog
logger = structlog.get_logger(__name__)
logger.info("event", key="value")
```
