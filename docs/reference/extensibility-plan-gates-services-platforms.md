# Plan d'extensibilite des gates, services et plateformes

**Date :** 2026-03-14

---

## Objectif

Definir un plan de modifications pour rendre les **gates**, **services** et **plateformes** facilement extensibles :

- cote **backend** : ajout d'un nouveau type sans dispersion dans de multiples fichiers
- cote **frontend** : affichage et configuration sans nouvelles branches hard-codees
- dans les **actions** : un nouveau type doit etre selectionnable et configurable
- dans les **workflows** : un nouveau type doit etre utilisable dans les steps et valide avant execution

Le but n'est pas seulement de simplifier le CRUD des integrations, mais de rendre un nouveau type **directement exploitable** dans les actions et les workflows.

---

## Mise a jour - etat reel sur `develop`

Depuis la redaction initiale de ce document, une partie du refactoring a ete implemente sur `develop`.

### Deja en place sur `develop`

- **PlatformRegistry** et **PlatformDefinition**
  - `idp-portal/django_backend/platforms/registry.py`
  - `idp-portal/django_backend/platforms/definitions.py`
- **ServiceDefinitionRegistry**
  - `idp-portal/django_backend/services/definitions.py`
- **GateRegistry** et **GateDefinition**
  - `idp-portal/django_backend/executions/gates/registry.py`
  - `idp-portal/django_backend/executions/gates/definitions.py`
- **API de capacites**
  - `idp-portal/django_backend/capabilities/views.py`
  - `idp-portal/django_backend/capabilities/serializers.py`
- **Frontend consommant une partie des capacites backend**
  - `idp-portal/frontend/src/services/capabilities_service.ts`
  - `idp-portal/frontend/src/hooks/useCapabilities.ts`
  - `idp-portal/frontend/src/hooks/useWorkflowStepCapabilities.ts`
  - `idp-portal/frontend/src/components/admin/step-config/ServiceCallStepConfig.tsx`
  - `idp-portal/frontend/src/components/admin/step-config/GateStepConfig.tsx`

### Ce que cela a reellement ameliore

- les **operations de services** ne sont plus dupliquees dans une constante frontend et une allowlist backend separee
- les **gates** ont maintenant une source de verite backend unique pour :
  - les types exposes
  - le mapping `gate_type -> condition_type`
  - la validation
- les **capacites backend** sont exposees au frontend pour les services, gates et les plateformes
- la **normalisation des aliases plateforme** est mieux centralisee
- les **kwargs runtime plateforme** sont mieux centralises via :
  - `idp-portal/django_backend/adapters/runtime_config.py`
- les **writes d'integration** ne sont plus verrouilles par `IntegrationType.choices`
- les **services** exposent maintenant :
  - `input_schema`
  - `output_schema`
  - `ui_hints`
- les **gates** utilisent maintenant une logique d'evaluation par strategie
- les **types de steps workflow** ont maintenant leur propre registre backend
- le frontend a maintenant :
  - `useCapabilities`
  - `useWorkflowStepCapabilities`
  - `SchemaFormRenderer`
- les anciens helpers frontend `serviceCallConstants.ts` et `integrationHelpers.ts` ont ete retires du chemin principal

### Ce qui reste incomplet

- la **resolution manuelle** des gates reste encore largement couplee a `approval_granted` et aux endpoints d'approbation existants
- le **dispatch runtime** des `step_type` reste encore base sur un `match` explicite dans le moteur de workflow
- le frontend garde encore des zones **workflow-specifiques** hard-codees :
  - palette des special steps
  - titres du panneau de configuration
  - validation `switch(stepType)`
  - labels de step dans certains utilitaires
- le frontend n'utilise pas encore pleinement les **schemas d'operation de service** pour rendre les champs de saisie
- la configuration plateforme est maintenant schema-driven pour le cas general, mais garde encore une **exception UX AAP**
- ajouter une **nouvelle integration executable** demande toujours du code runtime backend pour l'adapter ou le client de service

En consequence, ce document doit maintenant etre lu comme :

- **un plan directeur toujours valable**
- **avec une partie deja implementee sur develop**
- **et une partie encore a finir pour atteindre une extensibilite de bout en bout**

---

## Resume executif

L'etat actuel est **mieux extensible qu'avant, mais encore partiellement extensible** :

