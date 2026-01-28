"""Test project structure matches architecture specification (AC #5)."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # idp-portal/


def test_frontend_directory_structure():
    """AC #5: frontend/src/** structure exists."""
    frontend = PROJECT_ROOT / "frontend" / "src"
    assert frontend.is_dir()
    for subdir in ["theme", "types", "services", "hooks", "contexts", "pages", "components"]:
        assert (frontend / subdir).is_dir(), f"Missing frontend/src/{subdir}"


def test_frontend_component_directories():
    """AC #5: component subdirectories exist."""
    components = PROJECT_ROOT / "frontend" / "src" / "components"
    for subdir in ["layout", "catalog", "execution", "shared", "admin", "dashboard"]:
        assert (components / subdir).is_dir(), f"Missing components/{subdir}"


def test_backend_directory_structure():
    """AC #5: backend/app/** structure exists."""
    app = PROJECT_ROOT / "backend" / "app"
    assert app.is_dir()
    for subdir in ["api", "api/v1", "models", "repositories", "services", "adapters", "websocket", "core"]:
        assert (app / Path(subdir)).is_dir(), f"Missing backend/app/{subdir}"


def test_backend_init_files():
    """AC #5: all backend packages have __init__.py."""
    app = PROJECT_ROOT / "backend" / "app"
    packages = ["", "api", "api/v1", "models", "repositories", "services", "adapters", "websocket", "core"]
    for pkg in packages:
        init = app / pkg / "__init__.py"
        assert init.is_file(), f"Missing __init__.py in {pkg or 'app'}"


def test_database_directory_structure():
    """AC #5: database/ structure exists."""
    db = PROJECT_ROOT / "database"
    assert (db / "migrations").is_dir()
    assert (db / "seed").is_dir()


def test_root_files_exist():
    """AC #5: root files exist."""
    for filename in [".gitignore", ".env.example", "README.md"]:
        assert (PROJECT_ROOT / filename).is_file(), f"Missing {filename}"


def test_scripts_directory():
    """AC #5: scripts/ directory exists."""
    assert (PROJECT_ROOT / "scripts").is_dir()


def test_pyproject_toml_exists():
    """AC #5: backend/pyproject.toml exists."""
    assert (PROJECT_ROOT / "backend" / "pyproject.toml").is_file()
