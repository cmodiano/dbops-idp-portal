# Intégration Splunk HEC

> Story 27.8 — Envoi des logs structurés vers Splunk HTTP Event Collector et recherche audit par correlation_id.

## Architecture

```
                    ┌──────────────────────┐
                    │   Django Backend     │
                    │                      │
  structlog logs ──►│  SplunkLoggingHandler│──► buffer (queue.Queue)
                    │  (logging.Handler)   │         │
                    │                      │    flush (5s / 100 events)
                    └──────────────────────┘         │
                                                     ▼
                                            ┌────────────────┐
                                            │  SplunkService  │
                                            │  (Service)  │
                                            │  send_batch()   │
                                            └────────┬───────┘
                                                     │ POST /services/collector/event
                                                     ▼
                                            ┌────────────────┐
                                            │   Splunk HEC   │
                                            │   (HTTP Event  │
                                            │   Collector)   │
                                            └────────────────┘
```

### Composants

| Composant | Fichier | Rôle |
|-----------|---------|------|
| `SplunkService` | `services/splunk_service.py` | Envoi HTTP vers Splunk HEC (send_event, send_batch) |
| `SplunkLoggingHandler` | `core/splunk_logging_handler.py` | Buffer + flush automatique vers SplunkService |
| Configuration structlog | `core/logging.py` | Intégration handler dans la chaîne structlog |

## Configuration

### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SPLUNK_HEC_URL` | URL endpoint Splunk HEC | (vide = désactivé) |
| `SPLUNK_HEC_TOKEN` | Token d'authentification HEC | (vide) |
| `SPLUNK_INDEX` | Index Splunk cible | `prod-idp` |
| `SPLUNK_SOURCETYPE` | Sourcetype Splunk | `idp:execution` |
| `SPLUNK_FLUSH_INTERVAL` | Intervalle flush en secondes | `5` |
| `SPLUNK_BATCH_SIZE` | Taille batch avant auto-flush | `100` |
| `SPLUNK_MAX_BUFFER_SIZE` | Taille max buffer (FIFO drop) | `1000` |

### Django Settings (alternative)

```python
SPLUNK_CONFIG = {
    "HEC_URL": "https://splunk.example.com:8088",
    "HEC_TOKEN": "your-hec-token",
}
```

### Credential Ref Vault

Le token Splunk HEC peut être résolu via VaultService (Story 27.6) :

```
credential_ref: vault:secret/data/splunk/prod#token
```

## Event Schema JSON standardisé

```json
{
  "timestamp": "2026-02-14T10:30:45.123456Z",
  "event": "execution_started",
  "level": "INFO",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "john.doe@example.com",
  "execution_id": 42,
  "action_id": 10,
  "environment": "production",
  "platform": "aap",
  "details": {
    "job_template_id": "123",
    "extra_vars": {"key": "value"}
  },
  "source": "idp-portal",
  "sourcetype": "idp:execution",
  "index": "prod-idp"
}
```

Les champs `correlation_id`, `user_id`, `execution_id` et `platform` sont placés dans le champ `fields` du payload HEC pour indexation optimisée Splunk.

## Exemples d'événements

### 1. execution_started (Démarrage exécution)

```json
{
  "sourcetype": "idp:execution",
  "index": "prod-idp",
  "event": {
    "timestamp": "2026-02-14T10:30:45.123456Z",
    "event": "execution_started",
    "level": "INFO",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42,
    "action_id": 10,
    "environment": "production",
    "platform": "aap",
    "details": {
      "action_name": "Deploy Application",
      "job_template_id": "123",
      "extra_vars": {"app_version": "1.2.3"}
    }
  },
  "fields": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42
  }
}
```

### 2. step_completed (Fin step exécution)

```json
{
  "sourcetype": "idp:execution",
  "index": "prod-idp",
  "event": {
    "timestamp": "2026-02-14T10:32:18.987654Z",
    "event": "step_completed",
    "level": "INFO",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "execution_id": 42,
    "details": {
      "step_id": 1,
      "step_name": "Run Ansible Playbook",
      "status": "COMPLETED",
      "duration_seconds": 93.5
    }
  },
  "fields": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "execution_id": 42
  }
}
```

### 3. adapter_call (Appel adapter externe)

```json
{
  "sourcetype": "idp:adapter",
  "index": "prod-idp",
  "event": {
    "timestamp": "2026-02-14T10:31:02.456789Z",
    "event": "adapter_call",
    "level": "INFO",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "platform": "aap",
    "details": {
      "method": "POST",
      "url": "https://aap.example.com/api/v2/job_templates/123/launch/",
      "status_code": 201,
      "response_time_ms": 342
    }
  },
  "fields": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "platform": "aap"
  }
}
```

