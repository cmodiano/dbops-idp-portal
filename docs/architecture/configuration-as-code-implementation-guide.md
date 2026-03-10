# Guide d'implémentation CaC — Portail IDP

Ce document détaille les patterns de code, conventions et décisions d'architecture utilisés dans
l'implémentation Configuration-as-Code du portail IDP (Epic 64).

## Table des matières

1. [Format d'envelope YAML](#1-format-denvelope-yaml)
2. [Utilitaires core : `services_iac_utils.py`](#2-utilitaires-core-services_iac_utilspy)
3. [Pattern `_apply_field_changes`](#3-pattern-_apply_field_changes)
4. [Pattern `update_sync_tracking`](#4-pattern-update_sync_tracking)
5. [Pattern two-pass import (integrations)](#5-pattern-two-pass-import-integrations)
6. [Credential masking à l'export](#6-credential-masking-a-lexport)
7. [Pattern FBV pour endpoints CaC](#7-pattern-fbv-pour-endpoints-cac)
8. [Ordre de dépendances et graph](#8-ordre-de-dependances-et-graph)
9. [Conventions de nommage](#9-conventions-de-nommage)
10. [Ajouter une nouvelle entité CaC — checklist](#10-ajouter-une-nouvelle-entite-cac-checklist)

---

## 1. Format d'envelope YAML

Chaque document YAML CaC commence par une **envelope standardisée** qui identifie le type
d'entité et ses métadonnées. La validation est centralisée dans `core/services_iac_utils.py`.

### Structure

```yaml
apiVersion: idp/v1          # Toujours "idp/v1"
kind: <Kind>                 # Voir VALID_KINDS
metadata:
  name: <identifiant>        # Requis pour la plupart des kinds
  # Pour ReferenceData : type: engines | categories
spec:
  # Champs spécifiques à l'entité
```

### Validation avec `parse_yaml` + `validate_envelope`

```python
from core.services_iac_utils import parse_yaml, validate_envelope

# Étape 1 : parser le YAML bytes → dict
parsed = parse_yaml(content)
# Lève InvalidStateError(code="INVALID_YAML_SYNTAX") si malformé

# Étape 2 : valider l'envelope
validate_envelope(parsed, expected_kind="Action")
# Lève InvalidStateError selon le problème :
#   INVALID_API_VERSION — apiVersion absent ou != "idp/v1"
#   INVALID_KIND        — kind absent, null ou non dans VALID_KINDS
#   WRONG_KIND          — kind présent mais != expected_kind
#   INVALID_METADATA    — metadata absent ou non-dict
#   MISSING_NAME        — metadata.name requis mais absent/vide
```

### VALID_KINDS (liste complète)

```python
VALID_KINDS = {
    "ReferenceData",
    "Tags",
    "FeatureFlags",
    "IntegrationTypeCatalogue",
    "Integration",
    "BusinessRulePolicy",
    "Action",
    "WorkflowAction",
    "Profile",
}
```

### Décision : codes d'erreur spécifiques vs. ENVELOPE_MISSING_FIELD générique

Les codes de validation de l'envelope sont intentionnellement spécifiques (`INVALID_API_VERSION`,
`INVALID_KIND`, `INVALID_METADATA`) plutôt que d'utiliser un code générique `ENVELOPE_MISSING_FIELD`.
Cette décision améliore le débogage en indiquant précisément le champ invalide.

---

## 2. Utilitaires core : `services_iac_utils.py`

Toute la logique partagée CaC réside dans `core/services_iac_utils.py`.

| Fonction | Signature | Usage |
|----------|-----------|-------|
| `parse_yaml` | `(content: bytes) → dict` | Parser bytes → dict Python |
| `validate_envelope` | `(doc: dict, expected_kind=None) → None` | Valider structure envelope |
| `compute_yaml_hash` | `(content: bytes) → str` | SHA-256 hex du YAML (64 chars) |
| `serialize_to_yaml` | `(data: dict) → bytes` | Dict → bytes YAML UTF-8 |
| `_apply_field_changes` | `(obj, defaults: dict) → bool` | Mettre à jour champs modifiés |
| `update_sync_tracking` | `(obj, yaml_content: bytes) → None` | Mettre à jour colonnes de tracking |

---

## 3. Pattern `_apply_field_changes`

Pattern central pour détecter et appliquer les modifications d'un objet Django sans appel
`save()` systématique.

### Code source

```python
def _apply_field_changes(obj: object, defaults: dict) -> bool:
    """
    Apply field updates to a model instance where values differ.
    Does NOT call obj.save() — caller is responsible.
    Returns True if at least one field was changed.
    """
    changed = False
    for field, value in defaults.items():
        if getattr(obj, field) != value:
            setattr(obj, field, value)
            changed = True
    return changed
```

### Utilisation typique dans un service import

```python
@transaction.atomic
def import_action_yaml(content: bytes, mode="additive", user=None) -> tuple[int, int, int]:
    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="Action")
    spec = parsed.get("spec", {})
    name = parsed["metadata"]["name"]

    defaults = {
        "engine": spec.get("engine"),
        "status": spec.get("status", "draft"),
        "requires_target": spec.get("requires_target", True),
    }

    obj, created = Action.objects.get_or_create(name=name, defaults={**defaults, "created_by": user})

    if created:
        update_sync_tracking(obj, content)
        return 1, 0, 0

    changed = _apply_field_changes(obj, defaults)
    if changed:
        obj.save()
        update_sync_tracking(obj, content)
        return 0, 1, 0

    return 0, 0, 1  # unchanged
```

### Pourquoi pas `update_or_create` directement ?

`update_or_create()` retourne un tuple `(object, created)` où `created` vaut `True` si un nouvel
objet a été créé, `False` sinon. Il ne permet pas de savoir si un objet existant a été modifié
(seulement s'il a été créé). Ce pattern avec `_apply_field_changes` permet de distinguer
`created`, `unchanged` et `updated-with-field-changes` pour produire des rapports précis.

---

## 4. Pattern `update_sync_tracking`

Chaque entité CaC possède deux colonnes de tracking ajoutées en Story 64.11 :

```sql
last_synced_at   TIMESTAMP WITH TIME ZONE   -- Horodatage du dernier sync
last_synced_hash VARCHAR(64)                 -- SHA-256 du YAML importé
```

### Code source

```python
def update_sync_tracking(obj: object, yaml_content: bytes) -> None:
    obj.last_synced_at = timezone.now()
    obj.last_synced_hash = compute_yaml_hash(yaml_content)
    obj.save(update_fields=["last_synced_at", "last_synced_hash"])
```

### Règles d'appel

- Appeler **uniquement** sur `created=True` ou `changed=True` (jamais sur `unchanged`).
- Utiliser `save(update_fields=...)` pour minimiser les colonnes écrites en DB.
- Le `yaml_content` doit représenter l'entité **telle qu'importée** (bytes bruts du fichier).

### Usage dans `detect_drift`

```text
hash_fichier_git == obj.last_synced_hash → in_sync
hash_fichier_git != obj.last_synced_hash → diverged
obj.last_synced_hash is None             → jamais syncé
```

---

## 5. Pattern two-pass import (integrations)

Les `Integration` peuvent référencer une autre `Integration` comme `secret_service`
(ex: Vault comme gestionnaire de secrets d'AAP). Puisqu'une intégration peut référencer
une autre dans le même batch de fichiers YAML, un import en deux passes est nécessaire.

### Problème

```yaml
# integrations/vault-prod.yaml
name: vault-prod
# ...

# integrations/aap-prod.yaml
name: aap-prod
secret_service_ref: vault-prod   # Référence vault-prod qui peut ne pas encore être en DB
```

### Solution : deux passes dans `import_integration_yaml`

```python
@transaction.atomic
def import_integration_yaml(content: bytes, mode="additive", user=None) -> tuple[int, int, int]:
    created = updated = unchanged = 0
    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="Integration")
    spec = parsed.get("spec", {})
    name = parsed["metadata"]["name"]

    # ---------- Pass 1 : créer/mettre à jour sans secret_service ----------
    defaults = {
        "type": spec["type"],
        "base_url": spec.get("base_url", ""),
        "auth_flow": spec.get("auth_flow", ""),
        # credential_ref exclu si masqué (voir section 6)
    }
    obj, was_created = Integration.objects.get_or_create(name=name, defaults=defaults)
    if was_created:
        created += 1
    else:
        changed = _apply_field_changes(obj, defaults)
        if changed:
            obj.save()
            updated += 1
        else:
            unchanged += 1

    # ---------- Pass 2 : résoudre secret_service_ref ----------
    secret_service_ref = spec.get("secret_service_ref")
    if secret_service_ref:
        try:
            ref_integration = Integration.objects.get(name=secret_service_ref)
        except Integration.DoesNotExist:
            raise InvalidStateError(
                code="REF_NOT_FOUND",
                message=f"Integration référencée '{secret_service_ref}' introuvable.",
            )
        if obj.secret_service_id != ref_integration.id:
            obj.secret_service_id = ref_integration.id
            obj.save(update_fields=["secret_service_id"])
            update_sync_tracking(obj, content)  # Toujours si FK modifiée
            if unchanged:
                unchanged -= 1
                updated += 1
    elif obj.secret_service_id is not None and not was_created:
        # Effacer la référence si absente du YAML
        obj.secret_service_id = None
        obj.save(update_fields=["secret_service_id"])
        update_sync_tracking(obj, content)  # Toujours si FK modifiée
        if unchanged:
            unchanged -= 1
            updated += 1

    return (created, updated, unchanged)
```

### Quand utiliser ce pattern

Ce pattern est nécessaire pour toute entité avec une **auto-référence FK** ou une FK vers
une entité du même type importée dans la même séquence.

---

## 6. Credential masking à l'export

Les `Integration` peuvent stocker un chemin Vault dans `credential_ref`
(ex: `secret/integrations/aap-prod`). Ce chemin **ne doit jamais apparaître en clair dans Git**.

### Règle de masquage

À l'export, le **dernier segment du chemin** est remplacé par `***` :

```text
secret/integrations/aap-prod  →  secret/integrations/***
simple-secret                  →  ***
None / ""                      →  None
```

### Implémentation

```python
def _mask_credential_ref(credential_ref: str | None) -> str | None:
    """Mask the last path segment of a Vault credential ref for safe export to Git."""
    if not credential_ref:
        return None
    parts = credential_ref.rsplit("/", 1)
    if len(parts) == 1:
        return "***"
    return f"{parts[0]}/***"
```

### Comportement à l'import

À l'import, si `credential_ref` est masqué (`endswith("***")`), la valeur en DB n'est
**pas écrasée**. Le service détecte le masque et préserve le `credential_ref` réel en DB.
Cela permet des round-trips export → import sans perte du secret réel.

---

## 7. Pattern FBV pour endpoints CaC

Tous les endpoints CaC suivent le pattern **Function-Based Views (FBV)** canonique du
projet (établi en Story 63.1).

### Structure type

```python
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from django.http import HttpResponse

from core.exceptions import InvalidStateError
from core.parsers import YAMLParser, extract_yaml_content
from core.permissions import AdminProfilePermission


@api_view(['GET'])
@permission_classes([AdminProfilePermission])
def export_<entity>(request: Request) -> HttpResponse:
    """GET /api/v1/admin/<entity>/export/yaml/ — Export YAML."""
    content = export_<entity>_yaml()
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="<entity>.yaml"'
    return response


@api_view(['POST'])
@permission_classes([AdminProfilePermission])
@parser_classes([YAMLParser, MultiPartParser])
def sync_<entity>(request: Request) -> Response:
    """POST /api/v1/admin/<entity>/sync/ — Import depuis YAML."""
    mode = request.query_params.get('mode', 'additive')
    if mode not in ('additive', 'full'):
        return Response(
            {"error": {"code": "INVALID_IMPORT_MODE", "message": "Mode invalide."}},
            status=400,
        )
    content_bytes = extract_yaml_content(request)
    if content_bytes is None:
        return Response({"error": {"code": "EMPTY_BODY", "message": "Aucun YAML fourni."}}, status=400)
    try:
        created, updated, unchanged = import_<entity>_yaml(content_bytes, user=request.user, mode=mode)
    except InvalidStateError as e:
        return Response(
            {"error": {"code": e.code, "message": e.message, "details": getattr(e, 'details', {})}},
            status=400,
        )
    status_code = 201 if created > 0 and updated == 0 else 200
    return Response(
        {"data": {"created": created, "updated": updated, "unchanged": unchanged, "mode": mode}},
        status=status_code,
    )
```

### Règles FBV CaC

| Règle | Détail |
|-------|--------|
| `@permission_classes([AdminProfilePermission])` | Obligatoire sur tous les endpoints CaC |
| `@parser_classes([YAMLParser, MultiPartParser])` | Pour les endpoints POST (sync) |
| Retour export | `HttpResponse` avec `content_type='application/x-yaml'` |
| Retour sync | `Response({"data": ...})` (201 si création pure, 200 sinon) |
| Gestion erreurs | `except InvalidStateError` → `Response({"error": ...}, status=400)` |

---

## 8. Ordre de dépendances et graph

### Graph de dépendances FK

```text
RefEngine (code)         ← aucune dépendance
RefCategory (code)       ← aucune dépendance
Tag (name)               ← aucune dépendance
FeatureFlag (key)        ← aucune dépendance

IntegrationTypeCatalogue (code)  ← aucune dépendance

Integration (name)       ← IntegrationTypeCatalogue (type)
                           Integration (secret_service — self-ref, two-pass)

BusinessRulePolicy (name) ← aucune dépendance FK

Action (name)             ← Integration (integration_ref)
                            BusinessRulePolicy (business_rule_policy_ref)
                            Action (mutex.incompatible_with — self-ref)

Profile (name)            ← Action (action_names dans permissions)
```

### Ordre imposé par les endpoints d'import

Les endpoints API d'import (`POST .../sync/`) doivent être appelés dans cet ordre par le script
`apply_idp_config.py` pour respecter le graphe de dépendances :

```
1. reference/engines.yaml      (aucune dépendance)
2. reference/categories.yaml   (aucune dépendance)
3. tags.yaml                   (aucune dépendance)
4. feature-flags.yaml          (aucune dépendance)
5. integration-types/          (aucune dépendance)
6. integrations/               (→ integration-types)
7. policies/                   (aucune dépendance FK)
8. actions/                    (→ integrations, policies)
9. profiles/                   (→ actions)
```

---

## 9. Conventions de nommage

### Fichiers YAML

| Type | Convention | Exemple |
|------|------------|---------|
| Entités à fichier unique | Nom fixe | `tags.yaml`, `feature-flags.yaml` |
| Entités à fichier par instance | `<identifiant-slug>.yaml` | `deploy-oracle.yaml`, `aap-prod.yaml` |
| `metadata.name` | Identique au nom du fichier (sans `.yaml`) | `name: deploy-oracle` |

### Kinds et metadata

```yaml
# Entités nommées (action, integration, profile, policy, integration-type)
metadata:
  name: deploy-oracle          # slug unique, stable, pas d'espaces

# ReferenceData
metadata:
  type: engines                # ou "categories"

# Tags, FeatureFlags
metadata: {}                   # vide, pas de name requis
```

### Services Python

| Fichier | Pattern |
|---------|---------|
| `services_export_import.py` | Service principal (1 par entité Django app) |
| `services_export_import_<suffix>.py` | Services secondaires (tags, policies dans catalog) |
| `services_iac_utils.py` | Utilitaires partagés (core uniquement) |

### Tests

| Fichier | Pattern |
|---------|---------|
| `test_services_export_import.py` | Tests du service principal |
| `test_services_export_import_<suffix>.py` | Tests services secondaires |
| `test_iac_views.py` | Tests des endpoints HTTP CaC |
| `test_detect_drift_command.py` | Tests de la commande detect_drift |

---

## 10. Ajouter une nouvelle entité CaC — checklist

Pour ajouter le support CaC d'une nouvelle entité Django :

### Phase 1 : Modèle DB

- [ ] Ajouter colonnes `last_synced_at` et `last_synced_hash` au modèle (Story 64.11 pattern)
- [ ] Créer la migration Flyway correspondante

### Phase 2 : Service export/import

- [ ] Créer `<app>/services_export_import_<entity>.py` (ou ajouter dans le fichier existant)
- [ ] Implémenter `export_<entity>_yaml(name: str) -> bytes`
  - Envelope : `apiVersion: idp/v1 / kind: <Kind> / metadata.name: ...`
  - Masquer les secrets si applicable (pattern `_mask_credential_ref`)
- [ ] Implémenter `import_<entity>_yaml(content: bytes, mode="additive", user=None) -> tuple[int, int, int]`
  - `@transaction.atomic`
  - `parse_yaml(content)` + `validate_envelope(parsed, expected_kind="<Kind>")`
  - `_apply_field_changes(obj, defaults)` pour détection des changements
  - `update_sync_tracking(obj, content)` sur created + updated (pas unchanged)
  - Gestion du mode `additive` vs `full`
  - Levée de `REF_NOT_FOUND` pour toute FK non résolue
  - Appel `AuditService.create_entry(...)` en fin de transaction

### Phase 3 : Ajouter au VALID_KINDS

- [ ] Ajouter le nouveau kind dans `VALID_KINDS` dans `core/services_iac_utils.py`

### Phase 4 : Intégration dans le processus d'import API

- [ ] Ajouter le nouveau type d'entité dans `apply_idp_config.py` en respectant l'ordre de dépendances
  - Vérifier que l'appel à l'endpoint `POST .../sync/` est positionné après les dépendances FK

### Phase 5 : Endpoints HTTP CaC

- [ ] Créer `<app>/iac_views.py` (ou ajouter dans l'existant)
  - `export_<entity>` (GET) avec `@permission_classes([AdminProfilePermission])`
  - `sync_<entity>` (POST) avec `@parser_classes([YAMLParser, MultiPartParser])`
- [ ] Déclarer les routes dans `<app>/urls.py`
- [ ] Brancher dans le routeur principal

### Phase 6 : Support `detect_drift`

- [ ] Ajouter la configuration de l'entité dans `core/management/commands/detect_drift.py`
  - Mapping `ref_type → (Model, file_path_pattern, lookup_field)`

### Phase 7 : Tests

- [ ] `test_services_export_import.py` : export (envelope, champs, masquage), import (create/update/unchanged, refs invalides, mode full, round-trip, INVALID_YAML_SYNTAX)
- [ ] `test_iac_views.py` : endpoints export et sync (auth, format, erreurs)
- [ ] `test_detect_drift_command.py` : statuts in_sync, diverged, missing

### Phase 8 : Documentation

- [ ] Ajouter l'entité dans le tableau des entités gérées de `configuration-as-code-strategy.md`
- [ ] Ajouter le fichier YAML dans la structure de `idp-config/README.md`
- [ ] Créer un exemple de fichier YAML dans `idp-config/<entity>/` (ou mettre à jour les fichiers existants)

---

## Références croisées

- **Services** : `core/services_iac_utils.py`, `<app>/services_export_import*.py`
- **Commandes** : `core/management/commands/detect_drift.py`
- **Vues** : `core/iac_views.py`, `catalog/iac_views.py`, `integrations/iac_views.py`, etc.
- **Tests** : voir pattern de nommage en section 9
- **Stratégie** : [`configuration-as-code-strategy.md`](configuration-as-code-strategy.md)
- **Configuration** : [`idp-config/README.md`](../../idp-portal/idp-config/README.md)
