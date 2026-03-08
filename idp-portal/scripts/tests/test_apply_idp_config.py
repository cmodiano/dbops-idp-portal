"""
Tests unitaires pour scripts/apply_idp_config.py

Couverture :
  - validate-only avec fichiers valides (exit 0)
  - validate-only avec fichier invalide (exit 1)
  - dry-run : aucun appel HTTP effectué
  - sync success : résumé created/updated/unchanged
  - sync HTTP error : exit 1 et arrêt des syncs suivants
  - missing env var : exit 1 avec message explicite
"""
import sys
import textwrap
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch, call

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers — création de fichiers YAML valides / invalides
# ---------------------------------------------------------------------------

VALID_ENVELOPE = {
    "apiVersion": "idp/v1",
    "kind": "ReferenceEngine",
    "metadata": {"name": "test-engine"},
    "spec": {"type": "oauth2"},
}

INVALID_ENVELOPE_MISSING_KEY = {
    "apiVersion": "idp/v1",
    "kind": "ReferenceEngine",
    # metadata manquant
    "spec": {"type": "oauth2"},
}

INVALID_ENVELOPE_BAD_API_VERSION = {
    "apiVersion": "wrong/v2",
    "kind": "ReferenceEngine",
    "metadata": {"name": "test"},
    "spec": {},
}


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f)


def make_valid_config_dir(tmp_path: Path) -> Path:
    """Crée un répertoire de config minimal avec tous les fichiers nécessaires."""
    config = tmp_path / "idp-config"
    # single-file entries
    write_yaml(config / "reference" / "engines.yaml", VALID_ENVELOPE)
    write_yaml(config / "reference" / "categories.yaml", VALID_ENVELOPE)
    write_yaml(config / "tags.yaml", VALID_ENVELOPE)
    write_yaml(config / "feature-flags.yaml", VALID_ENVELOPE)
    # per-file entries — un fichier chacun
    write_yaml(config / "integration-types" / "type-a.yaml", VALID_ENVELOPE)
    write_yaml(config / "integrations" / "int-a.yaml", VALID_ENVELOPE)
    write_yaml(config / "policies" / "pol-a.yaml", VALID_ENVELOPE)
    write_yaml(config / "actions" / "act-a.yaml", VALID_ENVELOPE)
    write_yaml(config / "profiles" / "prof-a.yaml", VALID_ENVELOPE)
    return config


# ---------------------------------------------------------------------------
# Importer le module en ajustant sys.path
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def add_scripts_to_path(tmp_path):
    scripts_dir = str(Path(__file__).parents[1])
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    yield
    # Cleanup n'est pas nécessaire pour les tests


import apply_idp_config as script


# ---------------------------------------------------------------------------
# Test 3.2 — validate-only avec tous les fichiers valides → exit 0
# ---------------------------------------------------------------------------

