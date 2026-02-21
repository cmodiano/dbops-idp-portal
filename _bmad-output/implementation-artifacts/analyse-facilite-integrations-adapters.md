# Analyse : facilité d’ajout d’intégrations/adapters

**Contexte** : Évaluer la facilité d’ajouter des intégrations ou adapters (ex. API interne custom, autre service) et de les enregistrer pour les rendre disponibles et utilisables.

---

## 0. Vocabulaire et modèle cible

Il existe une confusion historique entre **intégration** et **plateforme**. Le modèle voulu est le suivant :

- **Intégration** : entité enregistrée dans le backend (modèle `Integration`), configurable dans **Admin > Intégrations** (`admin/integrations`). Une intégration a un type (ex. AAP, GitHub Actions, API custom) défini par le catalogue des types (`IntegrationTypeCatalogue`). À l’exécution, c’est l’**intégration** (instance configurée) qui est utilisée.
- **Action** : peut être associée à une **intégration** (ex. via `integration_id`) pour s’exécuter sur celle-ci. La liste des intégrations disponibles pour une action doit venir des **intégrations** effectivement configurées (filtrées par rôle plateforme si besoin), pas d’une table de référence séparée.
- **REF_PLATFORMS** : table de référence (Oracle V051) qui duplique cette notion avec des codes proches mais différents. Elle n’apporte pas de valeur par rapport au catalogue des types d’intégration et aux intégrations configurées ; **elle est considérée comme un doublon inutile** et peut être supprimée ou dépréciée une fois le formulaire action et la validation alignés sur les intégrations.

En résumé : la seule source de vérité pour « où peut s’exécuter une action » ce sont les **intégrations** (types dans le catalogue + instances dans Admin > Intégrations). Pas besoin d’une table REF_PLATFORMS à part.

---

## 1. Synthèse

| Aspect | Adapters (types d’intégration exécution) | Services |
|--------|------------------------------------------|----------|
| **Enregistrement** | Registry OCP : 1 factory + 1 `register()` dans `adapters/__init__.py` | Idem : 1 factory + 1 `register()` dans `services/__init__.py` + entrée dans `SERVICE_TYPES` |
| **Découverte** | Automatique via `get_platform_adapter(platform_type, ...)` (où `platform_type` = type d’intégration) | Automatique via `get_service_client(service_type, ...)` |
| **Contrat** | Implémenter `BaseAdapter` (trigger, get_status, get_job_logs, cancel_execution) | Pas d’interface formelle ; contrat par usage (config **kwargs) |
| **Point douloureux** | Aligner `Integration.type` et catalogue (IntegrationTypeCatalogue) ; **REF_PLATFORMS à supprimer** | `SERVICE_TYPES` doit rester synchronisé avec le registry (assert au import) |
| **Enregistrement externe** | Possible : `from adapters import adapter_registry` puis `register()` au démarrage (ex. AppConfig) | Idem pour `service_registry`, plus mise à jour de `SERVICE_TYPES` si utilisé |

**Verdict** : L’ajout d’une **intégration** (ex. API interne custom) est **facile** côté code (registry + factory) et plus simple côté métier si on s’appuie uniquement sur les intégrations et le catalogue (sans REF_PLATFORMS). L’ajout d’un **service** reste simple au registry, avec le couplage `SERVICE_TYPES` à maintenir.

---

## 2. Côté code : registries et factories

### 2.1 Adapters (plateformes d’exécution)

- **Fichiers clés** : `adapters/registry.py`, `adapters/__init__.py`, `adapters/base_adapter.py`.
- **Pattern** : `AdapterRegistry` avec `register(platform_type, factory_fn)` et `get(platform_type, **kwargs)`.
- **Ajouter un nouvel adapter (ex. API interne)** :
  1. Créer une classe héritant de `BaseAdapter` dans un nouveau module (ex. `adapters/custom_api_adapter.py`).
  2. Implémenter `trigger`, `get_status`, `get_job_logs`, `cancel_execution` (async).
  3. Définir une factory qui prend au minimum `base_url`, `auth_headers`, optionnellement `timeout` et `**kwargs`, et retourne l’instance.
  4. Dans `adapters/__init__.py` : importer la factory (lazy dans la factory si besoin), puis `adapter_registry.register("custom_api", _factory_custom_api)`.

Aucun `if/elif` à toucher : le registry est la seule source de vérité. La signature publique `get_platform_adapter(platform_type, base_url, auth_headers, timeout=None, **platform_kwargs)` reste inchangée.

**Enregistrement depuis l’extérieur du package** : possible en important `adapter_registry` (ex. dans un `AppConfig.ready()` ou au chargement d’une app Django) et en appelant `adapter_registry.register("custom_api", my_factory)`. Les tests le font déjà avec un mock puis `unregister()` pour ne pas polluer.

### 2.2 Services (Vault, Splunk, Jira, etc.)

