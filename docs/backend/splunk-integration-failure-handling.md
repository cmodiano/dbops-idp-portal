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
