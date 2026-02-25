"""
Tests de configuration des fichiers statiques Django admin.
Story 45.1 — Corriger les icônes manquantes.

Ces tests vérifient que :
1. STATIC_ROOT est configuré (requis pour collectstatic en production)
2. STATICFILES_FINDERS inclut AppDirectoriesFinder (requis pour servir les icônes admin)
3. Les fichiers statiques Django admin sont détectables par les finders configurés
4. Pas de régression sur les fonctionnalités admin existantes
"""

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase


class TestStaticFilesConfiguration(TestCase):
    """Vérifie que la configuration des fichiers statiques est correcte (AC: 1, 2, 3)."""

    def test_static_root_is_configured(self):
        """STATIC_ROOT doit être défini pour que collectstatic fonctionne en production."""
        self.assertTrue(
            hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT,
            "STATIC_ROOT doit être défini dans settings.py pour que collectstatic fonctionne."
        )

    def test_static_root_is_not_same_as_staticfiles_dirs(self):
        """STATIC_ROOT ne doit pas être dans STATICFILES_DIRS (erreur collectstatic courante)."""
        static_root = settings.STATIC_ROOT
        for d in settings.STATICFILES_DIRS:
            self.assertNotEqual(
                str(static_root), str(d),
                "STATIC_ROOT ne doit pas être dans STATICFILES_DIRS."
            )

    def test_app_directories_finder_configured(self):
        """AppDirectoriesFinder doit être dans STATICFILES_FINDERS pour servir les icônes Django admin."""
        app_finder = 'django.contrib.staticfiles.finders.AppDirectoriesFinder'
        self.assertIn(
            app_finder,
            settings.STATICFILES_FINDERS,
            "AppDirectoriesFinder doit être dans STATICFILES_FINDERS."
        )

    def test_filesystem_finder_configured(self):
        """FileSystemFinder doit être dans STATICFILES_FINDERS pour servir les fichiers projet."""
        fs_finder = 'django.contrib.staticfiles.finders.FileSystemFinder'
        self.assertIn(
            fs_finder,
            settings.STATICFILES_FINDERS,
            "FileSystemFinder doit être dans STATICFILES_FINDERS."
        )

    def test_static_url_is_set(self):
        """STATIC_URL doit être configuré."""
        self.assertEqual(settings.STATIC_URL, '/static/')

    def test_django_contrib_staticfiles_in_installed_apps(self):
        """django.contrib.staticfiles doit être dans INSTALLED_APPS."""
        self.assertIn('django.contrib.staticfiles', settings.INSTALLED_APPS)

    def test_django_contrib_admin_in_installed_apps(self):
        """django.contrib.admin doit être dans INSTALLED_APPS."""
        self.assertIn('django.contrib.admin', settings.INSTALLED_APPS)


class TestAdminStaticFilesDiscovery(TestCase):
    """Vérifie que les fichiers statiques Django admin sont détectables (AC: 3)."""

    def test_admin_icon_yes_svg_found(self):
        """L'icône admin icon-yes.svg doit être trouvable via les finders."""
        result = finders.find('admin/img/icon-yes.svg')
        self.assertIsNotNone(
            result,
            "admin/img/icon-yes.svg introuvable. Vérifier AppDirectoriesFinder et INSTALLED_APPS."
        )

    def test_admin_icon_no_svg_found(self):
        """L'icône admin icon-no.svg doit être trouvable via les finders."""
        result = finders.find('admin/img/icon-no.svg')
        self.assertIsNotNone(result, "admin/img/icon-no.svg introuvable.")

    def test_admin_dark_mode_css_found(self):
        """Le CSS du toggle de thème Django 5.x doit être trouvable (AC: 2)."""
        result = finders.find('admin/css/dark_mode.css')
        self.assertIsNotNone(
            result,
            "admin/css/dark_mode.css introuvable. Le toggle de thème ne fonctionnera pas."
        )

    def test_admin_base_css_found(self):
        """Le CSS de base Django admin doit être trouvable."""
        result = finders.find('admin/css/base.css')
        self.assertIsNotNone(result, "admin/css/base.css introuvable.")

    def test_admin_search_icon_svg_found(self):
        """L'icône de recherche Django admin doit être trouvable."""
        result = finders.find('admin/img/search.svg')
        self.assertIsNotNone(result, "admin/img/search.svg introuvable.")

    def test_admin_changelist_js_found(self):
        """Le JavaScript Django admin doit être trouvable."""
        result = finders.find('admin/js/change_form.js')
        self.assertIsNotNone(result, "admin/js/change_form.js introuvable.")
