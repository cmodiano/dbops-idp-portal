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


def test_mypy_in_dev_dependencies():
    """AC #4: mypy is listed in dev dependencies."""
    pyproject = PROJECT_ROOT / "backend" / "pyproject.toml"
    content = pyproject.read_text()
    assert "mypy>=" in content, "mypy should be in dev dependencies"


def test_mypy_configuration_exists():
    """AC #4: [tool.mypy] section exists in pyproject.toml."""
    pyproject = PROJECT_ROOT / "backend" / "pyproject.toml"
    content = pyproject.read_text()
    assert "[tool.mypy]" in content, "mypy configuration section should exist"


def test_mypy_configuration_settings():
    """AC #4: mypy configuration has required settings."""
    pyproject = PROJECT_ROOT / "backend" / "pyproject.toml"
    content = pyproject.read_text()
    assert 'python_version = "3.11"' in content
    assert "strict = false" in content
    assert "warn_return_any = true" in content
    assert "ignore_missing_imports = true" in content


# === CI/CD Workflow Tests (AC #4) ===


def test_ci_workflow_exists():
    """AC #4: CI workflow file exists."""
    ci_workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_workflow.is_file(), "CI workflow file should exist"


def test_ci_workflow_valid_yaml():
    """AC #4: CI workflow is valid YAML."""
    import yaml

    ci_workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    content = ci_workflow.read_text()
    parsed = yaml.safe_load(content)
    assert parsed is not None
    assert "name" in parsed
    # Note: 'on' in YAML is parsed as boolean True
    assert True in parsed, "CI workflow should have 'on' triggers"
    assert "jobs" in parsed


def test_ci_workflow_jobs():
    """AC #4: CI workflow has required jobs."""
    import yaml

    ci_workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    parsed = yaml.safe_load(ci_workflow.read_text())
    jobs = parsed["jobs"]

    required_jobs = [
        "lint-backend",
        "lint-frontend",
        "typecheck-backend",
        "typecheck-frontend",
        "test-backend",
        "test-frontend",
        "build-frontend",
    ]
    for job in required_jobs:
        assert job in jobs, f"CI workflow should have {job} job"


def test_deploy_workflow_exists():
    """AC #4: Deploy workflow file exists."""
    deploy_workflow = PROJECT_ROOT / ".github" / "workflows" / "deploy.yml"
    assert deploy_workflow.is_file(), "Deploy workflow file should exist"


def test_deploy_workflow_valid_yaml():
    """AC #4: Deploy workflow is valid YAML."""
    import yaml

    deploy_workflow = PROJECT_ROOT / ".github" / "workflows" / "deploy.yml"
    content = deploy_workflow.read_text()
    parsed = yaml.safe_load(content)
    assert parsed is not None
    assert "name" in parsed
    # Note: 'on' in YAML is parsed as boolean True
    assert True in parsed, "Deploy workflow should have 'on' triggers"
    assert "jobs" in parsed


def test_deploy_workflow_triggers():
    """AC #4: Deploy workflow has correct triggers."""
    import yaml

    deploy_workflow = PROJECT_ROOT / ".github" / "workflows" / "deploy.yml"
    parsed = yaml.safe_load(deploy_workflow.read_text())
    # Note: 'on' in YAML is parsed as boolean True
    triggers = parsed[True]

    assert "workflow_dispatch" in triggers, "Deploy should support manual trigger"
    assert "push" in triggers, "Deploy should trigger on push"


# === Nginx Configuration Tests (AC #5) ===


def test_nginx_config_exists():
    """AC #5: Nginx config file exists."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    assert nginx_conf.is_file(), "Nginx config file should exist"


def test_nginx_config_https_listener():
    """AC #5: Nginx config has HTTPS listener on 443."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "listen 443 ssl" in content, "Should listen on HTTPS 443"


def test_nginx_config_tls_protocols():
    """AC #5: Nginx config enforces TLS 1.2+."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "ssl_protocols TLSv1.2 TLSv1.3" in content, "Should enforce TLS 1.2+"


def test_nginx_config_api_proxy():
    """AC #5: Nginx config has API proxy to Uvicorn."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "location /api/" in content, "Should have API location block"
    assert "proxy_pass http://127.0.0.1:8000" in content, "Should proxy to Uvicorn"


def test_nginx_config_websocket_proxy():
    """AC #5: Nginx config has WebSocket proxy."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "location /ws/" in content, "Should have WebSocket location block"
    assert 'proxy_set_header Upgrade $http_upgrade' in content, "Should upgrade WebSocket"
    assert 'proxy_set_header Connection "upgrade"' in content, "Should set Connection header"


def test_nginx_config_security_headers():
    """AC #5: Nginx config has security headers."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "X-Content-Type-Options" in content
    assert "X-Frame-Options" in content
    assert "Strict-Transport-Security" in content


