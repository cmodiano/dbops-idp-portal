# Patterns de Sécurité Critiques — Django IDP Portal

> **Objectif :** Prévenir les failles récurrentes identifiées lors des code reviews Epic M (10 stories, ~70 issues corrigées).
> **Source :** Rétrospective Epic M — 2/10 stories CRITICAL, 3/10 HIGH (sécurité), 4/10 MEDIUM (types hardcodés).

## 1. Injection SQL — Utiliser Django ORM

**Problème :** Requêtes SQL brutes avec interpolation de chaînes.

```python
# MAUVAIS — injection SQL possible
cursor.execute(f"SELECT * FROM actions WHERE name = '{user_input}'")

# BON — ORM Django
Action.objects.filter(name=user_input)

# BON — Si SQL brut indispensable (Oracle-specific), utiliser des bind variables
cursor.execute("SELECT * FROM actions WHERE name = :name", {"name": user_input})
```

**Règle :** Toujours utiliser l'ORM Django. SQL brut uniquement pour queries Oracle-specific (JSON_VALUE, etc.) avec bind variables nommés (`:param`). Voir [ADR-001](../decisions/adr-001-django-orm-vs-sql-brut.md).

## 2. Enums Hardcodés — Utiliser les Enums Django

**Problème :** Types d'audit et status en strings libres → incohérence, erreurs silencieuses.

```python
# MAUVAIS — string libre, pas de validation
audit_service.log("ACTION_CREATED", ...)

# BON — enum validé à la compilation
from core.enums import AuditActionType
audit_service.log(AuditActionType.ACTION_CREATED, ...)
```

**Impact Epic M :** 4/10 stories avaient des types audit hardcodés. Corrigé en remplaçant par `AuditActionType`, `IntegrationType`, `ActionStatus` enums.

## 3. Validation des Paramètres — Serializers DRF

**Problème :** Paramètres utilisateur non validés → comportement imprévisible.

```python
# MAUVAIS — pas de validation
def create(self, request):
    action_id = request.data.get("action_id")
    Action.objects.get(id=action_id)  # Crash si action_id est None ou string

# BON — validation via serializer
class ExecuteActionSerializer(serializers.Serializer):
    action_id = serializers.IntegerField(min_value=1)
    environment = serializers.ChoiceField(choices=["dev", "staging", "prod"])
```

**Règle :** Valider dans le serializer. `ChoiceField` pour les enums, `IntegerField(min_value=1)` pour les IDs, `CharField(max_length=...)` pour les strings.

## 4. N+1 Queries — select_related / prefetch_related

**Problème :** Boucles avec accès lazy aux relations → explosion du nombre de requêtes.

```python
# MAUVAIS — 1 + N requêtes (N = nombre d'actions)
actions = Action.objects.all()
for action in actions:
    print(action.created_by.username)  # Requête SQL à chaque itération

# BON — 2 requêtes total (JOIN)
actions = Action.objects.select_related("created_by").all()
```

**Quand utiliser :**
- `select_related()` : ForeignKey, OneToOneField (JOIN SQL)
- `prefetch_related()` : ManyToManyField, reverse ForeignKey (requête séparée)

**Impact Epic M :** 3/10 stories corrigées pour N+1 queries.

## 5. RBAC — Permissions DRF

**Problème :** Oublier la permission RBAC → endpoint accessible à tous les utilisateurs authentifiés.

```python
# MAUVAIS — seulement authentification, pas RBAC
class AdminActionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

# BON — RBAC appliqué
class AdminActionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]
```

**Vérifications :**
- Endpoints admin → `DBOPSProfilePermission`
- Endpoints utilisateur → `IsAuthenticated` + filtrage par permissions cumulées
- Invalider cache RBAC après modification profils/permissions

## 6. Secrets & Logs — Redaction

**Problème :** Credentials, tokens, ou données sensibles dans les logs.

```python
# MAUVAIS — token dans les logs
logger.info("User authenticated", token=user_token)

# BON — redaction
logger.info("User authenticated", user_id=user.id)
```

**Règle :** Ne jamais logger : tokens JWT, mots de passe, clés API, SAML assertions, données personnelles. Utiliser `structlog` avec les processors de redaction configurés.

## 7. Invalidation Cache RBAC

**Problème :** Modification des permissions sans invalider le cache → utilisateur conserve anciennes permissions.

```python
# APRÈS modification des permissions d'un profil
from profiles.services import invalidate_permissions_cache
invalidate_permissions_cache()
```

**Quand invalider :**
- Création/modification/suppression de profil
- Modification des permissions actions/targets d'un profil
- Import YAML de profils
- Attribution/retrait de profil à un utilisateur

## 8. Upload de Fichiers — Validation Stricte

**Problème :** Fichiers uploadés sans validation → XSS via SVG, EXIF injection.

**Vérifications obligatoires :**
- MIME type validé (pas seulement l'extension)
- Taille maximale appliquée
- SVG : sanitization des balises `<script>`, `onload`, `onerror`
- Images : strip EXIF metadata
- Pas d'exécution de fichiers uploadés

---

**Références :**
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security Checklist](https://docs.djangoproject.com/en/stable/topics/security/)
- [Pre-PR Security Checklist](pre-pr-checklist.md)
- [Conventions de logging](../logging-conventions.md)
