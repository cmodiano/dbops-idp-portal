# Authentification SAML et JWT

## Vue d'ensemble

L'authentification utilise SAML 2.0 avec l'IdP d'entreprise. Après authentification SAML, le backend émet des tokens JWT pour les appels API.

## Flow d'authentification

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │     │   Backend   │     │     IdP     │     │   Oracle    │
│  (React)    │     │  (Django)   │     │  (AD FS)    │     │     DB      │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │  1. GET /auth/saml/login              │                   │
       ├──────────────────►│                   │                   │
       │                   │                   │                   │
       │  2. 302 Redirect to IdP               │                   │
       │◄──────────────────┤                   │                   │
       │                   │                   │                   │
       │  3. User authenticates                │                   │
       ├───────────────────────────────────────►                   │
       │                   │                   │                   │
       │  4. POST /auth/saml/callback (SAML Response)              │
       │                   │◄──────────────────┤                   │
       │                   │                   │                   │
       │                   │  5. Validate SAML │                   │
       │                   │  6. Extract claims (username, groups) │
       │                   │                   │                   │
       │                   │  7. Upsert user  │                   │
       │                   ├───────────────────────────────────────►
       │                   │                   │                   │
       │                   │  8. Create JWT (access + refresh)     │
       │                   │                   │                   │
       │  9. 302 to frontend with tokens       │                   │
       │◄──────────────────┤                   │                   │
       │                   │                   │                   │
       │  10. API calls with Bearer token      │                   │
       ├──────────────────►│                   │                   │
       │                   │  11. Validate JWT │                   │
       │                   │  12. Attach user + ad_groups          │
       │◄──────────────────┤                   │                   │
```

## Configuration SAML

### Variables d'environnement

```bash
# Service Provider (SP) - Notre application
SAML_SP_ENTITY_ID=https://idp-portal.example.com/metadata
SAML_SP_ACS_URL=http://localhost:8000/api/v1/auth/saml/callback
SAML_SP_CERT_PATH=/path/to/sp-cert.pem
SAML_SP_KEY_PATH=/path/to/sp-key.pem

# Identity Provider (IdP) - AD FS
SAML_IDP_ENTITY_ID=https://adfs.corp.example.com/entity
SAML_IDP_SSO_URL=https://adfs.corp.example.com/adfs/ls
SAML_IDP_SLO_URL=https://adfs.corp.example.com/adfs/ls?wa=wsignout1.0
SAML_IDP_CERT_PATH=/path/to/idp-cert.pem
```

### settings.py

```python
# SAML Configuration
SAML_SP_ENTITY_ID = os.getenv('SAML_SP_ENTITY_ID', 'https://idp-portal.example.com/metadata')
SAML_SP_ACS_URL = os.getenv('SAML_SP_ACS_URL', 'http://localhost:8000/api/v1/auth/saml/callback')
SAML_SP_CERT_PATH = os.getenv('SAML_SP_CERT_PATH', '')
SAML_SP_KEY_PATH = os.getenv('SAML_SP_KEY_PATH', '')

SAML_IDP_ENTITY_ID = os.getenv('SAML_IDP_ENTITY_ID', 'https://idp.example.com/entity')
SAML_IDP_SSO_URL = os.getenv('SAML_IDP_SSO_URL', 'https://idp.example.com/sso')
SAML_IDP_SLO_URL = os.getenv('SAML_IDP_SLO_URL', 'https://idp.example.com/slo')
SAML_IDP_CERT_PATH = os.getenv('SAML_IDP_CERT_PATH', '')
```

## Configuration JWT

### Variables d'environnement

```bash
JWT_SECRET_KEY=your-256-bit-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_HOURS=8
```

### settings.py

```python
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-me-in-production')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
JWT_REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRE_HOURS', '8'))
```

## JWT Utils

**Fichier:** `idp_auth/jwt_utils.py`

### Création de token

```python
def create_token(user_id: int, username: str, ad_groups: list[str],
                 token_type: str = 'access') -> str:
    """
    Crée un token JWT.

    Args:
        user_id: ID de l'utilisateur
        username: Nom d'utilisateur
        ad_groups: Liste des AD groups
        token_type: 'access' ou 'refresh'

    Returns:
        Token JWT encodé

    Payload:
        - sub: user_id
        - username: nom d'utilisateur
        - ad_groups: liste des AD groups
        - type: 'access' ou 'refresh'
        - iat: timestamp émission
        - exp: timestamp expiration
    """
