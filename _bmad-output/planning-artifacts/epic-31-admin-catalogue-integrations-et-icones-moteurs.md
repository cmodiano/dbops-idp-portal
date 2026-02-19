# Epic 31 : Admin catalogue — Intégrations alignées et icônes moteurs (février 2026)

**En tant que** DBOPS,  
**je veux** que le formulaire d’action ne propose que les intégrations réellement configurées, que la suppression d’une intégration désactive les actions qui en dépendent, et que je puisse définir les icônes des technologies/moteurs de base de données,  
**afin de** éviter des actions non exécutables, garder un catalogue cohérent et personnaliser l’affichage des moteurs.

---

## Contexte

- Aujourd’hui le champ « Plateforme d’exécution » dans le formulaire action est alimenté par REF_PLATFORMS (liste fixe) alors qu’à l’exécution c’est l’**intégration** (instance configurée) qui est utilisée.
- Un utilisateur peut choisir une plateforme sans intégration configurée → action non exécutable.
- La suppression d’une intégration utilisée par des actions ne désactive pas ces actions.
- Les icônes des moteurs (Oracle, SQL Server, DB2, etc.) sont codées en dur côté frontend ; il n’existe pas de moyen d’en définir ou modifier en admin.

---

## Stories

### Story 31.1 : Formulaire action — liste = intégrations configurées, libellé « Intégration »

**En tant que** DBOPS,  
**je veux** que lors de la création ou modification d’une action, le champ (aujourd’hui « Plateforme d’exécution ») affiche **uniquement les intégrations définies dans Admin > Intégrations** (rôle plateforme) et soit libellé **« Intégration »**,  
**afin de** ne plus pouvoir associer une action à une plateforme non configurée et d’avoir un vocabulaire cohérent avec le reste de l’admin.

**Acceptance Criteria:**

- **Given** le formulaire d’action (ActionForm, ActionWizard) est ouvert en création ou édition
- **When** l’utilisateur consulte le champ aujourd’hui nommé « Plateforme d’exécution »
- **Then** le libellé du champ est **« Intégration »** (ou « Intégration d’exécution ») et le placeholder « Sélectionnez une intégration »
- **And** la liste déroulante est alimentée par les **intégrations** retournées par l’API admin (ex. GET /admin/integrations/), filtrées aux intégrations dont le type est une **plateforme** (role=platform), et non par REF_PLATFORMS
- **And** chaque option affiche un libellé explicite (ex. nom de l’intégration + type) et la valeur envoyée au backend est l’**integration_id** ; le champ **platform** est dérivé côté frontend (ou backend) à partir du type de l’intégration sélectionnée pour respecter la validation existante
- **And** si aucune intégration plateforme n’est configurée, la liste est vide et un message explicite invite à en créer une dans Admin > Intégrations
- **And** les libellés « Plateforme d’exécution » / « plateforme » sont remplacés par « Intégration » / « intégration » dans ce formulaire (et cohérents dans les messages de validation affichés)

**Fichiers / zones :** `ActionForm.tsx`, `ActionWizard.tsx`, hook ou service pour charger les intégrations (filtrées role=platform), référence à `usePlatforms` remplacée par chargement des intégrations ; types API si besoin.

---

### Story 31.2 : Suppression d’intégration — désactiver les actions qui l’utilisent

**En tant que** DBOPS,  
**je veux** que lorsqu’une intégration est supprimée, toutes les actions qui référencent cette intégration passent en statut **désactivé** (disabled),  
**afin de** ne pas laisser des actions « orphelines » encore publiées alors qu’elles ne peuvent plus s’exécuter.

**Acceptance Criteria:**

- **Given** une intégration I est utilisée par au moins une action (action.integration_id = I)
- **When** un DBOPS supprime l’intégration I (DELETE /admin/integrations/{id} ou équivalent)
- **Then** avant ou lors de la suppression, toutes les actions dont `integration_id` = I passent en statut **disabled**
- **And** une entrée d’audit (ou log) indique que les actions ont été désactivées suite à la suppression de l’intégration (optionnel : message explicite côté UI après suppression)
- **And** si aucune action n’utilise l’intégration, la suppression se comporte comme aujourd’hui
- **And** des tests (backend et/ou E2E) valident le scénario : suppression intégration utilisée → actions concernées en disabled

