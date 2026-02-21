# Analyse des alternatives Open-Source — IDP Portal

**Date :** 2026-02-21
**Objectif :** Évaluer si des outils open-source existants (seuls ou combinés) couvrent les mêmes spécifications et fonctionnalités que l'IDP Portal.

---

## 1. Périmètre fonctionnel de l'IDP Portal

L'IDP Portal est une plateforme interne de self-service pour les opérations base de données (Oracle, SQL Server, DB2) dans un contexte bancaire/réglementé.

### Stack technique
- **Backend :** Django 5.2 + DRF 3.16, Oracle DB, Celery + Redis
- **Frontend :** React 19 + Vite + TypeScript + Ant Design 6.2
- **Auth :** SAML 2.0 SSO, JWT (30min access / 8h refresh)
- **Infra :** Docker, Nginx, GitHub Actions CI/CD, Splunk, Dynatrace

### 12 fonctionnalités clés identifiées

| # | Fonctionnalité | Description |
|---|----------------|-------------|
| 1 | **Catalogue logiciel DB** | Catalogue structuré d'actions DB (Oracle, SQL Server, DB2) avec métadonnées, tags, catégories, niveaux d'impact |
| 2 | **Orchestration multi-plateforme** | Déclenchement de jobs sur AAP/Tower, GitHub Actions, Azure DevOps, Terraform Cloud via adaptateurs |
| 3 | **Portail self-service guidé** | Wizard multi-étapes (environnement → paramètres → confirmation) pour utilisateurs non-techniques |
| 4 | **RBAC multi-dimensionnel** | Permissions par action × cible × environnement, mapping groupes AD, multi-profils (union) |
| 5 | **Monitoring temps réel** | Timeline WebSocket des étapes d'exécution avec mise à jour en direct |
| 6 | **Intégration Vault** | Zéro credentials stockés localement, résolution runtime via HashiCorp Vault |
| 7 | **Intégration ServiceNow ITSM** | Création automatique de tickets de changement pré-approuvés (non-bloquant) |
| 8 | **Piste d'audit immuable** | Table append-only SOC1, traçabilité complète (qui, quoi, quand, où, résultat) |
| 9 | **Workflows d'approbation** | Approbation manuelle pour opérations à haut risque / production, règles métier post-exécution |
| 10 | **Dashboards & analytics** | Statistiques, séries temporelles, comparaisons, export CSV/PDF |
| 11 | **SAML 2.0 SSO** | Authentification entreprise SP-initiated |
| 12 | **Callbacks webhook** | Réception de callbacks des plateformes d'exécution (AAP, GitHub, Azure DevOps, Terraform) |

---

## 2. Évaluation individuelle des outils

### 2.1. Rundeck (PagerDuty)

**Licence :** Apache 2.0 (Community), propriétaire (Enterprise)

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 1 - Catalogue DB | Absent | Pas de concept de catalogue structuré ; jobs organisés par projet/groupe sans taxonomie |
| 2 - Multi-plateforme | Partiel | Peut appeler Ansible, webhooks vers GitHub/Azure. Pas un orchestrateur d'orchestrateurs natif |
| 3 - Self-service | **Fort** | Force principale — exécution de jobs via formulaires. Mais formulaires plats, pas de wizard multi-étapes |
| 4 - RBAC + AD | Partiel/Enterprise | LDAP supporté, ACL fines possibles. **SAML/SSO = Enterprise uniquement** |
| 5 - Temps réel | Partiel | Streaming de logs (polling), pas de timeline WebSocket |
| 6 - Vault | **Oui** | Plugin officiel : Vault comme backend Key Storage |
| 7 - ServiceNow | **Oui** | Plugin officiel pour incidents et change records |
| 8 - Audit | Bon | Journal d'activité. Immuabilité non garantie en OSS |
| 9 - Approbations | Enterprise | Pas dans l'édition communautaire |
| 10 - Dashboard/export | Enterprise | Basique en OSS, avancé en Enterprise |
| 11 - SAML SSO | Enterprise | OSS = LDAP et pré-auth uniquement |
| 12 - Webhooks | **Oui** | Handlers webhook + notifications |

**Verdict :** Rundeck OSS couvre ~5-6/12. Enterprise monte à ~9-10. Manque le catalogue structuré et le wizard multi-étapes.

---

### 2.2. Squest (HPE) + AWX

**Licence :** GPL-3.0 (Squest), Apache 2.0 (AWX)