def test_nginx_config_http_redirect():
    """AC #5: Nginx config redirects HTTP 80 to HTTPS 443."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "listen 80" in content, "Should listen on HTTP 80"
    assert "return 301 https://" in content, "Should redirect to HTTPS"


def test_nginx_config_spa_routing():
    """AC #5: Nginx config has SPA fallback routing."""
    nginx_conf = PROJECT_ROOT / "nginx" / "idp-portal.conf"
    content = nginx_conf.read_text()
    assert "try_files $uri $uri/ /index.html" in content, "Should fallback to index.html"


# === systemd Service Tests (AC #6) ===


def test_systemd_service_exists():
    """AC #6: systemd service file exists."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    assert service_file.is_file(), "systemd service file should exist"


def test_systemd_service_unit_section():
    """AC #6: systemd service has [Unit] section."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    content = service_file.read_text()
    assert "[Unit]" in content, "Should have [Unit] section"
    assert "After=network.target" in content, "Should start after network"


def test_systemd_service_service_section():
    """AC #6: systemd service has [Service] section with required directives."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    content = service_file.read_text()
    assert "[Service]" in content, "Should have [Service] section"
    assert "Type=simple" in content, "Should be Type=simple"
    assert "ExecStart=" in content, "Should have ExecStart"
    assert "uvicorn" in content, "ExecStart should run uvicorn"
    assert "--host 127.0.0.1" in content, "Should bind to localhost"
    assert "--port 8000" in content, "Should use port 8000"
    assert "--workers 2" in content, "Should have 2 workers"


def test_systemd_service_restart_policy():
    """AC #6: systemd service has restart policy."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    content = service_file.read_text()
    assert "Restart=always" in content, "Should restart always"
    assert "RestartSec=5" in content, "Should wait 5 seconds between restarts"


def test_systemd_service_user():
    """AC #6: systemd service runs as dedicated user."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    content = service_file.read_text()
    assert "User=idp-portal" in content, "Should run as idp-portal user"


def test_systemd_service_environment():
    """AC #6: systemd service loads environment file."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    content = service_file.read_text()
    assert "EnvironmentFile=" in content, "Should have EnvironmentFile directive"


def test_systemd_service_install_section():
    """AC #6: systemd service has [Install] section."""
    service_file = PROJECT_ROOT / "nginx" / "idp-portal.service"
    content = service_file.read_text()
    assert "[Install]" in content, "Should have [Install] section"
    assert "WantedBy=multi-user.target" in content, "Should be wanted by multi-user"


# === Deploy Script Tests (AC #4) ===


def test_deploy_script_exists():
    """AC #4: Deploy script exists."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    assert deploy_script.is_file(), "Deploy script should exist"


def test_deploy_script_executable():
    """AC #4: Deploy script is executable."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    assert os.access(deploy_script, os.X_OK), "Deploy script should be executable"


def test_deploy_script_shebang():
    """AC #4: Deploy script has proper shebang."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    content = deploy_script.read_text()
    first_line = content.split("\n")[0]
    assert first_line.startswith("#!/"), "Should have shebang"
    assert "bash" in first_line, "Should use bash"


def test_deploy_script_error_handling():
    """AC #4: Deploy script has proper error handling."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    content = deploy_script.read_text()
    assert "set -e" in content or "set -euo pipefail" in content, "Should exit on error"


def test_deploy_script_argument_validation():
    """AC #4: Deploy script validates arguments."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    content = deploy_script.read_text()
    # Should check for required arguments
    assert "host" in content.lower() or "HOST" in content
    assert "user" in content.lower() or "USER" in content


def test_deploy_script_rsync():
    """AC #4: Deploy script uses rsync for deployment."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    content = deploy_script.read_text()
    assert "rsync" in content, "Should use rsync for deployment"


def test_deploy_script_systemctl():
    """AC #4: Deploy script restarts systemd service."""
    deploy_script = PROJECT_ROOT / "scripts" / "deploy.sh"
    content = deploy_script.read_text()
    assert "systemctl restart" in content, "Should restart systemd service"


# === Database Migration V000 / V002 Tests (Story 2.1, AC #3, Task 1.5) ===


def test_v000_migration_exists():
    """V000 migration file exists (SCHEMA_VERSION table)."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V000_create_schema_version.sql"
    assert migration.is_file(), "V000 migration file should exist"


def test_v000_creates_schema_version():
    """V000 creates SCHEMA_VERSION table."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V000_create_schema_version.sql"
    content = migration.read_text()
    assert "CREATE TABLE SCHEMA_VERSION" in content
    assert "VERSION" in content
    assert "APPLIED_AT" in content


def test_v002_migration_exists():
    """AC #3: V002 migration file exists."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    assert migration.is_file(), "V002 migration file should exist"


def test_v002_migration_creates_table():
    """AC #3: V002 migration creates ACTIONS_CATALOG table."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "CREATE TABLE ACTIONS_CATALOG" in content, "Should create ACTIONS_CATALOG table"


