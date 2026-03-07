# Observabilité: Middleware et Logging

## Vue d'ensemble

Le backend implémente une observabilité complète via:

- **Correlation ID:** Traçabilité des requêtes bout en bout
- **Logging structuré:** JSON logs pour Splunk
- **Middleware:** Request/Response logging, security headers
- **Health check:** Vérification des dépendances

## Middleware

### Ordre des middleware

L'ordre est important dans `settings.py`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CorrelationIdMiddleware',           # 1. Correlation ID (premier)
    'core.middleware.RequestResponseLoggingMiddleware',  # 2. Request logging
    'core.middleware.SecurityHeadersMiddleware',         # 3. Security headers
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',             # 4. CORS
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'idp_auth.middleware.AuditAuthMiddleware',           # 5. Auth audit (dernier)
]
```

### CorrelationIdMiddleware

Génère et propage un ID de corrélation pour tracer les requêtes.

```python
class CorrelationIdMiddleware:
    """
    Middleware qui génère/propage X-Idp-Request-Id.

    - Si header X-Idp-Request-Id présent: utilise cette valeur
    - Sinon: génère un UUID
    - Stocke dans thread-local pour accès dans views/services
    - Bind à structlog contextvars pour inclusion auto dans logs
    - Ajoute au response header
    """

    def __call__(self, request):
        # Get or generate correlation ID
        correlation_id = request.META.get('HTTP_X_IDP_REQUEST_ID') or str(uuid.uuid4())

        # Store in thread-local
        set_correlation_id(correlation_id)

        # Add to request for easy access
        request.correlation_id = correlation_id

        # Bind to structlog
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = self.get_response(request)

        # Add to response headers
        response['X-Idp-Request-Id'] = correlation_id

        # Cleanup
        set_correlation_id(None)
        structlog.contextvars.unbind_contextvars('correlation_id')

        return response
```

**Accès au correlation ID:**

```python
from core.middleware import get_correlation_id

# Dans un service
correlation_id = get_correlation_id()
logger.info("action_created", correlation_id=correlation_id)

# Dans un ViewSet
correlation_id = request.correlation_id
```

### RequestResponseLoggingMiddleware

Log chaque requête HTTP avec contexte.

```python
class RequestResponseLoggingMiddleware:
    """
    Log request_received et request_completed pour chaque requête.

    Events logged:
    - request_received: method, path, correlation_id, user_id, ip_address, user_agent
    - request_completed: status_code, duration_ms, correlation_id, user_id

    Log levels:
    - INFO: 2xx success
    - WARNING: 4xx client errors
    - ERROR: 5xx server errors
    """

    def __call__(self, request):
        start_time = time.time()
        correlation_id = get_correlation_id()
        user_id = self._get_user_id(request)

        # Log request received
        logger.info(
            "request_received",
            correlation_id=correlation_id,
            method=request.method,
            path=request.path,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            user_id=user_id,
        )

        try:
            response = self.get_response(request)
            duration_ms = int((time.time() - start_time) * 1000)
            user_id = self._get_user_id(request)  # Re-check after auth

            log_data = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
            }

            if response.status_code >= 500:
                logger.error("request_completed", **log_data)
            elif response.status_code >= 400:
                logger.warning("request_completed", **log_data)
            else:
                logger.info("request_completed", **log_data)

            return response

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "request_failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.path,
                duration_ms=duration_ms,
                exception=str(e),
                exc_info=True,
            )
            raise
```

### SecurityHeadersMiddleware

Ajoute les headers de sécurité à toutes les réponses.

```python
class SecurityHeadersMiddleware:
    """
    Ajoute les security headers.

    Headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Cache-Control: no-store (pour routes /api/)
    """

    def __call__(self, request):
        response = self.get_response(request)

        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'

        return response
```

## Logging structuré

### Configuration structlog

**Fichier:** `core/apps.py`

```python
class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import structlog

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(LOG_LEVEL),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
```

### Utilisation

```python
import structlog

logger = structlog.get_logger(__name__)

# Log simple
logger.info("action_created", action_id=123, action_name="Test")

# Avec correlation_id (auto-ajouté via contextvars)
logger.info("profile_updated", profile_id=456)

# Erreur avec traceback
try:
    do_something()
except Exception:
    logger.error("operation_failed", exc_info=True)
```

### Format de sortie JSON

```json
{
  "event": "action_created",
  "action_id": 123,
  "action_name": "Test",
  "user_id": "42",
  "correlation_id": "a1b2c3d4-e5f6-...",
  "level": "info",
  "timestamp": "2026-02-05T10:30:00.000000Z"
}
```

### Conventions de logging

| Champ | Description |
|-------|-------------|
| `event` | Nom de l'événement (snake_case) |
| `correlation_id` | ID de corrélation de la requête |
| `user_id` | ID de l'utilisateur (si authentifié) |
| `level` | Niveau de log (info, warning, error) |
| `timestamp` | Timestamp ISO 8601 |

**Événements standards:**

| Event | Level | Description |
|-------|-------|-------------|
| `request_received` | info | Requête HTTP reçue |
| `request_completed` | info/warn/error | Requête HTTP terminée |
| `request_failed` | error | Requête HTTP échouée (exception) |
| `action_created` | info | Action créée |
| `action_updated` | info | Action modifiée |
| `profile_created` | info | Profil créé |
| `handled_exception` | warning | Exception gérée (4xx) |
| `unhandled_exception` | error | Exception non gérée (5xx) |

## Gestion des erreurs

### Exception Handler

**Fichier:** `core/exceptions.py`

```python
def custom_exception_handler(exc, context):
    """
    Handler d'exceptions personnalisé.

    Format de sortie:
    {
        "error": {
            "code": "NOT_FOUND",
            "message": "Action non trouvée",
            "details": {"action_id": 123}
        }
    }

    Logging:
    - 4xx: warning level
    - 5xx: error level avec traceback

    Sécurité:
    - 5xx: masque les détails internes, retourne message générique
    """
    request_context = _get_request_context(context)

    # Custom exceptions (expected)
    if isinstance(exc, NotFoundError):
        logger.warning("handled_exception", exception_type="NotFoundError", **request_context)
        resp = Response({"error": {"code": exc.code, "message": exc.message, "details": exc.details}}, status=404)
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    # ... autres exceptions custom ...

    # Unhandled exception (5xx)
    logger.error("unhandled_exception", exception_type=type(exc).__name__, exc_info=True, **request_context)
    resp = Response({"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred", "details": {}}}, status=500)
    resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
    return resp
