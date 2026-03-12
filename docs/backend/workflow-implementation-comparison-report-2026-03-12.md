# Workflow implementation comparison report

Date: 2026-03-12

## Scope

This review compares the current workflow implementation in this repository with
Temporal and other workflow/orchestration solutions, with a specific focus on:

- orchestration model
- durability and resume behavior
- how inputs and outputs move between steps
- flow bugs, architectural gaps, and operational risks
- concrete improvement recommendations

Primary files reviewed:

- `idp-portal/django_backend/executions/container_workflow_runtime.py`
- `idp-portal/django_backend/executions/container_routing.py`
- `idp-portal/django_backend/executions/container_parallel.py`
- `idp-portal/django_backend/executions/template_resolver.py`
- `idp-portal/django_backend/executions/output_extractor.py`
- `idp-portal/django_backend/executions/tasks/gates.py`
- `idp-portal/django_backend/executions/views/approval_views.py`
- `idp-portal/django_backend/executions/step_handlers/*.py`
- `idp-portal/django_backend/catalog/validation.py`
- `docs/backend/decisions/adr-007-workflow-step-based-change-management.md`
- `docs/backend/decisions/adr-011-parallel-workflow-multi-connexion.md`

External comparison references used:

- Temporal workflow execution, event history, retry, and signals documentation
- AWS Step Functions input/output and retry/catch documentation
- Argo Workflows DAG, parameter/artifact, and suspend documentation
- n8n wait / human-in-the-loop documentation

## Executive summary

The current implementation is a useful step-based orchestrator with:

- explicit workflow graphs stored in `Action.execution_steps`
- save-time validation for references, joins, and cycles
- step handlers for `platform`, `service_call`, `http_request`, `evaluation`, and `gate`
- BFS-wave fan-out/fan-in execution
- approval and maintenance window gates
- a simple shared step-output context (`_step_outputs`) for mapping outputs into later steps

Conceptually, it is closer to a lightweight DB-backed DAG runner than to a
durable execution engine such as Temporal.

The strongest parts of the design are:

- explicit step definitions instead of hidden hooks
- good separation between routing, join policy, templating, and handlers
- decent validation of workflow graphs before execution
- pragmatic support for approval / waiting semantics

The biggest problems are in step I/O durability and execution fidelity:

1. non-platform handler outputs are not durably persisted, which makes
   post-gate resume unsafe for workflows that depend on those outputs
2. `input_mapping` stringifies structured values instead of preserving native
   Python/JSON types
3. container `platform` steps do not dispatch normal child actions through the
   real platform execution path; non-workflow child executions are marked
   `COMPLETED` by placeholder logic
4. `platform` step `output_mapping` can only extract parent metadata, not the
   real child execution output/artifacts described in the ADR examples

These issues are significant enough that the implementation should currently be
considered "workflow graph orchestration with partial dataflow support", not a
fully durable or semantically complete workflow engine.

## What the current implementation does well

### 1. Clear graph-based orchestration

`ContainerWorkflowRuntime` executes workflows as a graph, not just a linear
list. It supports:

- entry-step detection from graph structure
- success and error routing
- fan-out via multiple `on_success_step_ids` / `on_error_step_ids`
- fan-in via `join_policy`

Relevant files:

- `executions/container_workflow_runtime.py:1226-1365`
- `executions/container_routing.py:11-49`
- `executions/container_parallel.py:11-76`

### 2. Good pre-execution validation

`catalog/validation.py` validates:

- missing or duplicate `step_id`
- invalid branch references
- retry constraints
- cycle detection
- supported `join_policy` values

Relevant file:

- `catalog/validation.py:16-194`

### 3. Better model than hidden pre/post hooks

ADR-007 moved ServiceNow, approvals, evaluations, and gates toward explicit
workflow steps. That is a meaningful improvement over hidden hook behavior
because it makes orchestration visible in:

- the workflow definition
- execution steps
- user-facing timeline and audit trail

Relevant document:

- `docs/backend/decisions/adr-007-workflow-step-based-change-management.md`

### 4. Reasonable safety controls

Examples:

- `http_request` has host validation / SSRF guardrails
- `service_call` uses an allowlist of callable operations
- template rendering uses Jinja sandboxing

Relevant files:

- `executions/step_handlers/http_request_handler.py:135-170`
- `executions/step_handlers/service_call_handler.py:23-44, 96-174`
- `executions/template_resolver.py:97-109`

## Comparison with Temporal and other solutions

### High-level positioning

