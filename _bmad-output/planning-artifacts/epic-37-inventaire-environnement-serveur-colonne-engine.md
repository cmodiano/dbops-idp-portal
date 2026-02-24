# Epic 37 : Inventaire — Environnement par serveur, colonne paramètre, filtre engine_type

**En tant que** DBOPS ou DBA,  
**je veux** que l'inventaire dérive l'environnement depuis la table serveurs, que je puisse filtrer par technologie (engine_type) et choisir la colonne utilisée pour les paramètres issus de l'inventaire,  
**afin de** refléter correctement le schéma (serveur = environnement) et n'afficher que des cibles cohérentes avec l'action (Oracle / SQL Server, etc.) et la colonne métier souhaitée.

---

## Contexte

- **Environnement porté par le serveur :** database → instance → server ; c'est le serveur qui décide de l'environnement. Le filtre `environment` doit être appliqué via jointure avec la table **servers**, pas sur les colonnes éventuelles des tables databases/instances.
- **engine_type :** Les API instances et databases n'acceptent pas aujourd'hui `engine_type` ; le frontend ne le passe pas pour servers. Une action Oracle peut donc proposer des serveurs/instances/databases d'une autre technologie.
- **Colonne valeur :** Un paramètre `source: inventory` utilise en pratique toujours la colonne **name**. On ne peut pas configurer quelle colonne (name, id, etc.) fournit la valeur du paramètre.

**Spec détaillée :** `_bmad-output/planning-artifacts/spec-inventaire-environnement-serveur-colonne-engine.md`

---

## Portée (scope)

- **Backend (query_executor)** : dériver environment (et engine_type) depuis la table **servers** via JOIN (instances → servers ; databases → instances → servers).
- **Backend (API)** : paramètre optionnel `engine_type` pour `/inventory/instances/` et `/inventory/databases/`.
- **Frontend** : passer `action.engine` comme `engine_type` lors des appels inventaire (servers, instances, databases).
- **Parameters_schema** : propriété optionnelle `inventory_value_column` ; validation backend, édition et utilisation frontend.

---

## Definition of Done (epic)

- [ ] Les listes instances et databases sont filtrées par environment en s'appuyant sur la table **servers** (JOIN), pas sur une colonne environment des tables instances/databases.
- [ ] Les API instances et databases acceptent le paramètre optionnel `engine_type` et filtrent via la table servers.
- [ ] Le wizard d'exécution (et tout appel inventaire lié à une action) envoie l'engine de l'action en `engine_type` pour servers, instances et databases.
- [ ] Un paramètre inventory peut optionnellement préciser `inventory_value_column` (ex. name, id) ; la valeur soumise et affichée utilise cette colonne.

---

## Stories

| # | Story | Objectif |
|---|-------|----------|
| 37.1 | Dériver l'environnement depuis la table servers | Query executor : JOIN servers pour instances et databases, filtre sur servers.environment |
| 37.2 | Filtre engine_type pour instances et databases (backend) | API + query executor : paramètre engine_type, JOIN servers, filtre servers.engine_type |
| 37.3 | Frontend : passer engine_type aux appels inventaire | fetchInventoryItems + wizard : options.engine_type = action.engine |
| 37.4 | Paramètre : inventory_value_column (backend) | Validation parameters_schema, valeurs autorisées selon inventory_type |
| 37.5 | Paramètre : inventory_value_column (frontend) | Éditeur de paramètres + formulaire d'exécution utilisent la colonne configurée |

---

## Détail des stories

### Story 37.1 : Dériver l'environnement depuis la table servers

**En tant que** équipe backend / produit,  
**je veux** que le filtre `environment` sur les listes **instances** et **databases** soit appliqué via la table **servers** (JOIN),  
**afin de** refléter le modèle où c'est le serveur qui porte l'environnement (database → instance → server).