- les **services** et **plateformes** disposent deja d'un noyau correct via des registres backend
- le **frontend** est deja pilote par un catalogue pour la creation d'integrations
- mais le comportement reel reste largement distribue dans :
  - des enums Python et TypeScript
  - des allowlists runtime
  - des mappings frontend/backend dupliques
  - des formulaires specifiques non derives d'un schema
  - une logique de gate sans vrai pattern registre/strategie

La cible recommandee reste :

1. **une source de verite unique** pour les capacites d'integration et de workflow
2. **des registres backend** pour les plateformes, services et gates
3. **une API de capacites** consommee par le frontend
4. **des formulaires et validateurs drives par schema**
5. **des labels, aliases, icones et operations centralises**

---

## Clarification importante - ce que fait un registre, et ce qu'il ne fait pas

La question legitime est : **"si je dois encore modifier du code pour ajouter une plateforme ou un service, a quoi sert le registre ?"**

La reponse courte est :

- un **registre** ne supprime pas le besoin de coder un nouveau comportement runtime
- il **supprime la dispersion** de la connaissance de ce comportement dans 5 a 10 fichiers differents

### Sans registre

Ajouter une nouvelle plateforme/service demande souvent :

- un adapter ou client
- un mapping alias
- une allowlist runtime
- un mapping UI
- un mapping health check
- un mapping action/workflow
- des labels

Le risque principal est la derive :

- visible dans l'UI mais pas executable
- executable mais pas validable
- valide mais pas health-checkable
- supporte dans un endroit et oublie ailleurs

### Avec registre + definition

Ajouter une nouvelle plateforme/service executable demande encore :

1. **du code runtime**
   - un adapter de plateforme
   - ou un client de service
2. **une definition centralisee**
   - code canonique
   - labels
   - aliases
   - operations
   - capabilities
   - schemas
3. **un enregistrement unique dans le registre**

Ensuite, les autres couches peuvent **deriver automatiquement** :

- health check
- validation
- exposition des capacites frontend
- labels et listes
- options de configuration

### Ce que le registre apporte concretement

Le gain n'est donc pas **"zero code pour toute nouvelle plateforme"**.

Le gain est plutot :

- **code obligatoire uniquement la ou il y a un vrai comportement**
- **metadata et wiring centralises**
- **moins de fichiers a modifier**
- **moins de risques d'incoherence**

### Regle pratique

- **Nouveau type purement declaratif** : peut devenir proche du zero-code
  - exemple : nouveau label, alias, operation declarative deja supportee par un moteur generique
- **Nouvelle plateforme executable** : demandera toujours un adapter ou une logique runtime
- **Nouveau service avec comportement reel** : demandera toujours un client ou une logique runtime

Autrement dit :

- le **registre** rend l'ajout **simple, coherent et localise**
- il ne rend pas magiquement **sans code** une integration qui a un comportement runtime nouveau

---

## Probleme actuel a resoudre

Note importante :

- les sections ci-dessous decrivent surtout le **probleme de depart** et la cible de refactoring
- elles ne doivent plus etre lues comme un inventaire exact du `develop` actuel
- pour l'etat courant et le travail restant, voir aussi :
  - `docs/reference/extensibility-remaining-work-state-of-the-art.md`

## 1. Les integrations sont cataloguees, mais leur comportement reste hard-code

Constat actuel :

- le catalogue backend expose bien les types et actions d'integration
- le frontend utilise ce catalogue pour les formulaires d'integration
- mais l'execution reste gouvernee par des listes et mappings locaux

Exemples :

- backend :
  - `idp-portal/django_backend/executions/step_handlers/service_call_handler.py`
  - `idp-portal/django_backend/integrations/tasks.py`
  - `idp-portal/django_backend/integrations/serializers.py`
- frontend :
  - `idp-portal/frontend/src/components/admin/step-config/serviceCallConstants.ts`
  - `idp-portal/frontend/src/utils/integrationHelpers.ts`
  - `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx`

Impact :

- un nouveau type apparait facilement dans le CRUD
- mais il n'est pas automatiquement utilisable dans les actions et workflows

## 2. Les services ont une metadata dupliquee entre frontend et backend

Les operations d'un `service_call` existent a plusieurs endroits :

