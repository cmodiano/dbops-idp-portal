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
# SSO Runbook - Procédures de dépannage

**Story:** M.7 - Authentification SAML et sécurité
**Date:** 2026-02-04

## Erreurs courantes

### 403 SAML_VALIDATION_FAILED

**Symptôme:** L'utilisateur est redirigé vers l'IdP mais reçoit une erreur après le callback.

**Causes possibles:**

1. **Certificat IdP invalide ou expiré**
   - Vérifier `SAML_IDP_CERT_PATH`
   - Comparer avec le certificat actuel de l'IdP

2. **ACS URL incorrecte**
   - L'URL configurée côté IdP ne correspond pas à `SAML_SP_ACS_URL`
   - Vérifier les trailing slashes

3. **Horloge système désynchronisée**
   - Les assertions SAML ont une fenêtre de validité
   - Synchroniser NTP sur le serveur

4. **Mauvais bindings**
   - Le SP attend HTTP-POST mais l'IdP envoie HTTP-Redirect

**Diagnostique:**

```bash
# Logs Django
grep "saml_callback_error" /var/log/idp-portal/app.log

# Détails de l'erreur dans les logs
# errors=["invalid_response"]
# reason="Signature validation failed"
```

**Résolution:**

1. Vérifier les métadonnées IdP (certificat, URLs)
2. Régénérer les métadonnées SP si nécessaire
3. Contacter l'équipe IdP si le problème persiste

---

### 403 NO_PROFILE

**Symptôme:** L'utilisateur s'authentifie avec succès mais n'a pas accès au portail.

**Causes possibles:**

1. **Groupes AD non mappés**
   - Les groupes AD de l'utilisateur ne correspondent à aucun profil

2. **Attribut groups manquant**
   - L'IdP ne retourne pas les groupes AD

3. **Profil non créé**
   - Le profil existe dans AD mais pas dans la table PROFILES

**Diagnostique:**

```bash
# Logs Django
grep "saml_callback_no_profile" /var/log/idp-portal/app.log

# Voir les groupes AD reçus
# ad_groups=['CN=UnknownGroup,DC=example']
```

**Résolution:**

1. Vérifier les groupes AD de l'utilisateur
2. Créer le profil correspondant dans Admin > Profiles
3. Mapper le `ad_group` du profil aux groupes AD de l'utilisateur

---

### 401 Invalid or expired token

**Symptôme:** L'utilisateur reçoit 401 sur les requêtes API après login.

**Causes possibles:**

1. **Token expiré**
   - Access token > 30 minutes

2. **Token malformé**
   - Problème de copie/colle du token

3. **Secret JWT différent**
   - Le serveur a changé de `JWT_SECRET_KEY`

**Diagnostique:**

```bash
# Décoder le token (sans vérification)
python -c "from jose import jwt; print(jwt.get_unverified_claims('$TOKEN'))"

# Vérifier l'expiration
# {"exp": 1234567890, ...}
```

**Résolution:**

1. Vérifier que `JWT_SECRET_KEY` est identique sur tous les serveurs
2. Rafraîchir le token via POST /auth/refresh
3. Se reconnecter si le refresh token est aussi expiré

---

### 401 NO_REFRESH_TOKEN

**Symptôme:** POST /auth/refresh échoue.

**Causes possibles:**

1. **Cookie non envoyé**
   - Problème CORS (credentials)
   - Cookie path incorrect

2. **Cookie expiré**
   - > 8 heures depuis le login

**Diagnostique:**

```javascript
// Dans la console navigateur
document.cookie  // Ne doit PAS voir refresh_token (httpOnly)
```

**Résolution:**

1. Vérifier `CORS_ALLOW_CREDENTIALS = True`
2. Vérifier que le frontend envoie `credentials: 'include'`
3. Se reconnecter

---

## Vérifications de santé

### Vérifier la configuration SAML

```python
# Django shell
from idp_auth.saml_config import get_saml_settings
import json
print(json.dumps(get_saml_settings(), indent=2))
```

### Vérifier les profils

```python
# Django shell
from profiles.models import Profile
for p in Profile.objects.all():
    print(f"{p.name}: ad_group={p.ad_group}")
```

### Tester la génération JWT

```python
# Django shell
from idp_auth.jwt_utils import create_access_token, verify_token

token = create_access_token({'sub': '1', 'username': 'test', 'profile': 'dbops', 'ad_groups': []})
print(f"Token: {token[:50]}...")

payload = verify_token(token)
print(f"Payload: sub={payload.sub}, username={payload.username}")
```

### Vérifier les logs d'audit

```sql
-- Oracle
SELECT * FROM AUDIT_LOG
WHERE ACTION_TYPE IN ('USER_LOGIN', 'USER_LOGOUT', 'USER_REFRESH')
ORDER BY TIMESTAMP DESC
FETCH FIRST 20 ROWS ONLY;
```

## Mode bypass développement

Pour activer temporairement le bypass (développement uniquement):

```bash
export AUTH_DEV_BYPASS=true
# Redémarrer Django
```

**ATTENTION:** Ne JAMAIS activer en production!

## Procédure de rotation des certificats

### Rotation du certificat SP

1. Générer nouveau certificat
   ```bash
   openssl req -new -x509 -days 365 -nodes -out sp-new.pem -keyout sp-new-key.pem
   ```

2. Mettre à jour les métadonnées côté IdP (nouveau cert)

3. Déployer le nouveau certificat
   ```bash
   export SAML_SP_CERT_PATH=/path/to/sp-new.pem
   export SAML_SP_KEY_PATH=/path/to/sp-new-key.pem
   ```

4. Redémarrer Django

### Rotation du certificat IdP

1. Recevoir le nouveau certificat de l'équipe IdP

2. Mettre à jour la configuration
   ```bash
   cp idp-new-cert.pem /path/to/idp-cert.pem
   export SAML_IDP_CERT_PATH=/path/to/idp-cert.pem
   ```

3. Redémarrer Django

### Rotation du secret JWT

**ATTENTION:** Invalide tous les tokens en cours!

1. Générer nouveau secret
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Planifier le déploiement hors heures de pointe

3. Mettre à jour la configuration
   ```bash
   export JWT_SECRET_KEY=nouveau-secret
   ```

4. Redémarrer Django

5. Tous les utilisateurs devront se reconnecter

## Contacts

| Équipe | Responsabilité |
|--------|----------------|
| Équipe IdP | Configuration IdP, certificats IdP, attributs SAML |
| Équipe Plateforme | Infrastructure, TLS, reverse proxy |
| Équipe IDP Portal | Configuration SP, profils, debugging |
