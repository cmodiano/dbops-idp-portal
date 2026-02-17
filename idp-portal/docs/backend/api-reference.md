# API Reference

## Vue d'ensemble

L'API REST est construite avec Django REST Framework (DRF). Tous les endpoints sont préfixés par `/api/v1/`.

## Format de réponse

### Succès

```json
{
  "data": { ... }
}
```

### Succès avec pagination

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total": 100,
    "total_pages": 4
  }
}
```

### Erreur

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Action non trouvée",
    "details": { "action_id": 123 }
  }
}
```

## Authentification

Tous les endpoints (sauf `/health`) requièrent un token JWT dans le header:

```
Authorization: Bearer <jwt_token>
```

## Endpoints par domaine

### Health

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| GET | `/api/v1/health` | Health check (DB + services) | Non |

**Réponse:**

```json
{
  "data": {
    "status": "healthy",
    "database": "up",
    "vault": "up",
    "servicenow": "up",
    "timestamp": "2026-02-05T10:30:00Z"
  }
}
```

### Authentification

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/auth/saml/login` | Initie le flow SAML |
| POST | `/api/v1/auth/saml/callback` | Callback IdP SAML |
| POST | `/api/v1/auth/refresh` | Rafraîchit le token JWT |
| GET | `/api/v1/auth/me` | Retourne le profil utilisateur courant |

### Catalogue (Admin)

**Permission requise:** `DBOPSProfilePermission` (profil DBOPS)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/admin/actions` | Créer une action |
| GET | `/api/v1/admin/actions` | Lister toutes les actions |
| GET | `/api/v1/admin/actions/{id}` | Détails d'une action |
| PUT | `/api/v1/admin/actions/{id}` | Modifier une action |
| DELETE | `/api/v1/admin/actions/{id}` | Supprimer une action |
| PUT | `/api/v1/admin/actions/{id}/tags` | Modifier les tags |
| PATCH | `/api/v1/admin/actions/{id}/status` | Changer le statut |
| PUT | `/api/v1/admin/actions/{id}/execution-steps` | Modifier les étapes |
| PUT | `/api/v1/admin/actions/{id}/remediation-rules` | Modifier les règles de remédiation |
| GET | `/api/v1/admin/actions/eligible-for-workflow` | Actions publiées pour workflows |

### Catalogue (Public)

**Permission:** `OptionalUserPermission` (accessible à tous, filtrage RBAC si authentifié)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/catalog/actions` | Lister les actions publiées (avec RBAC) |
| GET | `/api/v1/catalog/actions/{id}` | Détails d'une action publiée |
| GET | `/api/v1/catalog/actions/{id}/stats` | Statistiques d'exécution |

**Query parameters pour liste:**

| Param | Type | Description |
|-------|------|-------------|
| `tags` | string | Tags séparés par virgule (ex: `oracle,patching`) |
| `category` | string | Filtrer par catégorie/tag |
| `q` | string | Recherche texte (name, description) |
| `engine` | string | Filtrer par engine (Oracle, SQL Server, DB2) |
| `environment` | string | Filtrer par environnement supporté |
| `impact` | string | Filtrer par niveau d'impact |
| `page` | int | Numéro de page (défaut: 1) |
| `page_size` | int | Taille de page (défaut: 25, max: 1000) |

### Tags

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/tags` | Lister tous les tags |
| GET | `/api/v1/tags/catalog` | Tags avec action_count (filtré par RBAC) |

**Note:** L'endpoint `/api/v1/tags/catalog` est implémenté comme une action DRF sur `TagViewSet` avec `url_path='catalog'`. Il retourne uniquement les tags associés aux actions visibles par l'utilisateur (filtrage RBAC) avec un compteur `action_count`.

### Profils (Admin)

**Permission requise:** `DBOPSProfilePermission`

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/admin/profiles` | Créer un profil |
| GET | `/api/v1/admin/profiles` | Lister les profils |
| GET | `/api/v1/admin/profiles/{id}` | Détails d'un profil |
| PUT | `/api/v1/admin/profiles/{id}` | Modifier un profil |
| DELETE | `/api/v1/admin/profiles/{id}` | Supprimer un profil |
| GET | `/api/v1/admin/profiles/{id}/action-permissions` | Permissions d'actions |
| PUT | `/api/v1/admin/profiles/{id}/action-permissions` | Modifier permissions actions |
| GET | `/api/v1/admin/profiles/{id}/target-permissions` | Permissions de targets |
| PUT | `/api/v1/admin/profiles/{id}/target-permissions` | Modifier permissions targets |
| GET | `/api/v1/admin/profiles/export` | Exporter en YAML |
| POST | `/api/v1/admin/profiles/import` | Importer depuis YAML |

### Intégrations (Admin)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/integrations` | Créer une intégration |
| GET | `/api/v1/integrations` | Lister les intégrations |
| GET | `/api/v1/integrations/{id}` | Détails d'une intégration |
| PUT | `/api/v1/integrations/{id}` | Modifier une intégration |
| DELETE | `/api/v1/integrations/{id}` | Supprimer une intégration |
| POST | `/api/v1/integrations/{id}/icon` | Upload icône |