```

### Vérification de token

```python
def verify_token(token: str, expected_type: str = 'access') -> TokenPayload | None:
    """
    Vérifie et décode un token JWT.

    Args:
        token: Token JWT
        expected_type: Type attendu ('access' ou 'refresh')

    Returns:
        TokenPayload si valide, None sinon

    Vérifications:
        - Signature valide
        - Non expiré
        - Type correct
    """
```

### Décodage non sécurisé (debug)

```python
def decode_token_unsafe(token: str) -> dict | None:
    """
    Décode un token sans vérifier la signature.

    ⚠️ SECURITY WARNING - CRITICAL:
    - JAMAIS pour l'authentification
    - JAMAIS pour prendre des décisions d'autorisation
    - JAMAIS faire confiance aux données retournées

    Seuls usages autorisés:
    - Debug/logging (afficher claims pour diagnostic)
    - Extraire des infos non-sensibles avant validation

    Cette fonction a fait l'objet d'un fix de sécurité CRITICAL
    dans Story M-7 pour s'assurer qu'elle n'est pas utilisée
    à la place de verify_token().
    """
```

**⚠️ Quand utiliser `verify_token()` vs `decode_token_unsafe()`:**

| Cas d'usage | Fonction à utiliser |
|-------------|---------------------|
| Authentifier une requête | `verify_token()` |
| Valider un refresh token | `verify_token()` |
| Logger le username pour debug | `decode_token_unsafe()` (OK) |
| Décider si un utilisateur a accès | `verify_token()` |
| Afficher les claims dans une erreur | `decode_token_unsafe()` (OK) |

## JWTAuthentication (DRF)

**Fichier:** `idp_auth/authentication.py`

```python
class JWTAuthentication(BaseAuthentication):
    """
    Backend d'authentification DRF pour JWT.

    Usage dans views:
        authentication_classes = [JWTAuthentication]

    Ou globalement dans settings:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': ['idp_auth.authentication.JWTAuthentication']
        }
    """

    def authenticate(self, request):
        """
        Authentifie la requête.

        1. Extrait le token du header Authorization
        2. Vérifie le token
        3. Charge l'utilisateur depuis la DB
        4. Attache ad_groups à l'utilisateur pour RBAC

        Returns:
            (user, None) si authentifié
            None si pas de header Authorization

        Raises:
            AuthenticationFailed si token invalide
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ', 1)[1]

        payload = verify_token(token, expected_type='access')
        if not payload:
            raise AuthenticationFailed('Token invalide ou expiré')

        try:
            user = User.objects.get(id=int(payload.sub))
        except User.DoesNotExist:
            raise AuthenticationFailed('Utilisateur non trouvé')

        # Attacher ad_groups pour RBAC
        user.ad_groups = payload.ad_groups

        return (user, None)
```

## Endpoints d'authentification

### GET /api/v1/auth/saml/login

Initie le flow SAML en redirigeant vers l'IdP.

```python
class SAMLLoginView(APIView):
    permission_classes = []

    def get(self, request):
        # Générer la requête SAML AuthnRequest
        authn_request = create_authn_request()

        # Rediriger vers l'IdP
        return redirect(f"{SAML_IDP_SSO_URL}?SAMLRequest={authn_request}")
```

### POST /api/v1/auth/saml/callback

Reçoit la réponse SAML de l'IdP.

```python
class SAMLCallbackView(APIView):
    permission_classes = []

    def post(self, request):
        saml_response = request.data.get('SAMLResponse')

        # Valider la réponse SAML
        claims = validate_saml_response(saml_response)
        if not claims:
            return Response({"error": "Invalid SAML response"}, status=400)

        # Extraire les claims
        username = claims.get('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name')
        ad_groups = claims.get('http://schemas.microsoft.com/ws/2008/06/identity/claims/groups', [])
        display_name = claims.get('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname')

        # Upsert utilisateur
        user = User.objects.create_or_update(
            username=username,
            display_name=display_name,
            saml_subject=claims.get('saml_subject'),
        )

        # Créer les tokens
        access_token = create_token(user.id, username, ad_groups, 'access')
        refresh_token = create_token(user.id, username, ad_groups, 'refresh')

        # Rediriger vers le frontend avec les tokens
        frontend_url = f"{FRONTEND_URL}/auth/callback?access_token={access_token}"
        response = redirect(frontend_url)

        # Optionnel: refresh token en cookie httpOnly
        response.set_cookie(
            'refresh_token',
            refresh_token,
            httponly=True,
            secure=True,
            samesite='Strict',
            max_age=JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        )

        return response
```

### POST /api/v1/auth/refresh

Rafraîchit le token d'accès.

```python
class RefreshView(APIView):
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            refresh_token = request.data.get('refresh_token')

        if not refresh_token:
            return Response({"error": "Refresh token required"}, status=400)

        payload = verify_token(refresh_token, expected_type='refresh')
        if not payload:
            return Response({"error": "Invalid refresh token"}, status=401)

        # Créer un nouveau access token
        access_token = create_token(
            user_id=int(payload.sub),
            username=payload.username,
            ad_groups=payload.ad_groups,
            token_type='access',
        )

        return Response({"data": {"access_token": access_token}})
```

### GET /api/v1/auth/me

Retourne le profil de l'utilisateur courant.

```python
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Récupérer les permissions cumulées
        permissions = ProfileService().get_cumulative_permissions(
            user.id,
            user.ad_groups or []
        )

        return Response({
            "data": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "ad_groups": user.ad_groups,
                "permissions": permissions,
            }
        })
```

## Mode développement (bypass)

Pour le développement local sans IdP:

```bash
AUTH_DEV_BYPASS=true
```

```python
# settings.py
AUTH_DEV_BYPASS = os.getenv('AUTH_DEV_BYPASS', 'False').lower() == 'true'
```

En mode bypass, un endpoint de dev login est disponible:

```
POST /api/v1/auth/dev-login
{
    "username": "dev-user",
    "ad_groups": ["DBA-DEV", "DBOPS"]
}
```

**⚠️ Ne jamais activer en production!**

## Résolution des profils

Après authentification, les AD groups dans le JWT sont utilisés pour résoudre les profils:

```python
# Dans JWTAuthentication.authenticate()
user.ad_groups = payload.ad_groups

# Dans les ViewSets
ad_groups = request.user.ad_groups  # ['CN=DBA-DEV,OU=Groups,...', ...]
profiles = Profile.objects.find_by_ad_groups(ad_groups)
permissions = ProfileService().get_cumulative_permissions(user.id, ad_groups)
```

## Sécurité

### Bonnes pratiques

1. **JWT Secret:** Utiliser une clé de 256 bits minimum
2. **Token expiration:** Access token court (30 min), refresh token plus long (8h)
3. **Refresh token:** Stocker en cookie httpOnly si possible
4. **HTTPS:** Toujours en production
5. **CORS:** Configurer les origines autorisées

### Audit des authentifications

```python
class AuditAuthMiddleware:
    """Middleware qui log les authentifications."""

    def __call__(self, request):
        response = self.get_response(request)

        if hasattr(request, 'user') and request.user.is_authenticated:
            AuditService.create_entry(
                user_id=str(request.user.id),
                action_type=AuditActionType.USER_LOGIN,
                entity_type=AuditEntityType.USER,
                entity_id=request.user.id,
                ip_address=get_client_ip(request),
            )

        return response
```
