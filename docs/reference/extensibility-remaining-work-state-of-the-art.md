# Extensibilite - remaining work pour une architecture state of the art

**Date :** 2026-03-14

---

## Objectif

Definir le **travail restant** pour atteindre une architecture moderne, simple et durable autour des **plateformes**, **services** et **gates**.

La cible souhaitee est la suivante :

- **aucune logique metier hard-codee dans le frontend**
- **le backend est la source de verite unique**
- **le frontend consomme des APIs de capacites et de schemas**
- **le code reste lisible et auto-explicatif**
- **l'extensibilite ne repose pas sur des branches speciales dispersees**

Ce document ne remplace pas le plan general :

- voir aussi `docs/reference/extensibility-plan-gates-services-platforms.md`

Ici, on se concentre sur :

- ce qu'il faut encore supprimer
- ce qu'il faut encore simplifier
- ce qu'il faut encore exposer via API
- le design cible le plus simple possible

---

## Vision cible

## Principe directeur

Pour tout ce qui concerne plateformes, services, gates, actions et workflows :

- le **backend declare**
- le **backend valide**
- le **backend expose**
- le **frontend affiche et orchestre l'edition**

Le frontend ne doit pas "connaitre" les verites metier.

Il doit seulement connaitre :

- comment charger les capacites
- comment afficher un schema
- comment poster une configuration valide

---

## Ce que signifie "state of the art" ici

L'objectif n'est **pas** de construire un framework plugin complexe.

L'objectif est de construire un systeme :

- **data-driven**
- **faiblement couple**
- **simple a lire**
- **difficile a casser**
- **facile a etendre sans chasse au tresor dans le code**

En pratique, cela veut dire :

1. **une seule declaration canonique par type**
2. **aucune duplication frontend/backend des memes regles**
3. **aucune conversion cachee dans plusieurs utilitaires**
4. **pas de composants generiques remplis de `if service === ...`**
5. **pas de logique runtime dispersee entre serializer, task, UI, helper et renderer**

---

## Principes de design non negociables

## 1. Backend source de verite

Le backend doit porter toutes les metadonnees necessaires :

- code canonique
- display name
- aliases
- role
- operations
- schemas d'entree
- schemas de sortie
- hints UI
- contraintes runtime
- support health check
- support action
- support workflow

Le frontend ne doit plus maintenir de listes locales comme source principale.

## 2. Frontend thin client

Le frontend doit :

- charger des capacites
- rendre des selects, forms et labels
- afficher des erreurs de validation
- poster les payloads

Le frontend ne doit pas :

- reconstituer les regles metier
- deduire localement les operations supportees
- convertir lui-meme les codes plateformes
- maintenir des fallback metier durables

## 3. Schemas avant branches speciales

Quand un nouveau type demande seulement :

- des champs
- des labels
- des contraintes
- des mappings simples

alors cela doit passer par un **schema** et non par une nouvelle branche codee en dur.

Les branches speciales ne doivent rester que pour :

- un adapter runtime reel
- un client de service reel
- un renderer UX exceptionnel justifie

## 4. Canonical codes only

Un type doit avoir :

- **un code canonique**
- des **aliases** uniquement cote backend

Le frontend consomme uniquement le code canonique.

## 5. Code auto-explicatif

Le design cible doit preferer :

- des dataclasses/declarations simples
- des noms explicites
- des schemas clairs
- peu d'indirections

Il faut eviter :

- les couches "plugin" abstraites inutiles
- les factories multiples qui cachent le comportement
- les mappages paralleles portant la meme information

---

## Cible fonctionnelle finale

## Ajouter une plateforme

Le flux cible doit etre :

1. implementer l'adapter runtime
2. declarer une `PlatformDefinition`
3. enregistrer la definition

Puis automatiquement :

- visible dans les integrations
- visible dans les actions
- config d'action derivee du schema backend
- health check derive de la definition
- workflow compatible sans ajout de mapping frontend

## Ajouter un service

Le flux cible doit etre :

