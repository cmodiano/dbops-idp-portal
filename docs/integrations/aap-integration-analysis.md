# Analyse d'intégration AAP (Ansible Automation Platform) — API REST & WebSocket

> Story 27.1 — Date : 2026-02-14

## 1. Vue d'ensemble

Ce document synthétise l'analyse de l'API Ansible Automation Platform (AAP) Controller v2
pour l'intégration avec le portail IDP. Il couvre les endpoints REST pour les workflows,
job templates, jobs, logs et statuts, ainsi que les mécanismes temps réel (WebSocket).

**Version AAP ciblée :** AAP 2.4+ / Ansible Controller API v2

---

## 2. Endpoints REST — Lancement

### 2.1 Lancer un Job Template

- **Endpoint :** `POST /api/v2/job_templates/{id}/launch/`
- **Paramètres acceptés :**
  - `extra_vars` (string JSON) — Variables supplémentaires : `{"extra_vars": "{\"foo\": \"bar\"}"}`
  - `limit` (string) — Hôtes/groupes cibles (séparés par virgule)
  - `inventory` (integer) — ID inventaire
  - `credential` (integer) — ID credential
  - `job_tags` / `skip_tags` (string)
  - `job_type` — `run` ou `check`
  - `verbosity` (0-4)
- **Réponse :** JSON avec `id`, `status`, `url` du job créé
- **Note :** "Prompt on Launch" doit être activé sur le template pour accepter `extra_vars` via API

### 2.2 Lancer un Workflow Job Template

- **Endpoint :** `POST /api/v2/workflow_job_templates/{id}/launch/`
- **Paramètres :** `extra_vars` (string JSON) propagées à tous les jobs du workflow
- **Réponse :** JSON avec `id`, `status`, `url` du workflow job créé

---

## 3. Endpoints REST — Statut des Jobs

### 3.1 Statut Job Template

- **Endpoint :** `GET /api/v2/jobs/{id}/`
- **Champs clés réponse :** `id`, `type`, `status`, `started`, `finished`, `failed`, `elapsed`

### 3.2 Statut Workflow Job

- **Endpoint :** `GET /api/v2/workflow_jobs/{id}/`
- **Champs clés :** identiques + `workflow_nodes` (liste des nœuds du workflow)

### 3.3 Valeurs de statut AAP

| Statut AAP    | Description                              | Mapping IDP Portal      |
|---------------|------------------------------------------|-------------------------|
| `pending`     | Job créé, pas encore en file             | `SUBMITTED`             |
| `waiting`     | En file d'attente                        | `SUBMITTED`             |
| `running`     | En cours d'exécution                     | `RUNNING`               |
| `successful`  | Terminé avec succès                      | `COMPLETED`             |
| `failed`      | Échec durant l'exécution                 | `FAILED`                |
| `error`       | Erreur système (pas une erreur playbook) | `FAILED`                |
| `canceled`    | Annulé par utilisateur ou système        | `CANCELLED`             |

---

## 4. Endpoints REST — Logs (stdout)

### 4.1 Logs Job Template

- **Endpoint :** `GET /api/v2/jobs/{id}/stdout/`
- **Formats supportés** (paramètre `?format=`) :
  - `txt` — Texte brut
  - `ansi` — ANSI avec codes couleur
  - `html` — HTML formaté
  - `json` — JSON wrappé
  - `txt_download` / `ansi_download` — Téléchargement (fichiers > 1 MB)
- **Pagination :** `?start_line=X&end_line=Y` pour récupération par range
- **Réponse format=json :**
  ```json
  {
    "range": {"start": 0, "end": 1024, "absolute_end": 5000},
    "content": "...",
    "content_type": "text/plain"
  }
  ```

### 4.2 Logs Workflow Job

- **Endpoint :** `GET /api/v2/workflow_jobs/{id}/stdout/`
- **Mêmes formats et pagination que job stdout**

### 4.3 Job Events (détaillés)

- **Endpoint :** `GET /api/v2/jobs/{id}/job_events/`
- **Pagination :** `?page=N&page_size=M` (max 200/page)
- **Réponse :** Collection paginée d'événements granulaires (task start, task ok, task failed, etc.)
- **Filtrage :** `?event__contains=task` etc.

---

## 5. Authentification

### 5.1 Basic Auth

- **Header :** `Authorization: Basic <base64(username:password)>`
- Stateless, envoyé à chaque requête
- Supporté mais déconseillé pour un usage programmatique

### 5.2 OAuth2 Bearer Token (recommandé)

- **Header :** `Authorization: Bearer <token>`
- Token créé via `POST /api/v2/tokens/`
- Expiration configurable, révocable, scopable
- Personal Access Token (PAT) supporté

### 5.3 Intégration portail IDP

L'adapter AAP existant utilise `_get_auth_headers()` qui récupère les credentials
depuis HashiCorp Vault (Story 4.2bis). Les deux méthodes (Basic / Bearer) sont supportées
selon la configuration de l'intégration (`auth_flow` : TOKEN, BASIC, BASIC_THEN_TOKEN, PAT).

---

## 6. WebSocket — Événements Temps Réel

### 6.1 Endpoint WebSocket AAP

- **URL :** `wss://<controller-host>/websocket/`
- **Auth :** Token inclus dans l'URL ou header de connexion
- Architecture : django-channels + Redis (wsrelay daemon)

