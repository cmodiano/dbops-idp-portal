from unittest.mock import patch

from pathlib import Path
from rest_framework.test import APITestCase
from rest_framework import status

from idp_auth.models import User


class HelpViewsTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create(username='testuser', profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_get_help_topic_ok(self):
        """Topic connu + fichier MD avec frontmatter → 200"""
        md_content = "---\nshort: Texte court\n---\n# Titre\n\nCorps du document."
        with patch('help.views.HELP_DIR', Path('/fake')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value=md_content):
                    resp = self.client.get('/api/v1/help/action-form-integration/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['topic_id'], 'action-form-integration')
        self.assertEqual(data['short'], 'Texte court')
        self.assertIn('# Titre', data['markdown'])
        self.assertIn('Corps du document.', data['markdown'])

    def test_get_help_topic_no_frontmatter(self):
        """Fichier MD sans frontmatter → short = première ligne, markdown = contenu complet"""
        md_content = "# Mon titre\n\nParagraphe de contenu."
        with patch('help.views.HELP_DIR', Path('/fake')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value=md_content):
                    resp = self.client.get('/api/v1/help/action-form-integration/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['short'], 'Mon titre')
        self.assertIn('# Mon titre', data['markdown'])
        self.assertIn('Paragraphe de contenu.', data['markdown'])

    def test_get_help_topic_unknown(self):
        """Topic inconnu → 404"""
        resp = self.client.get('/api/v1/help/topic-inexistant/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        data = resp.json()
        self.assertEqual(data['error']['code'], 'NOT_FOUND')

    def test_get_help_topic_file_missing(self):
        """Topic dans mapping mais fichier absent → 404"""
        with patch('help.views.HELP_DIR', Path('/fake')):
            with patch('pathlib.Path.exists', return_value=False):
                resp = self.client.get('/api/v1/help/action-form-integration/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_help_topic_unauthenticated(self):
        """Sans auth → 401"""
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/help/action-form-integration/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_help_topic_path_traversal(self):
        """Tentative de path traversal → 404 (hors mapping)"""
        resp = self.client.get('/api/v1/help/..%2F..%2F..%2Fetc%2Fpasswd/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_help_topic_invalid_yaml_frontmatter(self):
        """HELP-MED-01: Frontmatter YAML malformé → pas de 500 (fallback propre)."""
        # Frontmatter détecté (---...---) mais YAML invalide à l'intérieur
        md_content = "---\nshort: [invalid: yaml: {\n---\n# Titre\n\nCorps du document."
        with patch('help.views.HELP_DIR', Path('/fake')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value=md_content):
                    resp = self.client.get('/api/v1/help/action-form-integration/')
        # Doit retourner 200 avec fallback meta={} (short='', markdown=body)
        self.assertNotEqual(resp.status_code, 500)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['topic_id'], 'action-form-integration')
        # short vide car meta={} (pas de clé 'short')
        self.assertEqual(data['short'], '')
        # markdown = le corps après le frontmatter
        self.assertIn('# Titre', data['markdown'])