Squest est un portail self-service construit au-dessus d'AWX/Ansible Tower, développé par Hewlett Packard Enterprise.

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 1 - Catalogue DB | Bon | Catalogue de services avec définitions, suivi d'instances, opérations disponibles |
| 2 - Multi-plateforme | Partiel | AWX exécute Ansible nativement. Peut appeler GitHub/Azure/Terraform via modules Ansible, mais de manière indirecte |
| 3 - Self-service | **Fort** | Objectif principal de Squest : formulaires, navigation catalogue, gestion cycle de vie |
| 4 - RBAC + AD | Bon | AWX supporte LDAP, SAML, RBAC. Squest ajoute sa propre couche RBAC |
| 5 - Temps réel | Partiel | AWX fournit le streaming de sortie de jobs. Pas de timeline WebSocket dans Squest |
| 6 - Vault | **Oui** | AWX intègre Vault nativement |
| 7 - ServiceNow | Partiel | Pas d'intégration native Squest-ServiceNow, doit passer par des playbooks Ansible |
| 8 - Audit | Bon | AWX log toutes les exécutions. Squest trace le cycle de vie des requêtes |
| 9 - Approbations | **Oui** | Workflows d'approbation intégrés à Squest |
| 10 - Dashboard/export | Basique | Dashboard limité, pas d'export CSV/PDF natif |
| 11 - SAML SSO | **Oui** (AWX) | AWX supporte SAML nativement |
| 12 - Webhooks | Partiel | AWX supporte les webhooks de notification. Squest n'a pas de récepteur webhook natif |

**Verdict :** Couvre ~7-8/12. Combinaison la plus proche en full OSS si Ansible est le moteur principal. Manque l'orchestration multi-plateforme directe, le WebSocket, et les dashboards.

---

### 2.3. Windmill

**Licence :** AGPLv3 (self-host gratuit pour <10 utilisateurs), Enterprise pour SAML

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 1 - Catalogue DB | Absent | Moteur de workflows, pas de catalogue structuré |
| 2 - Multi-plateforme | **Fort** | Peut appeler n'importe quelle API via scripts Python/TypeScript/Go |
| 3 - Self-service | **Fort** | UIs auto-générées + constructeur d'apps low-code pour wizards |
| 4 - RBAC + AD | Bon/Enterprise | RBAC granulaire. **SAML + SCIM = Enterprise uniquement** |
| 5 - Temps réel | **Oui** | Streaming temps réel, visualisation de progression |
| 6 - Vault | **Oui** | Intégration HashiCorp Vault native |
| 7 - ServiceNow | Possible | Pas d'intégration pré-construite, développement custom via REST API |
| 8 - Audit | **Oui** | Chaque exécution loguée avec utilisateur, entrées, sorties, timestamps |
| 9 - Approbations | **Oui** | Étapes d'approbation natives (suspension + reprise) |
| 10 - Dashboard/export | Partiel | Constructeur d'apps pour dashboards. Pas d'export CSV/PDF natif |
| 11 - SAML SSO | Enterprise | SAML est une fonctionnalité Enterprise |
| 12 - Webhooks | **Oui** | Endpoints webhook auto-générés pour chaque script/flow |

**Verdict :** Couvre ~7-8/12 (9-10 avec Enterprise). Le plus flexible pour construire un portail custom, mais il faut tout développer soi-même (catalogue, ServiceNow, exports).

---

### 2.4. Backstage (Spotify)

**Licence :** Apache 2.0

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 1 - Catalogue DB | **Excellent** | Force principale — modèle d'entités extensible, métadonnées, ownership, tags |
| 2 - Multi-plateforme | Absent | N'exécute rien. Software Templates = scaffolding uniquement |
| 3 - Self-service | Faible | Templates pour créer des repos/services. Pas d'opérations Day-2 |
| 4 - RBAC + AD | Partiel | Framework de permissions en maturation. Pas de LDAP natif |
| 5-12 | Absent | Pas de moteur d'exécution = pas de monitoring, audit, approbations, etc. |

**Verdict :** Excelle sur le catalogue (1/12), mais n'est pas une plateforme d'exécution. Nécessite un moteur séparé + plugins custom + équipe dédiée.

---

### 2.5. StackStorm

**Licence :** Apache 2.0

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 1 - Catalogue DB | Absent | Pas de concept de catalogue |
| 2 - Multi-plateforme | **Fort** | 160+ packs d'intégration, 6000+ actions, règles event-driven |
| 3 - Self-service | Faible | UI développeur, pas de wizard pour non-techniques |
| 4 - RBAC + AD | **Oui** | RBAC open-sourcé depuis v3.4. LDAP disponible. SAML en WIP |
| 7 - ServiceNow | **Oui** | Pack officiel ServiceNow |
| 9 - Approbations | **Oui** | "Inquiries" — pause workflow pour approbation humaine |
| 12 - Webhooks | **Oui** | Architecture event-driven native |

