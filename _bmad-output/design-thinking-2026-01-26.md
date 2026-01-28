# Design Thinking Session: IDP Self-Service pour l'Automatisation Base de Donnees (inspire Port.io)

**Date:** 2026-01-26
**Facilitator:** Cyrille
**Design Challenge:** Concevoir un Internal Developer Platform (IDP) specialise base de donnees, inspire du modele Port.io, permettant aux DBA et clients business de decouvrir et executer des actions d'automatisation (Oracle, SQL Server, DB2, CosmosDB) via des Golden Paths self-service.

---

## 🎯 Design Challenge

**Contexte :** Au sein d'une grande entreprise bancaire, l'equipe d'automatisation des processus base de donnees gere des actions couvrant Oracle, SQL Server, DB2 (et bientot CosmosDB). Aujourd'hui, ces actions sont dispersees sur de multiples plateformes (GitHub Actions, Ansible Automation Platform, Azure DevOps, Terraform), ce qui cree de la complexite pour les consommateurs.

**Populations cibles :**
- **DBA (~50 utilisateurs)** : acces a l'ensemble des actions, y compris les operations techniques avancees
- **Clients business (potentiellement des centaines)** : acces a un sous-ensemble d'actions deleguees, avec une experience simplifiee

**Probleme :** La fragmentation des outils rend difficile la decouverte, la consommation et le suivi des actions disponibles. Les clients business n'ont pas de point d'entree simple et uniforme. Les DBA naviguent entre plusieurs plateformes.

**Enonce du defi :** Comment concevoir un Internal Developer Platform (IDP) specialise base de donnees qui permette a tout utilisateur autorise - qu'il soit DBA ou client business - de decouvrir, demander et suivre des actions d'automatisation via des Golden Paths self-service, de facon simple, fiable et securisee, en s'inspirant du modele Port.io ?

**Criteres de succes :**
- Simplicite de consommation pour le client final (Golden Paths intuitifs)
- Ouverture en self-service avec RBAC granulaire (autonomie controlee)
- Fiabilite de l'execution via architecture event-driven
- Experience uniforme quel que soit le moteur de base de donnees ou l'outil d'execution
- Reutilisation maximale des competences et outils existants au sein de l'equipe

---

## 👥 EMPATHIZE: Understanding Users

### User Insights

**Source :** Sondage interne + entretiens avec le responsable produit (connaissance terrain directe)

**Clients Business :**
- Ne savent pas quelles actions d'automatisation existent ni lesquelles sont disponibles en self-service
- Passent par JIRA Service Desk avec des demandes en langage naturel ("je voudrais faire X")
- N'ont aucune visibilite sur ce qui se passe en arriere-plan apres soumission du ticket
- Experience de "boite noire" : soumission → attente → resultat (ou pas)
- Dependance totale envers les DBA pour toute operation base de donnees

**DBA (~50 utilisateurs) - Deux profils distincts :**

*DBA Applicatifs* - Experts-conseils apportant une reelle valeur ajoutee :
- Expertise en design de bases de donnees et optimisation de performance
- Role de conseil aupres des clients sur les choix d'architecture et de conception
- Leur temps est mieux investi dans l'accompagnement expert que dans l'execution de taches routinieres

*DBA Infrastructure* - Role de conseil et d'execution :
- Conseillent les clients sur les solutions d'infrastructure adaptees a leurs besoins
- Executent et supervisent les operations d'infrastructure base de donnees

*Constats communs (sondage - 77% de satisfaction globale) :*
- Frustrations identifiees :
  - Documentation incomplete ou absente sur les playbooks/automatisations
  - Manque de clarte sur l'impact reel d'une automatisation sur le systeme avant execution
  - Interfaces des outils actuels jugees peu claires par certains
  - Manque de reactivite du support
- Temps consacre a des taches routinieres qui pourrait etre reinvesti dans le conseil et l'expertise
- Naviguent entre multiples plateformes (GitHub Actions, AAP, Azure DevOps, Terraform)

### Key Observations

1. **L'opacite est le probleme central** - A chaque niveau, l'information manque : le client ne sait pas ce qui existe, le DBA ne sait pas toujours ce que fait un playbook ni son impact, et personne n'a une vue unifiee du catalogue d'actions disponibles.

