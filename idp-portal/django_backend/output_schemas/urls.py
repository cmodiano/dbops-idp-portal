"""
URL configuration for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
Story 63.2 - Registre des Schémas & Résolution (endpoints discovery).
Story 63.9 - Déclarer les outputs par action (endpoint action schema).

Public endpoints: GET /api/v1/output-schemas/ and /api/v1/output-schemas/{id}/
Admin CaC endpoints: GET /api/v1/admin/output-schemas/export/yaml/
                     POST /api/v1/admin/output-schemas/sync/
Discovery endpoints: GET /api/v1/output-schemas/workflows/{id}/steps/{step_id}/output-schema/
                     GET /api/v1/output-schemas/workflows/{id}/available-variables/
                     GET /api/v1/output-schemas/actions/{action_id}/schema/
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from output_schemas.views import (
    OutputSchemaViewSet,
    get_action_output_schema,
    get_available_variables,
    get_step_output_schema,
)

router = DefaultRouter()
router.register(r'output-schemas', OutputSchemaViewSet, basename='output-schema')

# Public endpoints (registered via path('api/v1/', include('output_schemas.urls')))
urlpatterns = router.urls + [
    path(
        'output-schemas/workflows/<int:workflow_id>/steps/<str:step_id>/output-schema/',
        get_step_output_schema,
        name='output-schema-step',
    ),
    path(
        'output-schemas/workflows/<int:workflow_id>/available-variables/',
        get_available_variables,
        name='output-schema-available-variables',
    ),
    # Story 63.9: Schéma résolu pour une action donnée
    path(
        'output-schemas/actions/<int:action_id>/schema/',
        get_action_output_schema,
        name='output-schema-action',
    ),
]