- catalogue backend (`IntegrationAction`)
- allowlist runtime backend (`_ALLOWED_OPERATIONS`)
- constantes frontend (`SERVICE_CALL_OPERATIONS`)
- labels frontend (`OPERATION_LABELS`, `INTEGRATION_LABELS`)

Impact :

- risque de derive entre ce qui est visible dans l'UI et ce qui passe a l'execution
- ajout d'un nouveau service necessite plusieurs modifications synchronisees

## 3. Les gates ne suivent pas un modele extensible

Les gates sont repartis entre :

- validation
- mapping `gate_type -> condition type`
- evaluation runtime
- eventuels endpoints d'approbation
- rendu frontend

Impact :

- ajout d'un nouveau gate = modifications manuelles backend + frontend
- risque de mismatch entre validation et comportement runtime

## 4. Les plateformes souffrent de plusieurs taxonomies

On trouve aujourd'hui :

- des codes canoniques d'integration
- des aliases historiques
- des codes d'affichage pour les actions
- des mappings vers `connector_type`

Impact :

- les actions/workflows doivent faire des conversions multiples
- un nouveau type demande souvent des ajouts dans plusieurs mappings

## 5. Les formulaires frontend ne sont pas drives par schema

Le frontend sait lister les types, mais ne sait pas encore :

- construire un formulaire de configuration d'action/service/gate a partir de metadata backend
- afficher dynamiquement les operations et champs requis
- valider la configuration avant sauvegarde en restant synchronise avec le backend

Impact :

- chaque nouveau comportement necessite une branche UI supplementaire

---

## Principes d'architecture cibles

## 1. Source de verite unique

Toutes les capacites necessaires a la configuration et a l'execution doivent provenir d'une definition unique :

- type canonique
- role (`platform`, `service`, `gate`)
- operations supportees
- champs de configuration
- labels
- aliases
- icones
- support health check
- support actions
- support workflow steps
- schemas d'entree/sortie

## 2. Registre backend pour chaque famille extensible

Conserver et etendre le pattern registre :

- `PlatformRegistry`
- `ServiceRegistry`
- `GateRegistry`

Chaque definition doit decrire :

- le type canonique
- la factory backend
- les capacites exposees au frontend
- les hooks de validation/runtime

## 3. Capacites exposees par API

Le frontend ne doit plus maintenir de listes locales d'operations ou de labels.

Le backend doit exposer une API de capacites, par exemple :

- `GET /api/v1/capabilities/integrations`
- `GET /api/v1/capabilities/workflow-steps`

ou enrichir les endpoints existants avec les memes informations.

## 4. UI et validation drives par schema

Les formulaires d'action, d'integration et de workflow doivent etre generes a partir de schemas et metadata backend, pas a partir de constantes locales.

## 5. Typage canonique et aliases centralises

Le projet doit definir un **code canonique unique** par type et gerer les aliases au meme endroit, cote backend.

Le frontend ne doit consommer que ce type canonique et ne plus reimplementer les conversions.

---

## Etat cible par domaine

## A. Plateformes

### Resultat cible

Ajouter une nouvelle plateforme doit demander :

1. creation d'un adapter backend
2. enregistrement dans le registre
3. ajout d'une definition de capacites
4. eventuelle configuration specifique exposee par schema

Le reste doit etre automatique :

- visible dans l'admin integrations
- selectionnable dans les actions
- utilisable dans les workflows
- valide dans le backend et dans le frontend
- health check derive du registre

### Modifications necessaires

#### Backend

1. **Remplacer la validation enum rigide par une validation catalogue/capability**
   - aujourd'hui : `IntegrationType.choices` est encore utilise en ecriture
   - cible : accepter tout type actif declare dans la source de verite
   - fichiers concernes :
     - `idp-portal/django_backend/integrations/models.py`
     - `idp-portal/django_backend/integrations/serializers.py`

2. **Introduire une definition de capacites plateforme**
   - nouvelle structure Python du type :
     - `code`
     - `display_name`
     - `aliases`
     - `icon`
     - `connector_type`
     - `action_platform_code`
     - `supports_health_check`
     - `runtime_config_schema`
     - `action_config_schema`
     - `workflow_step_schema`
   - nouveaux modules proposes :
     - `idp-portal/django_backend/platforms/definitions.py`
     - `idp-portal/django_backend/platforms/capabilities.py`

