"""
Story 30.12: Tests de cohérence — normalisation tags, audit user_id,
hash MD5 collisions, helper methods booléens, User.is_authenticated.

AC1: Tag normalization consistency
AC2: MD5 hash collision detection (Option B)
AC3: Audit signal captures real user_id
AC4: Boolean IntegerField helper methods
AC5: User.is_authenticated documentation validation
AC6: Consolidated consistency tests
"""

import hashlib

import pytest
from unittest.mock import MagicMock
from django.test import TestCase, RequestFactory

from catalog.models import normalize_tag_name, Action, Tag, ActionTag
from catalog.services import CatalogService
from core.middleware import (
    get_current_user,
    set_current_user,
    CorrelationIdMiddleware,
)
from executions.models import RecurringPattern, ScheduledExecution
from idp_auth.models import User
from integrations.signals import _get_user_id_from_context
from profiles.models import Profile
from tests.factories import UserFactory


# ============================================================================
# AC1: Tag normalization consistency
# ============================================================================


class TestTagNormalization(TestCase):
    """Ensure normalize_tag_name() is the single source of truth for tag normalization."""

    def test_spaces_to_underscores(self):
        assert normalize_tag_name("my tag") == "my_tag"

    def test_lowercase(self):
        assert normalize_tag_name("ORACLE") == "oracle"

    def test_strip_whitespace(self):
        assert normalize_tag_name("  oracle  ") == "oracle"

    def test_combined_normalization(self):
        assert normalize_tag_name("  My Cool Tag  ") == "my_cool_tag"

    def test_empty_string(self):
        assert normalize_tag_name("") == ""

    def test_none_returns_empty(self):
        assert normalize_tag_name(None) == ""  # type: ignore[arg-type]

    def test_non_string_returns_empty(self):
        assert normalize_tag_name(123) == ""  # type: ignore[arg-type]

    def test_already_normalized(self):
        assert normalize_tag_name("oracle_dba") == "oracle_dba"


@pytest.mark.django_db
class TestSyncTagsUsesNormalization(TestCase):
    """AC1: Verify _sync_tags() uses same normalization as normalize_tag_name()."""

    def setUp(self):
        self.service = CatalogService()
        self.user = UserFactory()
        self.action = Action.objects.create(
            name="Test Action Sync",
            engine="Oracle",
            platform="AAP",
            created_by=self.user,
        )

    def test_sync_tags_normalizes_spaces(self):
        self.service._sync_tags(self.action, ["My Tag", "  Oracle DB  "])
        tags = list(
            ActionTag.objects.filter(action=self.action).values_list(
                "tag__name", flat=True
            )
        )
        assert "my_tag" in tags
        assert "oracle_db" in tags

    def test_sync_tags_matches_normalize_function(self):
        """Critical: _sync_tags and normalize_tag_name produce identical results."""
        test_cases = [
            "Hello World",
            "  SQL Server  ",
            "ORACLE_DBA",
            "mixed Case Tag",
        ]
        self.service._sync_tags(self.action, test_cases)
        stored_tags = set(
            ActionTag.objects.filter(action=self.action).values_list(
                "tag__name", flat=True
            )
        )
        expected = {normalize_tag_name(t) for t in test_cases}
        assert stored_tags == expected

    def test_add_tags_normalizes_consistently(self):
        self.service.add_tags(self.action.id, ["New Tag"])
        tag = Tag.objects.filter(name="new_tag").first()
        assert tag is not None

    def test_remove_tags_normalizes_consistently(self):
        self.service._sync_tags(self.action, ["to remove"])
        self.service.remove_tags(self.action.id, ["To Remove"])
        assert ActionTag.objects.filter(action=self.action).count() == 0


# ============================================================================
# AC2: MD5 hash collision detection (Option B)
# ============================================================================


class TestMD5HashCollisionDetection(TestCase):
    """AC2 Option B: Detect collisions in MD5 truncated hash used for entity_id."""

    @staticmethod
    def _compute_entity_id(code: str) -> int:
        return int(hashlib.md5(code.encode()).hexdigest()[:8], 16) % (10**9)

    def test_known_codes_no_collision(self):
        """Validate no collisions among known integration type codes."""
        known_codes = [
            "aap",
            "ansible_tower",
            "azure_devops",
            "github_actions",
            "terraform_cloud",
            "hashicorp_vault",
            "servicenow",
            "jira",
            "splunk",
        ]
        ids = {}
        for code in known_codes:
            eid = self._compute_entity_id(code)
            assert eid not in ids.values(), (
                f"Collision detected: '{code}' and '{[k for k, v in ids.items() if v == eid][0]}' "
                f"both produce entity_id={eid}"
            )
            ids[code] = eid

    def test_hash_produces_positive_integer(self):
        eid = self._compute_entity_id("test_code")
        assert isinstance(eid, int)
        assert 0 <= eid < 10**9

    def test_hash_is_deterministic(self):
        assert self._compute_entity_id("aap") == self._compute_entity_id("aap")

    def test_different_codes_different_ids(self):
        assert self._compute_entity_id("aap") != self._compute_entity_id("azure_devops")