| Capability | Current implementation | Temporal | AWS Step Functions | Argo Workflows | n8n |
|---|---|---|---|---|---|
| Core model | DB-backed step graph in Django | Durable code-first workflows with event history replay | Managed state machine | Kubernetes-native DAG/workflow engine | Low-code automation graph |
| Durability model | Execution + ExecutionStep rows, plus some Celery resume logic | Strong durable execution and replay from event history | Strong managed state persistence | Strong workflow CRD/state persistence | Persists node data, optimized for automation not deterministic replay |
| Step I/O semantics | Ad hoc `input_mapping` + `output_mapping` | Typed payloads via SDK data converters | Explicit input/output/result path controls | Parameters and artifacts | Node JSON data passing |
| Human approval / wait | Gate steps + resume task | Signals / updates / wait patterns | Callback / wait / task token patterns | `suspend` templates | Wait / form / human-in-the-loop nodes |
| Parallelism | BFS wave fan-out with local thread pool | Child workflows / activities / concurrent branches | `Parallel` and `Map` states | DAG tasks, artifacts, large k8s parallelism | Parallel branches available, less formal semantics |
| Retry model | Mixed, partly legacy, partly handler-specific | Built-in activity retry policies | Built-in retry/catch on states | Retry strategies | Node-level retry / wait patterns |
| Best fit | Internal orchestration inside current Django product | Mission-critical long-running workflows | Managed cloud orchestration | K8s-centric batch / ML / CI style flows | Low-code business automation |

### Compared with Temporal

Temporal is materially stronger in the areas where this repository is weakest:

- durable execution and deterministic recovery
- explicit event history
- consistent retry semantics
- robust message-driven workflow progression via signals/updates
- long-running workflows without losing state on process restarts

Current strengths versus Temporal:

- easier to understand for teams already living inside Django models
- lower conceptual overhead
- direct integration with existing domain models and permission system

Current weaknesses versus Temporal:

- no replay-based durable state machine
- no typed payload contract between steps
- partial persistence of step outputs
- waiting/resume logic depends on ad hoc reconstruction from `ExecutionStep.output`
- in-memory fan-out execution rather than durable branch scheduling

Bottom line:

The current engine is not yet a Temporal alternative. It is a lightweight
orchestrator with some durable records, not a durable execution runtime.

### Compared with AWS Step Functions

Step Functions is stronger in declarative step I/O shaping:

- input preservation vs replacement is explicit
- result merge behavior is explicit
- retries and catches are first-class
- parallel branches and maps are native primitives

Current engine strengths:

- easier to plug into internal Python services and Django-side business logic
- more flexible custom handlers without cloud-provider lock-in

Current engine weaknesses:

- no equivalent of `ResultPath` / `OutputPath` semantics
- output persistence is inconsistent across step types
- parallel + wait/gate behavior is incomplete

### Compared with Argo Workflows

Argo is stronger when:

- artifacts are large or explicit
- execution is container / Kubernetes centric
- parallelism is large-scale
- dependencies are truly DAG-first rather than wave-first

Current engine strengths:

- easier for app-level orchestration and approval logic
- simpler operational footprint if the product is already Django + Celery

Current engine weaknesses:

- no first-class artifact passing
- no explicit durable dependency graph execution state per branch
- join logic is limited to the current BFS wave

### Compared with n8n

n8n is closer in spirit for human-in-the-loop and service automation, but it is
more low-code and less governance-heavy.

Current engine is stronger than n8n for:

- backend-owned governance and RBAC
- internal service integration discipline
- explicit data model and audit integration

n8n is stronger for:

- ease of building wait/approval flows
- low-code UX
- out-of-the-box form/webhook based human interactions

## How inputs and outputs currently flow between steps

## Input handling

### Sources of step inputs

For `platform` steps, parameters come from:

1. global execution parameters
2. `workflow_step_parameters`
3. `input_mapping`, resolved against `_step_outputs`

Relevant code:

- `executions/container_workflow_runtime.py:234-266`
- `executions/container_workflow_runtime.py:376-395`

### Input resolution mechanism

`StepTemplateResolver` resolves templates like:

- `{{ steps.discovery.db }}`
- `{{ steps['create-change'].number }}`
- execution context values such as `{{ action_name }}`

Relevant code:

- `executions/template_resolver.py:74-150`

### Strengths

- syntax is familiar to Ansible / Jinja users
- sandboxing is in place
- missing values degrade to empty string instead of exploding

### Problems

- values are always rendered as strings, even when the underlying value is a
  list or dict
- the ADR examples show native list/dict forwarding, but the implementation
  does not preserve types

Direct runtime check in this environment:

- `{{ steps.discovery.databases }}` resolves to `str ['DB1', 'DB2']`
- `{{ steps.discovery.payload }}` resolves to `str {'x': 1}`

That behavior is consistent with `template_resolver.py:139-145`, which always
uses `render()` and returns the rendered string.

