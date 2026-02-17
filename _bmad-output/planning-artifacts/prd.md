---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation-skipped
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
inputDocuments:
  - design-thinking-2026-01-26.md
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  designThinking: 1
  projectDocs: 0
classification:
  projectType: internal_b2b_platform
  domain: fintech_banking
  complexity: high
  projectContext: greenfield
  regulatory: SOC1
  primaryUsers: DBA
  secondaryUsers: internal_business_clients
  buildTeam: db_automation_team
workflowType: 'prd'
lastEdited: '2026-01-28'
editHistory:
  - date: '2026-01-28'
    changes: 'Ajout editeurs visuels dynamiques pour parametres et regles impact (FR1, Journey 4)'
---

# Product Requirements Document - test

**Author:** Cyrille
**Date:** 2026-01-27

## Executive Summary

Internal Developer Platform (IDP) specialisee operations base de donnees pour une entreprise bancaire. Le portail centralise l'execution, le suivi et l'audit de toutes les operations DB (Oracle en premier, puis SQL Server, DB2, CosmosDB) a travers un Software Catalog d'actions, des Golden Paths guides, et une facade API event-driven vers les plateformes d'execution existantes (AAP, GitHub Actions, Azure DevOps, Terraform).

**Proposition de valeur :** Transformer les DBA d'executants de taches routinieres en consultants experts, tout en ouvrant le self-service DB aux clients business internes — avec tracabilite SOC1 complete et zero credential stocke dans le portail.

**Utilisateurs cibles :** DBA (primaires), clients business internes (secondaires), DBOPS (administrateurs), specialiste securite (audit).

**Contexte :** Greenfield, infrastructure on-prem ou Azure, equipe interne d'automatisation DB.

## Success Criteria

### User Success

**DBA (utilisateur primaire) :**
- Le DBA consacre la majorite de son temps au conseil expert (design, performance, architecture) plutot qu'aux taches routinieres — objectif : inversion du ratio actuel
- Le DBA trouve et execute une action via le portail sans documentation ni formation prealable
- Le DBA suit l'avancement d'une execution en temps reel sans assistance
- Les logs remontes sont suffisamment clairs pour diagnostiquer un probleme sans quitter le portail
- Le DBA ne navigue plus entre multiples plateformes (AAP, GitHub Actions, Azure DevOps, Terraform) pour les actions disponibles dans le catalogue

**Client Business (utilisateur secondaire, post-MVP) :**
- Le client business decouvre les actions disponibles en self-service sans solliciter un DBA
- Le client business execute une action deleguee de bout en bout via un Golden Path sans intermediaire humain
- Le client business suit l'avancement de sa demande en temps reel (fin de l'experience "boite noire")

### Business Success

- **70% des demandes routinieres** traitees en self-service sans intervention DBA (cible Iteration 1)
- Reduction mesurable du volume de tickets JIRA Service Desk pour les actions automatisees
- Satisfaction DBA avec le portail **>77%** (amelioration par rapport au sondage actuel)
- Capacite a absorber la croissance des clients business sans recrutement proportionnel de DBA
- Adoption croissante du portail mois apres mois (actions executees via portail vs outils natifs)

### Technical Success

- Connectivite facade API → plateformes d'execution etablie dans le contexte reseau bancaire
- 100% des actions du catalogue executees avec succes via le portail (3/3 au POC)
- Statut d'execution en temps reel sans refresh manuel
- Architecture event-driven : zero credential des plateformes stocke dans le portail
- Tracabilite et auditabilite de chaque action executee (objectif progressif vers conformite SOC1)
- Gestion d'erreur coherente quelle que soit la plateforme sous-jacente

### Measurable Outcomes

