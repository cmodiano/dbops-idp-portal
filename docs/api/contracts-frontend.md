# Contrats API – Frontend (client)

**Date :** 2026-03-16

---

## Vue d'ensemble

- **Base URL :** `/api/v1` (relative, même origine)
- **Client central :** `src/services/api_client.ts` — `handleAuthenticatedFetch`, `apiFetch`, `apiFetchRaw`
- **Auth :** Bearer JWT injecté via `setAuthAccessors(getToken, refreshFn)` ; retry 401 après refresh automatique
- **Retry :** 429 (rate limit) avec full-jitter backoff exponentiel (`MAX_429_RETRIES=3`) ; 503 `DB_UNAVAILABLE` retenté (`MAX_503_RETRIES=2`)
- **Header traçabilité :** `X-Correlation-ID` (UUID généré par requête) pour corrélation backend/logs
- **WebSocket :** `/ws/executions/{id}` — auth par message (pas dans l'URL)

---

## Headers HTTP utilisés

| Header | Direction | Description |
|--------|-----------|-------------|
| `Authorization: Bearer <token>` | Client → Serveur | Token JWT d'accès (injecté par `api_client.ts`) |
| `X-Correlation-ID: <uuid>` | Client → Serveur | ID unique par requête pour traçabilité (généré par `api_client.ts`) |
| `Content-Type: application/json` | Client → Serveur | Envoyé par `apiFetch` et `apiFetchRaw` |
| `Retry-After` | Serveur → Client | Délai avant retry (utilisé par `api_client.ts` pour 429 et 503) |

---

## Services consommateurs (appels API)

| Service | Fichier | Rôle |
|---------|---------|------|
| `api_client.ts` | `api_client.ts` | Fetch authentifié, retries 401/429/503, corrélation |
| `auth_service.ts` | `auth_service.ts` | Login SAML, refresh token, logout, profil utilisateur |
| `catalog_service.ts` | `catalog_service.ts` | Catalogue actions, favoris utilisateur |
| `execution_service.ts` | `execution_service.ts` | Façade : réexporte core + dashboard + inventory |
| `execution_core.ts` | `execution_core.ts` | CRUD exécutions, approve, reject, cancel, remediation |
| `execution_dashboard.ts` | `execution_dashboard.ts` | Stats et timeseries d'exécutions |
| `execution_inventory.ts` | `execution_inventory.ts` | Inventaire (databases, servers, instances) pour formulaires |
| `scheduled_execution_service.ts` | `scheduled_execution_service.ts` | Exécutions planifiées, cron |
| `profiles_service.ts` | `profiles_service.ts` | Profils utilisateurs, export/import YAML |
| `integrations_service.ts` | `integrations_service.ts` | Intégrations (AAP, ServiceNow, Azure DevOps, etc.) |
| `admin_service.ts` | `admin_service.ts` | Actions admin, tags, règles de remédiation |
| `audit_service.ts` | `audit_service.ts` | Logs d'audit, export PDF/CSV |
| `dashboard_service.ts` | `dashboard_service.ts` | Statistiques et analytics du dashboard |
| `reference_service.ts` | `reference_service.ts` | Engines actifs (REF_ENGINES), environnements disponibles |
| `categories_service.ts` | `categories_service.ts` | Catégories d'actions (REF_CATEGORIES), CRUD admin |
| `business_rules_service.ts` | `business_rules_service.ts` | Politiques de règles métier (CRUD admin) |
| `capabilities_service.ts` | `capabilities_service.ts` | Capacités plateformes + types de steps workflow |
| `engines_service.ts` | `engines_service.ts` | Moteurs de BD pour admin (Oracle, SQL Server, DB2) |
| `output_schema_service.ts` | `output_schema_service.ts` | Schémas de sortie, variables disponibles workflow |
| `api_keys_service.ts` | `api_keys_service.ts` | Clés API personnelles (list, create, revoke) |
| `help_service.ts` | `help_service.ts` | Aide contextuelle par topic (cache sessionStorage 10 min) |
| `feature_flag_service.ts` | `feature_flag_service.ts` | Feature flags (status utilisateur + admin) |

Les chemins appelés reflètent les routes du backend (`/api/v1/...`). La présence du trailing slash dépend du service : la majorité des endpoints admin l'utilisent (ex: `/admin/categories/{id}/`), mais certains services ne l'incluent pas (ex: `feature_flag_service.ts` appelle `/feature-flags/status` sans trailing slash).

---

## WebSocket — Exécutions temps réel

### Endpoint

```
ws://<host>/ws/executions/{id}     (HTTP)
wss://<host>/ws/executions/{id}    (HTTPS — auto-détecté par useWebSocket)
```

### Séquence d'authentification

Le token JWT n'est **jamais** passé dans l'URL. Il est envoyé dans le premier message après connexion.

```
1. client → WebSocket connect → /ws/executions/{id}
2. client → send: { "type": "auth", "token": "<JWT>" }
3. server → send: { "type": "auth_success", "user_id": "..." }
4. client → re-sync: GET /api/v1/executions/{id}
                   + GET /api/v1/executions/{id}/steps
5. server → messages métier...
```

### Codes de fermeture

| Code | Signification | Reconnexion automatique |
|------|---------------|------------------------|
| `4001` | Échec d'authentification | ❌ Non |
| `4003` | Accès non autorisé | ❌ Non |
| Autres codes | Fermeture réseau / normale | ✅ Oui (après 2 secondes) |

### Événements serveur → client

| `type` | Payload | Action côté client |
|--------|---------|-------------------|
| `auth_success` | `{ user_id: string }` | `setIsAuthenticated(true)`, re-sync REST |
| `step_update` | `{ id, step_order, step_name, status, step_type, started_at, completed_at, config_step_id }` | Upsert dans `steps[]` par `step_order` |
| `status_update` | `{ data: { status: ExecutionStatus } }` | Mise à jour statut exécution |
| `execution_complete` | — | `status = "COMPLETED"`, fermeture WS |
| `execution_failed` | `{ error_message: string }` | `status = "FAILED"`, fermeture WS |

> **`config_step_id`** : Identifiant du step dans la configuration workflow (pas l'ID de la table `EXECUTION_STEPS`). Utilisé par le graphe React Flow pour colorier le bon nœud même dans les workflows avec branches.

---

## Retry et résilience

### Rate limiting (HTTP 429)

```
Tentative 1 → 429
  → délai = Retry-After (si présent) ou random(0, 2^0 * 1000ms) — full jitter
  → notification UI "Trop de requêtes"
Tentative 2 → 429
  → délai = random(0, 2^1 * 1000ms)
Tentative 3 → 429
  → délai = random(0, 2^2 * 1000ms)
Tentative 4 → 429 → ApiError(429) levée
```

### DB indisponible (HTTP 503 DB_UNAVAILABLE)

```
503 avec body { error: { code: "DB_UNAVAILABLE" } }
  → notification UI "Service temporairement indisponible"
  → retry 1 (délai = Retry-After ou 5000ms par défaut)
  → retry 2
  → notification erreur "Base de données indisponible" + ApiError levée
```

Seuls les 503 avec code `DB_UNAVAILABLE` sont retentés. Les autres 503 (ex: page de maintenance) ne sont pas retentés.

---

*Mis à jour le 2026-03-16 — Story 87-2*