3. **Deriver les health checks depuis la definition**
   - supprimer les sets `_ADAPTER_TYPES`, `_SERVICE_TYPES` et aliases manuels la ou possible
   - utiliser la definition pour savoir :
     - quel registre instancier
     - quelles kwargs supplementaires extraire
   - fichier principal :
     - `idp-portal/django_backend/integrations/tasks.py`

4. **Centraliser les kwargs runtime specifique plateforme**
   - aujourd'hui les kwargs plateforme sont recopies dans plusieurs chemins d'execution
   - cible : une seule fonction, par exemple :
     - `build_platform_runtime_config(integration, action_or_step)`
   - modules proposes :
     - `idp-portal/django_backend/adapters/runtime_config.py`

5. **Unifier plateforme canonique / alias / code action**
   - deplacer la logique de normalisation dans une seule couche backend
   - fichiers a simplifier ensuite :
     - `idp-portal/django_backend/catalog/serializers/validators.py`
     - `idp-portal/django_backend/reference/views.py`

#### Frontend

1. **Supprimer les mappings codifies dans `integrationHelpers.ts`**
   - remplacer par les capacites backend
   - fichiers concernes :
     - `idp-portal/frontend/src/utils/integrationHelpers.ts`
     - `idp-portal/frontend/src/components/admin/ActionWizard.tsx`

2. **Rendre l'action wizard schema-driven**
   - le choix de plateforme doit charger :
     - les operations disponibles
     - la config specifique
     - les champs obligatoires
   - la section AAP/Tower doit devenir un cas standard de "plugin plateforme"

3. **Centraliser labels/icones frontend**
   - le node workflow, les listes, les panneaux et le rendu d'execution doivent consommer la meme metadata
   - fichiers concernes :
     - `WorkflowStepNode.tsx`
     - `executionRenderers.tsx`
     - `ActionWizard.tsx`

---

## B. Services

### Resultat cible

Ajouter un nouveau service doit demander :

1. implementation du client backend
2. enregistrement dans le registre
3. declaration des operations et schemas dans la source de verite

Le service doit ensuite :

- apparaitre dans les integrations
- proposer automatiquement ses operations dans les `service_call`
- exposer les champs de configuration et mappings utiles
- etre valide avant execution

### Modifications necessaires

#### Backend

1. **Fusionner metadata catalogue et allowlist runtime**
   - aujourd'hui `IntegrationAction` et `_ALLOWED_OPERATIONS` sont deux verites differentes
   - cible : l'allowlist runtime doit etre derivee de la definition du service
   - fichier a refactorer :
     - `idp-portal/django_backend/executions/step_handlers/service_call_handler.py`

2. **Introduire une definition de service**
   - nouvelle structure Python du type :
     - `code`
     - `display_name`
     - `credential_mode`
     - `operations`
     - `input_schema` par operation
     - `output_schema` par operation
     - `ui_hints`
     - `supports_health_check`
   - modules proposes :
     - `idp-portal/django_backend/services/definitions.py`
     - `idp-portal/django_backend/services/capabilities.py`

3. **Deriver le runtime `service_call` depuis la definition**
   - au lieu d'une liste manuelle :
     - verifier que l'operation existe dans la definition
     - instancier le service
     - valider les params via schema
   - `service_call_handler.py` doit devenir un orchestrateur generique

4. **Faire remonter les schemas d'operation au frontend**
   - enrichir `IntegrationAction` ou exposer une API de capacites
   - inclure :
     - labels
     - required params
     - optional params
     - types de champs
     - hints UI (textarea, select, secret ref, variable mapping)

5. **Remplacer `SERVICE_TYPES` duplique**
   - la liste statique dans `services/__init__.py` doit devenir un derive du registre ou disparaitre

#### Frontend

1. **Supprimer `serviceCallConstants.ts` comme source de verite**
   - conserver eventuellement des helpers de presentation, mais plus aucune operation ne doit y etre declaree en dur

2. **Construire `ServiceCallStepConfig` a partir de metadata backend**
   - liste des services disponible
   - operations disponibles
   - champs a saisir ou mapper
   - validation inline

3. **Construire les labels de node depuis la metadata**
   - `WorkflowStepNode.tsx` ne doit plus maintenir `INTEGRATION_LABELS` / `OPERATION_LABELS`

