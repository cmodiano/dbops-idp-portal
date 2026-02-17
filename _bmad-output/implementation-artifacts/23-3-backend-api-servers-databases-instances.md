# Story 23.3: Backend — API /servers, /databases, /instances

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur frontend,
je veux des endpoints API REST pour lister les serveurs, instances et bases de données avec filtres,
afin de pouvoir charger les listes d'inventaire multi-tables dans le wizard d'exécution avec filtrage par serveur.

## Acceptance Criteria

**Given** les méthodes InventoryService list_servers/list_instances/list_databases (story 23.2 complétée)
**When** je consomme l'API inventaire depuis le frontend
**Then** je reçois les entités dans le format attendu avec filtrage par environnement et serveur

**AC1 : Endpoint GET /api/v1/inventory/servers**

**Given** un utilisateur authentifié
**When** j'appelle `GET /api/v1/inventory/servers?environment=dev&engine_type=oracle`
**Then** l'endpoint retourne `200 OK` avec `{ data: [ { id, name, environment, engine_type? } ] }`
**And** utilise `InventoryService.list_servers(environment, engine_type)` en interne
**And** applique le filtrage RBAC via `list_targets_for_user` (serveurs autorisés uniquement)
**And** supporte query params : `environment` (requis), `engine_type` (optionnel)
**And** si `environment` absent, retourne `400 Bad Request`
**And** logue l'opération avec correlation_id et user_id

**AC2 : Endpoint GET /api/v1/inventory/instances**

**Given** un utilisateur authentifié avec accès à certains serveurs
**When** j'appelle `GET /api/v1/inventory/instances?environment=dev&server_name=srv01`
**Then** l'endpoint retourne `200 OK` avec `{ data: [ { id, name, environment, server_ref, db_ref? } ] }`
**And** utilise `InventoryService.list_instances(environment, server_name)` en interne
**And** valide que `server_name` est dans la liste des serveurs autorisés (RBAC)
**And** si `server_name` non autorisé, retourne `403 Forbidden` avec message explicite
**And** supporte query params : `environment` (requis), `server_name` (optionnel), `server_names` (liste optionnelle)
**And** si `server_names` fourni, supporte format `?server_names=srv01&server_names=srv02` (multi-value)
**And** si ni `server_name` ni `server_names`, retourne toutes les instances de l'environnement autorisées
**And** logue l'opération avec server_filter et nb_results

**AC3 : Endpoint GET /api/v1/inventory/databases**

**Given** un utilisateur authentifié
**When** j'appelle `GET /api/v1/inventory/databases?environment=dev&server_name=srv01`
**Then** l'endpoint retourne `200 OK` avec `{ data: [ { id, name, environment } ] }`
**And** utilise `InventoryService.list_databases(environment, server_name)` en interne
**And** valide que `server_name` est dans la liste des serveurs autorisés (RBAC)
**And** si `server_name` non autorisé, retourne `403 Forbidden`
**And** supporte query params : `environment` (requis), `server_name` (optionnel), `server_names` (liste optionnelle)
**And** si ni `server_name` ni `server_names`, retourne toutes les databases de l'environnement
**And** logue l'opération avec server_filter et nb_results

**AC4 : Sérialisation standardisée**

**Given** les nouveaux endpoints inventaire
**When** les réponses sont sérialisées
**Then** utiliser des serializers DRF dédiés :
- `ServerSerializer` : id, name, environment, engine_type (optionnel)
- `InstanceSerializer` : id, name, environment, server_ref, db_ref (optionnel)
- `DatabaseSerializer` : id, name, environment
**And** tous les serializers héritent de `serializers.Serializer` (pas de modèle Django)
**And** le format de réponse est cohérent : `{ "data": [...] }` (pas de pagination pour inventaire)
**And** les erreurs retournent `{ "detail": "..." }` avec status codes appropriés

**AC5 : Validation RBAC stricte pour server_name(s)**

**Given** un endpoint instances ou databases avec `server_name` fourni
**When** la requête est traitée
**Then** l'endpoint :
1. Appelle `InventoryService.list_targets_for_user(user, environment)` pour obtenir serveurs autorisés
2. Vérifie que `server_name` (ou tous les `server_names`) sont dans cette liste
3. Si validation échoue, retourne `403 Forbidden` avec message `"Access denied to server: {server_name}"`
4. Si validation réussit, appelle `list_instances`/`list_databases` avec `server_name` validé
**And** logue toute tentative d'accès non autorisé avec `WARNING` et correlation_id

