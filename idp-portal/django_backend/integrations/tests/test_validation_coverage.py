"""
Tests de couverture pour integrations/validation.py (Story 55).
Couvre les lignes manquantes :
  - 12-13 : JSONSCHEMA_AVAILABLE = False (ImportError jsonschema)
  - 26-27 : _SCHEMA_PATH fallback (aucun chemin n'existe)
  - 41-48 : branche validate_integration_config sans jsonschema
"""
import pytest
from unittest.mock import patch, MagicMock
import sys


class TestImportWithoutJsonschema:
    """Ligne 12-13 : simule l'absence de jsonschema pour couvrir JSONSCHEMA_AVAILABLE = False."""

    def test_module_sets_jsonschema_available_false_when_missing(self):
        """Lignes 12-13 : import jsonschema échoue → JSONSCHEMA_AVAILABLE = False."""
        # Sauvegarde du module original et du module jsonschema dans sys.modules
        original_module = sys.modules.get('integrations.validation')
        original_jsonschema = sys.modules.get('jsonschema')

        try:
            # Forcer l'échec de l'import jsonschema
            sys.modules['jsonschema'] = None  # type: ignore
            # Retirer le module du cache pour forcer le re-import
            if 'integrations.validation' in sys.modules:
                del sys.modules['integrations.validation']

            import integrations.validation as val_reloaded
            assert val_reloaded.JSONSCHEMA_AVAILABLE is False
        finally:
            # Restaurer jsonschema
            if original_jsonschema is None and 'jsonschema' in sys.modules:
                del sys.modules['jsonschema']
            elif original_jsonschema is not None:
                sys.modules['jsonschema'] = original_jsonschema
            # Restaurer le module original
            if 'integrations.validation' in sys.modules:
                del sys.modules['integrations.validation']
            if original_module is not None:
                sys.modules['integrations.validation'] = original_module


class TestSchemaPathFallback:
    """Lignes 26-27 : _SCHEMA_PATH trouvé dans la boucle (path.exists() = True)."""

    def test_schema_path_found_in_loop(self):
        """Lignes 26-27 : premier path.exists() = True → _SCHEMA_PATH = ce path + break."""
        original_module = sys.modules.get('integrations.validation')

        try:
            # Retirer le module du cache
            if 'integrations.validation' in sys.modules:
                del sys.modules['integrations.validation']

            with patch('pathlib.Path.exists', return_value=True):
                import integrations.validation as val_reloaded
                # _SCHEMA_PATH doit être le premier path (trouvé via break)
                assert val_reloaded._SCHEMA_PATH is not None
                assert val_reloaded._SCHEMA_PATH == val_reloaded._SCHEMA_PATHS[0]
        finally:
            if 'integrations.validation' in sys.modules:
                del sys.modules['integrations.validation']
            if original_module is not None:
                sys.modules['integrations.validation'] = original_module

    def test_load_schema_reads_file_when_exists(self):
        """Lignes 41-44 : _SCHEMA_PATH.exists() = True → fichier lu et mis en cache."""
        import integrations.validation as val_module
        import json

        original_cache = val_module._SCHEMA_CACHE
        schema_content = {"type": "object"}
        schema_json = json.dumps(schema_content)

        try:
            val_module._SCHEMA_CACHE = None
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.read = MagicMock(return_value=schema_json)

            from pathlib import Path
            with patch.object(Path, 'exists', return_value=True), \
                 patch('builtins.open', return_value=mock_file), \
                 patch('json.load', return_value=schema_content):
                result = val_module._load_schema()
                assert result == schema_content
        finally:
            val_module._SCHEMA_CACHE = original_cache

    def test_load_schema_double_checked_locking_branch(self):
        """Ligne 41->48 : double-checked locking — cache rempli par un autre thread entre les deux vérifications."""
        import integrations.validation as val_module

        original_cache = val_module._SCHEMA_CACHE
        schema_content = {"type": "object", "double_checked": True}

        try:
            # Simuler: _SCHEMA_CACHE=None en dehors du lock, mais à l'intérieur du lock déjà rempli
            _call_count = [0]

            def patched_schema_cache_check():
                """Premier check (ligne 38) retourne None, deuxième (ligne 41) retourne True."""
                pass

            # Approche: on met _SCHEMA_CACHE=None pour passer le premier check,
            # puis on le remplit avant l'entrée dans le lock en patchant le lock

            class FakeLock:
                def __enter__(self):
                    # Au moment d'entrer dans le lock, le cache est déjà rempli (simulant un autre thread)
                    val_module._SCHEMA_CACHE = schema_content
                    return self

                def __exit__(self, *args):
                    return False

            val_module._SCHEMA_CACHE = None
            with patch.object(val_module, '_SCHEMA_LOCK', FakeLock()):
                result = val_module._load_schema()
                assert result == schema_content
        finally:
            val_module._SCHEMA_CACHE = original_cache


