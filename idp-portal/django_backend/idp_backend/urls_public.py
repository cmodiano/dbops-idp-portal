"""
URL configuration for public API only.
Used by Swagger UI public schema — excludes admin, audit, dashboard, inventory, profiles, etc.
"""
from django.urls import path, include

# Public API: catalog (no admin), auth, executions, integrations types, reference (no admin)
# Excluded: admin_analytics, audit, dashboard, profiles, inventory, help, catalog admin, reference admin
urlpatterns = [
    path('api/v1/', include('catalog.urls_public')),
    path('api/v1/', include('idp_auth.urls')),
    path('api/v1/', include('executions.urls')),
    path('api/v1/', include('core.urls')),
    path('api/v1/', include('reference.urls')),
    path('api/v1/', include('integrations.urls_public')),
]