**Fichiers / zones :** backend (service ou signal de suppression d’intégration, mise à jour du statut des actions), éventuellement message côté frontend après suppression.

---

### Story 31.3 : Définir les icônes des technologies / moteurs de base de données

**En tant que** DBOPS,  
**je veux** pouvoir **définir l’icône** associée à chaque moteur de base de données (technologie) dans l’admin,  
**afin de** personnaliser l’affichage dans le catalogue, les exécutions et les rapports sans modifier le code (ex. logo Oracle, SQL Server, DB2, ou icône générique).

**Acceptance Criteria:**

- **Given** le référentiel des moteurs (REF_ENGINES ou équivalent) est administrable
- **When** un DBOPS édite un moteur (ou une entrée « moteur » dans l’admin)
- **Then** il peut renseigner une **icône** pour ce moteur : soit une URL d’image (SVG/PNG), soit un identifiant d’icône prédéfini (à définir selon le design : liste d’icônes Ant Design, ou URLs stockées en base)
- **And** l’API reference/engines (ou équivalent) expose ce champ (ex. `icon_url` ou `icon`) pour chaque moteur
- **And** le frontend utilise cette valeur pour afficher l’icône du moteur partout où le moteur est affiché (catalogue, tableau exécutions, cartes, etc.) avec un fallback propre si l’icône est absente ou invalide
- **And** la rétrocompatibilité est assurée : moteurs sans icône définie conservent un affichage par défaut (ex. icône générique ou mapping actuel codé en dur comme fallback)
- **And** des tests valident la persistance du champ et l’exposition API ; au moins un test frontend vérifie l’affichage à partir de la valeur renvoyée par l’API

**Fichiers / zones :** modèle REF_ENGINES (ou table dédiée) + migration pour le champ icône ; API reference/engines ; admin backend/frontend pour éditer l’icône ; frontend (iconHelpers, executionRenderers, ActionCard, etc.) pour consommer l’icône avec fallback.

---

### Story 31.4 : Refonte UX — Panneau « Changement ServiceNow par environnement » (gates vs changement, Code modèle unique)

**En tant que** DBOPS,  
**je veux** que le panneau de configuration par environnement soit plus clair et utilisable : **séparer** les gates (Approbation, Plage maintenance) de la partie « Changement ServiceNow », et **fusionner** « Code modèle » et « Template ID » en un seul champ (ils désignent la même chose),  
**afin de** ne plus mélanger des concepts différents dans une seule grille et éviter la redondance de saisie.

**Acceptance Criteria:**

- **Given** le formulaire d’action (ActionForm ou ActionWizard) affiche la section « Changement ServiceNow par environnement »
- **When** le DBOPS consulte cette section
- **Then** elle est structurée en **deux blocs distincts** :
  - **Bloc 1 — Conditions d’exécution par environnement (gates)** : uniquement « Autorisé », « Plage maintenance », « Approbation » (switches par environnement), avec un titre/sous-titre explicite (ex. « Gates — conditions d’exécution par environnement »)
  - **Bloc 2 — Changement ServiceNow par environnement** : « Changement requis », et **un seul champ** pour l’identifiant du modèle/template (ex. libellé « Code modèle (template) » ou « Modèle / Template ID »), éventuellement « Change type » si conservé
- **And** il n’y a plus deux colonnes séparées « Code modèle » et « Template ID » : un seul champ dont la valeur est envoyée au backend (mapping côté API sur `change_model_code` et/ou `template_id` selon le contrat existant)
- **And** la densité visuelle est réduite (espacement, regroupement) pour améliorer la lisibilité
- **And** les tests existants sont adaptés ; aucun changement de contrat API backend n’est requis si on envoie la valeur unique vers les champs existants

**Fichiers / zones :** `ChangeTypeConfig.tsx`, éventuellement libellés dans `ActionForm.tsx` / `ActionWizard.tsx` ; tests `ChangeTypeConfig.test.tsx`, `ActionForm.test.tsx`, `ActionWizard.test.tsx`.

---

### Story 31.5 : AAP — Sélection du template par liste ou par nom (résolution dynamique de l’ID)

