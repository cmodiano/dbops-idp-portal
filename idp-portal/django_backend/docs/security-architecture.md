# Architecture de Sécurité — IDP Portal

## 5.3 Politique de Fallback Superuser (Story 22.2 CRIT-2)

### Contexte

Le système RBAC du portail IDP repose sur `DBOPSProfilePermission` pour protéger
les endpoints d'administration. Cette permission vérifie que l'utilisateur possède
un profil DBOPS (via attribut direct, relation M2M, ou groupes AD).

Avant la correction CRIT-2, un **fallback inconditionnel** accordait l'accès à tout
utilisateur `is_superuser=True`, même sans profil DBOPS. Cela violait le principe
du moindre privilège et créait un risque d'escalade de privilèges (un compte
superuser compromis contournait l'intégralité du RBAC).

### Décision

Le fallback superuser est désormais **conditionnel**, contrôlé par la variable
d'environnement `ALLOW_SUPERUSER_FALLBACK` :

| Environnement | `DEBUG` | `ALLOW_SUPERUSER_FALLBACK` | Comportement |
|---|:---:|:---:|---|
| Dev local | `True` | `True` | Fallback autorisé, log WARNING |
| Test/Staging | `False` | `False` | Fallback refusé, fail-secure |
| Production | `False` | `False` | Fallback refusé, fail-secure |

### Pourquoi le fallback est désactivé par défaut

1. **Principe du moindre privilège** — Les superusers Django sont des comptes à
   haut privilège pour l'admin Django, pas nécessairement pour le portail DBOPS.
   L'accès au portail doit être explicite via un profil DBOPS.

2. **Conformité SOC1** — L'audit trail exige que tous les accès soient traçables
   et vérifiables. Un bypass silencieux du RBAC crée un angle mort dans l'audit.

3. **Réduction de la surface d'attaque** — Un compte superuser compromis ne doit
   pas automatiquement accéder à toutes les fonctionnalités du portail.

### Comment activer le fallback en développement local

Ajouter dans le fichier `.env` :

```bash
ALLOW_SUPERUSER_FALLBACK=true
```

Cela permet aux développeurs d'accéder au portail avec un compte superuser sans
avoir à configurer un profil DBOPS complet.

### Risques en production

**Ne jamais activer `ALLOW_SUPERUSER_FALLBACK=true` en production.**

Si activé en production (`DEBUG=False`), un log `WARNING` est émis à chaque
utilisation du fallback avec les détails suivants :
- `user_id`, `username` — identification de l'utilisateur
- `allow_superuser_fallback=True` — confirmation que le fallback est actif
- `debug_mode=False` — alerte que le mode debug est désactivé

**Exemple de log structuré JSON émis par le système (Story 22.2 MEDIUM-1):**

```json
{
  "event": "security_rbac_bypass_superuser_fallback",
  "level": "warning",
  "timestamp": "2026-02-09T15:42:33.123Z",
  "user_id": 42,
  "username": "admin",
  "allow_superuser_fallback": true,
  "debug_mode": false,
  "logger": "core.permissions"
}
```

Les équipes SOC/ops doivent **alerter immédiatement** sur l'événement
`security_rbac_bypass_superuser_fallback` en production.

### Fichiers concernés

- `core/permissions.py` — Logique `DBOPSProfilePermission.has_permission()`
- `idp_backend/settings.py` — Définition `ALLOW_SUPERUSER_FALLBACK`
- `.env.production.template` — Documentation de la variable
- `idp_backend/test_settings.py` — `ALLOW_SUPERUSER_FALLBACK = False`

### Références

- Story 22.1 CRIT-1 : Correction du bug `AttributeError` masqué
- Story 22.2 CRIT-2 : Cette story — fallback conditionnel
- Story 17.5 : Pattern de validation startup checks pour secrets
- Story 15.2 : Tests de sécurité fonctionnels RBAC
