# Système RBAC (Role-Based Access Control)

## Vue d'ensemble

Le système RBAC d'IDP Portal contrôle l'accès aux actions et targets basé sur les profils utilisateurs. Un profil est lié à un groupe Active Directory (AD group).

## Architecture RBAC

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Utilisateur                                │
│                      (AD groups dans JWT)                            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        ProfileService                                │
│               get_cumulative_permissions(user_id, ad_groups)         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌───────────┐   ┌───────────┐   ┌───────────┐
        │ Profile 1 │   │ Profile 2 │   │ Profile 3 │
        │ (DBA-DEV) │   │ (DBA-PROD)│   │ (AUDITOR) │
        └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
              │               │               │
              ▼               ▼               ▼
        ┌──────────────────────────────────────────┐
        │         Permissions Cumulées              │
        │  (Union de toutes les permissions)        │
        └──────────────────────────────────────────┘
```

## Modèles de données

### Profile

```python
class Profile(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=4000, null=True)
    ad_group = models.CharField(max_length=512)  # Ex: "CN=DBA-DEV,OU=Groups,DC=corp"
    is_admin = models.IntegerField(default=0)    # 1 = profil admin (is_admin_bool = True)
    is_auditor = models.IntegerField(default=0)  # 1 = profil auditeur
```

### ProfileActionPermission

```python
class ProfileActionPermission(models.Model):
    profile = models.OneToOneField(Profile, primary_key=True)
    permission_type = models.CharField()  # 'ALL' | 'LIST' | 'PATTERN'

    # Stockés en JSON (CLOB Oracle)
    action_ids_json = models.TextField()      # [1, 2, 3]
    tag_patterns_json = models.TextField()    # ["oracle", "patching"]
    environments_json = models.TextField()    # ["dev", "staging"]
```

### ProfileTargetPermission

```python
class ProfileTargetPermission(models.Model):
    profile = models.OneToOneField(Profile, primary_key=True)
    permission_type = models.CharField()  # 'ALL' | 'LIST' | 'PATTERN'

    # Stockés en JSON (CLOB Oracle)
    target_names_json = models.TextField()     # ["db-prod-01", "db-prod-02"]
    target_patterns_json = models.TextField()  # ["db-*", "oracle-*"]