**Contexte :** Actuellement le filtre environment est appliqué sur les colonnes mappées des tables instances et databases. Si seule la table servers contient environment, les requêtes sont incorrectes. Il faut joindre **instances → servers** et **databases → instances → servers** et filtrer sur **servers.environment**.

**Critères d'acceptation :**

- **Given** le mapper multi-tables est configuré avec entités servers, instances, databases  
**When** on appelle `read_instances(environment='dev')`  
**Then** la requête joint la table **instances** à la table **servers** (instances.server_ref → servers.name ou colonne id appropriée)  
**And** le filtre `WHERE` applique `servers.<env_column> = 'dev'` (colonne environment mappée pour servers)  
**And** les résultats ne contiennent que des instances dont le serveur est dans l'environnement demandé

- **Given** le mapper multi-tables est configuré  
**When** on appelle `read_databases(environment='dev')` sans filtre serveur  
**Then** la requête joint **databases → instances → servers** et filtre sur **servers.environment = 'dev'**  
**And** les résultats ne contiennent que des bases dont au moins une instance est sur un serveur de cet environnement

- **Given** on appelle `read_databases(environment='dev', server_names=['srv01'])`  
**Then** la requête joint databases → instances → servers  
**And** les filtres appliqués sont : servers.environment = 'dev' ET instances.server_ref IN ('srv01') (ou équivalent via servers.name)  
**And** la cohérence avec la story 37.2 (engine_type) est prévue (même jointure servers réutilisable)

- **Given** une config où instances ou databases ont encore une colonne `environment` mappée  
**Then** le comportement par défaut est d'utiliser la jointure avec servers pour le filtre environment (pas de filtre sur la colonne locale)  
**And** le mapper reste valide ; documenter en commentaire ou doc que pour « environnement porté par le serveur », la colonne environment sur instances/databases peut être omise

**Notes techniques :** Fichiers `inventory/query_executor.py` (_read_entity_from_config, _read_entity_multi_server, _read_databases_via_instances, _read_databases_multi_server), `inventory/mapper.py` (doc config).

---

### Story 37.2 : Filtre engine_type pour instances et databases (backend)

**En tant que** utilisateur du portail,  
**je veux** que les API inventaire **instances** et **databases** acceptent un paramètre optionnel `engine_type`,  
**afin de** ne recevoir que des instances/bases dont le serveur est de la technologie indiquée (ex. Oracle, SQL Server).

**Contexte :** L'API servers accepte déjà engine_type. Les API instances et databases ne l'acceptent pas ; il faut l'ajouter et, dans le query executor, joindre la table servers et filtrer sur servers.engine_type.

**Critères d'acceptation :**

- **Given** l'endpoint GET `/api/v1/inventory/instances/`  
**When** le client envoie `environment=dev&engine_type=oracle`  
**Then** le backend accepte le paramètre `engine_type` (validation serializer)  
**And** le service appelle le query executor avec `engine_type='oracle'`  
**And** la requête joint **instances → servers** (si pas déjà fait pour environment) et ajoute un filtre sur **servers.engine_type** (colonne mappée)  
**And** seules les instances dont le serveur est de type oracle sont retournées

- **Given** l'endpoint GET `/api/v1/inventory/databases/`  
**When** le client envoie `environment=dev&engine_type=oracle` (avec ou sans server_names)  
**Then** le backend accepte le paramètre `engine_type`  
**And** la requête (chemin « databases seules » ou « via instances / multi-server ») joint **servers** (via instances) et filtre sur **servers.engine_type**  
**And** seules les databases liées à des instances sur des serveurs oracle sont retournées

- **Given** `engine_type` est absent dans la requête  
**Then** aucun filtre sur engine_type n'est appliqué (comportement actuel)  
**And** pas de régression sur les appels existants

- **Given** une valeur `engine_type` non reconnue ou vide  
**Then** le backend peut soit l'ignorer soit retourner 400 selon la règle produit ; documenter le choix (recommandation : ignorer ou normaliser comme pour servers)

