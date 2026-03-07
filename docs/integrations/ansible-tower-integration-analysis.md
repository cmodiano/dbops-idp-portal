# Analyse d'intégration Ansible Tower / AWX — API REST & WebSocket

> Story 27.2 — Date : 2026-02-14

## 1. Vue d'ensemble

Ce document synthétise l'analyse de l'API Ansible Tower / AWX API v2 pour l'intégration
avec le portail IDP. Il couvre les endpoints REST pour les workflows, job templates, jobs,
logs et statuts, ainsi que les mécanismes temps réel (WebSocket / polling).

**Plateformes couvertes :**
- **Ansible Tower** : Version commerciale Red Hat (dernière majeure : Tower 3.8.6)
- **AWX** : Projet open source upstream (version actuelle : 24.x+)
- **Relation avec AAP** : AWX → Ansible Tower (commercial) → AAP Controller (successeur)

**API ciblée :** API v2 (`/api/v2/`) — identique pour Tower et AWX

---

## 2. Différences AAP vs Tower / AWX

### 2.1 Endpoints API

| Plateforme | Base API Path | Notes |
|------------|---------------|-------|
| Tower / AWX | `/api/v2/` | Stable, pas de changement prévu |
| AAP 2.4 et antérieurs | `/api/v2/` | Identique Tower/AWX |
| AAP 2.5+ (2026) | `/api/controller/v2/` | **Breaking change** — endpoints renommés |

### 2.2 Implications pour l'adapter

- Le `TowerAdapter` utilise exclusivement `/api/v2/` (Tower/AWX ne changeront pas)
- L'`AAPAdapter` existant utilise aussi `/api/v2/` (compatible AAP <2.5)
- Pour AAP 2.5+, un adapter séparé ou une configuration `api_path_prefix` serait nécessaire

### 2.3 Compatibilité API

L'API REST Tower/AWX v2 est **strictement identique** à l'API AAP v2 :
- Mêmes endpoints (job_templates, workflow_job_templates, jobs, workflow_jobs)
- Mêmes formats de requêtes et réponses
- Mêmes statuts de jobs et mécanismes d'authentification
- Mêmes formats de logs (txt, ansi, html, json)

---

## 3. Endpoints REST — Lancement

### 3.1 Lancer un Job Template

- **Endpoint :** `POST /api/v2/job_templates/{id}/launch/`
- **Paramètres acceptés :**
  - `extra_vars` (string JSON) — Variables supplémentaires
  - `limit` (string) — Hôtes/groupes cibles
  - `inventory`, `credential`, `job_tags`, `skip_tags`, `job_type`, `verbosity`
- **Réponse :** JSON avec `id`, `status`, `url` du job créé
- **Note :** "Prompt on Launch" doit être activé sur le template pour accepter `extra_vars` via API

### 3.2 Lancer un Workflow Job Template

- **Endpoint :** `POST /api/v2/workflow_job_templates/{id}/launch/`
- **Paramètres :** `extra_vars` (string JSON) propagées à tous les jobs du workflow
- **Réponse :** JSON avec `id`, `status`, `url` du workflow job créé

---

## 4. Endpoints REST — Statut des Jobs

### 4.1 Statut Job Template

- **Endpoint :** `GET /api/v2/jobs/{id}/`
- **Champs clés réponse :** `id`, `type`, `status`, `started`, `finished`, `failed`, `elapsed`

### 4.2 Statut Workflow Job

- **Endpoint :** `GET /api/v2/workflow_jobs/{id}/`
- **Champs clés :** identiques + `workflow_nodes`

### 4.3 Valeurs de statut Tower / AWX

| Statut Tower/AWX | Description                              | Mapping IDP Portal |
|------------------|------------------------------------------|--------------------|
| `pending`        | Job créé, pas encore en file             | `SUBMITTED`        |
| `waiting`        | En file d'attente                        | `SUBMITTED`        |
| `running`        | En cours d'exécution                     | `RUNNING`          |
| `successful`     | Terminé avec succès                      | `COMPLETED`        |
| `failed`         | Échec durant l'exécution                 | `FAILED`           |
| `error`          | Erreur système (pas erreur playbook)     | `FAILED`           |
| `canceled`       | Annulé par utilisateur ou système        | `CANCELLED`        |

**Note :** Mapping identique AAP (Story 27.1).

---

## 5. Endpoints REST — Logs (stdout)

### 5.1 Logs Job Template

- **Endpoint :** `GET /api/v2/jobs/{id}/stdout/`
- **Formats supportés** (paramètre `?format=`) : `txt`, `ansi`, `html`, `json`
- **Pagination :** `?start_line=X&end_line=Y`

### 5.2 Logs Workflow Job

- **Endpoint :** `GET /api/v2/workflow_jobs/{id}/stdout/`
- **Mêmes formats et pagination que job stdout**

---

## 6. Authentification

### 6.1 Méthodes supportées

| Méthode | Header | Notes |
|---------|--------|-------|
| Basic Auth | `Authorization: Basic <base64(user:pass)>` | Stateless, déconseillé production |
| Bearer Token | `Authorization: Bearer <token>` | Créé via `POST /api/v2/tokens/` |
| OAuth2 | Standard OAuth2 | Supporté Tower/AWX |
| PAT | `Authorization: Bearer <pat>` | Personal Access Token |

### 6.2 Intégration portail IDP

