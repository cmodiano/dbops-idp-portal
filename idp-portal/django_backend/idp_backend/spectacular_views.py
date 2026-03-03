"""
Vues personnalisées pour la documentation API.
"""
from drf_spectacular.views import SpectacularSwaggerView
from drf_spectacular.settings import spectacular_settings
from rest_framework.response import Response


class SpectacularSwaggerPublicView(SpectacularSwaggerView):
    """
    Swagger UI pour le schéma public — masque la section Schemas (components)
    pour une doc plus légère destinée aux consommateurs externes.
    """
    title = 'DBOps Portal API (Public)'

    def get(self, request, *args, **kwargs):
        # defaultModelsExpandDepth: -1 masque la section Schemas en bas de page
        ui_settings = dict(spectacular_settings.SWAGGER_UI_SETTINGS)
        ui_settings['defaultModelsExpandDepth'] = -1

        return Response(
            data={
                'title': self.title,
                'swagger_ui_css': self._swagger_ui_resource('swagger-ui.css'),
                'swagger_ui_bundle': self._swagger_ui_resource('swagger-ui-bundle.js'),
                'swagger_ui_standalone': self._swagger_ui_resource('swagger-ui-standalone-preset.js'),
                'favicon_href': self._swagger_ui_favicon(),
                'schema_url': self._get_schema_url(request),
                'settings': self._dump(ui_settings),
                'oauth2_config': self._dump(spectacular_settings.SWAGGER_UI_OAUTH2_CONFIG),
                'template_name_js': self.template_name_js,
                'script_url': None,
                'csrf_header_name': self._get_csrf_header_name(),
                'schema_auth_names': self._dump(self._get_schema_auth_names()),
            },
            template_name=self.template_name,
            headers={"Cross-Origin-Opener-Policy": "unsafe-none"},
        )
