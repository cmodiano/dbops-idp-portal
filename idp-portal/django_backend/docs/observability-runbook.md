# Runbook Observabilité - Django Backend

Story M.8 - Procédures de monitoring et dépannage

## Requêtes Splunk

### Recherche par Correlation ID

Tracer toutes les opérations d'une requête :

```spl
index=idp-portal correlation_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
| sort _time
| table _time, event, level, path, status_code, duration_ms, user_id
```

### Erreurs récentes (dernière heure)

```spl
index=idp-portal level="error"
| where _time > relative_time(now(), "-1h")
| stats count by event, path
| sort -count
```

### Requêtes lentes (> 1 seconde)

```spl
index=idp-portal event="request_completed" duration_ms > 1000
| stats count, avg(duration_ms) as avg_duration, max(duration_ms) as max_duration by path
| sort -avg_duration
```

### Taux d'erreur par endpoint

```spl
index=idp-portal event="request_completed"
| eval is_error=if(status_code>=500, 1, 0)
| stats sum(is_error) as errors, count as total by path
| eval error_rate=round(errors/total*100, 2)
| where errors > 0
| sort -error_rate
```

### Activité par utilisateur

```spl
index=idp-portal event="request_completed" user_id=*
| stats count, avg(duration_ms) as avg_duration by user_id
| sort -count
```

### Échecs de health check

```spl
index=idp-portal event="health_check_failed"
| stats count by service, error
| sort -count
```

### Tentatives d'accès non autorisé

```spl
index=idp-portal event="auth_unauthorized_access"
| stats count by path, ip_address
| sort -count
```

### Exceptions non gérées

```spl
index=idp-portal event="unhandled_exception"
| table _time, correlation_id, path, exception_type, exception_message
| sort -_time
```

## Alertes recommandées

### Alerte: Taux d'erreur 5xx élevé

**Seuil**: > 5% des requêtes en erreur 5xx sur 5 minutes

```spl
index=idp-portal event="request_completed"
| where _time > relative_time(now(), "-5m")
| eval is_5xx=if(status_code>=500, 1, 0)
| stats sum(is_5xx) as errors, count as total
| eval error_rate=errors/total*100
| where error_rate > 5
```

### Alerte: Health check dégradé

**Seuil**: 3 échecs consécutifs

```spl
index=idp-portal event="health_check_failed"
| where _time > relative_time(now(), "-5m")
| stats count by service
| where count >= 3
```

### Alerte: Requêtes lentes

**Seuil**: P95 > 2 secondes sur 10 minutes

```spl
index=idp-portal event="request_completed"
| where _time > relative_time(now(), "-10m")
| stats perc95(duration_ms) as p95
| where p95 > 2000
```

### Alerte: Pics d'authentification échouée

**Seuil**: > 10 échecs par IP en 5 minutes

```spl
index=idp-portal event="auth_unauthorized_access"
| where _time > relative_time(now(), "-5m")
| stats count by ip_address
| where count > 10
```

## Procédures de dépannage

### 1. Requête échouée avec 500

1. Obtenir le `correlation_id` de la réponse (header `X-Idp-Request-Id`)
2. Rechercher dans Splunk :
   ```spl
   index=idp-portal correlation_id="<id>" | sort _time
   ```
3. Identifier l'événement `unhandled_exception` ou `request_failed`
4. Analyser le traceback dans le champ `exception`

### 2. Lenteur intermittente

1. Identifier les endpoints lents :
   ```spl
   index=idp-portal event="request_completed" duration_ms > 1000
   | stats count, avg(duration_ms) by path | sort -avg(duration_ms)
   ```
2. Corréler avec les périodes de lenteur
3. Vérifier les appels externes (Vault, ServiceNow) via health check logs

### 3. Health check dégradé

1. Vérifier quel service est en échec :
   ```spl
   index=idp-portal event="health_check_failed" | stats last(error) by service
   ```
2. Actions par service :
   - **Oracle**: Vérifier connexion réseau, listener TNS, charge DB
   - **Vault**: Vérifier état du cluster Vault, tokens expirés
   - **ServiceNow**: Vérifier disponibilité instance, credentials

### 4. Pic d'erreurs 401/403

1. Identifier la source :
   ```spl
   index=idp-portal event="auth_unauthorized_access"
   | stats count by ip_address, path | sort -count
   ```
2. Si concentré sur une IP : possible attaque ou misconfiguration client
3. Si réparti : vérifier validité des tokens JWT, config SAML

## Métriques clés

| Métrique | Seuil normal | Alerte |
|----------|--------------|--------|
| Temps de réponse P50 | < 100ms | > 500ms |
| Temps de réponse P95 | < 500ms | > 2000ms |
| Taux d'erreur 5xx | < 0.1% | > 1% |
| Taux d'erreur 4xx | < 5% | > 10% |
| Health check | healthy | degraded |
| Auth failures / 5min | < 5 | > 20 |

## Contacts escalade

| Niveau | Équipe | Cas |
|--------|--------|-----|
| L1 | DBOPS | Health check degraded, alertes standard |
| L2 | Dev Backend | Erreurs applicatives, bugs |
| L3 | Infra | Problèmes réseau, DB, Vault |