4. **Afficher un formulaire generique + extensions**
   - modele recommande :
     - 80 % des services utilisent un renderer generique derive du schema
     - 20 % peuvent fournir un renderer specialise optionnel

---

## C. Gates

### Resultat cible

Ajouter un nouveau gate doit demander :

1. implementation d'une strategie backend
2. enregistrement dans le registre
3. declaration du schema de configuration et de rendu

Le gate doit ensuite :

- apparaitre dans la palette workflow
- proposer automatiquement son formulaire
- etre valide avant sauvegarde
- etre evaluable par le runtime
- exposer ses etats et messages dans l'UI d'execution

### Modifications necessaires

#### Backend

1. **Creer un `GateRegistry`**
   - nouveau pattern equivalant a `ServiceRegistry` / `AdapterRegistry`
   - module propose :
     - `idp-portal/django_backend/executions/gates/registry.py`

2. **Creer une interface `GateDefinition`**
   - champs recommandes :
     - `code`
     - `display_name`
     - `category`
     - `config_schema`
     - `supports_timeout`
     - `requires_manual_resolution`
     - `serialize_condition(step_config) -> dict`
     - `evaluate(step, condition) -> GateEvaluationResult`
     - `approval_api` optionnelle si resolution humaine

3. **Refactorer `GateHandler` pour utiliser le registre**
   - aujourd'hui le mapping `approval -> approval_granted` est local
   - cible : `GateHandler` demande au registre de serialiser le gate
   - fichier :
     - `idp-portal/django_backend/executions/step_handlers/gate_handler.py`

4. **Refactorer `GateEvaluator` pour deleguer au registre**
   - chaque gate est evalue par sa definition
   - le fallback `unsupported gate type` doit disparaitre au profit d'une validation amont
   - fichier :
     - `idp-portal/django_backend/executions/gate_evaluator.py`

5. **Refactorer la validation catalogue**
   - `VALID_GATE_CONDITION_TYPES` ne doit plus etre une constante statique
   - la validation doit interroger le registre/definition
   - fichier :
     - `idp-portal/django_backend/catalog/validators.py`

6. **Encapsuler les gates manuels**
   - les endpoints d'approbation ne doivent plus etre couples a `approval_granted`
   - introduire une resolution generique :
     - `POST /executions/steps/{id}/resolve-gate`
   - les gates manuels peuvent fournir leurs regles de resolution

#### Frontend

1. **Remplacer `GATE_TYPE_OPTIONS` par de la metadata backend**
   - fichier actuel :
     - `idp-portal/frontend/src/components/admin/step-config/GateStepConfig.tsx`

2. **Construire `GateStepConfig` depuis un schema**
   - champs dynamiques selon le gate selectionne
   - support timeout, champs conditionnels, valeurs par defaut

3. **Construire labels et validation depuis la definition**
   - `WorkflowStepNode.tsx`
   - `workflowValidation.ts`
   - `workflowStepLabels.ts`

4. **Ajouter une API frontend de metadata gates**
   - hook propose :
     - `useWorkflowStepCapabilities()`
   - cette API doit alimenter :
     - palette
     - panneau de configuration
     - rendu des nodes
     - validation

---

## Plan de modifications detaille

## Phase 0 - Stabilisation et reduction de derive

Objectif : supprimer les incoherences existantes avant le refactoring de fond.

### Backend

- aligner les gates valides et les gates evaluables
- recenser les aliases historiques et definir les codes canoniques
- documenter les chemins runtime qui injectent des kwargs plateforme

### Frontend

- recenser tous les mappings locaux :
  - services
  - operations
  - plateformes
  - labels
  - icones
  - gate types

### Livrables

- matrice de compatibilite type -> backend -> frontend -> workflow
- liste des mappings a supprimer

## Phase 1 - Source de verite backend

Objectif : faire du backend le fournisseur unique de capacites.

### Modifications

1. introduire les definitions et registres manquants :
   - `PlatformDefinition`
   - `ServiceDefinition`
   - `GateDefinition`

2. exposer une API de capacites

3. remplacer les validations `ChoiceField` et constantes par des appels a ces definitions

4. faire deriver health checks, operations autorisees et aliases depuis ces definitions

### Definition de done

- ajout d'un nouveau service ou plateforme sans modifier :
  - listes hard-codees de health check
  - allowlists d'operation runtime
  - aliases multiples dans plusieurs modules