**En tant que** DBOPS,  
**je veux** ne plus saisir manuellement le `workflow_job_template_id` ou `job_template_id` pour les étapes AAP : soit **choisir le template dans une liste** (chargée depuis l’intégration AAP), soit **saisir le nom du template** et laisser le système **résoudre l’ID dynamiquement**,  
**afin de** éviter les erreurs de saisie d’ID et rendre la configuration des actions AAP plus intuitive.

**Acceptance Criteria:**

- **Given** une étape d’exécution cible AAP (job template ou workflow job template) et une intégration AAP configurée
- **When** le DBOPS configure l’étape (dans StepsEditor ou équivalent)
- **Then** au lieu d’un simple champ texte pour l’ID, l’interface propose **au moins une** des options suivantes (à valider en design) :
  - **Option A — Liste déroulante** : les job templates (et/ou workflow job templates) sont chargés depuis l’API AAP (via le backend, en s’appuyant sur l’intégration sélectionnée pour l’action). L’utilisateur sélectionne un template dans la liste ; l’ID est envoyé au backend.
  - **Option B — Saisie du nom avec résolution** : l’utilisateur saisit le **nom** du template ; le backend ou le frontend appelle l’API AAP (ou un proxy backend) pour résoudre le nom en ID et enregistre l’ID. En cas d’ambiguïté (plusieurs templates avec le même nom), afficher un choix ou une erreur explicite.
- **And** la liste (si Option A) est filtrée selon le type d’étape (job vs workflow job) et limitée à l’intégration AAP liée à l’action
- **And** un fallback reste possible : si l’API AAP est indisponible ou si la liste ne peut pas être chargée, permettre temporairement la saisie manuelle de l’ID avec un avertissement
- **And** la rétrocompatibilité est assurée : les actions existantes avec un ID déjà renseigné continuent de fonctionner ; l’affichage peut montrer le nom du template si disponible (résolution ID → nom pour l’affichage)
- **And** des tests (et/ou documentation) couvrent le chargement de la liste, la résolution nom → ID, et le fallback saisie manuelle

**Fichiers / zones :** Backend : endpoint ou service pour lister les templates AAP (proxy vers l’API AAP de l’intégration) et optionnellement résolution nom → ID ; Frontend : `StepsEditor.tsx` (ou composant dédié pour la config connecteur AAP), appels API pour liste / résolution ; types API catalog (connector_config).

---

### Story 31.6 : Configuration des gates — étape dédiée, choix du service par gate, et création du changement ServiceNow avant exécution

**En tant que** DBOPS,  
**je veux** une **étape de configuration dédiée aux gates** où je définis quels gates s’appliquent à l’action et, pour chaque gate qui appelle un service externe, **quelle intégration** utiliser (ex. si j’ai plusieurs intégrations ServiceNow, choisir laquelle la gate « changement ServiceNow » doit appeler) ; et que le **changement ServiceNow soit créé avant l’exécution** lorsque « changement requis » est activé pour l’environnement, avec **annulation de l’exécution** si la création échoue,  
**afin de** maîtriser quelle instance de service chaque gate utilise et garantir qu’une exécution ne part pas sans changement créé quand c’est requis.

**Acceptance Criteria:**

**Partie A — Configuration des gates (étape dédiée)**

- **Given** le formulaire d’action (création ou édition)
- **When** le DBOPS accède à la configuration des gates (nouvelle section ou étape dédiée, distincte des étapes d’exécution et du panneau « Changement ServiceNow par environnement »)
- **Then** il peut définir **quels gates** s’appliquent à l’action (ex. : plage de maintenance, approbation, changement ServiceNow, etc.) — liste des types de gates supportés, avec possibilité d’activer/désactiver et de configurer les paramètres (timeout, on_timeout, etc.)
- **And** pour chaque gate qui s’appuie sur un **service externe** (ex. gate « changement ServiceNow »), il doit pouvoir **sélectionner l’intégration** à utiliser : une liste déroulante des intégrations du type correspondant (ex. toutes les intégrations ServiceNow configurées dans Admin > Intégrations). S’il existe plusieurs intégrations ServiceNow, le DBOPS choisit explicitement laquelle cette gate appellera.
- **And** cette configuration est persistée (modèle ou structure existante étendue : ex. `gate_conditions` avec champ optionnel `integration_id` par condition, ou bloc `gate_config` au niveau action avec mapping type de gate → integration_id). L’API et le backend utilisent cette configuration à l’exécution pour appeler le bon service.
- **And** la validation refuse une configuration invalide (ex. gate ServiceNow sans intégration sélectionnée si des intégrations ServiceNow existent). Rétrocompatibilité : actions sans intégration de gate définie conservent un comportement par défaut documenté (ex. première intégration du type, ou échec explicite).

