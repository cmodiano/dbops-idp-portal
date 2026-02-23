# Spec : Inventaire — Environnement par serveur, colonne paramètre, filtre engine_type

**Contexte :** Schéma inventaire où **l'environnement est porté par le serveur** (database → instance → server). Besoin d'aligner le backend, les paramètres d'action (choix de colonne) et le filtre par technologie (engine_type).

**Date :** 2026-02-23

---

## 1. Environnement dérivé du serveur (pas des tables databases/instances)

### Constat

- **Modèle métier :** database est liée à instance, instance à un serveur ; **c'est le serveur qui décide de l'environnement**.
- **Code actuel :** Le filtre `environment` est appliqué sur la table **databases** (colonne mappée `environment`) et sur la table **instances** (idem). Aucune jointure avec la table **servers**.
- **Problème :** Si en base seule la table **servers** contient la colonne environment (et éventuellement instances/databases ne l'ont pas), les requêtes sont incorrectes ou incomplètes.

### Changements à prévoir

- **Query executor (backend)**  
  - Pour **databases** (avec ou sans filtre serveur) : dériver l'environnement via **JOIN databases → instances → servers** et appliquer le filtre sur **servers.environment** (colonne mappée dans l’entité `servers`).  
  - Pour **instances** : idem — si `environment` n’est que sur servers, faire **JOIN instances → servers** et filtrer sur **servers.environment**.  
  - Conserver la compatibilité : si le mapper définit une colonne `environment` sur databases/instances, on peut soit la garder en fallback, soit ignorer et toujours passer par servers (décision produit).

- **Mapper**  
  - Documenter que lorsque l’environnement est « porté par le serveur », les entités `instances` et `databases` n’ont pas besoin de colonne `environment` dans la config ; le filtre sera appliqué via la jointure avec `servers`.

---

## 2. Choix de la colonne dont le paramètre est dérivé (indépendant des filtres)

### Constat

- Aujourd’hui, pour un paramètre `source: 'inventory'`, on choisit uniquement **la table** (`inventory_type`: servers / instances / databases). La valeur affichée/renvoyée est en pratique celle du champ **name** (ou id) retourné par l’API.
- On ne peut pas configurer **quelle colonne** de la table doit fournir la valeur du paramètre, indépendamment des filtres (environment, server_names, etc.).

### Proposition

- Ajouter une propriété **optionnelle** dans le schéma de paramètre (côté action), par exemple :
  - **`inventory_value_column`** (ou `inventory_display_column`) : concept métier ou colonne physique dont la valeur remplit le paramètre.
- **Valeurs possibles :** concepts déjà exposés par le mapper pour l’entité choisie (ex. `name`, `id`, ou d’autres colonnes mappées selon l’entité). À aligner avec les colonnes réellement retournées par l’API (servers : name, environment, engine_type ; instances : name, server_ref, db_ref, … ; databases : name, …).
- **Comportement :**
  - Si absent : comportement actuel (ex. `name` comme valeur affichée et envoyée).
  - Si présent : l’UI et le payload utilisent la colonne indiquée pour la valeur du paramètre.
- **Filtres (environment, server_names, engine_type)** restent inchangés : ils limitent **quelles lignes** sont retournées ; `inventory_value_column` indique **quelle colonne** utiliser comme valeur pour chaque ligne.

### Implémentation (ordre logique)

1. **Backend (catalog)** : dans la validation du `parameters_schema`, accepter une clé optionnelle `inventory_value_column` (valeurs autorisées à définir selon les concepts par entité).
2. **Frontend** : dans l’éditeur de paramètres, proposer un champ optionnel « Colonne valeur » (liste déroulante selon `inventory_type`). Lors du rendu du formulaire d’exécution, utiliser cette colonne pour l’affichage et la valeur soumise (au lieu de toujours `name`).
3. **API inventaire** : pas obligatoire de changer le format de réponse ; le frontend (ou le backend au moment de l’exécution) sélectionne la bonne clé dans les objets retournés (`id`, `name`, etc.).

---

## 3. Utilisation de engine_type dans les filtres inventaire

### Constat

- **Servers :** l’API `/inventory/servers/` accepte déjà `engine_type` et le service/query_executor filtre bien sur la table servers. En revanche, le **frontend** ne transmet pas `engine_type` lors des appels (ex. wizard d’exécution), donc on peut retourner des serveurs de toutes technologies alors que l’action est liée à un moteur (ex. Oracle).
- **Instances / Databases :** les API `/inventory/instances/` et `/inventory/databases/` **n’acceptent pas** `engine_type`. Or une action « Oracle » ne devrait afficher que des instances/bases sur des serveurs Oracle ; sans filtre, on peut mélanger des technologies.

### Changements à prévoir

- **Backend**
  - **Instances :** ajouter un paramètre de requête optionnel `engine_type`. Dans le query_executor, lorsque `engine_type` est fourni : joindre la table **servers** (instances.server_ref → servers.name) et filtrer sur **servers.engine_type** (colonne mappée). Si l’environnement est déjà dérivé du serveur (point 1), la même jointure instances → servers sert pour environment et engine_type.
  - **Databases :** idem — ajouter `engine_type` en paramètre ; dans le chemin « multi-server » ou « via instances », la jointure passe déjà par instances ; ajouter la jointure vers **servers** (instances.server_ref → servers.name) et filtrer sur servers.engine_type. Pour le chemin « databases seules » (sans filtre serveur), il faudra aussi passer par instances → servers pour appliquer engine_type.
  - **Servers :** déjà OK côté API ; s’assurer que le frontend envoie bien le paramètre.

- **Frontend**
  - Lors des appels à `fetchInventoryItems(type, environment, options)` depuis le wizard (ou tout formulaire lié à une action), passer l’**engine** de l’action (ex. `action.engine`) dans les options, par ex. `options.engine_type = action.engine`.
  - Adapter `fetchInventoryItems` pour ajouter `engine_type` dans la query string lorsque fourni (pour servers, instances, databases).
  - S’assurer que la clé utilisée côté API (ex. `engine_type`) soit alignée avec le backend (normalisation minuscules/underscore si nécessaire, comme dans REF_ENGINES).

### Effet attendu

- Une action Oracle n’affichera que des serveurs/instances/databases dont le serveur associé est de type Oracle ; idem pour SQL Server, etc. On évite de proposer des cibles d’une technologie différente de celle de l’action.

---

## Récapitulatif des impacts

| Zone | Changement |
|------|------------|
| **Query executor** | Dériver environment (et engine_type) depuis la table **servers** via JOIN (databases → instances → servers, instances → servers). |
| **API instances/databases** | Ajouter paramètre optionnel `engine_type` ; propager au service et au query_executor. |
| **Frontend fetchInventoryItems** | Accepter `engine_type` dans les options et l’envoyer en query param pour servers, instances, databases. |
| **Frontend wizard** | Passer `action.engine` comme `engine_type` aux appels inventaire. |
| **Parameters_schema (catalog)** | Ajouter propriété optionnelle `inventory_value_column` (ou équivalent) ; validation selon `inventory_type`. |
| **Frontend ParametersEditor / formulaire d’exécution** | Éditer et utiliser `inventory_value_column` pour la valeur du paramètre. |

---

## Références

- `idp-portal/django_backend/inventory/query_executor.py` — `_read_databases_via_instances`, `_read_databases_multi_server`, `_read_entity_multi_server`, `_read_entity_from_config`
- `idp-portal/django_backend/inventory/views.py` — `list_servers`, `list_instances`, `list_databases`
- `idp-portal/django_backend/inventory/mapper.py` — config entités (columns: name, environment, engine_type, server_ref, db_ref)
- `idp-portal/frontend/src/services/execution_service.ts` — `fetchInventoryItems`
- `idp-portal/frontend/src/hooks/useTargetInventory.ts` — pas de `engine_type` actuellement
- `idp-portal/django_backend/catalog/serializers.py` — `validate_parameters_schema_inventory`