- **Fichiers clés** : `services/registry.py`, `services/__init__.py`.
- **Pattern** : `ServiceRegistry` avec `register(service_type, factory_fn)` et `get(service_type, **config)`.
- **Ajouter un nouveau service (ex. API interne)** :
  1. Créer le client dans un nouveau module (ex. `services/custom_api_service.py`).
  2. Définir une factory `(**config) -> instance`.
  3. Dans `services/__init__.py` : `service_registry.register("custom_api", _factory_custom_api)` **et** ajouter une entrée dans le dict `SERVICE_TYPES` (clé `"custom_api"`, valeur = chemin du module/classe, pour rétrocompat et tests). Une assertion au import vérifie que les clés de `SERVICE_TYPES` coïncident avec `service_registry.list_types()`.

Contrainte : toute nouvelle inscription au registry doit être accompagnée d’une entrée dans `SERVICE_TYPES`, sinon `AssertionError` au chargement du module.

**Enregistrement externe** : possible via `service_registry.register()`, mais si le code qui liste les types s’appuie sur `SERVICE_TYPES`, il faudra aussi étendre ce dict (ou le rendre dérivé du registry pour éviter la double maintenance).

---

## 3. Côté métier : modèles et catalogue

Pour qu’une nouvelle plateforme soit **utilisable** end-to-end (création d’intégration, exécutions, annulation, catalogue), il faut aligner plusieurs couches.

### 3.1 `Integration.type` et exécution

- Les vues d’exécution utilisent `platform_type = getattr(integration, "integration_type", None) or integration.type` puis `get_platform_adapter(platform_type=platform_type, base_url=..., auth_headers=..., **platform_kwargs)`.
- Donc le **string** stocké dans `Integration.type` (ou exposé comme `integration_type`) doit être **exactement** la clé enregistrée dans l’adapter registry (ex. `"custom_api"`).

### 3.2 Modèle `Integration` et `IntegrationType`

- `Integration.type` est un `CharField(max_length=50, choices=IntegrationType.choices)`.
- Le commentaire dans le code indique que la base autorise des types libres (V024) ; en Django, `choices` ne contraint pas la base, seulement la validation formulaire.
- Pour une API custom, deux options :
  - **Recommandé** : ajouter une valeur dans `IntegrationType` (ex. `CUSTOM_API = 'custom_api', 'API interne'`) pour cohérence et formulaires/admin.
  - **Possible** : créer des intégrations avec `type='custom_api'` sans ajouter au enum (si l’admin/formulaire n’impose pas les choices).

### 3.3 Catalogue `IntegrationTypeCatalogue` et rôle

- Le catalogue (`IntegrationTypeCatalogue`) définit les types avec un `code` (aligné sur le type d’intégration) et un `integration_role` (platform vs service).
- Pour les plateformes, le workflow et le catalogue s’attendent à ce que les types « plateforme » existent dans ce catalogue (ex. pour la validation, les actions disponibles).
- **À faire pour une nouvelle plateforme** : créer une entrée dans `IntegrationTypeCatalogue` avec `code='custom_api'`, `integration_role=IntegrationRole.PLATFORM`, et éventuellement des `IntegrationAction` associées (ex. `start_job`, `cancel_job`).

### 3.4 REF_PLATFORMS — doublon à supprimer

- La table **REF_PLATFORMS** (modèle `RefPlatform`) est un **doublon** de la notion d’intégration / types du catalogue. Elle n’est pas utile : les intégrations (et leur type dans `IntegrationTypeCatalogue`) suffisent. Une fois le formulaire action et la validation basés sur les **intégrations** (voir Epic 31), REF_PLATFORMS peut être supprimée ou dépréciée. En attendant, le test `test_mapping_covers_all_platform_types` impose artificiellement un alignement catalogue ↔ RefPlatform ; ce test pourra être retiré ou adapté lors de la suppression de REF_PLATFORMS.

### 3.5 Fixtures / seed

- Les types par défaut sont chargés via fixtures (`loaddata integration_type_catalogue`) ou la commande `seed_integration_types`.
- Pour un type custom livré avec le produit : ajouter le type (et ses actions) dans les fixtures ou dans la logique de seed. Pour un type ajouté par une app externe, l’app peut enregistrer l’adapter dans le registry et créer les entrées de catalogue/RefPlatform au migrate ou via une commande dédiée.

---

## 4. Exemple concret : API interne custom

### 4.1 Adapter

1. **Fichier** : `adapters/custom_api_adapter.py`
   - Classe `CustomAPIAdapter(BaseAdapter)` avec `trigger`, `get_status`, `get_job_logs`, `cancel_execution` (appels à l’API interne).
2. **Enregistrement** dans `adapters/__init__.py` :
   - `def _factory_custom_api(base_url, auth_headers, timeout=None, **kwargs): ... return CustomAPIAdapter(...)`
   - `adapter_registry.register("custom_api", _factory_custom_api)`

Après ça, tout appel à `get_platform_adapter("custom_api", base_url=..., auth_headers=...)` renverra une instance de `CustomAPIAdapter`.

### 4.2 Rendre l’intégration utilisable dans l’app

