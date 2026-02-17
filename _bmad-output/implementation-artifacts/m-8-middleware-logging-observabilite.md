# Story M.8: Middleware, logging, observabilité

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want le middleware (CORS, correlation ID, erreurs), le logging structuré et l'observabilité alignés sur la plateforme et les NFR,
So que le portail Django soit monitorable et cohérent avec le reste de l'infra.

## Acceptance Criteria

1. **Given** le backend Django
   **When** une requête entre et sort
   **Then** un correlation ID (X-Idp-Request-Id ou équivalent) est généré et propagé dans les logs et réponses si applicable
   **And** les logs sont structurés (JSON) avec timestamp, level, event, correlation_id, user_id (NFR, convention hébergeur)
   **And** les exceptions sont catchées et renvoyées au client dans le format d'erreur actuel (enveloppe error, codes HTTP)
   **And** CORS est configuré pour les origines autorisées (frontend)
   **And** le health check reflète l'état DB (et optionnellement Vault, ServiceNow) pour le monitoring

## Tasks / Subtasks

### Task 1: Analyser l'implémentation existante des middleware et logging Django/FastAPI (AC: #1)

- [x] Subtask 1.1: Analyser `django_backend/core/middleware.py` — CorrelationIdMiddleware et SecurityHeadersMiddleware existants
- [x] Subtask 1.2: Analyser `django_backend/idp_auth/middleware.py` — AuditAuthMiddleware (auth failures logging)
- [x] Subtask 1.3: Analyser patterns de logging actuels dans Django views (logger.info/warning/error avec extra dict)
- [x] Subtask 1.4: Analyser `backend/app/core/logging.py` — Configuration structlog JSON FastAPI (référence)
- [x] Subtask 1.5: Analyser `backend/app/core/middleware.py` — Request/Response logging middleware FastAPI
- [x] Subtask 1.6: Documenter les écarts entre Django et FastAPI logging (standard logging vs structlog)
- [x] Subtask 1.7: Décider de la stratégie logging pour Django : adopter structlog ou enrichir standard logging

### Task 2: Implémenter ou améliorer le logging structuré JSON (AC: #1)

- [x] Subtask 2.1: Installer `structlog` dans `django_backend/requirements.txt` si stratégie structlog adoptée
- [x] Subtask 2.2: Créer ou mettre à jour `core/logging.py` — Configuration logging structuré JSON
- [x] Subtask 2.3: Dans logging config, définir format JSON avec champs : timestamp (ISO8601 UTC), level, event, correlation_id, user_id, path, method, status_code, duration_ms
- [x] Subtask 2.4: Configurer les processors structlog : TimeStamper(fmt="iso", utc=True), add_log_level, StackInfoRenderer(), format_exc_info
- [x] Subtask 2.5: Configurer le renderer JSON pour sortie structurée
- [x] Subtask 2.6: Intégrer la config dans `idp_backend/settings.py` — LOGGING dict Django pointant vers structlog config
- [x] Subtask 2.7: Si standard logging : créer custom JsonFormatter pour formater logs en JSON avec même structure

### Task 3: Créer ou améliorer le middleware de logging des requêtes/réponses (AC: #1)

- [x] Subtask 3.1: Créer `core/middleware.py` — RequestResponseLoggingMiddleware (ou améliorer existant)
- [x] Subtask 3.2: Dans middleware, logger chaque requête entrante : log "request_received" avec method, path, correlation_id, user_id, ip_address, user_agent
- [x] Subtask 3.3: Dans middleware, mesurer le temps de traitement (start_time → end_time)
- [x] Subtask 3.4: Dans middleware, logger chaque réponse sortante : log "request_completed" avec status_code, duration_ms, correlation_id, user_id
- [x] Subtask 3.5: Gérer les exceptions non catchées : logger "request_failed" avec exception, traceback, correlation_id
- [x] Subtask 3.6: Ajouter RequestResponseLoggingMiddleware dans MIDDLEWARE après CorrelationIdMiddleware

### Task 4: Améliorer CorrelationIdMiddleware et propagation (AC: #1)

