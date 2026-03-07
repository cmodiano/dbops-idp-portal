# Architecture SSO - IDP Portal Django

**Story:** M.7 - Authentification SAML et sécurité
**Date:** 2026-02-04
**Status:** Implémentation complète

## Vue d'ensemble

Le portail IDP utilise SAML 2.0 (SP-initiated) pour l'authentification single sign-on. L'architecture est conçue pour s'intégrer avec l'infrastructure SSO de la plateforme hébergeuse.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Navigateur                                      │
│                                                                              │
│  1. Utilisateur accède au portail                                           │
│  2. Pas de token? → Redirige vers /auth/saml/login                          │
│  8. Reçoit access_token via URL fragment                                    │
│  9. Stocke access_token en mémoire (pas de localStorage)                    │
└─────────────────────────────────────────────────────────────────────────────┘
         │                                                    ▲
         │ (1)                                                │ (8)
         ▼                                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Django Backend (SP)                                  │
│                                                                              │
│  GET /auth/saml/login                                                       │
│  ├─ 3. Génère SAMLRequest (AuthnRequest)                                    │
│  └─ 4. Redirige vers IdP SSO URL                                            │
│                                                                              │
│  POST /auth/saml/callback                                                   │
│  ├─ 6. Reçoit SAMLResponse de l'IdP                                         │
│  ├─ 7. Valide assertion SAML                                                │
│  ├─ 7a. Extrait attributs (username, displayName, groups)                   │
│  ├─ 7b. Résout profils par AD groups                                        │
│  ├─ 7c. Crée/met à jour utilisateur en DB                                   │
│  ├─ 7d. Génère JWT (access + refresh)                                       │
│  └─ 8. Redirige vers SPA avec access_token                                  │
└─────────────────────────────────────────────────────────────────────────────┘
         │ (4)                                              ▲ (6)
         │                                                  │
         ▼                                                  │
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Identity Provider (IdP)                                │
│                                                                              │
│  5. Authentifie l'utilisateur (login LDAP/AD)                               │
│  5a. Retourne assertion SAML avec attributs                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Composants

### Service Provider (SP) - Django Backend

| Composant | Description |
|-----------|-------------|
| `idp_auth/saml_config.py` | Configuration python3-saml (SP/IdP settings) |
| `idp_auth/saml_utils.py` | Helpers pour convertir request Django → format python3-saml |
| `idp_auth/views.py` | Views SAML (SAMLLoginView, SAMLCallbackView) |
| `idp_auth/jwt_utils.py` | Génération/validation JWT (access + refresh tokens) |
| `idp_auth/authentication.py` | DRF authentication backend (JWTAuthentication) |

### Identity Provider (IdP)

Configuration requise côté IdP:
- **Entity ID:** Identifiant unique de l'IdP
- **SSO URL:** URL de login SAML
- **SLO URL:** URL de logout (optionnel)
- **Certificat X.509:** Pour validation des assertions signées

### Attributs SAML

| Attribut | Description | Obligatoire |
|----------|-------------|-------------|
| `username` | Identifiant unique de l'utilisateur | Oui (fallback: NameID) |
| `displayName` | Nom d'affichage | Non |
| `profile` | Profil principal | Non (défaut: dba_applicatif) |
| `groups` ou `memberOf` ou `ad_groups` | Groupes AD pour résolution profils | Recommandé |

## Tokens JWT

### Access Token

