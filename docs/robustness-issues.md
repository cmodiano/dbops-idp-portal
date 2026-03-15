# Robustness Issues & Remediation Guide

This document catalogues the robustness gaps identified in the IDP Portal codebase and provides concrete steps to fix each one. Issues are grouped by severity.

---

## Critical (High Priority)

### 1. No Timeout on Adapter Calls — Step Hangs Indefinitely

**File:** `idp-portal/django_backend/adapters/base_adapter.py`
**Risk:** If AAP, Azure DevOps, GitHub Actions, or Terraform Cloud is unresponsive, the executing thread blocks forever. This starves the ThreadPoolExecutor and eventually freezes all parallel workflow execution.

**How to Fix:**

1. Add a `timeout_seconds` parameter to `ITriggerableAdapter.trigger()` and `get_status()`.
2. Pass the timeout to the underlying HTTP client (e.g., `requests.Session`).
3. Expose it as an environment variable per adapter (`AAP_SOCKET_TIMEOUT`, `AZURE_SOCKET_TIMEOUT`, etc.) with a safe default (e.g., 30s).
4. Catch `requests.Timeout` in the adapter and raise a domain-specific `AdapterTimeoutError` so the step handler can transition the step to `FAILED` cleanly.

```python
# base_adapter.py — add to interface
class ITriggerableAdapter(Protocol):
    def trigger(self, ..., timeout_seconds: int = 30) -> str: ...
    def get_status(self, job_id: str, timeout_seconds: int = 30) -> JobStatus: ...

# In concrete adapter
def trigger(self, ..., timeout_seconds: int = 30) -> str:
    try:
        response = self.session.post(url, json=payload, timeout=timeout_seconds)
    except requests.Timeout:
        raise AdapterTimeoutError(f"Platform did not respond within {timeout_seconds}s")
```

5. In `container_workflow_runtime.py`, catch `AdapterTimeoutError` where steps are dispatched and transition the step to `FAILED` with a clear error message.

---

### 2. ServiceNow `update_change` and `get_change_status` Raise `NotImplementedError`

**File:** `idp-portal/django_backend/services/servicenow_service.py`
**Risk:** Any workflow that executes a ServiceNow step to update or check a change request will raise `NotImplementedError` in production, failing the step with no graceful recovery.

**How to Fix:**

1. Implement `update_change(change_id, fields)` using the ServiceNow Table API `PATCH /api/now/table/change_request/{sys_id}`.
2. Implement `get_change_status(change_id)` using `GET /api/now/table/change_request/{sys_id}?sysparm_fields=state,approval`.
3. Map ServiceNow state codes to internal enum values (e.g., `-1=Cancelled`, `0=New`, `1=Assess`, `3=Authorize`, `4=Scheduled`, `7=Implement`, `8=Review`, `3=Closed`).
4. Add unit tests covering success responses, 404 (change not found), 403 (insufficient rights), and connection errors.
5. Add a `@pytest.mark.integration` test with a live or mocked ServiceNow sandbox.

```python
def update_change(self, change_id: str, fields: dict) -> None:
    url = f"{self.base_url}/api/now/table/change_request/{change_id}"
    response = self._session.patch(url, json=fields, timeout=self.timeout)
    response.raise_for_status()

def get_change_status(self, change_id: str) -> ChangeStatus:
    url = f"{self.base_url}/api/now/table/change_request/{change_id}"
    params = {"sysparm_fields": "state,approval,number"}
    response = self._session.get(url, params=params, timeout=self.timeout)
    response.raise_for_status()
    data = response.json()["result"]
    return ChangeStatus(state=data["state"], approval=data["approval"])
```

---

## Medium Priority

### 3. Gate Polling Has No Backoff

**File:** `idp-portal/django_backend/executions/gate_evaluator.py`
**Risk:** When a gate is in `WAITING` state, the evaluator polls every 5–10 seconds indefinitely with no backoff. Under load (many concurrent waiting gates), this floods the InventoryService with requests.

**How to Fix:**

1. Introduce a per-gate poll interval that grows exponentially up to a configurable ceiling.
2. Store the next poll time in the `ExecutionStep.output` JSON or in a dedicated cache key.
3. Skip evaluation if `now < next_poll_at`.

```python
# gate_evaluator.py
BASE_POLL_INTERVAL = 10        # seconds
MAX_POLL_INTERVAL = 300        # 5 minutes
POLL_BACKOFF_FACTOR = 2

def _next_poll_interval(self, attempt: int) -> int:
    interval = BASE_POLL_INTERVAL * (POLL_BACKOFF_FACTOR ** attempt)
    return min(interval, MAX_POLL_INTERVAL)
```

