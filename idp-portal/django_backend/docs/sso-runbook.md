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