def test_validate_only_valid(tmp_path, capsys):
    config = make_valid_config_dir(tmp_path)
    exit_code = script.main(["--validate-only", "--dir", str(config)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Validation OK" in captured.out


# ---------------------------------------------------------------------------
# Test 3.3 — validate-only avec un fichier invalide → exit 1
# ---------------------------------------------------------------------------

def test_validate_only_invalid(tmp_path, capsys):
    config = make_valid_config_dir(tmp_path)
    # Remplacer un fichier valide par un invalide
    write_yaml(config / "tags.yaml", INVALID_ENVELOPE_MISSING_KEY)

    exit_code = script.main(["--validate-only", "--dir", str(config)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "metadata" in captured.err or "Clé manquante" in captured.err


def test_validate_only_invalid_api_version(tmp_path, capsys):
    config = make_valid_config_dir(tmp_path)
    write_yaml(config / "feature-flags.yaml", INVALID_ENVELOPE_BAD_API_VERSION)

    exit_code = script.main(["--validate-only", "--dir", str(config)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "apiVersion" in captured.err


# ---------------------------------------------------------------------------
# Test 3.4 — dry-run : aucun appel HTTP effectué
# ---------------------------------------------------------------------------

def test_dry_run_prints_requests_no_http(tmp_path, capsys, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.setenv("IDP_API_URL", "https://idp.example.com")
    monkeypatch.setenv("IDP_API_TOKEN", "test-token")

    with patch("requests.post") as mock_post:
        exit_code = script.main(["--dry-run", "--dir", str(config)])
        mock_post.assert_not_called()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[DRY-RUN]" in captured.out
    assert "POST" in captured.out


# ---------------------------------------------------------------------------
# Test 3.5 — sync success : vérifie résumé created/updated/unchanged
# ---------------------------------------------------------------------------

def test_sync_success(tmp_path, capsys, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.setenv("IDP_API_URL", "https://idp.example.com")
    monkeypatch.setenv("IDP_API_TOKEN", "test-token")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"created": 1, "updated": 2, "unchanged": 3, "mode": "additive"}
    }

    with patch("requests.post", return_value=mock_response):
        exit_code = script.main(["--dir", str(config)])

    assert exit_code == 0
    captured = capsys.readouterr()
    # Le résumé doit contenir les totaux
    assert "Résumé" in captured.out
    assert "créés" in captured.out or "TOTAL" in captured.out


# ---------------------------------------------------------------------------
# Test 3.6 — sync HTTP error : exit 1 et arrêt (entités suivantes non appelées)
# ---------------------------------------------------------------------------

def test_sync_http_error_stops(tmp_path, capsys, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.setenv("IDP_API_URL", "https://idp.example.com")
    monkeypatch.setenv("IDP_API_TOKEN", "test-token")

    mock_error_response = MagicMock()
    mock_error_response.status_code = 422
    mock_error_response.text = '{"error": {"code": "INVALID_YAML_SYNTAX", "message": "bad yaml"}}'

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_error_response

    with patch("requests.post", side_effect=side_effect):
        exit_code = script.main(["--dir", str(config)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "422" in captured.err or "HTTP" in captured.err
    # Doit s'arrêter au premier échec : seulement 1 appel effectué
    assert call_count == 1


# ---------------------------------------------------------------------------
# Test 3.7 — missing env var → exit 1 avec message explicite
# ---------------------------------------------------------------------------

def test_missing_env_var_both(tmp_path, capsys, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.delenv("IDP_API_URL", raising=False)
    monkeypatch.delenv("IDP_API_TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        script.main(["--dir", str(config)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "IDP_API_URL" in captured.err
    assert "IDP_API_TOKEN" in captured.err


def test_missing_env_var_url_only(tmp_path, capsys, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.delenv("IDP_API_URL", raising=False)
    monkeypatch.setenv("IDP_API_TOKEN", "some-token")

    with pytest.raises(SystemExit) as exc_info:
        script.main(["--dir", str(config)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "IDP_API_URL" in captured.err


def test_missing_env_var_token_only(tmp_path, capsys, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.setenv("IDP_API_URL", "https://idp.example.com")
    monkeypatch.delenv("IDP_API_TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        script.main(["--dir", str(config)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "IDP_API_TOKEN" in captured.err


# ---------------------------------------------------------------------------
# Tests additionnels — validate_envelope directement
# ---------------------------------------------------------------------------

def test_validate_envelope_valid(tmp_path):
    f = tmp_path / "test.yaml"
    write_yaml(f, VALID_ENVELOPE)
    script.validate_envelope(f)  # Ne doit pas lever d'exception


def test_validate_envelope_not_dict(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("- item1\n- item2\n")
    with pytest.raises(ValueError, match="dict"):
        script.validate_envelope(f)


def test_validate_envelope_invalid_yaml(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("key: [unclosed bracket\n")
    with pytest.raises(ValueError, match="YAML invalide"):
        script.validate_envelope(f)


# ---------------------------------------------------------------------------
# Tests — mode --mode full passé en query param
# ---------------------------------------------------------------------------

def test_sync_mode_full_passed_in_url(tmp_path, monkeypatch):
    config = make_valid_config_dir(tmp_path)
    monkeypatch.setenv("IDP_API_URL", "https://idp.example.com")
    monkeypatch.setenv("IDP_API_TOKEN", "test-token")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"created": 0, "updated": 0, "unchanged": 1}}

    with patch("requests.post", return_value=mock_response) as mock_post:
        script.main(["--dir", str(config), "--mode", "full"])

    # Vérifier que l'URL contient mode=full
    for c in mock_post.call_args_list:
        url = c.args[0] if c.args else c.kwargs.get("url", "")
        assert "mode=full" in url, f"mode=full absent dans l'URL: {url}"


# ---------------------------------------------------------------------------
# Tests — per-file : tri alphabétique
# ---------------------------------------------------------------------------

def test_per_file_alphabetical_order(tmp_path, monkeypatch):
    config = tmp_path / "idp-config"
    # Créer plusieurs fichiers hors ordre
    write_yaml(config / "integration-types" / "z-last.yaml", VALID_ENVELOPE)
    write_yaml(config / "integration-types" / "a-first.yaml", VALID_ENVELOPE)
    write_yaml(config / "integration-types" / "m-middle.yaml", VALID_ENVELOPE)

    files = script.collect_files(config, "integration-types/", per_file=True)
    names = [f.name for f in files]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# Tests — répertoire config_dir inexistant → exit 1
# ---------------------------------------------------------------------------

def test_missing_config_dir(tmp_path, capsys):
    exit_code = script.main(["--validate-only", "--dir", str(tmp_path / "nonexistent")])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "introuvable" in captured.err
