# Deep Code Review - IDP Portal Django Backend

**Date:** 2026-03-06
**Branche:** `claude/deep-code-review-0OaJN`
**Scope:** Backend Django — securite, RBAC, auth, WebSocket, workflows, qualite code

---

## Corrections appliquees (commit fe94fa3)

### FIX-1 : Pagination sans borne — cap a 1000

| Propriete | Valeur |
|---|---|
| **Fichier** | `core/pagination.py` |
| **Severite** | HIGH |
| **Statut** | FIXE |
| **Description** | `paginate_queryset()` acceptait `limit=999999` sans plafond, permettant des queries non bornees |
| **Correction** | Ajout `MAX_PAGE_SIZE = 1000` et `limit = min(limit, MAX_PAGE_SIZE)` |

### FIX-2 : Null safety — target_metadata

| Propriete | Valeur |
|---|---|
| **Fichier** | `executions/serializers.py` |
| **Severite** | MEDIUM |
| **Statut** | FIXE |
| **Description** | `ExecutionTargetSerializer` pouvait retourner `None` pour `target_metadata` si `get_target_metadata()` retourne `None` |
| **Correction** | `obj.get_target_metadata() or {}` — garantit toujours un dict |

### FIX-3 : step_type hardcode a 'platform'

| Propriete | Valeur |
|---|---|
| **Fichier** | `executions/workflow_step_executor.py` |
| **Severite** | MEDIUM |
| **Statut** | FIXE |
| **Description** | `StepExecutor` creait les `ExecutionStep` avec `step_type='platform'` en dur au lieu d'utiliser le type reel du step |
| **Correction** | Utilisation de `step_type=step_type_routing` (le type reel calcule par le routeur) |

### FIX-4 : Audit trail approbation — commentaire manquant

| Propriete | Valeur |
|---|---|
| **Fichier** | `executions/views/approval_views.py` |
| **Severite** | MEDIUM |
| **Statut** | FIXE |
| **Description** | `ApproveExecutionView` ne capturait pas le commentaire optionnel d'approbation dans l'audit log (contrairement au reject qui le faisait) |
| **Correction** | Ajout capture `approval_comment` depuis `request.data` + inclusion dans `AuditService.create_entry()` + schema OpenAPI mis a jour |

---

## Issues non corrigees — A traiter

### SEC-1 : Fallback permissif dans _check_approver_permission

| Propriete | Valeur |
|---|---|
| **ID** | SEC-1 |
| **Fichier** | `executions/views/approval_views.py:100-114` |
| **Severite** | HIGH |
| **Type** | Authorization |
| **Statut** | OUVERT |

**Description :**
Si `step_config` ne contient pas de `approver_profile_ids` (vide ou absent), le fallback autorise tout utilisateur ayant `is_approver=True` sur n'importe quel profil a approuver n'importe quel step.

```python
def _check_approver_permission(user: User, step_config: dict) -> bool:
    approver_profile_ids = step_config.get('approver_profile_ids') or []
    if approver_profile_ids:
        user_profile_ids = _get_user_profile_ids(user)
        return bool(user_profile_ids & set(approver_profile_ids))
    # Fallback : tout profil is_approver=True  <-- TROP PERMISSIF
    return _is_user_approver(user)
```

**Impact :** Un utilisateur avec profil `is_approver=True` peut approuver des steps qui ne lui sont pas destines si la config du step est incomplete.

**Recommandation :**
1. Exiger explicitement `approver_profile_ids` dans la config des steps d'approbation
2. Retourner `False` si `approver_profile_ids` est absent/vide (fail-secure)
3. Ou au minimum logger un warning quand le fallback est utilise

---

### SEC-2 : WebSocket ExecutionConsumer — pas de verification d'acces a l'execution

| Propriete | Valeur |
|---|---|
| **ID** | SEC-2 |
| **Fichier** | `executions/consumers.py:17-42` |
| **Severite** | MEDIUM |
| **Type** | Authorization |
| **Statut** | OUVERT |

