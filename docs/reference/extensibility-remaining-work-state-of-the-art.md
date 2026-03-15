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

Avant de lister le travail restant, il faut noter que plusieurs points importants ont
deja ete **realises** sur `develop` :

- validation ecriture integration basee sur le **catalogue actif**
- **PlatformDefinition**, **ServiceDefinition**, **GateDefinition**
- **workflow_step_registry**
- **API de capacites** backend
- enrichissement des services avec :
  - `input_schema`
  - `output_schema`
  - `ui_hints`
- **SchemaFormRenderer** cote frontend
- rendu declaratif de :
  - la configuration plateforme des actions
  - certaines variantes de gate
  - certaines operations de service via `ui_hints`
- suppression des anciens helpers frontend dominants :
  - `serviceCallConstants.ts`
  - `integrationHelpers.ts`

Le travail restant est donc plus cible qu'avant.

## A. Hardcoding restant cote backend

### 1. Resolution manuelle des gates encore couplee a `approval_granted`

Probleme :

- l'evaluation auto des gates est maintenant basee sur des strategies
- mais la resolution manuelle reste encore principalement couplee au gate d'approbation historique

Exemples :

- `idp-portal/django_backend/executions/views/approval_views.py`
- references a `approval_granted` dans les services/outbox/runtime workflow

Impact :

- un futur gate manuel risque encore de demander des ajouts specifiques hors de sa definition

Travail restant :

- faire converger la resolution manuelle vers une logique plus generique
- permettre qu'un gate manuel declare sa `resolution_strategy` ou son mode de resolution
- reduire le couplage direct a `approval_granted`

### 2. Dispatch runtime des step types encore ferme

Probleme :

- le backend a maintenant un registre de definitions de step type pour les capabilities
- mais le moteur d'execution reste encore base sur un `match step_type`

Exemple :

- `idp-portal/django_backend/executions/container_workflow_runtime.py`

Impact :

- un nouveau step type ne deviendra pas executable simplement en declarant sa definition

Travail restant :

- introduire un registre de handlers runtime pour les step types
- aligner definitions de capabilities et execution runtime
- faire converger capabilities -> validation -> execution

### 3. Le schema existe, mais son usage n'est pas encore complet partout

Probleme :

- le backend expose deja :
  - `action_config_schema`
  - `runtime_config_schema`
  - `health_check_policy`
  - `input_schema`
  - `output_schema`
  - `ui_hints`

mais tous ces schemas ne sont pas encore exploites de maniere uniforme dans tous les flux.

Exemples :

- `idp-portal/django_backend/capabilities/views.py`
- `idp-portal/frontend/src/components/admin/step-config/ServiceCallStepConfig.tsx`

Travail restant :

- utiliser `input_schema` de service pour aller au-dela du simple key/value editor
- standardiser la validation frontend a partir des schemas exposes
- etendre les `ui_hints` quand un renderer specialise est vraiment necessaire

### 4. Heritage legacy `ActionPlatform` et mappings runtime encore presents

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
- reduire les conversions legacy au strict minimum

---

## B. Hardcoding restant cote frontend

### 1. ActionWizard est largement declaratif, mais garde une exception AAP

Probleme :

- la configuration plateforme est maintenant pilotee par `action_config_schema`
- mais le connecteur AAP garde un renderer UX et une serialisation runtime specifiques

Exemples :

- `idp-portal/frontend/src/components/admin/ActionWizard.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep2Automatisme.tsx`

Travail restant :

- garder l'exception AAP uniquement si elle est vraiment necessaire
- sinon converger vers un chemin de rendu/serialization plus uniforme

### 2. GateStepConfig consomme maintenant le schema, mais pas encore via un renderer totalement generique

Probleme :

- le composant s'appuie maintenant sur `config_schema`
- mais il reste encore un rendu conditionnel "manuel" de certains champs

Exemple :

- `idp-portal/frontend/src/components/admin/step-config/GateStepConfig.tsx`

Travail restant :

- brancher ce composant sur un renderer de schema plus generique
- supprimer la logique conditionnelle restante quand elle n'apporte pas de valeur UX

### 3. Le workflow UI garde encore des types, titres et labels locaux

Probleme :

- `WorkflowStepNode` consomme maintenant les capacites pour gates et services
- mais l'ecosysteme workflow garde encore plusieurs listes/types/titres locaux

Exemples :

- `WorkflowStepNode.tsx`
- `StepConfigPanel.tsx`
- `ActionPalette.tsx`
- `workflowStepLabels.ts`
- `workflowValidation.ts`
- `types/api/catalog.ts`