1. implementer le client runtime
2. declarer une `ServiceDefinition`
3. declarer les operations et leurs schemas
4. enregistrer la definition

Puis automatiquement :

- operations visibles dans `service_call`
- labels derives de l'API backend
- formulaire genere depuis schema
- validation frontend/backend coherente

## Ajouter un gate

Le flux cible doit etre :

1. implementer la strategie runtime
2. declarer une `GateDefinition`
3. enregistrer la definition

Puis automatiquement :

- gate visible dans la palette workflow
- formulaire derive du schema
- validation derivee de la definition
- rendu derive de metadata backend

---

## Etat actuel - ce qu'il reste a enlever

## A. Hardcoding restant cote backend

### 1. Types d'integration encore verrouilles par enum

Probleme :

- la creation/mise a jour d'integration reste liee a `IntegrationType.choices`

Exemple :

- `idp-portal/django_backend/integrations/serializers.py`

Impact :

- un nouveau type declare dans un registre reste bloque a l'ecriture tant que l'enum n'est pas modifie

Travail restant :

- remplacer la validation enum par une validation derivee :
  - du catalogue actif
  - ou du registre/capability backend

### 2. GateEvaluator encore partiellement code en dur

Probleme :

- le registre existe, mais l'evaluation contient encore des branches par type

Exemple :

- `idp-portal/django_backend/executions/gate_evaluator.py`

Impact :

- une nouvelle definition de gate ne suffit pas encore a rendre le gate executable

Travail restant :

- deplacer la logique d'evaluation dans les definitions/strategies de gate
- faire du `GateEvaluator` un simple orchestrateur

### 3. API de capacites encore trop legere

Probleme :

- les services exposent surtout :
  - code
  - label
  - operations

mais pas encore assez de details pour rendre une UI totalement declarative.

Exemple :

- `idp-portal/django_backend/capabilities/views.py`

Travail restant :

- exposer pour chaque operation :
  - input schema
  - output schema
  - ui hints
  - contraintes
  - valeurs par defaut

### 4. Step types encore partiellement statiques

Probleme :

- certains `step_types` restent decrits a la main dans la vue capabilities

Exemple :

- `_STEP_TYPES_STATIC` dans `idp-portal/django_backend/capabilities/views.py`

Travail restant :

- centraliser les step definitions de la meme maniere que les gates/services/plateformes
- faire du endpoint capabilities un simple reflecteur de definitions

### 5. Heritage legacy `ActionPlatform`

Probleme :

- il subsiste encore une couche de compatibilite entre :
  - code integration
  - connector type
  - code action

Impact :

- l'architecture reste plus complexe que necessaire

Travail restant :

- definir une cible de simplification :
  - soit supprimer `ActionPlatform`
  - soit le traiter comme detail de persistence derive automatiquement

---

## B. Hardcoding restant cote frontend

### 1. ActionWizard encore partiellement specifique plateforme

Probleme :

- l'ActionWizard utilise maintenant les capacites pour une partie du mapping
- mais certains comportements restent specifiques, notamment autour de la configuration AAP

Exemple :

- `idp-portal/frontend/src/components/admin/ActionWizard.tsx`

Travail restant :

- remplacer les blocs plateforme-specifiques par un rendu de `action_config_schema`
- limiter les renderers specifiques aux cas vraiment exceptionnels

### 2. GateStepConfig consomme des variants, mais pas encore un vrai schema

Probleme :

- les types de gates viennent du backend
- mais le formulaire n'est pas encore construit a partir de `config_schema`

Exemple :

- `idp-portal/frontend/src/components/admin/step-config/GateStepConfig.tsx`

Travail restant :

- rendre les champs conditionnels declaratifs
- faire disparaitre la dependance aux noms specifiques comme `approval`

### 3. WorkflowStepNode garde encore des labels de gates en dur

Probleme :

- le node workflow consomme deja les capacites pour les services
- mais garde une partie du rendu de gate localement

Exemple :

- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx`

Travail restant :

- rendre les labels/variants de gates derives du backend
- rendre le titre et le badge dependants de metadata plutot que de `if gate_type === ...`

### 4. Fallbacks frontend encore trop metier

Probleme :

- des fallbacks locaux restent presents pour les gates

Exemple :

- `idp-portal/frontend/src/hooks/useWorkflowStepCapabilities.ts`

Impact :

- le frontend peut continuer a porter une verite implicite differente du backend

Travail restant :

- limiter les fallbacks a la resilience technique
- ne jamais reintroduire une verite metier locale durable

### 5. Le frontend n'a pas encore un renderer de schema commun

Probleme :

- les composants consomment les capacites, mais il manque encore un moteur de rendu commun pour les schemas

Travail restant :

- creer un renderer simple pour :
  - string
  - number
  - boolean
  - enum
  - array simple
  - object simple
  - mapping key/value

Le but est de couvrir 80 % des besoins sans branches specifiques.

---

## Architecture cible recommandee

## 1. Definitions simples cote backend

Conserver une forme simple et lisible :

- `PlatformDefinition`
- `ServiceDefinition`
- `GateDefinition`
- `WorkflowStepDefinition`

Chaque definition doit etre :

- petite
- lisible
- auto-explicative
- proche du langage metier

### Exemple de structure cible minimale

```python
@dataclass(frozen=True)
class ServiceDefinition:
    code: str
    display_name: str
    requires_integration: bool
    operations: tuple["ServiceOperationDefinition", ...]
    supports_health_check: bool = False
```

```python
@dataclass(frozen=True)
class ServiceOperationDefinition:
    code: str
    label: str
    input_schema: dict
    output_schema: dict
    ui_hints: dict