4. Persist `poll_attempt` alongside gate state so it survives worker restarts.

---

### 4. No Retry on `InventoryServiceError` in Maintenance Window Gate

**File:** `idp-portal/django_backend/executions/gates/strategies.py`
**Risk:** A single transient network error from InventoryService permanently blocks the gate step. The workflow stays `BLOCKED` until manually intervened.

**How to Fix:**

1. Wrap the `InventoryService.get_next_maintenance_window()` call in a retry loop (e.g., 3 attempts with 2s, 4s, 8s backoff using `tenacity`).
2. Only convert to a hard failure after all retries are exhausted.
3. Log each retry attempt with the correlation ID at `WARNING` level.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    retry=retry_if_exception_type(InventoryServiceError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)
def _get_maintenance_window(self, target_id: str) -> MaintenanceWindow | None:
    return self.inventory_service.get_next_maintenance_window(target_id)
```

---

### 5. `gate_type` Not Validated at Workflow Definition Time

**File:** `idp-portal/django_backend/catalog/validation.py`
**Risk:** A workflow with an invalid `gate_type` (e.g., a typo or a removed gate) is saved successfully but fails at execution time with an unhelpful error.

**How to Fix:**

1. Import `gate_registry` into `catalog/validation.py`.
2. In the step validation loop, for steps with `step_type == 'gate'`, check that each condition's `type` field exists in the registry.
3. Return a `ValidationError` with the invalid type name and the list of valid types.

```python
# catalog/validation.py
from executions.gates.registry import gate_registry

def _validate_gate_step(step: dict) -> list[str]:
    errors = []
    for condition in step.get("gate_conditions", []):
        condition_type = condition.get("type")
        if condition_type and not gate_registry.get_for_condition_type(condition_type):
            valid = [g.condition_type for g in gate_registry.all()]
            errors.append(
                f"Unknown gate condition type '{condition_type}'. "
                f"Valid types: {valid}"
            )
    return errors
```

4. Add unit tests for unknown gate types and confirm the error surfaces before an execution is created.

---

### 6. Cancellation Cache Is In-Memory (Race Condition Under Multi-Process Polling)

**File:** `idp-portal/django_backend/executions/cancellation_cache.py`
**Risk:** When multiple Celery workers poll the same execution, each has its own in-memory cancellation cache. A cancellation signal set in one worker is invisible to the others, causing the execution to keep running.

**How to Fix:**

1. Replace the in-memory dict with a Redis-backed cache using Django's cache framework (`cache.set` / `cache.get`).
2. Use a namespaced key: `cancellation:{execution_id}` with a TTL of e.g. 24 hours.
3. This is already infrastructure that exists (Redis is the Celery broker), so no new dependencies are needed.

```python
# cancellation_cache.py
from django.core.cache import cache

CANCELLATION_KEY_PREFIX = "cancellation:"
CANCELLATION_TTL = 86400  # 24 hours

def mark_cancelled(execution_id: str) -> None:
    cache.set(f"{CANCELLATION_KEY_PREFIX}{execution_id}", True, CANCELLATION_TTL)

def is_cancelled(execution_id: str) -> bool:
    return bool(cache.get(f"{CANCELLATION_KEY_PREFIX}{execution_id}"))

def clear_cancelled(execution_id: str) -> None:
    cache.delete(f"{CANCELLATION_KEY_PREFIX}{execution_id}")
```

4. Update all call sites to use the new module interface.
5. Add a test that sets the flag from one cache instance and reads it from another (simulating a second worker).

---

### 7. No Retry for Service Call Steps Mid-Workflow

**File:** `idp-portal/django_backend/executions/step_handlers/service_call_handler.py`
**Risk:** Step-level retry (configured via `max_attempts`) retries the entire step, but if the underlying Vault/ServiceNow call fails transiently within a step, there is no service-level retry. This causes unnecessary step failures and workflow rollbacks.

**How to Fix:**

1. Apply `tenacity` retry decorators to the individual service call methods (Vault `read_secret`, ServiceNow `create_change`, etc.) rather than relying solely on step retry.
2. Only retry on transient errors (`VaultUnavailableError`, `ServiceNowConnectionError`, HTTP 429/503).
3. Never retry on semantic failures (404, 403, validation errors).
4. Expose retry counts as configurable settings (`VAULT_MAX_RETRIES`, `SERVICENOW_MAX_RETRIES`).

---

## Low Priority

### 8. No Overall Timeout on Health Check Endpoint

**File:** `idp-portal/django_backend/integrations/health_check.py`
**Risk:** With 10 integrations each taking up to 5 seconds, the admin health endpoint can take 50 seconds. This causes browser timeouts and can block the admin UI.

**How to Fix:**

1. Run all integration health checks concurrently using `concurrent.futures.ThreadPoolExecutor`.
2. Set an overall deadline (e.g., 10 seconds) using `executor.map(..., timeout=10)`.
3. Mark integrations that exceed the deadline as `{"status": "timeout", "message": "Health check did not respond within 10s"}`.

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

def check_all_health(integrations: list) -> dict:
    results = {}
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(i.check_health): i.code for i in integrations}
        for future, code in futures.items():
            try:
                results[code] = future.result(timeout=10)
            except FuturesTimeout:
                results[code] = {"status": "timeout", "message": "No response within 10s"}
    return results
```

