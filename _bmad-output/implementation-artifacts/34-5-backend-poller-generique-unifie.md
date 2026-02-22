# Story 34.5 : Backend — Poller générique unifié

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-BE-3 -->

## Story

En tant que mainteneur,
je veux unifier les 5 tâches Celery de polling quasi-identiques en une seule tâche générique `poll_platform_job_status` qui délègue à l'`AdapterRegistry` existant,
afin de respecter OCP (1054 → ~250 lignes), d'éliminer ~700 lignes de code dupliqué, et de permettre l'ajout d'une nouvelle plateforme sans aucune modification de `polling.py`.

## Contexte

**SOLID-BE-3** : `executions/tasks/polling.py` (1054 lignes) contient 5 tâches Celery quasi-identiques (`poll_aap_job_status`, `poll_tower_job_status`, `poll_azure_devops_run_status`, `poll_github_actions_run_status`, `poll_terraform_cloud_run_status`). Chacune duplique ~150 lignes de logique identique : construction adapter, `get_status()`, `get_job_logs()`, `_broadcast_execution_update()`, `_update_execution_from_poll()`, rescheduling, gestion des retries. Pour ajouter Jenkins, il faudrait ajouter une 6e fonction de 150 lignes — violation OCP directe.

**Fix :** Une seule tâche générique `poll_platform_job_status` délègue à l'`AdapterRegistry` existant (`adapters/registry.py`, Story 33.1). Les 5 tâches deviennent des shims backward-compat de ≤ 15 lignes.

## Acceptance Criteria

1. **Given** un job doit être surveillé sur n'importe quelle plateforme
   **When** la tâche de polling est lancée
   **Then** une seule tâche Celery `poll_platform_job_status` (name: `executions.tasks.poll_platform_job_status`) construit l'adapter via `get_platform_adapter()` et interroge `get_status()` + `get_job_logs()` — aucun `if/elif` sur `platform_type` dans la logique de polling.

2. **And** la détection de statut terminal est unifiée via `logs_data.get("complete", False)` — le contrat `BaseAdapter.get_job_logs()` garantit le champ `complete: bool` pour tous les adapters existants.

3. **And** les 5 tâches existantes sont conservées comme shims backward-compatibles (noms Celery inchangés) ; chaque shim traduit ses paramètres spécifiques et délègue directement à la fonction `poll_platform_job_status(...)` ; leur corps est ≤ 15 lignes.

4. **And** pour ajouter une nouvelle plateforme, il suffit de :
   a. Enregistrer l'adapter dans `adapters/__init__.py` (déjà fait pour les 5 existants)
   b. Appeler `poll_platform_job_status` avec `platform_type=<nouveau>` — aucune modification de `polling.py` requise (OCP).

5. **And** les tests existants (`test_polling_max_retries.py`, `test_aap_monitoring.py`, `test_tower_monitoring.py`, `test_azure_devops_monitoring.py`) passent sans régression. Au moins 3 nouveaux tests couvrent `poll_platform_job_status`.

6. **And** `poll_platform_job_status` est exporté dans `executions/tasks/__init__.py` et `__all__`.

## Tasks / Subtasks