# ============================================================================
# AC3: Audit signals capture real user_id
# ============================================================================


class TestAuditUserIdCapture(TestCase):
    """AC3: _get_user_id_from_context() captures user from thread-local."""

    def tearDown(self):
        set_current_user(None)

    def test_returns_system_when_no_user(self):
        set_current_user(None)
        assert _get_user_id_from_context() == "system"

    def test_returns_user_id_when_authenticated(self):
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = 42
        set_current_user(mock_user)
        assert _get_user_id_from_context() == "42"

    def test_returns_system_when_user_not_authenticated(self):
        mock_user = MagicMock()
        mock_user.is_authenticated = False
        set_current_user(mock_user)
        assert _get_user_id_from_context() == "system"


class TestCurrentUserMiddlewareIntegration(TestCase):
    """AC3: CorrelationIdMiddleware stores current user in thread-local."""

    def tearDown(self):
        set_current_user(None)

    def test_middleware_sets_user(self):
        factory = RequestFactory()
        request = factory.get("/api/v1/test")
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = 99
        request.user = mock_user

        def get_response(req):
            # Inside request processing, user should be available
            current = get_current_user()
            assert current is not None
            assert current.id == 99
            from django.http import HttpResponse
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        middleware(request)

        # After request, user should be cleared
        assert get_current_user() is None

    def test_middleware_no_user(self):
        factory = RequestFactory()
        request = factory.get("/api/v1/test")
        # No user attribute

        def get_response(req):
            assert get_current_user() is None
            from django.http import HttpResponse
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        middleware(request)


# ============================================================================
# AC4: Boolean IntegerField helper methods
# ============================================================================


@pytest.mark.django_db
class TestProfileBooleanHelpers(TestCase):
    """AC4: Profile.is_admin_bool and is_auditor_bool properties."""

    def test_is_admin_bool_true(self):
        profile = Profile.objects.create(
            name="admin_test", ad_group="GRP-ADMIN", is_admin=1, is_auditor=0
        )
        assert profile.is_admin_bool is True

    def test_is_admin_bool_false(self):
        profile = Profile.objects.create(
            name="nonadmin_test", ad_group="GRP-USER", is_admin=0, is_auditor=0
        )
        assert profile.is_admin_bool is False

    def test_is_auditor_bool_true(self):
        profile = Profile.objects.create(
            name="auditor_test", ad_group="GRP-AUDIT", is_admin=0, is_auditor=1
        )
        assert profile.is_auditor_bool is True

    def test_is_auditor_bool_false(self):
        profile = Profile.objects.create(
            name="nonauditor_test", ad_group="GRP-USER2", is_admin=0, is_auditor=0
        )
        assert profile.is_auditor_bool is False


@pytest.mark.django_db
class TestRecurringPatternBooleanHelper(TestCase):
    """AC4: RecurringPattern.is_active_bool property."""

    def setUp(self):
        self.user = UserFactory()
        action = Action.objects.create(
            name="Test Sched Action",
            engine="Oracle",
            platform="AAP",
            created_by=self.user,
        )
        from django.utils import timezone
        self.scheduled = ScheduledExecution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status="pending",
            scheduled_at=timezone.now(),
        )

    def test_is_active_bool_true(self):
        from django.utils import timezone
        rp = RecurringPattern.objects.create(
            scheduled_execution=self.scheduled,
            pattern_type="daily",
            next_execution_date=timezone.now(),
            is_active=1,
        )
        assert rp.is_active_bool is True

    def test_is_active_bool_false(self):
        from django.utils import timezone
        rp = RecurringPattern.objects.create(
            scheduled_execution=self.scheduled,
            pattern_type="daily",
            next_execution_date=timezone.now(),
            is_active=0,
        )
        assert rp.is_active_bool is False


# ============================================================================
# AC5: User.is_authenticated
# ============================================================================


@pytest.mark.django_db
class TestUserIsAuthenticated(TestCase):
    """AC5: User.is_authenticated is a class attribute set to True."""

    def test_is_authenticated_class_attribute(self):
        assert User.is_authenticated is True

    def test_is_authenticated_instance(self):
        user = UserFactory()
        assert user.is_authenticated is True

    def test_no_soft_delete_field_on_user(self):
        """Confirm User model has no is_deleted field (documented in AC5)."""
        field_names = [f.name for f in User._meta.get_fields()]
        assert "is_deleted" not in field_names
        assert "deleted_at" not in field_names
