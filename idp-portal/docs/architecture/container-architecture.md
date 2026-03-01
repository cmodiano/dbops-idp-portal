# Architecture des conteneurs — IDP Portal

> Document généré le 2026-03-01
> Audience : équipes Architecture, DevOps, Support production

---

## 1. Vue d'ensemble — Diagramme C4 niveau Container

```mermaid
C4Container
    title IDP Portal — Architecture des conteneurs

    Person(user, "Utilisateur DBA / Ops", "Accède au portail via navigateur")
    Person(admin, "Administrateur", "Gestion des catalogues, profils, intégrations")

    System_Boundary(idp, "IDP Portal Platform") {

        Container(nginx_fe, "Frontend (Nginx + React)", "nginx:alpine / React 19 / Ant Design 6", "SPA React servie par Nginx.\nProxy inverse vers l'API backend.\nPort 80 (container) → 8080 (host)")

        Container(django, "Backend API (Django + Gunicorn)", "python:3.12-slim / Django 5.2 / DRF 3.15", "API REST v1 + WebSocket (Daphne/Channels).\n4 workers Gunicorn (dev) / 9 workers (prod).\nPort 8000")

        Container(celery_worker, "Celery Worker", "python:3.12-slim / Celery 5.x", "Exécution asynchrone des tâches.\n4 queues : aap, azure, github, terraform (+ default).\nPas de port exposé")

        Container(celery_beat, "Celery Beat", "python:3.12-slim / Celery 5.x", "Planificateur de tâches périodiques.\nEvaluate gates : 60s\nScheduled executions : 60s\nHealth check : 3600s")

        ContainerDb(redis, "Redis", "redis:7-alpine", "Broker Celery + Result backend.\nCache applicatif (feature flags, sessions).\nPort 6379")

        ContainerDb(oracle, "Oracle Database", "oracle.com/database/free:latest (23ai)", "Base de données principale.\nPDB : FREEPDB1.\nUser applicatif : IDP_APP.\nPorts 1521 (SQL*Net), 5500 (EM Express)")
    }

    System_Ext(vault, "HashiCorp Vault", "Gestion des secrets — credentials des intégrations")
    System_Ext(aap, "Ansible Automation Platform", "Exécution de playbooks (AAP / Tower)")
    System_Ext(azure, "Azure DevOps", "Pipelines CI/CD")
    System_Ext(github, "GitHub Actions", "Workflows CI/CD")
    System_Ext(terraform, "Terraform Cloud", "Provisionnement infrastructure")
    System_Ext(servicenow, "ServiceNow", "Gestion ITSM (Change Management)")
    System_Ext(splunk, "Splunk", "Centralisation des logs (HEC)")
    System_Ext(idp_saml, "Identity Provider SAML 2.0", "Authentification SSO enterprise")

    Rel(user, nginx_fe, "HTTPS / WSS", "443 (prod) / 8080 (dev)")
    Rel(admin, nginx_fe, "HTTPS", "443 (prod) / 8080 (dev)")
    Rel(nginx_fe, django, "HTTP (proxy)", "8000 — /api/v1/*, /ws/*, /static/icons/")
    Rel(django, redis, "TCP", "6379 — Cache / pub-sub feature flags")
    Rel(django, oracle, "SQL*Net", "1521 — Connexion pool Oracle")
    Rel(django, vault, "HTTPS", "Résolution des secrets d'intégration")
    Rel(django, idp_saml, "HTTPS / SAML 2.0", "Authentification SSO")
    Rel(django, servicenow, "HTTPS", "Création / suivi de tickets ITSM")
    Rel(django, splunk, "HTTPS (HEC)", "Envoi des logs structurés")
    Rel(celery_worker, redis, "TCP", "6379 — Broker / Result backend")
    Rel(celery_worker, oracle, "SQL*Net", "1521 — Lecture/écriture résultats")
    Rel(celery_worker, vault, "HTTPS", "Résolution des secrets à l'exécution")
    Rel(celery_worker, aap, "HTTPS", "Lancement de jobs Ansible (queue: aap)")
    Rel(celery_worker, azure, "HTTPS", "Déclenchement de pipelines (queue: azure)")
    Rel(celery_worker, github, "HTTPS", "Déclenchement de workflows (queue: github)")
    Rel(celery_worker, terraform, "HTTPS", "Application de plans Terraform (queue: terraform)")
    Rel(celery_beat, redis, "TCP", "6379 — Publication des tâches planifiées")
    Rel(celery_beat, oracle, "SQL*Net", "1521 — Lecture des exécutions programmées")
```

---

## 2. Diagramme des flux réseau (production)

