"""
URL configuration for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).

Public endpoints: GET /api/v1/output-schemas/ and /api/v1/output-schemas/{id}/
Admin IaC endpoints: GET /api/v1/admin/output-schemas/export/yaml/
                     POST /api/v1/admin/output-schemas/sync/
"""

from rest_framework.routers import DefaultRouter
from output_schemas.views import (
    OutputSchemaViewSet,
)

router = DefaultRouter()
router.register(r'output-schemas', OutputSchemaViewSet, basename='output-schema')

# Public endpoints (registered via path('api/v1/', include('output_schemas.urls')))
urlpatterns = router.urls