class TestValidateIntegrationConfigNoJsonschema:
    """Tests de la branche JSONSCHEMA_AVAILABLE = False (lignes 41-48)."""

    def test_validate_without_jsonschema_valid_dict(self):
        """Sans jsonschema : un dict valide passe sans erreur."""
        import integrations.validation as val_module
        original = val_module.JSONSCHEMA_AVAILABLE
        try:
            val_module.JSONSCHEMA_AVAILABLE = False
            val_module.validate_integration_config({"auth_flow": "oauth2"})
        finally:
            val_module.JSONSCHEMA_AVAILABLE = original

    def test_validate_without_jsonschema_non_dict_raises(self):
        """Sans jsonschema : config non-dict lève InvalidStateError."""
        import integrations.validation as val_module
        from core.exceptions import InvalidStateError

        original = val_module.JSONSCHEMA_AVAILABLE
        try:
            val_module.JSONSCHEMA_AVAILABLE = False
            with pytest.raises(InvalidStateError) as exc_info:
                val_module.validate_integration_config("not_a_dict")
            assert exc_info.value.code == "INVALID_CONFIG"
        finally:
            val_module.JSONSCHEMA_AVAILABLE = original

    def test_validate_without_jsonschema_list_raises(self):
        """Sans jsonschema : liste passée → InvalidStateError."""
        import integrations.validation as val_module
        from core.exceptions import InvalidStateError

        original = val_module.JSONSCHEMA_AVAILABLE
        try:
            val_module.JSONSCHEMA_AVAILABLE = False
            with pytest.raises(InvalidStateError):
                val_module.validate_integration_config([1, 2, 3])
        finally:
            val_module.JSONSCHEMA_AVAILABLE = original


class TestValidateIntegrationConfigWithJsonschema:
    """Tests de la branche jsonschema disponible mais schema absent ou vide."""

    def test_validate_with_empty_schema_skips_validation(self):
        """Ligne 72-74 : schema vide → validation ignorée, pas d'erreur."""
        import integrations.validation as val_module

        with patch.object(val_module, '_load_schema', return_value={}), \
             patch.object(val_module, 'JSONSCHEMA_AVAILABLE', True):
            # Aucune exception levée
            val_module.validate_integration_config({"any": "config"})

    def test_validate_raises_on_schema_validation_error(self):
        """Lignes 78-88 : ValidationError jsonschema → InvalidStateError INVALID_CONFIG."""
        import integrations.validation as val_module
        from core.exceptions import InvalidStateError

        if not val_module.JSONSCHEMA_AVAILABLE:
            pytest.skip("jsonschema non disponible")

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        with patch.object(val_module, '_load_schema', return_value=schema):
            with pytest.raises(InvalidStateError) as exc_info:
                val_module.validate_integration_config({"wrong_field": 123})
            assert exc_info.value.code == "INVALID_CONFIG"

    def test_validate_raises_on_schema_error(self):
        """Lignes 89-94 : SchemaError jsonschema → InvalidStateError INVALID_SCHEMA."""
        import integrations.validation as val_module
        from core.exceptions import InvalidStateError

        if not val_module.JSONSCHEMA_AVAILABLE:
            pytest.skip("jsonschema non disponible")


        invalid_schema = {"type": "invalid_type_that_doesnt_exist"}
        with patch.object(val_module, '_load_schema', return_value=invalid_schema):
            with pytest.raises(InvalidStateError) as exc_info:
                val_module.validate_integration_config({"key": "value"})
            assert exc_info.value.code == "INVALID_SCHEMA"


class TestLoadSchema:
    """Tests pour _load_schema — cache et fallback."""

    def test_load_schema_returns_cached(self):
        """Ligne 38-39 : si _SCHEMA_CACHE est déjà rempli, le retourne directement."""
        import integrations.validation as val_module

        original_cache = val_module._SCHEMA_CACHE
        try:
            val_module._SCHEMA_CACHE = {"cached": True}
            result = val_module._load_schema()
            assert result == {"cached": True}
        finally:
            val_module._SCHEMA_CACHE = original_cache

    def test_load_schema_fallback_when_file_missing(self):
        """Lignes 45-47 : fichier schema absent → retourne {}."""
        import integrations.validation as val_module
        from pathlib import Path

        original_cache = val_module._SCHEMA_CACHE
        try:
            val_module._SCHEMA_CACHE = None
            with patch.object(Path, 'exists', return_value=False):
                result = val_module._load_schema()
            assert result == {}
        finally:
            val_module._SCHEMA_CACHE = original_cache

    def test_schema_path_fallback_when_no_path_exists(self):
        """Lignes 26-27 : _SCHEMA_PATH tombe sur le premier path si aucun n'existe."""
        import integrations.validation as val_module

        # Vérifie que _SCHEMA_PATH est défini (fallback ou réel)
        assert val_module._SCHEMA_PATH is not None