**Verdict :** ~5-6/12. Fort en backend event-driven, faible comme portail utilisateur. Communauté en déclin.

---

### 2.6. Temporal.io

**Licence :** MIT (serveur)

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 2 - Multi-plateforme | **Excellent** | Orchestration durable et fault-tolerant de n'importe quel système |
| 8 - Audit | **Excellent** | Event History complet pour chaque workflow |
| 9 - Approbations | **Oui** | Signaux/queries pour patterns human-in-the-loop |

**Verdict :** ~3-4/12 out-of-the-box. Meilleur choix comme **fondation** pour construire un IDP from scratch (ce que votre Django fait déjà). Utilisé par Stripe, Netflix, HashiCorp.

---

### 2.7. Bytebase

**Licence :** Apache 2.0 (Community), propriétaire (Enterprise)

| Fonctionnalité | Couverture | Notes |
|----------------|------------|-------|
| 1 - Catalogue DB | **Fort pour le schéma** | Tracking databases, schémas, environnements. Mais limité aux changements de schéma |
| 4 - RBAC | **Oui** | Rôles par workspace/projet |
| 8 - Audit | **Oui** | Piste d'audit complète des opérations DB |
| 9 - Approbations | **Oui** | Workflows d'approbation multi-étapes |

**Oracle supporté :** Oui (Oracle, SQL Server, PostgreSQL, MySQL, MongoDB).

**Verdict :** Excellent pour la **gestion de changements de schéma** spécifiquement, mais ne couvre pas les opérations non-schéma (backups, refreshes, clones) ni l'orchestration multi-plateforme. Complémentaire.

---

### 2.8. Port (getport.io) — Commercial, pas open-source

**Licence :** Propriétaire SaaS. Free tier : 15 sièges, 10K entités, 500 runs.

