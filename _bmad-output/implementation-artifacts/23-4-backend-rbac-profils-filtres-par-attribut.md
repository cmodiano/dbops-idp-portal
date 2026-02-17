# Story 23.4: Backend — RBAC profils filtres par attribut

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'administrateur DBOPS,
je veux pouvoir filtrer les permissions d'un profil par attribut d'inventaire (ex. engine_type),
afin de créer des profils "Tous les serveurs Oracle" ou "Tous les serveurs SQL" sans lister manuellement chaque serveur.

## Acceptance Criteria

**Given** le modèle ProfileTargetPermission existant (type LIST/PATTERN/ALL)
**When** un administrateur crée ou édite un profil
**Then** il peut spécifier des filtres par attribut d'inventaire pour un accès évolutif et maintenable

**AC1 : Ajouter champ filter_by_attribute au modèle ProfileTargetPermission**

**Given** le modèle Django ProfileTargetPermission (profiles/models.py)
**When** on ajoute le support des filtres par attribut
**Then** :
- Ajouter colonne `FILTER_BY_ATTRIBUTE_JSON` (CLOB/TextField) à la table `PROFILE_TARGET_PERMISSIONS`
- Créer migration Django (V055) avec `ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD FILTER_BY_ATTRIBUTE_JSON CLOB`
- Ajouter field `filter_by_attribute_json` au modèle ProfileTargetPermission
- Ajouter méthodes helper `get_filter_by_attribute()` et `set_filter_by_attribute(value)` (pattern existant)
- Format JSON attendu : `{"engine_type": ["oracle", "sqlserver"], "zone": ["prod"], ...}`
- Le champ est optionnel (null/blank=True)
**And** documenter que les clés du filtre correspondent aux **concepts métier** de l'InventoryMapper (pas aux noms de colonnes Oracle)
**And** valider en migration que la colonne supporte JSON valide (contrainte Oracle CHECK IS JSON ou validation applicative)

**AC2 : Appliquer filtres par attribut dans list_targets_for_user**

**Given** InventoryService.list_targets_for_user(user, environment) (inventory/services.py)
**When** un profil de l'utilisateur a des filtres par attribut définis
**Then** :
- Après avoir récupéré les serveurs selon permission_type (LIST/PATTERN/ALL), appliquer le filtre attribut
- Appeler `ProfileTargetPermission.get_filter_by_attribute()` pour chaque profil
- Si filtre présent, filtrer les serveurs retournés par `list_servers()` selon les attributs mappés
- Exemple : si `{"engine_type": ["oracle"]}`, ne garder que les serveurs où `engine_type in ["oracle"]`
- Les filtres sont cumulatifs au sein d'un profil (AND) : `{"engine_type": ["oracle"], "zone": ["prod"]}` = Oracle ET prod
- Les filtres entre profils sont additifs (OR) : profil A (Oracle) + profil B (SQL) = Oracle OU SQL
**And** si un attribut du filtre n'existe pas dans les données serveur retournées, ignorer ce filtre (log WARNING)
**And** logger l'application du filtre avec structlog : event `rbac_filter_by_attribute_applied`, filter, nb_servers_before, nb_servers_after, correlation_id

**AC3 : Validation des filtres à la sauvegarde d'un profil**

**Given** API PUT/POST /api/v1/profiles/{id}/permissions/targets (profiles/views.py)
**When** un administrateur sauvegarde un profil avec filter_by_attribute
**Then** :
- Valider que le JSON est valide et non vide si fourni
- Valider que les clés du filtre sont des **concepts métier reconnus** par InventoryMapper.get_available_concepts()
- Exemple clés valides : `engine_type`, `zone`, `region`, `name`, `environment` (selon config mapping)
- Si clé invalide, retourner `400 Bad Request` avec message explicite : `"Invalid filter attribute: {key}. Valid attributes: {valid_list}"`
- Valider que les valeurs sont des listes non vides de strings
- Si validation échoue, retourner erreur détaillée et ne PAS sauvegarder
**And** logger la validation : event `profile_filter_by_attribute_validated`, profile_id, filter, validation_result, correlation_id

**AC4 : Exposer filter_by_attribute dans l'API profils**

**Given** les endpoints API /api/v1/profiles (profiles/views.py, profiles/serializers.py)
**When** un client appelle GET /api/v1/profiles/{id} ou GET /api/v1/profiles/
**Then** :
- Le serializer ProfileTargetPermissionSerializer inclut le champ `filter_by_attribute` (lecture/écriture)
- Format retourné : `{"engine_type": ["oracle"], ...}` (dict, pas string JSON)
- Le champ est optionnel dans les réponses (null si non défini)
- Le serializer ProfileDetailSerializer inclut `target_permissions.filter_by_attribute`
**And** la documentation OpenAPI (drf-spectacular) documente ce champ avec exemple :
  - Type : `object` (dict de string → array de strings)
  - Exemple : `{"engine_type": ["oracle", "sqlserver"]}`
  - Description : "Filter targets by inventory attributes (concept keys from mapping config)"

**AC5 : Helper pour récupérer les concepts disponibles**

