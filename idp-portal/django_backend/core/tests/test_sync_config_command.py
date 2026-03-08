"""
Story 64.9 — Tests de la commande management sync_config.
"""
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(yaml.dump(data, allow_unicode=True).encode("utf-8"))


def _engines_yaml() -> dict:
    return {
        "apiVersion": "idp/v1",
        "kind": "ReferenceData",
        "metadata": {"type": "engines"},
        "spec": [{"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True}],
    }


def _integration_type_yaml(name: str = "ServiceNow") -> dict:
    return {
        "apiVersion": "idp/v1",
        "kind": "IntegrationTypeCatalogue",
        "metadata": {"name": name},
        "spec": {"label": name, "description": "desc"},
    }


def _action_yaml(name: str = "deploy-oracle") -> dict:
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


class TestSyncConfigCommand(TestCase):

    # ------------------------------------------------------------------ helpers
    def _call(self, config_dir: str, **kwargs) -> StringIO:
        out = StringIO()
        call_command("sync_config", config_dir=config_dir, stdout=out, **kwargs)
        return out

    # ------------------------------------------------------------------ 3.1 full sync additive
    @patch("core.management.commands.sync_config.import_reference_yaml", return_value=(1, 0, 0))
    def test_full_sync_additive(self, mock_import):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())

            out = self._call(str(config_dir))

        output = out.getvalue()
        self.assertIn("engines", output)
        self.assertIn("created=1", output)
        self.assertIn("Sync termin", output)
        mock_import.assert_called_once()

    # ------------------------------------------------------------------ 3.2 dry-run
    @patch("core.management.commands.sync_config.import_reference_yaml")
    def test_dry_run_makes_no_changes(self, mock_import):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())

            out = self._call(str(config_dir), dry_run=True)

        mock_import.assert_not_called()
        output = out.getvalue()
        self.assertIn("valide", output)
        self.assertIn("Dry-run termin", output)

    # ------------------------------------------------------------------ 3.3 validate-only
    @patch("core.management.commands.sync_config.import_reference_yaml")
    def test_validate_only_makes_no_changes(self, mock_import):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())

            out = self._call(str(config_dir), validate_only=True)

        mock_import.assert_not_called()
        output = out.getvalue()
        self.assertIn("valide", output)
        self.assertIn("Dry-run termin", output)

    # ------------------------------------------------------------------ 3.4 invalid yaml raises CommandError
    def test_validate_only_raises_on_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            engines_file = config_dir / "reference" / "engines.yaml"
            engines_file.parent.mkdir(parents=True, exist_ok=True)
            engines_file.write_bytes(b"apiVersion: idp/v1\nkind: INVALID_KIND\nmetadata: {}\n")

            with self.assertRaises(CommandError):
                self._call(str(config_dir), validate_only=True)

    # ------------------------------------------------------------------ 3.5 missing file is skipped
    def test_missing_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Répertoire vide — aucun fichier de config
            out = self._call(tmpdir)

        output = out.getvalue()
        # Tous les chemins absents → logs ⚠
        self.assertIn("introuvable", output)
        self.assertIn("Sync terminé", output)

    # ------------------------------------------------------------------ 3.6 mode full transmitted
    @patch("core.management.commands.sync_config.import_integration_types_yaml", return_value=(0, 1, 0))
    def test_mode_full_passed_to_services(self, mock_import):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(
                config_dir / "integration-types" / "servicenow.yaml",
                _integration_type_yaml("ServiceNow"),
            )

            self._call(str(config_dir), mode="full")

        mock_import.assert_called_once()
        _, kwargs = mock_import.call_args
        self.assertEqual(kwargs.get("mode"), "full")

    # ------------------------------------------------------------------ 3.7 config-dir required
    def test_config_dir_required(self):
        # Django's call_command raises CommandError (not SystemExit) when a required arg is missing
        with self.assertRaises((SystemExit, CommandError)):
            call_command("sync_config")

    # ------------------------------------------------------------------ 3.8 directory entities processed per file
    @patch("core.management.commands.sync_config.import_integration_types_yaml", return_value=(1, 0, 0))
    def test_directory_entities_processed_per_file(self, mock_import):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(
                config_dir / "integration-types" / "type_a.yaml",
                _integration_type_yaml("TypeA"),
            )
            _write_yaml(
                config_dir / "integration-types" / "type_b.yaml",
                _integration_type_yaml("TypeB"),
            )

            self._call(str(config_dir))

        self.assertEqual(mock_import.call_count, 2)

    # ------------------------------------------------------------------ 3.9 séquence complète multi-types (AC #2)
    @patch("core.management.commands.sync_config.import_action_yaml", return_value=(1, 0, 0))
    @patch("core.management.commands.sync_config.import_integration_types_yaml", return_value=(1, 0, 0))
    @patch("core.management.commands.sync_config.import_reference_yaml", return_value=(1, 0, 0))
    def test_multi_type_sequence_engines_inttypes_actions(self, mock_reference, mock_inttype, mock_action):
        """Séquence engines → int-types → actions : chaque service est appelé une fois,
        le rapport consolidé affiche les 3 types (AC #2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())
            _write_yaml(
                config_dir / "integration-types" / "servicenow.yaml",
                _integration_type_yaml("ServiceNow"),
            )
            _write_yaml(config_dir / "actions" / "deploy.yaml", _action_yaml())

            out = self._call(str(config_dir))

        mock_reference.assert_called_once()
        mock_inttype.assert_called_once()
        mock_action.assert_called_once()
        output = out.getvalue()
        self.assertIn("engines", output)
        self.assertIn("int-types", output)
        self.assertIn("actions", output)
        self.assertIn("Sync termin", output)

    # ------------------------------------------------------------------ 3.10 YAML invalide en milieu de séquence (AC #2)
    @patch("core.management.commands.sync_config.import_reference_yaml", return_value=(1, 0, 0))
    def test_invalid_yaml_mid_sequence_raises_command_error(self, mock_reference):
        """engines.yaml valide traité, puis integration-types/bad.yaml invalide → CommandError levée.
        Les engines ont été traités avant l'erreur (AC #2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())
            bad_file = config_dir / "integration-types" / "bad.yaml"
            bad_file.parent.mkdir(parents=True, exist_ok=True)
            # kind invalide → INVALID_KIND → levée en CommandError par le service
            bad_file.write_bytes(
                b"apiVersion: idp/v1\nkind: INVALID_KIND\nmetadata: {}\nspec: {}\n"
            )

            with self.assertRaises(CommandError):
                self._call(str(config_dir))

        # engines.yaml a été traité (avant l'erreur)
        mock_reference.assert_called_once()

    # ------------------------------------------------------------------ 3.11 dry-run multi-types (AC #2)
    @patch("core.management.commands.sync_config.import_reference_yaml")
    @patch("core.management.commands.sync_config.import_action_yaml")
    def test_dry_run_multi_types_no_services_called(self, mock_action, mock_reference):
        """Dry-run avec plusieurs types → aucun service d'import appelé, fichiers validés (AC #2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())
            _write_yaml(config_dir / "actions" / "deploy.yaml", _action_yaml())

            out = self._call(str(config_dir), dry_run=True)

        mock_reference.assert_not_called()
        mock_action.assert_not_called()
        output = out.getvalue()
        self.assertIn("Dry-run termin", output)

    # ------------------------------------------------------------------ 3.12 rapport consolidé multi-types (AC #2)
    @patch("core.management.commands.sync_config.import_integration_types_yaml", return_value=(0, 1, 2))
    @patch("core.management.commands.sync_config.import_reference_yaml", return_value=(2, 0, 0))
    def test_consolidated_report_sums_all_types(self, mock_reference, mock_inttype):
        """Le rapport final cumule les compteurs de tous les types traités (AC #2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            _write_yaml(config_dir / "reference" / "engines.yaml", _engines_yaml())
            _write_yaml(
                config_dir / "integration-types" / "type_a.yaml",
                _integration_type_yaml("TypeA"),
            )

            out = self._call(str(config_dir))

        output = out.getvalue()
        self.assertIn("engines", output)
        self.assertIn("int-types", output)
        self.assertIn("created=2", output)   # engines : 2 créés
        self.assertIn("updated=1", output)   # int-types : 1 mis à jour
        self.assertIn("Sync termin", output)