```

### Classes d'exceptions custom

```python
class NotFoundError(Exception):
    def __init__(self, code="NOT_FOUND", message="Resource not found", details=None):
        self.code = code
        self.message = message
        self.details = details or {}

class BadRequestError(Exception):
    """400 Bad Request"""

class InvalidStateError(Exception):
    """400 Invalid State (ex: transition de statut invalide)"""

class UnauthorizedError(Exception):
    """401 Unauthorized"""

class ForbiddenError(Exception):
    """403 Forbidden"""
```

## Health Check

### Endpoint

```
GET /api/v1/health
```

### Vérifications

1. **Database:** Connexion Oracle
2. **Vault:** Connexion HashiCorp Vault (si configuré)
3. **ServiceNow:** Connexion ServiceNow (si configuré)

### Implémentation

```python
def health_check(request):
    """
    Health check endpoint.

    Returns:
        200 si tous les services sont up
        503 si un service est down
    """
    status = "healthy"
    checks = {}

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
        checks['database'] = 'up'
    except Exception as e:
        checks['database'] = 'down'
        status = "unhealthy"
        logger.error("health_check_failed", service="database", error=str(e))

    # Vault check (optional)
    if VAULT_ADDR:
        try:
            # Simple connectivity check
            checks['vault'] = 'up'
        except Exception:
            checks['vault'] = 'down'

    # ServiceNow check (optional)
    if SERVICENOW_INSTANCE_URL:
        try:
            checks['servicenow'] = 'up'
        except Exception:
            checks['servicenow'] = 'down'

    response_status = 200 if status == "healthy" else 503
    return Response({
        "data": {
            "status": status,
            **checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }, status=response_status)
```

### Réponse

```json
{
  "data": {
    "status": "healthy",
    "database": "up",
    "vault": "up",
    "servicenow": "up",
    "timestamp": "2026-02-05T10:30:00.000000Z"
  }
}
```

## CORS

### Configuration

```python
# settings.py

CORS_ALLOWED_ORIGINS = [
    os.getenv('CORS_ORIGIN', 'http://localhost:5173'),
]

CORS_ALLOW_CREDENTIALS = True  # Pour httpOnly refresh token

CORS_EXPOSE_HEADERS = [
    'X-Idp-Request-Id',  # Expose correlation ID au frontend
]

CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'x-idp-request-id',  # Allow frontend to pass correlation ID
    # ...
]
```

## Intégration Splunk

Les logs JSON sont envoyés à Splunk via le standard output. Configuration Splunk:

1. **Index:** `idp-portal`
2. **Sourcetype:** `_json`
3. **Host:** hostname du conteneur

### Recherches Splunk utiles

```spl
# Toutes les requêtes d'un correlation_id
index=idp-portal correlation_id="a1b2c3d4-..."

# Erreurs 5xx
index=idp-portal event="request_completed" status_code>=500

# Requêtes lentes (>1s)
index=idp-portal event="request_completed" duration_ms>1000

# Actions créées par utilisateur
index=idp-portal event="action_created" | stats count by user_id

# Erreurs non gérées
index=idp-portal event="unhandled_exception" | table timestamp exception_type correlation_id
```

## Bonnes pratiques

### 1. Toujours utiliser structlog

```python
# ❌ Mauvais
import logging
logger = logging.getLogger(__name__)
logger.info("Action created: %s", action.name)

# ✅ Bon
import structlog
logger = structlog.get_logger(__name__)
logger.info("action_created", action_id=action.id, action_name=action.name)
```

### 2. Propager le correlation_id

```python
# Dans les services
from core.middleware import get_correlation_id

correlation_id = get_correlation_id()
logger.info("operation_started", correlation_id=correlation_id)

# Pour appels externes
requests.post(url, headers={'X-Idp-Request-Id': correlation_id})
```

### 3. Niveaux de log appropriés

```python
# INFO: événements normaux
logger.info("action_created", ...)

# WARNING: erreurs attendues (client)
logger.warning("handled_exception", ...)

# ERROR: erreurs inattendues (serveur)
logger.error("unhandled_exception", exc_info=True, ...)
```

### 4. Ne pas logger de données sensibles

```python
# ❌ Mauvais
logger.info("user_login", password=password)

# ✅ Bon
logger.info("user_login", user_id=user.id)
```