2. **Le flux actuel ne distingue pas routine et expertise** - Tout passe par un ticket JIRA Service Desk traite par un DBA, qu'il s'agisse d'une action routiniere automatisable ou d'un besoin reel de conseil expert (design, performance, architecture). Les DBA sont sollicites indifferemment, ce qui dilue leur capacite d'accompagnement a haute valeur.

3. **Les automatisations existent mais sont invisibles** - Le patrimoine d'automatisation est reel (77% de satisfaction), mais il est enfoui dans des outils techniques (AAP, GitHub Actions, etc.) inaccessibles aux clients business.

4. **La fragmentation des outils cree de la confusion** - Meme les DBA, utilisateurs techniques, trouvent les interfaces peu claires et peinent a naviguer entre les plateformes.

5. **Le passage a l'echelle est bloque** - Avec ~50 DBA dont le temps est partage entre taches routinieres et conseil expert, ouvrir le service a des centaines de clients business est impossible sans self-service. Le self-service doit liberer les DBA pour leur mission a haute valeur : conseil en design, performance et architecture.

6. **Le risque d'execution est mal gere** - Le manque de clarte sur l'impact des automatisations sur les systemes en arriere-plan est a la fois un probleme d'experience utilisateur et un risque operationnel dans un contexte bancaire.

### Empathy Map Summary

#### Client Business

| Dimension | Observations |
|-----------|-------------|
| **Dit** | "Je voudrais faire X" / "C'est quand que c'est fait ?" / "Je ne sais pas ce qui est possible" |
| **Pense** | "Je ne comprends pas pourquoi ca prend si longtemps" / "Il doit bien y avoir un moyen plus simple" |
| **Fait** | Cree un ticket JIRA → Attend → Relance si pas de reponse → Recoit le resultat sans comprendre ce qui s'est passe |
| **Ressent** | Dependance, frustration face a l'attente, sentiment d'etre deconnecte du processus |

#### DBA (Applicatif & Infrastructure)

| Dimension | Observations |
|-----------|-------------|
| **Dit** | "La doc est incomplete" / "Je ne suis pas sur de l'impact de ce playbook" / "L'interface n'est pas claire" / "Je devrais passer plus de temps a conseiller les clients sur le design et la performance" |
| **Pense** | "Est-ce que cette automatisation fait bien ce qu'il faut ?" / "Ce ticket est routinier, ca devrait etre en self-service" / "Le client aurait besoin d'un vrai accompagnement sur son architecture, mais je suis pris par les demandes operationnelles" |
| **Fait** | Recoit un ticket → Evalue s'il s'agit d'une tache routiniere ou d'un besoin de conseil → Cherche le bon outil/playbook → Execute → Conseille le client quand le temps le permet |
| **Ressent** | Satisfait de son expertise et des automatismes (77%), mais frustre de ne pas pouvoir consacrer assez de temps au conseil a haute valeur (design, performance, architecture) a cause des demandes routinieres et du manque de documentation |

---

## 🎨 DEFINE: Frame the Problem

### Point of View Statement

**POV 1 - Client Business :**
Le client business a besoin d'un moyen autonome de decouvrir et executer des actions base de donnees parce qu'aujourd'hui il depend entierement d'un ticket JIRA et n'a aucune visibilite sur ce qui est possible ni sur ce qui se passe.

**POV 2 - DBA Applicatif (PRIORITAIRE) :**
Le DBA applicatif a besoin que les taches routinieres soient deleguees en self-service parce que le temps consacre a ces demandes reduit sa capacite a exercer son expertise de conseil en design, performance et architecture.

**POV 3 - DBA Infrastructure (PRIORITAIRE) :**
Le DBA infrastructure a besoin d'une interface unifiee avec une documentation claire et une visibilite sur l'impact des automatisations parce que la fragmentation des outils et le manque de documentation creent de la confusion et du risque.

### How Might We Questions

**Liberation des DBA pour le conseil expert (POV 2) :**
- HMW1 : Comment pourrions-nous permettre aux clients d'executer les actions routinieres sans intervention DBA ?
- HMW2 : Comment pourrions-nous distinguer clairement les demandes qui necessitent un conseil expert de celles qui sont automatisables ?
- HMW3 : Comment pourrions-nous rendre le role de conseil des DBA applicatifs plus visible et accessible pour les clients ?