**AC6 : Gestion d'erreurs et logging**

**Given** une requête vers un endpoint inventaire
**When** une erreur survient
**Then** :
- `400 Bad Request` si params invalides (environment manquant, format incorrect)
- `403 Forbidden` si RBAC échoue (server_name non autorisé)
- `500 Internal Server Error` si `InventoryServiceError` (avec logging ERROR)
- `401 Unauthorized` si utilisateur non authentifié
**And** toutes les erreurs sont loggées avec correlation_id et contexte
**And** les messages d'erreur ne révèlent jamais de détails SQL ou config sensible

**AC7 : Documentation OpenAPI (drf-spectacular)**

**Given** les nouveaux endpoints inventaire
**When** la documentation API est générée
**Then** utiliser `@extend_schema` de drf-spectacular pour :
- Documenter tous les query params avec types et descriptions
- Spécifier les réponses 200/400/403/500 avec exemples
- Marquer `environment` comme requis, autres comme optionnels
- Inclure exemples de réponses JSON pour chaque endpoint
**And** la documentation est visible sur `/api/schema/swagger-ui/` et `/api/schema/redoc/`

**AC8 : Tests unitaires et d'intégration**

**Given** les 3 nouveaux endpoints inventaire
**When** les tests sont exécutés
**Then** ils couvrent :
- Succès 200 pour chaque endpoint avec params valides
- Validation RBAC (403) si server_name non autorisé
- 400 si environment manquant ou params invalides
- 500 si InventoryServiceError (mocker service error)
- server_names multi-value (liste de serveurs)
- Cas sans server_name (toutes instances/DB de l'env)
- Logging structlog events capturés
- Couverture ≥ 85% pour les nouvelles views

## Tasks / Subtasks

- [x] Task 1 : Serializers pour les nouvelles entités (AC4)
  - [x] 1.1 : Créer `ServerSerializer` dans `inventory/serializers.py` (id, name, environment, engine_type)
  - [x] 1.2 : Créer `InstanceSerializer` (id, name, environment, server_ref, db_ref)
  - [x] 1.3 : Créer `DatabaseSerializer` (id, name, environment)
  - [x] 1.4 : Créer `ServerFilterParamsSerializer` pour validation query params (environment, engine_type)
  - [x] 1.5 : Créer `InstanceFilterParamsSerializer` (environment, server_name, server_names)
  - [x] 1.6 : Créer `DatabaseFilterParamsSerializer` (environment, server_name, server_names)
  - [x] 1.7 : Ajouter validation `server_names` comme liste de strings (MultipleChoiceField ou ListField)
  - [x] 1.8 : Ajouter tests unitaires pour chaque serializer (validation params, format output)

- [x] Task 2 : Endpoint GET /api/v1/inventory/servers (AC1)
  - [x] 2.1 : Créer view `list_servers` dans `inventory/views.py` avec `@api_view(['GET'])`
  - [x] 2.2 : Ajouter `@permission_classes([IsAuthenticated])` pour protection
  - [x] 2.3 : Valider query params avec `ServerFilterParamsSerializer`
  - [x] 2.4 : Appeler `InventoryService.list_targets_for_user(user, environment)` pour RBAC
  - [x] 2.5 : Filtrer résultats par `engine_type` si fourni (côté client ou service)
  - [x] 2.6 : Sérialiser avec `ServerSerializer` et retourner `{ "data": [...] }`
  - [x] 2.7 : Logger avec structlog (event: `inventory_api_list_servers`, user_id, environment, engine_type, nb_results, correlation_id)
  - [x] 2.8 : Gérer erreurs (400, 500) avec messages appropriés

- [x] Task 3 : Endpoint GET /api/v1/inventory/instances (AC2)
  - [x] 3.1 : Créer view `list_instances` dans `inventory/views.py`
  - [x] 3.2 : Valider query params avec `InstanceFilterParamsSerializer`
  - [x] 3.3 : Si `server_name` ou `server_names` fournis, valider RBAC (AC5) :
    - Appeler `list_targets_for_user(user, environment)` → allowed_servers
    - Vérifier que tous server_name(s) sont dans allowed_servers
    - Si échec, retourner `403 Forbidden` avec `{ "detail": "Access denied to server: {name}" }`
    - Logger `WARNING` avec event `inventory_rbac_denied_server_access`
  - [x] 3.4 : Si validation OK (ou pas de server filter), appeler `InventoryService.list_instances(environment, server_name, server_names)`
  - [x] 3.5 : Sérialiser avec `InstanceSerializer` et retourner `{ "data": [...] }`
  - [x] 3.6 : Logger succès avec structlog (event: `inventory_api_list_instances`, server_filter, nb_results)
  - [x] 3.7 : Gérer erreurs (400, 403, 500)

- [x] Task 4 : Endpoint GET /api/v1/inventory/databases (AC3)
  - [x] 4.1 : Créer view `list_databases` dans `inventory/views.py`
  - [x] 4.2 : Valider query params avec `DatabaseFilterParamsSerializer`
  - [x] 4.3 : Si `server_name` ou `server_names` fournis, valider RBAC (même pattern que Task 3.3)
  - [x] 4.4 : Appeler `InventoryService.list_databases(environment, server_name, server_names)`
  - [x] 4.5 : Sérialiser avec `DatabaseSerializer` et retourner `{ "data": [...] }`
  - [x] 4.6 : Logger succès (event: `inventory_api_list_databases`)
  - [x] 4.7 : Gérer erreurs (400, 403, 500)

- [x] Task 5 : URLs et routing (AC1-3)
  - [x] 5.1 : Ajouter dans `inventory/urls.py` :
    - `path('servers/', list_servers, name='inventory-servers')`
    - `path('instances/', list_instances, name='inventory-instances')`
    - `path('databases/', list_databases, name='inventory-databases')`
  - [x] 5.2 : Vérifier que les URLs sont bien montées sous `/api/v1/inventory/` dans le URLconf principal
  - [x] 5.3 : Tester les URLs avec curl ou httpie pour vérifier routing correct

- [x] Task 6 : Documentation OpenAPI avec drf-spectacular (AC7)
  - [x] 6.1 : Importer `from drf_spectacular.utils import extend_schema, OpenApiParameter`
  - [x] 6.2 : Annoter `list_servers` avec `@extend_schema` :
    - `summary="List servers from inventory"`
    - `parameters=[OpenApiParameter('environment', str, required=True), OpenApiParameter('engine_type', str)]`
    - `responses={200: ServerSerializer(many=True), 400: ..., 403: ..., 500: ...}`
    - `examples` pour réponse 200 avec données fictives
  - [x] 6.3 : Annoter `list_instances` avec `@extend_schema` (environment required, server_name/server_names optional)
  - [x] 6.4 : Annoter `list_databases` avec `@extend_schema`
  - [x] 6.5 : Tester la doc générée sur `/api/schema/swagger-ui/` et vérifier que les 3 endpoints apparaissent
  - [x] 6.6 : Vérifier que les exemples et descriptions sont clairs et complets

- [x] Task 7 : Helper RBAC pour validation server_name (AC5)
  - [x] 7.1 : Créer fonction helper `_validate_server_access(user, environment, server_name=None, server_names=None)` dans `inventory/views.py` ou `inventory/rbac_utils.py`
  - [x] 7.2 : Appeler `InventoryService.list_targets_for_user(user, environment)`
  - [x] 7.3 : Extraire liste des noms de serveurs autorisés
  - [x] 7.4 : Si `server_name` fourni, vérifier qu'il est dans la liste (raise PermissionDenied si non)
  - [x] 7.5 : Si `server_names` fourni, vérifier que TOUS sont autorisés (raise PermissionDenied avec le premier non autorisé)
  - [x] 7.6 : Logger toute tentative d'accès refusé avec `WARNING` et correlation_id
  - [x] 7.7 : Retourner liste des serveurs autorisés (pour usage optionnel)
  - [x] 7.8 : Tester avec différents scénarios (server autorisé, non autorisé, liste mixte)

- [x] Task 8 : Tests unitaires endpoints (AC8)
  - [x] 8.1 : Créer `inventory/tests/test_views_multi_tables.py`
  - [x] 8.2 : Tester `list_servers` :
    - Succès 200 avec environment valide
    - 400 si environment manquant
    - Filtrage par engine_type fonctionne
    - RBAC appliqué (serveurs filtrés selon profils user)
    - Logging structlog capturé
  - [x] 8.3 : Tester `list_instances` :
    - Succès 200 avec environment seul
    - Succès 200 avec environment + server_name autorisé
    - 403 si server_name non autorisé
    - Succès avec server_names liste (multi-value query param)
    - 400 si environment manquant
    - Cas sans server_name (toutes instances env)
  - [x] 8.4 : Tester `list_databases` :
    - Succès 200 avec environment + server_name autorisé
    - 403 si server_name non autorisé
    - Succès avec server_names liste
    - Cas sans server_name
  - [x] 8.5 : Tester gestion d'erreurs :
    - 500 si InventoryServiceError (mocker service)
    - Messages d'erreur appropriés
  - [x] 8.6 : Tester helper `_validate_server_access` unitairement
  - [x] 8.7 : Vérifier couverture ≥ 85% pour inventory/views.py (nouvelles views)

- [x] Task 9 : Tests d'intégration (AC8)
  - [x] 9.1 : Créer `inventory/tests/test_integration_multi_tables.py`
  - [x] 9.2 : Tester flow complet : requête HTTP → RBAC → InventoryService → réponse JSON
  - [x] 9.3 : Utiliser APIClient de DRF avec utilisateur authentifié + profils RBAC
  - [x] 9.4 : Tester scénario réaliste : user avec accès à 2 serveurs, charge instances de ces serveurs
  - [x] 9.5 : Tester scénario refus : user essaie d'accéder à serveur hors de ses profils → 403
  - [x] 9.6 : Tester cas multi-tables config active vs fallback table plate (si applicable)
  - [x] 9.7 : Vérifier format réponse JSON exact : `{ "data": [...] }` avec structure attendue

## Dev Notes

### Contexte architectural

**Référence** : `docs/inventaire-multi-tables-ux-cibles.md`, Stories 23.1 et 23.2 (done), `inventory/views.py`, `inventory/serializers.py`

**Architecture API actuelle** :
- Endpoints existants : `GET /api/v1/inventory/targets`, `/targets/all`, `/environments`
- Pattern : `@api_view(['GET'])` + `@permission_classes([IsAuthenticated])`
- Sérialisation : `TargetSerializer` (Serializer sans modèle Django)
- Format réponse liste : `{ "data": [...], "pagination": {...} }` (targets) ou `{ "data": [...] }` (environments)
- RBAC : appliqué via `InventoryService.list_targets_for_user` dans les views

**Nouvelle architecture (Story 23.3)** :
- 3 nouveaux endpoints : `/servers`, `/instances`, `/databases`
- Réutiliser pattern existant : `@api_view`, serializers sans modèle, RBAC dans view
- Valider query params avec serializers dédiés (TargetFilterParamsSerializer pattern)
- RBAC strict : valider `server_name` avant d'appeler `list_instances`/`list_databases`
- Logging structlog systématique avec correlation_id

**Technologies** :
- Django 5.2 + Django REST Framework 3.16
- drf-spectacular 0.28+ pour OpenAPI 3.0 (story 22-20)
- structlog pour logging structuré
- InventoryService (story 23.2) pour logique métier

### Fichiers à modifier/créer

**Modifier** :
- `inventory/serializers.py` : Ajouter ServerSerializer, InstanceSerializer, DatabaseSerializer, *FilterParamsSerializer
- `inventory/views.py` : Ajouter list_servers, list_instances, list_databases views + helper RBAC
- `inventory/urls.py` : Ajouter routes servers/, instances/, databases/

**Créer** :
- `inventory/tests/test_views_multi_tables.py` : Tests unitaires des nouvelles views
- `inventory/tests/test_integration_multi_tables.py` : Tests d'intégration API

**Documenter** :
- Spec OpenAPI générée automatiquement via drf-spectacular

### Patterns de code

**Serializer pour entity sans modèle** :
```python
class ServerSerializer(serializers.Serializer):
    """
    Serializer for server inventory entity.
    Story 23.3 - Multi-table inventory API.
    """
    id = serializers.CharField(
        help_text="Server unique identifier (name or technical ID)"
    )
    name = serializers.CharField(
        help_text="Server hostname"
    )
    environment = serializers.CharField(
        help_text="Server environment (dev, staging, prod, lab, etc.)"
    )
    engine_type = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Database engine type (oracle, sqlserver, postgres, etc.)"
    )
```

**View avec validation RBAC server_name** :
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework.exceptions import PermissionDenied

@extend_schema(
    summary="List database instances from inventory",
    description="Returns instances filtered by environment and optionally by server. Applies RBAC filtering.",
    parameters=[
        OpenApiParameter('environment', str, required=True, description="Target environment"),
        OpenApiParameter('server_name', str, required=False, description="Filter instances by server name (single)"),
        OpenApiParameter('server_names', str, required=False, description="Filter instances by server names (multiple)", many=True),
    ],
    responses={
        200: InstanceSerializer(many=True),
        400: {"description": "Invalid query parameters"},
        403: {"description": "Access denied to specified server"},
        500: {"description": "Internal server error"},
    },
    examples=[
        OpenApiExample(
            'Success response',
            value={"data": [{"id": "INST01", "name": "INST01", "environment": "dev", "server_ref": "srv01", "db_ref": "DB01"}]},
            response_only=True,
        )
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_instances(request):
    """
    List instances with optional server filter.
    Validates RBAC before returning instances linked to specified server(s).

    AC2: Returns instances filtered by environment and server_name (RBAC validated).
    """
    correlation_id = get_correlation_id()
    user = request.user

    # Validate query params
    params_serializer = InstanceFilterParamsSerializer(data=request.query_params)
    if not params_serializer.is_valid():
        return Response(
            {'detail': params_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    params = params_serializer.validated_data
    environment = params['environment']  # required
    server_name = params.get('server_name')
    server_names = params.get('server_names')

    # Validate RBAC if server filter provided
    if server_name or server_names:
        try:
            _validate_server_access(user, environment, server_name, server_names)
        except PermissionDenied as e:
            logger.warning(
                "inventory_rbac_denied_server_access",
                user_id=user.id,
                environment=environment,
                server_name=server_name,
                server_names=server_names,
                correlation_id=correlation_id
            )
            raise  # Re-raise PermissionDenied to return 403

    # Fetch instances from inventory service
    inventory_service = InventoryService()
    try:
        instances = inventory_service.list_instances(
            environment=environment,
            server_name=server_name,
            server_names=server_names
        )
    except InventoryServiceError as e:
        logger.error(
            "inventory_api_list_instances_failed",
            user_id=user.id,
            environment=environment,
            error=str(e),
            correlation_id=correlation_id
        )
        return Response(
            {'detail': 'Failed to retrieve instances'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Serialize and return
    serializer = InstanceSerializer(instances, many=True)

    logger.info(
        "inventory_api_list_instances",
        user_id=user.id,
        environment=environment,
        server_filter={'server_name': server_name, 'server_names': server_names},
        nb_results=len(instances),
        correlation_id=correlation_id
    )

    return Response({'data': serializer.data}, status=status.HTTP_200_OK)
```

**Helper validation RBAC** :
```python
def _validate_server_access(
    user: User,
    environment: str,
    server_name: str | None = None,
    server_names: list[str] | None = None
) -> list[str]:
    """
    Validate that user has RBAC access to specified server(s).

    Args:
        user: Authenticated user
        environment: Target environment
        server_name: Single server name to validate (exclusive with server_names)
        server_names: List of server names to validate (exclusive with server_name)

    Returns:
        List of allowed server names for the user in this environment

    Raises:
        PermissionDenied: If any specified server is not in user's allowed servers

    Story 23.3 - RBAC validation for instances/databases endpoints.
    """
    correlation_id = get_correlation_id()
    inventory_service = InventoryService()

    # Get allowed servers for user
    allowed_targets = inventory_service.list_targets_for_user(user, environment)
    allowed_server_names = {target['name'] for target in allowed_targets}

    # Validate server_name (single)
    if server_name:
        if server_name not in allowed_server_names:
            logger.warning(
                "rbac_server_access_denied",
                user_id=user.id,
                environment=environment,
                requested_server=server_name,
                allowed_servers=list(allowed_server_names),
                correlation_id=correlation_id
            )
            raise PermissionDenied(f"Access denied to server: {server_name}")

    # Validate server_names (list)
    if server_names:
        unauthorized = [s for s in server_names if s not in allowed_server_names]
        if unauthorized:
            logger.warning(
                "rbac_servers_access_denied",
                user_id=user.id,
                environment=environment,
                unauthorized_servers=unauthorized,
                allowed_servers=list(allowed_server_names),
                correlation_id=correlation_id
            )
            raise PermissionDenied(f"Access denied to servers: {', '.join(unauthorized)}")

    return list(allowed_server_names)
```

**Serializer validation multi-value param** :
```python
class InstanceFilterParamsSerializer(serializers.Serializer):
    """
    Query params validation for instances endpoint.
    """
    environment = serializers.CharField(
        required=True,
        help_text="Target environment (required)"
    )
    server_name = serializers.CharField(
        required=False,
        help_text="Filter by single server name (exclusive with server_names)"
    )
    server_names = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=False,
        help_text="Filter by multiple server names (exclusive with server_name)"
    )

    def validate(self, attrs):
        """Ensure server_name and server_names are mutually exclusive."""
        server_name = attrs.get('server_name')
        server_names = attrs.get('server_names')

        if server_name and server_names:
            raise serializers.ValidationError(
                "Cannot specify both server_name and server_names"
            )

        return attrs
```

### Patterns de tests

**Test succès avec RBAC** :
```python
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

class TestInventoryMultiTablesAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = MagicMock(id=123, is_authenticated=True)
        self.client.force_authenticate(user=self.user)

    @patch('inventory.views.InventoryService')
    @patch('inventory.views.get_correlation_id')
    def test_list_instances_with_server_name_authorized(self, mock_corr_id, mock_service_class):
        """AC2: Success 200 when server_name is in user's allowed servers."""
        mock_corr_id.return_value = 'test-correlation-id'

        # Mock RBAC: user allowed srv01, srv02
        mock_service = mock_service_class.return_value
        mock_service.list_targets_for_user.return_value = [
            {'name': 'srv01', 'environment': 'dev'},
            {'name': 'srv02', 'environment': 'dev'}
        ]

        # Mock instances service
        mock_service.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01'}
        ]

        response = self.client.get('/api/v1/inventory/instances/', {
            'environment': 'dev',
            'server_name': 'srv01'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json())
        self.assertEqual(len(response.json()['data']), 1)

        # Verify RBAC called
        mock_service.list_targets_for_user.assert_called_once_with(self.user, 'dev')

        # Verify service called with validated server_name
        mock_service.list_instances.assert_called_once_with(
            environment='dev',
            server_name='srv01',
            server_names=None
        )

    @patch('inventory.views.InventoryService')
    def test_list_instances_server_name_unauthorized_403(self, mock_service_class):
        """AC2: Returns 403 when server_name not in user's allowed servers."""
        mock_service = mock_service_class.return_value
        mock_service.list_targets_for_user.return_value = [
            {'name': 'srv01', 'environment': 'dev'}
        ]

        response = self.client.get('/api/v1/inventory/instances/', {
            'environment': 'dev',
            'server_name': 'srv99'  # Not allowed
        })

        self.assertEqual(response.status_code, 403)
        self.assertIn('detail', response.json())
        self.assertIn('srv99', response.json()['detail'])
```

### Standards de tests

**Référence** : Story 23.2 (43 tests), Epic M patterns, Story 22-20 (drf-spectacular)

**Couverture requise** :
- Tests unitaires views : succès 200, erreurs 400/403/500, RBAC validation
- Tests serializers : validation params, format output
- Tests helper RBAC : server autorisé, non autorisé, liste mixte
- Tests d'intégration : flow complet HTTP → service → JSON
- Coverage ≥ 85% pour inventory/views.py (nouvelles views)

**Assertions clés** :
- Vérifier status codes exacts (200, 400, 403, 500)
- Vérifier format réponse `{ "data": [...] }` respecté
- Vérifier que RBAC est appelé avant service (list_targets_for_user)
- Vérifier logging structlog events (info succès, warning RBAC denied, error failures)
- Vérifier serializers retournent structure attendue (id, name, environment, etc.)

### Dépendances et ordre

**Dépend de** :
- Story 23.1 (done) : InventoryMapper + config mapping
- Story 23.2 (done) : InventoryService.list_servers/list_instances/list_databases
- Story 22-20 (done) : drf-spectacular intégré

**Bloque** :
- Story 23.6 : Frontend useTargetInventory avec server_name (nécessite ces endpoints API)
- Story 23.5 : Frontend admin source inventaire (consomme /servers /instances /databases)

**N'affecte PAS** :
- Endpoints existants `/inventory/targets`, `/targets/all`, `/environments` (continuent de fonctionner)
- Frontend actuel (jusqu'à story 23.6)

### Risques et mitigations

**Risque** : RBAC bypass si validation server_name oubliée
**Mitigation** : Helper dédié `_validate_server_access`, tests spécifiques 403, code review focus sécurité

**Risque** : Format réponse incohérent avec frontend expectations
**Mitigation** : Documenter format `{ "data": [...] }` explicitement, tests vérifier structure JSON exacte, consulter `execution_service.ts` frontend

**Risque** : Performance dégradée si multi-value server_names avec beaucoup de serveurs
**Mitigation** : Story 23.2 utilise déjà optimisation IN clause, documenter limite raisonnable (ex. max 50 serveurs par requête)

**Risque** : Documentation OpenAPI incomplète ou incorrecte
**Mitigation** : Tester manuellement Swagger UI, vérifier exemples, valider que query params multi-value sont bien documentés

### Intelligence des Stories 23.1 et 23.2

**Story 23.1 (done)** :
- InventoryMapper opérationnel : build_select_clause, build_where_clause, validate_config
- `_read_servers_from_config`, `_read_instances_from_config`, `_read_databases_from_config` implémentés
- Validation sécurité stricte : SAFE_TABLE_NAME_PATTERN, SAFE_COLUMN_NAME_PATTERN
- Limites DoS : MAX_MULTI_TABLE_RESULTS = 10000, ROWNUM dans requêtes
- Fallback table plate fonctionne : `_read_servers_flat_fallback`
- 69 tests passent (46 mapper + 23 inventory)

**Story 23.2 (done)** :
- Méthodes publiques : `list_servers`, `list_instances`, `list_databases` exposées
- `list_targets_for_user` adapté : détecte config multi-tables et utilise `list_servers`
- Optimisation performance : IN clause pour server_names (évite N+1)
- Validation empty list : `server_names=[]` raise ValueError
- Gestion erreurs : try/except MapperValidationError + Exception, raise InventoryServiceError
- Logging structlog systématique : correlation_id, nb_results, server_filter
- RBAC responsibility documentée : list_instances/databases ne filtrent PAS, API layer doit valider
- 43 tests passent (40 nouveaux + 3 fixes)

**Fichiers créés 23.1/23.2** :
- `inventory/mapper.py` : InventoryMapper
- `inventory/tests/test_mapper.py` : 38 tests
- `inventory/tests/test_inventory_multi_tables.py` : 31 tests
- `inventory/tests/test_inventory_service_multi_tables.py` : 40 tests
- `docs/inventory-mapping-config.md` : Documentation config + RBAC

**Patterns à réutiliser** :
- `from __future__ import annotations` pour Python 3.9+
- Type hints complets `dict[str, Any]`, `list[str]`
- Logging structlog : `logger.info("event_name", key=value, correlation_id=...)`
- Gestion erreurs : try/except spécifique → log ERROR → raise service error générique
- Documentation RBAC : Security Note + Performance Note dans docstrings

### Commits récents pertinents

**Référence** : `git log --oneline -5`

- `6f61d93 feat(23-2): add multi-table inventory service methods` — Story 23.2 complétée
- `3d39053 feat(23-1): implement config-driven multi-table inventory mapping` — Story 23.1 complétée
- `09a0c14 feat(22-20): integrate drf-spectacular for automated API documentation` — OpenAPI specs
- `e82c63f feat(22-19): implement progressive mypy enforcement with baseline tracking` — Mypy actif
- `eeb4aa7 fix(22-18): add missing requires_target field to frontend types` — Alignement types frontend

**Code patterns récents** :
- drf-spectacular : `@extend_schema` avec parameters, responses, examples
- DRF serializers sans modèle : `serializers.Serializer` pour data externes
- RBAC dans views : appeler service, vérifier résultats, raise PermissionDenied
- Type hints stricts (mypy progressif)

### Frontend expectations (référence)

**Fichier** : `idp-portal/frontend/src/services/execution_service.ts`

**Appels existants attendus** :
```typescript
// From useDynamicForm.ts / useTargetInventory.ts
const fetchInventoryItems = async (
  inventorySource: 'servers' | 'databases' | 'instances',
  environment: string,
  serverName?: string
): Promise<InventoryItem[]> => {
  const endpoint = `/api/v1/inventory/${inventorySource}`;
  const params = { environment, ...(serverName && { server_name: serverName }) };

  const response = await apiClient.get(endpoint, { params });
  return response.data.data; // Attend { data: [...] }
};
```

**Type attendu** :
```typescript
interface InventoryItem {
  id: string;
  name: string;
  environment: string;
  // Optionnel selon entity:
  engine_type?: string;  // servers
  server_ref?: string;   // instances
  db_ref?: string;       // instances
}
```

**Format réponse API attendu** : `{ "data": InventoryItem[] }` (pas de pagination pour inventaire)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- 57/57 tests pass (49 unit + 8 integration)
- 22 pre-existing failures in `test_views.py` (301 redirect) and `test_environments.py` (fixtures) — NOT caused by this story

### Completion Notes List

- **Task 1**: Created 6 serializers (ServerSerializer, InstanceSerializer, DatabaseSerializer + 3 FilterParamsSerializers) with `server_names` ListField validation and mutual exclusion with `server_name`. 19 serializer tests pass.
- **Task 7**: Created `_validate_server_access()` helper in views.py that calls `list_targets_for_user` for RBAC, validates server_name(s), raises PermissionDenied with explicit message, logs WARNING on denial. 5 unit tests.
- **Task 2**: `list_servers` view with `@api_view(['GET'])`, `IsAuthenticated`, RBAC filtering via `list_targets_for_user`, engine_type filter, structlog logging. 7 tests.
- **Task 3**: `list_instances` view with RBAC validation for server_name(s), multi-value `server_names` query param, 403 on unauthorized access. 6 tests.
- **Task 4**: `list_databases` view following same RBAC pattern as instances. 6 tests.
- **Task 5**: 3 URL routes added under `/api/v1/inventory/` (servers/, instances/, databases/). Verified mounting.
- **Task 6**: `@extend_schema` annotations on all 3 views with parameters, responses, examples. OpenAPI documentation auto-generated.
- **Task 8**: 49 unit tests covering serializers, views (200/400/403/500), RBAC helper, response format.
- **Task 9**: 8 integration tests covering full flow HTTP→RBAC→Service→JSON, RBAC denial, multi-value params, response structure, error format.

### Change Log

- 2026-02-09: Story 23.3 implemented — 3 new API endpoints (/servers, /instances, /databases) with RBAC, OpenAPI docs, 57 tests
- 2026-02-09: Code review fixes applied (11 issues):
  - **HIGH-1**: Increased page_size to 10000 for RBAC calls to handle large deployments
  - **HIGH-2**: Added safe dict access with `.get('name')` in RBAC validation to prevent KeyError
  - **HIGH-3**: Made InstanceSerializer.server_ref optional/nullable (required=False, allow_null=True)
  - **HIGH-4**: Added try/except in _validate_server_access to safely handle malformed data and raise PermissionDenied
  - **HIGH-5**: Created wrapper serializers (ServerListResponseSerializer, etc.) for correct OpenAPI documentation showing {"data": [...]} structure
  - **HIGH-6**: Removed duplicate RBAC denial logging in views (kept only in helper)
  - **HIGH-7**: Refactored ErrorHandlingTests to use parameterized test with subTest pattern (eliminates duplication)
  - **HIGH-8**: Enhanced test_list_servers_filter_engine_type with better documentation (engine_type filtering is service responsibility)
  - **MEDIUM-1**: Added max_length validation to all query param fields (environment=50, engine_type=20, server_name=255)
  - **MEDIUM-2**: Standardized error response format - all 400 errors now return {'detail': str(errors)} instead of raw dict
  - **MEDIUM-3**: Removed duplicate logging in list_instances and list_databases views (helper logs RBAC denial)

### File List

- `idp-portal/django_backend/inventory/serializers.py` (modified) — Added ServerSerializer, InstanceSerializer, DatabaseSerializer, 3 FilterParamsSerializers
- `idp-portal/django_backend/inventory/views.py` (modified) — Added _validate_server_access helper, list_servers, list_instances, list_databases views with @extend_schema
- `idp-portal/django_backend/inventory/urls.py` (modified) — Added servers/, instances/, databases/ routes
- `idp-portal/django_backend/inventory/tests/test_views_multi_tables.py` (created) — 49 unit tests
- `idp-portal/django_backend/inventory/tests/test_integration_multi_tables.py` (created) — 8 integration tests
