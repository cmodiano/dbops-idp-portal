"""
Container workflow parallel execution — join policy (Story 67.3, 67.8).
Délègue à executions.domain.workflow_graph depuis Story 85.1.
"""
from executions.domain.workflow_graph import apply_join_policy

__all__ = ["apply_join_policy"]
