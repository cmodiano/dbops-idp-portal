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
| FR7 | [SUPPRIMÉ] | Auto-generation documentation IA - Epic 10 supprimé |
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
| FR44 | [SUPPRIMÉ] | Consultation expert DBA depuis portail - Epic 10 supprimé |
| FR45 | [SUPPRIMÉ] | Interface IA conversationnelle - Epic 10 supprimé |

**Couverture : 50/53 FR mappees (incluant FR11a-c, FR25a-d, FR26a). FR7, FR44, FR45 non couverts (Epic 10 supprimé).**

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

### Epic 13 : Selection de targets a l'execution et permissions par environnement (inventaire)
Aujourd'hui les actions ne permettent pas de choisir explicitement un target (serveur/base) a l'execution ; l'environnement est associe a l'action alors qu'il doit etre derive du target dans l'inventaire. Cet epic introduit la selection de target(s) dans le wizard d'execution, aligne les permissions sur le modele "environnement = propriete du target" et "une action, des targets autorises par profil (env + pattern/liste)".
**FRs couvertes :** FR26, FR26a, FR43 (selection target, inventaire, RBAC aligne)
**Phase :** Growth (Phase 2)
**Reference :** implementation-artifacts/regles-metier-permissions-par-target-et-environnement.md

### Epic 14 : Moteur Ops “targets-first” + robustesse d'execution + scalabilite (Oracle)
Construire un moteur ops de niveau production dans `idp-portal` en complement d'Epic 13 : persistance relationnelle des targets (execution + scheduling), validation uniforme via registre, retries/backoff, dependances/mutex, **validation maintenance windows via inventaire (sans stockage portail)**, audit moteur corrélé, et scalabilite Oracle (partitionnement + retention + index).
**FRs couvertes :** FR15, FR19, FR22, FR30, FR33 (guardrails moteur + traçabilite + perf)
**Phase :** Growth (Phase 2) -> Scale (Phase 3)
**Reference :** planning-artifacts/epic-14-moteur-ops-et-scalabilite.md

### Epic 15 : Audit de Securite et Conformite SOC1 (premiere release)
Le specialiste securite et l'equipe technique valident que le portail respecte les exigences de securite (NFR6-NFR11) et la conformite SOC1 avant la premiere release en production. Un audit complet du code, des configurations, des tests de securite et de la documentation est realise avec un plan de remédiation pour les vulnerabilites identifiees.
**FRs couvertes :** FR24, FR25, FR26, FR29, FR30, FR33 (securite + audit)
**NFRs couvertes :** NFR6, NFR7, NFR8, NFR9, NFR10, NFR11
**Phase :** Release (pre-production)
**Reference :** Compliance SOC1, exigences securite premiere release

### Epic 18 : Ameliorations UX et corrections issues du feedback utilisateurs
Corrections et ameliorations basees sur le feedback terrain : admin actions (suppression/désactivation/filtres), identification workflow vs action, mode visuel builder (taille, blocs, lien, libellé), filtre Environnement catalogue, favoris, statut erreur intégration.
**FRs couvertes :** FR6, FR11, FR19 (cycle de vie actions, catalogue, statuts)
**Phase :** Growth (Phase 2)

### Epic 19 : UX — Vue d'exécution temps réel
Remplacer le popup « action démarrée » par une vue d'exécution immersive : pour une action simple, timeline avec logs détaillés et indicateur d'étape active ; pour un workflow, aperçu visuel du graphe avec étape active, et clic sur une étape pour afficher la timeline et les logs en direct de cette action.
**FRs couvertes :** FR19, FR20, FR21 (suivi temps réel, logs plateforme, logs techniques)
**Phase :** Growth (Phase 2)
**Reference :** planning-artifacts/epic-19-ux-vue-execution-temps-reel.md

### Epic 20 : Action items et suivi — Restant des stories « done »
Consolider et implémenter les action items, follow-ups et known issues documentés dans les stories déjà marquées done : fixtures User, validation M-4, retry Celery, ExecutionWizard Phase 4, Epic M rétrospective, 5-7 tasks restantes, M-10/17-12 follow-ups, 15-4/17-16 documentation.
**Phase :** Tech Debt / Quality — Amélioration continue
**Reference :** planning-artifacts/epic-20-action-items-et-suivi-stories-done.md

### Epic 21 : Inventaire — source unique des environnements
Supprimer la normalisation des environnements et utiliser l'inventaire comme seule source de vérité. Accepter toute valeur présente dans l'inventaire (ex. lab, dev, staging, prod), éliminer la récursion et les cascades Oracle, permettre l'ajout de nouveaux environnements sans migration.
**FRs couvertes :** FR43 (inventaire), FR26 (RBAC environnements)
**Phase :** Growth (Phase 2)
**Reference :** planning-artifacts/epic-21-inventaire-source-unique-environnements.md

### Epic 23 : Inventaire multi-tables (SERVER, INSTANCE, DB) et UX cibles
Étendre l'inventaire pour supporter les tables SERVER, INSTANCE et DB avec relations, filtrer les listes instance/DB par serveur choisi dans le wizard, permettre aux profils d'accorder l'accès « tous les serveurs Oracle » ou « tous les serveurs SQL », avec un modèle d'accès évolutif (mapping colonnes) et un RBAC intimement lié aux données d'inventaire.
**FRs couvertes :** FR42, FR43, FR25b, FR26/FR26a (extension inventaire multi-tables, RBAC par attributs)
**Phase :** Growth (Phase 2)
**Reference :** docs/inventaire-multi-tables-ux-cibles.md

### Epic 24 : Intégrations Admin alignées sur le backend
Encadrer la configuration des intégrations dans l'interface Admin pour n'autoriser que des types et des actions d'intégration explicitement supportés par le backend (AAP, ServiceNow, etc.), via un modèle "type d'intégration" + "instance d'intégration" et un catalogue d'actions contractuel.
**FRs couvertes :** FR18 (facade plateformes d'exécution), FR42, FR43 (cohérence inventaire / intégrations)
**NFRs couvertes :** NFR17, NFR18, NFR19, NFR20, NFR22 (robustesse intégrations, plugin/adapter)
**Phase :** Growth (Phase 2)

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

### Story 2.29 : Separation boutons creation action et workflow dans admin

As a DBOPS,
I want avoir deux boutons distincts "Nouvelle action" et "Nouveau workflow" dans l'admin,
So que la distinction entre action et workflow soit plus claire et que je n'aie pas a choisir le type dans le wizard.

**Contexte :** Actuellement, un seul bouton "Nouvelle action" ouvre ActionWizard avec un Radio.Group pour choisir entre "Action" et "Workflow". Cette separation ameliore la clarte de l'interface.

**Acceptance Criteria:**

**Given** un DBOPS accede a l'onglet Admin > Actions,
**When** il consulte la barre d'actions,
**Then** il voit deux boutons distincts :
- **"Nouvelle action"** (primary, bleu) avec icone `PlusOutlined`
- **"Nouveau workflow"** (secondary, outlined) avec icone `ApartmentOutlined` ou `DeploymentUnitOutlined`

**Given** un DBOPS clique sur "Nouvelle action",
**When** le wizard ActionWizard s'ouvre,
**Then** le type `item_type` est pre-selectionne a "action"
**And** le Radio.Group pour choisir le type est masque ou desactive (non modifiable)
**And** les champs specifiques aux workflows (WorkflowStepsEditor) ne sont pas affiches

**Given** un DBOPS clique sur "Nouveau workflow",
**When** le wizard ActionWizard s'ouvre,
**Then** le type `item_type` est pre-selectionne a "workflow"
**And** le Radio.Group pour choisir le type est masque ou desactive (non modifiable)
**And** les champs specifiques aux actions (engine, platform) ne sont pas affiches
**And** le WorkflowStepsEditor est affiche a l'etape 2

**Given** un DBOPS edite une action existante,
**When** le wizard s'ouvre en mode edition,
**Then** le Radio.Group reste masque/desactive (le type ne peut pas etre modifie apres creation)
**And** les champs affiches correspondent au type de l'action (action ou workflow)

**And** ActionWizard accepte un prop optionnel `initialItemType?: 'action' | 'workflow'` pour pre-selectionner le type
**And** si `initialItemType` est fourni, le Radio.Group est masque et le type est fixe
**And** si `initialItemType` n'est pas fourni (compatibilite retroactive), le Radio.Group reste visible comme avant
**And** AdminPage passe `initialItemType="action"` pour "Nouvelle action" et `initialItemType="workflow"` pour "Nouveau workflow"

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

### Story 5.8 : Visualiseur de workflow (flowchart)

As a DBA ou DBOPS,
I want visualiser un workflow comme un diagramme de flux avec les etapes et les conditions de passage,
So que je comprenne rapidement la structure et le flux d'execution d'un workflow complexe.

**Contexte :** Les workflows peuvent contenir plusieurs etapes. Actuellement, les workflows sont lineaires (etapes sequentielles), mais a l'avenir ils pourront avoir des branches conditionnelles (succes/erreur). Un visualiseur simple et lisible aide a comprendre rapidement la structure d'un workflow.

**Acceptance Criteria:**

**Given** un DBA ou DBOPS consulte un workflow dans le catalogue ou l'admin,
**When** il ouvre le drawer de detail ou la page d'edition,
**Then** un onglet ou section "Visualisation" affiche un diagramme de flux du workflow
**And** le diagramme montre :
  - Les etapes du workflow comme des noeuds (avec nom de l'action referencee)
  - Les connexions entre etapes comme des fleches
  - L'ordre d'execution (de gauche a droite ou de haut en bas)
  - Les conditions de passage si disponibles (fleche verte pour succes, fleche rouge pour erreur)

**Given** un workflow lineaire (etapes sequentielles),
**When** le visualiseur affiche le workflow,
**Then** les etapes sont affichees en sequence avec des fleches simples entre elles
**And** chaque noeud affiche : numero d'ordre, nom de l'action referencee, icone de la technologie

**Given** un workflow avec branches conditionnelles (futur),
**When** le visualiseur affiche le workflow,
**Then** les branches sont affichees avec des fleches colorees :
  - Fleche verte pour le chemin de succes
  - Fleche rouge pour le chemin d'erreur
  - Fleche bleue pour le chemin "toujours" (si applicable)

**Given** le visualiseur affiche un workflow,
**When** le workflow contient beaucoup d'etapes (10+),
**Then** le diagramme est zoomable et pannable pour naviguer
**And** un bouton "Vue d'ensemble" permet de voir tout le workflow en une seule vue

**Given** le visualiseur affiche un workflow,
**When** un utilisateur survole ou clique sur un noeud d'etape,
**Then** un tooltip ou panneau affiche les details de l'action referencee :
  - Nom complet de l'action
  - Description
  - Moteur et plateforme
  - Parametres requis (si disponibles)

**Given** le visualiseur affiche un workflow,
**When** le workflow est en cours d'execution,
**Then** les etapes executees sont mises en evidence (couleur verte pour succes, rouge pour echec)
**And** l'etape en cours est mise en evidence avec une animation ou couleur distincte

**And** le visualiseur utilise une bibliotheque legere (ex: Mermaid, React Flow, ou diagramme SVG custom)
**And** le format est simple et lisible (eviter la complexite visuelle d'AAP qui peut devenir "un mess")
**And** le visualiseur est accessible : navigation clavier, labels ARIA, contraste suffisant

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

### Story 4.11 : Delegation d'autorisation pour execution de workflows (actions referencees)

As a systeme,
I want permettre l'execution de workflows contenant des actions referencees meme si l'utilisateur n'a pas acces direct a ces actions,
So que les workflows multitechnologies puissent etre executes par delegation d'autorisation.

**Contexte :** Les workflows peuvent contenir des actions de plusieurs technologies (Oracle, SQL Server, etc.). Un utilisateur peut voir un workflow s'il a acces au workflow lui-meme (via tags/ID). **Lors de l'execution, le workflow delegue l'autorisation d'executer les actions referencees** : si l'utilisateur a acces au workflow, il peut executer toutes les actions referencees meme s'il n'a pas acces direct a ces actions.

**Regles metier :**
- **Visibilite** : Un utilisateur voit un workflow s'il a acces au workflow lui-meme (comportement actuel, pas de changement)
- **Execution** : Un utilisateur peut executer un workflow s'il a acces au workflow. Les actions referencees sont executees avec les permissions du workflow (delegation d'autorisation). **Pas besoin de verifier les permissions individuelles sur chaque action referencee.**
- **Affichage** : Pas d'avertissement dans le catalogue si l'utilisateur n'a pas acces a toutes les actions referencees

**Cas d'usage :** Un utilisateur Oracle peut executer un workflow contenant des actions SQL Server s'il a acces au workflow. C'est une delegation : le workflow "delegue" l'autorisation d'executer les actions referencees.

**Acceptance Criteria:**

**Given** un utilisateur tente d'executer un workflow,
**When** l'execution est soumise (POST /api/v1/executions),
**Then** le backend charge les etapes du workflow (workflow_steps avec referenced_action_id)
**And** pour chaque action referencee, le backend verifie seulement :
  - Que l'action existe (404 si non trouvee)
  - Que l'action est publiee (400 si status != 'published')
**And** **PAS de verification des permissions RBAC individuelles** sur les actions referencees (delegation)

**Given** un utilisateur tente d'executer un workflow contenant des actions referencees,
**When** toutes les actions referencees sont validees avec succes (existence + statut publie),
**Then** l'execution du workflow peut proceder normalement
**And** chaque action referencee est executee dans l'ordre **avec les permissions du workflow** (delegation)
**And** **aucune verification RBAC supplementaire** n'est effectuee lors de l'execution de chaque action referencee

**Given** un utilisateur Oracle exécute un workflow contenant des actions SQL Server,
**When** l'utilisateur a acces au workflow (mais pas aux actions SQL Server individuelles),
**Then** le workflow peut etre execute avec succes
**And** les actions SQL Server referencees sont executees grace a la delegation du workflow

**Given** un utilisateur consulte un workflow dans le catalogue,
**When** il voit le workflow (acces via tags/ID du workflow),
**Then** aucune verification supplementaire n'est effectuee sur les actions referencees
**And** aucun avertissement n'est affiche concernant les permissions sur les actions referencees

**Given** un utilisateur tente d'executer un workflow,
**When** une action referencee n'existe plus (supprimee),
**Then** l'execution est rejetee avec HTTP 404
**And** le message d'erreur indique : "L'action referencee '{action_id}' n'existe plus ou n'est plus disponible"

**Given** un utilisateur tente d'executer un workflow,
**When** une action referencee n'est plus publiee (status != 'published'),
**Then** l'execution est rejetee avec HTTP 400
**And** le message d'erreur indique : "L'action referencee '{action_name}' n'est plus publiee (statut: {status})"

**And** la validation est effectuee avant la creation de l'execution (pas apres le debut de l'execution)
**And** l'audit log enregistre la tentative d'execution avec le resultat de la validation (succes ou echec avec raison)
**And** l'audit log indique que les actions referencees sont executees avec delegation (permissions du workflow)
**And** les tests couvrent les scenarios : workflow multitechnologie avec delegation, action supprimee, action non publiee

### Story 4.12 : Parametres par etape lors de l'execution de workflows

As a DBA,
I want specifier les parametres pour chaque action referencee dans un workflow lors de l'execution,
So que chaque action du workflow recoive ses parametres specifiques.

**Contexte :** Les workflows n'ont pas de parametres directement car ce sont les actions referencees qui ont des parametres. Lors de l'execution d'un workflow, il faut pouvoir specifier les parametres pour chaque action referencee.

**Acceptance Criteria:**

**Given** un DBA execute un workflow (item_type='workflow'),
**When** le wizard d'execution s'ouvre,
**Then** l'etape 2 (Parametres) affiche une section pour chaque etape du workflow
**And** chaque section affiche le nom de l'action referencee et son formulaire de parametres dynamique (depuis parameters_schema de l'action referencee)

**Given** le DBA remplit les parametres pour chaque etape du workflow,
**When** il valide l'etape 2,
**Then** les parametres sont valides selon le schema de chaque action referencee
**And** le bouton "Suivant" est active seulement si tous les formulaires sont valides

**Given** le DBA confirme l'execution du workflow,
**When** l'execution est soumise (POST /api/v1/executions),
**Then** le backend recoit les parametres par etape dans le format : `workflow_step_parameters: { step_order: { parameters: {...} } }`
**And** chaque action referencee est executee avec ses parametres specifiques

