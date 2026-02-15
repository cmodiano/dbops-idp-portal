# Story 27.8 : Intégration Splunk — envoi des logs complets, correlation_id, et recherche audit par correlation_id

Status: review

## Story

En tant que **équipe ops et auditeurs**,
Je veux **conserver les logs résumé (acteur, correlation_id) dans notre système tout en envoyant les logs complets (actions et workflows) vers Splunk, avec le correlation_id présent dans Splunk pour associer chaque événement à un run et à une personne**,
Afin que **on dispose d'un audit détaillé dans Splunk tout en permettant une recherche par correlation_id dans l'audit du portail pour simplifier le travail d'audit**.

## Contexte Epic 27

**Objectif Epic :** Exposer les intégrations (AAP en premier) via des adapters backend : appels API (workflows, job templates), suivi des jobs en cours (logs + statut) et mise à jour en temps réel (websockets). Adapter pattern pour les intégrations avec plateformes tierces (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault), et maintenant Splunk pour l'observabilité et l'audit.

**Stories complétées :**
- **Story 27.1** : AAPAdapter avec trigger(), get_status(), get_job_logs(), monitoring WebSocket (41 tests)
- **Story 27.2** : TowerAdapter (Ansible Tower) avec poll_tower_job_status(), séparé de AAP (85 tests)
- **Story 27.3** : AzureDevOpsAdapter avec pipelines, runs, logs, polling 5s temps réel (126 tests)
- **Story 27.4** : GitHubActionsAdapter avec workflow runs, webhooks/polling monitoring (150 tests)
- **Story 27.5** : TerraformCloudAdapter avec runs (plan/apply), webhooks/polling (222 tests)
- **Story 27.6** : VaultService avec retry, circuit breaker, cache, résolution credential_ref (253 tests)
- **Story 27.7** : Admin frontend — catalogue types d'intégration (7 types : AAP, Tower, Azure DevOps, GitHub, Terraform, Vault, ServiceNow)

**État actuel (après Story 27.7) :**
- 6 adapters backend fonctionnels + ServiceNow
- Catalogue types d'intégration complet avec 7 types actifs
- VaultService résout credential_ref pour tous les adapters
- 281 tests backend integrations + 30 tests frontend IntegrationForm passent
- **Logging structuré avec structlog déjà en place** (structlog JSON → Files → Splunk Forwarder)
- **correlation_id déjà propagé** dans tous les logs, external calls, WebSocket
- [Source: 27-1 à 27-7 story files, architecture.md lines 238, 428, 678, 742, 748]

**Problème résolu par Story 27.8 :**
- Les logs structurés JSON sont écrits en fichiers, mais **pas d'envoi direct vers Splunk HEC (HTTP Event Collector)** pour audit temps réel
- **Aucune recherche par correlation_id** dans l'interface Audit du portail (menu Audit)
- Les auditeurs doivent basculer entre le portail et Splunk pour corréler les événements
- Pas de garantie que les logs complets (output steps, logs plateforme) sont envoyés à Splunk
- Pas de configuration Splunk centralisée (URL HEC, token, index) dans le système d'intégration

**Approche Story 27.8 :**
1. **Backend** : Créer SplunkAdapter (Pattern Story 27.1-27.6) avec envoi logs via HEC (HTTP Event Collector)
2. **Backend** : Enrichir logs avec correlation_id, acteur (user_id), execution_id systématiquement
3. **Backend** : Ajouter type d'intégration "splunk" au catalogue (Story 27.7 pattern) avec credential_ref Vault
4. **Backend** : Créer SplunkLoggingHandler (structlog sink) pour envoi asynchrone batch vers Splunk HEC
5. **Backend** : Étendre API Audit avec paramètre `correlation_id` (GET /api/v1/audit/executions?correlation_id=xxx)
6. **Frontend** : Ajouter champ recherche "Correlation ID" dans AuditPage avec filtre backend
7. **Tests** : Valider envoi Splunk (mock HEC), recherche correlation_id, propagation correlation_id dans tous logs

## Acceptance Criteria

**AC1 — SplunkAdapter hérite BaseAdapter avec méthodes send_event() et send_batch()**

**Given** le besoin d'envoyer des événements vers Splunk HEC de manière cohérente avec les autres adapters
**When** on implémente SplunkAdapter
**Then** un adapter `SplunkAdapter` est créé qui hérite de `BaseAdapter` (pattern Stories 27.1-27.6) dans `adapters/splunk_adapter.py` avec :
- Méthode `send_event(event: dict, **kwargs) -> dict` : envoie un événement unique vers Splunk HEC
- Méthode `send_batch(events: list[dict], **kwargs) -> dict` : envoie un batch d'événements vers Splunk HEC
- Configuration via `base_url` (Splunk HEC endpoint) et `auth_headers` (Authorization: Splunk <token>)
- Support credential_ref Vault pour résolution token Splunk via VaultService (Story 27.6)
- Logging structlog avec correlation_id pour traçabilité (pattern adapters existants)

**And** SplunkAdapter expose aussi méthodes BaseAdapter abstraites pour compatibilité (trigger, get_status, get_job_logs, cancel_execution) même si non utilisées pour Splunk

**AC2 — Enrichissement logs structlog avec correlation_id, user_id, execution_id**

**Given** le système de logging structuré JSON déjà en place (core/logging.py Story M.8)
**When** un événement est loggé (exécution, step, API call externe)
**Then** tous les logs structlog incluent systématiquement :
- `correlation_id` : UUID propagé dans toute la chaîne (request → execution → adapter calls → WebSocket)
- `user_id` : Identifiant de l'acteur ayant déclenché l'action (ou 'system' pour actions automatiques)
- `execution_id` : ID de l'exécution en cours (si applicable)
- `timestamp` : ISO8601 UTC
- `event` : Nom de l'événement (ex: "execution_started", "step_completed", "adapter_call")
- `level` : Niveau de log (INFO, WARNING, ERROR, etc.)

**And** structlog.contextvars.bind_contextvars() est utilisé pour propager correlation_id, user_id dans tous les logs downstream
**And** les événements enrichis sont disponibles pour SplunkLoggingHandler (AC3)

**AC3 — Type d'intégration "splunk" dans catalogue avec credential_ref Vault**

**Given** le catalogue IntegrationTypeCatalogue (Story 27.7) supporte AAP, Tower, Azure DevOps, GitHub, Terraform, Vault, ServiceNow
**When** on ajoute Splunk comme type d'intégration
**Then** une fixture pour type `splunk` est créée avec :
- `code` : "splunk"
- `name` : "Splunk HEC"
- `description` : "Splunk HTTP Event Collector — envoi logs structurés JSON vers Splunk pour observabilité et audit"
- `version` : "1.0"
- `is_active` : true