```

## Types de permissions

### Permission Actions

| Type | Description | Exemple |
|------|-------------|---------|
| `ALL` | Accès à toutes les actions | Profil admin |
| `LIST` | Accès à une liste spécifique d'actions | `action_ids: [1, 2, 3]` |
| `PATTERN` | Accès aux actions ayant certains tags | `tag_patterns: ["oracle", "patching"]` |

### Permission Environments

Liste des environnements autorisés pour l'exécution:

```json
{
  "environments": ["dev", "staging", "prod"]
}
```

### Permission Targets

| Type | Description |
|------|-------------|
| `ALL` | Accès à tous les targets |
| `LIST` | Accès à une liste de targets nommés |
| `PATTERN` | Accès aux targets matchant un pattern |

## Permissions DRF

### AdminProfilePermission

> **Note :** `DBOPSProfilePermission` est un alias maintenu pour la rétrocompatibilité. Utiliser désormais `AdminProfilePermission` (nom canonique depuis story 56.4).

`AdminProfilePermission` (dans `core/permissions.py`) restreint l'accès aux endpoints admin (profiles, integrations, actions, analytics) aux seuls profils avec `is_admin=1` en base de données. Tous les chemins d'authentification utilisent désormais `Profile.is_admin_bool` — il n'y a plus de comparaison par nom de profil.

**Story 56.7** : Le chemin SAML string utilise désormais un DB lookup (`Profile.objects.filter(name__iexact=...)`) au lieu de `DBOPS_PROFILE_NAMES`. La distinction DBA/DBOPS provient maintenant exclusivement de la base de données (`is_admin=0` pour DBA, `is_admin=1` pour DBOPS).

**Ordre canonique de résolution (Story 56.7) :**
1. `user.ad_groups` → `Profile.objects.find_by_ad_groups()` → `any(p.is_admin_bool)`
2. `user.profiles` (M2M si présent) → `any(p.is_admin_bool)`
3. `user.profile` (string) → `Profile.objects.filter(name__iexact=...).first()` → `is_admin_bool`
4. `user.profile` (objet Profile ORM) → `is_admin_bool` direct

En cas d'`OperationalError` DB, l'accès est refusé (fail-secure) et un log structuré `profile_db_unavailable_admin_check` est émis.

```python
class AdminProfilePermission(permissions.BasePermission):
    """
    Permission class that requires an admin profile (is_admin=1 in DB).

    Story 56.7: Fully flag-based — uses Profile.is_admin_bool for all auth paths.
    Story 15.2 AC2: DBA (is_admin=0) est refusé sur les endpoints admin.
    Seul DBOPS (ou tout profil avec is_admin=1) peut y accéder.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        profiles = _resolve_user_profiles(request.user)
        if any(getattr(p, 'is_admin_bool', False) for p in profiles):
            return True

        # Fallback superuser : uniquement si ALLOW_SUPERUSER_FALLBACK=True (défaut: False)
        if getattr(settings, 'ALLOW_SUPERUSER_FALLBACK', False) and request.user.is_superuser:
            return True

        return False
```

> **Note :** `ADMIN_PROFILE_NAMES` et `DBOPS_PROFILE_NAMES` dans `settings.py` sont **dépréciés** (Story 56.7). Ils ne sont plus utilisés par `core/permissions.py`. Conservés pour compatibilité avec d'éventuels outils externes.

**Utilisation dans ViewSet:**

```python
class ActionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, AdminProfilePermission]
```

### OptionalUserPermission

```python
class OptionalUserPermission(permissions.BasePermission):
    """
    Permission pour les endpoints publics.
    Autorise tous les utilisateurs (auth optionnelle).
    Le filtrage RBAC se fait dans le ViewSet.
    """

    def has_permission(self, request, view):
        return True
```

**Utilisation dans ViewSet:**

```python
class CatalogActionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [OptionalUserPermission]
```

## Filtrage RBAC dans les ViewSets

> **Story 26.3 :** La logique ci-dessous a été extraite dans `CatalogRBACService`
> (`catalog/rbac_service.py`). Utiliser `CatalogRBACService().get_permissions(user)`,
> `filter_actions()` et `check_action()` à la place des fonctions legacy.

### Récupération des permissions (legacy — voir CatalogRBACService)

```python
def _get_cumulative_permissions_for_user(user):
    """
    Récupère les permissions cumulées d'un utilisateur.

    Args:
        user: User instance avec ad_groups attachés

    Returns:
        Dict avec actions_type, action_ids, tag_patterns, environments
        ou None si pas de permissions
    """
    if not user or not user.is_authenticated:
        return None

    ad_groups = user.ad_groups or []

    profile_service = ProfileService()
    permissions = profile_service.get_cumulative_permissions(user.id, ad_groups)

    # Agréger les permissions (union)
    action_ids = set()
    tag_patterns = set()
    environments = set()
    actions_type_all = False

    for perm in permissions.get('action_permissions', []):
        if perm.get('actions_type') == 'all':
            actions_type_all = True
        else:
            action_ids.update(perm.get('action_ids', []) or [])
            tag_patterns.update(perm.get('tag_patterns', []) or [])
        environments.update(perm.get('environments', []) or [])

    return {
        'actions_type': 'all' if actions_type_all else 'pattern' if tag_patterns else 'list',
        'action_ids': sorted(action_ids),
        'tag_patterns': sorted(tag_patterns),
        'environments': sorted(environments),
    }
```

### Filtrage de liste

```python
def _filter_by_rbac(actions, cumulative_permissions):
    """
    Filtre une liste d'actions selon les permissions RBAC.

    Args:
        actions: QuerySet ou liste d'actions
        cumulative_permissions: Dict de permissions cumulées

    Returns:
        Liste filtrée d'actions
    """
    if cumulative_permissions is None:
        return actions

    actions_type = cumulative_permissions.get('actions_type', 'all')
    if actions_type == 'all':
        return actions

    action_ids = set(cumulative_permissions.get('action_ids', []))
    tag_patterns = set(cumulative_permissions.get('tag_patterns', []))

    result = []
    for action in actions:
        # Check if action_id is in allowed list
        if action.id in action_ids:
            result.append(action)
            continue

        # Check if any tag matches pattern
        action_tags = {at.tag.name for at in action.actiontag_set.all()}
        if action_tags & tag_patterns:
            result.append(action)

    return result
```

### Vérification pour une action spécifique

```python
def _check_rbac_for_action(action, cumulative_permissions):
    """
    Vérifie si l'utilisateur a accès à une action spécifique.

    Returns:
        True si accès autorisé, False sinon
    """
    if cumulative_permissions is None:
        return True

    actions_type = cumulative_permissions.get('actions_type', 'all')
    if actions_type == 'all':
        return True

    action_ids = set(cumulative_permissions.get('action_ids', []))
    if action.id in action_ids:
        return True

    tag_patterns = set(cumulative_permissions.get('tag_patterns', []))
    action_tags = {at.tag.name for at in action.actiontag_set.all()}
    if action_tags & tag_patterns:
        return True

    return False
```

### Exemple actuel (CatalogActionViewSet)

```python
# Utiliser CatalogRBACService (Story 26.3)
from catalog.rbac_service import CatalogRBACService

rbac_service = CatalogRBACService()

def list(self, request):
    cumulative_permissions = rbac_service.get_permissions(request.user)
    queryset = self.get_queryset()
    if cumulative_permissions:
        actions_list = list(queryset)
        filtered_actions = rbac_service.filter_actions(actions_list, cumulative_permissions)
        queryset = queryset.filter(id__in=[a.id for a in filtered_actions])
    # ...

def retrieve(self, request, pk=None):
    instance = self.get_object()
    cumulative_permissions = rbac_service.get_permissions(request.user)
    if cumulative_permissions:
        if not rbac_service.check_action(instance, cumulative_permissions):
            raise NotFoundError(message="Action non trouvée")
    # ...
```

## Cumul des permissions multi-profils

> **Spec de référence :** `_bmad-output/planning-artifacts/spec-rbac-cumul-permissions-multi-groupes.md`

Quand un utilisateur appartient à plusieurs AD groups, ses permissions sont **cumulées** (union):

```python
# Utilisateur avec AD groups: ["DBA-DEV", "DBA-STAGING"]

# Profile DBA-DEV:
#   action_ids: [1, 2]
#   environments: ["dev"]

# Profile DBA-STAGING:
#   action_ids: [3, 4]
#   tag_patterns: ["oracle"]
#   environments: ["staging"]

# Permissions cumulées (via CatalogRBACService.get_permissions):
#   action_ids: [1, 2, 3, 4]
#   tag_patterns: ["oracle"]
#   environments: ["dev", "staging"]
```

### Implémentation actuelle

Le cumul est réalisé en deux étapes :

1. **`ProfileService.get_cumulative_permissions(user_id, ad_groups)`** (`profiles/services.py`)
   — Résout les profils via `Profile.objects.find_by_ad_groups(ad_groups)` et retourne une liste brute de permissions par profil (une entrée par profil correspondant).

2. **`CatalogRBACService.get_permissions(user)`** (`catalog/rbac_service.py`)
   — Agrège les permissions via union (`set.update()`) sur `action_ids`, `tag_patterns` et `environments`. Si un profil a `actions_type='all'`, le résultat final est `'all'` (most permissive wins).

3. **`CurrentUserProfileView.get()`** (`idp_auth/views.py`)
   — Expose `cumulative_permissions` au frontend via `GET /auth/me` pour le filtrage côté catalogue.

### Formats de permissions (Story 2.31 H2)

| Endpoint / Service | Format retourné |
|--------------------|----------------|
| **`GET /auth/me`** (`CurrentUserProfileView`) | Format brut `ProfileService` : `{action_permissions: [{actions_type, action_ids, tag_patterns, environments}, ...], target_permissions: [...]}` |
| **`CatalogRBACService.get_permissions()`** (catalogue) | Format agrégé : `{actions_type, action_ids, tag_patterns, environments}` |

Le frontend qui consomme `/auth/me` reçoit le format brut. Le catalogue API utilise `CatalogRBACService` et retourne des résultats déjà filtrés. Si le frontend doit filtrer côté client, il doit agréger les `action_permissions` comme le fait `CatalogRBACService.get_permissions()`.

### Matching des tag_patterns (Story 2.31 M3)

`CatalogRBACService.filter_actions()` utilise une **intersection exacte** (`act_tags & tag_patterns`), pas de matching glob (fnmatch). Les patterns comme `db-*` ou `*-prod` ne matchent pas — seuls les tags littéraux (ex. `oracle`, `sql-server`) sont supportés. Pour des patterns glob, une évolution future serait nécessaire.

### Cas d'usage : DBA multi-technologies (PRD / spec)

Des DBAs qui travaillent sur **SQL** et **Oracle** appartiennent à deux groupes (ex. `DBA-SQL`, `DBA-ORACLE`), chacun lié à un profil distinct. Le portail doit leur donner accès aux **actions et droits des deux technologies** (union). Si un profil autorise X et l'autre non, l'action X est autorisée (most permissive wins).

```python
# DBA appartenant à [GRP-DBA-SQL, GRP-DBA-ORACLE]
# Profil SQL  : tag_patterns=["sql-server"], environments=["dev", "staging"]
# Profil Oracle : tag_patterns=["oracle"], environments=["prod"]
#
# Résultat CatalogRBACService.get_permissions() :
#   actions_type: "pattern"
#   tag_patterns: ["oracle", "sql-server"]   ← union
#   environments: ["dev", "prod", "staging"] ← union
```

## Diagramme de flux

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   HTTP Request  │────►│  JWT Validation   │────►│  User + AD      │
│ Authorization   │     │  JWTAuthentication│     │  groups loaded  │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         ViewSet                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  1. Permission classes check (DRF)                              │  │
│  │     - IsAuthenticated                                           │  │
│  │     - AdminProfilePermission (admin) OR OptionalUserPermission  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  2. _get_cumulative_permissions_for_user()                      │  │
│  │     - Find profiles by AD groups                                │  │
│  │     - Aggregate permissions (union)                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  3. _filter_by_rbac() ou _check_rbac_for_action()               │  │
│  │     - Filter list OR check single action                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │   Response    │
                        │ (filtered)    │
                        └───────────────┘
```

## Configuration d'un profil (exemple YAML)

```yaml
profiles:
  - name: "DBA-DEV"
    description: "DBAs environnement de développement"
    ad_group: "CN=DBA-DEV,OU=Groups,DC=corp"
    is_admin: false
    is_auditor: false
    action_permissions:
      type: "pattern"
      tag_patterns:
        - "oracle"
        - "sql-server"
      environments:
        - "dev"
    target_permissions:
      type: "pattern"
      target_patterns:
        - "db-dev-*"

  - name: "DBA-PROD"
    description: "DBAs environnement de production"
    ad_group: "CN=DBA-PROD,OU=Groups,DC=corp"
    is_admin: false
    is_auditor: false
    action_permissions:
      type: "all"
      environments:
        - "dev"
        - "staging"
        - "prod"
    target_permissions:
      type: "all"

  - name: "DBOPS"
    description: "Administrateurs DBOPS"
    ad_group: "CN=DBOPS-Admins,OU=Groups,DC=corp"
    is_admin: true
    is_auditor: false
```

## Bonnes pratiques

### 1. Toujours utiliser les permissions cumulées

```python
# ❌ Mauvais: vérifier un seul profil
profile = Profile.objects.get(ad_group=user.ad_groups[0])

# ✅ Bon: utiliser les permissions cumulées
permissions = _get_cumulative_permissions_for_user(user)
```

### 2. Prefetch les tags pour le filtrage RBAC

```python
# ❌ Mauvais: N+1 queries
actions = Action.objects.all()
filtered = _filter_by_rbac(actions, permissions)  # Query par action

# ✅ Bon: prefetch_related
actions = Action.objects.prefetch_related('actiontag_set__tag').all()
filtered = _filter_by_rbac(actions, permissions)  # 0 query supplémentaire
```

### 3. Retourner 404 au lieu de 403 pour le RBAC

```python
# ❌ Mauvais: révèle l'existence de la ressource
if not _check_rbac_for_action(action, permissions):
    raise ForbiddenError("Accès refusé")

# ✅ Bon: masque l'existence de la ressource
if not _check_rbac_for_action(action, permissions):
    raise NotFoundError("Action non trouvée")
```

## Exclusion explicite de cibles (Deny patterns) - Story 25.6

### Principe: "Allow first, then exclude"

Les patterns d'exclusion permettent de retirer explicitement des cibles des permissions accordées par les règles d'inclusion. La sémantique est **"allow first, then exclude"** :

1. Les règles d'inclusion (LIST, PATTERN, ALL) déterminent d'abord les cibles autorisées
2. Les filtres par attributs (`filter_by_attribute`) affinent ensuite ces cibles
3. **Enfin, les patterns d'exclusion retirent les cibles qui matchent**

Une cible qui matche un pattern d'exclusion n'est **jamais** retournée comme autorisée, même si elle matche une règle d'inclusion.

### Ordre d'application des règles RBAC

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. INCLUSION (LIST / PATTERN / ALL)                            │
│    → Ensemble initial de cibles autorisées                     │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. FILTRAGE PAR ATTRIBUTS (filter_by_attribute)                │
│    → Affine selon engine_type, zone, etc.                      │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. EXCLUSION (exclusion_patterns) ← Story 25.6                 │
│    → Retire les cibles qui matchent un pattern d'exclusion     │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                      Résultat final
```

### Exemples d'utilisation

#### Exemple 1 : Tous les serveurs Oracle sauf les critiques

**Configuration profil :**
```json
{
  "permission_type": "ALL",
  "filter_by_attribute": {"engine_type": ["oracle"]},
  "exclusion_patterns": ["PROD-CRITICAL-*"]
}
```

**Résultat :**
- ✅ PROD-APP-DB-01 (Oracle, pas critique)
- ✅ PROD-REPORTING-DB-02 (Oracle, pas critique)
- ❌ PROD-CRITICAL-DB-01 (Oracle, mais matche exclusion)
- ❌ PROD-SQL-01 (SQL Server, pas Oracle)

#### Exemple 2 : Pattern large avec exclusions spécifiques

**Configuration profil :**
```json
{
  "permission_type": "PATTERN",
  "target_patterns": ["PROD-*"],
  "exclusion_patterns": ["PROD-CRITICAL-*", "PROD-DR-*"]
}
```

**Résultat :**
- ✅ PROD-APP-01 (matche PROD-*)
- ✅ PROD-WEB-02 (matche PROD-*)
- ❌ PROD-CRITICAL-DB-01 (matche PROD-* mais exclu)
- ❌ PROD-DR-BACKUP (matche PROD-* mais exclu)

#### Exemple 3 : Liste explicite avec exclusion

**Configuration profil :**
```json
{
  "permission_type": "LIST",
  "target_names": ["SERVER-01", "SERVER-02", "SERVER-03"],
  "exclusion_patterns": ["SERVER-02"]
}
```

**Résultat :**
- ✅ SERVER-01 (dans la liste, pas exclu)
- ❌ SERVER-02 (dans la liste MAIS exclu)
- ✅ SERVER-03 (dans la liste, pas exclu)

### Cumul multi-profils : Union des exclusions

**Code review fix:** Clarification du comportement multi-profils.

Quand un utilisateur a plusieurs profils avec des patterns d'exclusion différents, l'**union** des exclusions s'applique (le plus restrictif gagne).

**Règle générale :**
1. **Inclusions** : Union (l'utilisateur obtient toutes les cibles de tous ses profils)
2. **Exclusions** : Union (toutes les exclusions de tous les profils s'appliquent)
3. Ordre d'application : Inclusions → Exclusions

**Exemple concret:**

Un utilisateur appartient à deux profils:

**Profil 1 (DBA Standard):**
```json
{
  "permission_type": "ALL",
  "exclusion_patterns": ["PROD-CRITICAL-*"]
}
```

**Profil 2 (DBA Backup):**
```json
{
  "permission_type": "ALL",
  "exclusion_patterns": ["*-DR-*"]
}
```

**Exclusions effectives :** `["PROD-CRITICAL-*", "*-DR-*"]` (union des deux profils)

**Résultat pour l'utilisateur :**
- ✅ PROD-APP-01 (inclus par les deux profils, pas exclu)
- ❌ PROD-CRITICAL-DB-01 (inclus mais **exclu par Profil 1**)
- ❌ PROD-DR-BACKUP (inclus mais **exclu par Profil 2**)
- ❌ STAGING-DR-02 (inclus mais **exclu par Profil 2**)

### Cas limites

#### Exclusion sans inclusion

Si un profil a des exclusions mais aucune inclusion (ex. `PATTERN` avec `target_patterns=[]`), aucune cible n'est autorisée. L'exclusion ne crée pas d'accès, elle ne fait que retirer.

**Configuration :**
```json
{
  "permission_type": "PATTERN",
  "target_patterns": [],
  "exclusion_patterns": ["PROD-*"]
}
```

**Résultat :** Aucune cible (pas d'erreur, simplement liste vide)

#### Pattern d'exclusion vide ou invalide

Les patterns vides (`""`) ou invalides (non-string, null) sont ignorés silencieusement avec un log warning. Ils n'affectent pas la résolution RBAC.

#### Limite de performance (max 100 patterns)

**Code review fix:** Pour éviter des problèmes de performance lors du matching RBAC, un maximum de **100 patterns d'exclusion** est imposé par profil.

- **Validation backend** : Refuse les `PUT` avec > 100 patterns (HTTP 400)
- **Validation frontend** : Bloque la saisie à 100 patterns
- **Warning** : Un log warning est émis si un profil a > 50 patterns (approche de la limite)

**Raison technique :** Le matching des patterns utilise `fnmatch` en O(n×m) où n = nombre de cibles, m = nombre de patterns. Avec 10 000 cibles et 1000 patterns, cela représente 10 millions de comparaisons par requête RBAC.

**Recommendation :** Si > 50 patterns sont nécessaires, réévaluer la stratégie RBAC (ex: utiliser `filter_by_attribute` pour réduire d'abord le scope, puis des exclusions ciblées).

### Matching des patterns

- **Syntaxe :** Glob-style (`*`, `?`, `[abc]`) via `fnmatch`
- **Sensibilité casse :** Case-insensitive (`PROD-CRITICAL-*` matche `prod-critical-db-01`)
- **Exemples :**
  - `PROD-*` → Tous les noms commençant par PROD-
  - `*-DR-*` → Tous les noms contenant -DR-
  - `SERVER-[123]` → SERVER-1, SERVER-2, SERVER-3
  - `APP-?-PROD` → APP-A-PROD, APP-1-PROD, etc.

### Implémentation technique

**Modèle Django:**
```python
class ProfileTargetPermission(models.Model):
    exclusion_patterns_json = models.TextField(
        null=True, blank=True, db_column='EXCLUSION_PATTERNS_JSON'
    )
    
    def get_exclusion_patterns(self) -> list[str]:
        """Retourne la liste des patterns d'exclusion (filtrés et validés)."""
    
    def set_exclusion_patterns(self, value: list[str] | None) -> None:
        """Sérialise la liste de patterns en JSON CLOB."""