Travail restant :

- faire deriver autant que possible :
  - les labels
  - les titres
  - la palette
  - les contraintes de validation
  depuis les capabilities backend

### 4. Validation workflow encore basee sur un `switch(stepType)`

Probleme :

- le frontend valide encore les step types connus via un `switch`

Exemple :

- `idp-portal/frontend/src/utils/workflowValidation.ts`

Impact :

- ajouter un nouveau step type demandera encore une modification frontend explicite

Travail restant :

- faire consommer les contraintes de validation depuis l'API de capabilities
- conserver uniquement les validations purement UI/graph si elles ne sont pas metier

### 5. Le renderer de schema existe, mais n'est pas encore utilise partout

Probleme :

- `SchemaFormRenderer` existe maintenant
- mais tous les flux n'en profitent pas encore

Exemples :

- `idp-portal/frontend/src/components/shared/SchemaFormRenderer.tsx`
- `WizardStep2Automatisme.tsx`
- `ServiceCallStepConfig.tsx`
- `GateStepConfig.tsx`

Travail restant :

- reutiliser davantage le renderer generique la ou les schemas le permettent
- reserver les renderers specifiques aux cas UX justifies

### 6. Palette et panneau de configuration encore fondes sur des listes connues

Probleme :

- la palette des special steps et les titres du panneau restent encore des constantes frontend

Exemples :

- `idp-portal/frontend/src/components/admin/ActionPalette.tsx`
- `idp-portal/frontend/src/components/admin/StepConfigPanel.tsx`

Travail restant :

- faire deriver la palette depuis `workflow_step_registry`
- faire deriver les titres du panneau depuis les labels exposes par le backend
- supprimer les constantes UI qui font doublon avec les capabilities

---

## Roadmap cible - atteindre 9/10 par composant

Cette section traduit le travail restant en **objectif de maturite**.

### Echelle de lecture

- **6/10** : extensible mais encore fragile ou trop manuel
- **7/10** : bonne base, quelques duplications/cas speciaux
- **8/10** : architecture solide, reste surtout du nettoyage cible
- **9/10** : ajout localise, comprehensible, peu de couplage, faible risque de derive

L'objectif ici n'est pas un 10/10 theorique.

Le **9/10** vise une architecture :

- simple
- lisible
- robuste
- vraiment exploitable au quotidien

### 1. Plateformes

**Etat estime actuel : 8/10**

Points forts deja acquis :

- `PlatformDefinition`
- `PlatformRegistry`
- aliases centralises
- `action_config_schema`
- `runtime_config_schema`
- `health_check_policy`
- `ActionWizard` largement base sur les capabilities backend

Ce qui manque pour 9/10 :

1. **reduire l'exception AAP au strict minimum**
   - conserver uniquement le renderer specialise si la recherche de templates AAP reste vraiment un besoin UX unique
   - sinon aligner AAP sur le meme chemin declaratif que les autres plateformes

2. **simplifier le legacy `ActionPlatform`**
   - reduire les conversions residuelles entre :
     - code integration
     - `connector_type`
     - code action
   - idealement, garder un seul code metier et deriver le reste au plus pres de la persistence/runtime

3. **faire converger execution runtime et definitions**
   - utiliser davantage `PlatformDefinition` pour eviter tout mapping ou regle residuelle hors definition

4. **completer l'usage des schemas**
   - exploiter davantage `runtime_config_schema` et `health_check_policy`
   - clarifier ce qui est purement descriptif vs effectivement applique

**Definition pratique du 9/10 pour les plateformes**

- ajouter une nouvelle plateforme = ecrire l'adapter + declarer la definition
- pas de nouvelle constante frontend
- pas de nouveau helper de mapping
- pas de nouveau branchement hors exception runtime reellement justifiee

### 2. Services

**Etat estime actuel : 8/10**

Points forts deja acquis :

- `ServiceDefinition`
- operations derivees du backend
- `input_schema` / `output_schema` / `ui_hints`
- plus de duplication majeure frontend/backend des operations

Ce qui manque pour 9/10 :

1. **rendre le formulaire d'operation vraiment schema-driven**
   - aujourd'hui, le flux service_call reste encore proche d'un key/value editor generaliste
   - il faut rendre les champs depuis `input_schema` quand le schema le permet

2. **faire converger validation frontend/backend**
   - le frontend doit exploiter plus directement les schemas exposes
   - les erreurs de saisie doivent etre visibles avant le submit, pas seulement au runtime