def test_v002_migration_creates_sequence():
    """AC #3: V002 migration creates sequence for ID."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "CREATE SEQUENCE SEQ_ACTIONS_CATALOG" in content, "Should create sequence"


def test_v002_migration_has_required_columns():
    """AC #3: V002 migration has all required columns."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    required_columns = [
        "ID",
        "NAME",
        "DESCRIPTION",
        "CATEGORY",
        "ENGINE",
        "PLATFORM",
        "PARAMETERS_SCHEMA",
        "IMPACT_RULES",
        "RBAC_POLICIES",
        "STATUS",
        "CREATED_BY",
        "CREATED_AT",
        "UPDATED_AT",
    ]
    for col in required_columns:
        assert col in content, f"Missing column {col}"


def test_v002_migration_has_clob_columns():
    """AC #3, #4: V002 migration uses CLOB for JSON columns."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    # Check that CLOB is used for JSON columns
    assert "PARAMETERS_SCHEMA" in content and "CLOB" in content
    assert "IMPACT_RULES" in content and "CLOB" in content
    assert "RBAC_POLICIES" in content and "CLOB" in content


def test_v002_migration_has_category_constraint():
    """AC #3: V002 migration has CHECK constraint for CATEGORY."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "Provisioning" in content
    assert "Patching" in content
    assert "Administration" in content
    assert "Monitoring" in content


def test_v002_migration_has_engine_constraint():
    """AC #3: V002 migration has CHECK constraint for ENGINE."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "'Oracle'" in content
    assert "'SQL Server'" in content
    assert "'DB2'" in content


def test_v002_migration_has_platform_constraint():
    """AC #3: V002 migration has CHECK constraint for PLATFORM."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "'AAP'" in content
    assert "'GitHub Actions'" in content
    assert "'Azure DevOps'" in content
    assert "'Terraform'" in content


def test_v002_migration_has_status_constraint():
    """AC #3: V002 migration has CHECK constraint for STATUS."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "'draft'" in content
    assert "'published'" in content
    assert "'disabled'" in content


def test_v002_migration_has_indexes():
    """AC #3: V002 migration creates required indexes."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "IDX_ACTIONS_CATALOG_STATUS" in content
    assert "IDX_ACTIONS_CATALOG_CATEGORY" in content
    assert "IDX_ACTIONS_CATALOG_ENGINE" in content


def test_v002_migration_has_foreign_key():
    """AC #3: V002 migration has FK to USERS table."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "REFERENCES USERS(ID)" in content, "Should have FK to USERS"


def test_v002_migration_has_unique_name():
    """AC #3: V002 migration has unique constraint on NAME."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "UNIQUE" in content and "NAME" in content, "NAME should be unique"


def test_v002_migration_updates_schema_version():
    """Task 1.5: V002 updates SCHEMA_VERSION (idempotent MERGE)."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V002_create_actions_catalog.sql"
    content = migration.read_text()
    assert "MERGE INTO SCHEMA_VERSION" in content
    assert "V002" in content


# === Database Migration V003 Tests (Story 2.2, AC #4) ===


def test_v003_migration_exists():
    """AC #4: V003 migration file exists."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V003_add_execution_steps.sql"
    assert migration.is_file(), "V003 migration file should exist"


def test_v003_migration_adds_execution_steps():
    """AC #4: V003 migration adds EXECUTION_STEPS column."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V003_add_execution_steps.sql"
    content = migration.read_text()
    assert "EXECUTION_STEPS" in content
    assert "CLOB" in content


def test_v003_migration_adds_change_type_config():
    """AC #4: V003 migration adds CHANGE_TYPE_CONFIG column."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V003_add_execution_steps.sql"
    content = migration.read_text()
    assert "CHANGE_TYPE_CONFIG" in content
    assert "CLOB" in content


def test_v003_migration_has_comments():
    """AC #4: V003 migration has column comments documenting JSON structure."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V003_add_execution_steps.sql"
    content = migration.read_text()
    assert "COMMENT ON COLUMN ACTIONS_CATALOG.EXECUTION_STEPS" in content
    assert "COMMENT ON COLUMN ACTIONS_CATALOG.CHANGE_TYPE_CONFIG" in content
    # Check JSON structure is documented
    assert "prerequisite" in content
    assert "execution" in content
    assert "verification" in content
    assert "pre_approved" in content
    assert "cab" in content


def test_v003_migration_updates_schema_version():
    """Task 1.3: V003 updates SCHEMA_VERSION (idempotent MERGE)."""
    migration = PROJECT_ROOT / "database" / "migrations" / "V003_add_execution_steps.sql"
    content = migration.read_text()
    assert "MERGE INTO SCHEMA_VERSION" in content
    assert "V003" in content
