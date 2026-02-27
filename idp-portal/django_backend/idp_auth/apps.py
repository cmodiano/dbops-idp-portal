from django.apps import AppConfig


class IdpAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'idp_auth'
    # Libellé affiché dans la sidebar Django Admin (jazzmin respecte AppConfig.verbose_name)
    verbose_name = "Authentification SAML & Clés API"
