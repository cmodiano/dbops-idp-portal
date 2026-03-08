"""
Story 64.10 — Tests de la commande management detect_drift.
"""

import json
import tempfile
from io import StringIO
from pathlib import Path

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(yaml.dump(data, allow_unicode=True).encode("utf-8"))


def _make_action_yaml(name: str) -> dict:
    return {
        "apiVersion": "idp/v1",
        "kind": "Action",
        "metadata": {"name": name},
        "spec": {
            "engine": "Oracle",
            "platform": "AAP",
            "status": "draft",
            "item_type": "action",
            "requires_target": True,
        },
    }


def _call_detect_drift(config_dir: str, **kwargs) -> StringIO:
    out = StringIO()
    call_command("detect_drift", config_dir=config_dir, stdout=out, **kwargs)
    return out


class TestDetectDriftCommand(TestCase):

    # ------------------------------------------------------------------ 2.1 in_sync
    def test_in_sync(self):
        """Entité identique en DB et YAML → in_sync."""
        from catalog.services_export_import import import_action_yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            action_data = _make_action_yaml("my-action")
            action_bytes = yaml.dump(action_data, allow_unicode=True).encode("utf-8")
            _write_yaml(config_dir / "actions" / "my-action.yaml", action_data)
            import_action_yaml(action_bytes)

            out = _call_detect_drift(str(config_dir), format="json")

        result = json.loads(out.getvalue())
        self.assertIn("my-action", result["actions"]["in_sync"])
        self.assertNotIn("my-action", result["actions"]["missing_in_db"])
        self.assertNotIn("my-action", result["actions"]["missing_in_yaml"])

    # ------------------------------------------------------------------ 2.2 missing_in_db
    def test_missing_in_db(self):
        """Entité dans YAML mais absente de DB → missing_in_db."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(
                config_dir / "actions" / "ghost-action.yaml",
                _make_action_yaml("ghost-action"),
            )
            out = _call_detect_drift(str(config_dir), format="json")

        result = json.loads(out.getvalue())
        self.assertIn("ghost-action", result["actions"]["missing_in_db"])
        self.assertNotIn("ghost-action", result["actions"]["in_sync"])

    # ------------------------------------------------------------------ 2.3 missing_in_yaml
    def test_missing_in_yaml(self):
        """Entité en DB absente du YAML → missing_in_yaml."""
        from catalog.services_export_import import import_action_yaml

        action_bytes = yaml.dump(
            _make_action_yaml("db-only-action"), allow_unicode=True
        ).encode("utf-8")
        import_action_yaml(action_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            # Répertoire actions vide — l'entité est en DB mais pas dans les YAML
            (config_dir / "actions").mkdir()
            out = _call_detect_drift(str(config_dir), format="json")

        result = json.loads(out.getvalue())
        self.assertIn("db-only-action", result["actions"]["missing_in_yaml"])
        self.assertNotIn("db-only-action", result["actions"]["in_sync"])

    # ------------------------------------------------------------------ 2.4 diverged
    def test_diverged(self):
        """Entité modifiée en DB après sync → diverged."""
        from catalog.models import Action
        from catalog.services_export_import import import_action_yaml

        action_data = _make_action_yaml("drift-action")
        action_bytes = yaml.dump(action_data, allow_unicode=True).encode("utf-8")
        import_action_yaml(action_bytes)

        # Modifier l'entité en DB directement (simule une modification via UI)
        Action.objects.filter(name="drift-action").update(description="Changed in UI")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "actions" / "drift-action.yaml", action_data)
            out = _call_detect_drift(str(config_dir), format="json")

        result = json.loads(out.getvalue())
        diverged_names = [d["name"] for d in result["actions"]["diverged"]]
        self.assertIn("drift-action", diverged_names)
        self.assertNotIn("drift-action", result["actions"]["in_sync"])

    # ------------------------------------------------------------------ 2.5 format_json
    def test_format_json(self):
        """--format json produit un JSON parsable avec toutes les clés."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = _call_detect_drift(str(tmpdir), format="json")

        result = json.loads(out.getvalue())
        self.assertIsInstance(result, dict)
        # Toutes les clés du DRIFT_ORDER doivent être présentes
        for label in ("engines", "categories", "tags", "flags", "int-types",
                      "integrations", "policies", "actions", "profiles"):
            self.assertIn(label, result)
            self.assertIn("in_sync", result[label])
            self.assertIn("diverged", result[label])
            self.assertIn("missing_in_db", result[label])
            self.assertIn("missing_in_yaml", result[label])

    # ------------------------------------------------------------------ 2.6 missing config dir ignored
    def test_missing_config_dir_ignored(self):
        """Répertoire/fichier absent dans config-dir → ignoré silencieusement avec log ⚠ sur stderr."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Aucun sous-répertoire créé → tous les patterns sont absents
            out = StringIO()
            err = StringIO()
            call_command("detect_drift", config_dir=str(tmpdir), stdout=out, stderr=err)

        # Doit contenir le symbole d'avertissement sur stderr
        self.assertIn("\u26a0", err.getvalue())
        # Ne doit pas lever d'exception (arrivé ici = pas d'erreur)

    # ------------------------------------------------------------------ 2.7 config_dir required
    def test_config_dir_required(self):
        """Sans --config-dir → SystemExit ou CommandError."""
        with self.assertRaises((SystemExit, CommandError)):
            call_command("detect_drift")

    # ------------------------------------------------------------------ format text
    def test_format_text_output(self):
        """--format text (défaut) produit un rapport texte lisible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = _call_detect_drift(str(tmpdir))

        output = out.getvalue()
        self.assertIn("R\u00e9sultat detect_drift", output)
        self.assertIn("R\u00e9sum\u00e9 global", output)
        self.assertIn("in_sync=", output)
        self.assertIn("diverged=", output)

    # ------------------------------------------------------------------ per_file absent dir
    def test_per_file_absent_dir_produces_warning(self):
        """Répertoire absent pour un type per_file → log ⚠, résultat vide."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = _call_detect_drift(str(tmpdir), format="json")

        result = json.loads(out.getvalue())
        # actions/ est absent → toutes les listes sont vides
        self.assertEqual(result["actions"]["in_sync"], [])
        self.assertEqual(result["actions"]["diverged"], [])
        self.assertEqual(result["actions"]["missing_in_db"], [])
        self.assertEqual(result["actions"]["missing_in_yaml"], [])

    # ------------------------------------------------------------------ single_file absent
    def test_single_file_absent_produces_warning(self):
        """Fichier absent pour un type single_file → log ⚠ sur stderr, résultat vide."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command("detect_drift", config_dir=str(tmpdir), stdout=out, stderr=err)

        # reference/engines.yaml est absent → avertissement sur stderr
        self.assertIn("engines.yaml", err.getvalue())

    # ------------------------------------------------------------------ in_sync tags (single_file_list)
    def test_tags_in_sync(self):
        """Tags présents à la fois en DB et YAML → in_sync.

        Note: _process_single_file_list compare directement les clés DB (via db_keys_fn)
        et les entrées du fichier YAML — export_tags_yaml n'est PAS appelé pour ce type.
        """
        from catalog.models import Tag

        Tag.objects.get_or_create(name="existing-tag")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(
                config_dir / "tags.yaml",
                {
                    "apiVersion": "idp/v1",
                    "kind": "Tags",
                    "metadata": {},
                    "spec": ["existing-tag"],
                },
            )
            out = _call_detect_drift(str(config_dir), format="json")

        result = json.loads(out.getvalue())
        self.assertIn("existing-tag", result["tags"]["in_sync"])
        self.assertEqual(result["tags"]["missing_in_db"], [])
        self.assertEqual(result["tags"]["missing_in_yaml"], [])
