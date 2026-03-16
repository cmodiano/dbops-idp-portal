"""
Container workflow routing — next step resolution (Story 67.2, 67.3).
Délègue à executions.domain.workflow_graph depuis Story 85.1.
"""
from executions.domain.workflow_graph import get_next_step_ids, get_linear_next_step_ids

__all__ = ["get_next_step_ids", "get_linear_next_step_ids"]