**Description :**
Apres authentification JWT, `ExecutionConsumer` rejoint le channel group `execution_{id}` sans verifier que l'utilisateur a le droit de consulter cette execution. Un utilisateur authentifie peut s'abonner a n'importe quelle execution via l'URL `/ws/executions/{execution_id}`.

```python
async def connect(self) -> None:
    self.execution_id = self.scope["url_route"]["kwargs"].get("execution_id")
    # ... joins channel group IMMEDIATELY, no permission check
    await self.channel_layer.group_add(self.group_name, self.channel_name)
```

**Impact :** Fuite d'information — un utilisateur authentifie peut observer en temps reel les executions d'autres utilisateurs.

**Recommandation :**
1. Apres auth dans `handle_authenticated_message()`, verifier que l'execution appartient a l'utilisateur ou que l'utilisateur est admin
2. Fermer la connexion avec code 4003 si non autorise
3. Ne joindre le group channel qu'apres validation

---

### SEC-3 : API Key token — profils multi-profils non inclus

| Propriete | Valeur |
|---|---|
| **ID** | SEC-3 |
| **Fichier** | `idp_auth/views/api_keys.py:93-99` |
| **Severite** | MEDIUM |
| **Type** | Authorization |
| **Statut** | OUVERT |

**Description :**
Lors de l'echange API Key -> JWT, le token genere ne contient que `user.profile` (champ string simple) et hardcode `ad_groups` a `[user.profile]`. Les profils M2M (`user.profiles.all()`) et les vrais AD groups ne sont pas inclus.

```python
token_data = {
    'sub': str(user.id),
    'username': user.username,
    'profile': user.profile,           # Seulement le profil principal
    'ad_groups': [user.profile],        # Hardcode, pas les vrais AD groups
}
```

**Impact :** Les permissions RBAC downstream (qui utilisent `ad_groups` en priorite) seront incorrectes pour les utilisateurs multi-profils authentifies via API key.

**Recommandation :**
1. Inclure tous les profils M2M dans le token : `[p.name for p in user.profiles.all()]`
2. Ou utiliser `ProfileManager.find_by_ad_groups()` pour populer correctement
3. Ajouter des tests pour le scenario multi-profil via API key

---

### SEC-4 : CORS — pas de validation que CORS_ORIGIN est configure en production

| Propriete | Valeur |
|---|---|
| **ID** | SEC-4 |
| **Fichier** | `idp_backend/settings.py:465-471` |
| **Severite** | MEDIUM |
| **Type** | Configuration |
| **Statut** | OUVERT |

**Description :**
`CORS_ALLOWED_ORIGINS` a un default `http://localhost:5173` via `os.getenv('CORS_ORIGIN', 'http://localhost:5173')`. Si la variable d'environnement `CORS_ORIGIN` n'est pas definie en production, les requetes cross-origin depuis localhost seront acceptees.

`CORS_ALLOW_CREDENTIALS = True` est active, ce qui amplifie le risque en cas de mauvaise configuration CORS.

**Recommandation :**
1. Ajouter un check au demarrage : si `DEBUG=False` et `CORS_ORIGIN` non defini, lever une erreur
2. Considerer `CORS_ALLOW_CREDENTIALS = False` si non necessaire

---

### SEC-5 : Superuser fallback — risque de misconfiguration production

| Propriete | Valeur |
|---|---|
| **ID** | SEC-5 |
| **Fichier** | `core/permissions.py:213-227` |
| **Severite** | MEDIUM |
| **Type** | Authorization |
| **Statut** | OUVERT |

**Description :**
`ALLOW_SUPERUSER_FALLBACK` (default `False`) permet de bypasser tout le RBAC pour les superusers. Le seul controle est un `logger.warning()`. Aucun mecanisme actif n'empeche l'activation en production.

```python
if getattr(settings, 'ALLOW_SUPERUSER_FALLBACK', False) and request.user.is_superuser:
    logger.warning("security_rbac_bypass_superuser_fallback", ...)
    return True
```

