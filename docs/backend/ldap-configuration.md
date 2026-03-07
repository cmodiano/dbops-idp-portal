# Configuration LDAP — Comptes de service

Ce document décrit la configuration LDAP requise pour activer l'authentification des comptes de service via `POST /api/v1/auth/service-login`.

## Vue d'ensemble

Le portail IDP intègre un `LDAPService` qui permet aux comptes Active Directory de s'authentifier de façon programmatique. Lorsqu'un compte de service appelle `/auth/service-login`, le portail :

1. Effectue un **bind LDAP** avec les credentials fournis (username + password)
2. Récupère les **groupes AD** du compte (attribut `memberOf`)
3. Résout le **profil IDP** associé via `Profile.objects.find_by_ad_groups(ad_groups)`
4. Émet un **JWT** avec les mêmes champs que le flow SAML (`sub`, `username`, `profile`, `ad_groups`)

Si `LDAP_URI` ou `LDAP_BASE_DN` est vide ou non défini, le service lève `LDAPUnavailableError` et l'endpoint retourne `503 LDAP_UNAVAILABLE`.

## Variables d'environnement

### LDAP_URI

| Attribut | Valeur |
|----------|--------|
| **Description** | URI de connexion au serveur LDAP / Active Directory |
| **Format** | `ldap://<host>:<port>` ou `ldaps://<host>:<port>` |
| **Valeur par défaut** | *(aucune)* — si vide, `LDAPUnavailableError` est levée |
| **Obligatoire en prod** | Oui |

**Exemples :**
```bash
# LDAP standard (port 389)
LDAP_URI=ldap://dc.example.com:389

# LDAPS avec TLS (port 636) — recommandé en production
LDAP_URI=ldaps://dc.example.com:636
```

> **Note :** En production, préférer `ldaps://` pour chiffrer les credentials en transit. La vérification du certificat TLS dépend de la configuration système.

---

### LDAP_BASE_DN

| Attribut | Valeur |
|----------|--------|
| **Description** | Base DN (Distinguished Name) de l'annuaire — racine des recherches LDAP |
| **Format** | DN LDAP standard : `DC=<domaine>,DC=<tld>` |
| **Valeur par défaut** | *(aucune)* |
| **Obligatoire en prod** | Oui |

**Exemples :**
```bash
LDAP_BASE_DN=DC=example,DC=com
LDAP_BASE_DN=DC=corp,DC=acme,DC=local
```

> **Note :** Si `LDAP_BASE_DN` est vide ou non défini, `LDAPService.authenticate()` lève `LDAPUnavailableError` → réponse `503 LDAP_UNAVAILABLE` (même comportement que `LDAP_URI` manquant).

---

### LDAP_USER_DN_TEMPLATE

| Attribut | Valeur |
|----------|--------|
| **Description** | Template du DN utilisé pour le bind LDAP — `{username}` est remplacé par la valeur fournie dans la requête |
| **Format** | Chaîne avec `{username}` comme placeholder |
| **Valeur par défaut** | `{username}` (insuffisant en production — le DN résultant ne sera pas un DN LDAP valide) |
| **Obligatoire en prod** | Oui |

