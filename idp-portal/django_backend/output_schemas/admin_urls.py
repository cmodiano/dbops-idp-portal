"""
Admin IaC URL configuration for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).

Registered via: path('api/v1/admin/', include('output_schemas.admin_urls'))
"""

from django.urls import path
from output_schemas.views import export_output_schemas, sync_output_schemas

urlpatterns = [
    path('output-schemas/export/yaml/', export_output_schemas, name='output-schemas-export-yaml'),
    path('output-schemas/sync/', sync_output_schemas, name='output-schemas-sync'),
]