**Given** une action referencee dans le workflow n'a pas de parametres (parameters_schema null ou vide),
**When** le wizard affiche l'etape correspondante,
**Then** aucun formulaire n'est affiche pour cette etape (message informatif : "Cette action n'a pas de parametres")

**Given** le DBA navigue entre les etapes du wizard,
**When** il revient a l'etape 2 (Parametres),
**Then** tous les parametres saisis pour chaque etape du workflow sont conserves

**And** l'API POST /api/v1/executions accepte le champ optionnel `workflow_step_parameters` pour les workflows
**And** le moteur d'execution passe les bons parametres a chaque action referencee lors de l'execution du workflow
**And** les parametres sont traces dans l'audit log pour chaque action referencee executee

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

### Story 8.3 : Dashboard de reporting avec statistiques par technologie et environnement

As a DBA,
I want consulter un dashboard de reporting avec des statistiques agregees par technologie (moteur) et par environnement,
So that je comprends les tendances d'utilisation et les problemes par plateforme et environnement.

**Acceptance Criteria:**

**Given** un DBA accede a l'onglet Dashboard
**When** la page se charge
**Then** le dashboard affiche uniquement des statistiques et graphiques (pas de table d'executions recentes)

**Given** le dashboard est charge
**When** le DBA consulte les statistiques
**Then** des StatCards affichent : executions du jour, taux de succes (%), executions en cours, executions en erreur

**Given** le DBA consulte les graphiques
**When** il voit la section "Repartition par technologie"
**Then** un graphique en barres affiche le nombre d'executions par moteur (AAP, Terraform, ServiceNow, etc.) sur la periode selectionnee

**Given** le DBA consulte les graphiques
**When** il voit la section "Repartition par environnement"
**Then** un graphique en barres affiche le nombre d'executions par environnement (dev, staging, prod) sur la periode selectionnee

**Given** le DBA consulte les tendances
**When** il voit le graphique temporel
**Then** un graphique ligne affiche les executions sur les 14 derniers jours avec une courbe par statut (succes, echec) et optionnellement par technologie

**Given** le DBA veut filtrer les donnees
**When** il selectionne une periode (7j, 14j, 30j, 90j)
**Then** tous les widgets et graphiques se mettent a jour avec les donnees de la periode selectionnee

**And** l'API GET /api/v1/dashboard/stats accepte des parametres de filtre (period, engine, environment)
**And** l'API GET /api/v1/dashboard/stats-by-technology retourne les executions groupees par moteur
**And** l'API GET /api/v1/dashboard/stats-by-environment retourne les executions groupees par environnement
**And** la table "Recent Executions" est retiree du Dashboard (redondante avec la page Executions)
**And** un lien "Voir toutes les executions" redirige vers la page Executions

### Story 8.4 : Filtres avances pour le dashboard de reporting

As a DBA,
I want appliquer des filtres avances sur le dashboard (technologie, environnement, tags, periode personnalisee),
So that je peux analyser des sous-ensembles specifiques d'executions.

**Acceptance Criteria:**

**Given** un DBA consulte le dashboard
**When** il ouvre le panneau de filtres avances
**Then** les filtres disponibles sont : periode (date debut/fin), technologie (moteur), environnement, tags d'actions, statut d'execution

**Given** le DBA selectionne un filtre technologie
**When** il choisit "AAP" dans le selecteur
**Then** tous les widgets et graphiques se mettent a jour pour afficher uniquement les executions AAP

**Given** le DBA selectionne un filtre environnement
**When** il choisit "prod" dans le selecteur
**Then** tous les widgets et graphiques se mettent a jour pour afficher uniquement les executions en production

**Given** le DBA selectionne plusieurs filtres simultanement
**When** il combine technologie + environnement + periode
**Then** tous les filtres sont appliques en AND (intersection)

**Given** le DBA a applique des filtres
**When** il clique sur "Reinitialiser"
**Then** tous les filtres reviennent aux valeurs par defaut et les widgets se mettent a jour

**Given** le DBA a applique des filtres
**When** il partage l'URL du dashboard
**Then** les filtres sont preserves dans les parametres de requete URL (query params)

**And** l'API GET /api/v1/dashboard/stats accepte les parametres query : engine, environment, tags[], status, from_date, to_date
**And** l'API GET /api/v1/dashboard/stats-by-technology accepte les memes filtres
**And** l'API GET /api/v1/dashboard/stats-by-environment accepte les memes filtres
**And** les filtres sont persistes dans le localStorage pour la session utilisateur

### Story 8.5 : Export de rapports analytics

As a DBA,
I want exporter les statistiques du dashboard en CSV ou PDF,
So that je peux partager des rapports avec mon equipe ou les archiver.

**Acceptance Criteria:**

**Given** un DBA consulte le dashboard avec des filtres appliques
**When** il clique sur le bouton "Exporter"
**Then** un menu propose : "Exporter en CSV", "Exporter en PDF"

**Given** le DBA selectionne "Exporter en CSV"
**When** le fichier est genere
**Then** le CSV contient : periode, statistiques globales (executions_jour, taux_succes, etc.), repartition par technologie, repartition par environnement, tendances temporelles (series de dates)

**Given** le DBA selectionne "Exporter en PDF"
**When** le fichier est genere
**Then** le PDF contient : titre du rapport avec date de generation, periode analysee, filtres appliques, graphiques (StatCards, barres, ligne), tableau de donnees detaillees

**Given** le DBA exporte un rapport
**When** le fichier est telecharge
**Then** le nom du fichier inclut la date et l'heure : "dashboard-report-2026-02-01-14-30.csv"

**Given** le DBA exporte avec des filtres actifs
**When** le rapport est genere
**Then** les filtres sont documentes dans le rapport (section "Parametres d'analyse")

**And** l'API GET /api/v1/dashboard/export/csv accepte les memes parametres de filtre que /stats
**And** l'API GET /api/v1/dashboard/export/pdf accepte les memes parametres de filtre que /stats
**And** le backend genere le CSV avec pandas ou equivalent
**And** le backend genere le PDF avec reportlab ou weasyprint (ou frontend avec jsPDF + html2canvas)

### Story 8.6 : Comparaisons et analyses avancees

As a DBA,
I want comparer les performances entre technologies, environnements ou periodes,
So that j'identifie les meilleures pratiques et les axes d'amelioration.

**Acceptance Criteria:**

**Given** un DBA consulte le dashboard
**When** il selectionne le mode "Comparaison"
**Then** une interface permet de selectionner deux dimensions a comparer : technologie vs technologie, environnement vs environnement, ou periode vs periode

**Given** le DBA compare deux technologies
**When** il selectionne "AAP" vs "Terraform"
**Then** un graphique compare cote a cote : taux de succes, temps moyen d'execution, nombre d'executions, nombre d'incidents

**Given** le DBA compare deux environnements
**When** il selectionne "dev" vs "prod"
**Then** un graphique compare cote a cote les memes metriques par environnement

**Given** le DBA compare deux periodes
**When** il selectionne "Semaine derniere" vs "Semaine actuelle"
**Then** un graphique compare cote a cote les tendances sur les deux periodes avec indicateurs de variation (delta %)

**Given** le DBA consulte une comparaison
**When** il voit les resultats
**Then** les differences significatives sont mises en evidence visuellement (couleurs, badges de variation)

**Given** le DBA veut analyser les causes d'une difference
**When** il clique sur une metrique dans la comparaison
**Then** un drawer s'ouvre avec la liste des executions correspondantes (filtrees) avec possibilite d'aller vers le detail

**And** l'API GET /api/v1/dashboard/compare accepte les parametres : dimension (technology|environment|period), value1, value2, metrics[] (success_rate, avg_time, etc.)
**And** l'API retourne les metriques pour chaque dimension avec les deltas de variation
**And** les graphiques de comparaison utilisent des barres groupees ou des lignes doubles selon le type de comparaison

### Story 8.7 : Navigation par categories avec tabs et filtres integres

As a DBA,
I want naviguer dans le catalogue par categories (tabs) et affiner avec des tags et filtres,
So that je trouve rapidement les actions par type d'operation sans avoir besoin d'un drawer de filtres separe.

**Acceptance Criteria:**

**Given** un DBA accede au catalogue
**When** la page se charge
**Then** des tabs de categories s'affichent en haut : "Tout", "Provisioning", "Patching", "Administration", "Monitoring", "Backup", "Mes actions"

**Given** le DBA selectionne une categorie (ex: "Patching")
**When** il clique sur le tab
**Then** seules les actions ayant un tag correspondant a la categorie s'affichent (ex: tag "patching")

**Given** le DBA est sur une categorie
**When** il voit les tags disponibles sous les tabs
**Then** un TagCloud affiche uniquement les tags pertinents pour cette categorie avec leurs compteurs

**Given** le DBA veut filtrer davantage
**When** il selectionne des tags dans le TagCloud
**Then** les filtres se cumulent avec la categorie active (intersection)

**Given** le DBA veut filtrer par moteur, environnement ou impact
**When** il consulte la barre de filtres horizontale sous les tabs
**Then** des Select compacts s'affichent : Moteur, Environnement, Impact (remplace le drawer lateral)

**Given** le DBA applique plusieurs filtres (categorie + tags + moteur)
**When** il consulte les resultats
**Then** tous les filtres actifs sont visibles comme chips sous la barre de filtres avec possibilite de les supprimer individuellement

**Given** le drawer de filtres lateral existait
**When** cette story est implementee
**Then** le drawer est supprime et remplace par la barre de filtres horizontale integree

**And** les categories sont mappees a des tags specifiques : "provisioning", "patching", "administration", "monitoring", "backup"
**And** l'API GET /api/v1/catalog/actions accepte un parametre `category` qui filtre par tag correspondant
**And** l'API GET /api/v1/catalog/tags accepte un parametre `category` pour retourner uniquement les tags de cette categorie
**And** le tab "Tout" affiche toutes les actions sans filtre de categorie
**And** le tab "Mes actions" affiche les favoris et recents (comportement existant)

### Story 8.9 : Tabs "Toutes les executions" et "Mes executions" sur la page Executions

As a DBA,
I want voir toutes les executions auxquelles j'ai acces ou uniquement mes propres executions via des tabs,
So that je peux choisir entre une vue globale (pour supervision) ou une vue personnelle (pour mes actions).

**Acceptance Criteria:**

**Given** un DBA accede a la page Executions
**When** la page se charge
**Then** deux tabs s'affichent : "Toutes les executions" et "Mes executions"

**Given** le DBA selectionne le tab "Toutes les executions"
**When** la page se charge
**Then** la table affiche toutes les executions auxquelles l'utilisateur a acces selon les regles RBAC (meme comportement que le Dashboard pour les executions recentes)

**Given** le DBA selectionne le tab "Mes executions"
**When** la page se charge
**Then** la table affiche uniquement les executions de l'utilisateur connecte (comportement actuel de Story 4.8)

**Given** le DBA change de tab
**When** il passe de "Mes executions" a "Toutes les executions" (ou inversement)
**Then** la table se recharge avec les donnees correspondantes et la pagination se remet a la page 1

**Given** le DBA applique des filtres (tri, pagination)
**When** il change de tab
**Then** les filtres sont conserves (tri et pagination restent actifs)

**Given** un utilisateur non-DBA/DBOPS accede a la page Executions
**When** la page se charge
**Then** seul le tab "Mes executions" est visible (pas de tab "Toutes les executions")

**And** l'API GET /api/v1/executions retourne les executions de l'utilisateur courant (comportement existant)
**And** l'API GET /api/v1/executions?all=true retourne toutes les executions auxquelles l'utilisateur a acces selon RBAC (nouveau parametre)
**And** le backend filtre les executions selon les permissions RBAC de l'utilisateur (meme logique que pour le catalogue)
**And** seuls les profils DBA et DBOPS peuvent utiliser le parametre ?all=true
**And** la table affiche une colonne "Utilisateur" (user_display_name) dans le tab "Toutes les executions" pour distinguer qui a lance chaque execution

### Story 8.10 : Vue liste en tableau avec colonnes pour le catalogue

As a DBA,
I want voir la vue liste du catalogue sous forme de tableau avec des colonnes correspondant aux champs des cards,
So that je peux comparer rapidement plusieurs actions et acceder aux informations importantes sans ouvrir chaque card.

**Acceptance Criteria:**

**Given** un DBA selectionne la vue liste dans le catalogue
**When** la page affiche les actions
**Then** un tableau Ant Design s'affiche avec des colonnes : Action (nom + icone), Description, Impact, Tags, Moteur, Executions, Favori, Actions

**Given** le DBA consulte le tableau
**When** il voit la colonne "Action"
**Then** elle affiche l'icone (moteur ou workflow) et le nom de l'action en gras

**Given** le DBA consulte la colonne "Description"
**When** il voit le contenu
**Then** la description est tronquee a 2 lignes avec ellipsis et tooltip au survol pour voir le texte complet

**Given** le DBA consulte la colonne "Impact"
**When** il voit les valeurs
**Then** l'ImpactIndicator s'affiche avec le meme code couleur que dans les cards (triple coding)

**Given** le DBA consulte la colonne "Tags"
**When** il voit les tags
**Then** les 3 premiers tags sont affiches avec un "+N" si d'autres tags existent (comme dans les cards)

**Given** le DBA consulte la colonne "Executions"
**When** il voit le nombre
**Then** le format est "N execution(s)" comme dans les cards

**Given** le DBA consulte la colonne "Favori"
**When** il voit l'icone
**Then** un bouton avec icone coeur permet de toggle le favori (meme comportement que dans les cards)

**Given** le DBA consulte la colonne "Actions"
**When** il voit les boutons
**Then** un bouton "Voir details" ouvre le drawer avec ActionDrawerPreview (meme comportement que clic sur card)

**Given** le DBA veut trier les actions
**When** il clique sur un header de colonne
**Then** le tri s'applique sur cette colonne (nom, moteur, executions, impact)

**Given** le DBA survole une ligne du tableau
**When** il passe la souris
**Then** la ligne est surlignee pour indiquer qu'elle est cliquable

**And** le tableau utilise Ant Design Table avec pagination si necessaire (ou scroll infini)
**And** les colonnes sont responsive : sur mobile, certaines colonnes peuvent etre masquees ou combinees
**And** le skeleton loading affiche des lignes de tableau (pas des cards) quand viewMode === 'list'
**And** le tableau conserve les memes fonctionnalites que les cards : favori, ouverture drawer, affichage des metriques si disponibles

### Story 8.7 : Navigation par categories avec tabs et filtres integres

As a DBA,
I want naviguer dans le catalogue par categories (tabs) et affiner avec des tags et filtres,
So that je trouve rapidement les actions par type d'operation sans avoir besoin d'un drawer de filtres separe.

**Acceptance Criteria:**

**Given** un DBA accede au catalogue
**When** la page se charge
**Then** des tabs de categories s'affichent en haut : "Tout", "Provisioning", "Patching", "Administration", "Monitoring", "Backup", "Mes actions"

**Given** le DBA selectionne une categorie (ex: "Patching")
**When** il clique sur le tab
**Then** seules les actions ayant un tag correspondant a la categorie s'affichent (ex: tag "patching")

**Given** le DBA est sur une categorie
**When** il voit les tags disponibles sous les tabs
**Then** un TagCloud affiche uniquement les tags pertinents pour cette categorie avec leurs compteurs

**Given** le DBA veut filtrer davantage
**When** il selectionne des tags dans le TagCloud
**Then** les filtres se cumulent avec la categorie active (intersection)

**Given** le DBA veut filtrer par moteur, environnement ou impact
**When** il consulte la barre de filtres horizontale sous les tabs
**Then** des Select compacts s'affichent : Moteur, Environnement, Impact (remplace le drawer lateral)

**Given** le DBA applique plusieurs filtres (categorie + tags + moteur)
**When** il consulte les resultats
**Then** tous les filtres actifs sont visibles comme chips sous la barre de filtres avec possibilite de les supprimer individuellement

**Given** le drawer de filtres lateral existait
**When** cette story est implementee
**Then** le drawer est supprime et remplace par la barre de filtres horizontale integree

**And** les categories sont mappees a des tags specifiques : "provisioning", "patching", "administration", "monitoring", "backup"
**And** l'API GET /api/v1/catalog/actions accepte un parametre `category` qui filtre par tag correspondant
**And** l'API GET /api/v1/catalog/tags accepte un parametre `category` pour retourner uniquement les tags de cette categorie
**And** le tab "Tout" affiche toutes les actions sans filtre de categorie
**And** le tab "Mes actions" affiche les favoris et recents (comportement existant)

### Story 8.8 : Deplacement des approbations vers la page Executions et notification dans la top bar

As a DBA,
I want voir les approbations en attente sur la page Executions avec une notification dans la top bar,
So that je suis alerte des approbations requises et je peux les gerer directement dans le contexte des executions.

**Acceptance Criteria:**

**Given** un DBA accede a la page Executions
**When** la page se charge
**Then** une section "Approbations en attente" s'affiche avant la liste des executions (si des approbations sont en attente)

**Given** la section approbations est affichee
**When** le DBA consulte la liste
**Then** elle contient les memes informations qu'avant : action, demandeur, environnement, date de soumission, boutons Approuver/Refuser

**Given** un DBA consulte le Dashboard
**When** la page se charge
**Then** la section "Approbations en attente" n'est plus affichee (deplacee vers Executions)

**Given** un DBA ou DBOPS a des approbations en attente
**When** il consulte la top bar
**Then** une icone de cloche (BellOutlined) s'affiche avec un badge indiquant le nombre d'approbations en attente

**Given** le DBA clique sur l'icone de cloche
**When** il interagit avec elle
**Then** il est redirige vers la page Executions (ou la section approbations scroll automatiquement en vue)

**Given** le DBA n'a pas d'approbations en attente
**When** il consulte la top bar
**Then** l'icone de cloche n'affiche pas de badge (ou affiche 0 de maniere discrete)

**And** l'API GET /api/v1/executions/pending-approvals?count_only=true est appelee periodiquement (polling ou WebSocket) pour mettre a jour le badge
**And** le badge se met a jour en temps reel quand une approbation est ajoutee ou resolue
**And** la section approbations sur ExecutionsPage utilise le meme composant PendingApprovalsList que le Dashboard utilisait
**And** seuls les profils DBA et DBOPS voient l'icone de cloche et la section approbations

---

As a DBA,
I want naviguer dans le catalogue par categories (tabs) et affiner avec des tags et filtres,
So that je trouve rapidement les actions par type d'operation sans avoir besoin d'un drawer de filtres separe.

**Acceptance Criteria:**

**Given** un DBA accede au catalogue
**When** la page se charge
**Then** des tabs de categories s'affichent en haut : "Tout", "Provisioning", "Patching", "Administration", "Monitoring", "Backup", "Mes actions"

**Given** le DBA selectionne une categorie (ex: "Patching")
**When** il clique sur le tab
**Then** seules les actions ayant un tag correspondant a la categorie s'affichent (ex: tag "patching")

**Given** le DBA est sur une categorie
**When** il voit les tags disponibles sous les tabs
**Then** un TagCloud affiche uniquement les tags pertinents pour cette categorie avec leurs compteurs

**Given** le DBA veut filtrer davantage
**When** il selectionne des tags dans le TagCloud
**Then** les filtres se cumulent avec la categorie active (intersection)

**Given** le DBA veut filtrer par moteur, environnement ou impact
**When** il consulte la barre de filtres horizontale sous les tabs
**Then** des Select compacts s'affichent : Moteur, Environnement, Impact (remplace le drawer lateral)

**Given** le DBA applique plusieurs filtres (categorie + tags + moteur)
**When** il consulte les resultats
**Then** tous les filtres actifs sont visibles comme chips sous la barre de filtres avec possibilite de les supprimer individuellement

**Given** le drawer de filtres lateral existait
**When** cette story est implementee
**Then** le drawer est supprime et remplace par la barre de filtres horizontale integree

**And** les categories sont mappees a des tags specifiques : "provisioning", "patching", "administration", "monitoring", "backup"
**And** l'API GET /api/v1/catalog/actions accepte un parametre `category` qui filtre par tag correspondant
**And** l'API GET /api/v1/catalog/tags accepte un parametre `category` pour retourner uniquement les tags de cette categorie
**And** le tab "Tout" affiche toutes les actions sans filtre de categorie
**And** le tab "Mes actions" affiche les favoris et recents (comportement existant)

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

## Epic 11 : Scheduling & Maintenance Planifiée

Le systeme permet de planifier des executions d'actions pour une date/heure future ou selon des patterns de recurrence. Les executions planifiees sont gerees via un modele de donnees et des APIs, mais l'execution effective est deleguee a un scheduler externe (Control-M ou Django scheduler) pour eviter la charge backend supplementaire.

**Approche technique :** Modele de donnees + UI/API completes, mais pas de scheduler integre (Celery). Les schedules sont recuperes et executes par un scheduler externe. Pas de seconde base de donnees, pas de charge backend supplementaire pour le polling.

### Story 11.1 : Modele de donnees scheduled executions et recurrence

As a systeme,
I want un modele de donnees pour stocker les executions planifiees avec support des patterns de recurrence,
So that les executions peuvent etre planifiees pour une date/heure future ou selon des patterns repetitifs.

**Acceptance Criteria:**

**Given** le schema Oracle existe
**When** une migration SQL est executee
**Then** la table SCHEDULED_EXECUTIONS est creee avec les colonnes : id, action_id, user_id, parameters (CLOB JSON), scheduled_at (timestamp), status (pending, executed, cancelled), created_at, updated_at

**Given** la table SCHEDULED_EXECUTIONS existe
**When** une migration SQL est executee
**Then** la table RECURRING_PATTERNS est creee avec les colonnes : id, scheduled_execution_id, pattern_type (one_time, daily, weekly, cron), pattern_config (CLOB JSON), next_execution_date (timestamp), is_active (boolean)

**Given** une execution planifiee est creee
**When** elle est de type "one_time"
**Then** RECURRING_PATTERNS n'a pas d'entree associee

**Given** une execution planifiee est creee
**When** elle est de type "recurring"
**Then** RECURRING_PATTERNS a une entree avec pattern_type et pattern_config, et next_execution_date est calcule pour la prochaine execution

**And** next_execution_date est utilise par le scheduler externe pour recuperer les schedules a executer
**And** le modele de donnees supporte les patterns simples (daily, weekly) et les expressions cron avancees

### Story 11.3 : API creer execution planifiee one-time

As a DBA,
I want creer une execution planifiee pour une date/heure future via l'API,
So that je peux programmer des executions sans intervention immediate.

**Acceptance Criteria:**

**Given** un DBA authentifie
**When** il envoie POST /api/v1/scheduled-executions avec action_id, parameters, scheduled_at (timestamp futur)
**Then** une entree SCHEDULED_EXECUTIONS est creee avec status="pending"

**Given** scheduled_at est dans le passe
**When** la requete est envoyee
**Then** l'API retourne une erreur 400 avec message "scheduled_at must be in the future"

**Given** l'utilisateur n'a pas les permissions pour executer l'action
**When** la requete est envoyee
**Then** l'API retourne une erreur 403

**And** l'API valide les parametres de l'action selon le schema defini dans ACTIONS_CATALOG
**And** l'API retourne l'entree creee avec id, scheduled_at, status
**And** l'audit trace la creation de l'execution planifiee

### Story 11.5 : UI scheduler dans wizard execution

As a DBA,
I want choisir entre "Executer maintenant" et "Planifier" dans le wizard d'execution,
So that je peux soit executer immediatement soit programmer l'execution pour plus tard.

**Acceptance Criteria:**

**Given** le DBA ouvre le wizard d'execution
**When** il remplit les parametres de l'action
**Then** il voit deux options : "Executer maintenant" (bouton principal) et "Planifier" (bouton secondaire)

**Given** le DBA clique sur "Planifier"
**When** le wizard s'etend
**Then** un selecteur de date/heure apparait pour choisir scheduled_at

**Given** le DBA selectionne une date/heure future
**When** il confirme
**Then** l'API POST /api/v1/scheduled-executions est appelee avec les parametres et scheduled_at
**And** un message de confirmation s'affiche : "Execution planifiee pour le [date/heure]"

**Given** le DBA clique sur "Executer maintenant"
**When** il confirme
**Then** l'execution se lance immediatement comme actuellement

**And** le selecteur de date/heure valide que la date est dans le futur
**And** le selecteur affiche le fuseau horaire utilise

### Story 11.6 : Liste executions planifiees et annulation

As a DBA ou DBOPS,
I want voir la liste des executions planifiees et pouvoir les annuler,
So that je peux gerer les executions planifiees et eviter les executions non desirees.

**Acceptance Criteria:**

**Given** un DBA ou DBOPS accede a la page admin
**When** il clique sur l'onglet "Executions planifiees"
**Then** une liste des executions planifiees s'affiche avec : action, utilisateur, date/heure planifiee, statut, date de creation

**Given** la liste des executions planifiees
**When** elle est chargee
**Then** les executions sont filtrees par utilisateur (DBA voit ses propres executions, DBOPS voit toutes)

**Given** une execution planifiee avec status="pending"
**When** le DBA clique sur "Annuler"
**Then** l'API PATCH /api/v1/scheduled-executions/{id} avec status="cancelled" est appelee
**And** l'execution est marquee comme annulee dans la base de donnees
**And** l'execution n'apparait plus dans la liste des executions a executer pour le scheduler externe

**Given** une execution planifiee avec status="executed" ou "cancelled"
**When** le DBA consulte la liste
**Then** l'action "Annuler" n'est pas disponible

**And** la liste supporte le filtrage par statut, action, date
**And** la liste affiche un indicateur visuel pour les executions proches (dans les 24h)

### Story 11.7 : Patterns recurrence simples daily weekly

As a DBA,
I want planifier des executions repetitives avec des patterns simples (tous les jours, toutes les semaines),
So that je peux automatiser des taches de maintenance regulieres sans configuration complexe.

**Acceptance Criteria:**

**Given** le DBA cree une execution planifiee
**When** il selectionne "Recurrence" dans le wizard
**Then** il peut choisir entre "One-time", "Daily", "Weekly"

**Given** le DBA selectionne "Daily"
**When** il configure la recurrence
**Then** il peut choisir l'heure d'execution (HH:MM)
**And** RECURRING_PATTERNS est creee avec pattern_type="daily" et pattern_config={"hour": HH, "minute": MM}
**And** next_execution_date est calcule pour demain a l'heure specifiee

**Given** le DBA selectionne "Weekly"
**When** il configure la recurrence
**Then** il peut choisir le jour de la semaine (lundi-dimanche) et l'heure d'execution
**And** RECURRING_PATTERNS est creee avec pattern_type="weekly" et pattern_config={"day_of_week": N, "hour": HH, "minute": MM}
**And** next_execution_date est calcule pour le prochain jour specifie a l'heure specifiee

**Given** une execution recurrente est executee par le scheduler externe
**When** elle se termine
**Then** next_execution_date est mis a jour pour la prochaine occurrence selon le pattern

**And** l'API POST /api/v1/scheduled-executions accepte recurring_pattern dans le body pour creer des executions recurrentes
**And** l'utilisateur peut desactiver une recurrence (is_active=false) sans supprimer l'historique

### Story 11.8 : Cron expressions pour recurrence avancee

As a DBA power user,
I want utiliser des expressions cron completes pour definir des patterns de recurrence complexes,
So that je peux planifier des executions avec des frequences avancees (ex: tous les 2 jours, le premier lundi du mois).

**Acceptance Criteria:**

**Given** le DBA cree une execution planifiee
**When** il selectionne "Recurrence avancee" dans le wizard
**Then** un champ texte apparait pour saisir une expression cron (ex: "0 2 * * *" pour tous les jours a 2h)

**Given** le DBA saisit une expression cron
**When** il confirme
**Then** l'expression est validee (format cron standard : minute hour day month day-of-week)
**And** si l'expression est invalide, une erreur est affichee avec un message explicatif

**Given** une expression cron valide est saisie
**When** l'execution planifiee est creee
**Then** RECURRING_PATTERNS est creee avec pattern_type="cron" et pattern_config={"expression": "..."}
**And** next_execution_date est calcule en utilisant une bibliotheque de parsing cron (ex: croniter)

**Given** le DBA consulte une execution planifiee avec pattern cron
**When** il voit les details
**Then** l'expression cron est affichee avec une description lisible (ex: "Tous les jours a 2h00")

**And** l'API valide les expressions cron avant de creer l'execution planifiee
**And** un helper/guide est disponible dans l'UI pour aider a construire des expressions cron valides

### Story 11.10 : API integration scheduler externe

As a scheduler externe (Control-M ou Django scheduler),
I want recuperer la liste des executions planifiees a executer via une API,
So that je peux executer les schedules au bon moment sans polling continu.

**Acceptance Criteria:**

**Given** un scheduler externe est configure
**When** il appelle GET /api/v1/scheduled-executions/pending avec un parametre ?before={timestamp}
**Then** l'API retourne la liste des executions avec status="pending" et next_execution_date <= before

**Given** une execution planifiee est retournee
**When** le scheduler externe l'execute
**Then** il peut appeler POST /api/v1/executions avec les parametres de l'execution planifiee
**And** apres execution, le scheduler peut appeler PATCH /api/v1/scheduled-executions/{id} avec status="executed" et execution_id

**Given** une execution recurrente est executee
**When** le scheduler met a jour le statut
**Then** next_execution_date est automatiquement recalcule selon le pattern de recurrence

**Given** aucune execution n'est a executer
**When** l'API est appelee
**Then** elle retourne une liste vide []

**And** l'API supporte la pagination pour les environnements avec beaucoup d'executions planifiees
**And** l'API peut etre securisee avec un token d'API specifique pour le scheduler externe
**And** l'API retourne les executions triees par next_execution_date (plus urgentes en premier)

---

## Epic M : Migration FastAPI vers Django REST

Migrer le backend du portail IDP de FastAPI + SQL brut (python-oracledb) vers Django + Django REST Framework afin de faciliter l'arrimage a la plateforme hebergeuse (meme stack, meme conventions, maintenance mutualisable). Le frontend React consomme la meme API (contrat preserve).

**Contexte :** Arrimage a la plateforme interne (hebergeur) — stack cible Django + DRF. Reduction de la dette d'arrimage et alignement stack.

**Perimetre :** Backend uniquement (API, couche donnees, auth, config, middleware, tests). Frontend React inchange (cohabitation ou meme API contract).

**Contrainte :** Parite fonctionnelle et contractuelle avec l'API actuelle (OpenAPI / contrats frontend).

### Story M.1 : Bootstrap projet Django et Django REST Framework

As a developpeur de l'equipe IDP,
I want un projet Django initial avec DRF, structure d'apps et configuration de base,
So that nous avons une base saine pour migrer les endpoints et la logique metier.

**Acceptance Criteria:**

**Given** un environnement Python dedie a la migration (venv ou equivalent)
**When** on installe Django, djangorestframework, djangocorsheaders, et les dependances Oracle (cx_Oracle ou oracledb)
**Then** un projet Django `idp_backend` est cree avec une structure d'apps : `catalog`, `profiles`, `auth`, `integrations`, `core`

**Given** le projet Django
**When** on configure `settings.py` (DEBUG, ALLOWED_HOSTS, DATABASES Oracle, INSTALLED_APPS avec rest_framework, CORS)
**Then** `python manage.py runserver` demarre sans erreur
**And** la structure respecte les conventions du projet hebergeur si documentees (nommage, place des configs)
**And** un fichier `requirements.txt` ou `pyproject.toml` liste toutes les dependances avec versions

**Given** DRF est installe
**When** on configure REST_FRAMEWORK dans settings (auth, pagination, format JSON, throttle si requis)
**Then** une route de test GET /api/v1/health (ou equivalent) renvoie 200 avec un payload minimal
**And** le format de reponse (enveloppe data/error, snake_case) est aligne avec l'API actuelle pour compatibilite frontend

### Story M.2 : Modeles Django et migrations (schema Oracle existant)

As a developpeur,
I want les modeles Django mappes sur le schema Oracle actuel (USERS, ACTIONS_CATALOG, PROFILES, etc.),
So that la couche ORM remplace le SQL brut sans changer le schema en production.

**Acceptance Criteria:**

**Given** le schema Oracle actuel (tables V001–V020+ : users, actions_catalog, execution_steps, profiles, profile_*_permissions, integrations, audit, etc.)
**When** on cree les modeles Django correspondants (Meta.db_table, champs CLOB/JSONField, relations ForeignKey, enums)
**Then** chaque table existante a un modele Django avec les memes noms de colonnes et types compatibles
**And** les champs JSON (parameters_schema, impact_rules, execution_steps, change_type_config) utilisent JSONField ou TextField + serialisation documentee
**And** les migrations Django initiales sont generees (makemigrations) et documentees pour execution sur un schema existant (--fake initial si tables deja presentes)

**Given** un schema Oracle de dev (ou fixture)
**When** on execute migrate (ou migrate --fake puis verification)
**Then** aucune regression sur le schema ; les contraintes et index existants sont respectes ou explicitement decides (nommage Django)
**And** un README ou ADR decide : migrations Django prennent le relais de Flyway a partir de la version X, ou cohabitation temporaire

### Story M.3 : Couche donnees — conversion des repositories vers l'ORM Django

As a developpeur,
I want la logique des repositories FastAPI (catalog, profiles, integrations, audit, user) reecrite avec l'ORM Django,
So que les vues DRF s'appuient sur des QuerySet et services Django au lieu de SQL brut.

**Acceptance Criteria:**

**Given** les repositories actuels (catalog_repository, profile_repository, profile_action_permission_repository, profile_target_permission_repository, integration_repository, user_repository, audit_repository)
**When** on cree l'equivalent en couche Django (managers personnalises, services dans chaque app, ou repositories encapsulant l'ORM)
**Then** chaque operation CRUD et requete metier actuelle a un equivalent teste (parite fonctionnelle)
**And** la gestion des CLOB/JSON (lecture/ecriture) est centralisee et couverte par des tests unitaires
**And** les transactions et l'audit (ecriture dans audit_log) sont geres (signals Django ou appels explicites) conformement aux NFR d'audit
**And** aucune requete SQL brute dans les vues DRF (sauf exception documentee et justifiee)