**Recommandation :**
1. Ajouter un check au demarrage : `if ALLOW_SUPERUSER_FALLBACK and not DEBUG: raise ImproperlyConfigured(...)`
2. Ou supprimer ce setting et exiger un profil admin explicite

---

### SEC-6 : Dev bypass auth — pas d'entree audit

| Propriete | Valeur |
|---|---|
| **ID** | SEC-6 |
| **Fichier** | `idp_auth/authentication.py:53-74` |
| **Severite** | MEDIUM |
| **Type** | Audit |
| **Statut** | OUVERT |

**Description :**
Le mode dev bypass (`AUTH_DEV_BYPASS=True` + token `dev-mock-token-for-testing`) cree/utilise un `dev-user` sans creer d'entree `AuditService`. Il logue un `CRITICAL` si `DEBUG=False` mais laisse la requete passer.

**Recommandation :**
1. Bloquer completement si `DEBUG=False` (return `None` au lieu de creer le user)
2. Creer une entree audit pour les auth dev bypass
3. Documenter que `dev-user` ne doit pas etre utilise pour les tests de securite

---

### SEC-7 : IP spoofing via X-Forwarded-For — warning sans blocage

| Propriete | Valeur |
|---|---|
| **ID** | SEC-7 |
| **Fichier** | `core/middleware.py:49-73` |
| **Severite** | LOW |
| **Type** | Input Validation |
| **Statut** | OUVERT |

**Description :**
`get_client_ip()` logue un warning si `X-Forwarded-For` contient plus de 2 IPs mais retourne quand meme la premiere IP. Si le reverse proxy (Nginx) ne filtre pas ce header, un attaquant peut injecter une IP arbitraire.

**Impact :** Faible si Nginx est correctement configure. Risque de contournement du rate limiting IP si mal configure.

**Recommandation :**
1. Valider `X-Forwarded-For` au niveau du reverse proxy Nginx (configuration infra)
2. Considerer rejeter les requetes avec headers suspects en production
3. Verifier que `SECURE_PROXY_SSL_HEADER` est bien configure

---

### DEP-1 : 19 vulnerabilites HIGH dans les dependances Python

| Propriete | Valeur |
|---|---|
| **ID** | DEP-1 |
| **Severite** | HIGH |
| **Type** | Dependencies |
| **Statut** | OUVERT (ref: security-remediation-plan.md VULN-001) |

**Description :**
19 vulnerabilites HIGH dans les dependances Python (azure-core, ecdsa, requests, protobuf, pyasn1, python-multipart, setuptools, urllib3). Voir `docs/security-remediation-plan.md` sections 3.1 et 3.2 pour le detail complet et la commande de mise a jour consolidee.

---

## Controles securite valides (points positifs)

| Controle | Fichier(s) | Verdict |
|---|---|---|
| SQL injection prevention (parameterized queries) | `inventory/query_builder.py`, `query_executor.py` | OK |
| WebSocket token dans premier message (pas dans URL) | `core/consumers.py` | OK |
| RBAC multi-layer filtering (targets + attributes + exclusions) | `inventory/rbac_filter.py` | OK |
| Security headers (nosniff, DENY, XSS, referrer) | `core/middleware.py:288-321` | OK |
| JWT validation (rejet refresh tokens, Bearer required) | `idp_auth/authentication.py` | OK |
| HTTPS/TLS enforce en production | `settings.py` (SSL_REDIRECT, HSTS, CSRF_COOKIE_SECURE) | OK |
| Webhook HMAC signature validation | `github_webhooks.py`, `terraform_webhooks.py` | OK |
| Object-level permissions (owner-or-admin) | `execution_views.py` (toutes les vues) | OK |
| Fail-secure defaults (DEBUG=False, SUPERUSER_FALLBACK=False) | `settings.py`, `permissions.py` | OK |
| Correlation ID tracking | `core/middleware.py` | OK |
| Max 5000 targets (memory exhaustion prevention) | `inventory/rbac_filter.py:19` | OK |

---

*Document genere par deep code review — 2026-03-06*
