---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
status: 'complete'
completedAt: '2026-01-27'
lastStep: 4
inputDocuments:
  - planning-artifacts/prd.md
  - planning-artifacts/architecture.md
  - planning-artifacts/ux-design-specification.md
workflowType: 'epics-and-stories'
project_name: 'test'
user_name: 'Cyrille'
date: '2026-01-27'
---

# test - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for test, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**1. Gestion du Software Catalog (FR1-FR7)**
- FR1: DBOPS peut creer une action dans le Software Catalog avec ses metadonnees (nom, description, moteur, plateforme d'execution, niveau d'impact) et configurer via des editeurs visuels dynamiques (ajouter/supprimer): Parametres (nom, type, requis, defaut, description) et Regles d'impact (criteres par environnement)
- FR2: DBOPS peut definir les etapes d'execution d'une action, chaque etape pouvant appeler un connecteur generique (AAP, ServiceNow, Azure DevOps, Jira, etc.) avec des conditions selon l'environnement cible
- FR3: [OBSOLETE - voir FR25a-d] Les regles RBAC sont gerees au niveau des profiles, pas des actions
- FR4: DBOPS peut configurer si un changement ServiceNow (pre-approuve) est requis pour chaque environnement cible
- FR5: DBOPS peut publier une action pour la rendre disponible dans le catalogue
- FR6: DBOPS peut modifier ou desactiver une action existante
- FR7: Le systeme peut auto-generer la documentation d'une action a partir du readme de l'automatisation via IA

**2. Decouverte et Navigation du Catalogue (FR8-FR12)**
- FR8: DBA peut parcourir l'integralite du catalogue d'actions disponibles
- FR9: DBA peut consulter la fiche descriptive d'une action (nom, description, indicateur d'impact, moteur, parametres attendus)
- FR10: Client Business peut parcourir une vue simplifiee des actions deleguees a son profil
- FR11: Tout utilisateur peut rechercher et filtrer les actions par tags, moteur, environnement, niveau d'impact ou mot-cle
- FR11a: Tout utilisateur peut basculer entre une vue en cartes (cards) et une vue en liste pour le catalogue
- FR11b: Tout utilisateur peut marquer des actions en favoris et les retrouver dans une section "Mes actions"
- FR11c: DBOPS peut assigner plusieurs tags flexibles a une action (ex: RAC, DATAGUARD, Provisioning)
- FR12: Tout utilisateur peut acceder a la documentation contextuelle d'une action

**3. Execution d'Actions (FR13-FR18)**
- FR13: DBA peut executer une action via un formulaire dynamique adapte aux parametres de l'action selectionnee
- FR14: Client Business peut executer les actions deleguees via un Golden Path guide
- FR15: Le systeme valide les parametres saisis avant de declencher l'execution
- FR16: Le systeme ouvre automatiquement un changement ServiceNow lorsqu'une etape de l'action le requiert selon la definition et l'environnement cible
- FR17: Le systeme recupere les secrets necessaires depuis HashiCorp Vault au moment de l'execution
- FR18: Le systeme route l'execution vers la bonne plateforme (AAP, GitHub Actions, Azure DevOps, Terraform) via une facade API event-driven

**4. Suivi d'Execution (FR19-FR23)**
- FR19: Tout utilisateur peut suivre le statut d'une execution en temps reel (soumis, en cours, termine, erreur)
- FR20: Tout utilisateur peut consulter les logs remontes par la plateforme d'execution
- FR21: DBA peut acceder aux logs techniques detailles d'une execution
- FR22: Tout utilisateur peut consulter l'historique de ses propres executions
- FR23: Le systeme recoit les callbacks de statut asynchrones des plateformes d'execution

**5. Controle d'Acces et Securite (FR24-FR29)**
- FR24: Les utilisateurs s'authentifient via le SSO d'entreprise et doivent appartenir au groupe AD global du portail
- FR25: Le systeme resout les profiles de l'utilisateur a partir de ses groupes AD
- FR25a: DBOPS peut creer et gerer des profiles dynamiques avec mapping vers un groupe AD
- FR25b: DBOPS peut definir les permissions d'un profile: actions (liste ou pattern/tags), targets (liste ou pattern), environnements
- FR25c: Les permissions d'un utilisateur multi-profiles sont cumulees (union)
- FR25d: DBOPS peut importer/exporter la configuration des profiles en YAML (as code)
- FR26: Le systeme applique les regles RBAC: actions + targets + environnements par profile
- FR26a: Les targets autorises sont valides contre l'inventaire interne au moment de l'execution
- FR27: Le systeme impose un workflow d'approbation pour les actions qui le requierent (approbation DBA pour la production)
- FR28: DBOPS peut configurer les regles d'approbation par action et par environnement
- FR29: Le systeme ne stocke aucun credential — tous les secrets sont recuperes depuis Vault a l'execution

**6. Audit et Conformite (FR30-FR35)**
- FR30: Le systeme genere une trace d'audit immutable pour chaque execution (qui, quoi, quand, parametres, resultat, autorisation RBAC)
- FR31: Le systeme genere une evidence specifique pour les actions de patching (version source, version cible, resultat)
- FR32: Le systeme trace toute creation de compte a privileges avec justification et approbateur
- FR33: Specialiste Securite peut consulter l'historique d'execution filtre par environnement, periode et type d'action
- FR34: Specialiste Securite peut exporter des rapports d'audit
- FR35: Le systeme enregistre l'evidence de gestion du changement (ID changement ServiceNow, type, approbation)

**7. Autoremediation (FR36-FR38)**
- FR36: Le systeme peut detecter un echec d'execution et proposer des actions correctives depuis le catalogue
- FR37: DBA peut evaluer et declencher une action corrective depuis la proposition de remediation
- FR38: Le systeme peut executer automatiquement des actions correctives pour les scenarios a faible risque