**Unification et clarte pour les DBA (POV 3) :**
- HMW4 : Comment pourrions-nous offrir une interface unique masquant la complexite des multiples plateformes d'execution ?
- HMW5 : Comment pourrions-nous rendre l'impact d'une automatisation explicite et comprehensible avant execution ?
- HMW6 : Comment pourrions-nous garantir une documentation fiable et a jour pour chaque action disponible ?

**Transverse :**
- HMW7 : Comment pourrions-nous creer un catalogue d'actions unifie qui serve a la fois les DBA et les clients business avec des niveaux d'acces differencies ?

### Key Insights

1. **Le probleme n'est pas l'automatisation, c'est l'accessibilite** - Les automatisations existent et satisfont 77% des DBA. Le vrai probleme est que personne ne peut les decouvrir, les comprendre et les consommer facilement.

2. **La priorite strategique est de liberer les DBA** - Resoudre d'abord pour les DBA (POV 2 & 3) est le prealable qui rendra possible l'ouverture self-service aux clients business. Sans interface unifiee et doc claire pour les DBA, on ne peut pas ouvrir aux clients business.

3. **Deux natures de demandes coexistent** - Il faut distinguer les actions routinieres (automatisables en self-service complet) des demandes necessitant un conseil expert (design, performance, architecture). Le portail doit router intelligemment.

4. **L'opacite genere du risque** - Dans un contexte bancaire, ne pas comprendre l'impact d'une automatisation avant execution est un risque operationnel. La transparence n'est pas un "nice-to-have" mais une exigence.

5. **L'abstraction de la plateforme est cle** - L'utilisateur final (DBA ou business) ne devrait pas avoir a savoir si l'action est executee par GitHub Actions, AAP, Azure DevOps ou Terraform. Le portail doit etre une facade unifiee.

**Hypotheses a valider :**
- Les DBA accepteront-ils de deleguer des actions en self-service direct ?
- Les clients business sont-ils prets a consommer des actions sans intermediaire humain ?
- La documentation peut-elle etre maintenue a jour de maniere durable ?

---

## 💡 IDEATE: Generate Solutions

### Selected Methods

- **Brainstorming structure** : Generation d'idees par axe HMW, sans filtre, pour explorer l'espace des solutions
- **SCAMPER Design** : Application de lentilles creatives aux outils existants (GitHub Actions, AAP, Azure DevOps, Terraform)
- **Analogous Inspiration** : Inspiration croisee avec des modeles existants (app stores, cloud consoles, plateformes de services internes)
- **Benchmark marche** : Analyse des solutions IDP existantes (Port.io, Backstage) et du paradigme Platform Engineering / Golden Paths pour identifier les concepts transposables

L'axe prioritaire retenu par le facilitateur est l'**Axe 2 - Interface unifiee et documentation**, identifie comme le socle necessaire avant toute ouverture self-service ou valorisation du conseil expert. L'analyse de marche a confirme cet axe et introduit le paradigme **Internal Developer Platform (IDP)** comme modele de reference.

### Generated Ideas

**Axe 1 - Self-service des actions routinieres (HMW1, HMW2) :**
1. Catalogue d'actions type "app store" avec fiche descriptive par action
2. Classification des actions : tag "self-service" vs "accompagnement expert requis"
3. Formulaire dynamique par action : parametres a remplir, execution automatique
4. Workflow d'approbation configurable selon le niveau de risque
5. Mode "dry-run" : simulation avant execution reelle
6. Assistant en langage naturel pour identifier l'action adaptee
7. Templates pre-remplies pour les cas les plus frequents

**Axe 2 - Interface unifiee et documentation (HMW4, HMW5, HMW6) - AXE PRIORITAIRE :**
8. Facade API unique orchestrant les appels vers les plateformes sous-jacentes
9. Documentation generee automatiquement par IA a partir des playbooks/workflows (deja en cours via readmes)
10. Indicateur d'impact visuel avant execution (vert/orange/rouge)
11. Tableau de bord unifie de suivi de toutes les executions en cours
12. Historique des executions par client et par base de donnees
13. Release notes automatiques a chaque ajout/modification d'action
14. Recherche unifiee a travers toutes les actions disponibles