---

### 9. Splunk Batch Buffer Is Not Durable

**File:** `idp-portal/django_backend/services/splunk_service.py`
**Risk:** If a Celery worker dies while holding a batch of Splunk events in memory, those events are lost. There is no transactional outbox mechanism like the one used for `EXECUTION_OUTBOX`.

**How to Fix:**

1. Before sending the batch, write it to a `SPLUNK_OUTBOX` database table (or reuse the existing outbox pattern) within the same transaction as the operation that generated the events.
2. A separate Celery beat task flushes the outbox, deleting rows after confirmed delivery.
3. This ensures events survive worker restarts.

Alternatively, if strict durability is not required, document this limitation explicitly and add a metric that tracks dropped batches.

---

### 10. No Warning Before Hitting `MAX_STEP_TRANSITIONS`

**File:** `idp-portal/django_backend/executions/container_workflow_runtime.py` (line 114-115)
**Risk:** Complex workflows silently fail when they hit the 100-transition hard limit. There is no log warning before the limit is reached, making debugging difficult.

**How to Fix:**

1. Log a `WARNING` when the transition count exceeds 80% of the limit (i.e., ≥ 80 transitions).
2. Log an `ERROR` and include the execution ID, current step, and transition count when the limit is actually reached.
3. Consider making the limit configurable via `settings.MAX_STEP_TRANSITIONS` with the current value as the default.

```python
WARNING_THRESHOLD = int(MAX_STEP_TRANSITIONS * 0.8)

if transition_count >= WARNING_THRESHOLD:
    logger.warning(
        "Approaching step transition limit",
        execution_id=execution_id,
        transition_count=transition_count,
        limit=MAX_STEP_TRANSITIONS,
    )
```

---

### 11. Retry Backoff Has No Jitter (Thundering Herd Risk)

**Files:** `idp-portal/django_backend/executions/services.py`, `idp-portal/frontend/src/services/api_client.ts`
**Risk:** When many executions fail simultaneously and all retry at the same backoff intervals, they create synchronized bursts (thundering herd) that hit the platform or backend together.

**How to Fix (Backend):**

```python
import random

def backoff_with_jitter(attempt: int, base: float = 2.0, cap: float = 60.0) -> float:
    expo = min(base ** attempt, cap)
    return random.uniform(0, expo)  # Full jitter
```

**How to Fix (Frontend — `api_client.ts`):**

```typescript
function backoffWithJitter(attempt: number, base = 2000, cap = 30000): number {
  const expo = Math.min(base * 2 ** attempt, cap);
  return Math.random() * expo; // Full jitter
}
```

---

## Summary Table

| # | Issue | File | Priority |
|---|-------|------|----------|
| 1 | No timeout on adapter calls | `adapters/base_adapter.py` | **HIGH** |
| 2 | ServiceNow methods not implemented | `services/servicenow_service.py` | **HIGH** |
| 3 | Gate polling has no backoff | `executions/gate_evaluator.py` | MEDIUM |
| 4 | No retry on InventoryServiceError | `executions/gates/strategies.py` | MEDIUM |
| 5 | `gate_type` not validated at definition time | `catalog/validation.py` | MEDIUM |
| 6 | In-memory cancellation cache | `executions/cancellation_cache.py` | MEDIUM |
| 7 | No service-level retry for service call steps | `step_handlers/service_call_handler.py` | MEDIUM |
| 8 | No overall timeout on health check endpoint | `integrations/health_check.py` | LOW |
| 9 | Splunk batch buffer not durable | `services/splunk_service.py` | LOW |
| 10 | No warning before step transition limit | `container_workflow_runtime.py` | LOW |
| 11 | No jitter in retry backoff | `services.py`, `api_client.ts` | LOW |