**Given** les tests unitaires existants des repositories (pytest)
**When** on les reecrit ou duplique pour la couche Django (pytest-django ou unittest)
**Then** le taux de couverture et les cas limites (pagination, filtres, champs optionnels) sont au moins equivalents

### Story M.4 : API REST — endpoints catalogue et admin (actions, tags)

As a developpeur,
I want les endpoints admin et catalogue (actions, tags) exposes en DRF avec le meme contrat que l'API FastAPI actuelle,
So que le frontend Admin et Catalogue continue de fonctionner sans changement (ou avec adaptation minimale documentee).

**Acceptance Criteria:**

**Given** les routes FastAPI actuelles : admin (create/list/get/update action, steps, metadata, tags, status), catalog (list catalog actions), tags (list)
**When** on implemente les ViewSet ou APIView DRF correspondants avec serializers
**Then** les URLs et verbes HTTP sont identiques (ex. GET /api/v1/catalog/actions, POST /api/v1/admin/actions, etc.)
**And** le format des corps de requete et de reponse (champs, types, enveloppe data) est inchange pour le client
**And** la pagination, filtres et tri du catalogue sont supportes (parametres query et format de reponse alignes)
**And** les permissions (RBAC) sont appliquees (DRF permissions ou middleware) : seuls les roles autorises accedent aux endpoints admin

