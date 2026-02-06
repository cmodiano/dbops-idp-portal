# Story 13.5 : API self-service standalone — déclencher une exécution sans frontend et la retrouver dans le portail

Status: ready-for-dev

## Story

As an application cliente (self-service via API),
I want pouvoir déclencher une action via l'API backend sans interface graphique (script, CI/CD, outil interne),
So that j'automatise des actions en libre service et je retrouve ensuite l'exécution dans le portail (historique, timeline, audit).

## Acceptance Criteria

### AC1 — Authentification par jeton Bearer (API standalone)
**Given** un client dispose d'un jeton d'accès valide (Authorization: Bearer <token>) et des permissions nécessaires,
**When** il appelle `POST /api/v1/executions` avec `action_id`, `target_names` et `parameters`,
**Then** le backend accepte la requête sans dépendance au frontend (pas de cookie/session UI requise) et retourne `201` avec `execution_id` (statut initial "SUBMITTED") dans le wrapper `{ "data": ... }`.

### AC2 — Refus explicite pour targets non autorisés ou payload invalide
**Given** une requête API tente de déclencher une exécution sur un target non autorisé (env + pattern/liste) ou inconnu,
**When** le backend valide la soumission,
**Then** il refuse explicitement (`403` si non autorisé, `404`/`422` si target inexistant ou payload invalide) avec un message d'erreur clair dans `{ "error": ... }`.

### AC3 — Visibilité portail des exécutions API
**Given** une exécution est créée via l'API,
**When** l'utilisateur ouvre le portail,
**Then** l'exécution apparaît dans l'historique (page Exécutions) et la page détail / timeline affiche le même état que pour une exécution déclenchée via le wizard, y compris les mises à jour temps réel.

### AC4 — Traçabilité audit SOC1 pour exécutions API
**And** l'audit enregistre l'identité issue du jeton (qui) + action + targets + environnement dérivé du target + paramètres (quoi) + horodatage (quand), de manière identique aux exécutions déclenchées via UI.

## Tasks / Subtasks

### Task 1 : Analyse de l'authentification JWT existante (AC: 1)

- [ ] **Subtask 1.1** — Vérifier que `JWTAuthentication` dans `core/auth_middleware.py` supporte les tokens Bearer sans cookie de session
  - Localiser `JWTAuthentication` et valider le flow sans session/cookie
  - Confirmer que `Authorization: Bearer <token>` est suffisant
- [ ] **Subtask 1.2** — Tester que l'endpoint POST /executions accepte uniquement le header Authorization (pas de CSRF pour API)
  - Vérifier la configuration CSRF exemption sur les endpoints API
  - Tester avec curl/httpie sans cookie
- [ ] **Subtask 1.3** — Documenter le flow d'obtention de token pour les clients API
  - Vérifier si un endpoint `/api/v1/auth/token` existe ou doit être créé
  - Si SAML-only : documenter le flow de génération de token machine-to-machine

### Task 2 : Validation et documentation du endpoint POST /executions existant (AC: 1,2)

- [ ] **Subtask 2.1** — Vérifier que le code actuel dans `executions/views.py:ExecutionsView.post()` gère correctement tous les cas d'erreur API
  - 400 Bad Request : payload invalide, target_names manquant, environments mixtes
  - 403 Forbidden : target non autorisé (RBAC)
  - 404 Not Found : action_id inexistant
  - 201 Created : succès
- [ ] **Subtask 2.2** — Valider le format de réponse d'erreur conforme `{ "error": { "code": "...", "message": "...", "details": {...} } }`
  - Vérifier `core/exceptions.py` et les handlers globaux
  - S'assurer que tous les cas retournent le format standard
- [ ] **Subtask 2.3** — Ajouter validation explicite du content-type (application/json attendu)
  - Si absent ou invalide → 415 Unsupported Media Type

### Task 3 : Enrichissement de l'audit pour traçabilité API (AC: 4)