## Output handling

### Output extraction

After a step finishes, `OutputExtractor` can map fields out of a raw result
using simple dot-path expressions such as `$.data.databases`.

Relevant file:

- `executions/output_extractor.py:12-73`

### Shared in-memory context

Extracted outputs are written into `self._step_outputs[step_id]` and used by
later steps during the same runtime session.

Relevant code:

- `executions/container_workflow_runtime.py:717-739`
- `executions/container_workflow_runtime.py:972-980`

### Resume behavior

When a workflow resumes after a gate, `resume_container_workflow_from_gate()`
tries to rebuild `_step_outputs` from completed `ExecutionStep.output`.

Relevant code:

- `executions/tasks/gates.py:827-869`

### Main weakness

The resume path only works if the prior step's output was durably stored in
`ExecutionStep.output`. That is not consistently true today.

## Findings: flaws, bugs, and limitations

### Critical

#### 1. Non-platform step outputs are not persisted, so resume after a gate can lose required data

Evidence:

- `executions/container_workflow_runtime.py:950-996`
  - `_finalize_handler_step()` extracts values into `_step_outputs`
  - but it never calls `parent_step.set_output(...)`
- `executions/tasks/gates.py:827-869`
  - gate resume reconstructs `_step_outputs` from `db_step.get_output()`

Impact:

- `service_call`, `http_request`, and `evaluation` step outputs are available
  only in memory during the original run
- after a waiting gate, downstream steps may lose access to upstream handler
  outputs entirely
- this breaks the durability expectation implied by ADR-007 and makes approval /
  maintenance-window resumes unsafe for workflows that depend on prior handler
  outputs

Why this matters relative to Temporal:

Temporal persists the workflow event history needed to restore workflow state.
Here, the output context is only partially reconstructible.

Recommendation:

- persist both raw handler output and extracted output on `ExecutionStep`
- rebuild from persisted extracted output on resume, not from "whatever happens
  to be in `ExecutionStep.output`"

#### 2. Structured values in `input_mapping` are stringified instead of preserved

Evidence:

- `executions/template_resolver.py:139-145`
- direct runtime check in this environment:
  - list resolves to `str ['DB1', 'DB2']`
  - dict resolves to `str {'x': 1}`

Impact:

- list/dict forwarding shown in ADR examples does not actually work as a native
  value transfer
- JSON request bodies, `extra_vars`, arrays of targets, and evaluation payloads
  can silently become strings
- downstream handlers may receive syntactically valid but semantically wrong
  data

Example mismatch:

- ADR-007 shows `extra_vars.databases: "{{ steps.discovery.databases }}"`
- current resolver returns a string representation, not a list

Recommendation:

- when the input string is exactly one Jinja expression, use native expression
  evaluation instead of `render()`
- keep string rendering only for mixed text templates such as
  `"Patch {{ steps.discovery.patch_number }}"`

### High

#### 3. Container `platform` steps do not execute normal child actions through the real platform dispatch path

Evidence:

- `executions/container_workflow_runtime.py:684-715`
  - non-workflow child executions are marked `COMPLETED` by placeholder logic
- contrast with legacy path:
  - `executions/workflow_step_executor.py:327-358`
  - dispatches `trigger_platform_job.apply_async(...)`

Impact:

- inside container workflows, a `platform` step referencing a normal action does
  not appear to trigger the actual platform adapter path
- child executions can be marked completed even though no real external work was
  started
- success/failure routing can therefore be based on placeholder completion
  rather than actual platform execution outcome

Recommendation:

- route container `platform` steps through the same real trigger/poll path used
  by the legacy step executor
- remove the placeholder branch that blindly completes non-workflow child
  executions

#### 4. `platform` step `output_mapping` can only see parent metadata, not child artifacts/output

Evidence:

- `executions/container_workflow_runtime.py:811-817`
  - parent step output is set to:
    - `child_execution_id`
    - `referenced_action_id`
    - `referenced_action_name`
    - `child_status`
    - `parameters_injected`
- `executions/container_workflow_runtime.py:717-739`
  - output extraction for platform steps reads from `parent_step.get_output()`

Impact:

- ADR examples such as extracting `$.artifacts.health_report` from a platform
  step cannot work with the current implementation
- only metadata about the child execution can be mapped, not the real result of
  that child action

Recommendation:

- define a real output contract for `platform` steps:
  - either persist child execution final output/artifacts onto the parent step
  - or allow `output_mapping` to explicitly reference child execution output

### Medium

#### 5. Step approval/reject views emit side effects before transaction commit

Evidence:

- approve path:
  - `executions/views/approval_views.py:726-730`
- reject path:
  - `executions/views/approval_views.py:820-824`