### 6.2 Protocole de souscription

Après connexion, envoyer un message JSON de souscription :

```json
{
  "groups": {
    "jobs": ["status_changed", "summary"],
    "job_events": [<job_id>],
    "workflow_events": [<workflow_job_id>]
  }
}
```

**Note :** Chaque nouvelle souscription remplace les précédentes.

### 6.3 Types d'événements

- `status_changed` — Changement de statut du job (running → successful, etc.)
- `summary` — Résumé fin d'exécution
- `job_events` — Événements granulaires par job (task start, ok, failed)
- `workflow_events` — Événements workflow (nœud démarré, terminé)

### 6.4 Limites

- Rate max : ~200 événements/seconde par client
- Configurable via `MAX_WEBSOCKET_EVENT_RATE`
- Désactivable : `UI_LIVE_UPDATES_ENABLED = False`

### 6.5 Stratégie d'intégration retenue

**Approche hybride :**
1. **Polling périodique (MVP)** — Interroger `GET /api/v2/jobs/{id}/` toutes les 5s
   - Avantage : Simple, fonctionne quelle que soit la config AAP
   - Inconvénient : Latence de 5s max
2. **WebSocket AAP (futur)** — Se connecter au websocket AAP natif pour events temps réel
   - Dépend de la configuration réseau et version AAP déployée
   - Meilleure réactivité mais plus complexe à gérer (reconnexion, auth)

---

## 7. Points d'intégration identifiés

| Composant        | Endpoint/Mécanisme                                 | Usage portail                    |
|------------------|---------------------------------------------------|----------------------------------|
| Lancement        | `POST .../job_templates/{id}/launch/`             | `AAPAdapter.trigger()`           |
| Lancement WF     | `POST .../workflow_job_templates/{id}/launch/`    | `AAPAdapter.trigger()`           |
| Statut           | `GET .../jobs/{id}/` ou `.../workflow_jobs/{id}/` | `AAPAdapter.get_status()`        |
| Logs             | `GET .../jobs/{id}/stdout/?format=txt`            | `AAPAdapter.get_job_logs()`      |
| Logs WF          | `GET .../workflow_jobs/{id}/stdout/?format=txt`   | `AAPAdapter.get_job_logs()`      |
| Events           | `GET .../jobs/{id}/job_events/`                   | Détail granulaire (optionnel)    |
| Auth             | Basic Auth / Bearer Token                          | `_get_auth_headers()` via Vault  |
| WebSocket        | `wss://<host>/websocket/`                         | Monitoring temps réel (Phase 2)  |
| Annulation       | `POST /api/v2/jobs/{id}/cancel/`                  | `AAPAdapter.cancel_execution()`  |

---

## 8. Format unifié des logs (retour adapter)

```python
{
    "content": "...",        # Texte brut des logs Ansible
    "format": "text/plain",  # Format du contenu
    "timestamp": "2026-02-14T10:30:00Z",  # Date de récupération
    "complete": True,         # True si tous les logs sont récupérés
    "job_status": "running",  # Statut AAP du job au moment de la récupération
}
```

---

## 9. Diagramme de séquence — Monitoring temps réel

```
┌──────────┐   ┌──────────────┐   ┌────────────────┐   ┌─────────────┐   ┌──────────┐
│ Frontend │   │ Django API   │   │ Celery Worker  │   │ AAPAdapter  │   │ AAP API  │
│ (React)  │   │ (DRF)        │   │ (poll task)    │   │             │   │ v2       │
└────┬─────┘   └──────┬───────┘   └───────┬────────┘   └──────┬──────┘   └────┬─────┘
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
     │  {type: auth}  │                    │                   │               │
     │<──auth_success─│                    │                   │               │
     │                │                    │                   │               │
     │                │  poll_aap_job_status (toutes les 5s)   │               │
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

### 9.1 Flow complet

1. **Soumission** : Frontend `POST /api/v1/executions` → backend crée l'exécution,
   appelle `AAPAdapter.trigger()` → AAP lance le job → retourne `platform_job_id`
2. **Connexion WebSocket** : Frontend ouvre `/ws/executions/{execution_id}`,
   s'authentifie via JWT message-based (Story 22.13)
3. **Monitoring polling** : Celery task `poll_aap_job_status` auto-schedulé toutes les 5s :
   - `AAPAdapter.get_status()` → statut AAP courant
   - `AAPAdapter.get_job_logs()` → logs stdout
   - Broadcast `status_update` + `log_update` via Django Channels group_send
   - Met à jour `EXECUTIONS.STATUS` et `EXECUTION_STEPS.OUTPUT` en DB
4. **Terminaison** : Statut terminal AAP (successful/failed/error/canceled) →
   broadcast `execution_complete` ou `execution_failed`, arrêt du polling

---

## Références

- [AAP 2.4 — API Overview](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.4/html-single/automation_controller_api_overview/)
- [AAP 2.4 — Token-Based Authentication](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.4/html/automation_controller_administration_guide/assembly-controller-token-based-authentication)
- [AWX WebSockets Documentation](https://github.com/ansible/awx/blob/devel/docs/websockets.md)
- [AAP 2.4 — Job Templates](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.4/html/automation_controller_user_guide/controller-job-templates)
