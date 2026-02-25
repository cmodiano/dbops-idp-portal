"""
Tests de configuration django-jazzmin.
Story 45.2 — Installer et configurer un thème Admin.
Story 45.4 — Regrouper et organiser les modèles par domaine.

Ces tests vérifient que :
1. jazzmin est présent dans INSTALLED_APPS AVANT django.contrib.admin (AC2)
2. JAZZMIN_SETTINGS configure correctement la sidebar, le titre, la recherche (AC3, AC4)
3. JAZZMIN_UI_TWEAKS active le toggle dark/light mode (AC5)
4. La contrainte d'ordre INSTALLED_APPS (daphne > jazzmin > django.contrib.admin) est respectée
5. IdpAuthConfig.verbose_name est correctement défini (Story 45.4 AC1)
6. JAZZMIN_SETTINGS["order_with_respect_to"] place auth avant idp_auth (Story 45.4 AC3)
"""

from django.apps import apps as django_apps
from django.conf import settings
from django.test import TestCase


class TestJazzminInstalledApps(TestCase):
    """Vérifie que jazzmin est correctement positionné dans INSTALLED_APPS (AC2)."""

    def test_jazzmin_in_installed_apps(self):
        """jazzmin doit être présent dans INSTALLED_APPS."""
        self.assertIn(
            'jazzmin',
            settings.INSTALLED_APPS,
            "jazzmin doit être dans INSTALLED_APPS pour que le thème admin soit actif.",
        )

    def test_jazzmin_before_django_contrib_admin(self):
        """jazzmin doit apparaître AVANT django.contrib.admin dans INSTALLED_APPS.

        Si jazzmin est après django.contrib.admin, ses templates ne sont pas chargés
        et l'interface admin utilise le thème Django par défaut.
        """
        apps = list(settings.INSTALLED_APPS)
        self.assertIn('django.contrib.admin', apps, "django.contrib.admin doit être dans INSTALLED_APPS.")
        jazzmin_index = apps.index('jazzmin')
        admin_index = apps.index('django.contrib.admin')
        self.assertLess(
            jazzmin_index,
            admin_index,
            f"jazzmin (position {jazzmin_index}) doit être AVANT django.contrib.admin "
            f"(position {admin_index}) dans INSTALLED_APPS.",
        )

    def test_daphne_remains_first(self):
        """daphne doit rester en première position (contrainte WebSocket Story 22.13)."""
        apps = list(settings.INSTALLED_APPS)
        self.assertEqual(
            apps[0],
            'daphne',
            "daphne doit rester en première position dans INSTALLED_APPS (contrainte WebSocket).",
        )

    def test_installed_apps_order_daphne_jazzmin_admin(self):
        """L'ordre daphne > jazzmin > django.contrib.admin doit être respecté simultanément."""
        apps = list(settings.INSTALLED_APPS)
        daphne_index = apps.index('daphne')
        jazzmin_index = apps.index('jazzmin')
        admin_index = apps.index('django.contrib.admin')
        self.assertLess(daphne_index, jazzmin_index, "daphne doit précéder jazzmin.")
        self.assertLess(jazzmin_index, admin_index, "jazzmin doit précéder django.contrib.admin.")


class TestJazzminSettings(TestCase):
    """Vérifie que JAZZMIN_SETTINGS est correctement configuré (AC3, AC4)."""

    def test_jazzmin_settings_defined(self):
        """JAZZMIN_SETTINGS doit être défini dans les settings."""
        self.assertTrue(
            hasattr(settings, 'JAZZMIN_SETTINGS'),
            "JAZZMIN_SETTINGS doit être défini dans settings.py.",
        )

    def test_site_title_configured(self):
        """Le titre de l'onglet navigateur doit être personnalisé (AC4)."""
        self.assertEqual(
            settings.JAZZMIN_SETTINGS.get('site_title'),
            'IDP Portal Admin',
            "site_title doit être 'IDP Portal Admin' (AC4).",
        )

    def test_site_header_configured(self):
        """L'en-tête de l'admin doit être personnalisé (AC4)."""
        self.assertIn(
            'IDP Portal',
            settings.JAZZMIN_SETTINGS.get('site_header', ''),
            "site_header doit contenir 'IDP Portal' (AC4).",
        )

    def test_sidebar_enabled(self):
        """La sidebar de navigation doit être activée (AC3)."""
        self.assertTrue(
            settings.JAZZMIN_SETTINGS.get('show_sidebar'),
            "show_sidebar doit être True pour afficher la sidebar de navigation (AC3).",
        )

    def test_ui_builder_disabled(self):
        """show_ui_builder doit être désactivé pour éviter les modifications accidentelles en prod."""
        self.assertFalse(
            settings.JAZZMIN_SETTINGS.get('show_ui_builder'),
            "show_ui_builder doit être False (risque de modification accidentelle en production).",
        )

    def test_google_fonts_cdn_disabled(self):
        """use_google_fonts_cdn doit être False pour éviter les requêtes CDN externes."""
        self.assertFalse(
            settings.JAZZMIN_SETTINGS.get('use_google_fonts_cdn'),
            "use_google_fonts_cdn doit être False (sécurité intranet).",
        )