Couvre ~10-11/12 fonctionnalités. **Le benchmark commercial le plus proche.** Mais SaaS-only (pas d'auto-hébergement), potentiellement incompatible avec les exigences de résidence des données bancaires.

---

### 2.9. Autres outils évalués (non retenus)

| Outil | Pourquoi non retenu |
|-------|---------------------|
| **n8n** | Workflows data/API, pas self-service opérations. Pas de catalogue. AGPLv3 |
| **Apache Airflow** | DAG scheduling développeur. Pas de portail self-service, pas d'approbations, pas de ServiceNow |
| **Kratix** | Kubernetes-natif, non pertinent pour opérations Oracle sur AAP/Azure DevOps |
| **Humanitec/Score** | Orchestration cloud-native, pas d'opérations DB |
| **OpsGenie/PagerDuty** | Gestion d'incidents, pas de self-service opérations |

---

## 3. Matrice de couverture comparative

| Fonctionnalité | Rundeck OSS | Squest+AWX | Windmill | StackStorm | Backstage | Temporal | Bytebase | Port (SaaS) |
|----------------|:-----------:|:----------:|:--------:|:----------:|:---------:|:--------:|:--------:|:-----------:|
| 1. Catalogue DB | - | ++ | - | - | +++ | - | ++ | +++ |
| 2. Multi-plateforme | + | Ansible | ++ | ++ | - | +++ | - | ++ |
| 3. Self-service wizard | ++ | +++ | ++ | - | + | - | + | +++ |
| 4. RBAC + AD | + | ++ | E | ++ | + | E | + | +++ |
| 5. WebSocket temps réel | - | - | ++ | + | - | + | - | + |
| 6. Vault | +++ | ++ | ++ | - | - | - | - | + |
| 7. ServiceNow | ++ | + | - | ++ | - | - | - | + |
| 8. Audit SOC1 | + | ++ | ++ | + | - | +++ | ++ | ++ |
| 9. Approbations | E | ++ | ++ | ++ | - | ++ | ++ | +++ |
| 10. Dashboard/export | E | - | + | - | - | - | + | ++ |
| 11. SAML SSO | E | ++ | E | - | + | E | E | +++ |
| 12. Webhooks | ++ | + | +++ | +++ | - | + | + | +++ |

*Légende : `+++` natif/fort, `++` bon, `+` partiel, `-` absent, `E` Enterprise/commercial uniquement*

---

## 4. Combinaisons recommandées

### Option A : Squest + AWX + Bytebase (la plus intégrée, le moins de dev custom)

```
┌─────────────────────────────────────────────┐
│  Squest (portail self-service + catalogue)  │
│  - Catalogue de services DB                 │
│  - Formulaires + workflows d'approbation    │
│  - Suivi cycle de vie des instances         │
├─────────────────────────────────────────────┤
│  AWX (moteur d'exécution)                   │
│  - Playbooks Ansible pour toutes opérations │
│  - LDAP/SAML, RBAC, audit                  │
│  - Vault + ServiceNow (via modules)         │
├─────────────────────────────────────────────┤
│  Bytebase (gestion changements schéma)      │
│  - Oracle/SQL Server/DB2                    │
│  - Revue DBA + approbation                  │
│  - Audit spécifique DB                      │
└─────────────────────────────────────────────┘
```

**Couvre :** 1, 3, 4, 6, 7, 8, 9, 11, 12 (partiel) → ~8/12
**Manque :** Orchestration multi-plateforme au-delà d'Ansible, WebSocket temps réel, dashboards/export
**Effort :** Moyen. Squest + AWX est un couple éprouvé.
**Licence :** GPL-3.0 (Squest) + Apache 2.0 (AWX, Bytebase). GPL-3.0 OK pour usage interne.

---

### Option B : Windmill comme moteur central (le plus flexible)

```
┌─────────────────────────────────────────────┐
│  Windmill (moteur workflow + UI builder)     │
│  - Formulaires auto-générés                 │
│  - App builder low-code pour wizards        │
│  - Étapes d'approbation natives             │
│  - Vault, webhooks, audit                   │
├─────────────────────────────────────────────┤
│  Scripts/Flows par plateforme :             │
│  - Python: AAP API → jobs Ansible           │
│  - TypeScript: GitHub Actions API           │
│  - Python: Azure DevOps API                 │
│  - Python: Terraform Cloud API              │
│  - Python: ServiceNow REST API              │
│  - Python: cx_Oracle → opérations DB        │
└─────────────────────────────────────────────┘
```

**Couvre :** 2, 3, 5, 6, 8, 9, 12 → ~7/12 (9-10 avec Enterprise pour SAML/RBAC avancé)
**Manque :** Catalogue structuré, export CSV/PDF natif, ServiceNow pré-intégré
**Effort :** Élevé. Windmill fournit les briques, mais le catalogue, les wizards, ServiceNow et les exports sont à développer.
**Licence :** AGPLv3 (OK pour self-host interne). Enterprise nécessaire pour SAML.

---

### Option C : Backstage + Rundeck Enterprise (budget commercial requis)

```
┌─────────────────────────────────────────────┐
│  Backstage (catalogue + portail UI)         │
│  - Catalogue structuré d'opérations DB      │
│  - Métadonnées, ownership, docs             │
│  - Plugin custom pour déclencher Rundeck    │
├─────────────────────────────────────────────┤
│  Rundeck Enterprise (moteur d'exécution)    │
│  - Self-service, SAML, RBAC, approbations   │
│  - Vault + ServiceNow                       │
│  - Webhooks, audit                          │
└─────────────────────────────────────────────┘
```

**Couvre :** ~10/12
**Manque :** WebSocket timeline, export avancé
**Effort :** Très élevé. Backstage nécessite une équipe dédiée + plugins custom. Rundeck Enterprise = coût de licence.
**Licence :** Apache 2.0 (Backstage) + commercial (Rundeck Enterprise).

---

## 5. Conclusion

### Aucun outil open-source ne couvre les 12 fonctionnalités

La combinaison spécifique de l'IDP Portal — RBAC multi-dimensionnel + orchestration multi-plateforme + wizards self-service + ServiceNow + Vault + audit SOC1 — est une niche qu'aucun projet open-source ne remplit seul.

### L'IDP Portal custom est architecturalement justifié

| Critère | Outils OSS combinés | IDP Portal custom |
|---------|---------------------|-------------------|
| Couverture fonctionnelle | 7-8/12 (meilleur cas OSS) | 12/12 |
| Orchestration multi-plateforme | Ansible uniquement (Squest) ou custom (Windmill) | Natif (5 adaptateurs) |
| UX pour non-techniques | Formulaires basiques | Wizard multi-étapes + timeline WebSocket |
| Coût intégration | 2-3 outils à intégrer + maintenance | Monolithe cohérent |
| Conformité SOC1 | À assembler | Natif (audit immuable) |
| SAML + RBAC multi-dim. | Dispersé entre outils | Unifié |

### Recommandation

Le développement custom Django + React est **la bonne approche** pour ce cas d'usage. Les alternatives OSS nécessiteraient :
- 2-3 outils à intégrer et maintenir
- Du développement custom significatif pour combler les lacunes
- Des compromis sur l'UX et la conformité
- Un coût total de possession potentiellement supérieur

Le seul scénario où un remplacement serait pertinent :
- **Port (getport.io)** si le SaaS est acceptable et que les contraintes de résidence des données bancaires le permettent (~11/12 fonctionnalités)
- **Rundeck Enterprise** si le budget licence est disponible et que le catalogue structuré n'est pas critique (~9-10/12)
