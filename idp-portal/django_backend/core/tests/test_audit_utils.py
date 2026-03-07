"""
Story 61.5 — sanitize_audit_changes doit masquer les champs sensibles
et laisser les champs non-sensibles intacts.
"""

from core.utils import sanitize_audit_changes


class TestSanitizeAuditChanges:
    """Unit tests — no DB needed."""

    def test_credential_ref_is_masked(self):
        """AC2, AC8 — 'credential_ref' contient 'credential' → masqué."""
        changes = {"credential_ref": {"old": "ref-old", "new": "ref-new"}}
        result = sanitize_audit_changes(changes)
        assert result["credential_ref"] == {"old": "***", "new": "***"}

    def test_config_is_masked(self):
        """AC2 — 'config' → masqué."""
        changes = {"config": {"old": {"host": "a"}, "new": {"host": "b"}}}
        result = sanitize_audit_changes(changes)
        assert result["config"] == {"old": "***", "new": "***"}

    def test_password_is_masked(self):
        """AC2 — 'password' → masqué."""
        changes = {"password": {"old": "hunter2", "new": "s3cr3t"}}
        result = sanitize_audit_changes(changes)
        assert result["password"] == {"old": "***", "new": "***"}

    def test_token_is_masked(self):
        """AC2 — 'token' → masqué."""
        changes = {"token": {"old": "tok-old", "new": "tok-new"}}
        result = sanitize_audit_changes(changes)
        assert result["token"] == {"old": "***", "new": "***"}

    def test_api_key_is_masked(self):
        """AC2 — 'api_key' → masqué."""
        changes = {"api_key": {"old": "key-old", "new": "key-new"}}
        result = sanitize_audit_changes(changes)
        assert result["api_key"] == {"old": "***", "new": "***"}

    def test_substring_match_db_password(self):
        """AC2 — 'db_password' contient 'password' → masqué (substring match)."""
        changes = {"db_password": {"old": "pass1", "new": "pass2"}}
        result = sanitize_audit_changes(changes)
        assert result["db_password"] == {"old": "***", "new": "***"}

    def test_secret_is_masked(self):
        """AC2 — 'secret' → masqué."""
        changes = {"secret": {"old": "s1", "new": "s2"}}
        result = sanitize_audit_changes(changes)
        assert result["secret"] == {"old": "***", "new": "***"}

    def test_non_sensitive_name_unchanged(self):
        """AC3 — 'name' → non masqué, valeur conservée."""
        changes = {"name": {"old": "Old Name", "new": "New Name"}}
        result = sanitize_audit_changes(changes)
        assert result["name"] == {"old": "Old Name", "new": "New Name"}

    def test_non_sensitive_base_url_unchanged(self):
        """AC3 — 'base_url' → non masqué."""
        changes = {"base_url": {"old": "https://old.com", "new": "https://new.com"}}
        result = sanitize_audit_changes(changes)
        assert result["base_url"] == {"old": "https://old.com", "new": "https://new.com"}

    def test_empty_dict_returns_empty(self):
        """AC3 — dict vide → dict vide."""
        assert sanitize_audit_changes({}) == {}

    def test_json_field_updated_true_not_masked(self):
        """AC3 — entrée {"updated": True} (sans 'old') → non masquée même si champ sensible-like."""
        changes = {"parameters_schema": {"updated": True}}
        result = sanitize_audit_changes(changes)
        assert result["parameters_schema"] == {"updated": True}

    def test_mixed_fields(self):
        """AC2, AC3 — dict mixte : sensibles masqués, non-sensibles conservés."""
        changes = {
            "name": {"old": "Old", "new": "New"},
            "credential_ref": {"old": "ref1", "new": "ref2"},
            "base_url": {"old": "http://a", "new": "http://b"},
            "config": {"old": {"k": "v1"}, "new": {"k": "v2"}},
        }
        result = sanitize_audit_changes(changes)
        assert result["name"] == {"old": "Old", "new": "New"}
        assert result["credential_ref"] == {"old": "***", "new": "***"}
        assert result["base_url"] == {"old": "http://a", "new": "http://b"}
        assert result["config"] == {"old": "***", "new": "***"}

    def test_description_unchanged(self):
        """AC3 — 'description' → non masqué."""
        changes = {"description": {"old": "old desc", "new": "new desc"}}
        result = sanitize_audit_changes(changes)
        assert result["description"] == {"old": "old desc", "new": "new desc"}

    def test_token_url_not_masked(self):
        """AC3 — 'token_url' est un endpoint OAuth, pas un token → non masqué."""
        changes = {"token_url": {"old": None, "new": "https://auth.example.com/token"}}
        result = sanitize_audit_changes(changes)
        assert result["token_url"] == {"old": None, "new": "https://auth.example.com/token"}

    def test_secret_service_id_not_masked(self):
        """AC3 — 'secret_service_id' est une FK vers le vault, pas un secret → non masqué."""
        changes = {"secret_service_id": {"old": None, "new": 42}}
        result = sanitize_audit_changes(changes)
        assert result["secret_service_id"] == {"old": None, "new": 42}

    def test_apikey_no_underscore_is_masked(self):
        """AC2 — keyword 'apikey' (sans underscore) dans _SENSITIVE_AUDIT_FIELD_KEYWORDS → masqué."""
        changes = {"myapikeyfield": {"old": "key-old", "new": "key-new"}}
        result = sanitize_audit_changes(changes)
        assert result["myapikeyfield"] == {"old": "***", "new": "***"}
