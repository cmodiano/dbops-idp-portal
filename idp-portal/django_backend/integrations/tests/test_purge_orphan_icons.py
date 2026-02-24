"""
Tests for integrations management command: purge_orphan_icons.
"""

import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase

from integrations.models import Integration


@pytest.mark.django_db
class TestPurgeOrphanIcons(TestCase):
    """Tests for the purge_orphan_icons management command."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.icons_dir = self.tmp_dir / 'icons'
        self.icons_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # --- Helpers ---

    def _call(self, *args, **kwargs):
        """Call command with STATIC_ROOT patched to tmp_dir."""
        out = StringIO()
        err = StringIO()
        with patch('django.conf.settings.STATIC_ROOT', str(self.tmp_dir)):
            call_command('purge_orphan_icons', *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()

    # --- Tests ---

    def test_icons_dir_does_not_exist(self):
        """2.1 handle() — répertoire icons inexistant → WARNING + retour anticipé, pas d'exception."""
        shutil.rmtree(self.icons_dir)  # Supprimer le répertoire icons
        out, err = self._call()
        self.assertIn('does not exist', out)

    def test_empty_icons_dir_no_orphans(self):
        """2.2 handle() — répertoire icons vide → message SUCCESS 'No orphan icon files found.'"""
        out, err = self._call()
        self.assertIn('No orphan icon files found', out)

    def test_dry_run_with_orphan(self):
        """2.3 handle() — un fichier orphelin, dry-run (défaut) → liste l'orphelin + WARNING 'Dry-run mode'."""
        orphan = self.icons_dir / 'orphan.png'
        orphan.write_bytes(b'fake-icon')

        out, err = self._call()

        self.assertIn('orphan.png', out)
        self.assertIn('Dry-run mode', out)
        self.assertTrue(orphan.exists())  # Non supprimé

    def test_delete_removes_orphan(self):
        """2.4 handle() — un fichier orphelin, --delete → supprime le fichier + message SUCCESS 'Deleted 1'."""
        orphan = self.icons_dir / 'to_delete.png'
        orphan.write_bytes(b'fake-icon')

        out, err = self._call('--delete')

        self.assertIn('Deleted 1', out)
        self.assertFalse(orphan.exists())

    def test_delete_with_oserror(self):
        """2.5 handle() — plusieurs orphelins dont 1 avec OSError → deleted et errors comptés."""
        file1 = self.icons_dir / 'error_file.png'
        file2 = self.icons_dir / 'ok_file.png'
        file1.write_bytes(b'icon1')
        file2.write_bytes(b'icon2')

        real_unlink = Path.unlink

        def fake_unlink(self_path, missing_ok=False):
            # Déterministe : échoue uniquement sur error_file.png (indépendant de l'ordre d'itération)
            if self_path.name == 'error_file.png':
                raise OSError("Permission denied")
            real_unlink(self_path, missing_ok=missing_ok)

        with patch.object(Path, 'unlink', fake_unlink):
            out, err = self._call('--delete')

        self.assertIn('Deleted 1', out)
        self.assertIn('could not be deleted', err)
        self.assertFalse(file2.exists())  # ok_file supprimé
        self.assertTrue(file1.exists())   # error_file encore présent

    def test_integration_with_static_icon_is_referenced(self):
        """2.6 Integration avec icon '/static/icons/logo.png' → fichier logo.png considéré référencé (non orphelin)."""
        Integration.objects.create(
            name='TestRef Integration',
            type='aap',
            base_url='http://example.com',
            icon='/static/icons/logo.png'
        )
        referenced_file = self.icons_dir / 'logo.png'
        referenced_file.write_bytes(b'logo-icon')

        out, err = self._call()

        # Le fichier référencé ne doit pas être considéré orphelin
        self.assertIn('No orphan icon files found', out)

    def test_integration_with_non_static_icon_is_orphan(self):
        """2.7 Integration avec icon ne commençant pas par '/static/icons/' → fichier reste un orphelin."""
        Integration.objects.create(
            name='MediaRef Integration',
            type='aap',
            base_url='http://example.com',
            icon='/media/logo.png'
        )
        orphan = self.icons_dir / 'logo.png'
        orphan.write_bytes(b'logo-icon')

        out, err = self._call()

        # Le chemin /media/logo.png n'est pas reconnu → logo.png reste orphelin
        self.assertIn('logo.png', out)
        self.assertIn('Dry-run mode', out)

    def test_integration_with_none_or_empty_icon(self):
        """2.8 Integration avec icon None ou vide → aucune erreur, pas de référence ajoutée."""
        Integration.objects.create(
            name='NullIcon Integration',
            type='aap',
            base_url='http://example.com',
            icon=None
        )
        Integration.objects.create(
            name='EmptyIcon Integration',
            type='servicenow',
            base_url='http://example2.com',
            icon=''
        )
        # Aucun fichier dans icons_dir → succès simple
        out, err = self._call()
        self.assertIn('No orphan icon files found', out)

    def test_integration_with_empty_filename_after_strip(self):
        """handle() — icon '/static/icons/' → filename vide après strip, fichier non référencé (branche 45->42)."""
        Integration.objects.create(
            name='TrailingSlash Integration',
            type='aap',
            base_url='http://example.com',
            icon='/static/icons/'
        )
        orphan = self.icons_dir / 'trailing_test.png'
        orphan.write_bytes(b'icon')

        out, err = self._call()

        # Le filename vide après strip ne compte pas comme référencé → fichier reste orphelin
        self.assertIn('trailing_test.png', out)
        self.assertIn('Dry-run mode', out)

    def test_add_arguments_delete_is_store_true(self):
        """2.9 add_arguments() — vérification que --delete est un argument booléen (action='store_true')."""
        import argparse
        from integrations.management.commands.purge_orphan_icons import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        args = parser.parse_args([])
        self.assertFalse(args.delete)  # Défaut False

        args_with_delete = parser.parse_args(['--delete'])
        self.assertTrue(args_with_delete.delete)  # store_true
