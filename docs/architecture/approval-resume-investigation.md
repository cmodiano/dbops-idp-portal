# Investigation: Approval Step Satisfied but Next Step Does Not Start

## Summary

After approving a workflow step (execution 406), the gate shows `satisfied: true` but the next step ("Exécuter Emergency Stop Database") never starts. No records exist in `RUNNABLE_STEPS` (expected for container workflows—see below).

## Complete Code Flow

### 1. Approval Request (User Clicks Approve)

**Entry point:** `POST /executions/{execution_id}/steps/{step_id}/approve/`  
**Handler:** `ApproveStepView.post()` in `executions/views/approval_views.py`

```
ApproveStepView.post()
├── _get_step_or_404(execution_id, step_id)
├── _validate_approval_gate_step(step)
├── _get_step_config(step)  ← CRITICAL: step config from action.execution_steps
├── _check_approver_permission(user, step_config)
├── Update step: status=COMPLETED, approved_by, approved_at, output
├── WorkflowEventService.emit_approval_granted()
├── RunnableStepService.delete(step.id)
├── on_success_step_id = step_config.get("on_success_step_id")
│   └── If None: _get_next_step_id_by_order(execution_steps, step_config)

├── if on_success_step_id:
│   └── transaction.on_commit(
│         lambda: resume_container_workflow_from_gate.apply_async(
│             args=[execution_id, on_success_step_id]
│         )
│       )
└── else:
    └── execution.status = COMPLETED  ← WORKFLOW ENDS HERE
```

### 2. Computing `on_success_step_id`

**`_get_step_config(step)`** (lines 150–165):
- Matches `step.step_name` against `s.get("step_id")` OR `s.get("name")` in `action.execution_steps`
- Returns `{}` if no match → `step_config_not_found` warning

**`_get_next_step_id_by_order(execution_steps, step_config)`** (lines 167–177):
- Filters: `[s for s in execution_steps if isinstance(s, dict) and s.get("step_id")]`
- **Only steps with `step_id` are considered**
- Sorts by `order`, returns first step with `order > current_order` → `step_id`

**Root cause hypothesis 1:** If the workflow has no `step_id` on any step:
- `sorted_steps` = []
- `_get_next_step_id_by_order` returns `None`
- `on_success_step_id` = `None`
- Execution is set to COMPLETED
- `resume_container_workflow_from_gate` is never called

**Root cause hypothesis 2:** If `_get_step_config` returns `{}` (no match):
- `step_config.get("on_success_step_id")` = `None`
- Fallback: `_get_next_step_id_by_order(execution_steps, {})` with `current_order = 0`
- Still requires steps with `step_id` to return a value

### 3. Celery Task: `resume_container_workflow_from_gate`

**Entry:** `executions/tasks/gates.py` – Celery Beat task

```
resume_container_workflow_from_gate(execution_id, on_success_step_id)
├── if is_cancelled(execution_id): return {'outcome': 'cancelled'}
├── execution = Execution.objects.select_related('action').get(id=execution_id)
├── if execution.status != RUNNING:
│   └── return {'outcome': 'not_running', 'status': str(execution.status)}  ← EARLY EXIT
│
├── all_steps = execution.action.execution_steps or []
├── remaining_steps = [steps from all_steps where s.get('step_id') == on_success_step_id, and all after]
├── if not found:
│   └── return {'outcome': 'step_not_found', 'step_id': on_success_step_id}
│
├── runtime = ContainerWorkflowRuntime(execution)
├── runtime.workflow_steps = remaining_steps
└── runtime._execute_workflow_steps()
```

**Root cause hypothesis 3:** `execution.status != RUNNING`
- If execution was set to COMPLETED (because `on_success_step_id` was None in ApproveStepView), the task bails early
- Log: `resume_container_workflow_gate_not_running`

**Root cause hypothesis 4:** `execution_steps` format
- If `execution_steps` is `{"steps": [...]}` (dict), `for s in all_steps` iterates over keys `["steps"]`, not step dicts
- Step not found → `step_not_found`
- Log: `resume_container_workflow_gate_step_not_found`

**Root cause hypothesis 5:** `on_success_step_id` doesn't match any `step_id`
- Workflow uses `step_id` values that don't match what `_get_next_step_id_by_order` returns
- E.g. fallback returns `step_id` from step def, but `resume_container_workflow_from_gate` expects exact match

### 4. RUNNABLE_STEPS Table

**For container workflows, RUNNABLE_STEPS is not used.** Resume uses `resume_container_workflow_from_gate` Celery task.
- `RunnableStepService.enqueue()` is used by `workflow_step_executor.py` for old-style WorkflowRuntime
- Container workflows use `ContainerWorkflowRuntime` and `resume_container_workflow_from_gate`
- Empty RUNNABLE_STEPS is expected for this workflow type