**Partie B — Création du changement ServiceNow avant exécution**

- **Given** une action a « changement requis » activé pour un environnement (change_type_config) et une intégration ServiceNow configurée pour la gate « changement ServiceNow » (ou pour l’action, selon le design retenu)
- **When** un utilisateur lance une exécution pour cet environnement
- **Then** **avant** de passer l’exécution en RUNNING (ou avant de lancer l’étape plateforme), le backend appelle le service ServiceNow (via l’intégration choisie dans la config des gates) pour **créer le changement** (create_change avec change_model_code / paramètres issus de change_type_config pour cet environnement)
- **And** en cas de **succès** : l’ID du changement créé est stocké sur l’exécution (Execution.servicenow_change_id) et l’exécution peut poursuivre (RUNNING puis étapes normales)
- **And** en cas d’**échec** de la création du changement (API ServiceNow indisponible, erreur métier, etc.) : l’exécution **n’est pas lancée** (ou est immédiatement mise en échec) : statut FAILED ou équivalent, message d’erreur explicite (ex. « Échec de la création du changement ServiceNow : … »). Aucune étape plateforme n’est déclenchée tant que le changement n’est pas créé.
- **And** ServiceNowService.create_change() est implémenté (plus de NotImplementedError) et s’appuie sur la config de l’intégration ServiceNow sélectionnée pour la gate (URL, auth, etc.). Les paramètres du changement (modèle, type, etc.) proviennent de change_type_config pour l’environnement cible.
- **And** des tests (backend et/ou E2E) valident : création du changement avant exécution, persistance de servicenow_change_id, et annulation / échec de l’exécution si create_change échoue.

**Fichiers / zones :** Backend : modèle/schéma de la config des gates (catalog, execution_steps ou action) avec integration_id par gate ; exécution (ExecutionService ou workflow) : appel create_change avant RUNNING, gestion échec ; ServiceNowService : implémentation de create_change ; intégrations (résolution de l’intégration ServiceNow depuis la config gate). Frontend : nouvelle section/étape « Configuration des gates » dans le formulaire action (liste des gates, sélection de l’intégration par gate pour les gates service). Validators : extension de validate_gate_conditions si nécessaire. Documentation : glossaire ou doc d’architecture mise à jour (gates, service par gate).

---

### Story 31.7 : Aide contextuelle (tooltip + popover Markdown) alimentée par le backend

**En tant que** DBOPS,  
**je veux** une **aide contextuelle** dans les fenêtres de configuration : un **tooltip** pour un contexte court au survol, et un **popover** avec doc **Markdown** pour les sections plus complexes au clic, le tout alimenté par des **fichiers MD stockés côté backend** (maintenables dans git),  
**afin de** comprendre rapidement une section (tooltip) ou consulter une doc détaillée (popover) sans quitter l'écran.

**Acceptance Criteria:**