- [ ] **Subtask 3.1** — Vérifier que `AuditService.create_entry()` est appelé pour chaque exécution créée
  - Localiser dans `ExecutionService.create_execution()` ou `executions/views.py`
  - Confirmer les champs : user_id, action_type, entity_type, entity_id, details, correlation_id
- [ ] **Subtask 3.2** — Ajouter un champ `source` dans les details d'audit pour distinguer UI vs API
  - `"source": "api"` si requête sans Referer/Origin ou avec header spécifique
  - `"source": "ui"` si requête provient du frontend (Referer header)
- [ ] **Subtask 3.3** — Ajouter l'IP source dans les logs d'audit (déjà dans AuditService ?)
  - Vérifier `X-Forwarded-For` header handling
  - Ajouter `ip_address` dans les details si manquant

### Task 4 : Documentation API OpenAPI/Swagger (AC: 1,2)

- [ ] **Subtask 4.1** — Vérifier que les docstrings dans `executions/views.py` génèrent une documentation OpenAPI correcte
  - Décrire les paramètres : action_id (int, required), target_names (list[str], required pour requires_target), parameters (object, optional)
  - Décrire les réponses : 201, 400, 403, 404
- [ ] **Subtask 4.2** — Créer un exemple de requête curl dans la documentation
  - Inclure l'obtention du token
  - Inclure l'appel POST /executions avec payload JSON

### Task 5 : Tests d'intégration API standalone (AC: 1,2,3,4)

- [ ] **Subtask 5.1** — Test `test_api_execution_with_bearer_token` : POST /executions avec Authorization Bearer → 201
  - Mock du token JWT valide
  - Vérifier execution_id dans la réponse
- [ ] **Subtask 5.2** — Test `test_api_execution_without_auth` : POST /executions sans header → 401
- [ ] **Subtask 5.3** — Test `test_api_execution_invalid_token` : POST /executions avec token expiré → 401
- [ ] **Subtask 5.4** — Test `test_api_execution_forbidden_target` : POST /executions avec target non autorisé → 403
- [ ] **Subtask 5.5** — Test `test_api_execution_invalid_payload` : POST /executions avec payload invalide → 400
- [ ] **Subtask 5.6** — Test `test_api_execution_action_not_found` : POST /executions avec action_id inexistant → 404
- [ ] **Subtask 5.7** — Test `test_api_execution_visible_in_portal` : Vérifier que l'exécution créée via API apparaît dans GET /executions
- [ ] **Subtask 5.8** — Test `test_api_execution_audit_logged` : Vérifier que l'audit contient source=api, ip_address, correlation_id

### Task 6 : Validation frontend — visibilité des exécutions API (AC: 3)

- [ ] **Subtask 6.1** — Vérifier que la page ExecutionsPage affiche les exécutions sans distinction de source
  - GET /executions retourne toutes les exécutions (scope=mine ou scope=all)
  - Pas de filtre sur source dans le frontend
- [ ] **Subtask 6.2** — Optionnel : Ajouter un indicateur visuel "API" pour les exécutions non-UI
  - Badge ou icône dans la colonne Source (si pertinent pour les DBA)
  - Filtre optionnel par source dans les filtres avancés

### Task 7 : Documentation utilisateur et exemples (AC: 1)

- [ ] **Subtask 7.1** — Créer un document `docs/api-self-service.md` avec exemples curl
- [ ] **Subtask 7.2** — Inclure un exemple Python avec requests
- [ ] **Subtask 7.3** — Documenter les erreurs courantes et leur résolution

## Dev Notes

### Architecture actuelle (post-Story 13.4)

**Authentification JWT** — Le système utilise déjà JWT pour l'authentification :
- `JWTAuthentication` dans `core/auth_middleware.py` ou équivalent
- Tokens générés après authentification SAML (flow UI)
- Le header `Authorization: Bearer <token>` est déjà supporté