**And** les actions supportées sont définies dans `IntegrationAction` :
1. **send_event** : Envoyer événement unique vers Splunk HEC
   - `required_params` : `{"event": {"type": "object", "description": "Événement JSON à indexer"}}`
   - `optional_params` : `{"sourcetype": {"type": "string"}, "index": {"type": "string"}}`
2. **send_batch** : Envoyer batch événements vers Splunk HEC
   - `required_params` : `{"events": {"type": "array", "description": "Liste événements JSON"}}`
   - `optional_params` : `{"sourcetype": {"type": "string"}, "index": {"type": "string"}}`

**And** la fixture est chargeable via `python manage.py loaddata` ou commande seed_integration_types
**And** le menu Admin > Intégrations permet de créer une intégration Splunk avec :
- URL : `https://splunk.example.com:8088` (Splunk HEC endpoint)
- Credential Ref : `vault:secret/data/splunk/prod#token` (résolu par VaultService)

**AC4 — SplunkLoggingHandler comme sink structlog pour envoi asynchrone batch**

**Given** le besoin d'envoyer tous les logs structlog vers Splunk sans bloquer l'exécution
**When** on configure structlog avec SplunkLoggingHandler
**Then** un handler `SplunkLoggingHandler` est créé dans `core/splunk_logging_handler.py` avec :
- Hérite `logging.Handler` Python standard
- Buffer interne (queue.Queue ou liste thread-safe) pour accumulation événements
- Flush automatique toutes les 5 secondes OU quand 100 événements accumulés (configurable)
- Appel SplunkAdapter.send_batch() pour envoi batch vers Splunk HEC
- Thread background ou async task Celery pour flush non-bloquant
- Gestion erreur : si Splunk indisponible → log warning local + drop events (ou retry limité selon stratégie)

**And** SplunkLoggingHandler est ajouté aux processors structlog dans `core/logging.py` (configure_structlog)
**And** tous les logs structlog (INFO, WARNING, ERROR, etc.) sont envoyés vers Splunk automatiquement
**And** les événements contiennent correlation_id, user_id, execution_id enrichis (AC2)

**AC5 — Extension API Audit avec paramètre correlation_id**

**Given** l'API audit existante `GET /api/v1/audit/executions` avec filtres from, to, environment, action_id, user_id, status (audit/views.py ligne 108-159)
**When** un auditeur veut filtrer par correlation_id
**Then** la fonction `_build_audit_queryset()` est étendue pour accepter paramètre `correlation_id` (query param) :
- Si `correlation_id` fourni → filtrer `AuditLog.objects.filter(correlation_id=<valeur>)` (match exact)
- Si vide ou absent → pas de filtre (comportement actuel conservé)

**And** l'API `GET /api/v1/audit/executions?correlation_id=abc-123-xyz` retourne uniquement les entrées avec ce correlation_id
**And** le paramètre est documenté dans la docstring AuditExecutionsView et dans l'OpenAPI (si existant)
**And** la réponse JSON inclut déjà correlation_id dans chaque entrée data (ligne 235 actuelle)

**AC6 — Frontend Audit : champ recherche Correlation ID**

**Given** la page Audit frontend (menu Audit) affiche la liste des exécutions avec filtres (from, to, environment, action_id, user_id, status)
**When** un auditeur veut rechercher par correlation_id
**Then** le composant AuditPage (ou AuditFilters) est étendu avec :
- Champ Input "Correlation ID" (Ant Design Input) dans la section filtres
- Label : "Correlation ID" avec tooltip : "Rechercher toutes les traces d'une exécution par son identifiant de corrélation"
- Le champ est relié au paramètre API `correlation_id` (query param)
- Changement de valeur → déclenche rechargement de la liste via `GET /api/v1/audit/executions?correlation_id=<valeur>`

**And** si correlation_id fourni → affichage d'un Tag/Badge "Filtré par correlation_id: <valeur>" pour visibilité
**And** bouton "Effacer filtres" reset aussi le champ correlation_id
**And** le filtre correlation_id fonctionne en combinaison avec les autres filtres (AND logique)

**AC7 — Configuration Splunk centralisée avec indisponibilité handling**

**Given** le besoin de configurer Splunk HEC (URL, token, index, sourcetype) de manière centralisée
**When** on configure SplunkAdapter et SplunkLoggingHandler
**Then** la configuration est gérée via :
- Option A : Variables d'environnement (`SPLUNK_HEC_URL`, `SPLUNK_HEC_TOKEN`, `SPLUNK_INDEX`, `SPLUNK_SOURCETYPE`)
- Option B : Intégration Admin > Intégrations type "splunk" (URL + credential_ref Vault) chargée au démarrage
- Option C : Fichier config Django settings (SPLUNK_CONFIG dict)