**Axe 3 - Valorisation du conseil expert (HMW3) :**
15. Bouton "Demander un conseil DBA" integre au portail
16. Profils DBA visibles avec specialites
17. Base de connaissances alimentee par les DBA
18. Systeme de consultation planifiee avec un DBA expert
19. Recommendations contextuelles post-execution

**Axe transverse - Catalogue unifie (HMW7) :**
20. Double vue portail : vue "DBA" complete et vue "Business" simplifiee
21. Permissions granulaires par moteur, environnement et type d'action
22. Onboarding guide pour les nouveaux clients business
23. Metriques d'usage et identification des goulots

**Axe 5 - Inspiration IDP / Port.io (benchmark marche) :**
24. **Software Catalog comme source de verite unique** - chaque action, base de donnees, environnement et equipe est une entite du catalogue, interconnectee et toujours a jour
25. **Self-service actions avec RBAC granulaire** - chaque action definit qui peut l'executer (DBA only, Business autorise, approbation requise) via des regles declaratives
26. **Golden Paths** - chaque operation est un chemin pre-approuve avec guardrails integres (securite, conformite, bonnes pratiques bancaires) plutot qu'un simple bouton d'execution
27. **Workflows d'approbation automatisables** - approbation automatique si l'action est a faible risque (ex: lecture seule), manuelle si impact production, avec politiques configurables
28. **Architecture event-driven** - le portail ne stocke pas de credentials des plateformes ; il publie un evenement (type Kafka/webhook) que la plateforme cible consomme, plus securise en contexte bancaire
29. **Scorecards et dashboards** - metriques de qualite par action (taux de succes, temps moyen, incidents), par equipe et par moteur de BD
30. **Interface IA conversationnelle** - decouverte d'actions en langage naturel ("je dois creer une base Oracle 19c en dev") avec routage intelligent vers self-service ou conseil DBA

### Top Concepts

**Concept A : "Le Software Catalog - Source de Verite Unique"**
Inspire du modele Port.io, le catalogue est bien plus qu'une liste d'actions. C'est un **Software Catalog** ou chaque entite (action, base de donnees, environnement, equipe, moteur) est modelisee et interconnectee. Chaque action est un **Golden Path** : un chemin pre-approuve avec description auto-generee par IA, indicateur d'impact, guardrails de securite et conformite integres, et RBAC granulaire (qui peut executer, qui doit approuver). Le catalogue est la source de verite pour tout : decouverte, execution, suivi, metriques.

**Concept B : "La Facade d'Execution Event-Driven"**
Inspire de l'architecture Port.io, la couche d'orchestration fonctionne en mode **event-driven** : le portail publie un evenement d'execution (via webhook ou file de messages) que la plateforme cible (AAP, GitHub Actions, Terraform) consomme de maniere asynchrone. Le portail ne stocke aucun credential des plateformes d'execution - communication sortante uniquement. Workflows d'approbation automatisables : execution directe si faible risque, validation DBA requise si impact production. Suivi d'execution en temps reel, historique par client et par base de donnees, scorecards de qualite par action.

**Relation entre les concepts :** A et B forment un **Internal Developer Platform (IDP) specialise base de donnees**. A est la couche portail et catalogue, B est le moteur d'orchestration. L'ensemble s'inspire des meilleures pratiques IDP (Port.io, Platform Engineering). Le choix technologique pour l'implementation reste ouvert et fera l'objet d'une evaluation separee.

**Vision a terme :** Un portail unifie ou le client (DBA ou business) peut decouvrir des actions via recherche ou interface IA conversationnelle, les executer via des Golden Paths securises, suivre l'avancement en temps reel, et acceder au conseil expert DBA quand necessaire - le tout depuis une interface unique, independamment du moteur de BD, de la plateforme d'execution ou de la technologie sous-jacente du portail.

---

## 🛠️ PROTOTYPE: Make Ideas Tangible

### Prototype Approach

**Methode retenue :** Proof of Concept fonctionnel inspire du modele IDP Port.io

**Pourquoi cette approche :**
- Un POC fonctionnel permet de valider les concepts cles (catalogue, Golden Paths, execution event-driven) de maniere tangible
- Les 3 actions choisies (Oracle) permettent de tester le flux complet sur un perimetre maitrise
- L'architecture en couches permet de valider les interactions independamment de la technologie choisie pour chaque couche

