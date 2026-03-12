# WebSocket + Celery + Redis Fan-out Load Test (2026-03-11)

## Scope

This document captures the load-test campaign run against the real-time workflow update pipeline:

`Celery worker -> Redis broker -> task execution -> channel_layer.group_send() -> Redis channel layer -> WebSocket clients`

Test objective:
- Validate correctness and latency under fan-out and burst conditions.
- Measure end-to-end latency using event emit timestamp and client receive timestamp.


## Environment and Pipeline

- Backend server: Gunicorn ASGI worker
- WebSocket stack: Django Channels + Redis channel layer
- Celery: Redis broker/backend
- WebSocket auth/origin policy enabled (`OriginValidator`)
- Client load generator: authenticated WebSocket clients


## Key Implementation Notes

- Early handshake failures were caused by missing `Origin` header in synthetic clients.
- Browser-like `Origin: http://localhost:8080` is required by current ASGI security policy.
- Real emitter path validated with Celery task dispatch and `group_send()` from worker context.


## Baseline Results (Before Tuning)

### Scenario A: 200 clients x 500 events (Celery real emitter)
- Delivery ratio: `0.9684` (`96843 / 100000`)
- Full-delivery clients: `123 / 200`
- E2E latency:
  - p50: `72 ms`
  - p95: `1212 ms`
  - p99: `1297 ms`

### Scenario B: 200 clients x 1000 events burst (sleep=0)
- Delivery ratio: `0.9448` (`188964 / 200000`)
- Full-delivery clients: `31 / 200`
- E2E latency:
  - p50: `619 ms`
  - p95: `1100 ms`
  - p99: `1179 ms`
- Emitter duration for 1000 events: `7621 ms` (target `< 2000 ms` not met)


## Tuning Pass Applied

### 1) Channels Redis queue tuning
In `idp_backend/settings.py`:
- `CHANNEL_REDIS_CAPACITY` default `5000`
- `CHANNEL_REDIS_EXPIRY` default `10`
- Applied to `CHANNEL_LAYERS["default"]["CONFIG"]`

### 2) Celery worker concurrency
In `docker-compose.yml`:
- `--concurrency=4` -> `--concurrency=8`

### 3) Gunicorn ASGI workers
In `django_backend/Dockerfile`:
- `--workers 4` -> `--workers 6`


## Results After Tuning

### Scenario A: 200 clients x 500 events
- Delivery ratio: `1.0000` (`100000 / 100000`)
- Full-delivery clients: `200 / 200`
- E2E latency:
  - p50: `15 ms`
  - p95: `95 ms`
  - p99: `111 ms`
  - max: `124 ms`
- Target `< 200 ms p95`: **met**

### Scenario B: 200 clients x 1000 events burst (sleep=0)
- Delivery ratio: `0.9998` (`199964 / 200000`)
- Full-delivery clients: `164 / 200`
- E2E latency:
  - p50: `16 ms`
  - p95: `232 ms`
  - p99: `538 ms`
  - max: `794 ms`
- Target `< 200 ms p95`: **not met (close)**
- Emitter duration for 1000 events: `9792 ms` (still not `< 2000 ms`)


## Interpretation

- Tuning produced a significant improvement in reliability and latency under heavy fan-out.
- The remaining gap is concentrated in **burst mode**:
  - publisher throughput is too high and too granular for strict p95 target,
  - clients may miss a very small tail of events in extreme burst windows.


## Remaining Steps (Prioritized)

## 1. Event Model Optimization (Highest Impact)
- Reduce event volume via semantic transitions instead of micro-updates.
- Introduce dedupe/throttle rules:
  - emit progress only on meaningful delta (for example >= 5%),
  - emit at most once every 500-1000 ms per step.
- Always emit terminal state immediately.

## 2. Batch Protocol
- Add backend message type `steps_update_batch`.
- Coalesce updates in a short window (50-150 ms).
- Update frontend WebSocket handlers to consume both:
  - existing `step_update`,
  - new `steps_update_batch`.

## 3. Burst Throughput Improvements
- Re-run burst tests with coalescing enabled and target:
  - `1000 events equivalent in < 2s`,
  - `p95 < 200 ms`,
  - near-zero event loss.

## 4. Optional Horizontal Hot-Spot Mitigation
- Add group sharding for very hot executions:
  - `execution_<id>_0`, `execution_<id>_1`, ...
- Route clients deterministically to shard.

## 5. Production Observability
- Keep and expose these metrics in dashboards:
  - emitter duration,
  - queue depth/capacity pressure,
  - end-to-end p50/p95/p99 latency,
  - per-client delivery completeness,
  - WebSocket disconnect and reconnect rates.


## Acceptance Targets for Next Iteration

- Fan-out (200 x 500): delivery ratio `>= 0.9999`, p95 `< 150 ms`
- Burst (200 x 1000): delivery ratio `>= 0.999`, p95 `< 200 ms`
- Emitter burst runtime: `1000 updates-equivalent in < 2s`

