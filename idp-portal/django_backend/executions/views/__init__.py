"""Package executions.views — backward-compatible exports.

Ce package réexporte toutes les vues pour que les imports existants
(ex: ``from executions.views import ExecutionsView``) fonctionnent sans modification.
"""
from .list_views import (
    ExecutionsListView,
    ExecutionStatsView,
    ExecutionTimeSeriesView,
    ExecutionTagsView,
)
from .execution_views import (
    ExecutionsCreateView,
    ExecutionDetailView,
    ExecutionCancelView,
    ExecutionStepsView,
    ExecutionStepLogsView,
    ExecutionLogsView,
)
from .scheduled_views import (
    ScheduledExecutionsView,
    ScheduledExecutionUpdateView,
    ScheduledExecutionRecurringPatternView,
    ScheduledExecutionValidateCronView,
    ScheduledExecutionCronNextExecutionsView,
)
from .approval_views import PendingApprovalsView, ApproveExecutionView, RejectExecutionView


class ExecutionsView(ExecutionsListView, ExecutionsCreateView):
    """Combined view for GET (list) and POST (create) executions."""
    pass


__all__ = [
    'ExecutionsView',
    'ExecutionStatsView',
    'ExecutionTimeSeriesView',
    'ExecutionTagsView',
    'ExecutionDetailView',
    'ExecutionCancelView',
    'ExecutionStepsView',
    'ExecutionStepLogsView',
    'ExecutionLogsView',
    'PendingApprovalsView',
    'ApproveExecutionView',
    'RejectExecutionView',
    'ScheduledExecutionsView',
    'ScheduledExecutionUpdateView',
    'ScheduledExecutionRecurringPatternView',
    'ScheduledExecutionValidateCronView',
    'ScheduledExecutionCronNextExecutionsView',
]