- **Durée:** 30 minutes (configurable: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Stockage client:** Mémoire JavaScript uniquement
- **Usage:** Header `Authorization: Bearer <token>` pour toutes les requêtes API
- **Payload:**
  ```json
  {
    "sub": "123",           // User ID
    "username": "jdoe",
    "profile": "dbops",
    "ad_groups": ["dbops", "dba_applicatif"],
    "type": "access",
    "exp": 1234567890
  }
  ```

### Refresh Token

- **Durée:** 8 heures (configurable: `JWT_REFRESH_TOKEN_EXPIRE_HOURS`)
- **Stockage client:** Cookie httpOnly (inaccessible au JavaScript)
- **Usage:** POST /auth/refresh pour obtenir un nouveau access token
- **Cookie properties:**
  - `httponly=True`
  - `secure=True` (en production)
  - `samesite=lax`
  - `path=/api/v1/auth`

## Configuration

### Variables d'environnement

```bash
# SAML SP
SAML_SP_ENTITY_ID=https://idp-portal.example.com/metadata
SAML_SP_ACS_URL=https://idp-portal.example.com/api/v1/auth/saml/callback
SAML_SP_CERT_PATH=/path/to/sp-cert.pem
SAML_SP_KEY_PATH=/path/to/sp-key.pem

# SAML IdP
SAML_IDP_ENTITY_ID=https://idp.example.com/entity
SAML_IDP_SSO_URL=https://idp.example.com/sso
SAML_IDP_SLO_URL=https://idp.example.com/slo
SAML_IDP_CERT_PATH=/path/to/idp-cert.pem

# JWT
JWT_SECRET_KEY=<secret-key-minimum-32-chars>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_HOURS=8

# Dev bypass (NEVER in production)
AUTH_DEV_BYPASS=false
```

### Django settings.py

Les settings sont chargés automatiquement depuis les variables d'environnement:

```python
# SAML Configuration
SAML_SP_ENTITY_ID = os.getenv('SAML_SP_ENTITY_ID')
SAML_SP_ACS_URL = os.getenv('SAML_SP_ACS_URL')
# ... etc.

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
JWT_REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRE_HOURS', '8'))

# DRF Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['idp_auth.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
}
```

## Endpoints

| Endpoint | Méthode | Description | Auth |
|----------|---------|-------------|------|
| `/auth/saml/login` | GET | Initie flow SAML, redirige vers IdP | - |
| `/auth/saml/callback` | POST | Reçoit assertion SAML, émet JWT | - |
| `/auth/me` | GET | Profil utilisateur courant | Bearer JWT |
| `/auth/refresh` | POST | Refresh token → access token | Cookie |
| `/auth/logout` | POST | Clear refresh token cookie | - |

## Politique de sécurité

### NFR6 - TLS

- TLS 1.2+ requis
- Terminé au reverse proxy (Nginx)
- Pas de données sensibles en HTTP

### NFR9 - Expiration session

- Access token: 30 minutes
- Refresh token: 8 heures
- Pas de "remember me" (politique sécurité stricte)

### NFR10 - Audit accès non autorisé

- Chaque tentative de login SAML logguée (succès/échec)
- Chaque refresh token logguée
- Chaque logout loggué
- 401/403 sur endpoints auth loggués par middleware

### Headers de sécurité

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Cache-Control: no-store (pour API)
```

## Résolution des profils

Le système utilise les groupes AD pour résoudre les profils utilisateur:

1. L'IdP SAML retourne les groupes AD dans `groups`, `memberOf` ou `ad_groups`
2. Django cherche les profils dont `ad_group` correspond aux groupes AD
3. Plusieurs profils peuvent matcher → cumulative permissions (Story 2.12)
4. Si aucun profil ne matche → 403 NO_PROFILE

```python
# Exemple de résolution
ad_groups = ['CN=DBOps,OU=Groups,DC=example,DC=com', 'CN=DBA-Infra,OU=Groups']
profiles = Profile.objects.find_by_ad_groups(ad_groups)
# → [Profile(name='dbops'), Profile(name='dba_infrastructure')]
```

## Mode développement

Pour le développement local sans IdP:

```bash
AUTH_DEV_BYPASS=true
```

Ce mode:
- Skip complètement l'IdP
- Crée automatiquement un utilisateur dev (id=0, username=dev-user, profile=dbops)
- Émet des JWT valides
- **JAMAIS en production**

## Intégration avec la plateforme hébergeuse

### Prérequis

1. **Métadonnées SP:** Fournir à l'hébergeur:
   - Entity ID: `SAML_SP_ENTITY_ID`
   - ACS URL: `SAML_SP_ACS_URL`
   - Certificat SP (si signature requise)

2. **Métadonnées IdP:** Recevoir de l'hébergeur:
   - Entity ID
   - SSO URL
   - Certificat IdP (pour validation signatures)

3. **Mapping attributs:** S'accorder sur les noms d'attributs SAML:
   - Comment l'IdP nomme le username
   - Comment l'IdP nomme les groupes AD

### Alternatives d'intégration

Si la plateforme hébergeuse a déjà un proxy SSO:

1. **Option proxy:** L'hébergeur gère le SAML, le portail reçoit directement l'identité via headers (ex: `X-Remote-User`)
2. **Option django-saml2:** Utiliser django-saml2 au lieu de python3-saml si l'hébergeur l'impose

## Voir aussi

- [SSO Runbook](sso-runbook.md) - Procédures de dépannage
- [DRF API Migration Notes](drf-api-migration-notes.md) - Notes de migration