Impact:

- durable events and runnable-step deletions can happen before the database
  transaction has committed
- if the transaction later rolls back, external observers may see approval /
  rejection side effects for changes that were not durably committed

Recommendation:

- move `WorkflowEventService.emit_*` and `RunnableStepService.delete(...)` into
  `transaction.on_commit(...)`, as already done elsewhere in the module

#### 6. Gate steps inside fan-out are explicitly unsupported and are converted to failure

Evidence:

- `executions/container_workflow_runtime.py:1050-1064`
- `executions/container_workflow_runtime.py:566-568`

Impact:

- a workflow author can define a valid graph that pauses correctly in sequence
  mode but fails in parallel mode
- this is a correctness limitation, not just a missing optimization

Recommendation:

- model waiting branches as durable branch state instead of forcing `FAILED`
- if unsupported for now, reject such workflows at validation time rather than
  letting them fail at runtime

#### 7. Join semantics are limited to predecessors in the current BFS wave

Evidence:

- documented in `docs/backend/decisions/adr-011-parallel-workflow-multi-connexion.md:108-114`

Impact:

- some valid DAG convergence patterns cannot be represented correctly
- behavior is wave-dependent rather than dependency-dependent

Recommendation:

- replace wave-local join evaluation with explicit predecessor tracking and
  per-node dependency counters

### Lower-priority issues

#### 8. Handler exceptions do not persist a useful `error_message` on the failed step

Evidence:

- `executions/container_workflow_runtime.py:1037-1048`

Impact:

- UI and operational debugging lose the concrete failure reason on the step row
- logs contain the stack trace, but step-level persistence is thin

Recommendation:

- store exception type/message in `parent_step.error_message` before saving

## Test coverage observations

There is good unit coverage for:

- routing and join behavior
- step dispatch
- basic template resolution
- gate behavior

But the current tests mostly cover scalar and in-memory paths, not durable I/O
semantics. In particular, I did not find focused tests that prove:

- list/dict values survive `input_mapping` as native types
- handler step outputs survive a gate pause and resume
- `platform` output mapping can read child artifacts
- approval/reject side effects only fire after commit

Relevant test files:

- `executions/tests/test_template_resolver.py`
- `executions/tests/test_step_dispatcher.py`
- `executions/tests/test_container_workflow_runtime.py`
- `executions/tests/test_gate_handler.py`

## Recommended improvement plan

### Priority 1: Fix the step I/O contract

1. Persist raw and extracted outputs for every step type
2. Standardize `ExecutionStep.output` shape, for example:

```json
{
  "raw_output": {...},
  "extracted_output": {...},
  "status_context": {...}
}
```

3. Rebuild `_step_outputs` from `extracted_output` during resume

### Priority 2: Preserve native types in input mapping

Implement two resolution modes:

- exact expression only -> evaluate to native Python/JSON type
- mixed text template -> render to string

This would align the implementation with the ADR examples and with user
expectations.

### Priority 3: Unify `platform` execution behavior

Make container `platform` steps use the same real execution path as the legacy
workflow runtime:

- trigger adapter job
- poll / receive callback
- persist real output
- propagate real success/failure

### Priority 4: Improve output extraction semantics

Enhancements to consider:

- support extracting from child execution output/artifacts
- support array paths and richer JSONPath
- add explicit result merge semantics similar to Step Functions

### Priority 5: Make wait/approval behavior fully durable

- move all side effects to `on_commit`
- support waiting branches in parallel mode
- validate unsupported graph patterns before execution

### Priority 6: Strengthen tests around real workflow durability

Add tests for:

1. list and dict forwarding through `input_mapping`
2. `service_call` output used after an approval gate resume
3. `http_request` output used after a maintenance-window resume
4. `platform` artifact extraction into later steps
5. approval transaction rollback vs event emission

## Overall assessment

This implementation is a meaningful improvement over hidden hooks and linear
delegation-only workflows. The graph model, validation, and step handler split
are good foundations.

However, compared to Temporal and other mature orchestration systems, the engine
is still missing a reliable, durable step data contract. The core risk is not
just "some edge cases"; it is that the current workflow semantics for step I/O
change depending on:

- whether the step type is `platform` or not
- whether the workflow pauses and resumes
- whether the value being passed is scalar or structured
- whether the graph uses parallel branches with gates

In its current state, the engine is best described as:

- a solid workflow-definition framework
- a useful graph runner for simple and mostly synchronous flows
- not yet a fully durable workflow execution engine

If the team wants "Temporal-like confidence" without adopting Temporal itself,
the next milestone should be to make step input/output persistence deterministic,
typed, and resume-safe before adding more step types or more graph complexity.