```

Pas plus d'abstraction tant qu'elle n'apporte pas un gain clair.

## 2. API de capacites complete

Le backend doit exposer une API assez riche pour piloter l'UI sans logique metier locale.

### Endpoint integrations capabilities

Doit exposer :

- plateformes
- services
- operations
- schemas
- labels
- aliases si utile
- hints UI

### Endpoint workflow capabilities

Doit exposer :

- step types
- gate variants
- config schemas
- contraintes
- labels
- icones si necessaire

## 3. Frontend = schema renderer + composeur de sections

Le frontend doit se structurer autour de :

- un client capabilities
- des hooks de chargement
- un `SchemaFormRenderer`
- des composants de section fins

### Regle simple

- **la logique metier vient du backend**
- **la logique de presentation reste dans le frontend**

Par exemple :

- backend dit : "`approval` a tel label, tel schema, tel timeout support"
- frontend dit : "j'affiche un select, un input, un helper text"

## 4. Runtime simple

Le runtime backend doit aussi rester simple :

- un handler generic
- une definition qui decrit
- une strategie qui execute

Pas de cascade de mappings :

- code -> alias -> helper -> switch -> handler

Mais plutot :

- code canonique -> definition -> execution

---

## Design cible par domaine

## A. Plateformes

### Cible

Une plateforme doit etre definie une fois avec :

- code
- labels
- aliases
- `connector_type`
- `action_platform_code`
- `runtime_config_schema`
- `action_config_schema`
- `health_check_policy`

### Travail restant

1. enrichir `PlatformDefinition`
2. sortir toute logique de mapping restant vers la definition
3. rendre `ActionWizard` pilote par `action_config_schema`
4. faire deriver les ecrans d'action de l'API de capacites

### Resultat attendu

Pour une nouvelle plateforme :

- code runtime a ecrire uniquement dans l'adapter
- aucune nouvelle constante frontend
- aucun nouveau helper de mapping

## B. Services

### Cible

Un service doit etre defini une fois avec :

- code
- label
- mode d'authentification
- operations
- schema d'entree par operation
- schema de sortie par operation
- hints UI

### Travail restant

1. enrichir `ServiceDefinition`
2. exposer les schemas via capabilities
3. rendre `ServiceCallStepConfig` completement schema-driven
4. supprimer toute logique locale de labels/operations

### Resultat attendu

Pour une nouvelle operation de service :

- pas de modification frontend si le schema est standard
- validation frontend/backend alignee

## C. Gates

### Cible

Un gate doit etre defini une fois avec :

- `gate_type`
- `condition_type`
- `display_name`
- `config_schema`
- `supports_timeout`
- `requires_manual_resolution`
- `evaluation_strategy`
- `resolution_strategy` si manuel

### Travail restant

1. rendre `GateDefinition` executable, pas seulement descriptive
2. deplacer l'evaluation dans des strategies
3. exposer les schemas de gate via capabilities
4. rendre le frontend completement derive des variants backend

### Resultat attendu

Pour un nouveau gate :

- pas de nouveau `switch` frontend
- pas de nouveau `match` central dans l'evaluateur

---

## Roadmap restante recommandee

## Phase 1 - Finir la source de verite backend

Priorite maximale.

### A faire

- supprimer `IntegrationType.choices` comme verrou metier principal
- enrichir `PlatformDefinition`, `ServiceDefinition`, `GateDefinition`
- introduire `WorkflowStepDefinition`
- faire deriver les capabilities depuis ces definitions uniquement

### Definition de done

- toute nouvelle capacite visible dans l'API sans mapping supplementaire ailleurs

## Phase 2 - Exposer des schemas complets

### A faire

- input schemas
- output schemas
- ui hints
- contraintes de validation
- defaults

### Definition de done

- le frontend peut generer un formulaire sans liste locale d'operations ou de champs

## Phase 3 - Rendre le frontend declaratif

### A faire

- creer `SchemaFormRenderer`
- remplacer les branches de `ActionWizard`
- remplacer les branches de `ServiceCallStepConfig`
- remplacer les branches de `GateStepConfig`
- nettoyer `WorkflowStepNode`

### Definition de done

- le frontend ne porte plus de verite metier sur les types supportes

## Phase 4 - Simplifier et supprimer le legacy

### A faire

- supprimer fallbacks metier locaux
- supprimer helpers de mapping devenus inutiles
- reduire les aliases residuels
- clarifier le role de `ActionPlatform`

### Definition de done

- lecture du code simple
- moins d'utilitaires "historique/compat"
- comportement comprensible en suivant definitions -> capabilities -> UI/runtime

---

## Ce qu'il faut explicitement eviter

Pour atteindre une architecture vraiment propre, il faut eviter :

- un nouveau systeme de plugins trop abstrait
- des registries imbriques difficiles a suivre
- des schemas trop generiques impossibles a lire
- des exceptions UI multipliees pour chaque plateforme
- des fallbacks frontend qui recrent la logique backend
- des aliases resolus a differents endroits

Le bon niveau de sophistication est :

- **registre simple**
- **definitions lisibles**
- **schemas explicites**
- **frontend declaratif**

---

## Regles de revue de code futures

Une PR future doit etre refusee si elle ajoute :

- une nouvelle constante frontend de type metier deja disponible via API
- un nouveau mapping plateforme/service/gate hors des definitions backend
- une nouvelle allowlist locale dupliquee
- un nouveau `if/elif/switch` central pour un type qui devrait etre declaratif

Une PR future est dans la bonne direction si :

- elle supprime un mapping
- elle remplace une branche par un schema
- elle centralise une definition
- elle rend le frontend plus passif

---

## Definition finale de succes

On pourra considerer l'architecture comme proche de la cible "state of the art" quand :

- le frontend ne porte plus de logique metier sur les types supportes
- le backend expose toutes les capacites necessaires via API
- une nouvelle operation declarative n'exige pas de modification frontend
- une nouvelle plateforme/service executable n'exige du code que dans sa logique runtime et sa definition
- le code se lit naturellement en suivant :

`definition -> capability API -> UI renderer -> payload -> runtime strategy`

Si cette chaine est simple a suivre, le systeme sera :

- extensible
- lisible
- stable
- beaucoup moins fragile qu'aujourd'hui
