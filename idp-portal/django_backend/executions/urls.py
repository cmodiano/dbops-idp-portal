"""
URL configuration for executions endpoints.
"""

from django.urls import path

from executions import views

app_name = "executions"

urlpatterns = [
    path("executions/", views.ExecutionsView.as_view(), name="executions"),
    path("executions/stats/", views.ExecutionStatsView.as_view(), name="executions-stats"),
    path("executions/timeseries/", views.ExecutionTimeSeriesView.as_view(), name="executions-timeseries"),
    path("executions/tags/", views.ExecutionTagsView.as_view(), name="executions-tags"),
    path("executions/pending-approvals/", views.PendingApprovalsView.as_view(), name="executions-pending-approvals"),
    path("executions/<int:execution_id>/", views.ExecutionDetailView.as_view(), name="execution-detail"),
    path("executions/<int:execution_id>/steps/", views.ExecutionStepsView.as_view(), name="execution-steps"),
    path(
        "executions/<int:execution_id>/steps/<int:step_id>/logs/",
        views.ExecutionStepLogsView.as_view(),
        name="execution-step-logs",
    ),

    # Scheduled executions (Story 11.5-11.8)
    path("scheduled-executions/", views.ScheduledExecutionsView.as_view(), name="scheduled-executions"),
    path(
        "scheduled-executions/<int:scheduled_execution_id>/",
        views.ScheduledExecutionUpdateView.as_view(),
        name="scheduled-execution-update",
    ),
    path(
        "scheduled-executions/<int:scheduled_execution_id>/recurring-pattern/",
        views.ScheduledExecutionRecurringPatternView.as_view(),
        name="scheduled-execution-recurring-pattern",
    ),
    path(
        "scheduled-executions/validate-cron/",
        views.ScheduledExecutionValidateCronView.as_view(),
        name="scheduled-execution-validate-cron",
    ),
    path(
        "scheduled-executions/cron-next-executions/",
        views.ScheduledExecutionCronNextExecutionsView.as_view(),
        name="scheduled-execution-cron-next-executions",
    ),
]