Réutilisation de `build_auth_headers()` (adapters/utils.py, Story 27.1) — compatible Tower sans modification.
Credentials récupérés depuis HashiCorp Vault via `credential_ref` de l'intégration.

---

## 7. WebSocket — Événements Temps Réel

### 7.1 Endpoint WebSocket Tower/AWX

- **URL :** `wss://<host>/websocket/`
- **Ports :** 80/443 (HTTP/HTTPS)
- **Auth :** Token inclus dans URL ou header
- **Architecture :** django-channels + Redis (wsrelay daemon)

### 7.2 Protocole de souscription

```json
{
  "groups": {
    "jobs": ["status_changed", "summary"],
    "job_events": [<job_id>],
    "workflow_events": [<workflow_job_id>]
  }
}
```

### 7.3 Stratégie d'intégration retenue

**Polling périodique 5s** (identique AAP Story 27.1) :
- Simple, fonctionne quelle que soit la config réseau Tower/AWX
- Latence max 5s acceptable pour le monitoring
- Réutilisation du polling Celery `poll_aap_job_status` / `poll_tower_job_status`

---

## 8. Points d'intégration

| Composant    | Endpoint/Mécanisme                              | Usage portail                   |
|--------------|------------------------------------------------|---------------------------------|
| Lancement    | `POST .../job_templates/{id}/launch/`          | `TowerAdapter.trigger()`        |
| Lancement WF | `POST .../workflow_job_templates/{id}/launch/` | `TowerAdapter.trigger()`        |
| Statut       | `GET .../jobs/{id}/` ou `.../workflow_jobs/{id}/` | `TowerAdapter.get_status()`  |
| Logs         | `GET .../jobs/{id}/stdout/?format=txt`         | `TowerAdapter.get_job_logs()`   |
| Logs WF      | `GET .../workflow_jobs/{id}/stdout/?format=txt`| `TowerAdapter.get_job_logs()`   |
| Auth         | Basic Auth / Bearer Token                       | `build_auth_headers()` via Vault|
| WebSocket    | `wss://<host>/websocket/`                      | Polling 5s (Phase 1)            |
| Annulation   | `POST /api/v2/jobs/{id}/cancel/`               | `TowerAdapter.cancel_execution()` |

---

## 9. Diagramme de séquence — Monitoring temps réel Tower

```
┌──────────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐   ┌──────────┐
│ Frontend │   │ Django API   │   │ Celery Worker  │   │ TowerAdapter │   │Tower API │
│ (React)  │   │ (DRF)        │   │ (poll task)    │   │              │   │ v2       │
└────┬─────┘   └──────┬───────┘   └───────┬────────┘   └──────┬───────┘   └────┬─────┘
     │                │                    │                   │               │
     │ POST /executions                    │                   │               │
     │───────────────>│                    │                   │               │
     │                │ trigger()          │                   │               │
     │                │───────────────────────────────────────>│               │
     │                │                    │                   │ POST ../launch│
     │                │                    │                   │──────────────>│
     │                │                    │                   │   {id,status} │
     │                │                    │                   │<──────────────│
     │   {execution_id, platform_job_id}   │                   │               │
     │<───────────────│                    │                   │               │
     │                │                    │                   │               │
     │ WS /ws/executions/{id}              │                   │               │
     │───────────────>│                    │                   │               │
     │                │                    │                   │               │
     │                │  poll_tower_job_status (toutes les 5s) │               │
     │                │                    │                   │               │
     │                │              ┌─────│ get_status()      │               │
     │                │              │     │──────────────────>│               │
     │                │              │     │                   │ GET ../jobs/  │
     │                │              │     │                   │──────────────>│
     │                │              │     │                   │   {status}    │
     │                │              │     │                   │<──────────────│
     │                │              │     │ get_job_logs()    │               │
     │                │              │     │──────────────────>│               │
     │                │              │     │                   │GET ../stdout/ │
     │                │              │     │                   │──────────────>│
     │                │              │     │                   │   {content}   │
     │                │              │     │                   │<──────────────│
     │                │              └─────│                   │               │
     │                │                    │                   │               │
     │   {status_update}  channel_layer.group_send()           │               │
     │<────────────────────────────────────│                   │               │
     │   {log_update}                      │                   │               │
     │<────────────────────────────────────│                   │               │
     │                                     │                   │               │
     │ (répété toutes les 5s jusqu'à terminaison)              │               │
     │                                     │                   │               │
     │   {execution_complete}              │                   │               │
     │<────────────────────────────────────│                   │               │
```

---

## Références

- [Ansible Tower API Reference Guide](https://docs.ansible.com/ansible-tower/latest/html/towerapi/api_ref.html)
- [AWX API Reference](https://docs.ansible.com/projects/awx/en/latest/rest_api/api_ref.html)
- [AWX GitHub](https://github.com/ansible/awx) — Projet open source upstream
- [Tower Workflow Templates Guide](https://docs.ansible.com/ansible-tower/latest/html/userguide/workflow_templates.html)
- [Tower WebSocket Troubleshooting](https://docs.ansible.com/ansible-tower/latest/html/administration/troubleshooting.html)
- [AAP 2.5 Breaking Change](https://knowledge.broadcom.com/external/article/394498/ansible-automation-platformansible-tower.html)
- [AAP Integration Analysis (Story 27.1)](./aap-integration-analysis.md)