- **Integration** : créer une `Integration` avec `type='custom_api'`, `base_url`, etc.
- **Catalogue** : ajouter `IntegrationTypeCatalogue` avec `code='custom_api'`, `integration_role='platform'`, et les `IntegrationAction` nécessaires.
- **Optionnel** : ajouter `IntegrationType.CUSTOM_API = 'custom_api', 'API interne'` pour l’admin/formulaires. **Pas besoin** d’entrée REF_PLATFORMS (doublon à supprimer).

### 4.3 Enregistrement depuis une app Django externe

- Dans `MyAppConfig.ready()` (ou un module importé au démarrage) :
  - `from adapters import adapter_registry`
  - Définir une factory qui instancie l’adapter custom (éventuellement dans un package tiers).
  - `adapter_registry.register("custom_api", my_factory)`.
- Côté catalogue / IntegrationType : soit les fixtures de l’app les créent (migration de données ou commande), soit l’équipe les ajoute manuellement pour ce type. Pas de RefPlatform (doublon).

---

## 5. Points de friction et recommandations

| Friction | Recommandation |
|----------|----------------|
| **SERVICE_TYPES** duplique la liste des services et impose une assert | À long terme : dériver `SERVICE_TYPES` du registry (ex. `{k: default_module_path(k) for k in service_registry.list_types()}`) ou documenter clairement la procédure « registry + SERVICE_TYPES » pour tout nouveau service. |
| Plusieurs couches à aligner (type, catalogue, fixtures) | Documenter un checklist « Nouvelle intégration » : 1) Adapter + register, 2) IntegrationType (optionnel), 3) IntegrationTypeCatalogue + actions, 4) Fixtures/seed. Ne plus dépendre de REF_PLATFORMS. |
| Pas de hook officiel « plugin » au démarrage Django | Si les intégrations custom sont fréquentes, envisager un point d’entrée explicite (ex. `AppConfig.ready()` documenté, ou liste `ADAPTER_PLUGINS` / `SERVICE_PLUGINS` dans les settings qui sont chargés et enregistrés). |
| Contrat services moins formel que BaseAdapter | Pour homogénéité, envisager une interface minimale (ex. classe de base ou protocole) pour les services, sans casser les clients existants. |

---

## 6. Références dans le code

- **Registries** : `adapters/registry.py` (AdapterRegistry), `services/registry.py` (ServiceRegistry).
- **Enregistrements** : `adapters/__init__.py` (l.68–76), `services/__init__.py` (l.56–64, 71–87).
- **Résolution en exécution** : `executions/views/execution_views.py` (l.352–366, 523–537), `executions/workflow_runtime.py` (l.860–882).
- **Modèles** : `integrations/models.py` (Integration, IntegrationType, IntegrationTypeCatalogue, IntegrationRole).
- **Tests d’intégration registry** : `adapters/tests/test_registry.py` (TestRegistryIntegration), `services/tests/test_registry.py`.
- **Story 33.1** : `_bmad-output/implementation-artifacts/33-1-ocp-registry-pattern-adapters-services.md`.

---

## 7. REF_PLATFORMS : doublon inutile

### 7.1 Conclusion

**REF_PLATFORMS est un doublon et n’est pas utile.** La confusion vient du vocabulaire (intégration vs plateforme). Le modèle cible est :

- Les **intégrations** sont enregistrées dans le backend et rendues disponibles dans **Admin > Intégrations** pour être définies et configurées.
- Une **action** utilise une **intégration** (via `integration_id` ou équivalent) ; la liste des choix pour l’action doit venir des intégrations configurées (filtrées par type / rôle si besoin), pas d’une table de référence séparée.
- Le **type** d’intégration (AAP, GitHub Actions, API custom, etc.) est porté par `IntegrationTypeCatalogue` et par le registry d’adapters. C’est la seule source de vérité nécessaire.

REF_PLATFORMS (Oracle V051) duplique cette notion avec des codes différents (AAP, « GitHub Actions », etc.) et oblige à maintenir deux listes en parallèle. Elle peut être **supprimée** une fois que :

1. Le formulaire action est alimenté par les **intégrations** (Epic 31, Story 31.1).
2. La validation de l’action s’appuie sur l’intégration sélectionnée (ou sur `IntegrationTypeCatalogue`) au lieu de RefPlatform.
3. L’API `GET /reference/platforms` est remplacée ou dépréciée au profit des intégrations (ex. GET intégrations filtrées par rôle).

### 7.2 État actuel (à migrer)

- **Validation** : `catalog/serializers.py` — `validate_platform()` exige que `Action.platform` soit dans RefPlatform → à remplacer par une validation basée sur l’intégration / le type du catalogue.
- **API** : `GET /api/v1/reference/platforms` → à remplacer par la liste des intégrations (types plateforme) ou par les types du catalogue.
- **Test** : `test_mapping_covers_all_platform_types` (catalogue ↔ RefPlatform) → à retirer ou adapter lorsque REF_PLATFORMS est supprimé.
- **Workflow** : `workflow_runtime` utilise `action.platform` pour appeler l’adapter ; à terme, le type peut être dérivé de l’intégration liée à l’action (`integration.type`) plutôt que d’un champ `platform` validé contre RefPlatform.