## Phase 2 - Frontend pilote par capacites

Objectif : supprimer les registres frontend manuels.

### Modifications

1. creer un client frontend pour les capacites
   - `frontend/src/services/capabilities_service.ts`
   - `frontend/src/hooks/useCapabilities.ts`

2. remplacer les constantes locales par les capacites backend

3. rendre les formulaires de configuration generiques

4. unifier les labels et icones affiches dans :
   - formulaires
   - tables
   - nodes workflow
   - rendu execution

### Definition de done

- ajout d'une nouvelle operation de service sans modification frontend de liste d'operations
- ajout d'un nouveau gate sans ajout de `switch` de labels dans plusieurs composants

## Phase 3 - Actions et workflows vraiment extensibles

Objectif : faire des actions et workflows des consommateurs standards de capacites.

### Actions

- une action de type plateforme doit etre configuree a partir des capacites de la plateforme selectionnee
- le backend doit valider la config d'action via schema
- le frontend doit afficher automatiquement les champs necessaires

### Workflows

- la palette des steps doit etre drivee par les step definitions disponibles
- chaque step doit declarer :
  - son label
  - son schema
  - ses contraintes de validation
  - ses prerequis runtime

### Definition de done

- pour ajouter un nouveau step `service_call` ou `gate`, il suffit de declarer sa definition backend et, au besoin, un renderer specialise optionnel

## Phase 4 - Migration et nettoyage

Objectif : supprimer la dette de compatibilite devenue inutile.

### Modifications

- supprimer les mappings frontend obsoletes
- supprimer les aliases backend redondants
- deprequer les anciens champs/constantes
- ajouter tests de non-regression de type "nouveau plugin visible partout"

---

## API cible recommandee

## 1. Capacites integrations

Exemple de charge utile cible :

```json
{
  "platforms": [
    {
      "code": "aap",
      "display_name": "Ansible Automation Platform",
      "aliases": ["tower"],
      "icon": "aap",
      "connector_type": "aap",
      "action_platform_code": "AAP",
      "supports_health_check": true,
      "action_config_schema": {},
      "workflow_step_schema": {}
    }
  ],
  "services": [
    {
      "code": "servicenow",
      "display_name": "ServiceNow",
      "credential_mode": "integration",
      "operations": [
        {
          "code": "create_change",
          "label": "Creer un change",
          "input_schema": {},
          "output_schema": {},
          "ui_hints": {}
        }
      ]
    }
  ]
}
```

## 2. Capacites workflow

Exemple de charge utile cible :

```json
{
  "step_types": [
    {
      "code": "platform",
      "label": "Executer",
      "category": "execution",
      "config_schema": {}
    },
    {
      "code": "service_call",
      "label": "Service",
      "category": "integration",
      "config_schema": {}
    },
    {
      "code": "gate",
      "label": "Attendre",
      "category": "control",
      "variants": [
        {
          "code": "maintenance_window",
          "label": "Fenetre de maintenance",
          "config_schema": {}
        },
        {
          "code": "approval",
          "label": "Approbation manuelle",
          "config_schema": {}
        }
      ]
    }
  ]
}
```

---

## Modifications de code recommandees par zone

## Backend

### A. Definitions et registres

Creer ou enrichir :

- `idp-portal/django_backend/adapters/registry.py`
- `idp-portal/django_backend/services/registry.py`
- `idp-portal/django_backend/executions/gates/registry.py`
- `idp-portal/django_backend/platforms/definitions.py`
- `idp-portal/django_backend/services/definitions.py`
- `idp-portal/django_backend/executions/gates/definitions.py`

### B. Capacites exposees

Creer :

- `idp-portal/django_backend/capabilities/views.py`
- `idp-portal/django_backend/capabilities/serializers.py`
- `idp-portal/django_backend/capabilities/urls.py`

### C. Validation et orchestration

Refactorer :

- `idp-portal/django_backend/integrations/serializers.py`
- `idp-portal/django_backend/integrations/tasks.py`
- `idp-portal/django_backend/executions/step_handlers/service_call_handler.py`
- `idp-portal/django_backend/executions/step_handlers/gate_handler.py`
- `idp-portal/django_backend/executions/gate_evaluator.py`
- `idp-portal/django_backend/catalog/validators.py`

## Frontend

### A. Client de capacites

Creer :