class TestJazzminUiTweaks(TestCase):
    """Vérifie que JAZZMIN_UI_TWEAKS active le toggle dark/light mode (AC5)."""

    def test_jazzmin_ui_tweaks_defined(self):
        """JAZZMIN_UI_TWEAKS doit être défini dans les settings."""
        self.assertTrue(
            hasattr(settings, 'JAZZMIN_UI_TWEAKS'),
            "JAZZMIN_UI_TWEAKS doit être défini dans settings.py.",
        )

    def test_dark_mode_theme_configured(self):
        """dark_mode_theme doit être configuré pour activer le toggle dark/light (AC5)."""
        dark_mode = settings.JAZZMIN_UI_TWEAKS.get('dark_mode_theme')
        self.assertIsNotNone(
            dark_mode,
            "dark_mode_theme doit être défini dans JAZZMIN_UI_TWEAKS pour activer le toggle (AC5).",
        )
        self.assertNotEqual(
            dark_mode,
            '',
            "dark_mode_theme ne doit pas être vide (AC5).",
        )

    def test_sidebar_dark_configured(self):
        """La sidebar sombre doit être configurée pour distinguer visuellement la navigation."""
        self.assertEqual(
            settings.JAZZMIN_UI_TWEAKS.get('sidebar'),
            'sidebar-dark-primary',
            "sidebar doit être 'sidebar-dark-primary' pour une sidebar sombre distinctive.",
        )


class TestIdpAuthAppConfig(TestCase):
    """Vérifie la configuration AppConfig de idp_auth (Story 45.4 — AC1)."""

    def test_idp_auth_verbose_name(self):
        """verbose_name de idp_auth doit être 'Authentification SAML & Clés API' (AC1).

        jazzmin utilise AppConfig.verbose_name comme libellé de section dans la sidebar.
        Ce test fige la valeur — toute modification accidentelle sera immédiatement détectée.
        """
        app_config = django_apps.get_app_config('idp_auth')
        self.assertEqual(
            app_config.verbose_name,
            "Authentification SAML & Clés API",
            "IdpAuthConfig.verbose_name doit être 'Authentification SAML & Clés API' "
            "pour que la sidebar jazzmin affiche le bon libellé de section (Story 45.4 AC1).",
        )


class TestJazzminSidebarOrder(TestCase):
    """Vérifie l'ordre de la sidebar jazzmin (Story 45.4 — AC3)."""

    def test_order_with_respect_to_configured(self):
        """JAZZMIN_SETTINGS doit contenir la clé order_with_respect_to (AC3)."""
        self.assertIn(
            'order_with_respect_to',
            settings.JAZZMIN_SETTINGS,
            "order_with_respect_to doit être défini dans JAZZMIN_SETTINGS pour contrôler "
            "l'ordre de la sidebar (Story 45.4 AC3).",
        )

    def test_auth_before_idp_auth_in_sidebar(self):
        """auth doit précéder idp_auth dans order_with_respect_to (AC3).

        Règle métier : la section authentification Django (Users/Groups admin) précède
        la section authentification SAML/DBOPS (idp_auth).
        """
        order = settings.JAZZMIN_SETTINGS.get('order_with_respect_to', [])
        self.assertIn('auth', order, "auth doit être dans order_with_respect_to.")
        self.assertIn('idp_auth', order, "idp_auth doit être dans order_with_respect_to.")
        auth_index = order.index('auth')
        idp_auth_index = order.index('idp_auth')
        self.assertLess(
            auth_index,
            idp_auth_index,
            f"auth (position {auth_index}) doit précéder idp_auth (position {idp_auth_index}) "
            "dans order_with_respect_to (Story 45.4 AC3).",
        )