- **Backend — Stockage et API**  
  - Répertoire dédié (ex. `docs/help/`) avec fichiers Markdown par topic, frontmatter YAML `short` optionnel pour le texte court.  
  - **GET /api/v1/help/<topic_id>/** retourne `{ "topic_id", "short", "markdown" }` ; 404 si topic inconnu. Mapping topic_id → fichier restreint (pas de path traversal). Endpoint protégé (auth). Réf. : `docs/help-contextual-design.md`.

- **Frontend — Composant et affichage**  
  - Composant réutilisable (ex. `SectionHelp`) avec `topicId` et `mode` (tooltip | popover | both). Tooltip au survol (short) ; Popover au clic avec rendu Markdown (`react-markdown`). Service `getHelpContent(topicId)` + cache session. Accessibilité : aria-label, Popover fermable Escape/clavier.

- **Intégration**  
  - Au moins 2–3 sections pilotes (ex. Intégration, Changement ServiceNow, Gates) avec icône d'aide et fichiers MD + mapping backend.

**Fichiers / zones :** Backend : app/module help, vue GET help/<topic_id>/, lecture `docs/help/`, frontmatter ; urls. Frontend : service getHelpContent, composant SectionHelp (tooltip + popover Markdown), intégration ActionForm/ActionWizard. Doc : `docs/help-contextual-design.md`.

---

### Story 31.8 : Service de notification multi-destinations (email, Teams, page)

**En tant que** DBOPS / utilisateur du portail,  
**je veux** un **service de notification** au même niveau que les services Jira, Splunk, Vault, ServiceNow, exposant plusieurs **types de destinations** (courriel, Teams, page individuel, page DBA), **paramétrable au niveau de l’action** et avec une **option à l’exécution** pour le page individuel,  
**afin de** livrer les outputs de jobs par courriel au demandeur, alerter l’équipe (Teams) en cas d’erreur, et paginer (support ou individu ou DBA) pour les jobs critiques en production.

**Acceptance Criteria:**

- **Given** le package `services/` (Vault, Splunk, Jira, ServiceNow)
- **When** on introduit un nouveau service de notification
- **Then** un **NotificationService** (ou équivalent) est ajouté dans `services/` avec une interface unifiée permettant d’envoyer une notification vers une **destination** donnée
- **And** les types de destinations supportés sont : **email** (livraison d’output au demandeur), **Teams** (message canal équipe, ex. erreur), **page individuel** (API interne, identité + nom du demandeur), **page DBA** (API interne fournie pour paginer le DBA on-call)
- **And** la configuration des notifications (quels canaux, dans quelles conditions) est **paramétrable au niveau de l’action** (ex. champs ou section dédiée dans le catalogue d’actions)
- **And** le **page individuel** est une **option à l’exécution** : la personne qui lance l’action peut choisir « être pagé en cas d’échec » ; son **nom et identité** sont transmis à l’API interne de page
- **And** le déclenchement d’un **page** (individuel, support ou DBA) n’a lieu **que si le target d’exécution est la production** et que le niveau est **critique** (ou selon règle métier définie)
- **And** le service s’intègre à la factory existante (`get_service_client("notification", ...)` ou instanciation dédiée) et est documenté dans `services/README.md`
- **And** des tests (unitaires et/ou d’intégration) valident l’envoi vers chaque type de destination (avec mocks pour les APIs internes et Teams/email)

**Fichiers / zones :** `services/notification_service.py` (ou `notification/` avec backends par type), configuration d’action (catalog) pour les options de notification, exécution (passage option « page moi » + target + niveau critique), `services/README.md`, `__init__.py` / factory si applicable.

---

## FRs / NFRs couverts

- **FR1, FR6 :** Création/édition d’actions avec une liste d’intégrations cohérente et désactivation prévisible lors de la suppression d’une intégration.
- **FR18 :** Routage vers la bonne plateforme via une intégration réellement configurée.
- **NFR22 :** Alignement avec le modèle intégrations/plateformes sans casser le pattern existant.

---

## Notes

- Story 31.1 et 31.2 découlent des échanges produit (liste = intégrations configurées, renommer plateforme → intégration, désactivation à la suppression).
- Story 31.3 correspond au souhait de pouvoir définir les icônes des technologies/moteurs (REF_ENGINES) côté admin.
- Story 31.4 : refonte UX du panneau « Changement ServiceNow par environnement » (séparation gates / changement, fusion Code modèle et Template ID) — pas de changement de code demandé, uniquement rédaction de la story.
- Story 31.5 : amélioration UX pour la configuration AAP — sélection du template par liste (depuis l’API AAP) ou par nom avec résolution dynamique de l’ID, au lieu de la saisie manuelle de l’ID.
- Story 31.6 : configuration des gates (étape dédiée : quels gates, quel service/intégration par gate quand service externe ; ex. plusieurs ServiceNow → choix de laquelle la gate appelle) ; création du changement ServiceNow avant exécution avec annulation si échec.
- Story 31.7 : aide contextuelle (tooltip court + popover Markdown) alimentée par le backend (fichiers MD dans docs/help/, API GET /api/v1/help/<topic_id>/), composant SectionHelp réutilisable.
- Story 31.8 : service de notification multi-destinations (email, Teams, page individuel, page DBA), au même niveau que Jira/Splunk/Vault/ServiceNow ; config au niveau action, option page à l’exécution, page uniquement en production et niveau critique.