- `idp-portal/frontend/src/services/capabilities_service.ts`
- `idp-portal/frontend/src/hooks/useCapabilities.ts`
- `idp-portal/frontend/src/hooks/useWorkflowStepCapabilities.ts`

### B. Refactoring des composants de configuration

Refactorer :

- `idp-portal/frontend/src/components/admin/ActionWizard.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep2Automatisme.tsx`
- `idp-portal/frontend/src/components/admin/step-config/ServiceCallStepConfig.tsx`
- `idp-portal/frontend/src/components/admin/step-config/GateStepConfig.tsx`
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx`
- `idp-portal/frontend/src/utils/workflowValidation.ts`

### C. Suppression des verites locales

Supprimer ou reduire fortement :

- `idp-portal/frontend/src/components/admin/step-config/serviceCallConstants.ts`
- `idp-portal/frontend/src/utils/integrationHelpers.ts`

---

## Strategie de migration

## 1. Compatibilite montante

Pendant la transition :

- conserver les endpoints actuels
- enrichir les reponses plutot que casser les payloads
- garder les aliases historiques cote backend
- faire consommer la nouvelle API par le frontend derriere un feature flag si necessaire

## 2. Compatibilite descendante

Pour les workflows deja persistants :

- maintenir un mapping de migration des codes legacy vers les codes canoniques
- resoudre les anciennes valeurs au chargement
- serialiser les nouvelles definitions en format stable

## 3. Ordre recommande

1. backend capabilities
2. frontend consumption en lecture seule
3. formulaires schema-driven
4. runtime derive des definitions
5. suppression des constantes legacy

---

## Tests a ajouter

## Backend

- test d'enregistrement d'une nouvelle definition plateforme
- test d'enregistrement d'une nouvelle definition service
- test d'enregistrement d'une nouvelle definition gate
- test de derive health check depuis la definition
- test d'execution `service_call` a partir d'une operation declaree
- test de validation gate via registre
- test de bout en bout "nouveau type visible via API de capacites"

## Frontend

- test du hook `useCapabilities`
- test de rendu dynamique des operations d'un service
- test de rendu dynamique des options de gate
- test de validation workflow sans constante locale
- test ActionWizard avec plateforme generee par metadata
- test WorkflowStepNode avec labels issus des capacites

## Integration / E2E

- creer une integration d'un nouveau type
- creer une action basee sur ce type
- inserer cette action dans un workflow
- sauvegarder, relire, executer et verifier la coherence UI/runtime

---

## Critere de succes principal

Le chantier sera reussi si, apres refactoring :

- **ajouter une nouvelle plateforme** ne demande pas de modifier le frontend pour la lister et la rendre selectionnable
- **ajouter un nouveau service** ne demande pas de dupliquer ses operations dans des constantes frontend/backend
- **ajouter un nouveau gate** se fait via une definition enregistree plutot que via plusieurs `switch` disperses
- **actions et workflows** consomment les memes capacites que le runtime

---

## Exemple de resultat attendu apres refactoring

## Ajouter une plateforme

1. creer l'adapter
2. declarer `PlatformDefinition`
3. enregistrer le type
4. redemarrer

Resultat attendu :

- visible dans l'admin integrations
- visible dans le wizard action
- config deduite du schema
- runtime, health check et UI alignes

## Ajouter un service

1. creer le client service
2. declarer les operations et schemas
3. enregistrer le service

Resultat attendu :

- operations disponibles dans `service_call`
- labels et formulaires automatiques
- validation frontend/backend coherente

## Ajouter un gate

1. creer `GateDefinition`
2. definir schema + evaluation
3. enregistrer le gate

Resultat attendu :

- visible dans la palette workflow
- formulaire genere automatiquement
- validation et evaluation synchronisees

---

## Recommandation de priorite

Ordre recommande de mise en oeuvre :

1. **Backend single source of truth**
2. **API de capacites**
3. **Frontend schema-driven pour services et plateformes**
4. **GateRegistry**
5. **Nettoyage des constantes legacy**

Cet ordre maximise le gain d'extensibilite tout en limitant le risque de regression.

---

## Epic et stories

L'Epic 82 et ses stories detaillees sont definis dans :

- [Epic 82 : Extensibilite gates, services et plateformes](../backend/epic-82-extensibilite-gates-services-platforms.md)