**Endpoint POST /executions existant** — `executions/views.py:170-379` :
```python
def post(self, request):
    """
    Create a new execution.
    Story 13.2: Supports target_names parameter for target-based execution.
    Story 13.4: target_names is REQUIRED for actions with requires_target=True.
    """
    # ... validation et création
    return Response({"data": {...}}, status=201)
```

**Ce qui existe DÉJÀ** :
- Validation `action_id`, `target_names`, `environment` (Story 13.4)
- RBAC via `InventoryService.list_targets_for_user()` (Story 13.3)
- Audit via `AuditService.create_entry()` (Story 6.1)
- Format de réponse standardisé `{ "data": ... }` ou `{ "error": ... }`

**Ce qui DOIT être ajouté/validé** :
1. Vérifier que l'authentification JWT fonctionne sans cookie de session
2. Ajouter `source: "api" | "ui"` dans les logs d'audit
3. Tests d'intégration complets pour le flow API-only
4. Documentation pour les clients API

### Flow API standalone

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CLIENT API (script, CI/CD, outil interne)                                    │
│                                                                              │
│  1. Obtenir un token JWT :                                                   │
│     - Via SAML programmatique (service account) OU                           │
│     - Via endpoint /auth/token avec credentials machine OU                   │
│     - Token long-lived configuré par admin                                   │
│                                                                              │
│  2. Appeler POST /api/v1/executions :                                        │
│     curl -X POST https://portail/api/v1/executions \                         │
│       -H "Authorization: Bearer <token>" \                                   │
│       -H "Content-Type: application/json" \                                  │
│       -d '{"action_id": 42, "target_names": ["srv-dev-01"], "parameters": {...}}'
│                                                                              │
│  3. Réponse 201 :                                                            │
│     {"data": {"execution_id": 123, "status": "SUBMITTED", "created_at": "..."}}
│                                                                              │
│  4. Optionnel : suivre le statut via GET /api/v1/executions/123              │
└──────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼

┌──────────────────────────────────────────────────────────────────────────────┐
│ BACKEND DJANGO                                                                │
│                                                                              │
│  ExecutionsView.post()                                                       │
│    │                                                                         │
│    ├─ Valider JWT (JWTAuthentication)                                        │
│    ├─ Parser payload JSON                                                    │
│    ├─ Valider action_id, target_names (Story 13.4)                           │
│    ├─ Vérifier RBAC targets (InventoryService)                               │
│    ├─ Dériver environment du target                                          │
│    ├─ Créer Execution (ExecutionService)                                     │
│    ├─ Logger audit (AuditService) avec source="api"                          │
│    └─ Retourner 201 + execution_id                                           │
└──────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼

┌──────────────────────────────────────────────────────────────────────────────┐
│ PORTAIL (frontend)                                                           │
│                                                                              │
│  Page Exécutions (ExecutionsPage)                                            │
│    - GET /api/v1/executions?scope=mine                                       │
│    - Affiche TOUTES les exécutions (UI + API)                                │
│    - Timeline identique pour toutes les sources                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Fichiers à analyser/modifier

| Fichier | Analyse/Modification | Priorité |
|---------|---------------------|----------|
| `core/auth_middleware.py` | Vérifier JWTAuthentication sans session | HAUTE |
| `core/settings.py` | Vérifier CSRF exemption pour API | HAUTE |
| `executions/views.py` | Ajouter source dans audit details | MOYENNE |
| `core/services.py` | Vérifier AuditService.create_entry() | MOYENNE |
| `executions/tests/test_story_13_5.py` | Nouveaux tests API standalone | HAUTE |
| `docs/api-self-service.md` | Nouvelle documentation | BASSE |

### Référence aux Stories précédentes