Deux formats sont supportés (voir section [Formats du DN utilisateur](#formats-du-dn-utilisateur)).

**Exemples :**
```bash
# Format UPN (UserPrincipalName) — le plus courant en environnement AD
LDAP_USER_DN_TEMPLATE={username}@example.com

# Format Full DN — pour les OUs spécifiques
LDAP_USER_DN_TEMPLATE=CN={username},OU=ServiceAccounts,DC=example,DC=com
```

---

### LDAP_CONNECT_TIMEOUT

| Attribut | Valeur |
|----------|--------|
| **Description** | Délai maximum (en secondes) pour établir la connexion TCP au serveur LDAP |
| **Format** | Entier (secondes) |
| **Valeur par défaut** | `10` |
| **Obligatoire en prod** | Non |

**Exemples :**
```bash
LDAP_CONNECT_TIMEOUT=10    # défaut
LDAP_CONNECT_TIMEOUT=5     # environnement avec latence faible
LDAP_CONNECT_TIMEOUT=30    # environnement avec latence élevée ou LDAPS lent
```

Si le timeout est atteint, `LDAPUnavailableError` est levée → réponse `503 LDAP_UNAVAILABLE`.

---

### LDAP_RECEIVE_TIMEOUT

| Attribut | Valeur |
|----------|--------|
| **Description** | Délai maximum (en secondes) pour recevoir une réponse après connexion (ex: bind, search) |
| **Format** | Entier (secondes) |
| **Valeur par défaut** | `10` |
| **Obligatoire en prod** | Non |

**Exemples :**
```bash
LDAP_RECEIVE_TIMEOUT=10    # défaut
LDAP_RECEIVE_TIMEOUT=15    # si le serveur AD est lent à répondre aux recherches
```

---

### THROTTLE_SERVICE_LOGIN_RATE

| Attribut | Valeur |
|----------|--------|
| **Description** | Taux de rate limiting pour `POST /auth/service-login` (protection brute-force) |
| **Format** | `<nombre>/<période>` — période : `second`, `minute`, `hour`, `day` |
| **Valeur par défaut** | `5/minute` |
| **Obligatoire en prod** | Non |

**Exemples :**
```bash
THROTTLE_SERVICE_LOGIN_RATE=5/minute    # défaut — 5 tentatives/min par IP
THROTTLE_SERVICE_LOGIN_RATE=10/minute   # environnement moins restrictif
THROTTLE_SERVICE_LOGIN_RATE=1/second    # test de charge (ne pas utiliser en prod)
```

> **Note :** Ce paramètre configure `ServiceLoginThrottle` (scope `service_login`). Il est distinct du rate limit de `/auth/token` (scope `token`, 10/min fixe). Un en-tête `Retry-After` est retourné en cas de dépassement (réponse `429`).

---

## Formats du DN utilisateur

Le `LDAP_USER_DN_TEMPLATE` supporte deux formats selon la configuration de votre Active Directory :

### Format UPN (UserPrincipalName)

Le plus courant en environnement Windows AD. Le DN de bind est de la forme `user@domaine`.

```bash
LDAP_USER_DN_TEMPLATE={username}@example.com
```

Avec un username `svc-ci-cd`, le bind LDAP utilisera : `svc-ci-cd@example.com`

**Quand utiliser :** Lorsque vos comptes AD ont un `userPrincipalName` défini et que votre AD accepte l'authentification par UPN.

### Format Full DN

Pour les configurations AD plus strictes ou les OUs dédiées aux comptes de service.

```bash
LDAP_USER_DN_TEMPLATE=CN={username},OU=ServiceAccounts,DC=example,DC=com
```

Avec un username `svc-ci-cd`, le bind LDAP utilisera : `CN=svc-ci-cd,OU=ServiceAccounts,DC=example,DC=com`

**Quand utiliser :** Lorsque vos comptes de service sont dans une OU spécifique ou que le UPN n'est pas configuré.

> **Note :** Le username fourni dans la requête (`{"username": "svc-ci-cd"}`) est inséré tel quel dans le template. Assurez-vous que le format correspond exactement à ce qui est attendu par votre AD.

---

## Vérification de la configuration

### Test de connectivité LDAP

Avant de démarrer le serveur, vérifiez la connectivité depuis l'environnement d'exécution :

```bash
# Test de connectivité TCP (ldap3 installé dans le venv)
python3 -c "
from ldap3 import Server, Connection, ALL
import os

uri = os.environ.get('LDAP_URI', 'ldap://dc.example.com:389')
# Extraire host et port de l'URI
host = uri.split('//')[1].split(':')[0]
port = int(uri.split(':')[-1]) if ':' in uri.split('//')[1] else 389
use_ssl = uri.startswith('ldaps://')

server = Server(host, port=port, use_ssl=use_ssl, get_info=ALL)
conn = Connection(server)
conn.open()
print(f'✅ Connexion LDAP réussie : {uri}')
conn.unbind()
"
```

### Test d'authentification d'un compte de service

```bash
# Depuis l'environnement django_backend
cd idp-portal/django_backend
source .venv/bin/activate

python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idp_backend.settings')
import django; django.setup()

from idp_auth.ldap_service import LDAPService

svc = LDAPService()
try:
    groups = svc.authenticate('svc-ci-cd', 'password_ici')
    print(f'✅ Authentification réussie')
    print(f'   Groupes AD : {groups}')
except Exception as e:
    print(f'❌ Échec : {type(e).__name__}: {e}')
"
```

### Test via curl

```bash
curl -s -X POST https://portail.example.com/api/v1/auth/service-login \
  -H "Content-Type: application/json" \
  -d '{"username": "svc-ci-cd", "password": "votre_password"}' | python3 -m json.tool
```

**Réponse attendue en cas de succès :**
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

---

## Exemple de fichier `.env` complet

```bash
# ============================================================
# Configuration LDAP — Comptes de service
# ============================================================

# Connexion au serveur Active Directory
LDAP_URI=ldaps://dc.example.com:636
LDAP_BASE_DN=DC=example,DC=com

# Template DN pour le bind (format UPN recommandé)
LDAP_USER_DN_TEMPLATE={username}@example.com

# Timeouts de connexion (secondes)
LDAP_CONNECT_TIMEOUT=10
LDAP_RECEIVE_TIMEOUT=10

# Rate limiting pour /auth/service-login
THROTTLE_SERVICE_LOGIN_RATE=5/minute
```

> **Sécurité :** Ne jamais committer le fichier `.env` en dépôt. Utiliser un gestionnaire de secrets (Vault, AWS Secrets Manager, etc.) pour les environnements de production.

---

## Voir aussi

- [`api/self-service.md`](../api/self-service.md) — Guide d'utilisation de l'endpoint pour les développeurs
- [`docs/backend/api-reference.md`](api-reference.md) — Référence complète de l'endpoint `POST /auth/service-login`
- [`docs/backend/authentication.md`](authentication.md) — Architecture générale de l'authentification
- Documentation OpenAPI/Swagger : `/api/docs`