**Notes techniques :** `inventory/views.py` (list_instances, list_databases), `inventory/serializers.py` (InstanceFilterParamsSerializer, DatabaseFilterParamsSerializer), `inventory/services.py` (list_instances, list_databases), `inventory/query_executor.py` (propagation engine_type et JOIN servers).

---

### Story 37.3 : Frontend — Passer engine_type aux appels inventaire

**En tant qu'**utilisateur lançant une action (ex. Oracle),  
**je veux** que les listes inventaire (serveurs, instances, bases) ne proposent que des éléments de la technologie de l'action,  
**afin de** ne pas choisir par erreur un serveur ou une base d'une autre technologie.

**Contexte :** L'API servers accepte déjà engine_type ; les API instances et databases l'accepteront après la story 37.2. Le frontend n'envoie aujourd'hui pas engine_type. Il faut passer l'engine de l'action (ex. `action.engine`) dans les options d'appel inventaire et l'ajouter à l'URL.

**Critères d'acceptation :**

- **Given** la fonction `fetchInventoryItems(type, environment?, options?)`  
**When** `options.engine_type` est fourni (ex. `'Oracle'` ou code normalisé)  
**Then** le paramètre `engine_type` est ajouté à la query string de l'URL pour les types `servers`, `instances` et `databases`  
**And** la clé utilisée est celle attendue par le backend (ex. `engine_type`)  
**And** le cache (clé / cacheKey) prend en compte engine_type pour éviter des hits incorrects

- **Given** le wizard d'exécution (ou tout formulaire lié à une action) charge des listes inventaire  
**When** l'action a un champ `engine` défini (ex. Oracle, SQL Server)  
**Then** les appels à `fetchInventoryItems` pour servers, instances et databases passent `engine_type` dérivé de `action.engine` (même valeur ou normalisation alignée avec REF_ENGINES / backend)  
**And** les listes affichées sont filtrées côté backend par cette technologie

- **Given** l'action n'a pas d'engine (ex. workflow conteneur) ou engine est vide  
**Then** `engine_type` n'est pas envoyé (comportement actuel : toutes technologies)  
**And** pas de régression pour les actions sans moteur

**Notes techniques :** `frontend/src/services/execution_service.ts` (fetchInventoryItems), `frontend/src/hooks/useTargetInventory.ts` (recevoir action ou engine et le passer en options). Vérifier alignement des codes engine (REF_ENGINES) entre frontend et backend.

---

### Story 37.4 : Paramètre d'action — inventory_value_column (backend)

**En tant que** DBOPS configurant une action,  
**je veux** pouvoir indiquer **quelle colonne** de l'entité inventaire (name, id, etc.) doit fournir la valeur du paramètre lorsque `source: inventory`,  
**afin de** utiliser la colonne métier adaptée (ex. id technique au lieu du nom) indépendamment des filtres (environment, server_names, engine_type).

**Contexte :** Aujourd'hui le schéma de paramètre accepte `source` et `inventory_type` mais pas le choix de la colonne. La valeur utilisée est en pratique toujours celle du champ name (ou id) retourné par l'API. On ajoute une propriété optionnelle `inventory_value_column`.

**Critères d'acceptation :**

- **Given** la validation du `parameters_schema` (catalog)  
**When** une propriété de paramètre a `source: 'inventory'` et optionnellement `inventory_value_column: <value>`  
**Then** si `inventory_value_column` est présent, il doit être une valeur autorisée pour l'`inventory_type` concerné  
**And** valeurs autorisées au minimum : `name`, `id` pour chaque type (servers, instances, databases) ; autres colonnes exposées par l'API (ex. environment, server_ref, db_ref pour instances) peuvent être ajoutées selon besoin  
**And** si `inventory_value_column` est absent, le schéma reste valide (comportement actuel : équivalent à name ou id selon implémentation existante)

