# Configuration LDAP — Authentification portail IDP

## Vue d'ensemble

Le portail IDP supporte deux méthodes d'authentification : **LDAP** et **SAML**. LDAP est configuré comme méthode prioritaire afin de garantir que seuls les comptes à haut privilège (comptes AD dédiés, distincts des comptes laptop quotidiens) peuvent accéder au portail.

---

## Variable `PORTAL_AUTH_METHODS`

### Description

`PORTAL_AUTH_METHODS` contrôle l'ordre des méthodes d'authentification disponibles pour la connexion au portail. La première méthode de la liste est présentée en priorité.

### Configuration

| Paramètre | Valeur par défaut | Source |
|---|---|---|
| `PORTAL_AUTH_METHODS` | `"ldap,saml"` | Variable d'environnement `PORTAL_AUTH_METHODS` |

### Valeurs valides

- `"ldap"` — Authentification via LDAP bind (username/password)
- `"saml"` — Authentification SSO SAML 2.0
- Toute autre valeur est ignorée silencieusement

### Exemples `.env`

```env
# LDAP uniquement — recommandé pour la sécurité (comptes à haut privilège uniquement)
PORTAL_AUTH_METHODS=ldap

# LDAP prioritaire, SAML en fallback (transition)
PORTAL_AUTH_METHODS=ldap,saml

# SAML uniquement (désactive LDAP pour le portail)
PORTAL_AUTH_METHODS=saml
```

### Comportement par défaut

Sans variable d'environnement définie, `PORTAL_AUTH_METHODS` vaut `["ldap", "saml"]` :
- LDAP est en première position (prioritaire)
- SAML est disponible en fallback

---

## Endpoint `POST /api/v1/auth/portal-login`

### Description

Authentifie un utilisateur interactif du portail avec son **compte AD à haut privilège** (username/password) via LDAP bind. Cet endpoint est distinct de `/auth/service-login` qui cible les comptes de service (scripts, CI/CD).

### Requête

```http
POST /api/v1/auth/portal-login/
Content-Type: application/json

{
  "username": "jdupont-admin",
  "password": "mot-de-passe-haut-privilege"
}
```

### Réponse succès (200)

```json
{
  "data": {
    "access_token": "<JWT>",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

Un cookie `refresh_token` httpOnly est également positionné :

```
Set-Cookie: refresh_token=<JWT>; Path=/api/v1/auth; HttpOnly; SameSite=Lax
```

### Codes d'erreur

| Code HTTP | Code erreur | Description |
|---|---|---|
| 400 | — | Champ `username` ou `password` manquant |
| 401 | `INVALID_CREDENTIALS` | Username ou password incorrect |
| 403 | `NO_PROFILE` | Aucun profil IDP associé aux groupes AD du compte |
| 429 | `RATE_LIMIT_EXCEEDED` | Trop de tentatives (limite : 5/min par IP) |
| 503 | `LDAP_UNAVAILABLE` | Service LDAP inaccessible |

### Exemple réponse erreur 401

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Credentials invalides"
  }
}
```

---

## Authentification portail (comptes à haut privilège)

Epic 68 exige que le portail IDP soit accessible **uniquement aux comptes AD à haut privilège** (comptes dédiés, distincts des comptes laptop quotidiens). L'utilisateur saisit manuellement son identifiant et mot de passe — il n'y a pas de SSO transparent.

### Flux d'authentification `portal-login`

```
1. Utilisateur saisit username + password
2. POST /api/v1/auth/portal-login/
3. Validation du corps de la requête
4. LDAPService.authenticate(username, password) → LDAP bind
   ├── Échec bind → 401 INVALID_CREDENTIALS (+ audit USER_LOGIN échec)
   └── Succès → récupération des groupes AD (memberOf)
5. Profile.objects.find_by_ad_groups(ad_groups)
   └── Aucun profil → 403 NO_PROFILE (+ audit USER_LOGIN échec)
6. AuthService.create_or_update_user() → JIT provisioning
7. Création JWT access_token + refresh_token
8. Audit AuditActionType.USER_LOGIN (succès)
9. Retour 200 + cookie refresh_token httpOnly
```

---

## Distinction `service-login` vs `portal-login`

| Caractéristique | `/auth/service-login` | `/auth/portal-login` |
|---|---|---|
| **Cible** | Scripts, CI/CD, automatisations | Utilisateurs interactifs (navigateur) |
| **Type de compte** | Compte de service AD | Compte à haut privilège AD |
| **Audit** | `SERVICE_LOGIN` | `USER_LOGIN` |
| **Throttle** | `ServiceLoginThrottle` (5/min) | `PortalLoginThrottle` (5/min) |
| **Story origine** | 49.2 | 68.1 |

---

## Configuration LDAP

Le service LDAP est configuré via les variables d'environnement suivantes (Story 49.1) :

| Variable | Description | Défaut |
|---|---|---|
| `LDAP_URI` | URI du serveur LDAP (ex: `ldap://ad.example.com:389`) | — |
| `LDAP_BIND_DN` | DN du compte de bind technique | — |
| `LDAP_BIND_PASSWORD` | Mot de passe du compte de bind | — |
| `LDAP_BASE_DN` | Base DN de recherche des utilisateurs | — |
| `LDAP_CONNECT_TIMEOUT` | Timeout connexion (secondes) | `10` |
| `LDAP_RECEIVE_TIMEOUT` | Timeout réception (secondes) | `10` |

### Rate limiting

La variable `THROTTLE_PORTAL_LOGIN_RATE` permet de configurer le taux de throttling :

```env
# Par défaut : 5 requêtes par minute par IP
THROTTLE_PORTAL_LOGIN_RATE=5/minute
```

---

*Document généré pour Story 68.1 — Configuration LDAP comme méthode d'authentification prioritaire.*