**8. Analytics et Reporting (FR39-FR41)**
- FR39: DBA peut consulter les scorecards par action (taux de succes, temps moyen d'execution, incidents)
- FR40: DBOPS peut consulter des dashboards globaux (actions par moteur, par equipe, tendances d'adoption)
- FR41: DBA peut consulter un tableau de bord d'activite recente et de statuts d'execution

**9. Donnees et Inventaire (FR42-FR43)**
- FR42: Le systeme se synchronise avec l'inventaire interne (API) pour alimenter les metadonnees des bases de donnees dans le catalogue
- FR43: Le systeme alimente les formulaires dynamiques avec les donnees de l'inventaire (liste des bases, environnements disponibles)

**10. Communication et IA (FR44-FR45)**
- FR44: Client Business peut demander une consultation expert DBA depuis le portail
- FR45: Tout utilisateur peut decouvrir des actions via une interface IA conversationnelle en langage naturel

### NonFunctional Requirements

**Performance (NFR1-NFR5)**
- NFR1: Les pages du portail (catalogue, formulaire, suivi) se chargent en moins de 2 secondes
- NFR2: La soumission d'une execution via le formulaire obtient une confirmation (statut "soumis") en moins de 3 secondes
- NFR3: La mise a jour du statut d'execution en temps reel se rafraichit avec un delai maximum de 5 secondes apres reception du callback
- NFR4: La recherche et le filtrage dans le catalogue retournent des resultats en moins de 1 seconde
- NFR5: Le portail supporte 10 utilisateurs simultanes au MVP (extensible a 50+ en Phase 2, 200+ en Phase 3)

**Securite (NFR6-NFR11)**
- NFR6: Toutes les communications entre le portail et les systemes integres sont chiffrees en transit (TLS 1.2+)
- NFR7: Aucun secret (credential, token, cle) n'est stocke dans le portail ou le catalogue — recuperation exclusive depuis Vault a l'execution
- NFR8: Les logs d'audit sont immutables — aucune modification ni suppression possible apres ecriture
- NFR9: Les sessions utilisateur expirent apres une periode d'inactivite conforme aux standards internes
- NFR10: Toute tentative d'acces non autorise (RBAC) est journalisee et refusee
- NFR11: Le portail ne conserve aucune donnee sensible des bases de donnees gerees — seules les metadonnees de l'inventaire sont stockees

**Fiabilite & Disponibilite (NFR12-NFR16)**
- NFR12: Le portail de production a un SLA de disponibilite de 99.9%
- NFR13: En cas de defaillance d'une plateforme d'execution, le portail remonte une erreur explicite sans planter ni bloquer les autres executions
- NFR14: Les executions en cours ne sont pas perdues en cas de redemarrage du portail — reprise sur l'etat du dernier callback recu
- NFR15: Le mecanisme de break-the-glass (acces direct DBOPS aux plateformes) est operationnel independamment de la disponibilite du portail
- NFR16: Le portail de developpement n'a pas de SLA de disponibilite

**Integration (NFR17-NFR21)**
- NFR17: Le portail gere les erreurs de connectivite vers chaque plateforme d'execution de maniere independante
- NFR18: Les callbacks asynchrones des plateformes sont idempotents — un callback recu en doublon ne corrompt pas l'etat
- NFR19: L'integration ServiceNow tolere un delai de reponse de l'API ServiceNow jusqu'a 30 secondes sans echouer l'action
- NFR20: La synchronisation avec l'inventaire interne se fait de maniere periodique ou on-demand sans impacter la performance
- NFR21: En cas d'indisponibilite de Vault, l'execution est refusee avec un message explicite (pas de fallback)

**Scalabilite (NFR22-NFR25)**
- NFR22: L'architecture supporte l'ajout de nouvelles plateformes d'execution sans modification du coeur du portail (pattern plugin/adapter)
- NFR23: Le catalogue supporte un minimum de 100 actions sans degradation de performance
- NFR24: L'historique d'execution supporte un volume de 10 000+ executions par an sans degradation des requetes d'audit
- NFR25: L'ajout de nouveaux moteurs de base de donnees ne necessite pas de refonte architecturale

### Additional Requirements

**Depuis l'Architecture :**

- **Starter Template (Epic 1 Story 1)** : Initialisation monorepo Vite + React + TypeScript + Ant Design 6 (frontend) + FastAPI + python-oracledb (backend). Commandes documentees dans l'Architecture section "Starter Template"
- **Schema Oracle** : 5 scripts de migration SQL (V001-V005) : USERS, ACTIONS_CATALOG, EXECUTIONS + EXECUTION_STEPS, AUDIT_LOG, USER_PERMISSIONS
- **SAML 2.0 SP-initiated** : Authentification via python3-saml, session JWT (access 30min + refresh 8h httpOnly cookie). Blocker #1
- **Repository Pattern SQL brut** : Chaque domaine (catalog, executions, users, audit) a son repository avec SQL via python-oracledb
- **Platform Adapter Pattern (Strategy)** : Interface commune base_adapter.py (trigger(), get_status(), parse_callback()). 4 implementations : AAP, GitHub Actions, Azure DevOps, Terraform
- **WebSocket natif FastAPI** : Endpoint /ws/executions/{id} pour timeline temps reel. Messages types : step_update, execution_complete, execution_failed
- **Structured logging** : structlog JSON → fichiers → Splunk Forwarder. Correlation ID (X-Idp-Request-Id) sur chaque requete
- **Cache in-memory** : cachetools / lru_cache Python. Cache catalogue TTL 5min, cache RBAC TTL 1min
- **CI/CD GitHub Actions** : Lint + tests + build + deploy (SSH + rsync vers VM)
- **Deployment VM** : Nginx reverse proxy (TLS) + Uvicorn + systemd. 2 VMs minimum (HA active-active)
- **Monitoring** : Dynatrace OneAgent + health check endpoint /api/v1/health (DB + Vault + ServiceNow)
- **Error hierarchy** : IdpError → NotFoundError, ForbiddenError, PlatformError, VaultError, ServiceNowError
- **API format** : snake_case JSON, wrapper { "data": ... } / { "error": ... }, ISO 8601 UTC dates
- **OpenAPI → TypeScript** : Generation automatique des types TS depuis le schema OpenAPI FastAPI (openapi-typescript)

**Depuis l'UX Design :**

- **6 composants custom** : ActionCard, ImpactIndicator, ExecutionTimeline, StructuredErrorCard, ExecutionWizard, AdminPreview — specifies en detail dans l'UX spec
- **Theme Ant Design Desjardins** : Palette #00874E primary, tokens CSS Variables, fichier desjardins.ts
- **Desktop-only** : 3 breakpoints (1280, 1600, 1920+), min-width 1280px
- **WCAG 2.1 AA** : Triple codage (couleur + icone + texte), navigation clavier complete, ARIA sur tous les composants custom
- **Skeleton loading** : Shimmer patterns pour cartes, tables, drawers. Jamais de spinner seul
- **Layout principal** : Top bar fixe (56px) + filtres lateraux (240px) + contenu fluide + drawer droit (480px) + wizard centre (640px)
- **HTML showcase** : Fichier ux-design-directions.html (7 ecrans) comme reference visuelle pour l'implementation

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 2 | DBOPS cree une action dans le Software Catalog (Stories 2.1, 2.17, 2.18: editeurs visuels parametres et regles d'impact) |
| FR2 | Epic 2 | DBOPS definit les etapes d'execution avec connecteurs generiques |
| FR3 | Epic 2 | [OBSOLETE] RBAC deplace vers profiles (FR25a-d) |
| FR4 | Epic 2 | DBOPS configure si changement ServiceNow requis par environnement |
| FR5 | Epic 2 | DBOPS publie une action dans le catalogue |
| FR6 | Epic 2 | DBOPS modifie ou desactive une action |
| FR7 | Epic 10 | Auto-generation documentation IA |
| FR8 | Epic 3 | DBA parcourt le catalogue d'actions |
| FR9 | Epic 3 | DBA consulte la fiche descriptive d'une action |
| FR10 | Epic 7 | Client Business parcourt une vue simplifiee |
| FR11 | Epic 3 | Recherche et filtrage actions par tags |
| FR11a | Epic 3 | Toggle cartes/liste pour le catalogue |
| FR11b | Epic 3 | Favoris et section "Mes actions" |
| FR11c | Epic 2 | Tags flexibles multi-valeurs (DBOPS) |
| FR12 | Epic 3 | Documentation contextuelle d'une action |
| FR13 | Epic 4 | DBA execute via formulaire dynamique |
| FR14 | Epic 7 | Client Business execute via Golden Path |
| FR15 | Epic 4 | Validation parametres avant execution |
| FR16 | Epic 4 | Ouverture changement ServiceNow automatique |
| FR17 | Epic 4 | Recuperation secrets Vault a l'execution |
| FR18 | Epic 4 | Routage vers la bonne plateforme (facade API) |
| FR19 | Epic 4 | Suivi statut execution temps reel |
| FR20 | Epic 4 | Consultation logs plateforme |
| FR21 | Epic 4 | Logs techniques detailles (DBA) |
| FR22 | Epic 4 | Historique propres executions |
| FR23 | Epic 4 | Reception callbacks asynchrones |
| FR24 | Epic 1 | Authentification SSO entreprise |
| FR25 | Epic 1 | Attribution profil RBAC depuis SSO |
| FR25a | Epic 2 | DBOPS cree et gere des profiles dynamiques avec mapping AD |
| FR25b | Epic 2 | DBOPS definit permissions profile: actions + targets + envs |
| FR25c | Epic 2 | Permissions cumulees pour multi-profiles |
| FR25d | Epic 2 | Import/export profiles en YAML (as code) |
| FR26 | Epic 2 | Application RBAC: actions + targets + envs par profile |
| FR26a | Epic 2 | Targets valides contre inventaire |
| FR27 | Epic 7 | Workflow d'approbation production |
| FR28 | Epic 7 | Configuration regles d'approbation |
| FR29 | Epic 4 | Zero credential — secrets depuis Vault |
| FR30 | Epic 6 | Trace d'audit immutable par execution |
| FR31 | Epic 6 | Evidence patching (version source/cible) |
| FR32 | Epic 6 | Trace creation comptes a privileges |
| FR33 | Epic 6 | Historique filtre par env/periode/action |
| FR34 | Epic 6 | Export rapports d'audit |
| FR35 | Epic 6 | Evidence gestion du changement ServiceNow |
| FR36 | Epic 9 | Detection echec + proposition corrective |
| FR37 | Epic 9 | DBA declenche action corrective |
| FR38 | Epic 9 | Execution auto corrective (faible risque) |
| FR39 | Epic 8 | Scorecards par action |
| FR40 | Epic 8 | Dashboards globaux |
| FR41 | Epic 5 | Tableau de bord activite recente |
| FR42 | Epic 4 | Synchronisation inventaire interne |
| FR43 | Epic 4 | Formulaires dynamiques depuis inventaire |
| FR44 | Epic 10 | Consultation expert DBA depuis portail |
| FR45 | Epic 10 | Interface IA conversationnelle |

**Couverture : 53/53 FR mappees (incluant FR11a-c, FR25a-d, FR26a).**

## Epic List

### Epic 1 : Bootstrap Projet & Authentification
L'equipe peut se connecter via SSO et acceder au portail avec son role. Le monorepo est initialise, le schema Oracle est en place, le CI/CD fonctionne, le logging structure est operationnel.
**FRs couvertes :** FR24, FR25
**Phase :** MVP (POC)

### Epic 2 : Administration du Catalogue (Karim)
DBOPS peut creer, configurer et publier des actions dans le Software Catalog. L'interface admin est de premiere classe avec preview temps reel. Inclut le systeme de tags flexibles et les connecteurs generiques.
**FRs couvertes :** FR1, FR2, FR3, FR4, FR5, FR6, FR11c
**Phase :** MVP (POC)

### Epic 3 : Decouverte du Catalogue (Marc)
DBA decouvre et comprend les actions disponibles a travers le catalogue avec modes d'affichage (cartes/liste), tags, favoris, recherche et fiches detaillees.
**FRs couvertes :** FR8, FR9, FR11, FR11a, FR11b, FR12
**Phase :** MVP (POC)

### Epic 4 : Execution & Suivi Temps Reel
DBA execute une action de bout en bout via le wizard et suit la progression etape par etape en temps reel via la timeline. Integrations Vault, ServiceNow, plateformes d'execution et inventaire incluses.
**FRs couvertes :** FR13, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR22, FR23, FR29, FR42, FR43
**Phase :** MVP (POC)

### Epic 5 : Dashboard & Activite
DBA consulte son tableau de bord d'activite recente et les statuts d'execution depuis une vue synthetique.
**FRs couvertes :** FR41
**Phase :** Growth (Phase 2)

### Epic 6 : Audit & Conformite SOC1 (Nadia)
Le specialiste securite consulte l'historique d'execution, genere des rapports d'audit exportables et valide la conformite SOC1.
**FRs couvertes :** FR30, FR31, FR32, FR33, FR34, FR35
**Phase :** Growth (Phase 2)

### Epic 7 : Self-Service Business & RBAC Granulaire (Fatima)
Les clients business executent des actions en self-service via Golden Paths guides, avec un controle d'acces granulaire et des workflows d'approbation pour la production.
**FRs couvertes :** FR10, FR14, FR26, FR27, FR28
**Phase :** Growth (Phase 2)

### Epic 8 : Analytics & Scorecards
DBOPS et DBA consultent des metriques d'adoption, de performance et de tendances a travers scorecards et dashboards globaux.
**FRs couvertes :** FR39, FR40
**Phase :** Growth (Phase 2)

### Epic 9 : Autoremediation
Le systeme detecte les echecs d'execution et propose des actions correctives depuis le catalogue, executables automatiquement pour les scenarios a faible risque.
**FRs couvertes :** FR36, FR37, FR38
**Phase :** Growth (Phase 2)

### Epic 10 : Documentation IA, Communication & Interface Conversationnelle
Le systeme auto-genere la documentation des actions, les clients demandent conseil DBA depuis le portail, et les utilisateurs decouvrent des actions via une interface IA conversationnelle.
**FRs couvertes :** FR7, FR44, FR45
**Phase :** Vision (Phase 3)

---

## Epic 1 : Bootstrap Projet & Authentification

L'equipe peut se connecter via SSO et acceder au portail avec son role. Le monorepo est initialise, le schema Oracle est en place, le CI/CD fonctionne, le logging structure est operationnel.

### Story 1.1 : Initialisation du monorepo et environnement de developpement

As a developpeur de l'equipe IDP,
I want le monorepo initialise avec le frontend React+Vite+Ant Design et le backend FastAPI+python-oracledb,
So that je peux commencer a developper les features du portail sur une base solide.

**Acceptance Criteria:**

**Given** un developpeur clone le repo
**When** il execute `npm run dev` dans frontend/ et `fastapi dev` dans backend/
**Then** le frontend demarre sur le port 5173 avec le theme Desjardins (#00874E) et le backend repond sur le port 8000
**And** le proxy Vite redirige `/api` et `/ws` vers le backend
**And** le fichier `desjardins.ts` configure les tokens Ant Design 6 (primary color, bordures, spacings)
**And** le layout principal est en place : top bar fixe (56px), zone contenu fluide, fond #FAFBFC
**And** la structure de fichiers respecte l'arborescence definie dans l'Architecture (frontend/src/**, backend/app/**)
**And** la table USERS (V001) est creee via le script de migration SQL
**And** le pool de connexions Oracle (oracledb.create_pool) est configure dans core/database.py
**And** les exceptions custom (IdpError hierarchy) sont definies dans core/exceptions.py

### Story 1.2 : Authentification SAML 2.0 et session JWT

As a membre de l'equipe (DBA ou DBOPS),
I want me connecter au portail via le SSO d'entreprise,
So that j'accede au portail avec mon identite corporative de maniere securisee.

**Acceptance Criteria:**

**Given** un utilisateur non authentifie ouvre le portail
**When** il est redirige vers l'IdP SAML et s'authentifie
**Then** le backend recoit l'assertion SAML, valide la signature, extrait les attributs (nom, profil, groupes)
**And** le backend cree ou met a jour l'utilisateur dans la table USERS
**And** le backend emet un access token JWT (30min) et un refresh token (8h, httpOnly cookie)
**And** le SPA stocke l'access token en memoire (jamais localStorage)
**And** toutes les requetes API incluent le header Authorization: Bearer <token>
**And** un token expire renvoie HTTP 401 et le SPA tente un refresh automatique
**And** un refresh echoue redirige vers la page de login SSO
**And** FR24 est satisfaite

### Story 1.3 : Profil RBAC et navigation du portail

As a utilisateur authentifie,
I want voir mon profil et naviguer entre les sections du portail selon mon role,
So that j'accede uniquement aux fonctionnalites qui me concernent.

**Acceptance Criteria:**

**Given** un utilisateur authentifie avec un profil DBOPS
**When** il accede au portail
**Then** la top bar affiche 4 onglets : Catalogue, Executions, Dashboard, Admin
**And** l'onglet actif est en vert #00874E avec underline 2px

**Given** un utilisateur authentifie avec un profil DBA
**When** il accede au portail
**Then** la top bar affiche 3 onglets : Catalogue, Executions, Dashboard (Admin masque)

**Given** un utilisateur authentifie
**When** il consulte son profil (coin superieur droit)
**Then** son nom, son role et un bouton deconnexion sont affiches

**And** le AuthContext React fournit user profile, token et permissions a toute l'application
**And** la table USER_PERMISSIONS (V005) est creee via le script de migration SQL
**And** le middleware RBAC FastAPI filtre les routes selon le profil (basic : DBA vs DBOPS)
**And** les pages sont lazy-loaded (React.lazy) par route
**And** FR25 est satisfaite

### Story 1.4 : Observabilite, Health Check et CI/CD

As a DBOPS responsable de la plateforme,
I want des logs structures, un health check et un pipeline de deploiement automatise,
So that le portail est monitorable, deployable et pret pour la production.

**Acceptance Criteria:**

**Given** le backend est en cours d'execution
**When** on appelle GET /api/v1/health
**Then** la reponse indique le statut de connectivite Oracle, et retourne HTTP 200 si OK, 503 sinon

**Given** une requete HTTP arrive sur le backend
**When** elle est traitee
**Then** un correlation ID (X-Idp-Request-Id, UUID) est genere et propage dans tous les logs
**And** chaque entree de log est en JSON structure (structlog) avec timestamp, level, event, correlation_id, user_id

**Given** un push sur la branche main
**When** GitHub Actions se declenche
**Then** le pipeline execute : lint (eslint+ruff), type check (tsc+mypy), tests (vitest+pytest), build (vite build)
**And** le deploy copie les fichiers via SSH+rsync vers la VM

**And** la config Nginx (idp-portal.conf) termine TLS et proxy vers Uvicorn
**And** le service systemd (idp-portal.service) gere le process Uvicorn avec restart automatique
**And** le middleware CORS est configure (origin portail uniquement)
**And** les niveaux de log suivent la convention Architecture (debug, info, warning, error, critical)

---

## Epic 2 : Administration du Catalogue (Karim)

DBOPS peut creer, configurer et publier des actions dans le Software Catalog. L'interface admin est de premiere classe avec preview temps reel. Inclut le systeme de tags flexibles et les connecteurs generiques.

### Story 2.1 : Creer une action avec ses metadonnees

As a DBOPS,
I want creer une nouvelle action dans le Software Catalog avec ses metadonnees completes,
So that je definisse les actions disponibles pour les DBA et les clients business.

**Acceptance Criteria:**

**Given** un DBOPS authentifie accede a l'onglet Admin
**When** il clique sur "Nouvelle action"
**Then** un formulaire admin s'affiche avec les sections : nom, description, categorie (Provisioning/Patching/Administration/Monitoring), moteur (Oracle/SQL Server/DB2), plateforme d'execution (AAP/GitHub Actions/Azure DevOps/Terraform)

**Given** le DBOPS remplit les champs de base
**When** il configure les parametres via l'editeur visuel (voir Story 2.17) et les regles d'impact (voir Story 2.18)
**Then** le systeme valide les donnees et enregistre l'action en statut "brouillon"

**And** la table ACTIONS_CATALOG (V002) est creee via le script de migration SQL
**And** les colonnes CLOB (parameters_schema, impact_rules, rbac_policies) stockent du JSON interrogeable via JSON_VALUE Oracle
**And** le catalog_repository.py encapsule le SQL brut (INSERT, SELECT)
**And** l'API POST /api/v1/admin/actions retourne 201 avec l'action creee dans { "data": {...} }
**And** la validation inline est presente sur le formulaire (pas de validation uniquement a la soumission)
**And** FR1 est satisfaite

### Story 2.2 : Definir les etapes d'execution et le changement ServiceNow

As a DBOPS,
I want configurer les etapes d'execution d'une action et indiquer si un changement ServiceNow est requis par environnement,
So that chaque action suit le bon processus d'execution selon l'environnement cible.

**Acceptance Criteria:**

**Given** un DBOPS edite une action en brouillon
**When** il accede a la section "Etapes d'execution"
**Then** il peut definir une liste ordonnee d'etapes avec nom et type (pre-requis, execution, verification)

**Given** le DBOPS configure une etape conditionnelle
**When** il specifie "ouverture changement ServiceNow" pour l'environnement Production
**Then** l'etape est marquee comme conditionnelle a l'environnement cible

**Given** le DBOPS configure les changements par environnement
**When** il definit "changement requis" pour Production
**Then** le systeme enregistre cette configuration (tous les changements sont pre-approuves, non-bloquants)

**And** la colonne execution_steps (CLOB JSON) est ajoutee a ACTIONS_CATALOG si absente
**And** l'API PUT /api/v1/admin/actions/{id}/steps enregistre les etapes
**And** FR2 et FR4 sont satisfaites

**Note:** Cette story a ete implementee avec l'ancien modele (is_servicenow_change + CAB). La story 2.7 et 2.8 refactorisent vers le nouveau modele (connecteurs generiques, pre-approuve uniquement).

### Story 2.3 : Configurer le RBAC par action [OBSOLETE - REFACTORING REQUIS]

**⚠️ CETTE STORY A ETE IMPLEMENTEE AVEC L'ANCIEN MODELE ET DOIT ETRE REFACTOREE**

L'ancien modele stockait les permissions RBAC dans chaque action (ACTIONS_CATALOG.rbac_policies).
Le nouveau modele gere les permissions au niveau des PROFILES (voir stories 2-9 a 2-13).

**Migration requise:**
- Supprimer la colonne rbac_policies de ACTIONS_CATALOG
- Supprimer le composant RbacEditor.tsx de l'admin action
- Supprimer l'endpoint PUT /api/v1/admin/actions/{id}/rbac
- Les permissions sont maintenant gerees via les profiles (stories 2-9 a 2-13)

### Story 2.4 : Publier et gerer le cycle de vie d'une action

As a DBOPS,
I want publier une action pour la rendre visible dans le catalogue, et pouvoir la modifier ou la desactiver,
So that je controle ce que les utilisateurs voient et peuvent executer.

**Acceptance Criteria:**

**Given** un DBOPS a complete la configuration d'une action en brouillon
**When** il clique sur "Publier"
**Then** l'action passe en statut "publiee" et apparait dans le catalogue pour les profils autorises

**Given** un DBOPS consulte la liste des actions dans l'onglet Admin
**When** il voit le dashboard admin
**Then** les actions sont listees avec leur statut (brouillon, publiee, desactivee), date de creation, et nombre d'executions

**Given** un DBOPS edite une action publiee
**When** il modifie des metadonnees et sauvegarde
**Then** les modifications sont appliquees immediatement dans le catalogue
**And** une entree d'audit est creee pour la modification

**Given** un DBOPS desactive une action
**When** il confirme la desactivation
**Then** l'action n'apparait plus dans le catalogue mais reste dans l'historique

**And** l'API PATCH /api/v1/admin/actions/{id}/status gere les transitions de statut
**And** FR5 et FR6 sont satisfaites

### Story 2.5 : Preview temps reel de l'action

As a DBOPS,
I want visualiser mon action en temps reel telle que les consommateurs la verront,
So that je valide l'experience utilisateur avant de publier.

**Acceptance Criteria:**

**Given** un DBOPS est sur le formulaire d'edition d'une action
**When** il modifie n'importe quel champ (nom, description, impact, parametres)
**Then** la preview a droite se met a jour instantanement et affiche : ActionCard (carte catalogue) + fiche action (drawer)

**Given** le DBOPS consulte la preview
**When** il voit la carte et la fiche
**Then** l'apparence est identique a ce que verra un DBA dans le catalogue (memes composants, memes styles)

**And** le composant AdminPreview utilise les memes composants ActionCard et ImpactIndicator que le catalogue
**And** la preview est en lecture seule (pas d'interaction)
**And** le layout est en split view : formulaire a gauche, preview a droite
**And** `aria-live="polite"` annonce les changements de preview pour l'accessibilite

### Story 2.6 : Systeme de tags flexibles pour les actions

As a DBOPS,
I want assigner plusieurs tags flexibles a une action (ex: RAC, DATAGUARD, Provisioning),
So that les utilisateurs peuvent filtrer le catalogue de maniere dynamique sans categories fixes.

**Acceptance Criteria:**

**Given** un DBOPS edite une action
**When** il accede a la section "Tags"
**Then** il voit un champ multi-select avec auto-completion sur les tags existants

**Given** le DBOPS saisit un nouveau tag qui n'existe pas
**When** il tape "RAC" et appuie sur Entree
**Then** le tag est cree automatiquement et assigne a l'action

**Given** le DBOPS consulte la liste des actions dans l'admin
**When** il voit le tableau
**Then** les tags de chaque action sont affiches sous forme de chips

**Given** le catalogue contient 100+ actions
**When** un utilisateur filtre par tag
**Then** les resultats se chargent en < 1 seconde (NFR4)

**And** la table TAGS (id, name, created_at) est creee via migration SQL V004
**And** la table ACTION_TAGS (action_id, tag_id) gere la relation many-to-many
**And** l'API GET /api/v1/tags retourne tous les tags existants
**And** l'API PUT /api/v1/admin/actions/{id}/tags assigne les tags a une action
**And** les tags sont en lowercase, sans espaces (normalisation automatique)
**And** FR11c est satisfaite

### Story 2.7 : Refactorisation des connecteurs generiques

As a developpeur,
I want refactoriser les etapes d'execution pour utiliser un connector_type generique au lieu du flag is_servicenow_change,
So that tous les systemes externes (AAP, ServiceNow, Azure DevOps, Jira, GitHub Actions) sont traites de maniere uniforme.

**Acceptance Criteria:**

**Given** une action existante avec des etapes
**When** le modele ExecutionStep est mis a jour
**Then** le champ is_servicenow_change est remplace par connector_type (enum: aap, servicenow, azuredevops, jira, github_actions, terraform, none)
**And** le champ connector_config (JSON) stocke la configuration specifique au connecteur

**Given** une action a une etape ServiceNow conditionnelle en production
**When** le DBOPS consulte la configuration
**Then** l'etape affiche connector_type: "servicenow" avec conditional_environments: ["PROD"]

**Given** une migration de donnees est executee
**When** les anciennes donnees sont converties
**Then** is_servicenow_change: true devient connector_type: "servicenow"
**And** is_servicenow_change: false devient connector_type: "none" ou conserve le type d'origine

**And** la migration SQL V005 ajoute les colonnes connector_type et connector_config
**And** le frontend StepsEditor est mis a jour pour afficher un dropdown de connecteurs
**And** les modeles Pydantic backend sont mis a jour
**And** la retro-compatibilite avec les donnees existantes est assuree
**And** FR2 (PRD mis a jour) est satisfaite

### Story 2.8 : Suppression du rail CAB et simplification ServiceNow

As a developpeur,
I want supprimer la logique de changement CAB bloquant et ne garder que les changements pre-approuves,
So that l'execution ne soit jamais bloquee en attente d'approbation ServiceNow.

**Acceptance Criteria:**

**Given** une action configure un changement ServiceNow
**When** l'execution atteint l'etape ServiceNow
**Then** le changement est cree comme pre-approuve et l'execution continue immediatement (non-bloquant)

**Given** le modele ChangeType contenait "pre_approved" et "cab"
**When** le modele est mis a jour
**Then** seul "pre_approved" existe (ou le champ est supprime car implicite)

**Given** l'interface admin permettait de choisir "CAB"
**When** le composant ChangeTypeConfig est mis a jour
**Then** l'option CAB est supprimee, seule la configuration par environnement reste (changement requis oui/non)

**And** la migration de donnees convertit tous les "cab" existants en "pre_approved"
**And** les stories 4-5 (ServiceNow) et les tests sont mis a jour
**And** FR4 et FR16 (PRD mis a jour) sont satisfaites

### Story 2.9 : Gestion des profiles dynamiques

As a DBOPS,
I want creer et gerer des profiles dynamiques avec leur mapping vers un groupe AD,
So that je peux definir des permissions granulaires pour chaque equipe ou role.

**Acceptance Criteria:**

**Given** un DBOPS accede a la section "Profiles" dans l'admin
**When** il clique sur "Nouveau profile"
**Then** un formulaire s'affiche avec : nom, description, groupe AD associe, flags (is_admin, is_auditor)

**Given** le DBOPS cree un profile "Assurance" avec groupe AD "GRP-IDP-ASSURANCE"
**When** il sauvegarde
**Then** le profile est cree et le mapping AD est enregistre

**Given** le DBOPS consulte la liste des profiles
**When** la page se charge
**Then** tous les profiles sont affiches avec : nom, groupe AD, nombre de permissions, date de creation

**Given** le DBOPS edite un profile existant
**When** il modifie le groupe AD
**Then** le nouveau mapping s'applique immediatement (cache invalide)

**And** la table PROFILES est creee via migration SQL
**And** l'API CRUD /api/v1/admin/profiles est implementee
**And** FR25a est satisfaite

### Story 2.10 : Permissions actions par profile

As a DBOPS,
I want definir les actions autorisees pour un profile (liste explicite ou pattern/tags),
So that chaque profile a acces uniquement aux actions necessaires.

**Acceptance Criteria:**

**Given** un DBOPS edite un profile
**When** il accede a la section "Actions autorisees"
**Then** il peut choisir entre : liste d'actions specifiques, pattern par tags, ou "*" (toutes)

**Given** le DBOPS choisit "Pattern par tags"
**When** il saisit "tag:oracle, tag:provisioning"
**Then** le profile aura acces a toutes les actions ayant ces tags

**Given** le DBOPS choisit "Liste d'actions"
**When** il selectionne des actions specifiques dans un multi-select
**Then** seules ces actions seront accessibles

**Given** le DBOPS definit les environnements autorises
**When** il selectionne [DEV, STAGING]
**Then** le profile ne pourra executer que sur ces environnements

**And** la table PROFILE_ACTION_PERMISSIONS est creee via migration SQL
**And** l'API PUT /api/v1/admin/profiles/{id}/actions enregistre les permissions
**And** FR25b est partiellement satisfaite (actions)

### Story 2.11 : Permissions targets par profile

As a DBOPS,
I want definir les targets (serveurs/bases) autorises pour un profile (liste explicite ou pattern),
So that chaque equipe ne puisse executer que sur ses propres ressources.

**Acceptance Criteria:**

**Given** un DBOPS edite un profile
**When** il accede a la section "Targets autorises"
**Then** il peut choisir entre : liste de targets explicites, pattern (ex: assurance-*), ou "*" (tous)

**Given** le DBOPS choisit "Pattern"
**When** il saisit "assurance-*"
**Then** le profile aura acces aux targets dont le nom commence par "assurance-"

**Given** le DBOPS choisit "Liste explicite"
**When** il selectionne des targets depuis l'inventaire (autocomplete)
**Then** seuls ces targets seront accessibles

**Given** un utilisateur execute une action
**When** le wizard charge les targets disponibles
**Then** seuls les targets autorises par ses profiles (cumules) ET presents dans l'inventaire sont affiches

**And** la table PROFILE_TARGET_PERMISSIONS est creee via migration SQL
**And** les targets sont valides contre l'inventaire interne au moment de l'execution
**And** FR25b est completement satisfaite (actions + targets)
**And** FR26a est satisfaite

### Story 2.12 : Cumul des permissions multi-profiles

As a systeme,
I want cumuler les permissions quand un utilisateur a plusieurs profiles,
So that les utilisateurs avec plusieurs roles aient l'union de leurs permissions.

**Acceptance Criteria:**

**Given** un utilisateur appartient aux groupes AD [GRP-IDP-ASSURANCE, GRP-IDP-DBA-APP]
**When** il se connecte au portail
**Then** ses permissions sont l'union des profiles Assurance et DBA Applicatif

**Given** Assurance autorise actions "tag:oracle" sur targets "assurance-*"
**And** DBA Applicatif autorise actions "tag:*" sur targets "*"
**When** les permissions sont cumulees
**Then** l'utilisateur a acces a actions "tag:*" sur targets "*" (union)

**Given** un utilisateur n'appartient a aucun groupe AD reconnu (hors groupe global portail)
**When** il se connecte
**Then** l'acces est refuse avec message "Aucun profile associe a votre compte"

**And** le service RBAC calcule les permissions cumulees au login et les stocke en session/JWT
**And** le cache des permissions est invalide quand un profile est modifie
**And** FR25c est satisfaite

### Story 2.13 : Import/Export profiles as code (YAML)

As a DBOPS,
I want importer et exporter la configuration des profiles en YAML,
So that je puisse gerer les profiles en GitOps et versionner les changements.

**Acceptance Criteria:**

**Given** un DBOPS consulte la liste des profiles
**When** il clique sur "Exporter YAML"
**Then** un fichier profiles.yaml est telecharge avec tous les profiles et leurs permissions

**Given** un DBOPS a un fichier profiles.yaml
**When** il clique sur "Importer YAML" et uploade le fichier
**Then** les profiles sont crees/mis a jour selon le contenu du fichier

**Given** le fichier YAML contient un profile existant avec des modifications
**When** l'import est execute
**Then** le profile est mis a jour (upsert par nom)

**Given** le fichier YAML contient une erreur de syntaxe
**When** l'import est execute
**Then** une erreur claire est affichee et aucun changement n'est applique

**Format YAML:**
```yaml
profiles:
  - name: Assurance
    description: Equipe assurance
    ad_group: GRP-IDP-ASSURANCE
    is_admin: false
    is_auditor: false
    actions:
      type: pattern  # ou "list"
      patterns: ["tag:oracle", "tag:provisioning"]
      # ou: list: [5, 12, 23]  # IDs d'actions
    targets:
      type: pattern  # ou "list"
      patterns: ["assurance-*"]
      # ou: list: ["assurance-srv-01", "assurance-srv-02"]
    environments: [DEV, STAGING]
```

**And** l'API GET/POST /api/v1/admin/profiles/export et /import sont implementees
**And** la validation du YAML est stricte (schema JSON)
**And** FR25d est satisfaite

### Story 2.14 : Refactoring - Supprimer l'ancien RBAC par action

As a developpeur,
I want supprimer l'ancien systeme RBAC stocke dans ACTIONS_CATALOG.rbac_policies,
So that le code soit coherent avec le nouveau modele base sur les profiles.

**Acceptance Criteria:**

**Given** l'ancien modele stockait rbac_policies dans ACTIONS_CATALOG
**When** la migration est executee
**Then** la colonne rbac_policies est supprimee de ACTIONS_CATALOG

**Given** le frontend avait un composant RbacEditor dans ActionForm
**When** le refactoring est complete
**Then** le composant RbacEditor est supprime et l'onglet "Controle d'acces" pointe vers la gestion des profiles

**Given** l'API avait un endpoint PUT /api/v1/admin/actions/{id}/rbac
**When** le refactoring est complete
**Then** l'endpoint est supprime et retourne 410 Gone avec redirection vers /admin/profiles

**Given** des tests existants testaient l'ancien RBAC
**When** le refactoring est complete
**Then** les tests sont mis a jour pour utiliser le nouveau modele

**And** les modeles Pydantic backend sont nettoyes (supprimer RbacPolicies, EnvironmentPermission)
**And** la story 2-3 est marquee comme remplacee par 2-9 a 2-13

### Story 2.17 : Editeur visuel de parametres d'action

As a DBOPS,
I want definir les parametres d'une action via un editeur visuel dynamique (ajouter/supprimer) au lieu d'un input JSON,
So that je configure les parametres de maniere intuitive sans risque d'erreur de syntaxe JSON.

**Acceptance Criteria:**

**Given** un DBOPS edite une action dans l'admin
**When** il accede a la section "Parametres"
**Then** il voit un editeur visuel avec une liste de parametres et un bouton "Ajouter un parametre"

**Given** le DBOPS clique sur "Ajouter un parametre"
**When** un nouveau parametre est ajoute
**Then** un formulaire inline s'affiche avec les champs : nom (texte), type (dropdown: string, number, boolean, date, select, etc.), requis (toggle oui/non), valeur par defaut (texte), description (texte)

**Given** le DBOPS a plusieurs parametres
**When** il veut reordonner ou supprimer un parametre
**Then** il peut drag-and-drop pour reordonner et cliquer sur l'icone X pour supprimer un parametre

**Given** le DBOPS sauvegarde l'action
**When** les parametres sont valides
**Then** le systeme genere automatiquement le JSON schema en backend et le stocke dans parameters_schema

**Given** une action existante a des parametres en JSON schema
**When** le DBOPS ouvre le formulaire d'edition
**Then** les parametres existants sont affiches dans l'editeur visuel (migration de l'affichage)

**And** la validation inline s'execute sur chaque champ (nom requis, nom unique, type requis)
**And** le composant ParametersEditor utilise le meme pattern que StepsEditor (UX coherente)
**And** FR1 (PRD mis a jour) est satisfaite pour les parametres visuels
**And** Cette story remplace l'input JSON schema de la Story 2.1

### Story 2.18 : Editeur visuel des regles d'impact

As a DBOPS,
I want definir les regles d'impact d'une action via un editeur visuel dynamique (ajouter/supprimer),
So that je configure les criteres d'evaluation du niveau de risque par environnement de maniere intuitive.

**Acceptance Criteria:**

**Given** un DBOPS edite une action dans l'admin
**When** il accede a la section "Regles d'impact"
**Then** il voit un editeur visuel avec une liste de regles par environnement et un bouton "Ajouter une regle"

**Given** le DBOPS clique sur "Ajouter une regle"
**When** une nouvelle regle est ajoutee
**Then** un formulaire inline s'affiche avec les champs : environnement (dropdown: DEV, STAGING, PROD, etc.), niveau d'impact (dropdown: faible/vert, moyen/orange, eleve/rouge), critere/justification (texte)

**Given** le DBOPS definit plusieurs regles
**When** il configure des niveaux differents par environnement
**Then** l'ImpactIndicator de la preview se met a jour dynamiquement selon l'environnement selectionne

**Given** le DBOPS veut supprimer une regle
**When** il clique sur l'icone X
**Then** la regle est supprimee de la liste

**Given** aucune regle n'est definie pour un environnement
**When** l'action est executee dans cet environnement
**Then** le niveau d'impact par defaut (configure dans l'action) s'applique

**And** la validation inline s'execute (environnement unique par regle, niveau requis)
**And** le composant ImpactRulesEditor utilise le meme pattern que ParametersEditor et StepsEditor
**And** les regles sont stockees dans impact_rules (CLOB JSON) de ACTIONS_CATALOG
**And** FR1 (PRD mis a jour) est satisfaite pour les regles d'impact visuelles
**And** Cette story remplace l'input JSON des regles d'impact de la Story 2.1

### Story 2.19 : Setup environnement Oracle dev avec Docker

As a developpeur,
I want un environnement Oracle local via Docker Compose,
So that je peux tester les operations CRUD et valider le comportement de la base de donnees en developpement.

**Acceptance Criteria:**

**Given** un developpeur clone le repo
**When** il execute `docker-compose up -d oracle`
**Then** un container Oracle Free (ou XE) demarre sur le port 1521
**And** les migrations Flyway s'appliquent automatiquement au demarrage

**Given** le container Oracle est demarre
**When** le developpeur execute les tests d'integration
**Then** les tests peuvent inserer, modifier et supprimer des donnees dans toutes les tables

**Given** le container Oracle est arrete
**When** le developpeur relance `docker-compose up -d oracle`
**Then** les donnees persistees sont restaurees (volume Docker)

**And** le fichier docker-compose.yml inclut le service Oracle avec volume persistant
**And** un script init.sql ou entrypoint applique les migrations
**And** le README documente le setup dev avec les commandes essentielles
**And** les variables d'environnement (user, password, SID) sont configurables via .env

### Story 2.20 : Refactoring migrations Flyway et Identity Columns

As a developpeur,
I want des migrations conformes aux standards Flyway et utilisant les identity columns Oracle,
So that la gestion de schema est robuste et les patterns sont modernes.

**Acceptance Criteria:**

**Given** les fichiers de migration existants
**When** ils sont renommes selon la convention Flyway
**Then** le format est `V001__description_snake_case.sql` (double underscore)

**Given** la table schema_version custom existe
**When** le refactoring est complete
**Then** la table schema_version est supprimee et Flyway utilise sa table native `flyway_schema_history`

**Given** les tables utilisent des sequences pour les IDs
**When** les migrations sont refactorees
**Then** toutes les colonnes ID utilisent `GENERATED ALWAYS AS IDENTITY` au lieu de sequences
**And** les sequences existantes sont supprimees

**Tables impactees:**
- USERS
- ACTIONS_CATALOG
- EXECUTIONS
- EXECUTION_STEPS
- AUDIT_LOG
- USER_PERMISSIONS
- TAGS
- ACTION_TAGS
- USER_FAVORITES

**And** le code backend (repositories) est mis a jour pour ne plus referencer les sequences
**And** les tests unitaires passent avec les nouvelles migrations
**And** un script de migration de donnees est fourni si necessaire

### Story 2.21 : Code modele de changement preapprouve

As a DBOPS,
I want specifier le code du modele de changement preapprouve (ex: "1516B") pour chaque action,
So that le service d'integration ServiceNow cree le changement avec le bon modele.

**Acceptance Criteria:**

**Given** un DBOPS edite une action qui necessite un changement ServiceNow
**When** il accede a la section changement
**Then** il voit un champ `change_model_code` (texte alphanumerique)

**Given** le DBOPS saisit un code
**When** le format ne respecte pas `^[A-Za-z0-9]+$`
**Then** une erreur de validation s'affiche inline

**And** migration SQL ajoute colonne `change_model_code VARCHAR(50)` nullable a `ACTIONS_CATALOG`
**And** modele Pydantic `Action` mis a jour avec champ optionnel
**And** API `PUT /api/v1/admin/actions/{id}` accepte le nouveau champ

### Story 2.22 : Wizard de creation et edition d'action

As a DBOPS,
I want creer ou editer une action via un wizard en 3 etapes,
So that l'experience soit plus guidee et moins intimidante qu'un long formulaire.

**Acceptance Criteria:**

**Given** un DBOPS clique sur "Nouvelle action" ou "Editer"
**When** le wizard s'ouvre
**Then** il affiche 3 etapes : (1) General, (2) Parametres, (3) Impact & Change

**Etape 1 - General** : nom, description, moteur, plateforme, tags
**Etape 2 - Parametres** : editeur visuel (reutilise composant Story 2.17)
**Etape 3 - Impact & Change** : regles d'impact (Story 2.18) + `change_model_code`

**Given** un DBOPS navigue entre les etapes
**When** il clique Precedent/Suivant
**Then** les donnees saisies sont conservees (state local)

**Given** un DBOPS est sur l'etape 3
**When** il clique "Enregistrer"
**Then** l'action est creee/mise a jour via l'API existante

**And** en mode edition, les champs sont pre-remplis
**And** indicateur de progression visible (stepper)
**And** validation par etape avant passage a la suivante

### Story 2.23 : Suppression de la Categorie — Tags Only

As a DBOPS,
I want que le champ Categorie soit supprime du formulaire d'action,
So that je n'utilise que les tags pour organiser et filtrer les actions (simplification).

**Acceptance Criteria:**

**Given** un DBOPS cree ou edite une action
**When** il accede au formulaire
**Then** le champ "Categorie" n'est plus present

**Given** une action existante a une categorie assignee
**When** la migration s'execute
**Then** un tag correspondant est cree automatiquement (ex: "Patching" → tag "patching")
**And** ce tag est associe a l'action

**Given** un utilisateur consulte le catalogue ou l'admin
**When** la page s'affiche
**Then** la categorie n'est plus affichee (remplacee par les tags)

**And** migration SQL : colonne `CATEGORY` devient nullable
**And** migration donnees : creation des tags a partir des categories existantes et association aux actions
**And** backend : champ `category` retire de `ActionCreate` (ou rendu optionnel temporairement)
**And** frontend : select "Categorie" supprime du formulaire ActionForm
**And** les filtres par categorie sont supprimes (utiliser filtres par tags existants)

### Story 2.24 : Changement ServiceNow conditionnel par environnement

As a DBOPS,
I want definir si un changement ServiceNow est requis pour chaque environnement et specifier le code modele par environnement,
So that je configure precisement quels environnements necessitent une ouverture de changement (souvent uniquement PROD).

**Acceptance Criteria:**

**Given** un DBOPS configure la section Changement d'une action
**When** il voit la liste des environnements
**Then** pour chaque environnement il peut activer/desactiver "Changement requis" (toggle, defaut: non)

**Given** un DBOPS active "Changement requis" pour un environnement
**When** le toggle est active
**Then** un champ "Code modele" apparait pour cet environnement
**And** le code modele est obligatoire et doit etre alphanumerique (max 50 caracteres)

**Given** un DBOPS desactive "Changement requis" pour un environnement
**When** le toggle est desactive
**Then** le champ "Code modele" disparait pour cet environnement

**Exemple de configuration:**
- DEV : Changement requis = Non
- STAGING : Changement requis = Non
- PROD : Changement requis = Oui, Code modele = "1516B"

**And** structure `change_type_config` evolue vers : `{"PROD": {"required": true, "change_model_code": "1516B"}}`
**And** migration donnees : si `change_model_code` existait au niveau action, le reporter sur les environnements qui avaient `pre_approved`
**And** le champ `change_model_code` au niveau action est supprime (deplace dans `change_type_config`)
**And** validation backend : si `required: true`, alors `change_model_code` obligatoire et alphanumerique
**And** API accepte la nouvelle structure et rejette l'ancienne avec message d'erreur clair

### Story 2.25 : Wizard de creation et edition de profil avec permissions

As a DBOPS,
I want creer ou editer un profil via un wizard en 3 etapes incluant la configuration des permissions,
So that je puisse definir les autorisations du profil directement lors de sa creation.

**Acceptance Criteria:**

**Given** un DBOPS clique sur "Nouveau profil" ou "Editer" un profil
**When** le wizard s'ouvre
**Then** il affiche 3 etapes : (1) General, (2) Permissions Actions, (3) Permissions Targets

**Etape 1 - General:**
- Nom du profil (obligatoire)
- Description (optionnel)
- Groupe AD associe (optionnel)
- Flags : Admin (toggle), Auditeur (toggle)

**Etape 2 - Permissions Actions:**
**Given** un DBOPS configure les permissions actions
**When** il selectionne le type de permission
**Then** il peut choisir parmi : "Toutes les actions", "Liste d'actions", "Pattern de tags"

**Given** le type est "Liste d'actions"
**When** le DBOPS configure
**Then** un multi-select affiche les actions existantes (publiees)

**Given** le type est "Pattern de tags"
**When** le DBOPS configure
**Then** un champ texte permet de saisir des patterns (ex: "oracle*", "provisioning")

**Given** un type de permission est selectionne
**When** le DBOPS configure les environnements
**Then** un multi-select permet de choisir les environnements autorises (DEV, STAGING, PROD, etc.)

**Etape 3 - Permissions Targets:**
**Given** un DBOPS configure les permissions targets
**When** il selectionne le type de permission
**Then** il peut choisir parmi : "Toutes les targets", "Liste de targets", "Pattern"

**Given** le type est "Liste de targets" ou "Pattern"
**When** le DBOPS configure
**Then** un champ texte libre permet de saisir les noms ou patterns (MVP : texte libre, futur : connexion API inventaire)

**Given** un DBOPS navigue entre les etapes
**When** il clique Precedent/Suivant
**Then** les donnees saisies sont conservees (state local)

**Given** un DBOPS est sur l'etape 3
**When** il clique "Enregistrer"
**Then** le profil est cree/mis a jour via les APIs existantes (POST/PUT /profiles, /profiles/{id}/action-permissions, /profiles/{id}/target-permissions)

**And** en mode edition, les champs sont pre-remplis avec les donnees et permissions existantes
**And** indicateur de progression visible (stepper)
**And** validation par etape avant passage a la suivante
**And** composants UI coherents avec le wizard actions (Story 2.22)

### Story 2.26 : Visualisation du format YAML pour import de profils

As a DBOPS,
I want voir un exemple du format YAML attendu et telecharger un template,
So that je puisse preparer correctement mon fichier d'import de profils.

**Acceptance Criteria:**

**Given** un DBOPS accede a l'interface d'import de profils
**When** la page s'affiche
**Then** un exemple YAML commente est visible dans un bloc collapsible (replie par defaut)

**Given** un DBOPS veut voir l'exemple
**When** il clique sur "Voir le format YAML"
**Then** le bloc se deplie et affiche un exemple complet avec commentaires explicatifs

**Exemple de contenu:**
```yaml
# Format d'import de profil DBOPS Portal
# Tous les champs sont optionnels sauf 'name'

name: "dba_oracle"                    # Obligatoire - Nom unique du profil
description: "DBAs Oracle production" # Description du profil
ad_group: "GRP-DBA-ORACLE"           # Groupe Active Directory associe
is_admin: false                       # Acces admin (defaut: false)
is_auditor: false                     # Acces audit (defaut: false)

action_permissions:
  type: "pattern"                     # "all" | "list" | "pattern"
  patterns: ["oracle*", "backup*"]    # Si type=pattern
  # action_ids: [1, 2, 3]            # Si type=list
  environments: ["DEV", "STAGING", "PROD"]

target_permissions:
  type: "list"                        # "all" | "list" | "pattern"
  targets: ["srv-ora-01", "srv-ora-02"]
  # patterns: ["srv-ora-*"]          # Si type=pattern
```

**Given** un DBOPS veut un fichier template
**When** il clique sur "Telecharger template"
**Then** un fichier `profile-template.yaml` est telecharge avec la structure vide/exemple

**And** le bloc exemple utilise une coloration syntaxique YAML
**And** le bouton telecharger est visible meme quand le bloc est replie

### Story 2.27 : Backend — Integrations (plateformes distantes)

As a DBOPS,
I want stocker la configuration des plateformes distantes (AAP, Terraform, ServiceNow, etc.) : type, nom, URL, reference aux credentials, icone,
So that le portail peut declarer quelles instances appeler pour declencher les executions et les afficher dans l'admin.

**Acceptance Criteria:**

**Given** une migration SQL est executee
**When** la table INTEGRATIONS est creee
**Then** elle contient au minimum : ID (identity), TYPE (aap | servicenow | terraform | azuredevops | jira | github_actions), NAME (unique), BASE_URL, CREDENTIAL_REF (reference Vault ou nom logique — aucun secret stocke, NFR7), ICON (varchar — identifiant preset ou URL d'icone), CREATED_AT, UPDATED_AT

**Given** un DBOPS appelle les API admin des integrations
**When** il fait GET /api/v1/admin/integrations
**Then** la liste des integrations est retournee (sans exposer de secret)

**Given** un DBOPS cree ou modifie une integration
**When** il fait POST /api/v1/admin/integrations ou PUT /api/v1/admin/integrations/{id}
**Then** le backend valide type, name, base_url, credential_ref (optionnel), icon (optionnel) et persiste en base

**And** les routes sont protegees par le profil DBOPS (require_profile dbops)
**And** aucun credential brut n'est stocke — uniquement credential_ref (NFR7, FR29)

### Story 2.28 : Frontend — Section Admin Integrations (liste, formulaire, icone)

As a DBOPS,
I want une section Admin « Integrations » avec liste des plateformes distantes, ajout/edition (type, nom, URL, credential ref, icone),
So that je configure les instances AAP, Terraform, etc. et leur representation visuelle (icone) depuis l'interface.

**Acceptance Criteria:**

**Given** un DBOPS accede a la page Admin
**When** il consulte les onglets
**Then** un onglet « Integrations » est visible (a cote de Actions et Profils)

**Given** un DBOPS ouvre l'onglet Integrations
**When** la page se charge
**Then** un tableau liste les integrations (colonnes : icone, nom, type, URL, date creation) avec actions Modifier / Supprimer et un bouton « Nouvelle integration »

**Given** un DBOPS clique sur « Nouvelle integration » ou « Modifier »
**When** un formulaire (ou modal) s'affiche
**Then** les champs sont : Type (select : AAP, ServiceNow, Terraform, Azure DevOps, Jira, GitHub Actions), Nom, URL de base, Reference credentials (optionnel, ex. chemin Vault ou nom logique), Icone (optionnel)

**Given** le champ Icone est configure
**When** l'utilisateur saisit une valeur
**Then** soit il selectionne un preset par type (icone associee au type : AAP, Terraform, etc.), soit il fournit une URL d'icone (image) ; l'icone choisie est affichee en apercu dans le formulaire et dans la liste

**Given** un DBOPS soumet le formulaire
**When** les validations passent (nom, URL requis ; type requis)
**Then** l'appel API POST ou PUT est envoye et la liste des integrations est rafraichie

**And** UX coherente avec les onglets Actions et Profils (Ant Design, formulaires, notifications succes/erreur)
**And** les libelles sont en francais

---

## Epic 3 : Decouverte du Catalogue (Marc)

DBA decouvre et comprend les actions disponibles a travers le catalogue avec modes d'affichage (cartes/liste), tags, favoris, recherche et fiches detaillees.

### Story 3.1 : Catalogue d'actions avec modes d'affichage et favoris

As a DBA,
I want parcourir le catalogue avec differents modes d'affichage (cartes ou liste) et acceder rapidement a mes actions favorites,
So that je navigue efficacement dans un catalogue de 100+ actions.

**Acceptance Criteria:**

**Given** un DBA authentifie accede a l'onglet Catalogue
**When** la page se charge
**Then** les actions publiees s'affichent en grille de cartes par defaut (3 colonnes sur 1280px, 4 colonnes sur 1600px+)

**Given** le DBA veut changer de mode d'affichage
**When** il clique sur le toggle "Cartes / Liste"
**Then** l'affichage bascule entre grille de cartes et vue liste (tableau avec colonnes : nom, tags, moteur, impact, executions)
**And** le mode choisi est persiste en localStorage

**Given** le catalogue affiche des actions
**When** le DBA regarde une ActionCard
**Then** chaque carte affiche : icone moteur, nom de l'action, description (2 lignes max), ImpactIndicator (couleur + icone + texte), tags (chips), nombre d'executions

**Given** le DBA veut marquer une action en favori
**When** il clique sur l'icone etoile sur une carte ou dans le drawer
**Then** l'action est ajoutee a ses favoris (stockes en base, lie au user_id)

**Given** le DBA consulte le catalogue
**When** il a des favoris
**Then** une section "Mes actions" s'affiche en haut avec ses favoris et ses actions recemment executees

**Given** le catalogue a des categories
**When** le DBA clique sur un onglet (Tout, Provisioning, Patching, Administration, Monitoring)
**Then** la grille/liste se filtre par la categorie selectionnee et le compteur se met a jour ("12 actions")

**And** le composant ActionCard est accessible (role="article", aria-label, focusable au clavier, Enter ouvre le drawer)
**And** le composant ImpactIndicator affiche triple codage (couleur + icone + texte) avec aria-label="Impact: [niveau]"
**And** le chargement affiche des skeleton cards/rows (shimmer) — pas de spinner seul
**And** le cache in-memory (TTL 5min) est utilise pour le catalogue cote backend
**And** l'API GET /api/v1/catalog/actions retourne les actions filtrees par le RBAC de l'utilisateur
**And** l'API GET /api/v1/users/me/favorites retourne les favoris de l'utilisateur
**And** l'API POST/DELETE /api/v1/users/me/favorites/{action_id} gere les favoris
**And** la table USER_FAVORITES (user_id, action_id, created_at) est creee via migration SQL
**And** FR8, FR11a et FR11b sont satisfaites

### Story 3.2 : Fiche descriptive en drawer lateral

As a DBA,
I want consulter la fiche descriptive complete d'une action dans un drawer lateral,
So that je comprenne ce que fait l'action, son impact et ses parametres avant de decider d'executer.

**Acceptance Criteria:**

**Given** un DBA clique sur une ActionCard dans le catalogue
**When** le drawer s'ouvre (480px a droite)
**Then** la fiche affiche : nom de l'action, description complete, ImpactIndicator, moteur, categorie, parametres attendus (liste avec types), et un bouton "Executer" en primary

**Given** le drawer est ouvert
**When** le DBA clique hors du drawer, sur le X ou appuie sur Escape
**Then** le drawer se ferme et le focus revient sur la carte cliquee

**Given** le DBA consulte une action qu'il ne peut pas executer dans un environnement
**When** le bouton "Executer" est visible
**Then** le bouton est desactive avec un tooltip expliquant pourquoi ("Acces non autorise pour cet environnement")

**And** le drawer est accessible : role="dialog", aria-label="Fiche action: [nom]", focus trap, Tab circule dans le contenu
**And** le chargement du detail affiche un skeleton dans le drawer
**And** l'API GET /api/v1/catalog/actions/{id} retourne la fiche complete
**And** FR9 est satisfaite

### Story 3.3 : Recherche et filtrage du catalogue par tags

As a DBA,
I want rechercher et filtrer les actions par tags, moteur, environnement, niveau d'impact ou mot-cle,
So that je trouve rapidement l'action dont j'ai besoin parmi 100+ actions.

**Acceptance Criteria:**

**Given** le DBA est sur le catalogue
**When** il tape dans la barre de recherche
**Then** les resultats se filtrent en temps reel (debounce 300ms) sur le nom, la description et les tags

**Given** le panneau de filtres lateraux (240px) est visible
**When** le DBA selectionne des tags (RAC, DATAGUARD), un moteur (Oracle), un environnement (Production), et un impact (Eleve)
**Then** les filtres se cumulent (intersection) et la grille/liste se met a jour

**Given** le DBA veut filtrer par tags
**When** il clique sur le filtre "Tags"
**Then** une liste multi-select affiche tous les tags disponibles avec le nombre d'actions par tag
**And** les tags selectionnes s'affichent comme chips sous la barre de recherche

**Given** des filtres sont actifs
**When** le DBA voit les chips sous la barre de recherche
**Then** chaque filtre actif (tag, moteur, env, impact) est represente par un chip avec bouton "X" pour le supprimer
**And** un bouton "Reinitialiser les filtres" est disponible

**Given** les filtres ne retournent aucun resultat
**When** la grille/liste est vide
**Then** un etat vide s'affiche : "Aucune action ne correspond a vos filtres" + bouton "Reinitialiser les filtres"

**And** le compteur dynamique ("12 actions") se met a jour avec aria-live="polite"
**And** la recherche et les filtres sont combines avec la categorie selectionnee (onglet)
**And** les filtres lateraux passent en panneau depliable sous 1280px
**And** l'API GET /api/v1/catalog/actions accepte les query params : q, tags (comma-separated), category, engine, environment, impact
**And** l'API GET /api/v1/tags retourne tous les tags avec leur count d'actions
**And** les resultats se chargent en < 1 seconde (NFR4, NFR23)
**And** FR11 est satisfaite

### Story 3.4 : Documentation contextuelle d'une action

As a DBA,
I want acceder a la documentation detaillee d'une action depuis sa fiche,
So that je comprenne en profondeur ce que fait l'action avant de l'executer.

**Acceptance Criteria:**

**Given** le DBA consulte la fiche d'une action dans le drawer
**When** une documentation est disponible
**Then** un onglet ou une section "Documentation" s'affiche dans le drawer avec le contenu Markdown rendu

**Given** la documentation est longue
**When** le DBA fait defiler le drawer
**Then** le contenu est scrollable dans le drawer sans affecter la page principale

**Given** aucune documentation n'est disponible
**When** le DBA consulte la section Documentation
**Then** un message "Aucune documentation disponible" s'affiche

**And** la documentation est stockee en Markdown dans la colonne description longue ou un champ dedie de ACTIONS_CATALOG
**And** le rendu Markdown supporte : titres, listes, blocs de code, tableaux
**And** FR12 est satisfaite

### Story 3.5 : Nuage de tags et clarte du bouton favori

As a DBA,
I want filtrer le catalogue par un ou plusieurs tags via un nuage de tags colore et comprendre clairement comment ajouter une action a mes favoris,
So that je navigue dans un catalogue avec beaucoup de tags sans multiplication d'onglets et j'utilise les favoris sans ambiguite.

**Acceptance Criteria:**

**Given** le DBA est sur l'onglet Catalogue (hors vue « Mes actions »)
**When** la page affiche la liste des actions
**Then** un nuage de tags (tag cloud) s'affiche au-dessus de la grille/liste, contenant tous les tags presents sur les actions du catalogue (ou les tags disponibles cote API).

**Given** le nuage de tags est affiche
**When** le DBA clique sur un tag
**Then** ce tag est selectionne (mise en evidence visuelle) et la liste des actions se filtre pour n'afficher que les actions portant ce tag. Le compteur « X actions » se met a jour (aria-live="polite").

**Given** un ou plusieurs tags sont deja selectionnes
**When** le DBA clique sur un autre tag
**Then** ce tag s'ajoute a la selection et le filtre est une intersection (AND) : seules les actions ayant tous les tags selectionnes sont affichees.

**Given** des tags sont selectionnes
**When** le DBA clique a nouveau sur un tag deja selectionne
**Then** ce tag est deselectionne et la liste se met a jour en consequence.

**Given** des tags sont selectionnes
**When** le DBA souhaite tout reinitialiser
**Then** un controle « Reinitialiser les filtres » (ou equivalent) est disponible et deselectionne tous les tags.

**Given** le DBA consulte une ActionCard (grille ou liste)
**When** il survole ou focus l'icone etoile (favori)
**Then** un tooltip s'affiche : « Ajouter aux favoris » si l'action n'est pas en favori, « Retirer des favoris » si elle l'est deja.

**Given** le bouton favori (icone etoile) est present
**Then** il possede un aria-label explicite : « Ajouter aux favoris » ou « Retirer des favoris » selon l'etat, pour l'accessibilite.

**Given** le bouton favori est affiche
**Then** l'etat visuel est net : etoile vide (ou contour) = pas en favori, etoile pleine (ou couleur distincte) = en favori.

**And** l'onglet « Mes actions » (favoris + recents) reste inchange : un seul onglet dedie, pas de modification de son comportement.
**And** FR11 et FR11b sont affines.

---

## Epic 4 : Execution & Suivi Temps Reel

DBA execute une action de bout en bout via le wizard et suit la progression etape par etape en temps reel via la timeline. Integrations Vault, ServiceNow, plateformes d'execution et inventaire incluses.

### Story 4.1 : Wizard d'execution en 3 etapes

As a DBA,
I want executer une action via un wizard guide (Environnement → Parametres → Confirmation),
So that j'avance une decision a la fois et je comprenne l'impact avant de confirmer.

**Acceptance Criteria:**

**Given** un DBA clique sur "Executer" dans le drawer d'une action
**When** le wizard s'ouvre (centre, 640px max)
**Then** le stepper affiche 3 etapes avec labels : Environnement, Parametres, Confirmation

**Given** le DBA est a l'etape 1 (Environnement)
**When** il selectionne "Production"
**Then** un badge orange avertissement s'affiche et l'ImpactIndicator se met a jour selon les regles d'impact de l'action

**Given** le DBA est a l'etape 2 (Parametres)
**When** il remplit les champs dynamiques generes depuis le parameters_schema JSON de l'action
**Then** la validation inline s'execute en temps reel sous chaque champ et le bouton "Suivant" reste desactive si la validation echoue
**And** les listes deroulantes sont pre-remplies depuis l'inventaire (bases, serveurs)

**Given** le DBA est a l'etape 3 (Confirmation)
**When** il voit le recap
**Then** s'affichent : nom de l'action, environnement, tous les parametres, ImpactIndicator, type de changement (pre-approuve / CAB)
**And** le bouton "Confirmer l'execution" est en primary

**And** le composant ExecutionWizard est accessible : aria-label="Etape [n] sur 3: [label]", navigation clavier entre etapes
**And** les donnees saisies sont conservees si l'utilisateur revient en arriere (Precedent)
**And** les labels sont toujours visibles au-dessus du champ (pas de placeholder-as-label)
**And** FR13 et FR15 sont satisfaites

### Story 4.2 : Donnees inventaire pour formulaires dynamiques

As a DBA,
I want que les listes deroulantes du wizard soient pre-remplies avec les donnees de l'inventaire interne,
So that je selectionne des valeurs valides sans saisie manuelle.

**Acceptance Criteria:**

**Given** le backend demarre
**When** la synchronisation periodique s'execute (configurable, defaut 1h)
**Then** les metadonnees de l'inventaire (bases, environnements, serveurs) sont stockees en cache in-memory

**Given** un DBA ouvre l'etape 2 du wizard
**When** un champ est de type "liste depuis inventaire"
**Then** les options sont chargees depuis l'API /api/v1/inventory/{type} et affichees en dropdown

**Given** l'inventaire est temporairement indisponible
**When** le wizard charge les options
**Then** les dernieres donnees en cache sont utilisees et un avertissement discret s'affiche

**And** la synchronisation on-demand est possible via POST /api/v1/inventory/sync (DBOPS uniquement)
**And** la performance du catalogue n'est pas impactee par la sync (NFR20)
**And** FR42 et FR43 sont satisfaites

### Story 4.2bis : Connecteur HashiCorp Vault

As a systeme,
I want un connecteur Vault qui se connecte dynamiquement a HashiCorp Vault et recupere les secrets a la demande (par chemin / credential_ref),
So that le moteur d'execution peut resoudre les credential_ref des integrations (Story 2.27) et fournir les credentials aux adapters de plateforme sans stocker de secret dans le portail.

**Acceptance Criteria:**

**Given** le backend demarre avec une config Vault valide (voir Dev Notes)
**When** le connecteur Vault est initialise
**Then** il se connecte a Vault en utilisant le "secret 0" fourni par l'environnement (VAULT_ADDR, VAULT_TOKEN ou VAULT_ROLE_ID + VAULT_SECRET_ID pour AppRole) — jamais stocke en base ni expose dans l'admin

**Given** le moteur d'execution (Story 4.3) ou un service a besoin d'un secret
**When** il appelle le connecteur avec un chemin ou credential_ref (ex. secret/data/idp/aap-prod)
**Then** le connecteur interroge Vault dynamiquement, retourne le secret (ou les champs necessaires) et ne le persiste pas

**Given** Vault est indisponible ou le secret 0 est invalide
**When** le connecteur tente de se connecter ou de recuperer un secret
**Then** une erreur explicite est remontee (ex. VaultError) et le caller peut refuser l'execution (NFR21)

**And** le connecteur est expose comme service injectable (ex. vault_service ou VaultConnector) utilise par le moteur d'execution
**And** FR17 et FR29 sont satisfaites pour la recuperation dynamique des credentials

### Story 4.3 : Moteur d'execution et facade API

As a DBA,
I want que ma soumission d'execution soit traitee par le backend qui orchestre automatiquement les etapes (Vault, plateforme, ServiceNow),
So that l'execution se lance de maniere fiable sans que je connaisse l'infrastructure sous-jacente.

**Acceptance Criteria:**

**Given** un DBA confirme l'execution au wizard
**When** le frontend envoie POST /api/v1/executions avec action_id, environment, parameters
**Then** le backend cree une entree EXECUTIONS (statut "soumis") et les EXECUTION_STEPS correspondantes
**And** la reponse retourne HTTP 201 avec l'execution_id en < 3 secondes (NFR2)

**Given** l'execution est creee
**When** le moteur d'execution demarre
**Then** il recupere les secrets necessaires via le connecteur Vault (Story 4.2bis) en resolvant les credential_ref des integrations (Story 2.27) — FR17, FR29
**And** il selectionne l'adapter de plateforme correct (Strategy Pattern) selon la plateforme definie dans l'action
**And** il appelle adapter.trigger() avec les parametres et les secrets

**Given** Vault est indisponible
**When** le moteur tente de recuperer les secrets via le connecteur Vault
**Then** l'execution est refusee avec un message explicite "Vault indisponible — execution impossible" (NFR21)
**And** le statut passe a "erreur" avec la cause dans EXECUTION_STEPS

**And** les tables EXECUTIONS et EXECUTION_STEPS (V003) sont creees via migration SQL
**And** execution_repository.py encapsule le SQL brut pour les operations CRUD
**And** le correlation ID est propage dans tous les appels (Vault, plateforme, ServiceNow)
**And** FR18, FR17 et FR29 sont satisfaites

### Story 4.4 : Adapter plateforme AAP (Ansible Automation Platform)

As a systeme,
I want declencher et suivre des executions sur AAP via un adapter dedie,
So that les actions basees AAP fonctionnent de bout en bout.

**Acceptance Criteria:**

**Given** une execution cible la plateforme AAP
**When** le moteur appelle aap_adapter.trigger()
**Then** l'adapter lance un job template AAP via l'API Tower avec les parametres extra_vars

**Given** AAP envoie un callback de statut
**When** le backend recoit POST /api/v1/callbacks/aap
**Then** l'adapter parse_callback() met a jour le statut de l'EXECUTION_STEP correspondant
**And** le callback est idempotent — un doublon ne corrompt pas l'etat (NFR18)

**Given** AAP est indisponible
**When** le moteur tente de declencher l'execution
**Then** l'EXECUTION_STEP passe en erreur avec le message "Plateforme AAP indisponible" (NFR17)
**And** les autres executions ne sont pas impactees (NFR13)

**And** l'adapter herite de base_adapter.py (interface commune: trigger(), get_status(), parse_callback())
**And** l'ajout d'un nouvel adapter ne modifie pas le moteur d'execution (NFR22)
**And** FR18 et FR23 sont satisfaites pour AAP

### Story 4.5 : Integration ServiceNow — ouverture automatique de changement

As a systeme,
I want ouvrir automatiquement un changement ServiceNow lorsqu'une etape de l'action le requiert,
So that la conformite du changement est assuree sans intervention manuelle.

**Acceptance Criteria:**

**Given** une action definit une etape "ouverture changement ServiceNow" pour l'environnement Production
**When** l'execution atteint cette etape
**Then** le moteur appelle l'API ServiceNow pour creer un changement avec les metadonnees (action, environnement, parametres, utilisateur)

**Given** le changement ServiceNow est cree
**When** le changement est pre-approuve
**Then** l'execution continue a l'etape suivante immediatement
**And** le servicenow_change_id est stocke dans EXECUTIONS

**Given** le changement requiert approbation CAB
**When** le changement est en attente d'approbation
**Then** l'EXECUTION_STEP reste en statut "en attente" et la timeline affiche "Approbation CAB en cours"

**Given** l'API ServiceNow ne repond pas dans les 30 secondes
**When** le timeout est atteint
**Then** l'etape est retentee une fois, puis passe en erreur avec message explicite (NFR19)

**And** FR16 est satisfaite

### Story 4.6 : Timeline d'execution temps reel

As a DBA,
I want suivre la progression de mon execution etape par etape en temps reel via une timeline visuelle,
So that je sais exactement ou en est l'execution a tout moment.

**Acceptance Criteria:**

**Given** un DBA confirme l'execution
**When** la timeline s'affiche (remplace le wizard)
**Then** les etapes sont listees verticalement avec leur statut : en attente (gris), en cours (bleu pulse), termine (vert check), erreur (rouge X)

**Given** une etape change de statut
**When** le backend recoit un callback ou complete une etape
**Then** le frontend recoit la mise a jour via WebSocket (/ws/executions/{id}) en < 5 secondes (NFR3)
**And** le noeud correspondant se met a jour visuellement sans refresh

**Given** le WebSocket est deconnecte
**When** la connexion est retablie
**Then** le frontend re-synchronise l'etat complet de l'execution via GET /api/v1/executions/{id}

**And** le composant ExecutionTimeline est accessible : role="list", noeuds role="listitem", aria-expanded pour le detail, aria-live="polite" pour les changements de statut
**And** les messages WebSocket suivent le format Architecture : { "type": "step_update", "execution_id", "data": { step_order, step_name, status, started_at, completed_at } }
**And** FR19 et FR23 sont satisfaites

### Story 4.7 : Resultat d'execution, logs et gestion d'erreur

As a DBA,
I want voir le resultat final de l'execution avec les logs detailles et une gestion d'erreur structuree,
So that je comprenne ce qui s'est passe et je dispose de toutes les preuves.

**Acceptance Criteria:**

**Given** l'execution se termine avec succes
**When** la timeline affiche le resultat
**Then** un bandeau vert s'affiche avec le resume de ce qui a ete fait + lien vers la trace d'audit

**Given** l'execution echoue a une etape
**When** la timeline affiche l'erreur
**Then** un StructuredErrorCard s'affiche avec : "Quoi" (etape echouee), "Pourquoi" (cause), "Options" (Relancer, Voir logs, Contacter DBA)

**Given** un DBA clique sur un noeud de la timeline
**When** le detail s'expande
**Then** les logs remontes par la plateforme s'affichent (output, parametres envoyes, reponse plateforme, duree)

**Given** un DBA clique sur "Voir logs detailles"
**When** le panneau de logs s'ouvre
**Then** les logs techniques complets de l'etape s'affichent avec horodatage

**And** le composant StructuredErrorCard est accessible : role="alert", sections aria-labelledby, focus automatique sur les options
**And** l'API GET /api/v1/executions/{id}/steps/{step_id}/logs retourne les logs
**And** FR20 et FR21 sont satisfaites

### Story 4.8 : Historique des executions

As a DBA,
I want consulter l'historique de mes propres executions,
So that je retrouve facilement les actions que j'ai lancees et leur resultat.

**Acceptance Criteria:**

**Given** un DBA accede a l'onglet Executions
**When** la page se charge
**Then** une table affiche ses executions recentes : action, environnement, statut, date, duree

**Given** le DBA clique sur une execution dans la table
**When** le detail s'ouvre
**Then** la timeline complete de l'execution s'affiche (reutilisation du composant ExecutionTimeline en mode historique)

**Given** le DBA a des executions en cours
**When** il consulte la table
**Then** les executions en cours apparaissent en haut avec un indicateur visuel (bleu pulse)

**And** l'API GET /api/v1/executions?user=me retourne les executions de l'utilisateur courant
**And** la table supporte le tri par date, statut, action
**And** la pagination est de 25 lignes par page
**And** les skeleton rows s'affichent pendant le chargement
**And** FR22 est satisfaite

---

## Epic 5 : Dashboard & Activite

DBA consulte son tableau de bord d'activite recente et les statuts d'execution depuis une vue synthetique.

### Story 5.1 : Dashboard avec statistiques et activite recente

As a DBA,
I want consulter un tableau de bord synthetique avec les chiffres cles et l'activite recente,
So that j'ai une vue d'ensemble immediate de ce qui se passe sur la plateforme.

**Acceptance Criteria:**

**Given** un DBA accede a l'onglet Dashboard
**When** la page se charge
**Then** des StatCards affichent : executions du jour, taux de succes (%), executions en cours, executions en erreur

**Given** le dashboard est charge
**When** le DBA regarde la section activite recente
**Then** une table affiche les 10 dernieres executions (tous utilisateurs visibles pour DBA) : action, utilisateur, environnement, statut, date

**Given** le DBA clique sur une execution dans la table
**When** le detail s'ouvre
**Then** la timeline complete s'affiche (reutilisation ExecutionTimeline en mode historique)

**And** l'API GET /api/v1/dashboard/stats retourne les statistiques agregees
**And** l'API GET /api/v1/dashboard/recent retourne les executions recentes
**And** le layout dashboard est en 2 colonnes sur desktop standard, 3 colonnes sur large
**And** le chargement affiche des skeleton cards et skeleton rows

### Story 5.2 : Statuts temps reel et notifications sur le dashboard

As a DBA,
I want voir les executions en cours se mettre a jour en temps reel sur le dashboard,
So that je suis alerte immediatement si une execution requiert mon attention.

**Acceptance Criteria:**

**Given** le DBA est sur le dashboard
**When** une execution en cours change de statut
**Then** la table d'activite recente se met a jour via WebSocket sans refresh

**Given** une execution est en erreur
**When** le DBA n'est pas sur le dashboard
**Then** un badge point rouge apparait sur l'onglet Dashboard dans la top bar

**Given** le DBA revient sur le dashboard
**When** il voit le badge
**Then** le badge disparait apres consultation et les executions en erreur sont mises en evidence (ligne rouge subtile)

**And** le WebSocket /ws/dashboard emet les mises a jour d'executions pertinentes pour l'utilisateur
**And** aria-live="polite" annonce les changements de statut
**And** FR41 est satisfaite

---

## Epic 6 : Audit & Conformite SOC1 (Nadia)

Le specialiste securite consulte l'historique d'execution, genere des rapports d'audit exportables et valide la conformite SOC1.

### Story 6.1 : Traces d'audit immutables pour chaque execution

As a specialiste securite,
I want que chaque execution genere automatiquement une trace d'audit immutable,
So that j'ai une preuve complete de qui a fait quoi, quand, avec quels parametres et quel resultat.

**Acceptance Criteria:**

**Given** une execution est lancee par un utilisateur
**When** l'execution demarre et progresse
**Then** des entrees d'audit sont creees automatiquement : user_id, action_type, entity_type, entity_id, parametres, resultat, autorisation RBAC appliquee, horodatage

**Given** une execution inclut une etape ServiceNow
**When** le changement ServiceNow est cree
**Then** l'entree d'audit inclut l'evidence de gestion du changement : servicenow_change_id, type de changement (pre-approuve/CAB), statut d'approbation

**Given** une entree d'audit est ecrite
**When** un utilisateur ou un processus tente de la modifier ou de la supprimer
**Then** l'operation est refusee — les entrees d'audit sont append-only (NFR8)

**And** la table AUDIT_LOG (V004) est creee via migration SQL avec contrainte INSERT-only (pas d'UPDATE, pas de DELETE via policies)
**And** l'adresse IP de l'utilisateur est enregistree dans chaque entree
**And** le correlation_id lie l'entree d'audit aux logs techniques
**And** audit_repository.py n'expose que des methodes insert() et select() — pas d'update ni delete
**And** FR30 et FR35 sont satisfaites

### Story 6.2 : Evidence specifique patching et comptes a privileges

As a specialiste securite,
I want des traces d'audit enrichies pour les operations de patching et les creations de comptes a privileges,
So that je dispose d'evidence specifique pour les controles SOC1 les plus exigeants.

**Acceptance Criteria:**

**Given** une execution de type "patching" se termine
**When** l'entree d'audit est generee
**Then** les champs additionnels sont captures : version source, version cible, resultat du patch, composants modifies

**Given** une execution de type "creation de compte a privileges" se termine
**When** l'entree d'audit est generee
**Then** les champs additionnels sont captures : justification, approbateur, scope des privileges accordes

**And** les details supplementaires sont stockes dans la colonne details (CLOB JSON) de AUDIT_LOG
**And** la structure JSON est documentee pour chaque type d'action auditable
**And** FR31 et FR32 sont satisfaites

### Story 6.3 : Consultation historique d'audit filtre

As a specialiste securite,
I want consulter l'historique d'execution avec des filtres precis (periode, environnement, action, utilisateur, resultat),
So that je trouve rapidement les executions pertinentes pour un audit.

**Acceptance Criteria:**

**Given** Nadia accede a la section Audit (sous l'onglet Executions ou page dediee)
**When** la page se charge
**Then** une table affiche toutes les executions avec : action, utilisateur, environnement, statut, date, changement ServiceNow

**Given** Nadia selectionne des filtres
**When** elle filtre par periode (date picker) + environnement "Production" + 30 derniers jours
**Then** la table se filtre en temps reel et le compteur se met a jour

**Given** Nadia clique sur une ligne
**When** le detail s'ouvre
**Then** le detail complet s'affiche : qui, quoi, quand, parametres, resultat, logs, timeline d'execution, lien vers le changement ServiceNow

**And** la table supporte le tri par colonne (clic en-tete) ascendant/descendant
**And** la pagination est de 25 lignes par page
**And** l'API GET /api/v1/audit/executions accepte les query params : from, to, environment, action_id, user_id, status
**And** les requetes d'audit supportent 10 000+ executions sans degradation (NFR24)
**And** FR33 est satisfaite

### Story 6.4 : Export rapports d'audit

As a specialiste securite,
I want exporter les donnees filtrees en CSV et PDF en un clic,
So that je genere les rapports d'audit SOC1 sans collecte manuelle.

**Acceptance Criteria:**

**Given** Nadia a applique des filtres sur la table d'audit
**When** elle clique sur "Exporter"
**Then** un menu propose deux formats : CSV et PDF

**Given** Nadia choisit CSV
**When** l'export se genere
**Then** un fichier CSV contenant toutes les colonnes de la table filtree est telecharge avec un nom standardise (audit-export-YYYY-MM-DD.csv)

**Given** Nadia choisit PDF
**When** l'export se genere
**Then** un document PDF formate est genere avec en-tete (date, filtres appliques, nombre d'enregistrements) et les donnees tabulaires

**And** l'API GET /api/v1/audit/export?format=csv|pdf avec les memes filtres que la table genere le fichier
**And** le toast notification "Rapport exporte — Telecharger" s'affiche avec lien
**And** FR34 est satisfaite

---

## Epic 7 : Self-Service Business & RBAC Granulaire (Fatima)

Les clients business executent des actions en self-service via Golden Paths guides, avec un controle d'acces granulaire et des workflows d'approbation pour la production.

### Story 7.1 : Vue catalogue simplifiee pour Client Business

As a client business,
I want parcourir une vue simplifiee du catalogue montrant uniquement les actions deleguees a mon profil,
So that je vois seulement ce que je peux faire, sans surcharge ni jargon technique.

**Acceptance Criteria:**

**Given** Fatima (profil Client Business) accede au catalogue
**When** la page se charge
**Then** seules les actions deleguees a son profil et a ses environnements autorises sont affichees (filtrage RBAC invisible)

**Given** Fatima consulte une ActionCard
**When** elle lit la description
**Then** le vocabulaire est non-technique : pas de "pipeline", "playbook", "webhook" — l'action est une boite noire

**Given** Fatima ouvre la fiche action (drawer)
**When** elle lit les details
**Then** la description est simplifiee, l'indicateur d'impact est clair (triple codage), et le bouton "Executer" est visible

**And** le filtrage RBAC s'applique cote API (GET /api/v1/catalog/actions filtre par profil + environnement)
**And** Fatima ne voit pas l'onglet Admin ni les actions DBA-only
**And** FR10 est satisfaite

### Story 7.2 : Golden Path guide pour Client Business

As a client business,
I want executer une action via un Golden Path guide avec des descriptions simples,
So that j'accomplis ma tache en autonomie sans aide d'un DBA.

**Acceptance Criteria:**

**Given** Fatima clique sur "Executer" depuis la fiche action
**When** le wizard s'ouvre
**Then** les etapes sont identiques (Environnement → Parametres → Confirmation) mais les labels et descriptions sont adaptes au profil Business (langage simple, aide contextuelle enrichie)

**Given** Fatima n'a acces qu'a l'environnement DEV
**When** elle est a l'etape 1
**Then** seul DEV est disponible (pas de choix a faire, l'environnement est pre-selectionne)

**Given** l'execution de Fatima echoue
**When** le StructuredErrorCard s'affiche
**Then** la section "Options" inclut un bouton "Contacter un DBA" en plus des options standards
**And** le message d'erreur est en langage non-technique

**And** le wizard reutilise le composant ExecutionWizard avec une variante "simplified" par profil
**And** FR14 est satisfaite

### Story 7.3 : RBAC granulaire par action, profil et environnement

As a systeme,
I want appliquer un controle d'acces granulaire combinant action, profil utilisateur et environnement cible,
So that chaque utilisateur ne voit et n'execute que ce qui lui est autorise.

**Acceptance Criteria:**

**Given** un utilisateur avec profil DBA Applicatif et droits sur l'action "Creer PDB" en DEV et STAGING
**When** il consulte le catalogue et ouvre la fiche
**Then** seuls DEV et STAGING sont disponibles dans le wizard (pas Production)

**Given** un utilisateur tente d'executer une action non autorisee via l'API
**When** POST /api/v1/executions est appele avec un action_id ou environment non autorise
**Then** le backend retourne HTTP 403 avec message "Acces non autorise"
**And** la tentative est journalisee dans AUDIT_LOG (NFR10)

**Given** les regles RBAC sont modifiees par un DBOPS (Epic 2, Story 2.3)
**When** le cache RBAC expire (TTL 1min)
**Then** les nouvelles regles s'appliquent automatiquement

**And** le middleware RBAC FastAPI est enrichi au-dela du basic DBA/DBOPS (Epic 1) pour supporter la granularite action x profil x environnement
**And** le cache RBAC in-memory (TTL 1min) est utilise pour la performance
**And** FR26 est satisfaite

### Story 7.4 : Workflow d'approbation pour la production

As a DBA,
I want approuver ou refuser les demandes d'execution en production qui le requierent,
So that les actions a fort impact sont validees par un expert avant execution.

**Acceptance Criteria:**

**Given** une action requiert approbation DBA pour la production (definie par DBOPS a l'Epic 2)
**When** un utilisateur soumet l'execution en environnement Production
**Then** l'execution passe en statut "en attente d'approbation" et le DBA approbateur est notifie

**Given** un DBA voit une execution en attente
**When** il consulte la demande (action, parametres, environnement, demandeur)
**Then** il peut "Approuver" ou "Refuser" avec un commentaire optionnel

**Given** le DBA approuve
**When** l'execution reprend
**Then** le workflow d'execution continue normalement et l'approbation est enregistree dans AUDIT_LOG

**Given** le DBA refuse
**When** le demandeur consulte son execution
**Then** le statut est "refuse" avec le commentaire du DBA

**And** l'API POST /api/v1/executions/{id}/approve et /reject gerent les decisions
**And** les notifications d'approbation en attente sont visibles dans le dashboard (badge)
**And** FR27 et FR28 sont satisfaites

---

## Epic 8 : Analytics & Scorecards

DBOPS et DBA consultent des metriques d'adoption, de performance et de tendances a travers scorecards et dashboards globaux.

### Story 8.1 : Scorecards par action

As a DBA,
I want consulter les metriques de performance d'une action (taux de succes, temps moyen, incidents),
So that je sais quelles actions sont fiables et lesquelles posent probleme.

**Acceptance Criteria:**

**Given** un DBA ouvre la fiche action dans le drawer
**When** il consulte la section "Metriques"
**Then** les scorecards affichent : taux de succes (%), temps moyen d'execution, nombre total d'executions, nombre d'incidents (echecs)

**Given** les scorecards sont affiches
**When** le DBA compare deux actions
**Then** chaque scorecard utilise un code couleur (vert > 95%, orange 80-95%, rouge < 80%) pour le taux de succes

**Given** une action n'a jamais ete executee
**When** les scorecards sont calcules
**Then** un message "Pas encore de donnees" s'affiche a la place des metriques

**And** l'API GET /api/v1/catalog/actions/{id}/stats retourne les metriques agregees
**And** les metriques sont calculees sur les 30 derniers jours par defaut
**And** FR39 est satisfaite

### Story 8.2 : Dashboards globaux DBOPS

As a DBOPS,
I want consulter des dashboards globaux montrant l'adoption, la repartition par moteur et les tendances,
So that je mesure l'impact de la plateforme et j'identifie les axes d'amelioration.

**Acceptance Criteria:**

**Given** un DBOPS accede au dashboard admin (onglet Admin → section Metriques)
**When** la page se charge
**Then** les widgets affichent : nombre total d'actions publiees, executions par moteur (graphique barres), executions par equipe/profil (graphique barres), tendance d'adoption sur 12 semaines (graphique ligne)

**Given** le DBOPS consulte la tendance d'adoption
**When** il voit le graphique ligne
**Then** l'axe X montre les semaines, l'axe Y le nombre d'executions, avec une courbe par moteur

**Given** le DBOPS veut voir une periode differente
**When** il selectionne un filtre de periode (30j, 90j, 12 mois)
**Then** tous les widgets se mettent a jour

**And** l'API GET /api/v1/admin/analytics retourne les donnees agregees avec filtre de periode
**And** les graphiques utilisent une librairie integree (Ant Design Charts ou equivalent)
**And** FR40 est satisfaite

---

## Epic 9 : Autoremediation

Le systeme detecte les echecs d'execution et propose des actions correctives depuis le catalogue, executables automatiquement pour les scenarios a faible risque.

### Story 9.1 : Detection d'echec et proposition d'actions correctives

As a systeme,
I want detecter un echec d'execution et proposer des actions correctives depuis le catalogue,
So that l'utilisateur n'est jamais dans une impasse apres un echec.

**Acceptance Criteria:**

**Given** une execution echoue a une etape
**When** le StructuredErrorCard s'affiche
**Then** la section "Options" inclut des propositions de remediation : actions du catalogue configurees comme correctives pour ce type d'echec

**Given** une action du catalogue a des regles de remediation configurees
**When** un echec correspondant se produit
**Then** le systeme identifie les actions correctives applicables (meme moteur, meme environnement, type d'erreur correspondant)

**Given** aucune action corrective n'est configuree pour ce type d'echec
**When** le StructuredErrorCard s'affiche
**Then** les options par defaut restent : "Relancer", "Voir logs", "Contacter DBA"

**And** les regles de remediation sont configurees par DBOPS dans ACTIONS_CATALOG (champ remediation_rules CLOB JSON)
**And** l'API GET /api/v1/executions/{id}/remediation retourne les actions correctives applicables
**And** FR36 est satisfaite

### Story 9.2 : Declenchement manuel d'action corrective par DBA

As a DBA,
I want evaluer et declencher une action corrective proposee depuis la timeline d'erreur,
So that je corrige le probleme rapidement sans quitter le portail.

**Acceptance Criteria:**

**Given** le DBA voit des propositions de remediation dans le StructuredErrorCard
**When** il clique sur une action corrective proposee
**Then** le wizard d'execution s'ouvre pour l'action corrective avec les parametres pre-remplis (environnement, contexte de l'echec)

**Given** le DBA confirme l'execution corrective
**When** l'execution corrective se lance
**Then** elle est liee a l'execution originale (parent_execution_id) dans EXECUTIONS
**And** la timeline de l'execution originale affiche un lien vers l'execution corrective

**Given** l'action corrective reussit
**When** le DBA revient a l'execution originale
**Then** le statut affiche "Echec — corrige par [action corrective]" avec lien

**And** l'API POST /api/v1/executions avec parent_execution_id lie les executions
**And** l'audit trace la remediation : execution originale, echec, action corrective, resultat
**And** FR37 est satisfaite

### Story 9.3 : Execution automatique corrective pour faible risque

As a systeme,
I want executer automatiquement des actions correctives pour les scenarios configures comme faible risque,
So that les echecs mineurs sont corriges sans intervention humaine.

**Acceptance Criteria:**

**Given** une action du catalogue a une regle de remediation marquee "auto" avec un niveau de risque "faible"
**When** l'execution echoue avec le type d'erreur correspondant
**Then** le systeme lance automatiquement l'action corrective sans intervention utilisateur

**Given** l'auto-remediation se lance
**When** la timeline de l'execution originale se met a jour
**Then** un noeud supplementaire apparait : "Auto-remediation en cours — [nom action corrective]"

**Given** l'auto-remediation echoue
**When** le systeme ne peut pas corriger automatiquement
**Then** l'execution revient au mode manuel : StructuredErrorCard avec propositions de remediation + notification DBA

**And** DBOPS configure les regles d'auto-remediation : type d'erreur, action corrective, niveau de risque (faible uniquement), environnements autorises
**And** l'auto-remediation n'est jamais declenchee en Production sans approbation DBA
**And** chaque auto-remediation est tracee dans AUDIT_LOG
**And** FR38 est satisfaite

---

## Epic 10 : Documentation IA, Communication & Interface Conversationnelle

Le systeme auto-genere la documentation des actions, les clients demandent conseil DBA depuis le portail, et les utilisateurs decouvrent des actions via une interface IA conversationnelle.

### Story 10.1 : Auto-generation de documentation via IA

As a DBOPS,
I want que le systeme genere automatiquement la documentation d'une action a partir du readme de l'automatisation sous-jacente,
So that la documentation du catalogue est toujours a jour sans effort manuel.

**Acceptance Criteria:**

**Given** un DBOPS cree ou edite une action dans l'admin
**When** il clique sur "Generer la documentation" et fournit l'URL du repository ou le contenu du readme
**Then** le systeme analyse le readme via un modele IA et genere une documentation structuree : description, prerequis, parametres, comportement par environnement, exemples

**Given** la documentation est generee
**When** le DBOPS la consulte dans le formulaire admin
**Then** il peut la modifier avant de sauvegarder (generation assistee, pas autonome)

**Given** le readme de l'automatisation est mis a jour
**When** le DBOPS relance la generation
**Then** la documentation est regeneree avec les deltas identifies

**And** l'API POST /api/v1/admin/actions/{id}/generate-docs envoie le contenu au service IA
**And** le modele IA est appele via API (Azure OpenAI ou equivalent interne)
**And** la documentation generee est en Markdown
**And** FR7 est satisfaite

### Story 10.2 : Demande de consultation expert DBA

As a client business,
I want demander une consultation expert DBA directement depuis le portail,
So that j'obtiens de l'aide sans quitter l'outil ni creer un ticket JIRA.

**Acceptance Criteria:**

**Given** Fatima est sur le portail (catalogue, fiche action, ou apres un echec)
**When** elle clique sur "Contacter un DBA"
**Then** un formulaire s'ouvre avec : sujet (pre-rempli selon le contexte : action, execution, erreur), description, urgence

**Given** Fatima soumet la demande
**When** le formulaire est envoye
**Then** une notification est envoyee au DBA de garde (email ou integration existante) avec le contexte complet (action, execution, erreur si applicable)
**And** Fatima voit un message de confirmation avec un numero de reference

**Given** le DBA repond
**When** la reponse est disponible
**Then** Fatima est notifiee dans le portail (badge sur son profil)

**And** l'API POST /api/v1/consultations cree la demande
**And** le contexte (action_id, execution_id) est automatiquement attache
**And** FR44 est satisfaite

### Story 10.3 : Interface IA conversationnelle pour decouverte d'actions

As a utilisateur du portail,
I want decouvrir des actions en posant des questions en langage naturel,
So that je trouve la bonne action meme si je ne connais pas le nom exact ni la categorie.

**Acceptance Criteria:**

**Given** un utilisateur ouvre l'interface conversationnelle (accessible depuis la top bar)
**When** il tape "je dois creer une base Oracle pour mon projet"
**Then** le systeme repond avec les actions pertinentes du catalogue : "Creer PDB" avec un resume, lien vers la fiche, et indication d'impact

**Given** l'utilisateur pose une question ambigue
**When** le systeme ne trouve pas de correspondance exacte
**Then** il pose des questions de clarification : "Quel moteur ? Quel environnement ?"

**Given** l'utilisateur demande une action qui n'existe pas
**When** le systeme cherche dans le catalogue
**Then** il repond "Aucune action correspondante trouvee" avec une suggestion de contacter un DBA

**And** le service IA utilise le catalogue comme base de connaissances (RAG ou prompt engineering sur les metadonnees du catalogue)
**And** les reponses sont filtrees par le RBAC de l'utilisateur — l'IA ne propose jamais une action non autorisee
**And** l'interface conversationnelle est un panneau lateral ou un widget en bas de page
**And** FR45 est satisfaite