- **Given** `inventory_value_column` contient une valeur non autorisée pour l'entité  
**Then** la validation renvoie une erreur explicite (ex. "inventory_value_column must be one of: name, id for inventory_type servers")

- **Given** sauvegarde / mise à jour d'une action avec un parameters_schema contenant `inventory_value_column` valide  
**Then** la valeur est persistée dans PARAMETERS_SCHEMA (Oracle JSON)  
**And** les API GET action retournent le schéma inchangé

**Notes techniques :** `catalog/serializers.py` (validate_parameters_schema_inventory ou équivalent), éventuellement `catalog/models.py`. Définir la liste des colonnes autorisées par inventory_type (ex. constantes ou mapping type → colonnes).

---

### Story 37.5 : Paramètre d'action — inventory_value_column (frontend)

**En tant que** DBOPS,  
**je veux** dans l'éditeur de paramètres pouvoir choisir la **colonne valeur** pour un paramètre source inventaire, et en exécution voir la valeur soumise correspondre à cette colonne,  
**afin de** utiliser la bonne colonne métier (name, id, etc.) pour chaque paramètre.

**Contexte :** Backend valide et persiste `inventory_value_column` (story 37.4). Le frontend doit permettre de l'éditer et de l'utiliser au moment du rendu du formulaire et de la soumission.

**Critères d'acceptation :**

- **Given** l'éditeur de paramètres (ParametersEditor ou équivalent)  
**When** un paramètre a `source: 'inventory'` et un `inventory_type` (servers, instances, databases)  
**Then** un champ optionnel « Colonne valeur » (ou « Valeur affichée / envoyée ») est affiché  
**And** les options sont une liste déroulante dépendante de l'`inventory_type` (ex. name, id ; éventuellement autres colonnes selon spec 37.4)  
**And** la valeur par défaut est `name` (ou équivalent actuel) si non renseigné  
**And** à la sauvegarde du schéma, `inventory_value_column` est inclus dans la propriété du paramètre si une valeur est choisie

- **Given** le formulaire d'exécution (wizard ou formulaire dynamique)  
**When** un champ est alimenté par l'inventaire (liste déroulante)  
**Then** les options affichées utilisent la colonne configurée (`inventory_value_column` ou défaut `name`) pour l'affichage du libellé  
**And** la valeur soumise (payload) est celle de la même colonne pour l'élément sélectionné  
**And** si `inventory_value_column` est absent, le comportement actuel est conservé (name ou id)

- **Given** une action existante sans `inventory_value_column`  
**Then** l'éditeur n'affiche pas d'erreur et le formulaire d'exécution se comporte comme aujourd'hui  
**And** la rétrocompatibilité est assurée

**Notes techniques :** `frontend/src/utils/parametersSchema.ts` (schemaToParameterList, parameterListToSchema), `frontend/src/types/api/catalog.ts` (ParameterDefinition), composants ParametersEditor et formulaire d'exécution (useDynamicForm, champs select inventaire). S'assurer que les objets retournés par l'API inventaire exposent bien les clés id, name, etc., utilisées par inventory_value_column.

---

## Dépendances

- **37.1** : prérequis pour 37.2 (jointure servers déjà en place pour environment, on ajoute le filtre engine_type sur la même jointure).
- **37.2** : prérequis pour 37.3 (le frontend ne peut envoyer engine_type que si le backend l'accepte).
- **37.4** : prérequis pour 37.5 (le frontend édite et utilise une propriété validée et persistée par le backend).

---

## Références

- `_bmad-output/planning-artifacts/spec-inventaire-environnement-serveur-colonne-engine.md`
- `idp-portal/django_backend/inventory/query_executor.py`
- `idp-portal/django_backend/inventory/views.py`, `inventory/services.py`, `inventory/serializers.py`
- `idp-portal/django_backend/catalog/serializers.py` (parameters_schema)
- `idp-portal/frontend/src/services/execution_service.ts`, `useTargetInventory.ts`, `parametersSchema.ts`