## Exemples Splunk Search Queries

### Recherche par correlation_id (tracer une exécution complète)

```spl
index="prod-idp" correlation_id="550e8400-e29b-41d4-a716-446655440000"
| sort timestamp
| table timestamp, event, level, user_id, execution_id, platform, details
```

### Recherche par user_id (actions d'un utilisateur sur 24h)

```spl
index="prod-idp" user_id="john.doe@example.com" earliest=-24h
| stats count by event
| sort -count
```

### Recherche par execution_id (logs complets d'une exécution)

```spl
index="prod-idp" execution_id=42
| sort timestamp
| table timestamp, event, level, details.status, details.output
```

### Erreurs par période (monitoring alertes)

```spl
index="prod-idp" level=ERROR earliest=-7d
| timechart span=1h count by event
```

## Catalogue Intégration

Le type `splunk` est enregistré dans le catalogue `IntegrationTypeCatalogue` (Story 27.7) avec 2 actions :

| Action | Label | Paramètres obligatoires |
|--------|-------|------------------------|
| `send_event` | Envoyer un événement | `event` (object) |
| `send_batch` | Envoyer un batch | `events` (array) |

Voir [integration-type-catalogue.md](integration-type-catalogue.md) pour le tableau complet.
# Gestion d'indisponibilité Splunk HEC

> Story 27.8 — Comportement en cas d'indisponibilité Splunk et impact sur le portail IDP.

## Principe

Le SplunkLoggingHandler est conçu pour ne **jamais** bloquer l'application. Si Splunk est indisponible, les logs d'audit en base de données (AUDIT_LOG, EXECUTION_STEPS) sont préservés. Seuls les événements envoyés vers Splunk HEC sont perdus temporairement.

## Comportement en cas d'erreur

### SplunkAdapter (retry)

| Étape | Comportement |
|-------|-------------|
| 1er appel | POST vers Splunk HEC |
| Erreur 500/503 | Retry après 5 secondes |
| 2e tentative | POST vers Splunk HEC |
| Encore en erreur | `ServiceUnavailableError` remontée au handler |

Les erreurs 4xx (token invalide, payload incorrect) ne sont **pas** retryées.

### SplunkLoggingHandler (drop events)

| Situation | Comportement |
|-----------|-------------|
| `send_batch()` échoue | Log warning `splunk_hec_unavailable` localement |
| Événements du batch | **Supprimés** (drop) pour éviter accumulation mémoire |
| Buffer plein (>1000 events) | Événements les plus anciens supprimés (FIFO) |
| `SPLUNK_HEC_URL` non configuré | Handler désactivé dès l'initialisation |

### Impact sur le portail

| Composant | Impact si Splunk down |
|-----------|----------------------|
| Exécutions | Aucun — les exécutions continuent normalement |
| Logs audit en BDD | Aucun — `AuditLog` et `ExecutionSteps` sont écrits indépendamment |
| API Audit `/audit/executions` | Aucun — les données viennent de la BDD |
| Recherche correlation_id | Fonctionne — filtre sur `AuditLog.correlation_id` en BDD |
| Logs dans Splunk | **Perdus** pendant l'indisponibilité |

## Monitoring

### Logs de diagnostic

Le handler émet un warning structlog local quand Splunk est indisponible :

```
splunk_hec_unavailable: <error details> — dropped <N> events
```

Ce log apparaît dans les fichiers logs locaux du serveur Django.

### Métriques à surveiller

| Métrique | Source | Alerte recommandée |
|----------|--------|-------------------|
| `splunk_hec_unavailable` count | Logs locaux | > 5 par minute |
| Buffer queue size | Monitoring applicatif | > 800 events |
| `splunk_hec_not_configured` | Logs démarrage | Toute occurrence en prod |

## Reprise après indisponibilité

Les événements perdus pendant l'indisponibilité Splunk ne sont **pas** re-envoyés automatiquement. Les données d'audit restent disponibles dans la base de données Oracle via l'API Audit du portail.

Pour combler le gap dans Splunk après une coupure, il est possible de :
1. Identifier la période d'indisponibilité via les logs `splunk_hec_unavailable`
2. Exporter les données d'audit de la BDD pour la période concernée via `GET /api/v1/audit/export/?fmt=csv&from=...&to=...`
3. Ré-indexer manuellement dans Splunk si nécessaire
