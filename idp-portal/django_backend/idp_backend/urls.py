"""
URL configuration for idp_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from executions.views.github_webhooks import github_webhook_workflow_run as _github_webhook_workflow_run
from executions.views.terraform_webhooks import terraform_webhook_run as _terraform_webhook_run

urlpatterns = [
    path('admin/', admin.site.urls),
    # Story 22.20: OpenAPI schema and documentation views
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/v1/', include('core.urls')),
    path('api/v1/', include('catalog.urls')),
    path('api/v1/', include('executions.urls')),
    path('api/v1/', include('dashboard.urls')),
    path('api/v1/', include('audit.urls')),
    path('api/v1/', include('idp_auth.urls')),
    path('api/v1/', include('integrations.urls')),
    path('api/v1/admin/', include('admin_analytics.urls')),
    path('api/v1/admin/', include('profiles.urls')),
    path('api/v1/inventory/', include('inventory.urls')),
    path('api/v1/reference/', include('reference.urls')),
    path('api/v1/', include('help.urls')),  # Story 31.7 - Aide contextuelle
    # Story 2.30: Admin CRUD categories
    path('api/v1/admin/', include('reference.admin_urls')),
    # Story 27.4: GitHub Actions webhook (HMAC-secured, no DRF auth)
    path(
        'api/v1/webhooks/github/workflow_run',
        _github_webhook_workflow_run,
        name='github-webhook-workflow-run',
    ),
    # Story 27.5: Terraform Cloud webhook (HMAC SHA-512 secured, no DRF auth)
    path(
        'api/v1/webhooks/terraform/run',
        _terraform_webhook_run,
        name='terraform-webhook-run',
    ),
]

# Serve static files in development (admin, jazzmin, icons)
# Required when using Daphne/ASGI — runserver serves them automatically, ASGI does not.
if settings.DEBUG:
    from django.conf.urls.static import static
    from django.views.static import serve
    from pathlib import Path

    _static_root = getattr(settings, 'STATIC_ROOT', None) or (Path(settings.BASE_DIR) / 'static')
    _icons_root = Path(_static_root) / 'icons'

    # Admin + Jazzmin CSS/JS (from STATIC_ROOT after collectstatic)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Fallback: icons if not in STATIC_ROOT yet
    urlpatterns += [
        path('static/icons/<path:path>', serve, {'document_root': _icons_root}),
    ]