**Given** InventoryMapper avec config de mapping (inventory/mapper.py)
**When** on a besoin de valider ou documenter les attributs filtrables
**Then** :
- Créer méthode statique `InventoryMapper.get_available_concepts(entity_name='servers')`
- Retourne liste des clés concept métier pour l'entité (ex. `['name', 'environment', 'engine_type', ...]`)
- Lit la config `entities[entity_name].columns` et retourne les clés du mapping
- Si config multi-tables absente, retourne concepts fallback : `['name', 'environment', 'type']`
- Utilisé par la validation AC3 pour lister les attributs valides
**And** documenter dans docstring que ces concepts sont **stables** (indépendants des colonnes Oracle réelles)

**AC6 : Gestion d'erreurs et edge cases**

**Given** l'application des filtres par attribut dans list_targets_for_user
**When** des cas limites surviennent
**Then** :
- Si `filter_by_attribute_json` est `null` ou `"{}"`, ignorer le filtre (comportement standard LIST/PATTERN/ALL)
- Si JSON est malformé, logger ERROR et ignorer le filtre pour ce profil (ne PAS bloquer l'authentification)
- Si attribut filtré absent des données serveur (ex. `engine_type` non fourni par inventaire), logger WARNING et ignorer ce critère
- Si tous les serveurs sont filtrés (résultat vide après filtre), retourner liste vide (pas d'erreur)
- Si combinaison LIST + filter_by_attribute : appliquer d'abord LIST, puis filtre attribut (affiner la liste)
- Si combinaison ALL + filter_by_attribute : récupérer tous serveurs, puis filtre attribut (restriction globale)
**And** tous les cas d'erreur sont loggés avec WARNING ou ERROR selon gravité, avec correlation_id

**AC7 : Documentation et exemples**

**Given** la nouvelle fonctionnalité de filtres par attribut
**When** un développeur ou administrateur consulte la documentation
**Then** :
- Créer fichier `docs/rbac-filter-by-attribute.md` documentant :
  - Concept : filtres basés sur attributs inventaire mappés
  - Exemples profils : "Tous Oracle" = `{"engine_type": ["oracle"]}`, "Tous SQL prod" = `{"engine_type": ["sqlserver"], "zone": ["prod"]}`
  - Comportement cumulatif (AND) et additif entre profils (OR)
  - Validation des clés (concepts métier)
  - Ordre d'application : permission_type → filter_by_attribute
  - Edge cases : attribut absent, JSON malformé, liste vide
- Ajouter exemples JSON dans docstrings ProfileTargetPermission
- Documenter dans migration V055 le format attendu en commentaire SQL

**AC8 : Tests unitaires et d'intégration**

**Given** la nouvelle fonctionnalité de filtres par attribut
**When** les tests sont exécutés
**Then** ils couvrent :
- **Model tests** : get_filter_by_attribute / set_filter_by_attribute (serialization JSON)
- **Validation tests** : clés valides/invalides, valeurs vides, JSON malformé
- **InventoryMapper tests** : get_available_concepts retourne concepts corrects (multi-tables + fallback)
- **list_targets_for_user tests** :
  - Profil avec `{"engine_type": ["oracle"]}` → filtre serveurs Oracle
  - Profil avec `{"engine_type": ["oracle"], "zone": ["prod"]}` → filtre Oracle ET prod
  - Deux profils (Oracle, SQL) → cumul serveurs Oracle + SQL
  - Attribut absent des données → filtre ignoré, WARNING loggé
  - JSON malformé → filtre ignoré, ERROR loggé
  - Combinaison LIST + filter → affine la liste
  - Combinaison ALL + filter → restriction globale
- **API tests** :
  - POST profil avec filter_by_attribute valide → 201 Created
  - POST avec clé invalide → 400 Bad Request avec message explicite
  - GET profil → filter_by_attribute retourné correctement
  - PUT profil → mise à jour filter_by_attribute fonctionne
- **Integration tests** : flow complet création profil → list_targets_for_user → serveurs filtrés
- Couverture ≥ 85% pour profiles/models.py (méthodes filter), inventory/services.py (application filtre)

## Tasks / Subtasks

- [x] Task 1 : Migration et modèle ProfileTargetPermission (AC1)
  - [x] 1.1 : Créer migration Django 0002_add_filter_by_attribute.py
  - [x] 1.2 : SQL : `ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD FILTER_BY_ATTRIBUTE_JSON CLOB`
  - [x] 1.3 : Validation applicative (JSON deserialization + catch malformed)
  - [x] 1.4 : Ajouter field `filter_by_attribute_json = models.TextField(null=True, blank=True, db_column='FILTER_BY_ATTRIBUTE_JSON')` au modèle
  - [x] 1.5 : Ajouter méthode `get_filter_by_attribute()` → dict | None
  - [x] 1.6 : Ajouter méthode `set_filter_by_attribute(value: dict | None)`
  - [x] 1.7 : Documenter format JSON dans docstring modèle avec exemple
  - [x] 1.8 : Migration testée via test suite
  - [x] 1.9 : Tests unitaires : 11 tests serialization/deserialization JSON, edge cases

- [x] Task 2 : Helper InventoryMapper.get_available_concepts (AC5)
  - [x] 2.1 : Créer méthode statique `get_available_concepts(entity_name='servers') -> list[str]`
  - [x] 2.2 : Lire config `entities[entity_name].columns` et retourner `list(columns.keys())`
  - [x] 2.3 : Fallback : `['name', 'environment', 'type']`
  - [x] 2.4 : Docstring documentant stabilité des concepts
  - [x] 2.5 : 6 tests unitaires (multi-tables, fallback, unknown entity, instances)

- [x] Task 3 : Validation filter_by_attribute dans serializer (AC3)
  - [x] 3.1 : Modifier ProfileTargetPermissionsSerializer (profiles/serializers.py)
  - [x] 3.2 : Ajouter field `filter_by_attribute = DictField(child=ListField(...))`
  - [x] 3.3 : Ajouter méthode `validate_filter_by_attribute(self, value)`
  - [x] 3.4 : Validation clés contre `InventoryMapper.get_available_concepts('servers')`
  - [x] 3.5 : Validation valeurs = listes non vides de strings
  - [x] 3.6 : ValidationError avec message explicite listant clés valides
  - [x] 3.7 : Logger `profile_filter_by_attribute_validated` avec correlation_id
  - [x] 3.8 : 8 tests serializer validation

- [x] Task 4 : Appliquer filtres dans list_targets_for_user (AC2)
  - [x] 4.1 : Modifier InventoryService.list_targets_for_user
  - [x] 4.2 : Collecter attribute_filters par profil, appliquer après target restrictions
  - [x] 4.3 : Créer `_apply_attribute_filter()` helper (module-level)
  - [x] 4.4 : Filtrage case-insensitive par attribut
  - [x] 4.5 : Cumulatif au sein d'un profil (AND)
  - [x] 4.6 : WARNING `rbac_filter_attribute_not_found` si attribut absent
  - [x] 4.7 : INFO `rbac_filter_by_attribute_applied` avec nb_before/after
  - [x] 4.8 : Dégradation gracieuse : erreur → log ERROR, skip filtre
  - [x] 4.9 : OR entre profils via `_apply_attribute_filters_across_profiles()`

- [x] Task 5 : Exposer filter_by_attribute dans API (AC4)
  - [x] 5.1 : ProfileTargetPermissionsSerializer inclut `filter_by_attribute`
  - [x] 5.2 : to_representation retourne filter_by_attribute (dict ou None)
  - [x] 5.3 : set_target_permissions gère filter_by_attribute dans services.py

- [x] Task 6 : Gestion edge cases et erreurs (AC6)
  - [x] 6.1 : null → pas de filtrage (test_none_filter_returns_all, test_profile_without_filter_passes_all)
  - [x] 6.2 : {} → pas de filtrage (test_empty_filter_returns_all)
  - [x] 6.3 : JSON malformé → log, skip (test_malformed_json_filter_ignored)
  - [x] 6.4 : Attribut absent → WARNING, ignore (test_attribute_not_found_in_servers_ignored)
  - [x] 6.5 : Résultat vide → [] (test_all_servers_filtered_out, test_empty_result_after_filter)
  - [x] 6.6 : LIST + filter → affine (test_list_plus_filter_refines_list)
  - [x] 6.7 : ALL + filter → restriction (test_all_plus_filter_restricts_global)
  - [x] 6.8 : Dégradation gracieuse (try/except dans list_targets_for_user + get_filter_by_attribute)

- [x] Task 7 : Tests unitaires modèle et mapper (AC8)
  - [x] 7.1 : profiles/tests/test_filter_by_attribute.py (11 tests)
  - [x] 7.2 : get/set_filter_by_attribute roundtrip
  - [x] 7.3 : Serialization idempotence (set → save → get)
  - [x] 7.4 : Edge cases : null, empty string, empty dict, malformed JSON, complex filter
  - [x] 7.5 : inventory/tests/test_mapper_concepts.py (6 tests)
  - [x] 7.6 : Multi-table config → concepts corrects
  - [x] 7.7 : Fallback → concepts par défaut

- [x] Task 8 : Tests unitaires list_targets_for_user (AC8)
  - [x] 8.1 : inventory/tests/test_rbac_filter_by_attribute.py (18 tests)
  - [x] 8.2 : Oracle filter → Oracle only
  - [x] 8.3 : AND within profile (engine_type + environment)
  - [x] 8.4 : Two profiles → OR union
  - [x] 8.5 : Attribute absent → ignored
  - [x] 8.6 : Malformed JSON → ignored
  - [x] 8.7 : LIST + filter → refined
  - [x] 8.8 : ALL + filter → restricted
  - [x] 8.9 : Logging events verified via test scenarios

- [x] Task 9 : Tests API profils (AC8)
  - [x] 9.1 : profiles/tests/test_api_filter_by_attribute.py (14 tests)
  - [x] 9.2 : Valid filter → serializer valid
  - [x] 9.3 : Invalid key → ValidationError with explicit message
  - [x] 9.4 : Empty values → ValidationError
  - [x] 9.5 : to_representation → dict (not JSON string)
  - [x] 9.6 : set_target_permissions → filter saved
  - [x] 9.7 : null filter → clears filter

- [x] Task 10 : Tests d'intégration (AC8)
  - [x] 10.1 : profiles/tests/test_integration_filter_by_attribute.py (4 tests)
  - [x] 10.2 : Full flow: create profile → list_targets_for_user → filtered servers
  - [x] 10.3 : Multi-profile Oracle + SQL → union
  - [x] 10.4 : Restrictive filter → empty result

- [x] Task 11 : Documentation (AC7)
  - [x] 11.1 : docs/rbac-filter-by-attribute.md créé
  - [x] 11.2 : Concept documenté
  - [x] 11.3 : Exemples profils documentés
  - [x] 11.4 : Comportement AND/OR documenté
  - [x] 11.5 : Validation clés documentée
  - [x] 11.6 : Ordre application documenté
  - [x] 11.7 : Edge cases documentés (tableau)
  - [x] 11.9 : Docstrings enrichies dans modèle et mapper
  - [x] 11.10 : Migration commentée avec SQL Oracle équivalent

## Dev Notes

### Contexte architectural

**Référence** : docs/inventaire-multi-tables-ux-cibles.md, Stories 23.1-23.3 (done), profiles/models.py, inventory/services.py

**Modèle RBAC actuel (Epic 2, Stories 2.9-2.14)** :
- Profils (PROFILES table) : mapping AD group → permissions
- ProfileActionPermission (V011) : type LIST/PATTERN/ALL, action_ids/tag_patterns/environments en JSON
- ProfileTargetPermission (V012) : type LIST/PATTERN/ALL, target_names/target_patterns en JSON
- InventoryService.list_targets_for_user(user, environment) : applique RBAC selon permission_type

**Nouvelle architecture (Story 23.4)** :
- Ajouter colonne FILTER_BY_ATTRIBUTE_JSON (CLOB) à PROFILE_TARGET_PERMISSIONS
- Format : `{"engine_type": ["oracle", "sqlserver"], "zone": ["prod"], ...}`
- Clés = **concepts métier** de l'InventoryMapper (pas colonnes Oracle réelles)
- Application dans list_targets_for_user : après LIST/PATTERN/ALL, appliquer filtre attribut
- Validation API : clés doivent être dans InventoryMapper.get_available_concepts()

**Principes RBAC intimement lié à l'inventaire (docs/inventaire-multi-tables-ux-cibles.md §5)** :
- Les filtres s'appuient uniquement sur les données et attributs mappés retournés par l'inventaire
- Les règles RBAC sont évaluées sur les concepts métier (stables), pas sur les colonnes Oracle (évolutives)
- Nouvelle colonne inventaire → mise à jour config mapping → nouveau concept filtrable (pas de refonte code)

**Technologies** :
- Django 5.2 + ORM (models.TextField pour CLOB)
- Oracle Database (python-oracledb 3.4.1)
- JSON helpers : json.loads / json.dumps (pattern existant dans ProfileActionPermission)
- structlog pour logging
- drf-spectacular pour OpenAPI

### Fichiers à modifier/créer

**Modifier** :
- `profiles/models.py` : Ajouter filter_by_attribute_json field + helpers get/set
- `profiles/serializers.py` : Ajouter filter_by_attribute field + validation
- `inventory/services.py` : Ajouter _apply_attribute_filter, intégrer dans list_targets_for_user
- `inventory/mapper.py` : Ajouter get_available_concepts()

**Créer** :
- `profiles/migrations/V055_add_filter_by_attribute.py` : Migration Django
- `docs/rbac-filter-by-attribute.md` : Documentation complète
- `profiles/tests/test_filter_by_attribute.py` : Tests unitaires modèle
- `inventory/tests/test_mapper_concepts.py` : Tests get_available_concepts
- `inventory/tests/test_rbac_filter_by_attribute.py` : Tests list_targets_for_user avec filtres
- `profiles/tests/test_api_filter_by_attribute.py` : Tests API
- `profiles/tests/test_integration_filter_by_attribute.py` : Tests intégration

### Patterns de code

**Helper JSON dans modèle (pattern existant)** :
```python
# profiles/models.py
class ProfileTargetPermission(models.Model):
    # ... existing fields ...
    filter_by_attribute_json = models.TextField(
        null=True,
        blank=True,
        db_column='FILTER_BY_ATTRIBUTE_JSON',
        help_text='JSON dict filtering targets by inventory attributes. Format: {"engine_type": ["oracle"], ...}'
    )

    def get_filter_by_attribute(self) -> dict[str, list[str]] | None:
        """
        Deserialize filter_by_attribute from JSON CLOB.

        Returns:
            Dict mapping attribute concept keys to list of values, or None if not set.
            Example: {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}

        Story 23.4 - RBAC filter by inventory attributes.
        """
        if self.filter_by_attribute_json:
            try:
                return json.loads(self.filter_by_attribute_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"Failed to deserialize filter_by_attribute for Profile {self.profile_id}: {e}"
                )
                return None
        return None

    def set_filter_by_attribute(self, value: dict[str, list[str]] | None) -> None:
        """
        Serialize filter_by_attribute to JSON CLOB.

        Args:
            value: Dict mapping attribute keys to list of values, or None to clear.

        Story 23.4 - RBAC filter by inventory attributes.
        """
        if value is not None:
            self.filter_by_attribute_json = json.dumps(value)
        else:
            self.filter_by_attribute_json = None
```

**Validation dans serializer** :
```python
# profiles/serializers.py
from inventory.mapper import InventoryMapper

class ProfileTargetPermissionSerializer(serializers.Serializer):
    # ... existing fields ...
    filter_by_attribute = serializers.DictField(
        child=serializers.ListField(
            child=serializers.CharField(),
            allow_empty=False,
            help_text="List of values for this attribute"
        ),
        required=False,
        allow_null=True,
        help_text="Filter targets by inventory attributes. Keys must be valid concept names from inventory mapping."
    )

    def validate_filter_by_attribute(self, value):
        """
        Validate filter_by_attribute keys against available inventory concepts.

        Story 23.4 - AC3.
        """
        if value is None or not value:
            return value

        # Get valid concept keys from InventoryMapper
        valid_concepts = InventoryMapper.get_available_concepts('servers')

        # Validate all keys are recognized concepts
        invalid_keys = [k for k in value.keys() if k not in valid_concepts]
        if invalid_keys:
            raise serializers.ValidationError(
                f"Invalid filter attributes: {', '.join(invalid_keys)}. "
                f"Valid attributes: {', '.join(valid_concepts)}"
            )

        # Validate all values are non-empty lists
        for key, values in value.items():
            if not isinstance(values, list) or not values:
                raise serializers.ValidationError(
                    f"Filter attribute '{key}' must have a non-empty list of values"
                )

        logger.info(
            "profile_filter_by_attribute_validated",
            filter=value,
            validation_result="success",
            correlation_id=get_correlation_id()
        )

        return value
```

**Helper get_available_concepts** :
```python
# inventory/mapper.py
class InventoryMapper:
    # ... existing methods ...

    @staticmethod
    def get_available_concepts(entity_name: str = 'servers') -> list[str]:
        """
        Get available concept keys for the specified entity type.

        Concept keys are stable attribute names defined in the inventory mapping config,
        independent of actual Oracle column names. Used for RBAC filter validation.

        Args:
            entity_name: Entity type ('servers', 'instances', 'databases')

        Returns:
            List of concept keys (e.g., ['name', 'environment', 'engine_type', ...])

        Examples:
            >>> InventoryMapper.get_available_concepts('servers')
            ['name', 'environment', 'engine_type', 'zone']

            >>> InventoryMapper.get_available_concepts('instances')
            ['name', 'environment', 'server_ref', 'db_ref']

        Story 23.4 - AC5.
        """
        # Get inventory config from integration
        config = InventoryMapper._get_inventory_config()

        # Multi-table mode: read concepts from config
        if config and 'entities' in config and entity_name in config['entities']:
            columns_mapping = config['entities'][entity_name].get('columns', {})
            return list(columns_mapping.keys())

        # Fallback mode (flat table): return default concepts
        return ['name', 'environment', 'type']
```

**Application du filtre dans list_targets_for_user** :
```python
# inventory/services.py
def _apply_attribute_filter(
    servers: list[dict[str, Any]],
    filter_by_attr: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """
    Apply attribute-based filtering to servers list.

    Filters are cumulative (AND): server must match ALL criteria.
    If an attribute is absent from server data, that criterion is ignored (WARNING logged).

    Args:
        servers: List of server dicts (from list_servers or list_targets_for_user)
        filter_by_attr: Dict mapping attribute keys to allowed values.
                        Example: {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}

    Returns:
        Filtered list of servers matching all criteria.

    Story 23.4 - AC2.
    """
    if not filter_by_attr:
        return servers

    correlation_id = get_correlation_id()
    filtered = servers.copy()

    for attr_key, allowed_values in filter_by_attr.items():
        if not allowed_values:
            continue

        # Filter servers where attribute value is in allowed list
        before_count = len(filtered)
        filtered = [
            srv for srv in filtered
            if srv.get(attr_key) in allowed_values
        ]
        after_count = len(filtered)

        # Log if attribute was not found in any server
        if before_count > 0 and after_count == 0:
            # Check if attribute exists in any server
            has_attribute = any(attr_key in srv for srv in servers)
            if not has_attribute:
                logger.warning(
                    "rbac_filter_attribute_not_found",
                    attribute=attr_key,
                    allowed_values=allowed_values,
                    correlation_id=correlation_id
                )

    return filtered

def list_targets_for_user(
    self,
    user: User,
    environment: str
) -> list[dict[str, Any]]:
    """
    List authorized targets (servers) for user in specified environment.
    Applies RBAC filtering based on user's profiles.

    Story 23.4 - AC2: Now applies filter_by_attribute after permission_type filtering.
    """
    correlation_id = get_correlation_id()

    # ... existing code to get user profiles ...

    all_targets: set[str] = set()

    for profile in profiles:
        try:
            target_perm = profile.profiletargetpermission
        except ProfileTargetPermission.DoesNotExist:
            continue

        # Apply standard permission_type filtering (LIST/PATTERN/ALL)
        profile_targets = self._get_targets_for_permission_type(
            target_perm, environment
        )

        # Apply filter_by_attribute if present (Story 23.4)
        filter_by_attr = target_perm.get_filter_by_attribute()
        if filter_by_attr:
            try:
                nb_before = len(profile_targets)
                profile_targets = _apply_attribute_filter(profile_targets, filter_by_attr)
                nb_after = len(profile_targets)

                logger.info(
                    "rbac_filter_by_attribute_applied",
                    profile_id=profile.id,
                    filter=filter_by_attr,
                    nb_servers_before=nb_before,
                    nb_servers_after=nb_after,
                    correlation_id=correlation_id
                )
            except Exception as e:
                # Never fail auth due to filter error - log and skip filter
                logger.error(
                    "rbac_filter_by_attribute_error",
                    profile_id=profile.id,
                    error=str(e),
                    correlation_id=correlation_id
                )
                # Use unfiltered targets from permission_type

        # Add to cumulative set (OR between profiles)
        all_targets.update(target['name'] for target in profile_targets)

    # ... existing code to return final targets ...
```

**Migration Django** :
```python
# profiles/migrations/V055_add_filter_by_attribute.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('profiles', 'V054_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='profiletargetpermission',
            name='filter_by_attribute_json',
            field=models.TextField(
                null=True,
                blank=True,
                db_column='FILTER_BY_ATTRIBUTE_JSON',
                help_text='JSON dict filtering targets by inventory attributes. Format: {"engine_type": ["oracle"], ...}'
            ),
        ),
        # Oracle SQL equivalent:
        # ALTER TABLE PROFILE_TARGET_PERMISSIONS
        # ADD FILTER_BY_ATTRIBUTE_JSON CLOB;
        #
        # Optional: Add JSON validation constraint
        # ALTER TABLE PROFILE_TARGET_PERMISSIONS
        # ADD CONSTRAINT CHK_FILTER_BY_ATTRIBUTE_JSON_VALID
        # CHECK (FILTER_BY_ATTRIBUTE_JSON IS NULL OR FILTER_BY_ATTRIBUTE_JSON IS JSON);
    ]
```

### Standards de tests

**Référence** : Stories 23.1-23.3 (69+43+57 tests), Epic M patterns, Story 22-1 (RBAC tests)

**Couverture requise** :
- Tests unitaires modèle : serialization/deserialization JSON, edge cases
- Tests unitaires mapper : get_available_concepts avec config multi-tables et fallback
- Tests unitaires service : _apply_attribute_filter avec différents filtres, logging
- Tests unitaires serializer : validation clés valides/invalides, valeurs vides
- Tests API : POST/PUT/GET avec filter_by_attribute, erreurs 400
- Tests intégration : flow complet création profil → list_targets_for_user → serveurs filtrés
- Coverage ≥ 85% pour profiles/models.py (méthodes filter), inventory/services.py (application filtre)

**Assertions clés** :
- Vérifier que filtres sont appliqués APRÈS permission_type (affiner, pas remplacer)
- Vérifier comportement cumulatif au sein d'un profil (AND)
- Vérifier comportement additif entre profils (OR)
- Vérifier degradation gracieuse : erreurs ne bloquent jamais l'authentification
- Vérifier logging : rbac_filter_by_attribute_applied, rbac_filter_attribute_not_found, errors
- Vérifier validation API : clés invalides → 400 avec message explicite

**Pattern tests intégration** :
```python
# profiles/tests/test_integration_filter_by_attribute.py
from django.test import TestCase
from rest_framework.test import APIClient
from profiles.models import Profile, ProfileTargetPermission
from inventory.services import InventoryService
from unittest.mock import patch

class TestRBACFilterByAttributeIntegration(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create profile with filter_by_attribute
        self.profile = Profile.objects.create(
            name='oracle_dba',
            ad_group='GRP-ORACLE-DBA'
        )
        self.target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )
        self.target_perm.set_filter_by_attribute({
            'engine_type': ['oracle']
        })
        self.target_perm.save()

    @patch('inventory.services.InventoryService.list_servers')
    def test_filter_by_engine_type_oracle_only(self, mock_list_servers):
        """
        Integration test: Profile with engine_type=oracle filter
        should only return Oracle servers from list_targets_for_user.

        Story 23.4 - AC2, AC8.
        """
        # Mock inventory returns mixed servers
        mock_list_servers.return_value = [
            {'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
            {'name': 'srv02', 'environment': 'dev', 'engine_type': 'sqlserver'},
            {'name': 'srv03', 'environment': 'dev', 'engine_type': 'oracle'},
        ]

        # Mock user with this profile
        user = MagicMock(id=1)
        with patch('profiles.models.Profile.objects.find_by_ad_groups') as mock_find:
            mock_find.return_value = [self.profile]

            # Call list_targets_for_user
            service = InventoryService()
            targets = service.list_targets_for_user(user, 'dev')

        # Assert only Oracle servers returned
        self.assertEqual(len(targets), 2)
        self.assertIn('srv01', [t['name'] for t in targets])
        self.assertIn('srv03', [t['name'] for t in targets])
        self.assertNotIn('srv02', [t['name'] for t in targets])
```

### Dépendances et ordre

**Dépend de** :
- Story 23.1 (done) : InventoryMapper avec config mapping → concepts métier
- Story 23.2 (done) : InventoryService.list_servers avec attributs (engine_type, etc.)
- Story 23.3 (done) : API endpoints exposent attributs inventaire
- Epic 2 (done) : Modèle RBAC ProfileTargetPermission (V012)

**Bloque** :
- Story 23.7 : Frontend ProfileForm options "Tous Oracle / Tous SQL" (nécessite ce backend)

**N'affecte PAS** :
- Profils existants sans filter_by_attribute : comportement inchangé (champ null)
- list_targets_for_user sans filtres : fonctionne comme avant
- Endpoints API /servers /instances /databases : indépendants

### Risques et mitigations

**Risque** : Erreur de filtre bloque l'authentification utilisateur
**Mitigation** : Degradation gracieuse systématique (try/except), log ERROR, skip filtre, ne jamais raise dans list_targets_for_user

**Risque** : Clé de filtre invalide (typo admin) cause filtrage vide silencieux
**Mitigation** : Validation stricte à la sauvegarde API (AC3), message 400 explicite avec liste des clés valides

**Risque** : Attribut inventaire absent (ex. engine_type non fourni) cause filtrage trop restrictif
**Mitigation** : Logger WARNING rbac_filter_attribute_not_found, ignorer ce critère (pas tout le filtre)

**Risque** : Performance dégradée si filtre attribut sur beaucoup de serveurs
**Mitigation** : Filtrage en mémoire Python (list comprehension), léger car déjà appliqué après LIST/PATTERN/ALL (liste réduite)

**Risque** : Confusion admin entre concepts métier (engine_type) et colonnes Oracle (ENGINE)
**Mitigation** : Documentation claire docs/rbac-filter-by-attribute.md, validation API avec liste concepts valides, exemples dans UI (Story 23.7)

### Intelligence des Stories 23.1-23.3

**Story 23.1 (done)** :
- InventoryMapper opérationnel avec config mapping : entities, columns, relations
- Concepts métier stables : `{'name': 'HOSTNAME', 'environment': 'ENV', 'engine_type': 'ENGINE', ...}`
- Validation sécurité stricte : SAFE_TABLE_NAME_PATTERN, SAFE_COLUMN_NAME_PATTERN
- Config format : `config['entities']['servers']['columns'] = {'name': 'HOSTNAME', ...}`
- 69 tests passent

**Story 23.2 (done)** :
- InventoryService.list_servers(environment, engine_type) : retourne serveurs avec attributs mappés
- list_targets_for_user adapté : détecte config multi-tables, utilise list_servers
- Attributs retournés incluent : id, name, environment, engine_type (si mappé)
- 43 tests passent

**Story 23.3 (done)** :
- API GET /api/v1/inventory/servers?environment=dev&engine_type=oracle
- Sérialiseurs : ServerSerializer avec engine_type optionnel
- RBAC validation : server_name vérifié avant instances/databases
- 55 tests passent

**Patterns à réutiliser** :
- JSON helpers get/set dans modèle (pattern ProfileActionPermission)
- Validation serializer avec ValidationError message explicite
- Logging structlog systématique : correlation_id, nb_before/after, filter details
- Degradation gracieuse : try/except → log ERROR → fallback comportement standard
- Documentation RBAC : Security Note, Performance Note dans docstrings

### Commits récents pertinents

**Référence** : `git log --oneline --grep="23-" -5`

- `a840414 feat(23-3): implement multi-table inventory API endpoints` — Story 23.3, 55 tests
- `6f61d93 feat(23-2): add multi-table inventory service methods` — Story 23.2, 43 tests
- `3d39053 feat(23-1): implement config-driven multi-table inventory mapping` — Story 23.1, 69 tests

**Code patterns récents** :
- InventoryMapper.get_available_concepts() : pattern pour lister concepts disponibles
- Validation avec liste explicite : `f"Valid attributes: {', '.join(valid_list)}"`
- RBAC helpers : _validate_server_access pattern (Story 23.3)
- Migration Django avec commentaires SQL explicites
- drf-spectacular : @extend_schema_field pour types complexes (dict)

### Architecture RBAC (référence)

**Fichier** : docs/inventaire-multi-tables-ux-cibles.md §5

**Principe** : RBAC intimement lié aux données d'inventaire
- Les règles RBAC s'appuient uniquement sur les attributs mappés retournés par l'inventaire
- Les filtres (LIST, PATTERN, ou par attribut) sont évalués sur les **concepts métier** (stables)
- Une nouvelle colonne inventaire → mise à jour config mapping → nouveau concept filtrable → pas de refonte code RBAC

**Implémentation** :
- Ajouter filtres par attribut (ex. `{"engine_type": ["oracle"]}`) en JSON dans ProfileTargetPermission
- Dans list_targets_for_user, appliquer ces filtres sur les champs mappés
- La colonne réelle est dans la config de mapping ; le profil référence le concept métier

**UI** (Story 23.7 - à venir) :
- ProfileForm : options "Tous / Tous Oracle / Tous SQL"
- Extension à d'autres attributs mappés (ex. zone) sans changement schéma

### Exemples d'utilisation

**Exemple 1 : Profil "Tous les serveurs Oracle"**
```json
{
  "profile": {
    "name": "oracle_dba",
    "ad_group": "GRP-ORACLE-DBA"
  },
  "target_permissions": {
    "permission_type": "ALL",
    "filter_by_attribute": {
      "engine_type": ["oracle"]
    }
  }
}
```
**Résultat** : L'utilisateur avec ce profil voit uniquement les serveurs Oracle (tous environnements selon action_permissions.environments).

**Exemple 2 : Profil "Serveurs SQL en production uniquement"**
```json
{
  "profile": {
    "name": "sql_prod_dba",
    "ad_group": "GRP-SQL-PROD-DBA"
  },
  "target_permissions": {
    "permission_type": "ALL",
    "filter_by_attribute": {
      "engine_type": ["sqlserver"],
      "zone": ["prod"]
    }
  }
}
```
**Résultat** : L'utilisateur voit uniquement les serveurs SQL Server situés en zone prod (AND).

**Exemple 3 : Deux profils cumulés (Oracle + SQL)**
```json
{
  "profiles": [
    {
      "name": "oracle_dba",
      "target_permissions": {
        "permission_type": "ALL",
        "filter_by_attribute": {"engine_type": ["oracle"]}
      }
    },
    {
      "name": "sql_dba",
      "target_permissions": {
        "permission_type": "ALL",
        "filter_by_attribute": {"engine_type": ["sqlserver"]}
      }
    }
  ]
}
```
**Résultat** : L'utilisateur avec les deux profils voit serveurs Oracle OU SQL Server (OR entre profils).

**Exemple 4 : Combinaison LIST + filter**
```json
{
  "target_permissions": {
    "permission_type": "LIST",
    "target_names": ["srv01", "srv02", "srv03", "srv04"],
    "filter_by_attribute": {
      "engine_type": ["oracle"]
    }
  }
}
```
**Résultat** : Parmi srv01-04, l'utilisateur ne voit que ceux qui sont Oracle (affine la liste).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- 53 tests all passing (0.35s)
- Regression check: 22 pre-existing failures in inventory/tests + 1 in profiles/tests (not caused by changes)

### Completion Notes List

- Migration named `0002_add_filter_by_attribute.py` (not V055 — follows Django convention for profiles app)
- `_apply_attribute_filter` is a module-level function (not a method) to keep it testable independently
- `_apply_attribute_filters_across_profiles` method on InventoryService handles OR-between-profiles logic
- Case-insensitive matching for attribute filter values (consistent with existing RBAC patterns)
- Multi-table path in list_targets_for_user now preserves all mapped server attributes (engine_type, zone, etc.)
- drf-spectacular annotation not added as separate @extend_schema_field (DictField with help_text is self-documenting)

### File List

**Modified:**
- `profiles/models.py` — filter_by_attribute_json field + get/set helpers on ProfileTargetPermission
- `profiles/serializers.py` — filter_by_attribute DictField + validate_filter_by_attribute() + to_representation
- `profiles/services.py` — set_target_permissions handles filter_by_attribute
- `inventory/mapper.py` — get_available_concepts() static method
- `inventory/services.py` — _apply_attribute_filter() + _apply_attribute_filters_across_profiles() + list_targets_for_user integration

**Created:**
- `profiles/migrations/0002_add_filter_by_attribute.py` — Django migration
- `profiles/tests/test_filter_by_attribute.py` — 11 model tests
- `profiles/tests/test_api_filter_by_attribute.py` — 14 API/serializer tests
- `profiles/tests/test_integration_filter_by_attribute.py` — 4 integration tests
- `inventory/tests/test_mapper_concepts.py` — 6 mapper concept tests
- `inventory/tests/test_rbac_filter_by_attribute.py` — 18 RBAC filter tests
- `docs/rbac-filter-by-attribute.md` — Documentation complète

### Change Log

| AC | Status | Evidence |
|----|--------|----------|
| AC1 | Done | `profiles/models.py:232-314`, `migrations/0002_add_filter_by_attribute.py` |
| AC2 | Done | `inventory/services.py:47-95` (_apply_attribute_filter), `:729-804` (_apply_attribute_filters_across_profiles) |
| AC3 | Done | `profiles/serializers.py:235-266` (validate_filter_by_attribute) |
| AC4 | Done | `profiles/serializers.py:225-233` (DictField), `:306-319` (to_representation) |
| AC5 | Done | `inventory/mapper.py:264-293` (get_available_concepts) |
| AC6 | Done | Graceful degradation in services.py (try/except), model (malformed JSON) |
| AC7 | Done | `docs/rbac-filter-by-attribute.md` |
| AC8 | Done | 53 tests: 11 model + 6 mapper + 18 RBAC + 14 API + 4 integration |



## Code Review Findings (Completed)

**Review Date:** 2026-02-09  
**Reviewer:** Code Review Agent (bmad_bmm_code-review)  
**Issues Found:** 7 High, 2 Medium, 0 Low  
**All issues fixed automatically**

### Issues Fixed

**HIGH-1:** Type hint incorrect dans ProfileTargetPermission.get_filter_by_attribute()  
✅ Fixed: Changed `dict | None` to `dict[str, list[str]] | None`

**HIGH-2:** Risque de SQL injection dans get_available_concepts()  
✅ Fixed: Added `mapper.validate_config()` check before reading concepts

**HIGH-3:** Perte de données dans _apply_attribute_filters_across_profiles  
✅ Fixed: Changed key from `set[str]` to `set[tuple[str, str]]` pour éviter collisions (name, environment)

**HIGH-4:** Logging incomplet dans _apply_attribute_filter  
✅ Fixed: Added INFO log avec nb_servers_before/after per AC2

**HIGH-5:** Migration ne valide pas le JSON Oracle  
✅ Fixed: Documented validation strategy (app-layer vs DB constraint trade-off)

**HIGH-6:** Dégradation gracieuse incomplète dans get_filter_by_attribute  
✅ Fixed: Changed WARNING to ERROR for malformed JSON

**HIGH-7:** Absence de validation empty list dans DictField serializer  
✅ Fixed: Added check to reject empty dict `{}`

**MEDIUM-1:** Performance potentielle dégradée avec de nombreux profils  
✅ Fixed: Added performance note in docstring about O(n×m) complexity

**MEDIUM-2:** Documentation incomplète dans get_available_concepts docstring  
✅ Fixed: Added performance note about InventoryService instantiation cost

All tests still passing: 53/53 ✓