```

**Service RBAC:** `inventory/services.py` → `InventoryService.list_targets_for_user()` applique les exclusions après le filtrage par attributs.

**API endpoint:** `GET/PUT /api/v1/admin/profiles/{id}/targets`

**Frontend:** Champ `exclusion_patterns` dans `ProfileForm.tsx` (Select mode="tags")

### Comportement API (PUT)

**Code review fix:** Clarification du comportement lors de la mise à jour des exclusions via `PUT /api/v1/admin/profiles/{id}/targets`:

| Payload | Comportement | Use case |
|---------|--------------|----------|
| `exclusion_patterns` **non présent** (clé absente) | **Préserve** les exclusions existantes | Mettre à jour `target_patterns` sans toucher aux exclusions |
| `exclusion_patterns: []` (array vide) | **Efface** toutes les exclusions | Supprimer toutes les exclusions |
| `exclusion_patterns: null` | **Efface** toutes les exclusions (équivalent à `[]`) | Réinitialiser les exclusions |
| `exclusion_patterns: ["PROD-*"]` | **Remplace** par les nouvelles exclusions | Définir de nouvelles exclusions |

**Exemple:** Mettre à jour `target_patterns` sans modifier `exclusion_patterns`
```json
PUT /api/v1/admin/profiles/123/targets
{
  "targets_type": "pattern",
  "target_patterns": ["STAGING-*"],
  "target_names": []
  // exclusion_patterns: omis → préservé
}
```

### Tests

- `profiles/tests/test_exclusion_patterns_model.py` - Tests unitaires helpers
- `inventory/tests/test_rbac_exclusion.py` - Tests d'intégration RBAC
- `profiles/tests/test_api_exclusion_patterns.py` - Tests API