- [x] Subtask 4.1: Vérifier `core/middleware.py` — CorrelationIdMiddleware génère X-Idp-Request-Id si absent
- [x] Subtask 4.2: S'assurer que get_correlation_id() et set_correlation_id() sont utilisés via thread-local
- [x] Subtask 4.3: Ajouter correlation_id au contexte structlog si structlog adopté (bind(correlation_id=...))
- [x] Subtask 4.4: Vérifier que correlation_id est propagé dans tous les appels AuditService.create_entry()
- [x] Subtask 4.5: Vérifier que tous les appels externes (Vault, ServiceNow, plateformes) propagent X-Idp-Request-Id en header

### Task 5: Améliorer la gestion d'erreurs et exception handler (AC: #1)

- [x] Subtask 5.1: Vérifier `core/exceptions.py` — Custom exception handler pour DRF
- [x] Subtask 5.2: S'assurer que toutes les exceptions retournent format {"error": {"code": "...", "message": "...", "details": {...}}}
- [x] Subtask 5.3: Logger toutes les exceptions non gérées avec log "unhandled_exception" incluant correlation_id, path, user_id, traceback
- [x] Subtask 5.4: Pour les 500 errors, masquer les détails internes au client (message générique) mais logger le détail complet
- [x] Subtask 5.5: Ajouter correlation_id dans les réponses d'erreur si pertinent (header X-Idp-Request-Id dans response)

### Task 6: Améliorer le health check pour observabilité (AC: #1)

- [x] Subtask 6.1: Analyser `core/views.py` — Endpoint GET /api/v1/health actuel (test connexion Oracle)
- [x] Subtask 6.2: Étendre health check pour vérifier Vault : appel API GET /sys/health (timeout 5s)
- [x] Subtask 6.3: Étendre health check pour vérifier ServiceNow : appel API GET /api/now/table/sys_metadata (timeout 5s)
- [x] Subtask 6.4: Si tous les services répondent OK → status "healthy" (200)
- [x] Subtask 6.5: Si au moins un service échoue → status "degraded" (503) avec détails des services en échec
- [x] Subtask 6.6: Enrichir réponse health check : {"status": "healthy|degraded", "oracle": "connected|disconnected", "vault": "reachable|unreachable", "servicenow": "reachable|unreachable", "timestamp": "ISO8601"}
- [x] Subtask 6.7: Logger chaque health check failure avec log "health_check_failed" incluant service, error
- [x] Subtask 6.8: Ajouter tests unitaires pour health check (mock DB, Vault, ServiceNow)

### Task 7: Configurer CORS pour sécurité (AC: #1)