- [x] Task 1 — Créer `poll_platform_job_status` dans `polling.py` (AC: #1, #2, #4)
  - [x] 1.1 Ajouter la tâche Celery générique avec signature :
        ```python
        @shared_task(bind=True, max_retries=0, name="executions.tasks.poll_platform_job_status")
        def poll_platform_job_status(
            self: Any,
            execution_id: int,
            platform_job_id: str,
            platform_type: str,
            base_url: str = "",
            credential_ref: str = "",
            auth_flow: str = "token",
            poll_interval: int = 5,
            retry_count: int = 0,
            adapter_kwargs: dict | None = None,
            poll_kwargs: dict | None = None,
        ) -> dict:
        ```
  - [x] 1.2 Construire l'adapter : `from adapters import get_platform_adapter` + `from adapters.utils import build_auth_headers_from_credentials` (imports lazy `# noqa: PLC0415`)
  - [x] 1.3 Appeler `asyncio.run(adapter.get_status(platform_job_id=platform_job_id, correlation_id=correlation_id, **(poll_kwargs or {})))` et idem pour `get_job_logs`
  - [x] 1.4 Détecter `is_terminal = logs_data.get("complete", False)` — NE PAS reproduire la logique d'inspection `aap_status`, `azure_devops_state`, etc.
  - [x] 1.5 Conserver la même structure error/retry/reschedule que les tâches existantes (Story 30.7 RACE-1) : `retry_count >= MAX_POLLING_RETRIES` → `_tasks._mark_execution_polling_exhausted()` ; sinon reschedule `retry_count+1`
  - [x] 1.6 Re-schedule via `poll_platform_job_status.apply_async(args=[execution_id, platform_job_id, platform_type], kwargs={...}, countdown=poll_interval)`
  - [x] 1.7 Ajouter `import executions.tasks as _tasks` en tête de corps (pattern existant pour patchability)

- [x] Task 2 — Refactoriser les 5 tâches existantes en shims (AC: #3)
  - [x] 2.1 `poll_aap_job_status` : conserver `@shared_task(... name="executions.tasks.poll_aap_job_status")` + signature inchangée ; corps : `return poll_platform_job_status(execution_id=..., platform_type="aap", adapter_kwargs={"ssl_verify": ssl_verify, "ca_bundle_path": ca_bundle_path}, poll_kwargs={"resource_type": resource_type}, ...)`
  - [x] 2.2 `poll_tower_job_status` : `platform_type="tower"`, `poll_kwargs={"resource_type": resource_type}`, `adapter_kwargs={}`
  - [x] 2.3 `poll_azure_devops_run_status` : `platform_type="azure_devops"`, `poll_kwargs={"pipeline_id": pipeline_id}`, `adapter_kwargs={}`
  - [x] 2.4 `poll_github_actions_run_status` : `platform_type="github_actions"`, `adapter_kwargs={"owner": owner, "repo": repo}`, `poll_kwargs={}`
  - [x] 2.5 `poll_terraform_cloud_run_status` : `platform_type="terraform_cloud"`, `adapter_kwargs={"organization": organization}`, `poll_kwargs={}`
  - [x] 2.6 Les shims appellent `poll_platform_job_status(...)` directement (appel Python synchrone dans le même worker), PAS via `.apply_async()`. Voir Dev Notes sur le comportement de re-schedule.

- [x] Task 3 — Mettre à jour `executions/tasks/__init__.py` (AC: #6)
  - [x] 3.1 Ajouter `poll_platform_job_status` à l'import depuis `executions.tasks.polling`
  - [x] 3.2 Ajouter `"poll_platform_job_status"` à `__all__`

- [x] Task 4 — Tests (AC: #5)
  - [x] 4.1 Créer `executions/tests/test_generic_poller.py`
  - [x] 4.2 **Test terminal** : `poll_platform_job_status` avec `platform_type="aap"`, adapter mock retourne `logs_data={"complete": True, "content": ""}` et `status_data={"status": "COMPLETED"}` → résultat `{"outcome": "complete"}`
  - [x] 4.3 **Test non-terminal** : adapter mock retourne `logs_data={"complete": False}`, `status_data={"status": "RUNNING"}` → `poll_platform_job_status.apply_async` appelé avec `retry_count=0`
  - [x] 4.4 **Test épuisement** : adapter lève `Exception`, `retry_count=MAX_POLLING_RETRIES` → `{"outcome": "exhausted"}`, `_mark_execution_polling_exhausted` appelé
  - [x] 4.5 Exécuter : `.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py` → 0 nouvelle régression

## Dev Notes

### ⚠️ SOLID-BE-3 — Analyse structurelle du code actuel

**`executions/tasks/polling.py`** (1054 lignes) — pattern répété 5 fois :

```
# Chaque tâche (~150 lignes) :
1. import asyncio + import executions.tasks as _tasks
2. correlation_id = _tasks.get_correlation_id()
3. logger.info("poll_XXX_start", ...)
4. try:
     build_adapter (import lazy spécifique + construction)
     status_data = asyncio.run(adapter.get_status(..., **specific_kwargs))
     logs_data = asyncio.run(adapter.get_job_logs(..., **specific_kwargs))
5. except Exception:
     if retry_count >= MAX_POLLING_RETRIES: exhausted
     else: reschedule(retry_count+1)
6. is_terminal = LOGIQUE_SPÉCIFIQUE(status_data)  ← seule vraie différence
7. _tasks._broadcast_execution_update(...)
8. _tasks._update_execution_from_poll(...)
9. if is_terminal: return complete
10. reschedule(retry_count=0)
```

**La seule vraie différence** : la détection `is_terminal`. Mais `BaseAdapter.get_job_logs()` retourne déjà `complete: bool` (documenté dans `base_adapter.py:68-86` et implémenté dans tous les adapters).

### ⚠️ Contrat BaseAdapter.get_job_logs() — clé de l'unification

```python
# base_adapter.py — retour garanti pour get_job_logs() :
# - content: str
# - format: str
# - timestamp: str
# - complete: bool  ← True if execution is in terminal state  ← USE THIS
# - job_status: str
```

Vérification adapters existants :
- `aap_adapter.py:361-362` : `is_complete = aap_status in terminal_statuses` → `"complete": bool(is_complete)` ✓
- `tower_adapter.py:343-344` : même pattern ✓
- `azure_devops_adapter.py:527` : `is_complete = state == "completed" and result in AZURE_DEVOPS_TERMINAL_RESULTS` ✓
- `github_actions_adapter.py:570` : `is_complete = gh_status == "completed" and gh_conclusion in TERMINAL_CONCLUSIONS` ✓
- `terraform_cloud_adapter.py:505` : `is_complete = tc_status in TERRAFORM_CLOUD_TERMINAL_STATUSES` ✓

### ⚠️ Mapping paramètres shims → tâche générique

| Shim | platform_type | adapter_kwargs | poll_kwargs | auth_flow |
|------|--------------|----------------|-------------|-----------|
| poll_aap | `"aap"` | `{"ssl_verify": ssl_verify, "ca_bundle_path": ca_bundle_path}` | `{"resource_type": resource_type}` | tel quel |
| poll_tower | `"tower"` | `{}` | `{"resource_type": resource_type}` | tel quel |
| poll_azure | `"azure_devops"` | `{}` | `{"pipeline_id": pipeline_id}` | tel quel (default "basic") |
| poll_github | `"github_actions"` | `{"owner": owner, "repo": repo}` | `{}` | `"token"` (déjà Bearer direct) |
| poll_terraform | `"terraform_cloud"` | `{"organization": organization}` | `{}` | `"token"` (déjà Bearer direct) |

### ⚠️ get_platform_adapter() — API existante à utiliser (`adapters/__init__.py`)

```python
# adapters/__init__.py — API publique
def get_platform_adapter(
    platform_type: str,      # 'aap', 'tower', 'azure_devops', 'github_actions', 'terraform_cloud'
    base_url: str,
    auth_headers: dict[str, str],
    timeout: float | None = None,
    **platform_kwargs,       # owner, repo, organization, ssl_verify, ca_bundle_path...
) -> BaseAdapter:
```

Usage dans `poll_platform_job_status` :
```python
from adapters import get_platform_adapter                        # noqa: PLC0415
from adapters.utils import build_auth_headers_from_credentials   # noqa: PLC0415

auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
adapter = get_platform_adapter(
    platform_type=platform_type,
    base_url=base_url,
    auth_headers=auth_headers,
    **(adapter_kwargs or {}),
)
```

### ⚠️ build_auth_headers_from_credentials — comportement exact

```python
# adapters/utils.py:77-98
def build_auth_headers_from_credentials(credential_ref: str, auth_flow: str = "token") -> dict[str, str]:
    # "basic" → Basic <base64(credential_ref)>
    # "token" / "pat" / autre → {"Authorization": "Bearer <credential_ref>"}
```

GitHub/Terraform utilisent actuellement `{"Authorization": f"Bearer {credential_ref}"}` directement — équivalent exact de `build_auth_headers_from_credentials(credential_ref, "token")`. `auth_flow` transmis tel quel depuis le shim. ✓

### ⚠️ Comportement de re-schedule (backward compat)

Les shims appellent `poll_platform_job_status(...)` directement (synchrone Python). La tâche générique se re-schedule elle-même via `poll_platform_job_status.apply_async(...)`. Donc :
- 1ère invocation via queue : `executions.tasks.poll_aap_job_status` → shim → générique (synchrone)
- Re-schedules suivants : `executions.tasks.poll_platform_job_status` directement

Les tâches déjà en file Redis avec noms `poll_aap_job_status` etc. fonctionnent via le shim une fois, puis basculent sur le générique. ✓

### ⚠️ Impact sur les tests existants

`test_polling_max_retries.py` patches :
- `executions.tasks._mark_execution_polling_exhausted` → toujours dans la tâche générique ✓
- `executions.tasks.poll_aap_job_status.apply_async` → le shim ne reschedule plus directement (`apply_async` se fait dans le générique sous `poll_platform_job_status.apply_async`) → ⚠️ **les patches `poll_aap_job_status.apply_async` ne seront plus déclenchés**

**Conséquence** : les tests `test_reschedule_with_incremented_retry` et `test_successful_poll_resets_retry_count` dans `test_polling_max_retries.py` patchent `executions.tasks.poll_aap_job_status.apply_async` — ce patch ne capturera plus le re-schedule (qui se fait via `poll_platform_job_status.apply_async`). **Ces tests devront être mis à jour** pour patcher `executions.tasks.poll_platform_job_status.apply_async` à la place. Vérifier et adapter si nécessaire.

Les tests d'exhaustion (`test_exhaustion_on_adapter_error`) ne testent que `_mark_execution_polling_exhausted` → non impacté ✓

### ⚠️ Contexte stories précédentes

**Story 34.4** (feat(34-4)) — RuntimeRegistry établi :
- Pattern OCP registry → dispatch → pas de if/elif : même philosophie pour le poller générique
- `threading.Lock` sur les mutations de registry : non nécessaire ici (polling.py est un module, pas un registry mutable)

**Story 33.1** — AdapterRegistry établi :
- `adapters/registry.py` : `AdapterRegistry` avec `register/get/list_types`
- `adapters/__init__.py` : 5 factories enregistrées, `get_platform_adapter()` exposé et testé

**Story 30.7** (RACE-1) — MAX_POLLING_RETRIES établi :
- `MAX_POLLING_RETRIES = 20` dans `polling.py:30` — conserver, ne pas déplacer
- `_mark_execution_polling_exhausted()` — helper inchangé dans `polling.py`
- Logique retry : erreur + `retry_count >= MAX_POLLING_RETRIES` → exhausted ; sinon reschedule `retry_count+1` ; après succès non-terminal : reschedule `retry_count=0`

**Story 34.3** (feat(34-3)) — Pattern import lazy établi :
- `# noqa: PLC0415` pour les imports lazy à l'intérieur des fonctions

### Project Structure Notes

```
idp-portal/django_backend/
  executions/
    tasks/
      polling.py               ← MODIFIER : ajouter poll_platform_job_status + refactoriser shims
      __init__.py              ← MODIFIER : export poll_platform_job_status
    tests/
      test_generic_poller.py   ← CRÉER : 3+ tests pour poll_platform_job_status
      test_polling_max_retries.py  ← MODIFIER si besoin (patches apply_async)
  adapters/
    __init__.py                ← LIRE SEULEMENT
    base_adapter.py            ← LIRE SEULEMENT (contrat complete: bool)
    utils.py                   ← LIRE SEULEMENT
```

Aucune migration DB. Aucun impact API REST.

### Commandes de test recommandées

```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Vérification import
.venv/bin/python -c "from executions.tasks import poll_platform_job_status; print('OK:', poll_platform_job_status.name)"

# Tests nouveaux
.venv/bin/python -m pytest executions/tests/test_generic_poller.py -v

# Suite complète périmètre
.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py
```

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-3] — 5 tâches dupliquées, fix recommandé : poll_platform_job_status
- [Source: django_backend/executions/tasks/polling.py:1-1054] — code actuel complet
- [Source: django_backend/adapters/__init__.py] — get_platform_adapter() + factories
- [Source: django_backend/adapters/base_adapter.py:68-86] — contrat BaseAdapter.get_job_logs() : `complete: bool`
- [Source: django_backend/adapters/utils.py:77] — build_auth_headers_from_credentials(credential_ref, auth_flow)
- [Source: django_backend/executions/tasks/__init__.py] — exports à mettre à jour
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.5]
- [Source: _bmad-output/implementation-artifacts/34-4-backend-runtime-registry-webhooks-di.md] — pattern OCP registry établi

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_Aucun debug log requis — implémentation directe sans blocage._

### Completion Notes List

- **OCP atteint** : `polling.py` réduit de 1054 → ~390 lignes (-63%). Pour ajouter une 6e plateforme, aucune modification de `polling.py` n'est requise.
- **Unification `is_terminal`** : tous les adapters utilisent désormais `logs_data.get("complete", False)` via le contrat `BaseAdapter.get_job_logs()`, éliminant 5 blocs d'inspection de statuts spécifiques à chaque plateforme.
- **Backward compat** : les 5 noms de tâches Celery (`poll_aap_job_status`, etc.) sont conservés comme shims ≤15 lignes qui délèguent à `poll_platform_job_status`. Les jobs en file Redis avec anciens noms fonctionnent via le shim une première fois, puis basculent sur le générique.
- **Tests mis à jour** : `test_polling_max_retries.py` et les 3 fichiers de tests monitoring patchent désormais `poll_platform_job_status.apply_async` (point de re-schedule réel) — 0 nouvelle régression.
- **9 nouveaux tests** dans `test_generic_poller.py` couvrent : terminal, plateforme-agnostique, non-terminal, épuisement, incrément retry, nom tâche, export `__init__`, présence `__all__`, délégation shim.
- **Résultat final** : 9 + 22 + 38 = 69 tests dans le périmètre, tous verts. Pré-existants confirmés non liés à Story 34.5.
- **Code review (2026-02-22)** : 3 issues MEDIUM + 2 LOW corrigés automatiquement. Voir section Senior Developer Review.

### File List

- `idp-portal/django_backend/executions/tasks/polling.py` — MODIFIÉ : ajout `poll_platform_job_status` + refactorisation des 5 tâches en shims
- `idp-portal/django_backend/executions/tasks/__init__.py` — MODIFIÉ : export `poll_platform_job_status` + ajout à `__all__`
- `idp-portal/django_backend/executions/tests/test_generic_poller.py` — CRÉÉ : 11 tests pour `poll_platform_job_status` (2 ajoutés lors du code review : shims GitHub Actions et Terraform Cloud)
- `idp-portal/django_backend/executions/tests/test_polling_max_retries.py` — MODIFIÉ : patches mis à jour vers `poll_platform_job_status.apply_async` ; patch mort `TERRAFORM_CLOUD_TERMINAL_STATUSES` supprimé (code review)
- `idp-portal/django_backend/executions/tests/test_aap_monitoring.py` — MODIFIÉ : patches + assertions statuts spécifiques supprimés
- `idp-portal/django_backend/executions/tests/test_tower_monitoring.py` — MODIFIÉ : patches + assertions statuts spécifiques supprimés
- `idp-portal/django_backend/executions/tests/test_azure_devops_monitoring.py` — MODIFIÉ : patches + assertions statuts spécifiques supprimés

## Senior Developer Review (AI)

**Date :** 2026-02-22 | **Statut :** ✅ APPROUVÉ après corrections

### Résultats du review

| Sévérité | Nb | Statut |
|----------|-----|--------|
| 🔴 HIGH | 0 | — |
| 🟡 MEDIUM | 3 | ✅ Auto-corrigés |
| 🟢 LOW | 2 | ✅ L2 corrigé ; L1 documenté |

### Issues corrigés

**[M1] `polling.py:219` — Clé `"aap_logs"` dans helper générique** *(MEDIUM)*
`_update_execution_from_poll` stockait les logs de toutes les plateformes sous la clé `"aap_logs"`. Renommé en `"platform_logs"` — Tower, Azure DevOps, GitHub Actions et Terraform Cloud utilisent désormais la clé correcte.

**[M2] `polling.py:202,225,232` — Noms d'événements structlog `poll_aap_*`** *(MEDIUM)*
Les événements `poll_aap_status_transition_invalid`, `poll_aap_execution_not_found`, `poll_aap_update_error` du helper générique renommés en `poll_status_transition_invalid`, `poll_execution_not_found`, `poll_update_error` pour éviter les traces trompeuses pour 4/5 plateformes.

**[M3] `test_generic_poller.py` — Shims GitHub Actions et Terraform Cloud non testés** *(MEDIUM)*
2 nouvelles classes de tests ajoutées : `TestPollGitHubActionsShimDelegates` et `TestPollTerraformCloudShimDelegates`. Vérifient le mapping correct de `owner`/`repo` et `organization` dans `adapter_kwargs`.

**[L2] `test_polling_max_retries.py:222` — Patch mort sur `TERRAFORM_CLOUD_TERMINAL_STATUSES`** *(LOW)*
Patch désormais inutile après refactorisation vers le poller générique (qui n'inspecte plus cette constante). Supprimé.

### Issues documentés (non corrigés)

**[L1] `polling.py:132,163` — `"aap_status"` dans messages WebSocket broadcast** *(LOW)*
`_broadcast_execution_update` hardcode `"aap_status": status_data.get("aap_status")` dans les messages WebSocket. Pour Tower/Azure/GitHub/Terraform, ce champ sera `null`. Non corrigé : changement de schéma WebSocket nécessitant coordination frontend.

### Résultat final

- 71 tests dans le périmètre, tous verts (69 originaux + 2 nouveaux)
- 0 régression

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-22 | 1.0 | Implémentation initiale — `poll_platform_job_status` générique + 5 shims + 9 tests | claude-sonnet-4-6 |
| 2026-02-22 | 1.1 | Code review — 3 MEDIUM + 1 LOW corrigés : `platform_logs`, logs génériques, tests shims GitHub/Terraform, patch mort supprimé | claude-sonnet-4-6 |
