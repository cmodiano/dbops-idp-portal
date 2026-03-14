"""
Story 82.2: Tests unitaires pour build_platform_runtime_config.
"""
import pytest

from adapters.runtime_config import build_platform_runtime_config


class FakeIntegration:
    """Fake integration pour les tests (pas de DB)."""

    def __init__(self, itype: str, config: dict | None = None):
        self.type = itype
        self._config = config or {}

    def get_config(self) -> dict:
        return self._config


class FakeIntegrationNoConfig:
    """Integration sans méthode get_config."""

    def __init__(self, itype: str):
        self.type = itype


# ─────────────────────────────────────────────
# Tests nominaux
# ─────────────────────────────────────────────

def test_github_actions_nominal():
    """github_actions avec owner et repo présents."""
    integration = FakeIntegration("github_actions", {"owner": "myorg", "repo": "myrepo"})
    result = build_platform_runtime_config(integration)
    assert result == {"owner": "myorg", "repo": "myrepo"}


def test_terraform_cloud_nominal():
    """terraform_cloud avec organization présent."""
    integration = FakeIntegration("terraform_cloud", {"organization": "myorg"})
    result = build_platform_runtime_config(integration)
    assert result == {"organization": "myorg"}


def test_aap_no_required_kwargs():
    """aap n'a pas de kwargs requis — retourne seulement les optionnels avec défauts."""
    integration = FakeIntegration("aap", {})
    result = build_platform_runtime_config(integration)
    assert result == {"ca_bundle_path": None}


def test_tower_ssl_verify_default():
    """tower sans ssl_verify dans config → valeur par défaut False."""
    integration = FakeIntegration("tower", {})
    result = build_platform_runtime_config(integration)
    assert result["ssl_verify"] is False
    assert result["ca_bundle_path"] is None


def test_tower_ssl_verify_from_config():
    """tower avec ssl_verify explicite dans config."""
    integration = FakeIntegration("tower", {"ssl_verify": True})
    result = build_platform_runtime_config(integration)
    assert result["ssl_verify"] is True


def test_azure_devops_no_kwargs():
    """azure_devops n'a pas de kwargs requis ni optionnels."""
    integration = FakeIntegration("azure_devops", {})
    result = build_platform_runtime_config(integration)
    assert result == {}


# ─────────────────────────────────────────────
# Tests alias
# ─────────────────────────────────────────────

def test_alias_azuredevops_resolved():
    """azuredevops est résolu en azure_devops."""
    integration = FakeIntegration("azuredevops", {})
    result = build_platform_runtime_config(integration)
    assert result == {}  # azure_devops n'a pas de kwargs


def test_alias_terraform_resolved():
    """terraform est résolu en terraform_cloud."""
    integration = FakeIntegration("terraform", {"organization": "myorg"})
    result = build_platform_runtime_config(integration)
    assert result == {"organization": "myorg"}


# ─────────────────────────────────────────────
# Tests kwargs requis manquants
# ─────────────────────────────────────────────

def test_github_actions_missing_repo():
    """github_actions avec repo manquant → ValueError."""
    integration = FakeIntegration("github_actions", {"owner": "myorg"})
    with pytest.raises(ValueError, match="'repo'"):
        build_platform_runtime_config(integration)


def test_github_actions_missing_owner():
    """github_actions avec owner manquant → ValueError."""
    integration = FakeIntegration("github_actions", {"repo": "myrepo"})
    with pytest.raises(ValueError, match="'owner'"):
        build_platform_runtime_config(integration)


def test_terraform_missing_organization():
    """terraform_cloud avec organization manquante → ValueError."""
    integration = FakeIntegration("terraform_cloud", {})
    with pytest.raises(ValueError, match="'organization'"):
        build_platform_runtime_config(integration)


def test_github_actions_empty_owner():
    """github_actions avec owner vide → ValueError."""
    integration = FakeIntegration("github_actions", {"owner": "", "repo": "myrepo"})
    with pytest.raises(ValueError, match="'owner'"):
        build_platform_runtime_config(integration)


# ─────────────────────────────────────────────
# Tests types non-gérés (service, vault, etc.)
# ─────────────────────────────────────────────

def test_service_type_returns_empty():
    """servicenow n'est pas dans PlatformRegistry → {}."""
    integration = FakeIntegration("servicenow", {})
    result = build_platform_runtime_config(integration)
    assert result == {}


def test_vault_type_returns_empty():
    """vault n'est pas dans PlatformRegistry → {}."""
    integration = FakeIntegration("vault", {})
    result = build_platform_runtime_config(integration)
    assert result == {}


def test_unknown_type_returns_empty():
    """Type inconnu → {}."""
    integration = FakeIntegration("unknown_platform", {})
    result = build_platform_runtime_config(integration)
    assert result == {}


def test_no_get_config_method():
    """Integration sans get_config() → {} pour un type non-enregistré."""
    integration = FakeIntegrationNoConfig("servicenow")
    result = build_platform_runtime_config(integration)
    assert result == {}


def test_no_get_config_method_registered_type():
    """Integration sans get_config() pour aap → optionnels avec défauts."""
    integration = FakeIntegrationNoConfig("aap")
    result = build_platform_runtime_config(integration)
    # Sans get_config(), config = {} → seuls les optionnels avec défauts
    assert result == {"ca_bundle_path": None}


def test_none_config_uses_defaults():
    """get_config() retourne None → config traité comme {}."""
    class FakeIntegrationNoneConfig:
        type = "tower"
        def get_config(self):
            return None

    integration = FakeIntegrationNoneConfig()
    result = build_platform_runtime_config(integration)
    assert result["ssl_verify"] is False


# ─────────────────────────────────────────────
# Tests ca_bundle_path optionnel
# ─────────────────────────────────────────────

def test_aap_ca_bundle_path_from_config():
    """aap avec ca_bundle_path dans config."""
    integration = FakeIntegration("aap", {"ca_bundle_path": "/etc/ssl/my-ca.crt"})
    result = build_platform_runtime_config(integration)
    assert result["ca_bundle_path"] == "/etc/ssl/my-ca.crt"


def test_tower_ca_bundle_path_from_config():
    """tower avec ca_bundle_path dans config."""
    integration = FakeIntegration("tower", {"ca_bundle_path": "/etc/ssl/my-ca.crt"})
    result = build_platform_runtime_config(integration)
    assert result["ca_bundle_path"] == "/etc/ssl/my-ca.crt"
