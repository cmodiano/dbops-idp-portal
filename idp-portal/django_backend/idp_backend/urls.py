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

urlpatterns = [
    path('admin/', admin.site.urls),
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
    # Story 2.30: Admin CRUD categories
    path('api/v1/admin/', include('reference.admin_urls')),
]

# Serve uploaded integration icons in development
if settings.DEBUG:
    from django.views.static import serve
    from pathlib import Path
    _icons_root = Path(settings.BASE_DIR) / 'static' / 'icons'
    urlpatterns += [
        path('static/icons/<path:path>', serve, {'document_root': _icons_root}),
    ]
