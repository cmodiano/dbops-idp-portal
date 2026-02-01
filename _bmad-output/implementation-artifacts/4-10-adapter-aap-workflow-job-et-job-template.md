# Story 4.10 : Adapter AAP — Support workflow job et job template (resource_type par action)

Status: done

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **DBOPS**,
je veux **pouvoir lancer et suivre à la fois des job templates et des workflow jobs sur AAP**,
afin que **le portail supporte les deux types de ressources AAP sans dupliquer les intégrations**.

## Acceptance Criteria

1. **AC1 — resource_type au niveau action/catalogue**
   **Given** une action est configurée pour appeler AAP,
   **When** les paramètres d'exécution sont définis,
   **Then** un paramètre (ex. `aap_resource_type` ou `resource_type`) indique `job_template` ou `workflow_job` ; ce paramètre est passé au moteur d'exécution et à l'adapter AAP.

2. **AC2 — Adapter AAP : chemins selon resource_type**
   **Given** l'adapter AAP reçoit un trigger avec un paramètre resource_type et un identifiant (template_id ou workflow_id),
   **When** resource_type est `job_template`,
   **Then** trigger utilise `POST /api/v2/job_templates/{id}/launch/` et get_status utilise `GET /api/v2/jobs/{id}/` (comportement actuel).
   **When** resource_type est `workflow_job`,
   **Then** trigger utilise `POST /api/v2/workflow_job_templates/{id}/launch/` (ou équivalent AAP) et get_status utilise `GET /api/v2/workflow_jobs/{id}/` (ou équivalent).

3. **AC3 — Rétrocompatibilité**
   **And** si resource_type est absent, le comportement par défaut reste job_template (comportement actuel).