```mermaid
flowchart TD
    subgraph INTERNET["Zone Internet / Intranet entreprise"]
        USER["Utilisateur\n(navigateur)"]
    end

    subgraph DMZ["DMZ / Reverse Proxy"]
        LB["Load Balancer\nNginx / HAProxy\nport 443 HTTPS"]
    end

    subgraph APP["Zone applicative"]
        FE["frontend\nnginx:alpine\n:80"]
        BE["backend\ngunicorn\n:8000"]
        CW["celery-worker\n(x N répliques)"]
        CB["celery-beat\n(singleton)"]
    end

    subgraph DATA["Zone données"]
        RD["redis:6379\nbroker + cache"]
        ORA["oracle:1521\nPDB FREEPDB1"]
    end

    subgraph EXTERNAL["Services externes"]
        VAULT["Vault\n:8200"]
        AAP["AAP/Tower"]
        AZ["Azure DevOps"]
        GH["GitHub Actions"]
        TF["Terraform Cloud"]
        SN["ServiceNow"]
        SP["Splunk HEC"]
        IDP_SAML["IdP SAML 2.0"]
    end

    USER -->|"HTTPS :443"| LB
    LB -->|"HTTP"| FE
    FE -->|"/api/* /ws/*\nHTTP proxy"| BE
    BE -->|"TCP :6379"| RD
    BE -->|"SQL*Net :1521"| ORA
    BE -->|"HTTPS"| VAULT
    BE -->|"SAML POST"| IDP_SAML
    BE -->|"HTTPS"| SN
    BE -->|"HTTPS HEC"| SP
    CW -->|"TCP :6379"| RD
    CW -->|"SQL*Net :1521"| ORA
    CW -->|"HTTPS"| VAULT
    CW -->|"HTTPS"| AAP
    CW -->|"HTTPS"| AZ
    CW -->|"HTTPS"| GH
    CW -->|"HTTPS"| TF
    CB -->|"TCP :6379"| RD
    CB -->|"SQL*Net :1521"| ORA
```

---

## 3. Diagramme des volumes et persistance

```mermaid
flowchart LR
    subgraph VOLUMES["Volumes Docker nommés"]
        VOL_ORA[("oracle-data\nOracle data files\n/opt/oracle/oradata")]
        VOL_BEAT[("celery-beat-data\nBeat schedule\n/var/lib/celery")]
    end

    subgraph CONTAINERS["Conteneurs"]
        ORA["oracle-db"]
        CB["celery-beat"]
        BE["backend"]
        CW["celery-worker"]
        FE["frontend"]
    end

    subgraph BIND_MOUNTS["Bind mounts (dev uniquement)"]
        MIG["./database/migrations\n(Flyway SQL)"]
        STATIC["./staticfiles/icons\n(uploads runtime)"]
    end

    VOL_ORA --> ORA
    VOL_BEAT --> CB
    MIG -.->|"dev only"| ORA
    STATIC -.->|"dev only"| BE
    STATIC -.->|"proxy /static/icons/"| FE
```

---

## 4. Diagramme des files Celery

```mermaid
flowchart LR
    BE["Backend Django\n(task producer)"]
    CB["Celery Beat\n(scheduled tasks)"]

    subgraph REDIS["Redis :6379"]
        Q_AAP["queue: aap"]
        Q_AZR["queue: azure"]
        Q_GH["queue: github"]
        Q_TF["queue: terraform"]
        Q_DEF["queue: default"]
    end

    subgraph WORKERS["Celery Workers"]
        W1["Worker 1\naap + default"]
        W2["Worker 2\nazure + default"]
        W3["Worker 3\ngithub + terraform\n+ default"]
    end

    AAP["AAP / Tower"]
    AZ["Azure DevOps"]
    GH["GitHub Actions"]
    TF["Terraform Cloud"]

    BE --> Q_AAP
    BE --> Q_AZR
    BE --> Q_GH
    BE --> Q_TF
    BE --> Q_DEF
    CB --> Q_DEF

    Q_AAP --> W1 --> AAP
    Q_AZR --> W2 --> AZ
    Q_GH --> W3 --> GH
    Q_TF --> W3 --> TF
    Q_DEF --> W1
    Q_DEF --> W2
    Q_DEF --> W3
```

---

## 5. Diagramme d'authentification SAML + JWT

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant FE as Frontend (Nginx)
    participant BE as Backend Django
    participant IDP as IdP SAML 2.0

    U->>FE: GET /login
    FE->>BE: GET /api/v1/auth/saml/login/
    BE-->>FE: Redirect → IdP (AuthnRequest)
    FE-->>U: Redirect → IdP

    U->>IDP: Authentification SSO
    IDP-->>U: SAMLResponse (POST)
    U->>BE: POST /api/v1/auth/saml/acs/ (SAMLResponse)
    BE->>BE: Vérification certificat + assertions
    BE-->>U: Set-Cookie: access_token (JWT)\n+ refresh_token (HttpOnly)

    note over BE,U: Requêtes suivantes
    U->>FE: GET /dashboard
    FE->>BE: GET /api/v1/... + Authorization: Bearer <JWT>
    BE->>BE: Vérification JWT (JWT_SECRET_KEY)
    BE-->>FE: 200 OK + données
```

---

## 6. Décisions architecturales clés

| # | Décision | Justification |
|---|----------|---------------|
| 1 | Django 5.2 + DRF | Migration depuis FastAPI (fév. 2026) — meilleure intégration ORM/Admin/RBAC |
| 2 | Oracle 23ai | Contrainte d'entreprise — compatibilité avec parc DB existant |
| 3 | Gunicorn sync workers | Stabilité pour requêtes longues (exécutions > 60s) |
| 4 | Daphne/Channels ASGI | WebSocket pour timeline d'exécution temps-réel |
| 5 | Celery + Redis | Découplage exécutions longues (AAP, Terraform) du cycle HTTP |
| 6 | Files par plateforme | Isolation des pannes inter-plateforme, QoS différenciée |
| 7 | HashiCorp Vault | Aucun secret en base (NFR7, NFR21) |
| 8 | Feature flags Redis pub/sub | Invalidation cache cohérente multi-instance |
| 9 | Flyway pour migrations | Gestion versionnée du schéma Oracle indépendante du framework |
| 10 | Nginx SPA + proxy | Pas de CORS en production, routing unifié |