3. **mieux utiliser `ui_hints`**
   - normaliser les hints utiles
   - limiter les renderers specifiques a des cas bien identifies

4. **clarifier les services non operationnels**
   - exemple : services presents pour health check/consommation interne mais sans `service_call`
   - leur role doit etre explicite dans les capabilities

**Definition pratique du 9/10 pour les services**

- ajouter un nouveau service = ecrire le client + declarer les operations
- si les operations ont un schema standard, aucune modification frontend supplementaire
- les labels, champs et validations viennent de l'API backend

### 3. Gates

**Etat estime actuel : 6.5/10**

Points forts deja acquis :

- `GateDefinition`
- `GateRegistry`
- strategies d'evaluation
- variants exposes via capabilities
- `GateStepConfig` deja partiellement derive de `config_schema`

Ce qui manque pour 9/10 :

1. **generaliser la resolution manuelle**
   - supprimer le couplage dur a `approval_granted`
   - permettre a un gate manuel de declarer sa resolution de maniere plus generique

2. **mieux utiliser `config_schema` pour le rendu**
   - brancher davantage `GateStepConfig` sur un renderer de schema
   - ne garder du code conditionnel que si la valeur UX est evidente

3. **reduire les references legacy**
   - approval flow, outbox, events et runtime contiennent encore des references explicites au gate historique

4. **stabiliser l'extension des gates manuels**
   - un nouveau gate manuel ne doit pas exiger de chasse au tresor dans les views/services/tasks

**Definition pratique du 9/10 pour les gates**

- ajouter un nouveau gate auto-evalue = definition + strategie
- ajouter un nouveau gate manuel = definition + mecanisme de resolution dedie
- pas de nouveau `if gate_type == ...` disperse dans plusieurs couches

### 4. Workflow UI / extensibilite des step types

**Etat estime actuel : 6.5/10**

C'est aujourd'hui la zone la plus importante a faire progresser.

Points forts deja acquis :

- capabilities workflow exposees par le backend
- labels/variants de gates deja relies aux capabilities dans plusieurs composants
- `SchemaFormRenderer` disponible

Ce qui manque pour 9/10 :

1. **palette backend-driven**
   - `ActionPalette` ne doit plus embarquer une liste locale des special steps

2. **titres/backend labels unifies**
   - `StepConfigPanel`
   - `workflowStepLabels`
   - `WorkflowStepNode`
   - ces composants doivent consommer le meme vocabulaire expose par le backend

3. **validation backend-driven**
   - `workflowValidation.ts` ne doit plus etre un `switch(stepType)` metier
   - il doit lire les contraintes de validation depuis les capabilities

4. **typing plus souple cote frontend**
   - eviter que l'ajout d'un nouveau step type demande une cascade de modifications TypeScript purement descriptives
   - conserver les unions strictes uniquement quand elles apportent un vrai gain de surete

5. **aligner capabilities et execution**
   - un step type expose au frontend doit correspondre a un handler runtime connu
   - idealement via un registre de handlers backend

**Definition pratique du 9/10 pour le workflow UI**

- ajouter un nouveau step type standard = declaration backend + handler runtime + eventuel schema
- la palette, le panneau, les labels et la validation frontend s'adaptent sans duplication locale majeure

### 5. Backend orchestration / execution runtime

**Etat estime actuel : 7/10**

Points forts deja acquis :

- definitions backend riches
- capabilities bien exposees
- evaluation gate plus modulaire

Ce qui manque pour 9/10 :

1. **remplacer le `match step_type` central**
   - introduire un registre de handlers runtime pour les step types

2. **aligner definitions et execution**
   - ce qui est declarable dans capabilities doit correspondre a un chemin runtime clair

3. **reduire le legacy d'approbation**
   - limiter la logique speciale historique au strict necessaire

**Definition pratique du 9/10 pour le runtime**

- definition -> validation -> execution suit la meme structure mentale
- on peut suivre un step type sans changer de paradigme entre capabilities et runtime

### 6. Objectif global

Pour atteindre une note globale proche de **9/10** sur l'ensemble du sujet, l'ordre recommande est :

1. **runtime workflow handler registry**
2. **manual gate resolution generic path**
3. **workflow UI derive des capabilities**
4. **service forms plus schema-driven**
5. **reduction finale des compatibilites legacy plateforme/action**

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

---

## Epic de mise en œuvre

Epic 83 : [Extensibilite state-of-the-art — achevement architecture data-driven](../backend/epic-83-extensibilite-state-of-the-art.md)