- [x] Subtask 7.1: Vérifier configuration CORS dans `idp_backend/settings.py` — CORS_ALLOWED_ORIGINS
- [x] Subtask 7.2: S'assurer que CORS_ALLOWED_ORIGINS liste uniquement les origines autorisées (frontend uniquement)
- [x] Subtask 7.3: Configurer CORS_ALLOW_CREDENTIALS = True pour cookies httpOnly
- [x] Subtask 7.4: Vérifier que les headers CORS appropriés sont ajoutés (Access-Control-Allow-Origin, etc.)
- [x] Subtask 7.5: Tester CORS en mode dev avec frontend local (http://localhost:5173) et production (domaine prod)

### Task 8: Ajouter des niveaux de log appropriés selon les conventions (AC: #1)

- [x] Subtask 8.1: Auditer tous les modules Django pour identifier les logs inappropriés (logger.info au lieu de warning, etc.)
- [x] Subtask 8.2: Définir les conventions de niveaux de log :
  - DEBUG : Détails techniques pour debugging local (pas en prod)
  - INFO : Événements normaux (requêtes, actions utilisateur)
  - WARNING : Situations anormales mais non bloquantes (échec récupérable, timeout récupéré)
  - ERROR : Erreurs bloquantes nécessitant attention (échec API externe, exception non prévue)
  - CRITICAL : Défaillances système (DB down, Vault inaccessible de façon prolongée)
- [x] Subtask 8.3: Corriger les niveaux de log dans les modules existants selon conventions
- [x] Subtask 8.4: Documenter les conventions de logging dans `docs/logging-conventions.md`

### Task 9: Ajouter logging contextuel dans les services critiques (AC: #1)

- [x] Subtask 9.1: Dans `idp_auth/services.py` — AuthService : logger login/logout/refresh avec user_id, correlation_id
- [x] Subtask 9.2: Dans `profiles/services.py` — ProfileService : logger résolution profils avec ad_groups, resolved_profiles, correlation_id
- [x] Subtask 9.3: Dans `catalog/services.py` — CatalogService : logger actions CRUD avec action_id, user_id, correlation_id
- [x] Subtask 9.4: Dans `executions/services.py` — ExecutionService : logger soumission/état exécutions avec execution_id, action_id, user_id, status, correlation_id
- [x] Subtask 9.5: Dans `integrations/services.py` — IntegrationService : logger appels externes avec integration_id, platform, status, duration_ms, correlation_id

### Task 10: Créer tests pour middleware et logging (AC: #1)

- [x] Subtask 10.1: Créer `core/tests/test_middleware.py` — Tests pour RequestResponseLoggingMiddleware
- [x] Subtask 10.2: Tester que chaque requête génère logs "request_received" et "request_completed"
- [x] Subtask 10.3: Tester que correlation_id est présent dans tous les logs
- [x] Subtask 10.4: Tester que duration_ms est calculé correctement
- [x] Subtask 10.5: Tester que les exceptions non gérées sont loggées avec "request_failed"
- [x] Subtask 10.6: Créer `core/tests/test_health_check.py` — Tests pour health check étendu
- [x] Subtask 10.7: Tester health check avec DB OK + Vault OK + ServiceNow OK → 200 healthy
- [x] Subtask 10.8: Tester health check avec DB KO → 503 degraded
- [x] Subtask 10.9: Tester health check avec Vault KO → 503 degraded avec détails

### Task 11: Documenter l'architecture observabilité et runbook (AC: #1)

- [x] Subtask 11.1: Créer `docs/observability-architecture.md` — Documenter l'architecture de logging structuré
- [x] Subtask 11.2: Documenter le format des logs JSON avec exemples
- [x] Subtask 11.3: Documenter les niveaux de log et conventions
- [x] Subtask 11.4: Documenter la propagation du correlation_id à travers les couches
- [x] Subtask 11.5: Créer `docs/observability-runbook.md` — Procédures de monitoring et dépannage
- [x] Subtask 11.6: Documenter comment interroger les logs structurés (requêtes Splunk)
- [x] Subtask 11.7: Documenter les alertes recommandées (health check failures, error rate, slow requests)

### Task 12: Valider la parité avec FastAPI et aligner les patterns (AC: #1)

- [x] Subtask 12.1: Comparer le format de logs JSON Django vs FastAPI (même structure de champs)
- [x] Subtask 12.2: Vérifier que les mêmes événements sont loggués (request_received, request_completed, request_failed, health_check_failed)
- [x] Subtask 12.3: Vérifier que correlation_id est propagé de la même manière
- [x] Subtask 12.4: Vérifier que le health check a le même format de réponse
- [x] Subtask 12.5: Documenter les écarts acceptables entre Django et FastAPI (si applicable)
- [x] Subtask 12.6: Mettre à jour `docs/drf-api-migration-notes.md` avec les notes de cette story

## Dev Notes

### Context from Previous Stories

**Story M.1 - Bootstrap Django établi:**
- Projet Django créé avec structure d'apps: `catalog`, `profiles`, `idp_auth`, `integrations`, `core`, `executions`
- Configuration DRF en place (REST_FRAMEWORK dans settings.py)
- Format de réponse API préservé (enveloppe data/error, snake_case)

**Story M.7 - Authentification SAML complète:**
- CorrelationIdMiddleware déjà implémenté dans core/middleware.py
- SecurityHeadersMiddleware déjà implémenté
- AuditAuthMiddleware pour logging auth failures dans idp_auth/middleware.py
- Logging standard Python avec extra dict pour contexte
- Middleware order établi : CorrelationId → SecurityHeaders → ... → AuditAuth

**Patterns de logging existants:**
- Standard Python `logging.getLogger(__name__)` utilisé partout
- Logs avec extra dict : `logger.info("event", extra={"correlation_id": ..., "user_id": ...})`
- Semantic event names : "saml_login_redirect", "auth_dev_bypass_login", "saml_callback_success", etc.
- Pas de structlog actuellement — logs non structurés JSON

**Health check actuel:**
- Endpoint GET /api/v1/health implémenté dans core/views.py
- Teste uniquement connexion Oracle
- Retourne 200 si healthy, 503 si degraded
- Format : {"data": {"status": "healthy|degraded", "oracle": "connected|disconnected"}}

**Exception handling établi:**
- Custom exception hierarchy : NotFoundError, BadRequestError, UnauthorizedError, ForbiddenError, InvalidStateError
- Custom exception handler dans core/exceptions.py
- Format erreur : {"error": {"code": "...", "message": "...", "details": {...}}}

### Architecture Compliance

**Contrainte critique :** Le logging structuré JSON est une décision architecturale CRITIQUE (Architecture#Core Decisions). Doit être en place dès le skeleton backend pour envoi vers Splunk.

**Architecture de logging (depuis Architecture#Infrastructure & Deployment):**
```
Django Backend → structlog JSON → Fichiers logs → Splunk Universal Forwarder → Splunk
```

**Décisions architecturales applicables:**

| Decision | Choix | Source |
|----------|-------|--------|
| Format de log | JSON structuré avec champs standardisés | Architecture#Infrastructure & Deployment |
| Librairie | structlog (Python) | Architecture#Infrastructure & Deployment |
| Destination | Fichiers logs collectés par Splunk Forwarder | Architecture#Infrastructure & Deployment |
| Correlation ID | X-Idp-Request-Id généré par middleware, propagé partout | Architecture#Core Decisions |
| Health check | GET /api/v1/health vérifie DB + Vault + ServiceNow | Architecture#Infrastructure & Deployment |
| CORS | Restreint aux origines frontend uniquement | Architecture#API & Communication Patterns |

**Format de log JSON standardisé (depuis Architecture#Implementation Patterns):**
```json
{
  "timestamp": "2026-02-05T14:30:05.123Z",
  "level": "info",
  "event": "request_completed",
  "correlation_id": "req-abc-456",
  "user_id": "marc.dupont",
  "path": "/api/v1/catalog/actions",
  "method": "GET",
  "status_code": 200,
  "duration_ms": 45
}
```

**Niveaux de log (depuis Architecture#Implementation Patterns):**
- **DEBUG** : Détails techniques (pas en production)
- **INFO** : Événements normaux (requêtes, succès)
- **WARNING** : Situations anormales mais récupérables
- **ERROR** : Erreurs bloquantes nécessitant attention
- **CRITICAL** : Défaillances système (DB down, etc.)

**Règles de propagation correlation_id (Architecture#Validation & Quality Rules):**
- Généré par middleware si absent
- Propagé dans tous les logs via bind() ou extra dict
- Propagé dans tous les appels externes (headers X-Idp-Request-Id)
- Inclus dans toutes les entrées audit_log

### Technical Requirements

**Stratégie logging recommandée : Adopter structlog**

Raisons :
1. **Parité avec FastAPI** : Le backend FastAPI utilise structlog pour logs JSON
2. **Format JSON natif** : structlog génère JSON structuré nativement
3. **Context binding** : structlog permet bind(correlation_id=..., user_id=...) pour propagation automatique
4. **Processors** : Facilite ajout timestamp ISO8601, stack traces, etc.
5. **Intégration Django** : structlog s'intègre bien avec le système de logging Django

**Configuration structlog recommandée:**

```python
# core/logging.py
import structlog
from structlog.processors import TimeStamper, add_log_level, StackInfoRenderer, format_exc_info, JSONRenderer

def configure_structlog():
    """Configure structlog for structured JSON logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # Merge context from contextvars
            add_log_level,  # Add log level
            TimeStamper(fmt="iso", utc=True),  # ISO8601 UTC timestamp
            StackInfoRenderer(),  # Render stack info
            format_exc_info,  # Format exceptions
            JSONRenderer()  # Render as JSON
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

**Usage dans les services:**

```python
import structlog
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

class AuthService:
    def create_or_update_user(self, username, display_name, profile, saml_subject):
        correlation_id = get_correlation_id()
        logger.info(
            "user_created",
            correlation_id=correlation_id,
            username=username,
            profile=profile,
        )
        # ...
```

**Middleware de logging des requêtes/réponses:**

```python
# core/middleware.py
import time
import structlog
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

class RequestResponseLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        correlation_id = get_correlation_id()
        user_id = str(request.user.id) if request.user.is_authenticated else None

        # Log requête entrante
        logger.info(
            "request_received",
            correlation_id=correlation_id,
            method=request.method,
            path=request.path,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            user_id=user_id,
        )

        try:
            response = self.get_response(request)
            duration_ms = int((time.time() - start_time) * 1000)

            # Log réponse sortante
            logger.info(
                "request_completed",
                correlation_id=correlation_id,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_id=user_id,
            )

            return response
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "request_failed",
                correlation_id=correlation_id,
                exception=str(e),
                duration_ms=duration_ms,
                user_id=user_id,
                exc_info=True,
            )
            raise

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
```

**Health check étendu:**

```python
# core/views.py
import structlog
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import requests

logger = structlog.get_logger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint returning service status."""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Test database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            health_data["oracle"] = "connected"
    except Exception as e:
        logger.error("health_check_failed", service="oracle", error=str(e))
        health_data["oracle"] = "disconnected"
        health_data["status"] = "degraded"

    # Test Vault connection (optional)
    try:
        vault_url = settings.VAULT_ADDR
        response = requests.get(f"{vault_url}/v1/sys/health", timeout=5)
        if response.status_code == 200:
            health_data["vault"] = "reachable"
        else:
            raise Exception(f"Vault returned {response.status_code}")
    except Exception as e:
        logger.warning("health_check_failed", service="vault", error=str(e))
        health_data["vault"] = "unreachable"
        health_data["status"] = "degraded"

    # Test ServiceNow connection (optional)
    try:
        servicenow_url = settings.SERVICENOW_INSTANCE_URL
        response = requests.get(
            f"{servicenow_url}/api/now/table/sys_metadata",
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if response.status_code == 200:
            health_data["servicenow"] = "reachable"
        else:
            raise Exception(f"ServiceNow returned {response.status_code}")
    except Exception as e:
        logger.warning("health_check_failed", service="servicenow", error=str(e))
        health_data["servicenow"] = "unreachable"
        health_data["status"] = "degraded"

    response_data = {"data": health_data}
    http_status = status.HTTP_200_OK if health_data["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(response_data, status=http_status)
```

### Library/Framework Requirements

**Dépendances à ajouter:**

- `structlog>=24.1.0` — Logging structuré JSON
- `requests>=2.31.0` — Appels HTTP pour health check (Vault, ServiceNow)

**Versions vérifiées (février 2026):**
- structlog 24.1.0 stable — Compatible Django, Python 3.12+
- requests 2.31.0 stable — Widely used, stable

### File Structure Requirements

**Structure Django cible:**

```
idp-portal/django_backend/
├── core/
│   ├── logging.py              # Configuration structlog JSON (NOUVEAU)
│   ├── middleware.py           # CorrelationId, SecurityHeaders, RequestResponseLogging (MODIFIÉ)
│   ├── views.py                # Health check étendu (MODIFIÉ)
│   ├── exceptions.py           # Custom exception handler avec logging (MODIFIÉ)
│   └── tests/
│       ├── test_middleware.py  # Tests RequestResponseLoggingMiddleware (NOUVEAU)
│       └── test_health_check.py # Tests health check étendu (MODIFIÉ)
├── idp_backend/
│   └── settings.py             # Configuration LOGGING avec structlog (MODIFIÉ)
└── docs/
    ├── observability-architecture.md # Architecture observabilité (NOUVEAU)
    ├── observability-runbook.md      # Runbook monitoring (NOUVEAU)
    ├── logging-conventions.md        # Conventions de logging (NOUVEAU)
    └── drf-api-migration-notes.md    # Notes migration (MODIFIÉ)
```

### Testing Requirements

**Tests à créer:**

1. **Tests middleware de logging:**
   - test_request_response_logging_success
   - test_request_response_logging_includes_correlation_id
   - test_request_response_logging_includes_duration
   - test_request_response_logging_authenticated_user
   - test_request_response_logging_unauthenticated
   - test_request_response_logging_exception

2. **Tests health check étendu:**
   - test_health_check_all_services_up (→ 200)
   - test_health_check_oracle_down (→ 503)
   - test_health_check_vault_unreachable (→ 503)
   - test_health_check_servicenow_unreachable (→ 503)
   - test_health_check_response_format

3. **Tests propagation correlation_id:**
   - test_correlation_id_generated_if_absent
   - test_correlation_id_preserved_from_header
   - test_correlation_id_in_all_logs
   - test_correlation_id_in_audit_entries

**Commandes de test:**
```bash
pytest core/tests/test_middleware.py
pytest core/tests/test_health_check.py
pytest --cov=core --cov-report=html
```

### Previous Story Intelligence

**Apprentissages de Story M.7:**
- CorrelationIdMiddleware déjà en place et fonctionnel
- Thread-local storage pour get_correlation_id() et set_correlation_id()
- AuditAuthMiddleware pattern établi pour logging ciblé
- Standard Python logging utilisé partout — pas de structlog
- Format logs actuel : logger.info("event", extra={...})

**Patterns de logging établis dans Django:**
- Semantic event names : "saml_login_redirect", "auth_dev_bypass_login", etc.
- Extra dict pour contexte : correlation_id, user_id, ip_address, etc.
- Logging des erreurs avec exc_info=True pour tracebacks
- AuditService.create_entry() pour audit immutable

**FastAPI logging comme référence:**
- structlog JSON avec processors pour timestamp ISO8601, stack traces, JSON rendering
- Request/Response middleware loggant toutes les requêtes
- Correlation ID propagé via contextvars.ContextVar
- Health check testant DB + Vault + ServiceNow

**Ordre des middleware établi (M.7):**
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CorrelationIdMiddleware',      # 1er pour correlation ID
    'core.middleware.SecurityHeadersMiddleware',    # 2ème pour security headers
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'idp_auth.middleware.AuditAuthMiddleware',      # Dernier pour audit auth
]
```

**Insérer RequestResponseLoggingMiddleware APRÈS CorrelationIdMiddleware, AVANT SecurityHeadersMiddleware pour capturer toutes les requêtes avec correlation_id disponible.**

### Git Intelligence

**Derniers commits pertinents:**
- `m-7` — Authentification SAML et sécurité - Code review fixes (middleware CorrelationId établi)
- `m-6` — API REST auth, health, integrations - Health check base implémenté
- `m-3` — Migration repositories FastAPI vers Django ORM - AuditService complet

**Pattern de commit à suivre:**
```
feat(m-8): Middleware, logging, observabilité - Django structlog JSON
```

### Project Context Reference

**Contexte Epic M:**
- Migration FastAPI → Django REST pour arrimage plateforme hébergeuse
- Parité fonctionnelle et contractuelle avec API actuelle (OpenAPI / contrats frontend)
- Backend uniquement (API, couche données, auth, config, middleware, tests)

**Contraintes critiques:**
- Logging structuré JSON obligatoire (décision architecturale CRITIQUE)
- Format de log identique FastAPI pour faciliter analyse Splunk
- Correlation ID propagé partout (logs, audit, appels externes)
- Health check détaillé pour monitoring Dynatrace et load balancer

**Alignement plateforme hébergeuse:**
- Stack cible Django + DRF (même conventions que plateforme)
- Logging JSON pour Splunk (standard hébergeur)
- Health check pour monitoring centralisé

### References

- [Source: _bmad-output/planning-artifacts/epic-migration-fastapi-django.md#Story-M.8] - Story M.8 : Middleware, logging, observabilité
- [Source: _bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment] - Décisions architecturales logging structlog JSON → Splunk
- [Source: _bmad-output/planning-artifacts/architecture.md#Core Architectural Decisions] - Structured logging JSON vers Splunk — décision CRITIQUE
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns] - Format de log JSON standardisé, niveaux de log
- [Source: idp-portal/backend/app/core/logging.py] - Configuration structlog FastAPI (référence)
- [Source: idp-portal/backend/app/core/middleware.py] - Request/Response logging middleware FastAPI (référence)
- [Source: idp-portal/django_backend/core/middleware.py] - CorrelationIdMiddleware et SecurityHeadersMiddleware existants
- [Source: idp-portal/django_backend/idp_auth/middleware.py] - AuditAuthMiddleware pattern (M.7)
- [Source: idp-portal/django_backend/core/views.py] - Health check base actuel
- [Source: idp-portal/django_backend/idp_auth/views.py] - Patterns de logging avec extra dict (M.7)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- **Task 1 Complete**: Analyse complète des middleware et logging existants Django/FastAPI. Décision: adopter structlog pour parité.
- **Task 2 Complete**: Configuration structlog créée dans core/logging.py avec processors JSON, timestamp ISO8601 UTC, merge_contextvars.
- **Task 3 Complete**: RequestResponseLoggingMiddleware créé avec logs request_received, request_completed, request_failed selon niveau.
- **Task 4 Complete**: CorrelationIdMiddleware amélioré avec bind structlog.contextvars pour propagation automatique.
- **Task 5 Complete**: Exception handler enrichi avec logging structuré, masquage détails internes, header X-Idp-Request-Id.
- **Task 6 Complete**: Health check étendu pour vérifier Oracle + Vault + ServiceNow avec timestamp ISO8601.
- **Task 7 Complete**: Configuration CORS complète avec CORS_EXPOSE_HEADERS et CORS_ALLOW_HEADERS pour X-Idp-Request-Id.
- **Task 8 Complete**: Migration vers structlog pour AuditAuthMiddleware et conventions de niveaux documentées.
- **Task 9 Complete**: Services critiques migrés vers structlog (AuthService, ProfileService, CatalogService, ExecutionService, IntegrationService, AuditService).
- **Task 10 Complete**: Tests créés pour middleware (15 tests) et health check (11 tests).
- **Task 11 Complete**: Documentation complète créée (observability-architecture.md, observability-runbook.md, logging-conventions.md).
- **Task 12 Complete**: Parité validée et documentée dans drf-api-migration-notes.md.

### Change Log

- 2026-02-05: Story M.8 implémentée - Middleware, logging, observabilité complets

### File List

**Fichiers créés:**
- idp-portal/django_backend/core/logging.py
- idp-portal/django_backend/core/tests/test_middleware.py
- idp-portal/django_backend/core/tests/test_health_check.py
- idp-portal/django_backend/docs/observability-architecture.md
- idp-portal/django_backend/docs/observability-runbook.md
- idp-portal/django_backend/docs/logging-conventions.md

**Fichiers modifiés:**
- idp-portal/django_backend/requirements.txt (ajout structlog, requests)
- idp-portal/django_backend/core/middleware.py (RequestResponseLoggingMiddleware, get_client_ip, bind structlog)
- idp-portal/django_backend/core/views.py (health check étendu Vault/ServiceNow)
- idp-portal/django_backend/core/exceptions.py (logging structuré, X-Idp-Request-Id header)
- idp-portal/django_backend/core/apps.py (init structlog)
- idp-portal/django_backend/core/services.py (migration structlog)
- idp-portal/django_backend/idp_backend/settings.py (LOGGING, CORS, VAULT_ADDR, SERVICENOW_INSTANCE_URL)
- idp-portal/django_backend/idp_auth/middleware.py (migration structlog)
- idp-portal/django_backend/idp_auth/views.py (migration structlog)
- idp-portal/django_backend/idp_auth/services.py (migration structlog)
- idp-portal/django_backend/profiles/services.py (migration structlog)
- idp-portal/django_backend/catalog/services.py (migration structlog)
- idp-portal/django_backend/executions/services.py (migration structlog)
- idp-portal/django_backend/integrations/services.py (migration structlog)
- idp-portal/django_backend/docs/drf-api-migration-notes.md (section M.8 ajoutée)