### Exécutions

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/executions` | Soumettre une exécution |
| GET | `/api/v1/executions` | Lister mes exécutions |
| GET | `/api/v1/executions/{id}` | Détails d'une exécution |
| GET | `/api/v1/executions/{id}/steps` | Steps d'une exécution |

### Scheduled Executions

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/scheduled-executions` | Créer une exécution planifiée |
| GET | `/api/v1/scheduled-executions` | Lister mes exécutions planifiées |
| GET | `/api/v1/scheduled-executions/{id}` | Détails |
| PATCH | `/api/v1/scheduled-executions/{id}` | Modifier (cancel, toggle) |
| GET | `/api/v1/scheduled-executions/pending` | Pending pour scheduler externe |

## Serializers

### ActionSerializer

```python
class ActionSerializer(serializers.ModelSerializer):
    """Serializer complet pour action."""

    tags = TagSerializer(source='actiontag_set', many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    integration_name = serializers.CharField(source='integration.name', read_only=True)

    # JSON fields désérialisés
    parameters_schema = serializers.JSONField(allow_null=True)
    impact_rules = serializers.JSONField(allow_null=True)
    execution_steps = serializers.JSONField(allow_null=True)
    change_type_config = serializers.JSONField(allow_null=True)
    remediation_rules = serializers.JSONField(allow_null=True)

    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'category', 'engine', 'platform',
            'status', 'item_type', 'parameters_schema', 'impact_rules',
            'execution_steps', 'change_type_config', 'remediation_rules',
            'documentation_md', 'default_impact_level',
            'tags', 'created_by_name', 'integration_name',
            'created_at', 'updated_at',
        ]
```

### ActionCreateSerializer

```python
class ActionCreateSerializer(serializers.Serializer):
    """Serializer pour création/update d'action."""

    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=4000, allow_null=True, required=False)
    category = serializers.ChoiceField(choices=ActionCategory.choices, required=False)
    engine = serializers.ChoiceField(choices=ActionEngine.choices, required=False)
    platform = serializers.ChoiceField(choices=ActionPlatform.choices, required=False)
    status = serializers.ChoiceField(choices=ActionStatus.choices, default='draft')
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default='action')
    parameters_schema = serializers.JSONField(allow_null=True, required=False)
    impact_rules = serializers.JSONField(allow_null=True, required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
```

### ProfileSerializer

```python
class ProfileSerializer(serializers.ModelSerializer):
    """Serializer pour profil."""

    is_admin = serializers.SerializerMethodField()
    is_auditor = serializers.SerializerMethodField()
    permissions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'name', 'description', 'ad_group', 'is_admin', 'is_auditor', 'permissions_count']

    def get_is_admin(self, obj):
        return obj.is_admin == 1

    def get_is_auditor(self, obj):
        return obj.is_auditor == 1
```

## Pagination

### Configuration

```python
class CustomPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 1000
```

### Utilisation

```
GET /api/v1/catalog/actions?page=2&page_size=50
```

### Réponse

```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "page_size": 50,
    "total": 234,
    "total_pages": 5
  }
}
```

## Gestion des erreurs

### Codes d'erreur

| Code HTTP | Code erreur | Description |
|-----------|-------------|-------------|
| 400 | `BAD_REQUEST` | Requête invalide |
| 400 | `VALIDATION_ERROR` | Erreur de validation |
| 400 | `INVALID_STATE` | État invalide (ex: transition de statut) |
| 401 | `UNAUTHORIZED` | Token manquant ou invalide |
| 403 | `FORBIDDEN` | Permission refusée |
| 404 | `NOT_FOUND` | Ressource non trouvée |
| 500 | `INTERNAL_ERROR` | Erreur serveur |

### Exemples

**Validation error:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "name": ["Ce champ est obligatoire."],
      "engine": ["'Invalid' n'est pas un choix valide."]
    }
  }
}
```

**Invalid state:**

```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "Transition 'publish' invalide pour le statut 'published'",
    "details": {
      "current_status": "published",
      "transition": "publish"
    }
  }
}
```

## Headers

### Request headers

| Header | Description | Obligatoire |
|--------|-------------|-------------|
| `Authorization` | Bearer token JWT | Oui (sauf /health) |
| `Content-Type` | `application/json` | Oui pour POST/PUT |
| `X-Idp-Request-Id` | Correlation ID (propagé si fourni) | Non |

### Response headers

| Header | Description |
|--------|-------------|
| `X-Idp-Request-Id` | Correlation ID de la requête |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Cache-Control` | `no-store, no-cache` (API routes) |

## Cache

Le catalogue utilise un cache in-memory TTL 5 minutes pour améliorer les performances:

```python
# Cache invalidé automatiquement après:
# - Création d'action
# - Modification d'action
# - Changement de statut
# - Modification de tags
```

## Rate limiting

Non implémenté actuellement. Prévu pour une future version.
