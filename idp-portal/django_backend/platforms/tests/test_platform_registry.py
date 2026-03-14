"""
Story 82.2: Tests unitaires pour PlatformRegistry et PlatformDefinition.
"""
import pytest

from platforms.definitions import PlatformDefinition
from platforms.registry import platform_registry, PlatformRegistry


# ─────────────────────────────────────────────
# Tests PlatformDefinition
# ─────────────────────────────────────────────

def test_platform_definition_is_frozen():
    """PlatformDefinition est immutable (frozen=True)."""
    defn = PlatformDefinition(
        code="test",
        display_name="Test",
        aliases=frozenset(),
        icon="test",
        connector_type="test",
        action_platform_code="Test",
        supports_health_check=True,
    )
    with pytest.raises((AttributeError, TypeError)):
        defn.code = "other"  # type: ignore[misc]


def test_platform_definition_defaults():
    """runtime_kwargs_required et runtime_kwargs_optional ont des valeurs par défaut."""
    defn = PlatformDefinition(
        code="test",
        display_name="Test",
        aliases=frozenset(),
        icon="test",
        connector_type="test",
        action_platform_code="Test",
        supports_health_check=False,
    )
    assert defn.runtime_kwargs_required == ()
    assert defn.runtime_kwargs_optional == {}


# ─────────────────────────────────────────────
# Tests PlatformRegistry — enregistrement / lookup
# ─────────────────────────────────────────────

def test_is_registered_canonical():
    """Les 5 codes canoniques sont enregistrés."""
    for code in ("aap", "tower", "azure_devops", "github_actions", "terraform_cloud"):
        assert platform_registry.is_registered(code), f"{code} should be registered"


def test_is_registered_alias_false():
    """Les aliases ne sont PAS des codes canoniques."""
    assert not platform_registry.is_registered("azuredevops")
    assert not platform_registry.is_registered("terraform")


def test_is_registered_unknown_false():
    """Un type inconnu retourne False."""
    assert not platform_registry.is_registered("unknown_platform")


def test_get_existing_platform():
    """get() retourne la PlatformDefinition pour un code canonique."""
    defn = platform_registry.get("github_actions")
    assert defn.code == "github_actions"
    assert defn.runtime_kwargs_required == ("owner", "repo")
    assert defn.connector_type == "github_actions"
    assert defn.supports_health_check is True


def test_get_unknown_raises_key_error():
    """get() lève KeyError pour un code inconnu."""
    with pytest.raises(KeyError):
        platform_registry.get("unknown_platform")


def test_get_alias_raises_key_error():
    """get() lève KeyError pour un alias (pas un code canonique)."""
    with pytest.raises(KeyError):
        platform_registry.get("azuredevops")


def test_list_types_contains_all():
    """list_types() retourne au moins les 5 plateformes."""
    types = platform_registry.list_types()
    for code in ("aap", "tower", "azure_devops", "github_actions", "terraform_cloud"):
        assert code in types


# ─────────────────────────────────────────────
# Tests resolve_alias
# ─────────────────────────────────────────────

def test_resolve_alias_azuredevops():
    """azuredevops → azure_devops."""
    assert platform_registry.resolve_alias("azuredevops") == "azure_devops"


def test_resolve_alias_terraform():
    """terraform → terraform_cloud."""
    assert platform_registry.resolve_alias("terraform") == "terraform_cloud"


def test_resolve_alias_canonical_passthrough():
    """Un code canonique est retourné inchangé."""
    assert platform_registry.resolve_alias("aap") == "aap"
    assert platform_registry.resolve_alias("github_actions") == "github_actions"


def test_resolve_alias_unknown_passthrough():
    """Un type inconnu est retourné inchangé (pas de raise)."""
    assert platform_registry.resolve_alias("unknown_type") == "unknown_type"
    assert platform_registry.resolve_alias("servicenow") == "servicenow"


def test_resolve_alias_tower_passthrough():
    """tower est un code canonique — resolve_alias retourne 'tower' inchangé."""
    # tower n'est PAS un alias dans PlatformRegistry (c'est une plateforme à part)
    assert platform_registry.resolve_alias("tower") == "tower"


# ─────────────────────────────────────────────
# Tests des métadonnées des plateformes enregistrées
# ─────────────────────────────────────────────

def test_aap_metadata():
    defn = platform_registry.get("aap")
    assert defn.display_name == "Ansible Automation Platform"
    assert defn.icon == "aap"
    assert defn.connector_type == "aap"
    assert defn.action_platform_code == "AAP"
    assert defn.aliases == frozenset()
    assert defn.runtime_kwargs_required == ()


def test_tower_metadata():
    defn = platform_registry.get("tower")
    assert defn.display_name == "Ansible Tower"
    assert defn.icon == "aap"
    assert defn.connector_type == "aap"
    assert defn.action_platform_code == "Tower"
    assert "ssl_verify" in defn.runtime_kwargs_optional
    assert defn.runtime_kwargs_optional["ssl_verify"] is False


def test_azure_devops_metadata():
    defn = platform_registry.get("azure_devops")
    assert defn.display_name == "Azure DevOps"
    assert defn.aliases == frozenset({"azuredevops"})


def test_github_actions_metadata():
    defn = platform_registry.get("github_actions")
    assert defn.runtime_kwargs_required == ("owner", "repo")


def test_terraform_cloud_metadata():
    defn = platform_registry.get("terraform_cloud")
    assert defn.display_name == "Terraform Cloud"
    assert defn.aliases == frozenset({"terraform"})
    assert defn.runtime_kwargs_required == ("organization",)


# ─────────────────────────────────────────────
# Tests PlatformRegistry isolé (instance fraîche)
# ─────────────────────────────────────────────

def test_registry_register_and_get():
    """register() + get() fonctionnent correctement."""
    registry = PlatformRegistry()
    defn = PlatformDefinition(
        code="myplatform",
        display_name="My Platform",
        aliases=frozenset({"myalias"}),
        icon="myplatform",
        connector_type="myplatform",
        action_platform_code="MyPlatform",
        supports_health_check=True,
        runtime_kwargs_required=("token",),
        runtime_kwargs_optional={"timeout": 30},
    )
    registry.register(defn)
    assert registry.is_registered("myplatform")
    assert not registry.is_registered("myalias")
    assert registry.resolve_alias("myalias") == "myplatform"
    retrieved = registry.get("myplatform")
    assert retrieved.runtime_kwargs_required == ("token",)
    assert retrieved.runtime_kwargs_optional == {"timeout": 30}