**Given** les tests d'integration ou E2E du frontend (Admin, Catalogue)
**When** on pointe le frontend vers le backend Django
**Then** les scenarios critiques (liste actions, creation action, edition, tags, statut) passent ; les regressions sont documentees et tracees

### Story M.5 : API REST — endpoints profils et permissions

As a developpeur,
I want les endpoints profils (list, get, create, update, delete, profile_actions, profile_targets) migres en DRF,
So que la gestion des profils et des permissions par le frontend reste fonctionnelle.

**Acceptance Criteria:**

**Given** les routes FastAPI profiles (list_profiles, get_profile, create_profile, update_profile, delete_profile, get_profile_actions, get_profile_targets)
**When** on implemente les vues DRF et serializers correspondants
**Then** le contrat (query params, body, response shape) est preserve
**And** les regles metier (cumul multi-profils, resolution AD, validation des permissions) sont respectees (delegation aux services Django)
**And** l'import/export YAML (si expose via API) reste supporte ou est documente comme evolution separee

**Given** les tests unitaires et d'integration des profils
**When** on les execute contre le backend Django
**Then** les cas de succes et d'erreur (validation, 404, 403) sont couverts

### Story M.6 : API REST — auth, health, integrations

As a developpeur,
I want les endpoints auth (current user, refresh), health et integrations migres en DRF,
So que l'authentification, le monitoring et la gestion des integrations fonctionnent sur Django.

**Acceptance Criteria:**

**Given** les routes FastAPI : auth (get_current_user_profile), health (GET /api/v1/health), integrations (CRUD)
**When** on implemente les equivalents DRF
**Then** GET /api/v1/health renvoie le statut des dependances (DB, optionnellement Vault/ServiceNow) avec codes HTTP 200/503
**And** les endpoints d'integrations (list, get, create, update, delete) respectent le contrat actuel
**And** l'endpoint de profil utilisateur courant renvoie le meme format (user, permissions, profils) pour le frontend
**And** la documentation OpenAPI (schema) est generee (drf-spectacular ou equivalent) et comparee a l'actuelle pour ecarts documentes

### Story M.7 : Authentification SAML et securite (alignement plateforme cible)

As a responsable technique,
I want l'authentification SAML 2.0 et la gestion des sessions (JWT ou session Django) alignees avec la plateforme hebergeuse,
So que le portail IDP s'integre a leur infra SSO et politique de securite.

**Acceptance Criteria:**

**Given** la plateforme hebergeuse utilise Django + SSO (SAML ou autre)
**When** on integre le mecanisme d'auth (django-saml2, python3-saml, ou proxy SSO cote hebergeur)
**Then** un utilisateur non authentifie est redirige vers l'IdP et revient avec une session valide
**And** les attributs utilisateur (nom, groupes AD, etc.) sont disponibles pour la resolution des profils IDP (FR25, FR25a-d)
**And** les tokens ou cookies de session respectent la politique de securite (httpOnly, duree, renouvellement)
**And** NFR6 (TLS), NFR9 (expiration session), NFR10 (acces non autorise journalise) sont satisfaits
**And** un document d'architecture ou runbook decrit l'interaction SSO entre le portail IDP et l'infra hebergeur

**Given** des tests d'auth (login, refresh, 401, 403)
**When** on les execute contre le backend Django
**Then** les scenarios de succes et d'echec sont couverts

### Story M.8 : Middleware, logging, observabilite

As a DBOPS,
I want le middleware (CORS, correlation ID, erreurs), le logging structure et l'observabilite alignes sur la plateforme et les NFR,
So que le portail Django soit monitorable et coherent avec le reste de l'infra.

**Acceptance Criteria:**

**Given** le backend Django
**When** une requete entre et sort
**Then** un correlation ID (X-Idp-Request-Id ou equivalent) est genere et propage dans les logs et reponses si applicable
**And** les logs sont structures (JSON) avec timestamp, level, event, correlation_id, user_id (NFR, convention hebergeur)
**And** les exceptions sont catchees et renvoyees au client dans le format d'erreur actuel (enveloppe error, codes HTTP)
**And** CORS est configure pour les origines autorisees (frontend)
**And** le health check reflete l'etat DB (et optionnellement Vault, ServiceNow) pour le monitoring

### Story M.9 : Tests unitaires et d'integration (parite avec FastAPI)

As a developpeur,
I want une suite de tests (unitaires + integration) au moins equivalente a celle du backend FastAPI,
So que la migration n'introduise pas de regressions et que les futures evolutions restent couvertes.

**Acceptance Criteria:**

**Given** la liste des tests pytest actuels (repositories, API, auth, middleware)
**When** on migre ou reecrit les tests pour Django (pytest-django, client DRF, factories)
**Then** chaque module critique (catalog, profiles, integrations, auth, health) a des tests unitaires et, si pertinent, des tests d'integration (DB reelle ou test DB)
**And** les tests d'API (endpoints) valident statut HTTP, corps de reponse et cas d'erreur (400, 403, 404)
**And** la couverture de code est mesuree et documentee ; objectif : au moins egal a la couverture actuelle
**And** les tests s'executent dans le CI (GitHub Actions ou equivalent) a chaque push

### Story M.10 : Strategie de bascule et decommissionnement FastAPI

As a chef de projet ou tech lead,
I want une strategie de bascule (double run, feature flag, ou bascule unique) et un plan de decommissionnement du backend FastAPI,
So que la mise en production du backend Django soit maîtrisee et sans perte de service.

**Acceptance Criteria:**

**Given** le backend Django est fonctionnel et teste (parite avec FastAPI)
**When** on definit la strategie de bascule (bascule DNS/route, feature flag backend, ou fenetre de maintenance)
**Then** un document "Plan de bascule FastAPI → Django" decrit les etapes, les roles, le rollback et la verification post-bascule
**And** les donnees (Oracle) sont partagees : pas de migration de donnees si meme schema ; si changement de BDD, un script de migration est prevu et teste
**And** le frontend est configure pour pointer vers le backend Django (env, config) et une checklist de validation (catalogue, admin, profils, auth, health) est executee
**And** apres validation en production, le code et les deploiements FastAPI sont desactives ou archives ; le depot/documentation indique Django comme backend officiel

**Given** la bascule est effectuee
**When** on surveille les erreurs et les metriques (logs, health, temps de reponse)
**Then** les incidents sont traites selon le runbook ; un retour arriere vers FastAPI est possible si documente (snapshot config, rollback DNS/deploy)

### Story M.11 : Nettoyage code FastAPI — suppression des references et mise a jour documentation

As a developpeur,
I want supprimer toutes les references a FastAPI dans le code et mettre a jour la documentation pour refleter que Django est le backend unique,
So que le codebase soit coherent, sans dette documentaire, et que les nouveaux contributeurs ne soient plus induits en erreur par des mentions de FastAPI.

**Acceptance Criteria:**

**Given** la documentation technique du portail (README, docs/, planning-artifacts)
**When** on la consulte
**Then** elle decrit uniquement Django/DRF comme backend
**And** les mentions de FastAPI sont supprimees ou reformulees en contexte historique uniquement si pertinent
**And** les guides de demarrage, d'architecture et de contribution ne font plus reference a FastAPI comme option active