**And** en cas d'indisponibilité Splunk (timeout, HTTP 5xx, network error) :
- SplunkLoggingHandler log warning avec structlog local : "splunk_hec_unavailable" + error details
- Événements sont **drop** après retry (2 tentatives max espacées de 5s) pour éviter accumulation mémoire
- Les logs résumé en base (AUDIT_LOG, EXECUTION_STEPS) sont **préservés** (pas d'impact sur portail)
- Comportement documenté dans `docs/splunk-integration-failure-handling.md`

**And** healthcheck Splunk HEC (optionnel) : endpoint `/health` vérifie connectivité Splunk et retourne status "healthy" ou "degraded"

**AC8 — Tests backend : SplunkAdapter, SplunkLoggingHandler, API Audit correlation_id**

**Given** le besoin de valider l'intégration Splunk end-to-end
**When** on exécute les tests backend
**Then** au minimum **30 tests backend** sont créés couvrant :

**Tests SplunkAdapter (12 tests)** :
1. test_splunk_adapter_send_event_success : Mock httpx POST HEC → retour 200 → event envoyé
2. test_splunk_adapter_send_event_with_correlation_id : event contient correlation_id
3. test_splunk_adapter_send_batch_success : Mock POST HEC batch → retour 200 → 10 events envoyés
4. test_splunk_adapter_send_event_hec_error : Mock POST HEC → retour 503 → raise ServiceUnavailableError
5. test_splunk_adapter_send_batch_timeout : Mock POST HEC → timeout 30s → raise ServiceUnavailableError
6. test_splunk_adapter_credential_ref_vault : credential_ref résolu via VaultService (mock) → token injecté dans auth_headers
7. test_splunk_adapter_base_adapter_methods : trigger(), get_status(), get_job_logs(), cancel_execution() lèvent NotImplementedError (ou return dummy)
8. test_splunk_adapter_event_format : event dict contient fields (correlation_id, user_id, execution_id, timestamp, level, event)
9. test_splunk_adapter_sourcetype_index : send_event avec sourcetype="idp:execution" index="prod-idp"
10. test_splunk_adapter_retry_on_500 : Mock POST HEC → 1er call 500, 2e call 200 → success après retry
11. test_splunk_adapter_circuit_breaker : 5 échecs consécutifs → circuit ouvert → raise sans appel HTTP (optionnel)
12. test_splunk_adapter_logging_structlog : send_event log "splunk_event_sent" avec structlog

**Tests SplunkLoggingHandler (10 tests)** :
13. test_handler_buffer_flush_on_count : 100 événements → flush automatique → send_batch appelé
14. test_handler_buffer_flush_on_time : 5 secondes → flush automatique même si <100 events
15. test_handler_emit_event : handler.emit(LogRecord) → event ajouté au buffer
16. test_handler_flush_calls_send_batch : handler.flush() → SplunkAdapter.send_batch() appelé avec buffer events
17. test_handler_error_handling : send_batch raise ServiceUnavailableError → log warning + drop events
18. test_handler_enrichment_correlation_id : LogRecord avec extra={'correlation_id': 'abc'} → event contient correlation_id
19. test_handler_enrichment_user_id : LogRecord avec extra={'user_id': 'john'} → event contient user_id
20. test_handler_thread_safety : 10 threads émettent 100 events chacun → tous events buffered sans loss
21. test_handler_disable_if_no_config : SPLUNK_HEC_URL non défini → handler disabled + log warning
22. test_handler_max_buffer_size : buffer dépasse 1000 events → drop oldest events (FIFO) pour éviter OOM

**Tests API Audit correlation_id (8 tests)** :
23. test_audit_api_filter_correlation_id_exact : GET /audit/executions?correlation_id=abc-123 → retourne uniquement entrées avec correlation_id=abc-123
24. test_audit_api_filter_correlation_id_empty : correlation_id="" → pas de filtre appliqué (comportement actuel)
25. test_audit_api_filter_correlation_id_not_found : correlation_id inexistant → retourne data=[] vide
26. test_audit_api_filter_correlation_id_with_other_filters : correlation_id + environment + from/to → filtres combinés (AND)
27. test_audit_api_response_includes_correlation_id : chaque entrée data contient champ correlation_id (ligne 235)
28. test_audit_api_pagination_with_correlation_id : 50 entrées même correlation_id → pagination fonctionne (limit 25, offset 25)
29. test_audit_export_csv_includes_correlation_id : GET /audit/export?fmt=csv&correlation_id=abc → CSV contient colonne correlation_id (ligne 321-341)
30. test_audit_api_correlation_id_case_sensitive : correlation_id=ABC vs abc → match exact case-sensitive

**And** tous les tests utilisent pytest avec factories AuditLogFactory, IntegrationFactory, mock httpx.AsyncClient pour HEC
**And** couverture backend > 90% sur nouveau code (SplunkAdapter, SplunkLoggingHandler, API extension)

**AC9 — Tests frontend : filtre Correlation ID dans AuditPage**

**Given** le besoin de valider le filtre correlation_id frontend
**When** on exécute les tests frontend
**Then** au minimum **8 tests frontend** sont créés couvrant :

1. test_audit_page_correlation_id_input_renders : AuditPage affiche champ Input "Correlation ID"
2. test_audit_page_correlation_id_filter_sends_param : Input valeur "abc-123" → API call GET /audit/executions?correlation_id=abc-123
3. test_audit_page_correlation_id_filter_displays_results : Mock API retourne 3 entrées → Table affiche 3 lignes
4. test_audit_page_correlation_id_badge_shown : correlation_id filtré → Badge "Filtré par correlation_id: abc-123" affiché
5. test_audit_page_correlation_id_clear_filter : Bouton "Effacer filtres" → champ correlation_id reset + badge disparu
6. test_audit_page_correlation_id_combined_filters : correlation_id + environment "prod" → API call avec les 2 params
7. test_audit_page_correlation_id_tooltip : Input correlation_id affiche tooltip explicatif au survol
8. test_audit_page_correlation_id_empty_results : Mock API retourne data=[] → message "Aucune entrée trouvée"

**And** tests utilisent React Testing Library + Mock Service Worker (MSW) pour mock API
**And** couverture frontend > 85% sur nouveau code (AuditPage, AuditFilters composants)

**AC10 — Documentation : Splunk integration, correlation_id usage, failure handling**

**Given** le besoin de documenter l'intégration Splunk et l'usage correlation_id
**When** on met à jour la documentation
**Then** les fichiers suivants sont créés/mis à jour :

1. **docs/splunk-integration.md** :
   - Architecture : SplunkAdapter + SplunkLoggingHandler → Splunk HEC
   - Configuration : Variables env, intégration Admin, credential_ref Vault
   - Event schema : correlation_id, user_id, execution_id, timestamp, level, event, details
   - Exemples événements Splunk (3 exemples : execution_started, step_completed, adapter_call)
   - Splunk search queries exemples (4 queries : recherche par correlation_id, par user_id, par execution_id, erreurs par période)

2. **docs/splunk-integration-failure-handling.md** :
   - Comportement en cas d'indisponibilité Splunk (retry 2x, drop events, log warning)
   - Impact sur portail : logs résumé préservés (AUDIT_LOG, EXECUTION_STEPS), pas de blocage exécution
   - Monitoring : métriques Splunk HEC (events sent, errors, drops), healthcheck endpoint

3. **docs/audit-correlation-id-search.md** :
   - Guide auditeur : recherche par correlation_id dans portail Audit
   - Lien portail ↔ Splunk : copier correlation_id du portail → coller dans Splunk search
   - Exemples screenshots (optionnel) : filtre correlation_id, résultats affichés

4. **docs/integration-type-catalogue.md** (mise à jour Story 27.7) :
   - Section nouveau type "Splunk HEC" (code: splunk) avec actions send_event, send_batch
   - Tableau récapitulatif mis à jour : 8 types au total (AAP, Tower, Azure DevOps, GitHub, Terraform, Vault, ServiceNow, **Splunk**)

**And** README principal référence Splunk integration avec lien vers docs/splunk-integration.md

**AC11 — Structlog Event Schema standardisé et exemples Splunk queries**

**Given** le besoin d'un schéma JSON cohérent pour les événements Splunk
**When** on définit le schéma événement
**Then** un schéma JSON standardisé est documenté dans `docs/splunk-integration.md` avec structure :

```json
{
  "timestamp": "2026-02-14T10:30:45.123Z",  // ISO8601 UTC
  "event": "execution_started",  // Nom événement
  "level": "INFO",  // DEBUG, INFO, WARNING, ERROR, CRITICAL
  "correlation_id": "abc-123-def-456",  // UUID traçabilité
  "user_id": "john.doe@example.com",  // Acteur
  "execution_id": 42,  // ID exécution (si applicable)
  "action_id": 10,  // ID action (si applicable)
  "environment": "production",  // Environnement cible
  "platform": "aap",  // Plateforme intégration (aap, azure_devops, etc.)
  "details": {  // Détails spécifiques événement
    "job_template_id": "123",
    "extra_vars": {"key": "value"}
  },
  "source": "idp-portal",  // Source système
  "sourcetype": "idp:execution",  // Sourcetype Splunk
  "index": "prod-idp"  // Index Splunk
}
```

**And** 3 exemples événements concrets documentés :
1. **execution_started** : Démarrage exécution action avec correlation_id, user_id, action_id, environment
2. **step_completed** : Fin step exécution avec correlation_id, execution_id, step_id, output, status
3. **adapter_call** : Appel adapter externe (AAP, GitHub, etc.) avec correlation_id, platform, method, url, status_code

**And** 4 exemples Splunk search queries documentés :
1. **Recherche par correlation_id** : `index="prod-idp" correlation_id="abc-123-def-456" | table timestamp, event, user_id, details`
2. **Recherche par user_id** : `index="prod-idp" user_id="john.doe@example.com" earliest=-24h | stats count by event`
3. **Recherche par execution_id** : `index="prod-idp" execution_id=42 | sort timestamp | table timestamp, event, level, details`
4. **Erreurs par période** : `index="prod-idp" level=ERROR earliest=-7d | timechart count by event`

## Tasks / Subtasks

- [x] Task 1: Créer SplunkAdapter héritant BaseAdapter (AC: #1)
  - [x]1.1: Créer fichier `adapters/splunk_adapter.py` avec classe SplunkAdapter(BaseAdapter)
  - [x]1.2: Implémenter méthode `send_event(event: dict, sourcetype: str = None, index: str = None, **kwargs) -> dict`
  - [x]1.3: Implémenter méthode `send_batch(events: list[dict], sourcetype: str = None, index: str = None, **kwargs) -> dict`
  - [x]1.4: Configuration __init__(base_url: str, auth_headers: dict, timeout: float = 30.0)
  - [x]1.5: Support credential_ref Vault : résolution token via VaultService (pattern Stories 27.1-27.6)
  - [x]1.6: Logging structlog pour traçabilité : "splunk_event_sent", "splunk_batch_sent", "splunk_hec_error" avec correlation_id
  - [x]1.7: Méthodes BaseAdapter abstraites (trigger, get_status, get_job_logs, cancel_execution) → raise NotImplementedError ou return dummy
  - [x]1.8: Gestion erreur HTTP (4xx, 5xx) → raise ServiceUnavailableError avec message détaillé
  - [x]1.9: Retry sur erreur temporaire (500, 503) : 2 tentatives max espacées de 5s (pattern adapters existants)

- [x] Task 2: Enrichir logging structlog avec correlation_id, user_id, execution_id (AC: #2)
  - [x]2.1: Vérifier structlog.contextvars.merge_contextvars dans core/logging.py configure_structlog (déjà présent ligne 46)
  - [x]2.2: Pattern propagation correlation_id : structlog.contextvars.bind_contextvars(correlation_id=<uuid>) au début request/execution
  - [x]2.3: Pattern propagation user_id : structlog.contextvars.bind_contextvars(user_id=<user>) après auth
  - [x]2.4: Pattern propagation execution_id : structlog.contextvars.bind_contextvars(execution_id=<id>) au démarrage execution
  - [x]2.5: Vérifier tous adapters existants (AAP, Tower, Azure, GitHub, Terraform, Vault) loggent avec correlation_id (déjà fait Stories 27.1-27.6)
  - [x]2.6: Vérifier ExecutionService, consumers, tasks loggent avec correlation_id, user_id, execution_id
  - [x]2.7: Documenter schéma événement structlog standardisé dans docs/splunk-integration.md (voir AC11)

- [x] Task 3: Ajouter type "splunk" dans catalogue IntegrationTypeCatalogue (AC: #3)
  - [x]3.1: Créer fixture `integrations/fixtures/splunk_integration_type.json` avec type splunk
  - [x]3.2: Définir IntegrationTypeCatalogue splunk (code, name, description, version, is_active)
  - [x]3.3: Définir 2 actions Splunk (send_event, send_batch) avec schémas JSON required_params/optional_params
  - [x]3.4: Mettre à jour fixture consolidée `integrations/fixtures/integration_type_catalogue.json` (ajouter splunk comme 8e type)
  - [x]3.5: Tester chargement fixture : `python manage.py loaddata splunk_integration_type` ou `python manage.py seed_integration_types --force`
  - [x]3.6: Vérifier menu Admin > Intégrations affiche type "Splunk HEC" dans Select Type (frontend charge déjà dynamiquement)
  - [x]3.7: Vérifier création intégration Splunk : URL=https://splunk.example.com:8088, credential_ref=vault:secret/data/splunk/prod#token

- [x] Task 4: Créer SplunkLoggingHandler comme sink structlog (AC: #4)
  - [x]4.1: Créer fichier `core/splunk_logging_handler.py` avec classe SplunkLoggingHandler(logging.Handler)
  - [x]4.2: Buffer interne : queue.Queue (thread-safe) ou liste + Lock pour accumulation événements
  - [x]4.3: Méthode emit(record: LogRecord) : extraire event dict depuis LogRecord.msg (structlog JSONRenderer) + ajouter au buffer
  - [x]4.4: Méthode flush() : appeler SplunkAdapter.send_batch(buffer_events) + vider buffer
  - [x]4.5: Thread background ou timer (threading.Timer) : flush automatique toutes les 5 secondes (configurable SPLUNK_FLUSH_INTERVAL)
  - [x]4.6: Flush automatique si buffer atteint 100 événements (configurable SPLUNK_BATCH_SIZE)
  - [x]4.7: Gestion erreur : send_batch raise ServiceUnavailableError → log warning "splunk_hec_unavailable" + drop events
  - [x]4.8: Max buffer size : si buffer dépasse 1000 events → drop oldest (FIFO) pour éviter OOM
  - [x]4.9: Configuration : charger SPLUNK_HEC_URL, SPLUNK_HEC_TOKEN depuis env ou settings Django ou intégration Admin
  - [x]4.10: Intégrer SplunkLoggingHandler dans core/logging.py configure_structlog : ajouter handler à logging.root

- [x] Task 5: Étendre API Audit avec paramètre correlation_id (AC: #5)
  - [x]5.1: Modifier audit/views.py fonction _build_audit_queryset (ligne 108-159)
  - [x]5.2: Extraire paramètre correlation_id depuis request.query_params.get("correlation_id")
  - [x]5.3: Si correlation_id fourni (non vide) → filtrer queryset : qs = qs.filter(correlation_id=correlation_id) (match exact)
  - [x]5.4: Si correlation_id vide ou absent → pas de filtre (comportement actuel)
  - [x]5.5: Documenter paramètre dans docstring AuditExecutionsView (ligne 162-168)
  - [x]5.6: Vérifier réponse JSON inclut déjà correlation_id dans chaque entrée data (ligne 235 actuelle : "correlation_id": r.correlation_id)
  - [x]5.7: Tester manuellement GET /api/v1/audit/executions?correlation_id=abc-123 retourne uniquement entrées matching

- [x] Task 6: Frontend Audit — ajouter champ recherche Correlation ID (AC: #6)
  - [x]6.1: Identifier composant AuditPage ou AuditFilters (frontend/src/pages/AuditPage.tsx ou équivalent)
  - [x]6.2: Ajouter state local correlationId (useState hook) pour valeur Input
  - [x]6.3: Ajouter Ant Design Input dans section filtres : <Input placeholder="Correlation ID" value={correlationId} onChange={handleCorrelationIdChange} />
  - [x]6.4: Label Input : "Correlation ID" avec Tooltip : "Rechercher toutes les traces d'une exécution par son identifiant de corrélation"
  - [x]6.5: Relier Input au paramètre API : lors de rechargement liste → inclure correlation_id dans query params GET /api/v1/audit/executions
  - [x]6.6: Afficher Badge "Filtré par correlation_id: {correlationId}" si correlationId non vide (Ant Design Tag closable)
  - [x]6.7: Bouton "Effacer filtres" → reset correlationId state + recharger liste sans paramètre
  - [x]6.8: Vérifier filtre correlation_id fonctionne en combinaison avec autres filtres (environment, from, to, user_id, status)

- [x] Task 7: Configuration Splunk centralisée et indisponibilité handling (AC: #7)
  - [x]7.1: Définir variables d'environnement dans settings Django ou .env : SPLUNK_HEC_URL, SPLUNK_HEC_TOKEN, SPLUNK_INDEX, SPLUNK_SOURCETYPE
  - [x]7.2: Option alternative : charger config depuis intégration Admin type "splunk" (Integration.objects.filter(type__code='splunk').first()) au démarrage app
  - [x]7.3: SplunkLoggingHandler : si SPLUNK_HEC_URL non défini → handler disabled + log warning "splunk_hec_not_configured"
  - [x]7.4: SplunkAdapter retry : 2 tentatives max espacées de 5s sur erreur temporaire (500, 503, timeout)
  - [x]7.5: SplunkLoggingHandler : si send_batch échoue après retry → log warning "splunk_hec_unavailable" + drop events (pas de blocage)
  - [x]7.6: Documenter comportement indisponibilité dans docs/splunk-integration-failure-handling.md (voir AC10)
  - [x]7.7: Healthcheck Splunk HEC (optionnel) : endpoint GET /health vérifie connectivité Splunk → retourne {"splunk": "healthy"} ou {"splunk": "degraded"}
  - [x]7.8: Logs résumé AUDIT_LOG, EXECUTION_STEPS préservés même si Splunk down (pas d'impact portail)

- [x] Task 8: Tests backend SplunkAdapter (AC: #8)
  - [x]8.1: Créer fichier `adapters/tests/test_splunk_adapter.py` avec 12 tests SplunkAdapter (voir AC8)
  - [x]8.2: Mock httpx.AsyncClient pour POST Splunk HEC (pytest-httpx ou respx)
  - [x]8.3: Test send_event_success : Mock POST → 200 → event envoyé
  - [x]8.4: Test send_event_with_correlation_id : event dict contient correlation_id
  - [x]8.5: Test send_batch_success : Mock POST batch → 200 → 10 events envoyés
  - [x]8.6: Test send_event_hec_error : Mock POST → 503 → raise ServiceUnavailableError
  - [x]8.7: Test send_batch_timeout : Mock POST → timeout → raise ServiceUnavailableError
  - [x]8.8: Test credential_ref_vault : mock VaultService.resolve_credential_ref → token résolu
  - [x]8.9: Test base_adapter_methods : trigger(), get_status() raise NotImplementedError
  - [x]8.10: Test event_format : event dict fields (correlation_id, user_id, execution_id, timestamp, level, event)
  - [x]8.11: Test sourcetype_index : send_event avec sourcetype="idp:execution" index="prod-idp"
  - [x]8.12: Test retry_on_500 : Mock POST → 1er call 500, 2e call 200 → success
  - [x]8.13: Test logging_structlog : send_event log "splunk_event_sent" avec structlog

- [x] Task 9: Tests backend SplunkLoggingHandler (AC: #8)
  - [x]9.1: Créer fichier `core/tests/test_splunk_logging_handler.py` avec 10 tests handler (voir AC8)
  - [x]9.2: Test buffer_flush_on_count : 100 events → flush automatique
  - [x]9.3: Test buffer_flush_on_time : 5 secondes → flush automatique
  - [x]9.4: Test emit_event : handler.emit(LogRecord) → event buffered
  - [x]9.5: Test flush_calls_send_batch : handler.flush() → SplunkAdapter.send_batch() appelé
  - [x]9.6: Test error_handling : send_batch raise → log warning + drop events
  - [x]9.7: Test enrichment_correlation_id : LogRecord extra={'correlation_id': 'abc'} → event contient correlation_id
  - [x]9.8: Test enrichment_user_id : LogRecord extra={'user_id': 'john'} → event contient user_id
  - [x]9.9: Test thread_safety : 10 threads × 100 events → tous buffered
  - [x]9.10: Test disable_if_no_config : SPLUNK_HEC_URL non défini → handler disabled
  - [x]9.11: Test max_buffer_size : buffer > 1000 events → drop oldest (FIFO)

- [x] Task 10: Tests backend API Audit correlation_id (AC: #8)
  - [x]10.1: Créer fichier `audit/tests/test_audit_correlation_id.py` avec 8 tests API (voir AC8)
  - [x]10.2: Test filter_correlation_id_exact : GET /audit/executions?correlation_id=abc-123 → filtre exact
  - [x]10.3: Test filter_correlation_id_empty : correlation_id="" → pas de filtre
  - [x]10.4: Test filter_correlation_id_not_found : correlation_id inexistant → data=[]
  - [x]10.5: Test filter_correlation_id_with_other_filters : correlation_id + environment + from/to → AND
  - [x]10.6: Test response_includes_correlation_id : chaque entrée data contient correlation_id
  - [x]10.7: Test pagination_with_correlation_id : 50 entrées → pagination limit 25
  - [x]10.8: Test export_csv_includes_correlation_id : CSV contient colonne correlation_id
  - [x]10.9: Test correlation_id_case_sensitive : ABC vs abc → match case-sensitive

- [x] Task 11: Tests frontend filtre Correlation ID (AC: #9)
  - [x]11.1: Créer fichier `frontend/src/pages/AuditPage.test.tsx` (ou étendre existant) avec 8 tests frontend (voir AC9)
  - [x]11.2: Test correlation_id_input_renders : AuditPage affiche Input "Correlation ID"
  - [x]11.3: Test correlation_id_filter_sends_param : Input "abc-123" → API call avec param
  - [x]11.4: Test correlation_id_filter_displays_results : Mock API retourne 3 entrées → Table affiche 3 lignes
  - [x]11.5: Test correlation_id_badge_shown : correlation_id filtré → Badge affiché
  - [x]11.6: Test correlation_id_clear_filter : Bouton "Effacer" → reset champ + badge disparu
  - [x]11.7: Test correlation_id_combined_filters : correlation_id + environment → API avec 2 params
  - [x]11.8: Test correlation_id_tooltip : Input affiche tooltip au survol
  - [x]11.9: Test correlation_id_empty_results : Mock API data=[] → message "Aucune entrée"
  - [x]11.10: Mock Service Worker (MSW) pour mock GET /api/v1/audit/executions

- [x] Task 12: Documentation Splunk integration et correlation_id (AC: #10, #11)
  - [x]12.1: Créer `docs/splunk-integration.md` avec sections : Architecture, Configuration, Event Schema, Exemples événements, Splunk queries
  - [x]12.2: Documenter schéma JSON standardisé (voir AC11) avec exemple complet
  - [x]12.3: Documenter 3 exemples événements concrets : execution_started, step_completed, adapter_call
  - [x]12.4: Documenter 4 exemples Splunk search queries : par correlation_id, par user_id, par execution_id, erreurs par période
  - [x]12.5: Créer `docs/splunk-integration-failure-handling.md` avec comportement indisponibilité Splunk (retry, drop, log warning)
  - [x]12.6: Créer `docs/audit-correlation-id-search.md` avec guide auditeur : recherche portail → Splunk
  - [x]12.7: Mettre à jour `docs/integration-type-catalogue.md` (Story 27.7) : ajouter type "Splunk HEC" (8e type) dans tableau récapitulatif
  - [x]12.8: Mettre à jour README principal avec lien vers docs/splunk-integration.md
  - [x]12.9: Screenshots (optionnel) : filtre correlation_id dans AuditPage, événements Splunk

## Dev Notes

### Contexte Architectural

**État actuel du logging structuré (Story M.8) :**
- Module `core/logging.py` configure structlog avec JSON output (ligne 1-78)
- Processors : merge_contextvars, add_log_level, TimeStamper ISO8601 UTC, format_exc_info, JSONRenderer
- Tous les adapters (AAP, Tower, Azure DevOps, GitHub, Terraform, Vault) utilisent structlog avec correlation_id (Stories 27.1-27.6)
- correlation_id propagé via structlog.contextvars.bind_contextvars() dans request/execution lifecycle
- [Source: core/logging.py, adapters/aap_adapter.py ligne 90-96, adapters/terraform_cloud_adapter.py, etc.]

**État actuel du système Audit :**
- Modèle AuditLog (core/models.py ligne 202-259) avec champs : id, timestamp, user_id, action_type, entity_type, entity_id, details (JSON CLOB), ip_address, **correlation_id**
- API Audit `GET /api/v1/audit/executions` (audit/views.py ligne 162-255) avec filtres : from, to, environment, action_id, user_id, status
- Fonction _build_audit_queryset (ligne 108-159) construit queryset AuditLog avec filtres
- Réponse JSON inclut déjà correlation_id pour chaque entrée (ligne 235 : "correlation_id": r.correlation_id)
- Export CSV inclut déjà colonne correlation_id (ligne 321, 341)
- [Source: audit/views.py, core/models.py]

**État actuel des adapters (Stories 27.1-27.6) :**
- BaseAdapter abstrait (adapters/base_adapter.py ligne 14-109) définit contrat : trigger(), get_status(), get_job_logs(), cancel_execution()
- 6 adapters implémentés : AAPAdapter, TowerAdapter, AzureDevOpsAdapter, GitHubActionsAdapter, TerraformCloudAdapter, VaultService
- Tous adapters utilisent httpx.AsyncClient pour API calls HTTP
- Tous adapters loggent avec structlog + correlation_id pour traçabilité (pattern ligne 90-96 aap_adapter.py)
- VaultService (Story 27.6) résout credential_ref format `vault:secret/data/path#key` pour tous adapters
- [Source: adapters/base_adapter.py, adapters/aap_adapter.py, core/vault_service.py]

**État actuel du catalogue IntegrationTypeCatalogue (Story 27.7) :**
- Tables INTEGRATION_TYPE_CATALOGUE et INTEGRATION_ACTIONS avec 7 types actifs : AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault, ServiceNow
- Fixtures consolidées : integrations/fixtures/integration_type_catalogue.json (7 types + 27 actions)
- Management command seed_integration_types idempotent pour chargement fixtures
- Frontend Admin > Intégrations charge dynamiquement types depuis API GET /api/v1/integrations/types (Select Type, Actions disponibles)
- [Source: 27-7 story file, integrations/fixtures/, integrations/management/commands/seed_integration_types.py]

**Ce qui manque (objectif Story 27.8) :**
- SplunkAdapter pour envoi événements vers Splunk HEC (POST https://splunk.example.com:8088/services/collector/event)
- SplunkLoggingHandler comme sink structlog pour envoi asynchrone batch (buffer + flush toutes les 5s ou 100 events)
- Type d'intégration "splunk" dans catalogue IntegrationTypeCatalogue (8e type)
- Extension API Audit avec paramètre `correlation_id` dans _build_audit_queryset
- Champ recherche "Correlation ID" dans frontend AuditPage avec filtre backend
- Documentation Splunk integration, event schema, queries exemples, failure handling

### Contraintes Techniques

**Backend (Django + structlog) :**
- SplunkAdapter hérite BaseAdapter (même si trigger/get_status/get_job_logs non utilisés pour Splunk) pour cohérence architecture
- Splunk HEC endpoint : POST https://splunk.example.com:8088/services/collector/event avec header `Authorization: Splunk <token>`
- Body HEC : `{"event": {...}, "sourcetype": "idp:execution", "index": "prod-idp", "fields": {"correlation_id": "abc", ...}}`
- SplunkLoggingHandler : hérite logging.Handler Python standard, buffer events, flush async (thread ou Celery task)
- structlog.contextvars.bind_contextvars() pour propagation correlation_id, user_id, execution_id dans tous logs downstream
- VaultService résout credential_ref `vault:secret/data/splunk/prod#token` pour token Splunk HEC
- Tests : pytest avec mock httpx.AsyncClient (pytest-httpx ou respx), factories AuditLogFactory
- [Source: core/logging.py, adapters/base_adapter.py, core/vault_service.py, Splunk HEC API docs]

**Frontend (React + Ant Design) :**
- AuditPage : ajouter Input "Correlation ID" dans section filtres (Ant Design Input component)
- Relier Input au paramètre API `correlation_id` via query params GET /api/v1/audit/executions?correlation_id=<valeur>
- Afficher Badge "Filtré par correlation_id: {value}" si filtre actif (Ant Design Tag closable)
- Bouton "Effacer filtres" reset state correlationId + recharger liste
- Tests : React Testing Library + Mock Service Worker (MSW) pour mock API
- [Source: frontend patterns Story 27.7, Ant Design docs Input/Tag components]

**Splunk HEC (HTTP Event Collector) :**
- Endpoint : POST https://<splunk>:8088/services/collector/event
- Headers : `Authorization: Splunk <token>`, `Content-Type: application/json`
- Body single event : `{"event": {...}, "sourcetype": "...", "index": "...", "fields": {...}}`
- Body batch events : ligne par ligne JSON (newline-delimited JSON) ou array JSON selon config HEC
- Response 200 : `{"text": "Success", "code": 0}` ou 4xx/5xx si erreur
- Champs indexés : correlation_id, user_id, execution_id doivent être dans `fields` pour indexation Splunk
- [Source: Splunk HEC API documentation, HTTP Event Collector Reference]

**Tests :**
- Backend : 30 tests minimum (12 SplunkAdapter + 10 SplunkLoggingHandler + 8 API Audit)
- Frontend : 8 tests minimum (filtre correlation_id AuditPage)
- Mock httpx pour HEC calls, mock VaultService pour credential_ref, factories Django pour AuditLog/Integration
- Couverture > 90% backend, > 85% frontend sur nouveau code
- [Source: test patterns Stories 27.1-27.7, pytest docs, React Testing Library docs]

### Référencement Code Existant

**Fichiers à modifier :**
- `core/logging.py` — Ajouter SplunkLoggingHandler aux processors/handlers structlog (ligne 43-64 configure_structlog)
- `audit/views.py` — Étendre _build_audit_queryset avec paramètre correlation_id (ligne 108-159)
- `integrations/fixtures/integration_type_catalogue.json` — Ajouter type "splunk" comme 8e type (Story 27.7 pattern)
- `frontend/src/pages/AuditPage.tsx` (ou équivalent) — Ajouter Input "Correlation ID" dans filtres
- `docs/integration-type-catalogue.md` — Mise à jour tableau récapitulatif avec type Splunk (Story 27.7)
- `README.md` — Ajouter référence Splunk integration

**Fichiers à créer :**
- `adapters/splunk_adapter.py` — SplunkAdapter(BaseAdapter) avec send_event(), send_batch()
- `core/splunk_logging_handler.py` — SplunkLoggingHandler(logging.Handler) avec buffer + flush async
- `integrations/fixtures/splunk_integration_type.json` — Fixture type splunk + actions (optionnel si consolidé)
- `adapters/tests/test_splunk_adapter.py` — 12 tests SplunkAdapter
- `core/tests/test_splunk_logging_handler.py` — 10 tests SplunkLoggingHandler
- `audit/tests/test_audit_correlation_id.py` — 8 tests API Audit correlation_id
- `frontend/src/pages/AuditPage.test.tsx` — 8 tests frontend filtre correlation_id (ou étendre existant)
- `docs/splunk-integration.md` — Documentation complète Splunk integration
- `docs/splunk-integration-failure-handling.md` — Documentation indisponibilité Splunk
- `docs/audit-correlation-id-search.md` — Guide auditeur recherche correlation_id

**Fichiers de référence (patterns à suivre) :**
- Adapters existants : `adapters/aap_adapter.py` (ligne 35-150) — Pattern BaseAdapter, httpx, structlog, correlation_id, VaultService
- Logging structlog : `core/logging.py` (ligne 22-78) — Configure structlog avec JSON, contextvars, TimeStamper
- API Audit : `audit/views.py` (ligne 108-255) — Pattern _build_audit_queryset, filtres, pagination, CSV export
- Modèle AuditLog : `core/models.py` (ligne 202-259) — Champs correlation_id, get_details(), set_details()
- Fixtures catalogue : `integrations/fixtures/integration_type_catalogue.json` (Story 27.7) — Format JSON fixtures types + actions
- Tests adapters : `adapters/tests/test_aap_adapter.py`, `adapters/tests/test_terraform_cloud_adapter.py` — Pattern mock httpx, factories, pytest
- Tests frontend : `frontend/src/components/admin/IntegrationFormNewTypes.test.tsx` (Story 27.7) — Pattern React Testing Library, MSW mock API

### Structlog Event Schema Standardisé

**Schéma JSON événement Splunk (champs obligatoires + optionnels) :**

```json
{
  // Champs Splunk HEC (meta)
  "sourcetype": "idp:execution",  // Type source Splunk (configurable)
  "index": "prod-idp",  // Index Splunk (configurable)

  // Champs événement (dans "event" HEC ou fields)
  "timestamp": "2026-02-14T10:30:45.123456Z",  // ISO8601 UTC avec microsecondes
  "event": "execution_started",  // Nom événement structlog (string)
  "level": "INFO",  // Niveau log : DEBUG, INFO, WARNING, ERROR, CRITICAL

  // Champs traçabilité (obligatoires si disponibles)
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",  // UUID v4 traçabilité
  "user_id": "john.doe@example.com",  // Identifiant acteur (ou "system" pour actions auto)
  "execution_id": 42,  // ID exécution IDP Portal (integer, si applicable)
  "action_id": 10,  // ID action IDP Portal (integer, si applicable)

  // Champs contexte (optionnels selon événement)
  "environment": "production",  // Environnement cible (dev, staging, production)
  "platform": "aap",  // Plateforme intégration (aap, tower, azure_devops, github_actions, terraform_cloud, vault, servicenow, splunk)
  "ip_address": "192.168.1.100",  // IP client (si applicable)

  // Détails spécifiques événement (JSON arbitraire)
  "details": {
    "job_template_id": "123",
    "extra_vars": {"ansible_var": "value"},
    "status": "RUNNING",
    "output": "Step 1 completed successfully"
  },

  // Métadonnées système
  "source": "idp-portal",  // Système source (constant)
  "hostname": "idp-backend-pod-1",  // Hostname serveur (optionnel)
  "pid": 1234  // Process ID (optionnel)
}
```

**Champs dans Splunk HEC event :**
- Option A : Tous champs dans `event` → `{"event": {...tous les champs...}, "sourcetype": "...", "index": "..."}`
- Option B : Champs indexés dans `fields`, reste dans `event` → `{"event": {...}, "fields": {"correlation_id": "...", "user_id": "...", "execution_id": ...}, "sourcetype": "...", "index": "..."}`
- Recommandation : Option B pour indexation optimisée Splunk (fields indexés + recherchables)

### Exemples Événements Splunk

**Exemple 1 : execution_started (Démarrage exécution action)**

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
      "extra_vars": {
        "app_version": "1.2.3",
        "deploy_env": "production"
      }
    },
    "source": "idp-portal"
  },
  "fields": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42
  }
}
```

**Exemple 2 : step_completed (Fin step exécution avec output)**

```json
{
  "sourcetype": "idp:execution",
  "index": "prod-idp",
  "event": {
    "timestamp": "2026-02-14T10:32:18.987654Z",
    "event": "step_completed",
    "level": "INFO",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42,
    "environment": "production",
    "platform": "aap",
    "details": {
      "step_id": 1,
      "step_name": "Run Ansible Playbook",
      "status": "COMPLETED",
      "output": "PLAY [Deploy Application] *******\nTASK [Install package] ******** ok: [host1]\nPLAY RECAP ******************** ok=5 changed=3",
      "duration_seconds": 93.5
    },
    "source": "idp-portal"
  },
  "fields": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42
  }
}
```

**Exemple 3 : adapter_call (Appel adapter externe AAP avec réponse)**

```json
{
  "sourcetype": "idp:adapter",
  "index": "prod-idp",
  "event": {
    "timestamp": "2026-02-14T10:31:02.456789Z",
    "event": "adapter_call",
    "level": "INFO",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42,
    "platform": "aap",
    "details": {
      "method": "POST",
      "url": "https://aap.example.com/api/v2/job_templates/123/launch/",
      "status_code": 201,
      "response_time_ms": 342,
      "platform_job_id": "456",
      "request_payload": {
        "extra_vars": {"app_version": "1.2.3"}
      }
    },
    "source": "idp-portal"
  },
  "fields": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "john.doe@example.com",
    "execution_id": 42,
    "platform": "aap"
  }
}
```

### Splunk Search Queries Exemples

**Query 1 : Recherche par correlation_id (tracer une exécution complète)**

```spl
index="prod-idp" correlation_id="550e8400-e29b-41d4-a716-446655440000"
| sort timestamp
| table timestamp, event, level, user_id, execution_id, platform, details
```

**Résultat attendu :** Tous les événements liés à l'exécution 42 (execution_started, adapter_call, step_completed, execution_completed) triés chronologiquement.

**Query 2 : Recherche par user_id (actions d'un utilisateur sur 24h)**

```spl
index="prod-idp" user_id="john.doe@example.com" earliest=-24h
| stats count by event
| sort -count
```

**Résultat attendu :** Nombre d'événements par type (execution_started: 5, step_completed: 12, adapter_call: 8, etc.) pour john.doe sur les dernières 24h.

**Query 3 : Recherche par execution_id (logs complets d'une exécution)**

```spl
index="prod-idp" execution_id=42
| sort timestamp
| table timestamp, event, level, details.status, details.output
```

**Résultat attendu :** Timeline complète de l'exécution 42 avec statuts et outputs de chaque step.

**Query 4 : Erreurs par période (monitoring alertes)**

```spl
index="prod-idp" level=ERROR earliest=-7d
| timechart span=1h count by event
```

**Résultat attendu :** Graphique nombre d'erreurs par heure sur 7 jours, groupé par type événement (adapter_call_failed, execution_failed, vault_resolution_error, etc.).

### Project Structure Notes

**Alignement avec structure Django existante :**
- Adapters : `adapters/splunk_adapter.py` (pattern adapters existants AAP, Tower, Azure, GitHub, Terraform, Vault)
- Core services : `core/splunk_logging_handler.py` (à côté de core/logging.py, core/vault_service.py)
- Fixtures : `integrations/fixtures/splunk_integration_type.json` (pattern Story 27.7)
- Tests adapters : `adapters/tests/test_splunk_adapter.py` (pattern test_aap_adapter.py, test_terraform_cloud_adapter.py)
- Tests core : `core/tests/test_splunk_logging_handler.py` (pattern test_vault_service.py)
- Tests audit : `audit/tests/test_audit_correlation_id.py` (nouveau fichier)
- Tests frontend : `frontend/src/pages/AuditPage.test.tsx` (ou étendre existant)
- Docs : `docs/splunk-integration.md`, `docs/splunk-integration-failure-handling.md`, `docs/audit-correlation-id-search.md`

**Aucun conflit détecté avec structure existante**

### References

**Source principale :**
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 27, Story 27.8] (lines 4610-4633)
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 27 Overview] (lines 335-340)

**Stories précédentes (adapters backend) :**
- [Source: _bmad-output/implementation-artifacts/27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md] — AAPAdapter, BaseAdapter pattern, httpx, structlog, correlation_id
- [Source: _bmad-output/implementation-artifacts/27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md] — TowerAdapter
- [Source: _bmad-output/implementation-artifacts/27-3-adapter-azure-devops-pipelines-runs-monitoring.md] — AzureDevOpsAdapter
- [Source: _bmad-output/implementation-artifacts/27-4-adapter-github-actions-workflow-runs-monitoring.md] — GitHubActionsAdapter
- [Source: _bmad-output/implementation-artifacts/27-5-adapter-terraform-cloud-runs-monitoring.md] — TerraformCloudAdapter
- [Source: _bmad-output/implementation-artifacts/27-6-vault-service-hashicorp-vault-enterprise.md] — VaultService, credential_ref resolution

**Stories précédentes (catalogue frontend) :**
- [Source: _bmad-output/implementation-artifacts/27-7-admin-frontend-menu-integrations-adapters.md] — Catalogue IntegrationTypeCatalogue, fixtures consolidées, management command seed

**Fichiers backend existants :**
- [Source: idp-portal/django_backend/core/logging.py] — Configure structlog JSON, contextvars, TimeStamper, JSONRenderer
- [Source: idp-portal/django_backend/audit/views.py] — AuditExecutionsView, _build_audit_queryset, filtres, pagination, correlation_id retourné (ligne 235)
- [Source: idp-portal/django_backend/core/models.py] — AuditLog modèle avec champ correlation_id (ligne 224), get_details(), set_details()
- [Source: idp-portal/django_backend/adapters/base_adapter.py] — BaseAdapter abstrait, contrat trigger(), get_status(), get_job_logs(), cancel_execution()
- [Source: idp-portal/django_backend/adapters/aap_adapter.py] — Pattern adapter avec httpx, structlog logging, correlation_id (ligne 90-96)
- [Source: idp-portal/django_backend/core/vault_service.py] — VaultService credential_ref resolution pattern
- [Source: idp-portal/django_backend/integrations/fixtures/integration_type_catalogue.json] — Fixtures 7 types existants (Story 27.7)
- [Source: idp-portal/django_backend/integrations/management/commands/seed_integration_types.py] — Management command seed idempotent

**Fichiers frontend existants :**
- [Source: idp-portal/frontend/src/pages/AuditPage.tsx] (supposé) — Page Audit avec filtres, liste exécutions
- [Source: idp-portal/frontend/src/components/admin/IntegrationForm.tsx] (Story 27.7) — Pattern Select Type dynamique, Actions affichées

**Documentation externe :**
- [Source: Splunk HEC API Documentation] — HTTP Event Collector, endpoints, authentication, event format, batch mode
- [Source: structlog documentation] — contextvars.bind_contextvars, processors, JSONRenderer, custom handlers
