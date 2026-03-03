# Documentation API - DBOps Portal

## Accès aux interfaces de documentation

### Swagger UI — API complète (privée, filtrée par permissions)
- **URL** : `http://localhost:8000/api/schema/swagger-ui/`
- **Accès** : authentification requise (session SAML ou JWT)
- **Filtrage** : chaque utilisateur ne voit que les endpoints auxquels il a droit (permissions DRF)
- Ex. : un DBA ne voit pas les endpoints admin (profiles, audit, etc.) ; un DBOPS voit tout

### Swagger UI — API publique
- **URL** : `http://localhost:8000/api/schema/swagger-ui-public/`
- Sous-ensemble d'endpoints destinés aux consommateurs externes
- Section **Schemas** (components) masquée pour une doc plus légère
- Inclut : catalog, auth, executions, reference, integrations/types
- Exclut : admin, audit, dashboard, inventory, profiles, help

### ReDoc
- **URL** : `http://localhost:8000/api/schema/redoc/` (complet)
- **URL** : `http://localhost:8000/api/schema/redoc-public/` (public, section Schemas masquée)
- Documentation statique organisée par tags/domaines

### Schéma OpenAPI brut
- **URL** : `http://localhost:8000/api/schema/` (complet)
- **URL** : `http://localhost:8000/api/schema/public/` (public)
- Format JSON OpenAPI 3.0

## Authentification

Deux flux d'authentification sont disponibles :

### Flux SAML (interactif)

Pour les utilisateurs connectés via le portail (SAML) :
1. Cliquer sur **Authorize** en haut à droite
2. Entrer votre token JWT : `Bearer <votre_token>`
3. Cliquer sur **Authorize**

> En mode développement avec `AUTH_DEV_BYPASS=True`, utiliser `Bearer dev-mock-token-for-testing`.

### Flux API key (programmatique)

Pour les scripts, pipelines CI/CD ou consommation API externe :
1. Appeler `POST /api/v1/auth/token` avec le header `X-API-Key` contenant votre clé API
2. Copier `access_token` de la réponse JSON (`data.access_token`)
3. Cliquer **Authorize** et coller le token **sans préfixe "Bearer"** — Swagger l'ajoute automatiquement

> Pour les détails complets (curl, erreurs, rate limit, création de clés), consulter [api-self-service.md](api-self-service.md) (doc interne) ou l'interface interactive [Swagger UI](http://localhost:8000/api/schema/swagger-ui/).

## Export du schéma

Pour exporter le schéma OpenAPI en fichier YAML :

```bash
python manage.py spectacular --file openapi-schema.yml
```

Pour valider le schéma :

```bash
python manage.py spectacular --validate
```

## Organisation des endpoints

Les endpoints sont organisés par tags :

| Tag | Description |
|-----|-------------|
| `catalog` | Gestion du catalogue d'actions |
| `executions` | Exécution et suivi des actions |
| `profiles` | Gestion des profils et permissions RBAC |
| `inventory` | Inventaire des targets et environnements |
| `integrations` | Intégrations plateformes distantes |
| `audit` | Audit trail et conformité SOC1 |
| `auth` | Authentification SAML et JWT |
| `reference` | Données de référence (engines, platforms, catégories) |
| `dashboard` | Dashboard et analytics |
| `scheduling` | Planification et exécutions programmées |

## Conventions d'annotation OpenAPI

Pour les développeurs ajoutant de nouveaux endpoints :

### Viewsets
```python
from drf_spectacular.utils import extend_schema, extend_schema_view

@extend_schema_view(
    list=extend_schema(tags=['mon_tag'], summary='Description courte'),
    create=extend_schema(tags=['mon_tag'], summary='Créer un objet'),
)
class MonViewSet(viewsets.ModelViewSet):
    ...
```

### APIViews
```python
from drf_spectacular.utils import extend_schema

class MaVue(APIView):
    @extend_schema(tags=['mon_tag'], summary='Description', responses={200: MonSerializer})
    def get(self, request):
        ...
```

### SerializerMethodField
```python
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

@extend_schema_field(OpenApiTypes.INT)
def get_mon_champ(self, obj):
    return obj.count
```

## Dépendances

- **drf-spectacular** >= 0.27.0 : Génération automatique du schéma OpenAPI
- Configuration dans `settings.py` : `SPECTACULAR_SETTINGS`
- Extension auth : `core/schema.py` (JWTAuthenticationExtension)

## Story de référence

Story 22.20 — Epic 22 : Amélioration Qualité du Code
