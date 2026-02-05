from django.urls import path

from audit import views

app_name = "audit"

urlpatterns = [
    path("audit/executions", views.AuditExecutionsView.as_view(), name="audit-executions"),
    path("audit/export", views.AuditExportView.as_view(), name="audit-export"),
]