**Architecture du prototype (inspiree Port.io) :**
```
[Utilisateur] → [Portail IDP / Catalogue / Golden Paths]
                        ↓
               [Software Catalog (source de verite)]
                        ↓
               [Facade API / Event-driven]
                        ↓
               [Plateforme d'execution (AAP / GitHub Actions / Terraform)]
                        ↓ (callback)
               [Reception statut] → [Suivi temps reel]
```

**Couches a implementer (choix technologique ouvert) :**
- **Couche portail :** Interface web pour la decouverte, l'execution et le suivi (ex: APEX, Backstage, React, Retool, Port.io...)
- **Couche API / orchestration :** Facade REST event-driven vers les plateformes d'execution (ex: ORDS, API Gateway, Node.js, FastAPI...)
- **Couche catalogue :** Base de donnees structuree pour les entites du Software Catalog (ex: Oracle DB, PostgreSQL, ou catalogue integre type Backstage/Port.io)

**Hypothese a valider :** Un IDP specialise base de donnees peut reproduire les fonctionnalites cles d'un IDP moderne (catalogue, Golden Paths, execution event-driven, suivi temps reel) dans le contexte et les contraintes de l'organisation.

### Prototype Description

**Portail "DB Actions Portal" - Perimetre minimal :**

**Ecran 1 - Catalogue d'actions :**
- Liste de 3 actions avec fiche descriptive :
  - Creer une BD/PDB
  - Installer Oracle
  - Patcher une BD
- Chaque fiche affiche : nom, description (issue du readme IA), indicateur d'impact (texte), plateforme d'execution (masquee ou visible selon le profil)

**Ecran 2 - Formulaire d'execution :**
- Formulaire dynamique adapte a l'action selectionnee
- Parametres specifiques par action (ex: nom de la PDB, version Oracle cible, niveau de patch)
- Bouton "Executer" qui declenche l'appel API vers la facade d'orchestration

**Ecran 3 - Suivi d'execution :**
- Statut en temps reel (soumis / en cours / termine / erreur)
- Log de retour de la plateforme d'execution
- Lien vers le detail technique (pour les DBA)