### 5. Step Definition Structure

**Validation** (`catalog/validation.py`):
- `step_id` is required when `uses_branches_or_retry` is True (any step has `on_success_step_id`, `on_error_step_id`, retry, or `parallel_group`)
- Simple linear workflows without `on_success_step_id` may have no `step_id` on any step

**Container workflow** expects:
- `step_id` for step lookup in `resume_container_workflow_from_gate`
- `_step_lookup_by_id` and `steps_to_execute` filter by `step_id`; steps without `step_id` are excluded from `steps_to_execute` (line 1286: `s.get('step_id') not in self._member_step_ids` → steps without `step_id` have `s.get('step_id')` = None, and `None not in frozenset()` is True, so they stay in the list—actually `None in frozenset()` is False, so they'd be included)

Actually: `s.get('step_id') not in self._member_step_ids` — if `step_id` is None, `None not in member_ids` is True (member_ids contains step_id strings), so the step stays in `steps_to_execute`. So steps without step_id can still be executed.

But for resume: we need `on_success_step_id` to match `s.get('step_id')`. If no step has `step_id`, we can't find it.

## Diagnostic Checklist

To narrow down the root cause, run these checks:

### 1. Check execution status (execution 406)

```sql
SELECT id, status, started_at, completed_at, error_message 
FROM executions 
WHERE id = 406;
```

If `status = 'COMPLETED'` → execution was marked COMPLETED by ApproveStepView (because `on_success_step_id` was None).

### 2. Check workflow definition (action.execution_steps)

```sql
SELECT a.id, a.name, a.execution_steps 
FROM catalog_actions a
JOIN executions e ON e.action_id = a.id
WHERE e.id = 406;
```

Verify:
- Is `execution_steps` a list `[{...}, {...}]` or a dict `{"steps": [...]}`?
- Does each step have `step_id`?
- Does the approval step have `on_success_step_id`?
- What are the `order` values?

### 3. Check Celery logs

Search for:
- `resume_container_workflow_gate_start` (execution_id=406)
- `resume_container_workflow_gate_not_running`
- `resume_container_workflow_gate_step_not_found`
- `resume_container_workflow_gate_complete`

### 4. Check audit log for approval

```sql
SELECT * FROM audit_log 
WHERE entity_type = 'EXECUTION' AND entity_id = 406 
  AND action_type = 'EXECUTION_APPROVED'
ORDER BY created_at DESC LIMIT 1;
```

Check `details` JSON for `on_success_step_id` — if it's `null`, that confirms the approval path set execution to COMPLETED.

### 5. Step config matching

The approval step has `step_name = "test"` (from logs). `_get_step_config` matches:
- `s.get("step_id") == "test"` OR
- `s.get("name") == "test"`

If the workflow uses `step_id` like `"step-1"` and `name` like `"Attendre test"`, the match would fail (step_name in DB might be "test" based on the logs). Confirm what `ExecutionStep.step_name` is for the approved step.

## Root Cause (Confirmed)

**`_step_order_counter` started at 0 on resume**, causing a unique constraint violation on `(EXECUTION_ID, STEP_ORDER)`. When resuming after approval, the platform step was created with `step_order=1`, but the approval step already had `step_order=1` → `ORA-00001: UK_EXEC_STEPS_EXEC_ORDER violated`.

**Fix:** In `resume_container_workflow_from_gate`, initialize `runtime._step_order_counter` to the max existing `step_order` for the execution before calling `_execute_workflow_steps()`.

## Previous Hypothesis (Ruled Out)

**Workflow steps lack `step_id`.** For a simple linear workflow (gate → platform) without explicit branching:
- Validation does not require `step_id`
- `_get_next_step_id_by_order` filters to steps with `step_id` → empty list
- `on_success_step_id` = None
- ApproveStepView sets execution to COMPLETED
- `resume_container_workflow_from_gate` is never called

## Recommended Fix (After Confirmation)

If steps lack `step_id`:
1. Extend `_get_next_step_id_by_order` to support steps without `step_id` by using a synthetic identifier (e.g. `order` or index), or
2. Ensure `resume_container_workflow_from_gate` can find the next step by `order` when `step_id` is absent, or
3. Require `step_id` for all workflow steps (including linear gates) in validation.

## Files Reference

| File | Relevance |
|------|------------|
| `executions/views/approval_views.py` | ApproveStepView, _get_step_config, _get_next_step_id_by_order |
| `executions/tasks/gates.py` | resume_container_workflow_from_gate |
| `executions/container_workflow_runtime.py` | _execute_workflow_steps, _load_workflow_steps |
| `catalog/validation.py` | step_id requirement, uses_branches_or_retry |
| `executions/services/runnable_steps.py` | RUNNABLE_STEPS (not used for container workflows) |