**Given** le code source du backend Django (django_backend/)
**When** on recherche FastAPI ou fastapi dans les fichiers
**Then** aucune occurrence ne subsiste dans les commentaires, docstrings ou chaines
**And** les formulations sont adaptees (ex. format d'erreur DRF au lieu de format FastAPI)

**Given** le repertoire backend/ (code FastAPI legacy)
**When** la story est terminee
**Then** soit il est supprime de la branche principale, soit une note claire indique qu'il est archive
**And** les scripts CI/CD et de demarrage ne pointent plus vers le backend FastAPI

---

## Epic 12 : Documentation technique

Documenter l'implementation technique complete du portail IDP apres la migration vers Django pour faciliter la maintenance, l'onboarding des nouveaux developpeurs et la comprehension de l'architecture.

**Contexte :** A realiser apres le passage a Django pour documenter la cible finale.

### Story 12.1 : Documentation backend implementation

As a developpeur rejoignant l'equipe,
I want une documentation detaillee de l'implementation backend (Django),
So that je peux comprendre rapidement l'architecture, les patterns utilises et comment contribuer.

**Acceptance Criteria:**

**Given** la migration Django est completee
**When** la documentation backend est redigee
**Then** elle inclut : structure des apps Django, modeles et relations, services et managers, endpoints API et serializers, gestion des permissions RBAC, integration SAML, middleware et logging, tests et couverture

**Given** un developpeur consulte la documentation
**When** il cherche une information specifique (ex: comment ajouter un endpoint)
**Then** il trouve un guide pas-a-pas avec exemples de code

**And** la documentation inclut des diagrammes d'architecture (couches, flux de donnees)
**And** la documentation inclut un guide de contribution (setup dev, conventions de code, processus de review)
**And** la documentation est maintenue a jour avec les changements majeurs

### Story 12.2 : Documentation frontend implementation

As a developpeur frontend rejoignant l'equipe,
I want une documentation detaillee de l'implementation frontend (React),
So that je peux comprendre rapidement la structure, les composants et les patterns utilises.

**Acceptance Criteria:**

**Given** le frontend React est en production
**When** la documentation frontend est redigee
**Then** elle inclut : structure des dossiers et organisation du code, composants principaux et leurs responsabilites, gestion d'etat (hooks, context), routing et navigation, integration avec l'API backend, theming et design system (Ant Design), tests et couverture

**Given** un developpeur consulte la documentation
**When** il cherche une information specifique (ex: comment ajouter une nouvelle page)
**Then** il trouve un guide pas-a-pas avec exemples de code

**And** la documentation inclut des diagrammes de composants et flux de donnees
**And** la documentation inclut un guide de contribution frontend (setup dev, conventions, processus de review)
**And** la documentation est maintenue a jour avec les changements majeurs

### Story 12.3 : Schema base de donnees et relations tables

As a developpeur ou DBOPS,
I want un schema detaille de la base de donnees avec les relations entre les tables,
So that je peux comprendre la structure des donnees et les dependances.

**Acceptance Criteria:**

**Given** le schema Oracle est stabilise (post-migration Django)
**When** la documentation du schema est generee
**Then** elle inclut : diagramme ER (Entity-Relationship) avec toutes les tables et relations, description de chaque table (colonnes, types, contraintes, index), relations ForeignKey et leurs cardinalites, migrations Flyway/Django et leur historique

**Given** un developpeur consulte la documentation
**When** il cherche une information sur une table specifique
**Then** il trouve la description complete avec exemples de requetes courantes

**And** la documentation inclut les contraintes metier importantes (ex: RBAC, audit)
**And** la documentation inclut un guide de migration de schema (comment ajouter une table, modifier une colonne)
**And** la documentation est generee automatiquement depuis les modeles Django si possible (django-extensions graph_models)

---

## Epic 13 : Selection de targets a l'execution et permissions par environnement (inventaire)

Aujourd'hui les actions ne permettent pas de choisir explicitement un target (serveur, base, groupe Ansible) a l'execution ; l'environnement est associe a l'action alors qu'il doit etre derive du target dans l'inventaire. Cet epic introduit la selection de target(s) dans le wizard d'execution, aligne les permissions sur le modele "environnement = propriete du target" et "une action, des targets autorises par profil (env + pattern/liste)".

**Contexte :** Voir regles-metier-permissions-par-target-et-environnement.md pour les regles metier et criteres d'acceptation.

### Story 13.1 : Inventaire — source via integration (API ou DB), association target a un environnement, API targets filtres

As a systeme,
I want que la source des targets soit une integration (type inventory ou inventory_db) et que chaque target soit associe a un environnement (dev, certif, prod),
So that l'environnement d'une execution est derive du target choisi et qu'en dev sans API le fallback DBOPS_INVENTORY (synonyme) soit utilise.

**Acceptance Criteria:**

**Given** la source des targets est une **integration** (table INTEGRATIONS) : type `inventory` (API externe, base_url + credential_ref) ou `inventory_db` (lecture depuis schéma BD, config ex. schema DBOPS_INVENTORY). Si aucune integration inventaire n'est configuree (ex. dev), le backend utilise le **fallback** : lecture depuis le schéma DBOPS_INVENTORY (acces via synonyme).

**Given** un target (serveur, base, groupe) est enregistre (API, table inventaire, ou DBOPS_INVENTORY),
**When** on le consulte,
**Then** il possede un attribut environnement (dev, certif, prod) et cet attribut est la source de verite pour l'env.

**Given** une API liste les targets (ex. GET /api/v1/inventory/targets ou equivalent),
**When** elle est appelee avec des filtres (environnement, user/permissions),
**Then** elle retourne les targets avec leur environnement, filtres par permissions utilisateur (pour usage dans le wizard). La liste est alimentee depuis l'integration inventaire active ou le fallback DBOPS_INVENTORY.

**And** les donnees inventaire alimentant les formulaires (FR43) exposent l'environnement par target.

### Story 13.2 : Wizard d'execution — etape ou integration de selection des targets autorises

As a DBA,
I want selectionner explicitement le ou les targets (serveurs, bases) sur lesquels executer l'action dans le wizard,
So que je cible precisement la ressource et que l'environnement soit deduit du target.

**Acceptance Criteria:**

**Given** un DBA ouvre le wizard d'execution pour une action,
**When** le wizard affiche les etapes,
**Then** une etape (ou une section) permet de choisir un ou plusieurs targets parmi une liste ; cette liste contient uniquement les targets autorises pour l'utilisateur (environnements + restriction pattern/liste du profil).

**Given** l'utilisateur selectionne un target,
**When** il passe a l'etape suivante (parametres / confirmation),
**Then** l'environnement utilise pour l'impact, ServiceNow et l'audit est celui du target selectionne (plus de choix d'environnement separe si le target impose l'env).

**Given** l'action ne requiert pas de target (cas particuliers),
**When** le wizard est configure pour cette action,
**Then** l'etape target peut etre masquee ou optionnelle selon la definition de l'action.

**And** le payload d'execution (POST /api/v1/executions) inclut le ou les target_ids (ou target names) et l'environnement est derive cote backend du target.

### Story 13.3 : RBAC — deriver l'environnement du target et filtrer les targets par profil

As a systeme,
I want calculer les targets autorises pour un utilisateur a partir de ses profils (environnements autorises + restriction pattern/liste),
So que le wizard et l'API ne proposent que des targets sur lesquels l'utilisateur a le droit.

**Acceptance Criteria:**

**Given** un utilisateur a des droits sur les environnements [DEV, CERTIF] et aucune restriction target (pattern/liste),
**When** il demande la liste des targets disponibles pour une action,
**Then** il obtient tous les targets dont l'environnement est DEV ou CERTIF.

**Given** un utilisateur a des droits sur DEV et une restriction target de type pattern (ex. web-*),
**When** il demande la liste des targets disponibles,
**Then** il obtient uniquement les targets en DEV dont l'identifiant matche le pattern.

**Given** un utilisateur a des droits sur DEV et une restriction target de type liste explicite [srv1, srv2],
**When** il demande la liste des targets disponibles,
**Then** il obtient uniquement srv1 et srv2 s'ils appartiennent a un environnement autorise.

**Given** une requete POST /api/v1/executions avec action_id et target_id(s),
**When** le backend valide les permissions,
**Then** il verifie que le target appartient a l'inventaire, qu'il est dans un environnement autorise pour l'utilisateur et qu'il respecte les restrictions target du profil ; sinon 403.

**And** le cumul multi-profils applique l'union des targets autorises (regles metier RM6).

### Story 13.4 : Refactoring — une action unique, validation backend et suppression liaison action-environnement

As a systeme,
I want qu'une action ne soit plus dupliquee par environnement et que la validation d'execution repose sur le target et les permissions profil,
So que le modele soit coherent avec "une action, des targets autorises".

**Acceptance Criteria:**

**Given** le catalogue d'actions,
**When** on consulte les actions disponibles,
**Then** une action n'existe qu'une seule fois (pas d'instances "action X — dev", "action X — prod").

**Given** des donnees ou configurations existantes lient encore "action" a "environnement" (ex. ancien RBAC ou champs deprecated),
**When** cet epic est livre,
**Then** la logique d'autorisation et d'execution utilise exclusivement : action + target(s) + environnement derive du target + permissions profil (env + pattern/liste).

**Given** une execution est creee,
**When** elle est enregistree (DB, audit),
**Then** l'environnement enregistre est celui du target (ou des targets) choisi(s), pas une propriete de l'action.

**And** les APIs et le cache RBAC (ex. can_execute) sont adaptes pour accepter action_id + target_id(s) ou target(s) avec environnement derive, et refuser si le target n'est pas autorise.

### Story 13.5 : API self-service standalone — declencher une execution sans frontend et la retrouver dans le portail

As an application cliente (self-service via API),
I want pouvoir declencher une action via l'API backend sans interface graphique (script, CI/CD, outil interne),
So that j'automatise des actions en libre service et je retrouve ensuite l'execution dans le portail (historique, timeline, audit).

**Acceptance Criteria:**

**Given** un client dispose d'un jeton d'acces valide (Authorization: Bearer <token>) et des permissions necessaires,
**When** il appelle `POST /api/v1/executions` avec `action_id`, `target_id(s)` (ou identifiants de targets) et `parameters`,
**Then** le backend accepte la requete sans dependance au frontend (pas de cookie/session UI requise) et retourne `201` avec `execution_id` (statut initial "soumis") dans le wrapper `{ "data": ... }`.

**Given** une requete API tente de declencher une execution sur un target non autorise (env + pattern/liste) ou inconnu,
**When** le backend valide la soumission,
**Then** il refuse explicitement (`403` si non autorise, `404`/`422` si target inexistant ou payload invalide) avec un message d'erreur clair dans `{ "error": ... }`.

**Given** une execution est creee via l'API,
**When** l'utilisateur ouvre le portail,
**Then** l'execution apparait dans l'historique (FR22) et la page detail / timeline affiche le meme etat que pour une execution declenchee via le wizard (FR19/FR23), y compris les mises a jour temps reel.

**And** l'audit enregistre l'identite issue du jeton (qui) + action + targets + environnement derive du target + parametres (quoi) + horodatage (quand), de maniere identique aux executions declenchees via UI (FR30).

### Story 13.6 : Menu Calendrier — vue calendrier et exécutions planifiées pour les DBA

As a DBA,
I want accéder à un menu Calendrier qui affiche les exécutions planifiées dans une vraie vue calendrier (semaine/mois) avec des filtres alignés sur la page Exécutions (action, environnement, plateforme, technologie),
So que je consulte l'ensemble des tâches planifiées sans passer par l'interface Admin (réservée à DBOPS) et que je retrouve la même logique de filtrage qu'en Exécutions.

**Contexte :** Les exécutions planifiées sont aujourd'hui dans l'Admin ; les DBA doivent pouvoir les consulter. Un menu dédié « Calendrier » évite de donner l'accès Admin aux DBA et offre un point d'entrée clair pour « ce qui est prévu ».

**Acceptance Criteria:**

**Given** un utilisateur avec un profil DBA (ou DBOPS) accède au portail,
**When** il consulte la navigation principale,
**Then** un menu (ou onglet) **Calendrier** est visible et mène à une page dédiée aux exécutions planifiées (hors Admin).

**Given** un utilisateur ouvre la page Calendrier,
**When** la page est chargée,
**Then** une **vue calendrier** réelle est affichée (affichage type semaine et/ou mois, avec les exécutions planifiées positionnées sur les créneaux date/heure). Chaque événement affiche au minimum : action, environnement, date/heure ; au clic ou au survol : détail (action, environnement, plateforme, technologie, utilisateur, etc.).

**Given** la page Calendrier,
**When** l'utilisateur souhaite filtrer les planifications affichées,
**Then** un panneau (ou barre) de **filtres** propose les mêmes dimensions que la page Exécutions : **Action** (select searchable), **Environnement** (dev, staging, prod), **Plateforme** (plateforme d'exécution), **Technologie** (Oracle, SQL Server, Workflow, etc.). Optionnel : plage de dates, tags, utilisateur. Les options et la sémantique sont alignées sur ExecutionsFiltersPanel / API Exécutions.

**Given** des filtres sont appliqués,
**When** l'utilisateur consulte le calendrier,
**Then** seules les exécutions planifiées qui matchent les filtres sont affichées. Idéalement les filtres sont persistés en URL (comme Story 9.10) et un badge indique le nombre de filtres actifs avec un bouton pour réinitialiser.

**Given** un DBA a planifié une exécution (choix « à une date précise » dans le wizard),
**When** il ouvre le Calendrier,
**Then** cette planification apparaît dans la vue et dans l'ensemble des tâches planifiées.

**And** la page Calendrier est accessible en lecture aux DBA (et DBOPS si pertinent) ; la gestion technique des planifications (scheduler, intégrations) reste côté Admin pour DBOPS.

### Story 13.7 : Référentiels — environnements et technologies pilotés par tables (aucune valeur en dur)

As a DBOPS,
I want que les environnements valides proviennent de l'inventaire et que les technologies (moteurs) et plateformes soient gérées via des tables de référence dans le portail,
So que je puisse contrôler ces listes sans toucher au code et que la source de vérité pour les environnements soit l'inventaire.

**Contexte :** Aujourd'hui environnements (dev, staging, prod) et technologies (Oracle, SQL Server, DB2) sont en CHECK + listes en dur. Objectif : tout piloter par des tables ; pour les environnements, la source = inventaire. Voir implementation-artifacts/13-ref-environnements-et-technologies-via-tables.md.

**Acceptance Criteria:**

**Given** les technologies (moteurs) et plateformes,
**When** on consulte ou configure une action ou un filtre,
**Then** les listes proviennent de tables de référence (REF_ENGINES, REF_PLATFORMS) exposées via une API (ex. GET /api/v1/reference/engines, GET /api/v1/reference/platforms). Aucune liste en dur dans le code (backend et frontend). ACTIONS_CATALOG.ENGINE et PLATFORM référencent ces tables (code ou FK) ; les contraintes CHECK fixes sont supprimées.

**Given** les environnements valides,
**When** on en a besoin (filtres, profils, validation d'exécution),
**Then** la liste provient de l'inventaire : un endpoint (ex. GET /api/v1/inventory/environments) retourne les environnements exposés par l'inventaire (API externe ou distinct des targets). Aucune liste d'environnements en dur dans le code. EXECUTIONS.ENVIRONMENT et SCHEDULED_EXECUTIONS.ENVIRONMENT ne sont plus contraintes par un CHECK fixe ; la validation applicative vérifie que la valeur appartient à la liste retournée par l'inventaire (ou dérivée du target en Epic 13).

**Given** un DBOPS configure un profil (environnements autorisés),
**When** il sélectionne les environnements,
**Then** les options proposées viennent de l'API inventaire/environments (ou reference/environments si option table cache), pas d'une liste en dur.

**And** la normalisation des alias (ex. certif → staging) peut rester côté inventaire ou dans le service portail qui agrège les environnements ; le portail n'impose plus un jeu fixe de valeurs en dur.

### Story 13.8 : Amélioration calendrier — détails enrichis (targets, paramètres), annulation, modification, décommission admin

As a DBA ou DBOPS,
I want que le calendrier affiche tous les détails nécessaires (targets, paramètres) et permette l'annulation et la modification des exécutions planifiées,
So que je n'ai plus besoin de passer par l'admin pour consulter ou gérer les exécutions planifiées et que l'interface soit unifiée dans le calendrier.

**Contexte :** La story 13.6 a créé le menu Calendrier avec vue calendrier. L'onglet Admin "Exécutions planifiées" (ScheduledExecutionsPage) devient redondant. Cette story enrichit le calendrier avec les fonctionnalités manquantes et retire l'onglet admin.

**Acceptance Criteria:**

**Given** un utilisateur consulte le calendrier et clique ou survole un événement,
**When** le popover de détails s'affiche,
**Then** il inclut tous les champs suivants :
- Action (nom + ID)
- Environnement (badge coloré)
- **Targets** : liste des targets sélectionnés (depuis `parameters._targets` si présent)
- **Paramètres** : affichage formaté des paramètres d'exécution (JSON formaté avec indentation, masquage des champs techniques `_targets`, `_env_config`)
- Utilisateur (nom + ID)
- Date/heure planifiée (UTC)
- Type (unique / récurrent avec pattern)
- Plateforme et Technologie
- Statut (En attente, Exécutée, Annulée)
- Si exécutée : lien vers l'exécution effective (`execution_id`)

**Given** un utilisateur consulte le calendrier,
**When** il clique sur un événement d'exécution planifiée en statut "pending",
**Then** le popover affiche un bouton "Annuler" si :
- L'utilisateur est le créateur de l'exécution planifiée (`user_id` correspond), OU
- L'utilisateur a le profil DBOPS (admin)

**Given** un utilisateur DBA consulte le calendrier,
**When** il clique sur une exécution planifiée créée par un autre utilisateur,
**Then** le bouton "Annuler" n'est pas affiché (pas de permission)

**Given** un utilisateur clique sur "Annuler" dans le popover du calendrier,
**When** il confirme l'annulation,
**Then** une modal de confirmation s'affiche avec les détails de l'exécution à annuler
**And** l'appel API `PATCH /scheduled-executions/{id}` avec `status=cancelled` est effectué
**And** en cas de succès, une notification de succès s'affiche et le calendrier est rafraîchi
**And** en cas d'erreur (déjà annulée, permission refusée), un message d'erreur approprié s'affiche

**Given** un utilisateur clique sur "Modifier" dans le popover du calendrier,
**When** la modal de modification s'ouvre,
**Then** elle permet de modifier la date planifiée, les paramètres, les targets, l'environnement, et le pattern de récurrence (selon le type)
**And** l'appel API `PUT /api/v1/scheduled-executions/{id}` met à jour les champs modifiés
**And** en cas de succès, une notification de succès s'affiche et le calendrier est rafraîchi
**And** en cas d'erreur (validation, permission refusée), un message d'erreur approprié s'affiche

**Given** un utilisateur DBOPS consulte le calendrier,
**When** il clique sur un événement récurrent en statut "pending",
**Then** le popover affiche un toggle pour activer/désactiver la récurrence (si `recurring_pattern` présent)
**And** le toggle appelle `PATCH /scheduled-executions/{id}/recurring-pattern` avec `is_active` inversé
**And** une notification de succès/erreur s'affiche selon le résultat

**Given** l'onglet Admin "Exécutions planifiées" existe dans AdminPage,
**When** on retire cet onglet,
**Then** l'import de `ScheduledExecutionsPage` est supprimé de `AdminPage.tsx`
**And** l'onglet avec `key: 'scheduled-executions'` est retiré du composant Tabs
**And** le composant `ScheduledExecutionsPage.tsx` peut être supprimé (ou conservé pour référence historique)
**And** les tests associés à `ScheduledExecutionsPage` sont mis à jour ou supprimés

**Given** un utilisateur DBOPS accède à la page Admin,
**When** il consulte les onglets disponibles,
**Then** l'onglet "Exécutions planifiées" n'est plus présent
**And** seuls les onglets Actions, Profils, Intégrations et Métriques sont disponibles

**And** toutes les fonctionnalités de gestion des exécutions planifiées (consultation, annulation, toggle récurrence) sont désormais disponibles uniquement via le menu Calendrier.

---

## Epic 16 : Builder de Workflow Visuel avec Branches Conditionnelles et Retry

En tant que **DBOPS créant des workflows complexes**,
je veux **un éditeur visuel de workflow avec branches conditionnelles (succès/erreur) et options de retry configurables**,
afin que **je puisse créer des workflows robustes avec gestion d'erreurs et réessais automatiques sans avoir à écrire du code complexe**.

**Contexte :** Les workflows actuels sont des séquences linéaires d'actions. Cet épic ajoute un éditeur graphique avec drag-and-drop, branches conditionnelles (succès/erreur), options de retry avec backoff exponentiel, et validation visuelle des chemins d'exécution.

**Note :** Voir `epic-16-builder-workflow-visuel.md` pour les détails complets des stories.

---

## Epic 15 : Audit de Securite et Conformite SOC1 (premiere release)

Le specialiste securite et l'equipe technique valident que le portail respecte les exigences de securite (NFR6-NFR11) et la conformite SOC1 avant la premiere release en production. Un audit complet du code, des configurations, des tests de securite et de la documentation est realise avec un plan de remédiation pour les vulnerabilites identifiees.

### Story 15.1 : Audit de securite du code (SAST, dependances, secrets)

As a specialiste securite,
I want un audit complet du code source pour identifier les vulnerabilites de securite, les dependances obsolètes ou vulnerables, et les fuites potentielles de secrets,
So que je puisse valider que le code respecte les standards de securite avant la release et documenter les risques identifies.

**Acceptance Criteria:**

**Given** le codebase du portail (frontend React + backend Django),
**When** on execute un audit de securite statique (SAST),
**Then** un outil d'analyse (ex. SonarQube, Bandit pour Python, ESLint security pour JS) scanne tout le code source
**And** un rapport liste toutes les vulnerabilites identifiees avec leur niveau de severite (CRITICAL, HIGH, MEDIUM, LOW)
**And** les vulnerabilites sont categorisees : injection SQL, XSS, CSRF, authentification faible, gestion d'erreurs exposant des informations, etc.
**And** chaque vulnerabilite inclut la localisation exacte (fichier, ligne) et une recommandation de correction

**Given** les dependances du projet (requirements.txt, package.json),
**When** on execute un scan de vulnerabilites des dependances,
**Then** un outil (ex. Snyk, Dependabot, Safety) analyse toutes les dependances Python et npm
**And** un rapport liste les packages vulnerables avec leur version actuelle, la version corrigee disponible, et le CVE associe
**And** les vulnerabilites sont triees par severite et impact sur le projet
**And** un plan de mise a jour est propose pour les vulnerabilites critiques et elevees

**Given** le codebase et les fichiers de configuration,
**When** on execute un scan de detection de secrets,
**Then** un outil (ex. GitGuardian, TruffleHog, detect-secrets) scanne le code et les commits Git
**And** aucun secret (API keys, tokens, mots de passe, certificats) n'est detecte dans le code source ou l'historique Git
**And** si des secrets sont detectes, ils sont immediatement revoques et remplaces par des references a Vault ou des variables d'environnement
**And** NFR7 est verifiee : aucun secret stocke dans le portail

**Given** les resultats des audits,
**When** on consolide les rapports,
**Then** un document d'audit de securite est genere avec un resume executif, la liste complete des vulnerabilites, et leur priorisation
**And** chaque vulnerabilite est documentee avec son impact potentiel, sa probabilite d'exploitation, et son statut (ouvert, en cours, corrige)

### Story 15.2 : Tests de securite fonctionnels (authentification, autorisation, RBAC)

As a specialiste securite,
I want des tests de securite fonctionnels qui valident l'authentification, l'autorisation RBAC, et la protection des endpoints,
So que je puisse prouver que les mecanismes de securite fonctionnent correctement et respectent les exigences NFR6, NFR9, NFR10.

**Acceptance Criteria:**

**Given** les endpoints API du portail,
**When** on execute des tests d'authentification,
**Then** tous les endpoints proteges renvoient HTTP 401 pour les requetes non authentifiees
**And** les tokens JWT expires renvoient HTTP 401 avec un message d'erreur approprie
**And** les tokens JWT invalides ou malformes sont rejetes avec HTTP 401
**And** le mecanisme de refresh token fonctionne correctement et les tokens expires sont renouveles automatiquement
**And** NFR9 est verifiee : les sessions expirent apres la periode d'inactivite configuree

**Given** les regles RBAC du portail (profils, permissions actions/targets/environnements),
**When** on execute des tests d'autorisation,
**Then** un utilisateur avec un profil DBA ne peut acceder qu'aux endpoints autorises pour son profil
**And** un utilisateur avec un profil DBOPS peut acceder aux endpoints Admin
**And** un utilisateur avec un profil Client Business ne peut executer que les actions deleguees a son profil
**And** toute tentative d'acces non autorise renvoie HTTP 403 avec un message d'erreur approprie
**And** NFR10 est verifiee : toutes les tentatives d'acces non autorise sont journalisees dans AUDIT_LOG avec le type d'action APPROVAL_DENIED ou EXECUTION_DENIED

**Given** les endpoints sensibles (execution d'actions, modification de profils, acces aux logs),
**When** on execute des tests de controle d'acces,
**Then** un utilisateur ne peut executer une action que si son profil a la permission pour cette action ET ce target ET cet environnement
**And** un utilisateur ne peut modifier un profil que s'il a le role DBOPS
**And** un utilisateur ne peut consulter les logs d'execution que pour ses propres executions (sauf DBOPS qui peut tout voir)
**And** les validations RBAC sont appliquees a la fois au niveau API et au niveau service/metier

**Given** les tests de securite fonctionnels,
**When** on les execute dans un environnement de test,
**Then** tous les tests passent et un rapport de tests est genere
**And** le rapport documente chaque scenario teste avec le resultat attendu et obtenu
**And** les tests sont integres dans le pipeline CI/CD pour validation automatique a chaque commit

### Story 15.3 : Validation conformite SOC1 (audit trail, immutabilite, chiffrement)

As a specialiste securite / auditeur SOC1,
I want valider que le portail respecte les exigences SOC1 pour l'audit trail, l'immutabilite des logs, et le chiffrement des communications,
So que je puisse certifier la conformite avant la release et documenter les controles de securite.

**Acceptance Criteria:**

**Given** le systeme d'audit du portail (table AUDIT_LOG),
**When** on valide l'immutabilite des logs d'audit,
**Then** aucune operation UPDATE ou DELETE n'est possible sur la table AUDIT_LOG (contraintes DB ou permissions)
**And** les logs d'audit sont ecrits une seule fois et ne peuvent etre modifies apres ecriture
**And** NFR8 est verifiee : les logs d'audit sont immutables
**And** un test demontre qu'une tentative de modification d'un log d'audit echoue avec une erreur appropriee

**Given** chaque execution d'action dans le portail,
**When** on valide la tracabilite complete,
**Then** une entree dans AUDIT_LOG est creee avec : utilisateur (qui), action executee (quoi), timestamp precis (quand), parametres de l'execution, resultat (succes/echec), autorisation RBAC appliquee
**And** FR30 est verifiee : trace d'audit immutable pour chaque execution
**And** les logs d'audit incluent un correlation_id pour tracer une execution complete de bout en bout
**And** les logs d'audit sont consultables via l'API /api/v1/audit avec filtres par environnement, periode, type d'action (FR33)

**Given** les communications entre le portail et les systemes integres (Vault, ServiceNow, plateformes d'execution),
**When** on valide le chiffrement en transit,
**Then** toutes les communications utilisent TLS 1.2 ou superieur
**And** les certificats SSL/TLS sont valides et non expires
**And** NFR6 est verifiee : toutes les communications sont chiffrees en transit
**And** un test demontre qu'une connexion non chiffree est rejetee

**Given** les secrets et credentials utilises par le portail,
**When** on valide la gestion des secrets,
**Then** aucun secret n'est stocke dans le code source, les fichiers de configuration, ou la base de donnees
**And** tous les secrets sont recuperes depuis HashiCorp Vault au moment de l'execution
**And** NFR7 est verifiee : aucun secret stocke dans le portail
**And** FR29 est verifiee : tous les secrets sont recuperes depuis Vault a l'execution
**And** un test demontre qu'une execution echoue avec un message explicite si Vault est indisponible (NFR21)

**Given** les donnees sensibles stockees dans le portail,
**When** on valide la protection des donnees,
**Then** le portail ne stocke que les metadonnees de l'inventaire (noms de bases, environnements, technologies)
**And** aucune donnee sensible des bases de donnees gerees n'est stockee (pas de mots de passe, donnees utilisateurs, etc.)
**And** NFR11 est verifiee : le portail ne conserve aucune donnee sensible
**And** un audit de la base de donnees confirme qu'aucune donnee sensible n'est presente

**Given** les exigences SOC1,
**When** on consolide la validation,
**Then** un document de conformite SOC1 est genere avec la liste des controles valides et les preuves associees
**And** chaque controle SOC1 est documente avec son implementation, sa validation, et les tests associes
**And** les ecarts identifies sont documentes avec un plan de correction et une date cible

### Story 15.4 : Documentation de securite et plan de remédiation

As a responsable technique / specialiste securite,
I want une documentation complete de securite et un plan de remédiation pour toutes les vulnerabilites identifiees,
So que l'equipe puisse corriger les problemes avant la release et que la documentation serve de reference pour les audits futurs.

**Acceptance Criteria:**

**Given** les resultats des audits de securite (Story 15.1, 15.2, 15.3),
**When** on consolide la documentation,
**Then** un document de securite est cree avec :
- Resume executif des vulnerabilites identifiees
- Liste complete des vulnerabilites avec priorisation (CRITICAL, HIGH, MEDIUM, LOW)
- Plan de remédiation avec affectation, estimation, et date cible pour chaque vulnerabilite
- Statut de chaque vulnerabilite (ouvert, en cours, corrige, verifie)
- Preuves de correction (tests, code review, validation)

**Given** les vulnerabilites critiques et elevees identifiees,
**When** on cree le plan de remédiation,
**Then** chaque vulnerabilite CRITICAL et HIGH a une story ou ticket associe avec :
- Description detaillee du probleme
- Impact potentiel et risque associe
- Solution proposee avec estimation
- Criteres d'acceptation pour la correction
- Date cible de correction (avant release si blocker)

**Given** les vulnerabilites non critiques (MEDIUM, LOW),
**When** on les documente,
**Then** elles sont classees en deux categories :
- A corriger avant release (si impact utilisateur ou compliance)
- A corriger post-release (amelioration continue, pas de blocker)

**Given** la documentation de securite,
**When** on la finalise,
**Then** elle inclut :
- Architecture de securite du portail (authentification, autorisation, chiffrement)
- Liste des controles de securite implementes et valides
- Procedures de reponse aux incidents de securite
- Guide de bonnes pratiques pour les developpeurs
- References aux standards et frameworks utilises (SOC1, OWASP Top 10, etc.)

**Given** toutes les vulnerabilites critiques et elevees sont corrigees,
**When** on valide la release,
**Then** un rapport de validation de securite est genere confirmant que :
- Toutes les vulnerabilites CRITICAL et HIGH sont corrigees et verifiees
- Tous les tests de securite fonctionnels passent
- La conformite SOC1 est validee
- Le portail est pret pour la release en production
**And** ce rapport est approuve par le specialiste securite et le responsable technique avant la release

---

## Epic 17 : Reduction de la dette technique & amelioration qualite (audit 06/02/2026)

En tant que **equipe securite (beneficiaire principal) et equipe de developpement**,
je veux **traiter l'ensemble des constats de l'audit qualite du 6 fevrier 2026**,
afin de **reduire durablement la dette technique, diminuer la surface d'attaque, et accelerer la delivery sans regression**.

**Contexte :** Un audit complet du depot `idp-portal` a mis en evidence une dette technique majeure (double backend FastAPI + Django), des opportunites de refactor frontend (composants surdimensionnes), de la duplication dans le client HTTP, ainsi que des axes d'amelioration securite et DevOps (secrets, lockfile, Dockerfile, rate limiting, feature flags).

### Portee (scope)

- **Backend**
  - Finaliser le **decommissionnement FastAPI** (suppression du dossier `backend/` legacy) une fois la migration validee
  - Ameliorer la robustesse de la gestion d'erreurs (restreindre les `except Exception` non justifies)
  - Remplacer les getter/setter JSON repetitifs du modele `Action` par un **OracleJSONField** (ou abstraction equivalente) avec validation
- **Frontend**
  - Refactoriser les fichiers surdimensionnes (en priorite `ExecutionWizard.tsx`) en sous-composants et hooks dedies
  - Extraire un **wrapper HTTP commun** dans `api_client.ts` pour eliminer la duplication (auth, retry 401, parsing erreurs)
  - Remplacer `console.*` par un service de logging frontend + regle linter/CI
  - **UX vue Executions** : densifier la table (reduire hauteur des lignes) ; permettre a l'utilisateur initiateur ou aux admins d'annuler une operation (Soumise/En cours) et de relancer une execution passee avec les memes parametres sans ressaisie
- **Securite & Tooling**
  - Supprimer les secrets par defaut risquant de fuiter en prod et appliquer un **fail-fast** en environnement non-dev si variables manquantes
  - Ajouter `pyproject.toml` + lockfile pour le Django backend (build reproductible)
  - Durcir progressivement le type checking (mypy) jusqu'a le rendre bloquant
- **DevOps**
  - Ajouter des Dockerfile pour backend et frontend (build reproductible)
  - Implementer du rate limiting sur les endpoints exposes
  - Mettre en place un systeme de feature flags (deploiements progressifs)

### Definition of Done (criteres d'acceptation de l'epic)

- Le depot ne contient plus de backend FastAPI legacy (un seul backend cible), et la doc/CI/deploiement sont alignes
- Aucun secret "par defaut" exploitable n'est present ; demarrage refuse en non-dev si secrets non configures
- Les gros composants/pages frontend sont decoupes et testes, sans regression fonctionnelle
- Le client HTTP a une logique commune (auth/retry/errors) sans duplication
- Le JSON Oracle est centralise (champ/abstraction unique) avec validation
- Les `except Exception` non justifies sont supprimes ou documentes ; les erreurs inattendues sont logguees
- Un lockfile est present pour le Django backend ; le durcissement mypy est enclenche
- Les Dockerfile(s) buildent ; rate limiting et feature flags sont disponibles (si retenus)

### Story 17.1 : Finaliser migration backend et decommissionner FastAPI

En tant qu'equipe technique,
je veux supprimer le backend FastAPI legacy une fois la migration Django validee,
afin d'eliminer la dette technique majeure (double backend), eviter les divergences de comportement et simplifier la base de code.

**Contexte (assessment §4.1) :** Le depot contient deux backends complets (`backend/` FastAPI ~48k LOC et `django_backend/` Django). La coexistence represente un risque de divergence, de la duplication et de la confusion.

**Acceptance Criteria:**

**Given** la migration vers Django est validee (parite fonctionnelle, tests, bascule effectuee)
**When** le decommissionnement est execute
**Then** le dossier `backend/` (FastAPI) est supprime du depot
**And** la doc, la CI et les procedures de deploiement ne reference plus FastAPI
**And** un seul backend (Django) est la cible de deploiement

### Story 17.2 : Refactoriser les composants frontend volumineux

En tant que developpeur,
je veux decouper les fichiers frontend qui depassent les bonnes pratiques de taille,
afin d'ameliorer la maintenabilite et la lisibilite (max ~300-400 lignes par composant).

**Contexte (assessment §4.2) :** ExecutionWizard.tsx (1 661 lignes), executions/views.py (1 140), ScheduledExecutionsPage.tsx (692), ExecutionTimeline.tsx (664), ExecutionsPage.tsx (650), catalog/views.py (749).

**Acceptance Criteria:**

**Given** un fichier composant ou page depasse ~500 lignes
**When** le refactoring est realise
**Then** la logique est extraite en sous-composants et/ou hooks dedies
**And** aucun fichier cible ne depasse ~300-400 lignes sans justification
**And** les tests existants passent sans regression
**And** en priorite : ExecutionWizard.tsx (chaque step en composant, hook pour la logique)

### Story 17.3 : Eliminer la duplication dans le client API frontend

En tant que developpeur,
je veux un wrapper HTTP commun dans `api_client.ts`,
afin d'eviter la duplication d'auth, retry 401 et parsing d'erreurs entre apiFetch, apiFetchRaw, apiFetchBlob, apiPostFormData.

**Contexte (assessment §4.3) :** Quatre fonctions dupliquent la meme logique (auth, intercepteur 401, parsing erreurs).

**Acceptance Criteria:**

**Given** le frontend appelle l'API (GET, POST, blob, form-data)
**When** une requete est effectuee
**Then** un wrapper HTTP commun gere : authentification, intercepteur 401 avec retry, parsing d'erreurs au format unifie
**And** les methodes specifiques (apiFetch, apiFetchRaw, apiFetchBlob, apiPostFormData) s'appuient sur ce wrapper sans dupliquer la logique
**And** les tests existants passent

### Story 17.4 : Oracle JSON field pour le modele Action

En tant que developpeur,
je veux centraliser le stockage JSON du modele Action (CLOB) via un champ/abstraction unique avec validation,
afin d'eliminer les 7 paires getter/setter manuelles et d'avoir une validation JSON au niveau du modele.

**Contexte (assessment §4.4) :** Le modele Action stocke du JSON dans des TextField (CLOB) avec getter/setter repetitifs ; pas de validation JSON ni de JSONField natif (Oracle).

**Acceptance Criteria:**

**Given** le modele Action a des champs JSON (parameters_schema, impact_rules, etc.)
**When** on lit ou ecrit ces champs
**Then** un OracleJSONField custom (ou descripteur equivalent) est utilise
**And** la validation JSON est appliquee au niveau du modele
**And** les getter/setter dupliques sont supprimes
**And** les serializers et services restent compatibles

### Story 17.5 : Securiser la gestion des secrets

En tant qu'equipe securite,
je veux qu'aucun secret par defaut ne soit exploitable en production,
afin d'eviter les fuites si les variables d'environnement ne sont pas configurees.

**Contexte (assessment §4.7) :** SECRET_KEY, JWT_SECRET_KEY et mots de passe par defaut en dur ou commentes "development only".

**Acceptance Criteria:**

**Given** l'application demarre en environnement non-dev (staging, production)
**When** SECRET_KEY ou JWT_SECRET_KEY (ou autres secrets critiques) ne sont pas definis
**Then** le demarrage echoue (fail-fast) avec un message explicite
**And** aucun secret "change-me-in-production" ou valeur par defaut exploitable n'est present dans le code
**And** detect-secrets (ou equivalent) est utilise dans le CI

### Story 17.6 : Restreindre les exception catches trop larges

En tant que developpeur,
je veux que les `except Exception` ou `except:` soient restreints aux exceptions specifiques attendues,
afin de ne pas masquer des bugs et de logger les exceptions inattendues.

**Contexte (assessment §4.5) :** 14 occurrences de broad exception catches dans le Django backend ; certains masquent des erreurs (ex. catalog/views.py).

**Acceptance Criteria:**

**Given** du code attrape des exceptions
**When** un `except Exception` ou `except:` est utilise
**Then** il est justifie (fallback graceful documente) ou remplace par des exceptions specifiques
**And** les exceptions inattendues sont loguees avant re-raise ou traitement
**And** les cas identifies dans l'audit (ex. ProfileService) sont corriges

### Story 17.7 : Remplacer console.log par un service de logging frontend

En tant que developpeur,
je veux un service de logging frontend avec niveaux (debug/info/warn/error) et regle linter,
afin que les sorties soient structurees et filtrables (et envoyables au backend en prod si besoin).

**Contexte (assessment §4.6) :** 21 occurrences de console.log/error/warn dans le frontend de production.

**Acceptance Criteria:**

**Given** le code frontend doit emettre des logs
**When** un log est emis
**Then** un service de logging frontend est utilise (niveaux debug/info/warn/error)
**And** les appels directs a `console.log` / `console.error` / `console.warn` sont supprimes ou remplaces
**And** une regle linter/CI interdit l'usage direct de console.* (sauf exception documentee)

### Story 17.8 : pyproject.toml et lockfile pour le Django backend

En tant que developpeur,
je veux un pyproject.toml et un lockfile pour le backend Django,
afin d'avoir des builds reproductibles et un alignement avec les bonnes pratiques Python.

**Contexte (assessment §4.8) :** Le Django backend utilise requirements.txt avec ranges de versions ; pas de lock, contrairement au backend FastAPI qui a deja un pyproject.toml.

**Acceptance Criteria:**

**Given** le backend Django est installe ou build
**When** on installe les dependances
**Then** un pyproject.toml definit les dependances du projet
**And** un lockfile (pip-tools, poetry ou equivalent) fixe les versions exactes
**And** le CI verifie la coherence du lockfile
**And** la doc de build est mise a jour

### Story 17.9 : Rendre mypy bloquant progressivement

En tant que developpeur,
je veux durcir le type checking jusqu'a le rendre bloquant dans le CI,
afin de reduire les erreurs de typage et d'ameliorer la fiabilite.

**Contexte (assessment §4.9) :** Le CI execute mypy avec continue-on-error: true ; strict = false dans le pyproject.toml FastAPI.

**Acceptance Criteria:**

**Given** le CI execute mypy sur le code cible (Django backend et/ou frontend selon portee)
**When** des erreurs de typage sont presentes
**Then** une strategie progressive est definie (baseline, correction par module)
**And** a terme, mypy est execute sans continue-on-error et bloque le merge en cas d'erreur
**And** la configuration mypy (strict ou niveaux) est documentee

### Story 17.10 : Dockerfile pour backend et frontend

En tant qu'equipe DevOps,
je veux des Dockerfile pour le backend et le frontend,
afin de conteneuriser les applications pour des deploiements reproductibles et portables.

**Contexte (assessment §4.10) :** docker-compose existe pour Oracle uniquement ; pas de Dockerfile applicatif ; deploiement via systemd/Nginx manuels.

**Acceptance Criteria:**

**Given** on build l'image backend ou frontend
**When** on utilise le Dockerfile fourni
**Then** l'application demarre correctement dans le conteneur
**And** les secrets ne sont pas inclus dans l'image (injection par env ou volume)
**And** la doc de deploiement mentionne l'option conteneurisee
**And** les Dockerfile sont dans le depot (ou reference explicite)

### Story 17.11 : Rate limiting sur les endpoints publics

En tant qu'equipe securite,
je veux un rate limiting sur les endpoints exposes (API publiques),
afin de limiter les abus et les attaques par force brute.

**Contexte (assessment §6, §7) :** Rate limiting API non implemente.

**Acceptance Criteria:**

**Given** un client appelle un endpoint expose (ex. login, API v1)
**When** le nombre de requetes depasse un seuil defini (par IP ou par utilisateur)
**Then** le serveur repond 429 Too Many Requests (ou equivalent)
**And** la configuration (seuils, fenetre) est parametrable
**And** les endpoints critiques (auth, execution) sont couverts

### Story 17.12 : Systeme de feature flags

En tant qu'equipe produit / DevOps,
je veux un systeme de feature flags,
afin de permettre des deploiements progressifs et des rollouts controles.

**Contexte (assessment §6, §7) :** Pas de systeme de feature flags.

**Acceptance Criteria:**

**Given** une fonctionnalite peut etre livree sans etre activee pour tous les utilisateurs
**When** un feature flag est configure (on/off ou pourcentage)
**Then** le frontend et/ou le backend respectent l'etat du flag
**And** la configuration des flags est centralisee (fichier, env, ou service dedie)
**And** l'impact sur la CI et le deploiement est documente

### Story 17.13 : Densite table Executions

As a DBA,
I want que les lignes de la table Executions soient plus compactes,
So that je puisse afficher plus d'executions a l'ecran sans scroller.

**Acceptance Criteria:**

**Given** un DBA accede a la vue Executions
**When** la table se charge
**Then** les lignes ont une hauteur reduite (padding vertical, badges, icones compacts) tout en restant lisibles

**Given** la table affiche les colonnes Action, Statut, Technologie, Plateforme, Utilisateur, Environnement, Date
**When** le DBA consulte la liste
**Then** plus de lignes sont visibles dans le viewport sans scroll qu'avant

### Story 17.14 : Annuler une operation (initiateur ou admin)

As a DBA ou admin,
je veux annuler une operation (statut Soumise ou En cours) que j'ai declenchee, ou n'importe quelle operation si je suis admin,
afin de corriger rapidement une erreur de parametrage ou une operation lancee par erreur.

**Privileges :** L'utilisateur qui a declenche l'operation peut l'annuler ; les **admins** peuvent annuler **n'importe quelle** operation.

**Acceptance Criteria:**

**Given** un DBA a declenche une operation (statut Soumise ou En cours)
**When** il consulte la vue Executions
**Then** un bouton ou action "Annuler" est visible sur la ligne pour les operations qu'il a initiees

**Given** un utilisateur avec role admin consulte la vue Executions
**When** il voit une operation Soumise ou En cours (initiee par n'importe qui)
**Then** un bouton ou action "Annuler" est visible ; l'admin peut annuler n'importe quelle operation

**Given** le DBA ou l'admin clique sur "Annuler" pour une operation Soumise ou En cours
**When** il confirme l'annulation
**Then** l'operation est annulee et le statut est mis a jour (ex. Annulee)
**And** les privileges sont : initiateur de l'operation OU admin (RBAC)

**Given** une operation est en cours d'execution sur le moteur distant
**When** le DBA ou l'admin annule
**Then** le backend tente d'annuler l'execution cote AAP/moteur si supporte, ou marque comme annulee

### Story 17.15 : Relancer une execution (parametres pre remplis, modifiables)

As a DBA ou admin,
je veux relancer une execution passee en partant des memes parametres (que j'ai initiee, ou n'importe laquelle si je suis admin),
afin de gagner du temps tout en pouvant ajuster les parametres avant de reexecuter.

**Privileges :** L'utilisateur qui a declenche l'execution peut la relancer ; les **admins** peuvent relancer **n'importe quelle** execution.

**Acceptance Criteria:**

**Given** un DBA consulte la vue Executions
**When** il selectionne une execution passee qu'il a initiee (terminee, echouee ou annulee)
**Then** un bouton ou action "Relancer" est disponible

**Given** un utilisateur avec role admin consulte la vue Executions
**When** il selectionne une execution passee (initiee par n'importe qui)
**Then** un bouton ou action "Relancer" est disponible ; l'admin peut relancer n'importe quelle execution

**Given** le DBA ou l'admin clique sur "Relancer" pour une execution
**When** l'action est declenchee
**Then** le wizard d'execution s'ouvre avec les parametres pre remplis (action, target(s), environnement, parametres dynamiques) issus de l'execution passee
**And** l'utilisateur peut modifier tout ou partie de ces parametres avant de soumettre
**And** a la soumission du wizard, une nouvelle execution est creee avec les parametres affiches (pre remplis ou modifies)
**And** les privileges sont : initiateur de l'execution OU admin (RBAC)

**Given** le DBA n'a plus les permissions pour l'action ou l'environnement (et n'est pas admin)
**When** il tente de relancer
**Then** une erreur explicite est affichee et le wizard ne demarre pas (ou l'execution n'est pas creee a la soumission)

### Story 17.16 : Verification conformite FRONTEND-STANDARDS

En tant qu'equipe produit,
je veux que la conformite aux standards definis dans FRONTEND-STANDARDS.md soit verifiable et appliquee dans le code,
afin que les regles (React 19, Ant Design 6.2, APIs publiques, naming, tests) restent respectees au fil des evolutions.

**Contexte :** Le document idp-portal/frontend/FRONTEND-STANDARDS.md (Story 5.5) definit les regles adoptees ; aucun mecanisme ne garantit aujourd'hui que le code reste conforme.

**Acceptance Criteria:**

**Given** le document FRONTEND-STANDARDS.md
**When** on execute une verification (script, ESLint, ou CI)
**Then** les regles suivantes sont controlees automatiquement : pas d'import depuis antd/es/*, pas de class components, message/notification/modal via App.useApp() uniquement, types Table extraits depuis TableProps

**Given** une PR frontend
**When** elle est soumise
**Then** la checklist PR Frontend est integree (template ou CI) ou couverte par les verifications automatiques

**And** les tests existants passent ; pas de regression ; exceptions documentees si besoin

### Story 17.17 : Optimisation des requetes BD — page Catalogue

En tant qu'utilisateur du portail,
je veux que la page Catalogue se charge rapidement,
afin que l'experience reste fluide meme avec peu d'actions affichees.

**Contexte :** La page Catalogue (peu d'actions) est percue comme lente ; les donnees viennent de catalog/actions, catalog/tags, users/me/favorites.

**Acceptance Criteria:**

**Given** les endpoints utilises par la page Catalogue (catalog/actions, catalog/tags, users/me/favorites)
**When** un audit est realise
**Then** on dispose d'un inventaire : nombre de requetes par endpoint, N+1, select_related/prefetch_related, index

**Given** l'audit
**When** on applique les optimisations
**Then** les vues catalog et favoris n'executent plus de N+1 ; jointures via select_related/prefetch_related ; index adaptes si besoin

**And** le temps de reponse (ou nombre de requetes) est mesure avant/apres ; gains documentes

---

## Epic 18 : Ameliorations UX et corrections issues du feedback utilisateurs

En tant que **DBOPS et DBA**,
je veux **des corrections et ameliorations basees sur le feedback utilisateurs recueilli**,
afin de **fluidifier l'usage quotidien du portail, eliminer les irritants et fiabiliser les statuts d'execution**.

**Contexte :** Feedback terrain sur l'admin des actions, le mode visuel du builder de workflows, le catalogue, les favoris et l'affichage des erreurs d'integration.

### Portee (scope)

- **Admin Actions** : suppression/désactivation des actions jamais exécutées, filtres (actives par défaut, désactivées via filtre), propagation aux workflows
- **Admin + Catalogue** : identification visuelle des workflows vs actions (icône ou type avec icône)
- **Builder visuel** : taille fenêtre, déplacement blocs Départ/Fin, lien automatique sans erreur, affichage du nom d'action
- **Catalogue** : filtre Environnement obsolète (environnement = propriété du target)
- **Favoris** : correction du compteur et de l'affichage (actions désactivées)
- **Execution** : afficher le statut erreur quand l'intégration échoue (pas "soumis")
- **Tests** : correction des tests en échec (fixtures, migrations, refactorings)

### Definition of Done (criteres d'acceptation de l'epic)

- Les actions jamais exécutées peuvent être supprimées ; les autres peuvent être désactivées (avec message si workflow impacté)
- Les workflows et actions sont visuellement distincts dans Admin et Catalogue
- Le mode visuel du builder offre une zone de travail suffisante et des blocs repositionnables
- Le filtre Environnement du catalogue est retiré ou adapté au modèle target-first
- Les favoris affichent correctement le contenu et le compteur
- Une erreur d'intégration se traduit par un statut erreur visible (pas soumis)
- La suite de tests (backend et frontend) passe à nouveau

### Story 18.1 : Admin Actions — suppression, désactivation et filtres

En tant que **DBOPS**,
je veux **supprimer les actions jamais exécutées et désactiver les autres**, avec filtres pour voir actives par défaut et désactivées à la demande,
afin de **maintenir un catalogue propre tout en préservant la traçabilité des exécutions passées**.

**Acceptance Criteria:**

**Given** une action dans l'admin
**When** elle n'a jamais été exécutée
**Then** je peux la supprimer

**Given** une action ayant au moins une exécution passée
**When** je veux la retirer du catalogue actif
**Then** je peux la désactiver (pas supprimer, pour traçabilité/audit)

**Given** je désactive une action utilisée par un ou plusieurs workflows
**When** je confirme la désactivation
**Then** un message de confirmation m'informe que le(s) workflow(s) sera/seront désactivé(s) aussi
**And** le(s) workflow(s) référençant cette action est/sont désactivé(s)

**Given** la liste des actions en admin
**When** j'accède par défaut
**Then** je vois uniquement les actions actives

**Given** je veux gérer les actions désactivées
**When** j'applique un filtre "Inclure désactivées" (ou équivalent)
**Then** je vois les actions désactivées, pouvant les réactiver ou les modifier

### Story 18.2 : Identification visuelle workflow vs action (Admin et Catalogue)

En tant que **DBOPS ou DBA**,
je veux **distinguer facilement les workflows des actions simples** dans les listes,
afin de **identifier rapidement le type d'élément sans lire le détail**.

**Acceptance Criteria:**

**Given** la liste des actions en admin
**When** j'affiche les lignes
**Then** chaque élément affiche une icône ou un indicateur (type + icône) permettant de distinguer workflow vs action

**Given** la liste des actions côté catalogue
**When** j'affiche les cartes ou la liste
**Then** chaque élément affiche la même distinction visuelle (icône ou type avec icône)

### Story 18.3 : Mode visuel builder — taille, blocs, lien et libellé

En tant que **DBOPS**,
je veux **un mode visuel du builder de workflows plus utilisable**,
afin de **concevoir et modifier les workflows sans friction**.

**Acceptance Criteria:**

**Given** je crée ou modifie un workflow en mode visuel
**When** la fenêtre modale s'ouvre
**Then** la zone de dessin (canvas) est suffisamment grande pour visualiser le workflow sans scroll excessif

**Given** les blocs Départ et Fin sur le canvas
**When** je souhaite réorganiser la disposition
**Then** je peux déplacer les blocs Départ et Fin (comme les autres blocs d'action)

**Given** j'ajoute la première action au workflow (entre Départ et Fin)
**When** la connexion Départ → première action est établie
**Then** le lien se crée automatiquement sans condition et s'affiche en succès (pas en erreur)

**Given** je sauvegarde un workflow puis je le rouvre
**When** je visualise les blocs d'action
**Then** le nom de l'action s'affiche (ex. "Apply Oracle Patch"), pas un libellé générique "Action #2"

### Story 18.4 : Catalogue — retirer ou adapter le filtre Environnement

En tant que **utilisateur du catalogue**,
je veux **que le filtre Environnement soit pertinent ou retiré**,
afin de **ne pas être induit en erreur** : l'environnement est défini par le target, pas par l'action.

**Acceptance Criteria:**

**Given** le catalogue avec filtre Environnement actuel
**When** les actions ne sont plus reliées directement à un environnement (c'est le target qui définit l'environnement)
**Then** le filtre Environnement est retiré OU adapté pour refléter le modèle target-first (ex. filtrer par environnements des targets disponibles)

### Story 18.5 : Favoris — correction affichage et compteur

En tant que **DBA**,
je veux **que mes actions favorites s'affichent correctement** dans l'onglet Favoris,
afin de **retrouver rapidement les actions que j'utilise le plus**.

**Acceptance Criteria:**

**Given** j'ai des actions en favoris
**When** j'accède à l'onglet Favoris
**Then** les actions favorites s'affichent (et non une liste vide)

**Given** une action en favoris est désactivée
**When** je consulte mes favoris
**Then** le compteur et l'affichage excluent ou gèrent correctement les actions désactivées (pas de compteur incorrect ni d'onglet vide alors qu'un chiffre s'affiche)

**And** la requête côté client/serveur retourne bien les favoris visibles (investigation possible : action désactivée encore comptée côté serveur mais non retournée dans la liste)

### Story 18.6 : Erreur intégration — afficher statut erreur

En tant que **DBA ou utilisateur**,
je veux **voir un statut erreur** quand l'intégration (AAP, ServiceNow, etc.) retourne une erreur,
afin de **savoir immédiatement que l'action n'a pas été correctement soumise**.

**Acceptance Criteria:**

**Given** je déclenche une action
**When** l'intégration (plateforme distante) retourne une erreur
**Then** l'exécution n'apparaît pas comme "soumise" ou "en cours" de manière trompeuse
**And** l'exécution affiche un statut erreur explicite (ex. "Erreur", "Échec intégration")
**And** un message ou un détail permet de comprendre la cause (idéalement issu de la réponse d'erreur de l'intégration)

**Given** le backend reçoit une erreur de l'intégration avant ou pendant la création de l'exécution
**When** la réponse est traitée
**Then** le statut en base et/ou le callback reflètent l'état d'erreur
**And** le frontend affiche correctement ce statut (pas de statut "soumis" pour une exécution qui a échoué côté intégration)

### Story 18.7 : Correction des tests en échec

En tant qu'**équipe de développement**,
je veux **que l'ensemble des tests (backend et frontend) passent à nouveau**,
afin de **restaurer la confiance dans la suite de tests et permettre les déploiements en CI**.

**Contexte :** Un bon nombre de tests échouent actuellement ; causes possibles : fixtures obsolètes (ex. User), migrations, refactorings (OracleJSONField, etc.), changements d'API ou de modèles. Cette story vise à identifier et corriger ces échecs.

**Acceptance Criteria:**

**Given** la suite de tests backend et frontend
**When** on exécute `pytest` (backend) et les tests frontend (Vitest/Jest)
**Then** l'ensemble des tests passent (ou les échecs restants sont documentés avec tickets de suivi)

**Given** des tests échouent pour cause de fixtures obsolètes (User, Action, etc.)
**When** on corrige les fixtures
**Then** elles reflètent le modèle de données et les contraintes actuels

**Given** des tests échouent pour cause de refactoring (OracleJSONField, changements d'API)
**When** on adapte les tests
**Then** ils valident le comportement attendu sans dépendre d'implémentations internes fragiles

**And** la CI (ou commande locale) exécute la suite complète avec succès ; les échecs connus sont documentés si des corrections sont reportées

---

## Epic 21 : Inventaire — source unique des environnements

En tant que **équipe produit et utilisateurs du portail**,
je veux **que l'inventaire soit la seule source de vérité pour les environnements**, sans normalisation ni liste hardcodée,
afin de **accepter toute valeur présente dans l'inventaire (ex. lab, dev, staging, prod), éviter les cascades de requêtes Oracle et les warnings, et permettre l'ajout de nouveaux environnements sans migration**.

**Contexte :** `_normalize_environment` impose une liste fixe, appelle récursivement `list_environments()`, et force les valeurs inconnues vers `dev`, provoquant récursion, incohérence et problèmes de perf.

**Reference :** planning-artifacts/epic-21-inventaire-source-unique-environnements.md

### Story 21.1 : Backend — Supprimer normalisation inventaire et utiliser valeurs brutes

En tant que développeur backend,
je veux que la lecture de l'inventaire Oracle retourne les valeurs ENVIRONMENT telles quelles (trim/lowercase uniquement),
afin d'éliminer la récursion et les warnings `unknown_environment_value_defaulted`.

**Acceptance Criteria:**

**Given** `_read_oracle_inventory` dans `inventory/services.py`
**When** une ligne Oracle contient `ENVIRONMENT = 'lab'`
**Then** la valeur retournée est `lab` (ou lowercased), sans appel à `_normalize_environment`
**And** aucun warning `unknown_environment_value_defaulted` n'est loggé

**Given** la méthode `_normalize_environment`
**When** on la supprime ou la simplifie
**Then** elle ne contient plus d'appel à `list_environments()`
**And** optionnel : on conserve uniquement un mapping d'alias pour legacy (ex. certif→staging) sans appel récursif

**Given** `list_environments()`
**When** elle extrait les environnements distincts des targets
**Then** elle utilise les valeurs brutes des targets (sans normalisation dans la boucle)

### Story 21.2 : Backend — Ajuster profile/env matching et exécutions

En tant que développeur backend,
je veux que les profils et les exécutions comparent les environnements de manière case-insensitive sans normalisation forcée,
afin d'accepter les valeurs de l'inventaire et des profils de façon cohérente.

**Acceptance Criteria:**

**Given** `list_targets_for_user` et `get_allowed_environments_for_user`
**When** un profil a `ENVIRONMENTS_JSON = ["lab", "dev"]` et l'inventaire contient lab, dev
**Then** la comparaison est case-insensitive
**And** les targets avec `environment: lab` sont autorisés

**Given** `_validate_environment_against_inventory`
**When** l'environnement soumis est lab et l'inventaire le contient
**Then** la validation réussit
**And** aucun fallback vers dev n'est appliqué

**Given** `change_type_config` et `impact_rules` lookup
**When** l'environnement d'exécution est lab
**Then** le lookup utilise env_upper ou comparaison case-insensitive
**And** si aucune règle n'existe pour lab, `default_impact_level` est utilisé pour impact

### Story 21.3 : Tests backend — inventaire, exécutions, profils

En tant que développeur,
je veux que les tests couvrent les nouveaux comportements (valeurs brutes, profils avec lab, exécutions avec env inconnu),
afin d'éviter les régressions et documenter le comportement attendu.

**Acceptance Criteria:**

**Given** les tests `inventory/tests/test_services.py`
**When** on exécute la suite
**Then** les tests de `_normalize_environment` sont mis à jour ou supprimés
**And** des tests vérifient que `list_targets` retourne des environnements bruts (ex. lab)
**And** des tests vérifient que `list_environments()` retourne les valeurs distinctes sans normalisation

**Given** les tests d'exécution et de profils
**When** un profil a `environments: [lab]` et l'inventaire contient lab
**Then** les tests vérifient l'accès autorisé

### Story 21.4 : Frontend — Editeurs admin avec environnements dynamiques

En tant que DBOPS,
je veux que les editeurs d'actions (règles d'impact, étapes, changement ServiceNow, règles de remédiation) proposent la liste des environnements issue de l'inventaire,
afin de configurer des règles pour tous les environnements existants (ex. lab, dev, staging, prod) sans liste fixe.

**Acceptance Criteria:**

**Given** `ImpactRulesEditor`
**When** j'ajoute une règle d'impact
**Then** le dropdown Environnement affiche les options de `useEnvironments()`
**And** `IMPACT_ENVIRONMENTS` hardcodé est remplacé par la liste dynamique

**Given** `StepsEditor`, `ChangeTypeConfig`, `RemediationRulesEditor`
**When** je configure des environnements (conditional_environments, change type, remediation)
**Then** les composants utilisent les environnements de l'inventaire
**And** les listes hardcodées sont remplacées

### Story 21.5 : Frontend — TargetSelectionStep, labels et type ExecutionEnvironment

En tant que DBA ou utilisateur,
je veux que la sélection d'environnement et l'affichage des labels utilisent les valeurs de l'inventaire sans fallback hardcodé,
afin de pouvoir exécuter des actions sur des environnements comme lab et les afficher correctement.

**Acceptance Criteria:**

**Given** `TargetSelectionStep`
**When** le cache d'environnements est chargé
**Then** le Select Environnement utilise uniquement ces valeurs
**And** le fallback `[dev, staging, prod]` est supprimé

**Given** `ENVIRONMENT_LABELS`
**When** un environnement n'est pas dans la map (ex. lab)
**Then** on affiche la valeur avec capitalisation ou telle quelle

**Given** le type `ExecutionEnvironment`
**When** on étend le type
**Then** `ExecutionEnvironment` devient `string` (ou union étendue) pour accepter lab et autres

### Story 21.6 (optionnel) : Validation des environnements de profil à la sauvegarde

En tant que DBOPS,
je veux que la sauvegarde d'un profil valide que les environnements sélectionnés existent dans l'inventaire,
afin d'éviter les typo et les références à des environnements obsolètes.

**Acceptance Criteria:**

**Given** le formulaire de profil
**When** je sauvegarde un profil avec `environments: [lab, invalid_env]`
**Then** le backend vérifie que chaque valeur existe dans `list_environments()`
**And** si invalid_env n'existe pas, une erreur de validation est retournée

---

## Epic 23 : Inventaire multi-tables (SERVER, INSTANCE, DB) et UX cibles

Étendre l'inventaire pour supporter les tables SERVER, INSTANCE et DB avec relations, filtrer les listes instance/DB par serveur choisi dans le wizard, permettre aux profils d'accorder l'accès « tous les serveurs Oracle » ou « tous les serveurs SQL », avec un modèle d'accès évolutif (mapping colonnes) et un RBAC intimement lié aux données d'inventaire.

**Source :** docs/inventaire-multi-tables-ux-cibles.md

### Exigences couvertes (résumé)

- **Données :** Plusieurs tables (SERVER, INSTANCE, DB), relations Serveur 1–N Instance, Instance → DB, DB 1–N Instances. Modèle piloté par config (mapping entités/colonnes/relations), pas de colonnes en dur.
- **Définition des paramètres (Admin) :** Lors de la définition d’un paramètre pour une action, DBOPS peut indiquer que la valeur **provient de l’inventaire** et choisir **quelle table/entité** : **serveurs**, **instances** ou **bases de données**. Le schéma des paramètres de l’action porte cette info (ex. `source: 'inventory'`, `inventory_type: 'servers' | 'instances' | 'databases'`). Les éditeurs Admin (paramètres d’action) doivent proposer explicitement ce choix.
- **UX exécution (Wizard) :** Si l’utilisateur a choisi un ou plusieurs serveurs à l’étape 1 (cibles), alors pour tout paramètre marqué « source = inventaire, table = **instances** » (ex. `instance_name`), la liste déroulante à l’étape 2 n’affiche **que les instances liées au(x) serveur(s) choisi(s)**. Idem pour « table = **databases** » : uniquement les bases liées à ce(s) serveur(s). Pour « table = serveurs », la liste reste filtrée par environnement (comportement actuel).
- **Profils :** Options « Tous les serveurs Oracle » / « Tous les serveurs SQL » (filtre par type de moteur) ; RBAC sur attributs mappés (ex. `engine_type`).
- **API :** `GET /inventory/servers`, `/databases`, `/instances` avec `environment` et `server_name`/`server_names` ; format `{ data: [...] }`.
- **Sécurité / perf :** Validation stricte noms tables/colonnes et paramètres ; pagination / limite de serveurs pour gros inventaires ; rétrocompatibilité table plate.

### Comportement cible (exemple)

- **Admin :** Pour l’action « Patching instance », le paramètre `instance_name` est configuré avec : source = inventaire, table = **instances**.
- **Exécution :** L’utilisateur choisit `server1` (et éventuellement `server2`) à l’étape 1. À l’étape 2, le champ `instance_name` affiche **uniquement les instances liées à server1** (et server2 si multi-sélection). Pas toutes les instances de l’environnement.

### Stories proposées (ordre suggéré)

1. **Backend — Config mapping colonnes + lecture entités** : Config (entités, colonnes, relations), layer InventoryMapper, requêtes SQL pilotées par config, fallback table plate.
2. **Backend — InventoryService multi-tables** : `list_servers`, `list_instances`, `list_databases` avec filtres environment / server_name / engine_type ; RBAC list_targets_for_user inchangé sur serveurs, listes instance/DB cohérentes avec serveurs autorisés.
3. **Backend — API /servers, /databases, /instances** : Endpoints avec query params, format attendu par le front.
4. **Backend — RBAC profils filtres par attribut** : Champ JSON `filter_by_attribute` (ex. engine_type), application dans `list_targets_for_user`, exposition API profils.
5. **Frontend — Admin : source inventaire + table par paramètre** : Dans l’éditeur de paramètres d’une action, permettre de marquer un paramètre « source = inventaire » et de choisir la table : **Serveurs**, **Instances** ou **Bases de données**. Persistance dans le schéma (ex. `inventory_type`) pour alimenter le wizard.
6. **Frontend — useTargetInventory + contexte serveur** : Paramètre `selectedServerNames` (ou `selectedTargets`), appels API avec `server_name`/`server_names` pour les paramètres de type instances/databases ; à l’étape 2 du wizard, les listes instance/DB sont restreintes aux instances/bases du (des) serveur(s) choisi(s).
7. **Frontend — ProfileForm options Tous / Oracle / SQL** : UI pour filtres par type de moteur (et extension à d’autres attributs mappés).

## Epic 24 : Intégrations Admin alignées sur le backend

Encadrer la configuration des intégrations dans l'interface Admin pour n'autoriser que des types et des actions d'intégration explicitement supportés par le backend (AAP, ServiceNow, etc.), via un modèle "type d'intégration" + "instance d'intégration" et un catalogue d'actions contractuel. L'objectif est de supprimer les intégrations "libres" non supportées, réduire les erreurs de configuration, et rendre les exécutions d'intégrations prévisibles et observables.

### Exigences couvertes (résumé)

- **Modèle d'intégration** : Distinction claire entre **Type d'intégration** (AAP, ServiceNow, …) et **Instance d'intégration** (ex. "AAP Dev", "ServiceNow ITSM Préprod"). Chaque type définit un catalogue d'actions supportées (ex. `start_job`, `start_workflow`, `get_job_status`, `create_change`) avec leur contrat de paramètres minimal.
- **Catalogue d'actions contractuel** : Le backend expose pour chaque type la liste des actions possibles, leurs noms, descriptions, paramètres attendus (obligatoires / optionnels) et formats de réponse. Le frontend consomme ce catalogue et ne peut pas inventer de nouvelles actions.
- **UI Admin restreinte** : L'écran Admin Intégrations permet uniquement de créer/éditer des **instances d'intégration** en choisissant un **type existant** fourni par le backend, puis en remplissant les paramètres attendus (URL, credentials, IDs de templates, options métiers, etc.). Aucun champ ne permet de définir directement des verbes HTTP ou des endpoints arbitraires.
- **Validation forte** : Une intégration dont le type ou une action n'existe plus côté backend est marquée comme **invalide ou dépréciée** ; elle est clairement signalée dans l'UI, et son utilisation dans les workflows est bloquée ou dégradée de manière contrôlée.
- **Migration & compatibilité** : Les intégrations existantes "libres" sont migrées vers des instances typées autant que possible, ou marquées comme "legacy / read-only" avec garde-fous pour éviter de nouvelles utilisations.

### Stories proposées (ordre suggéré)

1. **Backend — Catalogue des types d'intégration et actions supportées**  
   Définir le modèle `IntegrationType` (nom, code, version, description) et la liste des `IntegrationAction` associées (nom technique, label, description, paramètres exigés). Exposer une API de lecture (ex. `GET /api/v1/integrations/types`) permettant au frontend de récupérer le catalogue complet, avec versionnement minimal pour tracer les changements.

2. **Frontend Admin — Création d'instances à partir des types d'intégration backend**  
   Adapter l'écran Admin Intégrations pour que la création/édition passe obligatoirement par la sélection d'un `IntegrationType` renvoyé par le backend, puis par la configuration des champs attendus (URL, credential_ref, IDs AAP/ServiceNow, options métiers). Supprimer ou masquer les champs qui permettent d'encoder directement des endpoints/verbs/payloads arbitraires.

3. **Backend & Frontend — Validation d'intégration et état (valide / invalide / dépréciée)**  
   Introduire un statut d'intégration (`valid`, `invalid`, `deprecated`) calculé côté backend en fonction de l'existence du type et des actions référencées. Exposer ce statut via l'API, l'afficher clairement dans l'UI Admin (badge + message), et empêcher l'utilisation d'intégrations `invalid` dans les nouveaux workflows ou exécutions.

4. **Migration des intégrations existantes et garde-fous d'exécution**  
   Identifier les intégrations déjà configurées dans le système : pour chacune, tenter de les rattacher à un `IntegrationType` existant (AAP, ServiceNow, …) ou les marquer comme `legacy`. Mettre en place des garde-fous côté moteur d'exécution pour refuser proprement l'utilisation d'intégrations non typées ou invalides, avec messages d'erreur explicites et logs d'audit.