| Metrique | POC | Iteration 1 | Vision |
|----------|-----|-------------|--------|
| Actions dans le catalogue | 3 (Oracle) | 10-15 (Oracle) | Multi-moteur complet |
| Demandes routinieres en self-service | Validation technique | 70% | ~100% |
| Intervention DBA | Toujours requise | Conseil uniquement pour la majorite | Conseil uniquement |
| Satisfaction DBA | Baseline testeurs | >77% | A definir |
| Tracabilite SOC1 | Non requis | Partielle | Complete |
| Autoremediation | Hors scope | Assistee (proposition d'actions correctives) | Autonome (faible risque) |

## Product Scope

Le produit evolue en trois phases, de la validation technique (POC) a la plateforme complete. Le detail complet des feature sets, des journeys supportes par phase, et de la strategie de mitigation des risques se trouve dans la section [Project Scoping & Phased Development](#project-scoping--phased-development).

| Phase | Perimetre cle | Utilisateurs |
|-------|---------------|-------------|
| **MVP (POC)** | 3 actions Oracle, interface admin DBOPS, facade API event-driven, Vault, ServiceNow, suivi temps reel | DBA (5-7 testeurs) + DBOPS |
| **Growth (Iterations 1-2)** | 10-15 Golden Paths, RBAC complet, vue Business, audit, multi-moteur, autoremediation assistee | + Clients Business + Securite |
| **Vision (Iteration 3+)** | IA conversationnelle, autoremediation autonome, multi-moteur complet, tracabilite SOC1 complete | Tous profils |

Les criteres de succes mesurables par phase sont definis dans la section [Measurable Outcomes](#measurable-outcomes) ci-dessus.

## User Journeys

Les cinq journeys suivants illustrent comment chaque profil utilisateur interagit avec le portail. Ils ont directement alimente les exigences fonctionnelles et le cadrage du MVP.

### Journey 1 : Marc, DBA Applicatif — "Enfin du conseil"

**Scene d'ouverture :** Marc arrive le matin. Avant le portail, sa boite mail est pleine de tickets JIRA : "creer une PDB pour le projet Alpha", "patcher la base de staging Beta". Il sait que ca va lui prendre la matinee. Pendant ce temps, un client attend depuis 3 jours un avis d'expert sur le design de son schema pour un nouveau service critique.

**Action montante :** Avec le portail IDP, Marc ouvre le dashboard. Il voit que 4 demandes routinieres ont ete executees en self-service pendant la nuit par les clients business eux-memes. Les logs sont propres, les statuts verts. Aucune intervention requise.

**Climax :** Marc passe sa matinee entiere avec le client qui attendait. Il analyse le schema, identifie un probleme de performance potentiel, recommande un partitionnement. Le client repart avec un design solide.

**Resolution :** En fin de journee, Marc consulte les scorecards : 12 actions executees via le portail, zero incident. Il a passe 80% de son temps en conseil expert. C'est pour ca qu'il est DBA.

### Journey 2 : Sophie, DBA Infrastructure — "Le diagnostic en temps reel"

**Scene d'ouverture :** Sophie recoit une alerte : un patching automatise sur une base de production Oracle s'est arrete a 60%. Avant le portail, elle devait se connecter a AAP, chercher le job, lire les logs bruts, puis basculer sur un terminal pour diagnostiquer.

**Action montante :** Sophie ouvre le portail IDP, retrouve l'execution en un clic. Le statut affiche "En erreur — etape 3/5". Les logs remontes indiquent clairement : espace disque insuffisant sur le tablespace temporaire.

**Climax :** Le portail lui propose une action corrective (autoremediation assistee) : "Etendre le tablespace temporaire de 5 Go". Sophie evalue l'impact (indicateur vert — faible risque), valide, et relance le patching. Tout depuis le portail, sans changer d'outil.

**Resolution :** Le patching se termine avec succes. L'historique complet est trace : erreur initiale, action corrective, reprise, succes final. Sophie n'a ouvert qu'un seul outil. L'audit SOC1 aura toutes les preuves.

### Journey 3 : Fatima, Client Business — "Je n'attends plus"

**Scene d'ouverture :** Fatima, chef de projet sur une application bancaire, a besoin d'une nouvelle base de donnees pour son environnement de dev. Avant, elle soumettait un ticket JIRA et attendait. Parfois 2 jours. Sans savoir ou ca en etait.

**Action montante :** Fatima ouvre le portail IDP. Elle decouvre le catalogue et trouve le Golden Path "Creer une BD/PDB". La fiche lui explique en langage clair ce que fait l'action, les parametres a fournir, et l'indicateur d'impact (vert — environnement de dev, risque faible).

**Climax :** Fatima remplit le formulaire, clique sur "Executer". Elle voit le statut passer en temps reel : soumis → en cours → termine. Sa PDB est creee en quelques minutes.

**Resolution :** Fatima peut avancer sur son projet immediatement. Plus de ticket, plus d'attente, plus de "boite noire". Et si elle a besoin d'un conseil sur le design de son schema, le portail lui propose un lien "Demander un conseil DBA".

### Journey 4 : Karim, DBOPS — "Le catalogue vivant"

**Scene d'ouverture :** Karim est responsable de l'ajout d'une nouvelle action au catalogue : "Migration de schema Oracle". Il a le playbook Ansible fonctionnel, les parametres sont valides, les tests sont passes.

**Action montante :** Karim accede a l'interface d'administration du Software Catalog. Il cree une nouvelle entite action : nom, description, moteur (Oracle), plateforme d'execution (AAP), parametres via l'editeur visuel dynamique (ajouter/supprimer avec nom, type, requis, defaut, description), regles d'impact via l'editeur visuel (criteres par environnement), et regles RBAC (DBA uniquement pour la production, self-service pour les environnements non-prod).

**Climax :** La documentation est auto-generee par IA a partir du readme du playbook. Karim la revise, ajuste l'indicateur d'impact, et publie l'action. Elle apparait instantanement dans le catalogue pour les DBA autorises.

**Resolution :** Les DBA peuvent decouvrir et utiliser la nouvelle action immediatement. Karim n'a pas eu a former personne — le Golden Path guide l'utilisateur. Il passe a l'automatisation suivante.

### Journey 5 : Nadia, Specialiste Securite — "L'audit sans friction"

**Scene d'ouverture :** Nadia prepare l'audit SOC1 annuel. Elle doit prouver que chaque action executee sur les bases de donnees de production est tracable, autorisee, et conforme aux politiques de controle.

**Action montante :** Nadia accede au portail IDP avec son profil auditeur. Elle consulte l'historique des executions filtre par environnement "production" sur les 12 derniers mois. Chaque entree montre : qui a execute, quoi, quand, avec quels parametres, quel resultat, et quelle regle RBAC l'a autorise.

**Climax :** Nadia genere un rapport d'audit complet exportable. Elle verifie que chaque action production a ete validee par un DBA autorise (workflow d'approbation), que les actions a haut risque ont eu une approbation explicite, et que les logs d'erreur ont des traces de remediation.

**Resolution :** L'audit se deroule sans friction. Les preuves sont completes, structurees, et immediatement disponibles. Plus de collecte manuelle d'evidence a travers 4 plateformes differentes.

### Journey Requirements Summary

| Journey | Capabilities revelees |
|---------|----------------------|
| **Marc (DBA Applicatif)** | Dashboard d'activite, statuts d'execution self-service, scorecards, liberation du temps DBA vers le conseil |
| **Sophie (DBA Infra)** | Suivi d'execution temps reel, logs exploitables, autoremediation assistee, indicateur d'impact, tracabilite complete |
| **Fatima (Client Business)** | Catalogue decouvert, Golden Paths self-service, formulaire dynamique, suivi temps reel, lien vers conseil DBA |
| **Karim (DBOPS)** | Interface d'administration du catalogue, creation d'entites action, regles RBAC, doc auto-generee IA, publication instantanee |
| **Nadia (Securite)** | Historique d'execution filtrable, profil auditeur, rapport d'audit exportable, preuves RBAC et approbation, traces de remediation |

**Capabilities transverses :**
- Software Catalog avec CRUD pour DBOPS
- RBAC granulaire (par action, profil, environnement)
- Facade API event-driven + callbacks statut
- Moteur d'autoremediation (assistee puis autonome)
- Module d'audit et export de rapports
- Documentation auto-generee par IA
- Systeme de notification et suivi temps reel

## Domain-Specific Requirements

Le contexte bancaire impose des exigences specifiques en matiere de conformite, de gestion du changement, de securite et de continuite. Ces exigences conditionnent les choix architecturaux et les contraintes fonctionnelles du portail.

### Conformite & Audit (SOC1)

- **Generation automatique d'evidences** : chaque action executee via le portail produit automatiquement les preuves d'audit requises (qui, quoi, quand, parametres, resultat, autorisation RBAC)
- **Evidence de patching** : le portail genere un rapport tracable pour chaque action de patching (base cible, version source, version cible, resultat, timestamp)
- **Justification des comptes a privileges** : toute creation de compte a haut privilege est tracee avec justification, approbateur, et contexte d'execution
- **Immutabilite des logs** : les traces d'execution ne peuvent etre ni modifiees ni supprimees — historique complet et inalterable
- **Rapport d'audit exportable** : generation de rapports filtres par periode, environnement, type d'action, pour le specialiste securite

### Gestion du Changement

- **Changements pre-approuves uniquement** : toutes les actions du catalogue portent un statut pre-approuve. L'ouverture de changement ServiceNow est automatique, integree a l'execution, et non-bloquante (pas d'attente d'approbation)
- **Conditionnel par environnement** : chaque action definit si un changement est requis selon l'environnement cible (ex: pas de changement en dev/cert, changement en prod)
- **ServiceNow comme connecteur generique** : l'ouverture de changement est un step d'execution parmi d'autres, au meme titre que les appels vers AAP, Azure DevOps, Jira ou tout autre systeme integre

### Securite & Credentials

- **Integration HashiCorp Vault** : les secrets (credentials des plateformes d'execution, acces aux bases cibles) sont recuperes dynamiquement depuis Vault au moment de l'execution. Zero secret stocke dans le portail ou dans le catalogue
- **Architecture event-driven** : le portail emet des evenements (webhooks) consommes par les plateformes. Communication sortante uniquement
- **RBAC granulaire** : chaque action definit qui peut executer (par profil, environnement, moteur) et qui doit approuver

### Haute Disponibilite & Continuite

- **Le portail est un systeme critique** : si le portail est indisponible, les operations DB sont bloquees pour les utilisateurs standards
- **Exigence de haute disponibilite** : SLA a definir (cible a discuter avec l'architecture — ex: 99.9%)
- **"Break the glass"** : certains administrateurs (DBOPS) conservent un acces direct aux plateformes d'infrastructure pour les situations d'urgence. Cet acces est l'exception, pas la norme
- **Pas de mode de repli dans le portail** : le break-the-glass est externe au portail, gere par les acces d'urgence aux plateformes

### Risques Specifiques au Domaine

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Action executee sans autorisation adequate | Non-conformite SOC1, risque operationnel | RBAC granulaire + workflows d'approbation + logs immutables |
| Perte de tracabilite d'une action production | Echec d'audit SOC1 | Generation automatique d'evidence, logs immutables, pas d'acces direct |
| Indisponibilite du portail | Blocage des operations DB | Haute disponibilite + break-the-glass pour urgences |
| Secrets exposes | Compromission des plateformes | Integration Vault, zero secret stocke, communication sortante uniquement |
| Action executee sans changement requis | Non-conformite au processus de changement | Configuration obligatoire du changement par environnement dans la definition de l'action, validation a l'execution |

## Platform-Specific Requirements

Les exigences suivantes decoulent du type de plateforme (IDP interne B2B) et definissent l'architecture d'integration, le modele de deploiement et la matrice RBAC.

### Project-Type Overview

Plateforme interne B2B (Internal Developer Platform) specialisee operations base de donnees, deployee en infrastructure controlee (on-prem ou Azure, pas de SaaS-only), avec authentification SSO, integrations API vers toutes les plateformes d'execution et les systemes ITSM de l'entreprise.

### Technical Architecture Considerations

**Deploiement :**
- **Production** : haute disponibilite, gere tous les environnements DB (dev, staging, prod des clients)
- **Developpement** : meme stack, disponibilite reduite, acces restreint aux administrateurs (DBOPS) pour le developpement du portail
- **Hebergement** : on-prem ou Azure — pas de SaaS-only. Decision a prendre lors de l'evaluation technologique

**Authentification :**
- SSO d'entreprise (protocole a confirmer — SAML, OIDC, ou autre selon le standard interne)
- Groupe AD global pour l'acces au portail (ex: GRP-IDP-PORTAL)
- Profiles dynamiques mappes sur des groupes AD (ex: GRP-IDP-ASSURANCE → Profile Assurance)
- Un utilisateur peut appartenir a plusieurs groupes AD → permissions cumulees (union)
- RBAC granulaire : profile → actions (liste ou pattern/tags) + targets (liste ou pattern) + environnements

### Integration Architecture

Toutes les integrations sont en **API REST**.

| Systeme | Direction | Usage |
|---------|-----------|-------|
| **Ansible Automation Platform (AAP)** | Sortante (webhook/API) | Execution d'actions (playbooks Ansible) |
| **GitHub Actions** | Sortante (API) | Execution d'actions (workflows CI/CD) |
| **Azure DevOps** | Sortante (API) | Execution d'actions (pipelines) |
| **Terraform** | Sortante (API) | Execution d'actions (infrastructure as code) |
| **HashiCorp Vault** | Sortante (API) | Recuperation dynamique des secrets au moment de l'execution |
| **ServiceNow** | Sortante (API) | Connecteur generique pour ouverture automatique de changements pre-approuves (etape d'une action, conditionnel par environnement) |
| **Inventaire interne** | Entrante (API) | Source de verite pour les metadonnees des bases de donnees (plus riche que la CMDB ServiceNow) |
| **ServiceNow CMDB** | A evaluer | Source secondaire d'inventaire — determiner si le portail doit lire et/ou mettre a jour la CMDB apres certaines actions |
| **SSO d'entreprise** | Entrante | Authentification et identification des profils utilisateurs |

**Pattern d'integration :**
- Sortante uniquement vers les plateformes d'execution (event-driven, zero credential stocke)
- Callback asynchrone des plateformes vers le portail pour la remontee de statut
- Lecture de l'inventaire interne pour alimenter le Software Catalog et les formulaires dynamiques (ex: liste des bases disponibles, environnements)

### RBAC Model

**Architecture RBAC dynamique basee sur les groupes AD:**

```
User (SAML) → Groupes AD → Profile(s) → Permissions
                              │
                              ├── Actions: liste explicite OU pattern (tags)
                              ├── Targets: liste explicite OU pattern (valide contre inventaire)
                              └── Environments: [DEV, STAGING, PROD] ou [*]
```

**Profiles geres dynamiquement par DBOPS** (pas de liste fixe). Exemples:

| Profile | Groupe AD | Actions | Targets | Envs | Admin | Audit |
|---------|-----------|---------|---------|------|-------|-------|
| **DBOPS** | GRP-IDP-DBOPS | `*` | `*` | `*` | Oui | Complet |
| **DBA Applicatif** | GRP-IDP-DBA-APP | `tag:*` | `*` | `*` | Non | Propres exec |
| **DBA Infrastructure** | GRP-IDP-DBA-INFRA | `tag:*` | `*` | `*` | Non | Propres exec |
| **Specialiste Securite** | GRP-IDP-SECURITE | aucune | aucun | - | Non | Complet + export |
| **Assurance** | GRP-IDP-ASSURANCE | `tag:oracle`, `tag:provisioning` | `assurance-*` | DEV, STAGING | Non | Propres exec |
| **Finance** | GRP-IDP-FINANCE | Action #5, #12 | `finance-*`, `shared-*` | DEV | Non | Propres exec |

**Multi-profiles:** Un utilisateur dans plusieurs groupes AD cumule les permissions (union).

**Gestion:** Interface admin du portail + import/export YAML (as code).

### Implementation Considerations

- **Inventaire interne comme source de verite** : le Software Catalog du portail s'alimente depuis l'inventaire interne (API) pour les metadonnees des bases de donnees. L'inventaire interne est plus riche que la CMDB ServiceNow
- **ServiceNow CMDB** : a evaluer si le portail doit mettre a jour la CMDB apres certaines actions (ex: creation de BD) pour maintenir la coherence avec l'ecosysteme ITSM
- **Connecteurs generiques** : toutes les integrations (AAP, ServiceNow, Azure DevOps, Jira, GitHub Actions, Terraform) sont des connecteurs standardises appelables depuis les steps d'une action. ServiceNow n'a pas de traitement special — c'est un connecteur comme les autres
- **ServiceNow Change Management** : l'ouverture de changement pre-approuve est un step d'execution conditionnel par environnement (ex: requis en prod, pas requis en dev/cert). Pas de changement CAB bloquant
- **Scalabilite** : le portail production gere tous les environnements DB — le volume d'actions augmentera significativement avec l'ouverture aux clients business

## Project Scoping & Phased Development

Cette section detaille la strategie de livraison progressive : le perimetre exact du MVP, les feature sets par phase, et les risques identifies avec leurs mitigations.

### MVP Strategy & Philosophy

**Approche MVP :** Platform MVP — valider le cycle de vie complet d'une action, de sa creation par DBOPS a son execution par un DBA, en passant par toutes les integrations critiques.

**Philosophie :** Le POC ne teste pas juste "est-ce que ca execute ?". Il teste "est-ce que la plateforme tient debout de bout en bout ?". Si le cycle complet fonctionne pour 3 actions, il fonctionnera pour 30.

**Utilisateurs MVP :** DBA (5-7 testeurs) + DBOPS (administrateurs du catalogue)

### MVP Feature Set (Phase 1 — POC)

**Journeys supportes :**
- **Karim (DBOPS)** — Creation et publication d'actions dans le catalogue (cycle admin complet)
- **Sophie (DBA Infra)** — Execution d'une action et suivi temps reel avec logs
- **Marc (DBA Applicatif)** — Decouverte et execution d'actions via le catalogue

**Must-Have Capabilities :**

| Capability | Justification |
|-----------|---------------|
| Software Catalog avec 3 actions Oracle | Coeur du produit — sans catalogue, pas de plateforme |
| Interface d'administration DBOPS (CRUD actions) | Valide le cycle de vie complet, pas juste l'execution |
| Fiche descriptive par action + indicateur d'impact | Repond au probleme central d'opacite identifie en empathie |
| Formulaire dynamique d'execution | Experience self-service — le DBA ne navigue plus entre outils |
| Facade API event-driven vers plateformes d'execution | Architecture fondatrice — si ca ne marche pas, rien ne marche |
| Integration HashiCorp Vault | Zero credential stocke — exigence de securite non-negociable |
| Integration ServiceNow (ouverture de changement comme etape) | Faible effort, haute valeur — deja operationnel cote equipe |
| Suivi d'execution temps reel + logs | Repond a l'experience "boite noire" identifiee en empathie |
| RBAC de base (DBA / DBOPS) | Deux profils distincts avec droits differents des le POC |

**Explicitement hors MVP :**
- Vue Client Business (Fatima) — arrive en Phase 2
- Audit et rapports (Nadia) — arrive en Phase 2
- Scorecards et dashboards — Phase 2
- Multi-moteur (SQL Server, DB2) — Phase 2
- Autoremediation — Phase 2 (architecture prevue pour)
- Documentation auto-generee par IA — Phase 2
- Workflows d'approbation configurables — Phase 2
- IA conversationnelle — Phase 3

### Post-MVP Features

**Phase 2 — Growth (Iterations 1-2) :**
- Elargissement a 10-15 Golden Paths Oracle
- RBAC granulaire complet (par action, profil, environnement)
- Workflows d'approbation configurables (auto si faible risque, validation DBA si production)
- Vue "Business" simplifiee pour les clients internes (ouverture pilote Fatima)
- Module d'audit et rapports exportables (ouverture Nadia)
- Multi-moteur : SQL Server, DB2
- Scorecards et dashboards (taux de succes, temps moyen)
- Documentation auto-generee par IA
- Autoremediation assistee (proposition d'actions correctives)
- Tracabilite SOC1 partielle
- Historique des executions par client et par base

**Phase 3 — Vision (Iteration 3+) :**
- Interface IA conversationnelle pour decouverte d'actions
- Routage intelligent self-service vs conseil expert DBA
- Autoremediation autonome pour les cas a faible risque
- Integration CosmosDB (multi-moteur complet)
- Tracabilite SOC1 complete
- Canal "Demander un conseil DBA" integre
- Metriques d'usage avancees et enrichissement continu par les logs

### Risk Mitigation Strategy

| Type de risque | Risque | Probabilite | Mitigation |
|----------------|--------|-------------|------------|
| **Technique** | Connectivite facade API → plateformes bloquee par le reseau bancaire | Connue | Break-the-glass pour les cas bloquants. Le POC valide ou invalide ce risque |
| **Technique** | Latence callbacks statut inacceptable | Moyenne | Test de charge sur les 3 actions POC. Mecanisme de polling en fallback |
| **Adoption** | DBA resistant au changement d'outil | Moyenne | Mix enthousiastes/sceptiques dans les testeurs. Mesurer satisfaction vs outils actuels (>77%) |
| **Scope** | MVP plus riche que prevu (admin + ServiceNow + Vault) | Faible | Perimetre strict a 3 actions. Pas de feature creep au-dela du cycle de vie complet |
| **Operationnel** | Portail critique indisponible | Faible (si HA) | Architecture HA des le design. Break-the-glass pour urgences |

## Functional Requirements

Les 45 exigences fonctionnelles ci-dessous decoulent des user journeys, des exigences domaine, et du cadrage par phase. Chaque FR est attribuable a un ou plusieurs journeys. Les FR sont regroupees par capacite.

### 1. Gestion du Software Catalog

- **FR1:** DBOPS peut creer une action dans le Software Catalog avec ses metadonnees (nom, description, moteur, plateforme d'execution, niveau d'impact) et configurer via des editeurs visuels dynamiques (ajouter/supprimer):
  - **Parametres**: nom, type (string, number, boolean, etc.), requis (oui/non), valeur par defaut, description
  - **Regles d'impact**: criteres d'evaluation du niveau de risque par environnement
- **FR2:** DBOPS peut definir les etapes d'execution d'une action, chaque etape pouvant appeler un connecteur generique (AAP, ServiceNow, Azure DevOps, Jira, GitHub Actions, Terraform, etc.) avec des conditions selon l'environnement cible
- **FR3:** [DEPLACE vers FR25a-d] Les regles RBAC sont gerees au niveau des profiles, pas des actions individuelles
- **FR4:** DBOPS peut configurer si un changement ServiceNow (pre-approuve) est requis pour chaque environnement cible
- **FR5:** DBOPS peut publier une action pour la rendre disponible dans le catalogue
- **FR6:** DBOPS peut modifier ou desactiver une action existante
- **FR7:** Le systeme peut auto-generer la documentation d'une action a partir du readme de l'automatisation via IA

### 2. Decouverte et Navigation du Catalogue

- **FR8:** DBA peut parcourir l'integralite du catalogue d'actions disponibles
- **FR9:** DBA peut consulter la fiche descriptive d'une action (nom, description, indicateur d'impact, moteur, parametres attendus)
- **FR10:** Client Business peut parcourir une vue simplifiee des actions deleguees a son profil
- **FR11:** Tout utilisateur peut rechercher et filtrer les actions par tags, moteur, environnement, niveau d'impact ou mot-cle
- **FR11a:** Tout utilisateur peut basculer entre une vue en cartes (cards) et une vue en liste pour le catalogue
- **FR11b:** Tout utilisateur peut marquer des actions en favoris et les retrouver dans une section "Mes actions"
- **FR11c:** DBOPS peut assigner plusieurs tags flexibles a une action (ex: RAC, DATAGUARD, Provisioning) — les tags sont geres dynamiquement, pas des categories fixes
- **FR12:** Tout utilisateur peut acceder a la documentation contextuelle d'une action

### 3. Execution d'Actions

- **FR13:** DBA peut executer une action via un formulaire dynamique adapte aux parametres de l'action selectionnee
- **FR14:** Client Business peut executer les actions deleguees via un Golden Path guide
- **FR15:** Le systeme valide les parametres saisis avant de declencher l'execution
- **FR16:** Le systeme ouvre automatiquement un changement ServiceNow pre-approuve (non-bloquant) lorsqu'un step de type ServiceNow est configure et que l'environnement cible le requiert
- **FR17:** Le systeme recupere les secrets necessaires depuis HashiCorp Vault au moment de l'execution
- **FR18:** Le systeme route l'execution vers la bonne plateforme (AAP, GitHub Actions, Azure DevOps, Terraform) via une facade API event-driven

### 4. Suivi d'Execution

- **FR19:** Tout utilisateur peut suivre le statut d'une execution en temps reel (soumis, en cours, termine, erreur)
- **FR20:** Tout utilisateur peut consulter les logs remontes par la plateforme d'execution
- **FR21:** DBA peut acceder aux logs techniques detailles d'une execution
- **FR22:** Tout utilisateur peut consulter l'historique de ses propres executions
- **FR23:** Le systeme recoit les callbacks de statut asynchrones des plateformes d'execution

### 5. Controle d'Acces et Securite

- **FR24:** Les utilisateurs s'authentifient via le SSO d'entreprise et doivent appartenir au groupe AD global du portail
- **FR25:** Le systeme resout les profiles de l'utilisateur a partir de ses groupes AD (un groupe AD = un profile, multi-profiles supportes)
- **FR25a:** DBOPS peut creer et gerer des profiles dynamiques avec mapping vers un groupe AD
- **FR25b:** DBOPS peut definir les permissions d'un profile : actions (liste explicite ou pattern/tags), targets (liste explicite ou pattern), environnements autorises
- **FR25c:** Les permissions d'un utilisateur multi-profiles sont cumulees (union des permissions de chaque profile)
- **FR25d:** DBOPS peut importer/exporter la configuration des profiles en YAML (as code)
- **FR26:** Le systeme applique les regles RBAC : l'utilisateur ne voit que les actions autorisees par ses profiles, et ne peut executer que sur les targets et environnements autorises
- **FR26a:** Les targets autorises sont valides contre l'inventaire interne au moment de l'execution
- **FR27:** Le systeme impose un workflow d'approbation pour les actions qui le requierent (approbation DBA pour la production)
- **FR28:** DBOPS peut configurer les regles d'approbation par action et par environnement
- **FR29:** Le systeme ne stocke aucun credential — tous les secrets sont recuperes depuis Vault a l'execution

### 6. Audit et Conformite

- **FR30:** Le systeme genere une trace d'audit immutable pour chaque execution (qui, quoi, quand, parametres, resultat, autorisation RBAC)
- **FR31:** Le systeme genere une evidence specifique pour les actions de patching (version source, version cible, resultat)
- **FR32:** Le systeme trace toute creation de compte a privileges avec justification et approbateur
- **FR33:** Specialiste Securite peut consulter l'historique d'execution filtre par environnement, periode et type d'action
- **FR34:** Specialiste Securite peut exporter des rapports d'audit
- **FR35:** Le systeme enregistre l'evidence de gestion du changement (ID changement ServiceNow, timestamp, environnement cible)

### 7. Autoremediation

- **FR36:** Le systeme peut detecter un echec d'execution et proposer des actions correctives depuis le catalogue
- **FR37:** DBA peut evaluer et declencher une action corrective depuis la proposition de remediation
- **FR38:** Le systeme peut executer automatiquement des actions correctives pour les scenarios a faible risque

### 8. Analytics et Reporting

- **FR39:** DBA peut consulter les scorecards par action (taux de succes, temps moyen d'execution, incidents)
- **FR40:** DBOPS peut consulter des dashboards globaux (actions par moteur, par equipe, tendances d'adoption)
- **FR41:** DBA peut consulter un tableau de bord d'activite recente et de statuts d'execution

### 9. Donnees et Inventaire

- **FR42:** Le systeme se synchronise avec l'inventaire interne (API) pour alimenter les metadonnees des bases de donnees dans le catalogue
- **FR43:** Le systeme alimente les formulaires dynamiques avec les donnees de l'inventaire (liste des bases, environnements disponibles)

### 10. Communication et IA

- **FR44:** Client Business peut demander une consultation expert DBA depuis le portail
- **FR45:** Tout utilisateur peut decouvrir des actions via une interface IA conversationnelle en langage naturel

## Non-Functional Requirements

Les 25 NFR couvrent performance, securite, fiabilite, integration et scalabilite. Elles sont calibrees par phase (MVP → Growth → Vision).

### Performance

- **NFR1:** Les pages du portail (catalogue, formulaire, suivi) se chargent en moins de 2 secondes
- **NFR2:** La soumission d'une execution via le formulaire obtient une confirmation (statut "soumis") en moins de 3 secondes
- **NFR3:** La mise a jour du statut d'execution en temps reel se rafraichit avec un delai maximum de 5 secondes apres reception du callback
- **NFR4:** La recherche et le filtrage dans le catalogue retournent des resultats en moins de 1 seconde
- **NFR5:** Le portail supporte 10 utilisateurs simultanes au MVP (extensible a 50+ en Phase 2, 200+ en Phase 3 avec les clients business)

### Securite

- **NFR6:** Toutes les communications entre le portail et les systemes integres sont chiffrees en transit (TLS 1.2+)
- **NFR7:** Aucun secret (credential, token, cle) n'est stocke dans le portail ou le catalogue — recuperation exclusive depuis Vault a l'execution
- **NFR8:** Les logs d'audit sont immutables — aucune modification ni suppression possible apres ecriture
- **NFR9:** Les sessions utilisateur expirent apres une periode d'inactivite conforme aux standards internes de la banque
- **NFR10:** Toute tentative d'acces non autorise (RBAC) est journalisee et refusee
- **NFR11:** Le portail ne conserve aucune donnee sensible des bases de donnees gerees — seules les metadonnees de l'inventaire sont stockees

### Fiabilite & Disponibilite

- **NFR12:** Le portail de production a un SLA de disponibilite de 99.9% (hors fenetres de maintenance planifiees)
- **NFR13:** En cas de defaillance d'une plateforme d'execution, le portail remonte une erreur explicite sans planter ni bloquer les autres executions
- **NFR14:** Les executions en cours ne sont pas perdues en cas de redemarrage du portail — reprise sur l'etat du dernier callback recu
- **NFR15:** Le mecanisme de break-the-glass (acces direct DBOPS aux plateformes) est operationnel independamment de la disponibilite du portail
- **NFR16:** Le portail de developpement n'a pas de SLA de disponibilite — acces restreint aux administrateurs DBOPS

### Integration

- **NFR17:** Le portail gere les erreurs de connectivite vers chaque plateforme d'execution de maniere independante — la defaillance d'une plateforme n'impacte pas les autres
- **NFR18:** Les callbacks asynchrones des plateformes sont idempotents — un callback recu en doublon ne corrompt pas l'etat de l'execution
- **NFR19:** L'integration ServiceNow tolere un delai de reponse de l'API ServiceNow jusqu'a 30 secondes sans echouer l'action
- **NFR20:** La synchronisation avec l'inventaire interne se fait de maniere periodique ou on-demand sans impacter la performance du portail
- **NFR21:** En cas d'indisponibilite de Vault, l'execution est refusee avec un message explicite (pas de fallback sur des credentials stockes)

### Scalabilite

- **NFR22:** L'architecture supporte l'ajout de nouvelles plateformes d'execution sans modification du coeur du portail (pattern plugin/adapter)
- **NFR23:** Le catalogue supporte un minimum de 100 actions sans degradation de performance de navigation, recherche ou filtrage par tags
- **NFR24:** L'historique d'execution supporte un volume de 10 000+ executions par an sans degradation des requetes d'audit
- **NFR25:** L'ajout de nouveaux moteurs de base de donnees (SQL Server, DB2, CosmosDB) ne necessite pas de refonte architecturale
