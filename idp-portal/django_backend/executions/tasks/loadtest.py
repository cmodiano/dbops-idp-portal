"""
Load-test Celery task for WebSocket fan-out verification.

This task intentionally emits synthetic ``step_update`` events to an execution
group so that we can validate the full pipeline:
Celery worker -> Redis broker/task execution -> Channels group_send -> WS clients.
"""

from __future__ import annotations

import time
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]


@shared_task(
    bind=True,
    name="executions.tasks.loadtest_emit_step_updates",
)
def loadtest_emit_step_updates(
    self: Any,
    execution_id: int,
    run_id: str,
    event_count: int = 100,
    sleep_ms: int = 0,
) -> dict[str, Any]:
    """Emit synthetic ``step_update`` events to one execution group.

    Args:
        execution_id: Target execution id (group name execution_{id}).
        run_id: Unique test run identifier echoed in each payload.
        event_count: Number of updates to publish.
        sleep_ms: Delay between events in milliseconds (0 for burst mode).
    """
    from asgiref.sync import async_to_sync  # noqa: PLC0415
    from channels.layers import get_channel_layer  # noqa: PLC0415

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return {"ok": False, "error": "channel_layer_unavailable", "emitted": 0}

    group_name = f"execution_{execution_id}"
    emitted = 0
    started_ms = int(time.time() * 1000)
    sleep_s = max(0, sleep_ms) / 1000.0

    for seq in range(max(0, event_count)):
        emit_ts_ms = int(time.time() * 1000)
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "step_update",
                "data": {
                    "execution_id": execution_id,
                    "status": "RUNNING",
                    "step_name": "loadtest-step",
                    "run_id": run_id,
                    "seq": seq,
                    "emit_ts_ms": emit_ts_ms,
                },
            },
        )
        emitted += 1
        if sleep_s > 0:
            time.sleep(sleep_s)

    finished_ms = int(time.time() * 1000)
    return {
        "ok": True,
        "run_id": run_id,
        "execution_id": execution_id,
        "emitted": emitted,
        "started_ms": started_ms,
        "finished_ms": finished_ms,
        "duration_ms": finished_ms - started_ms,
        "sleep_ms": sleep_ms,
    }