4. **AC4 — Catalogue / UI**
   **And** lors de la configuration d'une action qui cible AAP, l'utilisateur peut choisir le type de ressource (job template ou workflow job) ; la valeur est persistée et utilisée à l'exécution.

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 4) — Modèle et catalogue
  - [x] 1.1 : Définir où stocker resource_type (paramètre d'action ou champ dédié dans le catalogue/execution step) ; aligner avec le modèle d'action existant.
  - [x] 1.2 : Exposer resource_type dans l'API d'exécution (paramètres envoyés à l'adapter).

- [x] Task 2 (AC: 2, 3) — Adapter AAP
  - [x] 2.1 : Dans AAPAdapter.trigger(), lire resource_type (et l'id template/workflow) ; construire l'URL de launch selon job_template vs workflow_job (vérifier la doc AAP pour les chemins exacts).
  - [x] 2.2 : Dans AAPAdapter.get_status(), utiliser le bon endpoint (/jobs/ vs /workflow_jobs/) selon le type de job lancé (peut être déduit du trigger ou stocké avec platform_job_id).
  - [x] 2.3 : Si resource_type absent, garder le comportement actuel (job_template).

- [x] Task 3 (AC: 4) — Frontend
  - [x] 3.1 : Dans le wizard ou la config d'action pour AAP, ajouter le choix « Job template » / « Workflow job » et persister la valeur.

- [x] Task 4 — Tests
  - [x] 4.1 : Tests unitaires adapter : trigger + get_status pour job_template (existant) et pour workflow_job (nouveau).
  - [x] 4.2 : Vérifier la non-régression des exécutions job template existantes.

---

## Dev Notes

- **AAP API** : Vérifier la documentation Red Hat AAP pour les endpoints exacts (workflow_job_templates, workflow_jobs) et le format de réponse (mapping de statuts identique ou à adapter).
- **Réutilisation** : app/adapters/aap_adapter.py ; execution_service et paramètres d'action dans le catalogue.

---

## Developer Context (guardrails)

### Contexte métier

- L'adapter AAP actuel (Story 4.4) ne supporte que les **job templates** : `POST /api/v2/job_templates/{id}/launch/` et `GET /api/v2/jobs/{id}/`.
- Les **workflow jobs** AAP utilisent des endpoints distincts : `POST /api/v2/workflow_job_templates/{id}/launch/` et `GET /api/v2/workflow_jobs/{id}/`.
- La distinction doit être **portée par l'action/catalogue** (type de ressource choisi par DBOPS), pas par une deuxième intégration AAP.
- FR18 (routage vers la bonne plateforme) et FR23 (callbacks asynchrones) restent couverts ; on étend uniquement le type de ressource AAP.

### Flux actuel à préserver

- `ExecutionService._execute_platform_step()` récupère `action_info` (action + intégration), appelle `adapter.trigger(parameters, credentials, correlation_id)` avec `execution.parameters`.
- L'adapter AAP attend aujourd'hui `parameters["job_template_id"]` et optionnellement des `extra_vars` (tous les autres champs de parameters).
- Le `platform_job_id` retourné par `trigger()` est stocké en base et utilisé pour `get_status()` et pour les callbacks.

### Où placer resource_type

- **Option retenue** : dans `connector_config` de l'étape d'exécution (ExecutionStep) quand `connector_type == AAP`. Clé proposée : `resource_type` avec valeurs `job_template` | `workflow_job`. Clé pour l’ID : `job_template_id` (existant) ou `workflow_job_template_id` selon le type, ou une seule clé `template_id` + `resource_type`.
- Le moteur d’exécution doit **fusionner** les infos de l’étape (connector_config : resource_type, template_id) avec `execution.parameters` (extra_vars utilisateur) avant d’appeler `adapter.trigger(parameters, ...)`, afin que l’adapter reçoive toujours `resource_type` et l’id de template.
- **Rétrocompatibilité** : si `resource_type` est absent dans les paramètres envoyés à l’adapter, l’adapter se comporte comme aujourd’hui (job_template + job_template_id).

### Endpoints AAP (Ansible Automation Platform / Controller)

- **Job template** (actuel) :  
  - Launch : `POST {base_url}/api/v2/job_templates/{id}/launch/`  
  - Status : `GET {base_url}/api/v2/jobs/{id}/`
- **Workflow job** :  
  - Launch : `POST {base_url}/api/v2/workflow_job_templates/{id}/launch/`  
  - Status : `GET {base_url}/api/v2/workflow_jobs/{id}/`
- Vérifier en doc officielle AAP/Controller que le préfixe est bien `/api/v2/` (certaines doc mentionnent `/api/controller/v2/`).
- Les réponses (status, result_traceback, job_explanation, etc.) sont similaires ; réutiliser `_parse_job_response()` pour les deux si la structure le permet, sinon adapter le parsing pour workflow_jobs.

---

## Technical Requirements

- **Backend**
  - **AAPAdapter** (`app/adapters/aap_adapter.py`) :
    - Dans `trigger()` : lire `parameters.get("resource_type", "job_template")` et l’identifiant (ex. `job_template_id` ou `workflow_job_template_id` / `template_id`). Construire l’URL de launch et, si besoin, conserver le type pour `get_status()`.
    - Dans `get_status()` : savoir si le job est un job standard ou un workflow_job (soit passé en paramètre, soit déduit d’un état interne set dans `trigger()`). Appeler `GET /api/v2/jobs/{id}/` ou `GET /api/v2/workflow_jobs/{id}/` en conséquence.
    - Exclure `resource_type`, `job_template_id`, `workflow_job_template_id` (ou `template_id`) des `extra_vars` envoyés dans le body du launch.
  - **ExecutionService** (`app/services/execution_service.py`) : pour l’étape plateforme AAP, fusionner le `connector_config` de l’étape (resource_type, template id) avec `execution.parameters` avant d’appeler `adapter.trigger(parameters, ...)`.
  - **Catalogue / execution_steps** : permettre dans `connector_config` les clés `resource_type` (`job_template` | `workflow_job`) et `job_template_id` ou `workflow_job_template_id` (ou `template_id`). Validation Pydantic si modèle dédié.
- **Frontend**
  - Lors de la configuration d’une action avec étape AAP : champ ou select « Type de ressource » : Job template | Workflow job. Persister dans la définition de l’étape (connector_config).
- **Tests**
  - Tests unitaires AAPAdapter : trigger avec resource_type=job_template (comportement actuel), trigger avec resource_type=workflow_job (nouveaux appels HTTP mockés).
  - Tests get_status pour les deux types.
  - Test de non-régression : exécution existante avec job template sans resource_type reste inchangée.

---

## Architecture Compliance

- **Strategy Pattern** : ne pas dupliquer l’intégration AAP ; étendre `AAPAdapter` pour gérer les deux types de ressources (même adapter, chemins différents).
- **Repository / API** : pas de nouvelle table ; données dans le catalogue (execution_steps / connector_config) et éventuellement en lecture dans execution_repository si besoin.
- **snake_case** : `resource_type`, `job_template_id`, `workflow_job_template_id` dans JSON et code.
- **Errors** : réutiliser `PlatformError` avec codes existants (ex. `AAP_JOB_TEMPLATE_NOT_FOUND`) et ajouter si besoin `AAP_WORKFLOW_JOB_TEMPLATE_NOT_FOUND`, `AAP_WORKFLOW_JOB_NOT_FOUND`.
- **Logging** : structlog avec correlation_id ; événements distincts pour workflow_job si utile (ex. `aap_workflow_trigger_started`).

---

## Library / Framework Requirements

- **AAP (Ansible Automation Platform) REST API v2** : pas de SDK obligatoire ; appels HTTP via `httpx` (déjà utilisé dans l’adapter). Vérifier la doc Red Hat / Ansible Controller pour les chemins exacts et le format des réponses workflow_jobs.
- **httpx** : conserver timeout 30s et gestion TimeoutException / ConnectError / HTTPStatusError comme dans l’adapter actuel.

---

## File Structure Requirements

- **Modifier (pas dupliquer)** :
  - `idp-portal/backend/app/adapters/aap_adapter.py` : trigger() et get_status() selon resource_type.
  - `idp-portal/backend/app/services/execution_service.py` : construction des paramètres pour l’étape AAP (fusion connector_config + execution.parameters).
- **Modèles / API** :
  - Si validation explicite : étendre le modèle ou schéma qui décrit `connector_config` (catalogue) pour inclure `resource_type` et les ids de template. Fichiers possibles : `app/models/catalog.py`, ou endroits où execution_steps sont validés.
- **Frontend** : formulaire de configuration d’action / étape AAP (ex. composant ou étape du wizard qui édite les execution_steps). Fichiers à identifier dans `idp-portal/frontend/src/` (ex. admin, wizard, ou config d’action).
- **Tests** :
  - `idp-portal/backend/tests/unit/test_aap_adapter.py` (ou équivalent) : scénarios job_template et workflow_job, et absence de resource_type.

---

## Testing Requirements

- **Unitaires (adapter)** :
  - Trigger avec resource_type=job_template et job_template_id → appelle POST job_templates/{id}/launch/, retourne job id.
  - Trigger avec resource_type=workflow_job et workflow_job_template_id (ou template_id) → appelle POST workflow_job_templates/{id}/launch/, retourne workflow job id.
  - Trigger sans resource_type → comportement actuel (job_template).
  - get_status(platform_job_id) pour job standard → GET /jobs/{id}/.
  - get_status(platform_job_id) pour workflow job → GET /workflow_jobs/{id}/ (avec un moyen de distinguer, ex. flag ou type passé).
- **Non-régression** : une exécution existante (job template uniquement) continue de fonctionner sans changement de données.
- **ExecutionService** : test que les paramètres passés à l’adapter contiennent bien resource_type et le bon template id lorsqu’ils sont définis dans connector_config.

---

## Previous Story Intelligence (4.9 — Intégrations type libre, flow d’auth, upload icône)

- Story 4.9 a introduit le **type d’intégration libre** et **auth_flow** (token, basic, basic_then_token, pat). L’adapter AAP utilise déjà les credentials Vault (token ou basic) via `_get_auth_headers()`. Rien à changer côté auth pour 4.10.
- **connector_config** et les modèles d’intégration (type libre, auth_flow, icône) sont en place. Pour 4.10, on ajoute des clés **spécifiques AAP** dans connector_config (resource_type, template id) sans casser les intégrations existantes.
- Fichiers modifiés en 4.9 : migrations Flyway, `integration_repository`, modèles Pydantic intégration, endpoint upload icône, frontend formulaire intégrations. Ne pas dupliquer ; réutiliser le pattern connector_config pour l’étape d’exécution côté catalogue.

---

## Latest Technical Information (AAP workflow jobs)

- **Ansible Automation Platform / Controller API v2** :
  - Workflow job templates : `POST /api/v2/workflow_job_templates/{id}/launch/` pour lancer, `GET /api/v2/workflow_jobs/{id}/` pour le statut.
  - Les réponses workflow job sont proches des job standards (status, result_traceback, etc.) ; vérifier la doc pour d’éventuels champs spécifiques (ex. noms de champs légèrement différents).
- Consulter la doc officielle Red Hat AAP / Ansible Controller pour la version déployée (ex. 4.5) afin de confirmer les chemins et les codes de statut.

---

## Project Context Reference

- **Epic** : Epic 4 — Exécution & Suivi temps réel (MVP).
- **FR** : FR18 (routage plateforme), FR23 (callbacks).
- **Architecture** : `_bmad-output/planning-artifacts/architecture.md` — Adapter Pattern, ExecutionService, API v2, snake_case, PlatformError, structlog.
- **Code existant** : `idp-portal/backend/app/adapters/aap_adapter.py`, `base_adapter.py` ; `execution_service.py` ; `app/models/catalog.py` (ExecutionStep, connector_config).

---

## Dev Agent Record

### Agent Model Used

(À remplir par l’agent d’implémentation.)

### Debug Log References

### Completion Notes List

- Task 1: resource_type stocké dans connector_config des execution_steps (clés resource_type, job_template_id / workflow_job_template_id). ExecutionService._merge_aap_connector_config() fusionne connector_config avec execution.parameters pour les étapes AAP ; step_order passé à _execute_platform_step pour retrouver la step def.
- Task 2: AAPAdapter.trigger() lit resource_type (défaut job_template), construit URL job_templates ou workflow_job_templates ; exclut resource_type, job_template_id, workflow_job_template_id des extra_vars. get_status() utilise _resource_type pour /jobs/ ou /workflow_jobs/. Codes erreur AAP_WORKFLOW_JOB_TEMPLATE_NOT_FOUND, AAP_WORKFLOW_JOB_NOT_FOUND.
- Task 3: StepsEditor affiche pour connector_type AAP le select « Type de ressource » (Job template / Workflow job) et le champ « ID template », persistés dans connector_config.
- Task 4: Tests unitaires ajoutés (test_aap_adapter: trigger workflow_job, défaut resource_type, get_status workflow_job, 404 workflow) ; test_execution_service: test_platform_step_aap_merges_connector_config. 61 tests AAP + execution_service passent. Suite complète backend : 12 échecs préexistants (DB pool, inventory) non liés à 4.10.
- Code review (2026-01-30): 2 HIGH + 4 MEDIUM + 2 LOW identifiés. Correctifs appliqués: (1) StepsEditor: validation « ID template requis » pour étapes AAP + min=1; (2) aap_adapter.get_status(): erreurs HTTP non-404 converties en PlatformError AAP_ERROR; (3) aap_adapter.trigger(): template_id coercé en int, refus id &lt; 1; (4) docstring module 4.10. Test ajouté: test_get_status_500_raises_platform_error. 62 tests passent.

### File List

- idp-portal/backend/app/adapters/aap_adapter.py
- idp-portal/backend/app/services/execution_service.py
- idp-portal/frontend/src/components/admin/StepsEditor.tsx
- idp-portal/backend/tests/unit/test_aap_adapter.py
- idp-portal/backend/tests/unit/test_execution_service.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/4-10-adapter-aap-workflow-job-et-job-template.md