**Couche API (Facade d'orchestration event-driven - inspire Port.io) :**
- Endpoint REST par action (ex: POST /api/actions/create-pdb)
- Logique de routage event-driven vers la bonne plateforme d'execution (webhook sortant, pas de credentials plateforme stockees dans le portail)
- Endpoint callback pour reception asynchrone du statut (POST /api/executions/{id}/status)
- Stockage du statut d'execution en base (table de suivi)
- Endpoint de consultation du statut (GET /api/executions/{id})

**Couche Software Catalog (source de verite - inspire Port.io) :**
- Entite ACTIONS_CATALOG : metadata par action (nom, description, moteur, plateforme, parametres JSON, niveau d'impact, profil autorise)
- Entite EXECUTIONS : historique des executions (action, utilisateur, parametres, statut, timestamps, logs)
- Entite RBAC_POLICIES : regles d'acces par action et par profil (DBA / Business / approbation requise)

**Ce qui est hors perimetre du prototype (Iteration 1+) :**
- RBAC complet et workflows d'approbation
- Double vue DBA / Business
- Multi-moteur (SQL Server, DB2, CosmosDB)
- Documentation auto-generee integree et enrichissement IA
- Scorecards et metriques d'usage
- Interface IA conversationnelle

### Key Features to Test

**Faisabilite technique (priorite principale) :**
- [ ] La facade API peut appeler les API externes des plateformes d'execution (AAP, GitHub Actions, Terraform)
- [ ] Le routage vers la bonne plateforme fonctionne de maniere fiable
- [ ] Le statut d'execution remonte en temps reel depuis la plateforme vers le portail
- [ ] La gestion des erreurs est coherente quelle que soit la plateforme sous-jacente

**Experience utilisateur (validation secondaire) :**
- [ ] Un DBA trouve et execute une action plus rapidement que via l'outil natif actuel
- [ ] Le formulaire dynamique capture correctement les parametres necessaires pour chaque action
- [ ] L'indicateur d'impact est compris avant execution
- [ ] Le suivi de statut est suffisamment clair et en temps reel

**Questions ouvertes a explorer durant le test :**
- La facade API a-t-elle des limitations de connectivite vers les API externes dans le contexte reseau bancaire ?
- Quel est le delai de latence ajoute par la couche d'orchestration intermediaire ?
- Comment gerer l'authentification vers les plateformes externes de maniere securisee ?

---

## ✅ TEST: Validate with Users

### Testing Plan

**Volet 1 : Validation technique (pre-requis)**

| # | Test | Critere de succes |
|---|------|-------------------|
| T1 | Connectivite facade API → API plateforme (AAP / GitHub Actions / Terraform) | L'appel REST aboutit depuis le reseau bancaire |
| T2 | Routage : une action redirige vers la bonne plateforme | 3/3 actions routees correctement |
| T3 | Remontee de statut en temps reel | Le statut du portail se met a jour sans refresh manuel |
| T4 | Gestion d'erreur | Un echec plateforme remonte un message exploitable dans le portail |

**Volet 2 : Validation utilisateur**

**Participants :** 5-7 DBA (mix enthousiastes et sceptiques, a identifier par Cyrille)

**Format :** Sessions individuelles en direct, observation + questions post-session

**Scenario de test (identique pour chaque participant) :**
1. Ouvrir le portail IDP sans briefing ni documentation
2. Trouver et executer l'action "Creer une BD/PDB"
3. Trouver et executer l'action "Installer Oracle"
4. Trouver et executer l'action "Patcher une BD"
5. Pour chaque action, le testeur doit suivre l'avancement jusqu'a la fin

**Criteres de succes (GO / NO-GO) :**
- [ ] Le DBA trouve l'action facilement sans documentation
- [ ] Le formulaire est compris et rempli sans aide
- [ ] La tache s'execute correctement
- [ ] Le DBA peut suivre l'avancement en temps reel
- [ ] Les logs sont clairs et exploitables
- [ ] La tache se termine avec succes

**Points d'observation pendant la session :**
- Ou le DBA hesite-t-il ? (clics, pauses, retours en arriere)
- Pose-t-il des questions ? Lesquelles ?
- Regarde-t-il l'indicateur d'impact ?
- Quelle est sa reaction spontanee a la fin ?

### User Feedback

**Grille de capture par participant (a remplir lors des sessions) :**

| Participant | Action testee | Trouve sans aide ? | Formulaire compris ? | Suivi d'avancement clair ? | Logs clairs ? | Succes ? | Commentaire spontane |
|-------------|--------------|-------------------|---------------------|---------------------------|---------------|----------|---------------------|
| DBA #1 | Creer BD/PDB | | | | | | |
| DBA #1 | Installer Oracle | | | | | | |
| DBA #1 | Patcher BD | | | | | | |
| DBA #2 | ... | | | | | | |

**Questions post-session :**
1. Comparee a votre facon de faire aujourd'hui, qu'est-ce qui est mieux ? Moins bien ?
2. Utiliseriez-vous ce portail au quotidien ? Pourquoi / pourquoi pas ?
3. Qu'est-ce qui manque pour que ca devienne votre outil principal ?
4. Feriez-vous confiance a ce portail pour executer une action en production ?
5. A quel point etait-il facile de comprendre l'impact de l'action avant de l'executer ?

**Feedback Capture Grid (synthese apres toutes les sessions) :**

| Ce qui a plu | Questions soulevees | Idees des testeurs | A changer |
|-------------|--------------------|--------------------|-----------|
| *(a remplir)* | *(a remplir)* | *(a remplir)* | *(a remplir)* |

### Key Learnings

**Hypotheses a valider par le test :**

| # | Hypothese | Statut | Evidence |
|---|-----------|--------|----------|
| H1 | La facade API peut atteindre les plateformes externes dans le contexte reseau bancaire | A valider (Volet 1) | |
| H2 | Un DBA trouve et execute une action sans documentation via le portail IDP | A valider (Volet 2) | |
| H3 | Le suivi d'execution en temps reel est suffisant pour rassurer le DBA | A valider (Volet 2) | |
| H4 | Les logs remontes sont exploitables pour diagnostiquer un probleme | A valider (Volet 2) | |
| H5 | Les DBA prefereraient utiliser ce portail plutot que les outils natifs actuels | A valider (Volet 2) | |

**Analyse post-test (a completer) :**
- Hypotheses validees : ...
- Hypotheses invalidees : ...
- Surprises / decouvertes inattendues : ...
- Obstacles techniques identifies : ...
- Decision GO / NO-GO pour l'iteration suivante : ...

---

## 🚀 Next Steps

### Refinements Needed

**Iteration 1 - Consolider le socle IDP (post-POC) :**
- Integrer les retours des sessions DBA dans l'interface du portail
- Stabiliser la connectivite event-driven facade API → plateformes d'execution
- Formaliser le Software Catalog : modele de donnees complet (actions, environnements, moteurs, equipes)
- Implementer le RBAC granulaire par action (inspire Port.io : qui execute, qui approuve)
- Formaliser l'indicateur d'impact pour chaque action (capter le savoir tacite des DBA)
- Enrichir la documentation auto-generee par IA dans les fiches du catalogue
- Elargir le catalogue a 10-15 Golden Paths Oracle couvrant les cas les plus frequents

**Iteration 2 - Elargir et structurer l'IDP :**
- Ajouter des actions SQL Server et DB2 (validation multi-moteur)
- Workflows d'approbation automatisables (approbation auto si faible risque, validation DBA si production)
- Creer la vue "Business" simplifiee avec Golden Paths dedies
- Scorecards et dashboards par action (taux de succes, temps moyen, incidents)
- Historique des executions par client et par base de donnees

**Iteration 3 - Ouvrir le self-service et enrichir par l'IA :**
- Onboarding des premiers clients business (pilote)
- Interface IA conversationnelle pour decouverte d'actions en langage naturel
- Routage intelligent self-service vs conseil expert DBA
- Integration CosmosDB
- Metriques d'usage, feedback continu et enrichissement auto de la documentation par les logs d'execution
- Canal "Demander un conseil DBA" integre au portail

### Action Items

**Actions immediates (lancement du POC) :**
- [ ] Identifier 5-7 DBA testeurs (mix enthousiastes et sceptiques)
- [ ] Selectionner les playbooks/automatisations existants pour les 3 actions du POC (Creer BD/PDB, Installer Oracle, Patcher BD)
- [ ] Identifier sur quelle(s) plateforme(s) ces 3 actions sont actuellement executees
- [ ] Valider la faisabilite technique facade API → API externes dans le contexte reseau
- [ ] Evaluer et selectionner la stack technologique pour le portail IDP (portail, API, catalogue)
- [ ] Developper le prototype du portail (catalogue + formulaire + suivi)
- [ ] Developper la facade API (endpoints REST + routage event-driven)

**Actions post-POC :**
- [ ] Conduire les sessions de test individuelles avec les DBA
- [ ] Synthetiser les retours dans la grille de capture et le Feedback Capture Grid
- [ ] Decision GO / NO-GO sur l'Iteration 1
- [ ] Si GO : planifier l'Iteration 1 avec perimetre enrichi

**Actions structurantes :**
- [ ] Definir le modele de donnees du Software Catalog (entites : actions, moteurs, environnements, equipes, permissions)
- [ ] Definir le modele de gouvernance du catalogue d'actions (qui ajoute, qui valide, qui documente)
- [ ] Concevoir le modele de Golden Path : structure d'une action (metadata, parametres, guardrails, indicateur d'impact, RBAC)
- [ ] Etablir le processus de capture de l'indicateur d'impact (responsabilite du createur de l'action + enrichissement par usage)
- [ ] Documenter la strategie IDP : vision Port.io-inspired avec evaluation des options technologiques pour validation par l'architecture
- [ ] Preparer la communication aupres des DBA sur la vision self-service et le role valorise de conseil expert

### Success Metrics

**POC (Iteration 0) :**
| Metrique | Cible |
|----------|-------|
| Faisabilite technique facade API → plateformes | Connectivite etablie pour au moins 1 plateforme |
| Taux de reussite d'execution via le portail | 3/3 actions executees avec succes |
| DBA trouvent l'action sans documentation | 100% des testeurs (5-7 DBA) |
| DBA suivent l'avancement sans aide | 100% des testeurs |
| Logs juges clairs et exploitables | >80% des testeurs |

**Iteration 1 - Socle consolide :**
| Metrique | Cible |
|----------|-------|
| Nombre d'actions disponibles dans le catalogue | 10-15 actions Oracle |
| Satisfaction DBA avec le portail vs outils actuels | >77% (amelioration vs sondage actuel) |
| Actions executees via le portail vs directement sur les outils | Adoption croissante mois apres mois |

**Iteration 2-3 - Self-service ouvert :**
| Metrique | Cible |
|----------|-------|
| Nombre de clients business utilisant le portail | Premiers pilotes actifs |
| Taux d'actions executees en self-service sans intervention DBA | A definir apres Iteration 1 |
| Reduction du volume de tickets JIRA Service Desk pour les actions automatisees | Baisse mesurable |
| Temps DBA reinvesti en conseil expert (design, performance, architecture) | Augmentation perçue par les DBA |

---

## 🔍 Benchmark Marche & Strategie d'Innovation

### Analyse du marche (janvier 2026)

**Tendance dominante : Internal Developer Platform (IDP)**
- Gartner prevoit que 80% des organisations d'ingenierie auront une equipe Platform Engineering d'ici 2026
- Le paradigme passe de "tickets et intermediaires" a "self-service via portails developeurs internes"
- Le concept de **Golden Paths** (chemins pre-approuves avec guardrails) remplace les formulaires d'execution simples

**Solutions de reference analysees :**

| Solution | Modele | Forces | Limites pour notre contexte |
|----------|--------|--------|----------------------------|
| **Port.io** | SaaS + brokers on-prem | Self-service actions, RBAC granulaire, event-driven (sans credentials), scorecards, workflows d'approbation | SaaS uniquement, qualification nouveau produit requise |
| **Backstage** (Spotify) | Open-source, self-hosted | Software Catalog, templates, plugins extensibles, on-prem possible | Effort de setup/maintenance eleve |
| **Oracle EM DBaaS Portal** | On-prem (Oracle) | Portail self-service natif, provisioning DB/PDB/Schema | Oracle-only, lourd a operer, ne couvre pas SQL Server/DB2/CosmosDB |

### Strategie retenue : importer les concepts, pas le produit

**Principe :** Construire un IDP specialise base de donnees en transposant les concepts innovants de Port.io. Le choix de la stack technologique fera l'objet d'une evaluation separee (build vs buy, outils existants vs nouvelles solutions).

**Concepts Port.io a transposer dans la solution :**

| Concept Port.io | Transposition IDP DB |
|-----------------|----------------------|
| Software Catalog (source de verite) | Base de metadata interconnectees (actions, environnements, moteurs, equipes) |
| Self-service actions avec RBAC | Formulaires dynamiques par action + regles d'acces granulaires par profil (DBA/Business) |
| Golden Paths (chemins pre-approuves) | Chaque action = un parcours avec guardrails, documentation, indicateur d'impact, validation integree |
| Architecture event-driven | Webhooks sortants vers les plateformes, callbacks pour statut, aucun credential stocke dans le portail |
| Workflows d'approbation | Regles declaratives : execution directe si faible risque, validation DBA si production |
| Scorecards & dashboards | Metriques par action (taux de succes, temps moyen), par equipe et par moteur |

**Avantage strategique :**
- Concepts valides independamment de la technologie d'implementation
- Progressivite (POC → IDP complet par iterations)
- Si un IDP comme Port.io ou Backstage s'impose dans l'entreprise, les concepts seront deja en place et la migration sera fonctionnelle, pas conceptuelle
- L'evaluation technologique (build interne, APEX/ORDS, Backstage, Port.io, autre) se fera sur la base des resultats du POC et des contraintes de l'organisation

**Sources :**
- [Port.io - Self-Service Actions](https://docs.port.io/actions-and-automations/create-self-service-experiences/)
- [Port.io - Golden Paths](https://docs.port.io/solutions/resource-self-service/create-golden-paths/)
- [Backstage - Developer Portal](https://backstage.io/)
- [Google Cloud - Golden Paths](https://cloud.google.com/blog/products/application-development/golden-paths-for-engineering-execution-consistency)
- [Platform Engineering - What is an IDP](https://internaldeveloperplatform.org/what-is-an-internal-developer-platform/)
- [Oracle EM DBaaS Portal](https://docs.oracle.com/en/enterprise-manager/cloud-control/enterprise-manager-cloud-control/13.4/emclo/using-dbaas-self-service-portal.html)

---

_Generated using BMAD Creative Intelligence Suite - Design Thinking Workflow_