| Story | Implémentation | Réutilisable |
|-------|----------------|--------------|
| **13.1** | API `/api/v1/inventory/targets` + InventoryService | Oui |
| **13.2** | Validation POST /executions avec target_names | Oui — base du endpoint |
| **13.3** | RBAC filtrage par env + pattern/liste | Oui — utilisé dans validation |
| **13.4** | target_names REQUIRED, env dérivé du target | Oui — logique actuelle |

### Codes HTTP et format de réponse

| Code | Situation | Exemple response |
|------|-----------|------------------|
| 201 | Exécution créée | `{"data": {"execution_id": 123, "status": "SUBMITTED"}}` |
| 400 | Payload invalide | `{"error": {"code": "BAD_REQUEST", "message": "target_names requis"}}` |
| 401 | Token absent/invalide | `{"error": {"code": "UNAUTHORIZED", "message": "Token invalide"}}` |
| 403 | Target non autorisé | `{"error": {"code": "FORBIDDEN", "message": "Cible non autorisée: srv-prod-01"}}` |
| 404 | Action inexistante | `{"error": {"code": "ACTION_NOT_FOUND", "message": "Action non trouvée"}}` |
| 415 | Content-Type invalide | `{"error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "application/json requis"}}` |

### Points d'attention

1. **CSRF** — Les endpoints API doivent être exemptés de CSRF pour permettre les appels machine-to-machine. Vérifier `CsrfExemptMixin` ou `@csrf_exempt`.

2. **Token machine-to-machine** — Si l'authentification est SAML-only, prévoir un mécanisme de génération de tokens pour les scripts/CI. Options :
   - Token long-lived (API key) avec permissions limitées
   - Service account SAML
   - Endpoint `/auth/token` avec client_id/secret

3. **Rate limiting** — Prévoir un rate limiting pour les appels API (optionnel MVP, mais recommandé).

4. **Correlation ID** — Le header `X-Idp-Request-Id` doit être supporté pour traçabilité. Si absent, en générer un.

### Dépendances techniques

| Composant | Version | Usage |
|-----------|---------|-------|
| Django REST Framework | 3.14+ | APIView, permissions |
| PyJWT | 2.x | Token JWT |
| structlog | 25.x | Logging structuré |
| python-oracledb | 3.4+ | Accès Oracle |

### Exemple de requête API

```bash
# 1. Obtenir un token (à adapter selon le mécanisme d'auth)
# Option A: Token depuis SAML (flow existant via UI)
# Option B: Token depuis /auth/token (si implémenté)

# 2. Déclencher une exécution
curl -X POST https://portail.example.com/api/v1/executions \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -H "X-Idp-Request-Id: $(uuidgen)" \
  -d '{
    "action_id": 42,
    "target_names": ["srv-dev-oracle-01", "srv-dev-oracle-02"],
    "parameters": {
      "database_name": "TESTDB",
      "operation": "backup"
    }
  }'

# Réponse attendue (201):
# {
#   "data": {
#     "execution_id": 123,
#     "status": "SUBMITTED",
#     "created_at": "2026-02-05T14:30:00Z"
#   }
# }

# 3. Suivre le statut
curl -X GET https://portail.example.com/api/v1/executions/123 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Project Structure Notes

- L'endpoint POST /executions existe déjà dans `executions/views.py`
- L'authentification JWT est gérée par `core/auth_middleware.py`
- Les tests doivent être ajoutés dans `executions/tests/test_story_13_5.py`
- La documentation API sera dans `docs/api-self-service.md`

### References

- [Source: executions/views.py#ExecutionsView.post()] — Endpoint POST /executions
- [Source: core/auth_middleware.py] — Authentification JWT
- [Source: core/services.py#AuditService] — Service d'audit
- [Source: inventory/services.py#InventoryService] — Service inventaire RBAC
- [Source: _bmad-output/planning-artifacts/epics.md#Story 13.5] — Critères d'acceptation

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

- 2026-02-05: Story 13.5 créée — analyse exhaustive du contexte, 7 tasks définies

### File List

