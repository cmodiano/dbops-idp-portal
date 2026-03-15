"""
Coverage tests for profiles/serializers.py — targeting missing lines to reach ≥90%.
Story 55-4.

Missing lines targeted:
  46, 53 (ProfileCreateSerializer validators)
  69, 75-78 (ProfileUpdateSerializer validators)
  130-145, 149-183, 187-198 (ProfileActionPermissionsSerializer)
  243-275, 283-332, 336-370, 374-386 (ProfileTargetPermissionsSerializer)
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import serializers

from profiles.serializers import (
    ProfileActionPermissionsSerializer,
    ProfileCreateSerializer,
    ProfileListSerializer,
    ProfileSerializer,
    ProfileTargetPermissionsSerializer,
    ProfileUpdateSerializer,
)


# ---------------------------------------------------------------------------
# ProfileSerializer.to_representation
# ---------------------------------------------------------------------------

class TestProfileSerializerToRepresentation(TestCase):
    """Cover ProfileSerializer.to_representation (lines 25-30)."""

    def test_to_representation_converts_int_to_bool(self):
        """is_admin=1, is_auditor=0, is_approver=1 → True/False/True."""
        instance = MagicMock()
        instance.id = 1
        instance.name = "TestProfile"
        instance.description = "Desc"
        instance.ad_group = "CN=group"
        instance.is_admin = 1
        instance.is_auditor = 0
        instance.is_approver = 1
        instance.created_at = None
        instance.updated_at = None

        serializer = ProfileSerializer()
        # Call super().to_representation via a mocked approach
        with patch.object(
            serializers.ModelSerializer,
            "to_representation",
            return_value={
                "id": 1,
                "name": "TestProfile",
                "description": "Desc",
                "ad_group": "CN=group",
                "is_admin": 1,
                "is_auditor": 0,
                "is_approver": 1,
                "created_at": None,
                "updated_at": None,
            },
        ):
            result = serializer.to_representation(instance)

        self.assertEqual(result["is_admin"], True)
        self.assertEqual(result["is_auditor"], False)
        self.assertEqual(result["is_approver"], True)

    def test_to_representation_already_bool(self):
        """is_admin=True, is_auditor=True, is_approver=False stays True/True/False."""
        instance = MagicMock()
        instance.is_admin = True
        instance.is_auditor = True
        instance.is_approver = False

        serializer = ProfileSerializer()
        with patch.object(
            serializers.ModelSerializer,
            "to_representation",
            return_value={"is_admin": True, "is_auditor": True, "is_approver": False},
        ):
            result = serializer.to_representation(instance)

        self.assertEqual(result["is_admin"], True)
        self.assertEqual(result["is_auditor"], True)
        self.assertEqual(result["is_approver"], False)


# ---------------------------------------------------------------------------
# ProfileCreateSerializer — validate_name / validate_ad_group
# ---------------------------------------------------------------------------

class TestProfileCreateSerializerValidators(TestCase):
    """Cover ProfileCreateSerializer.validate_name and validate_ad_group (lines 42-54)."""

    def test_validate_name_empty_raises(self):
        """Line 46: empty stripped name → ValidationError."""
        s = ProfileCreateSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_name("")

    def test_validate_name_whitespace_only_raises(self):
        """Line 46: whitespace-only name → ValidationError."""
        s = ProfileCreateSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_name("   ")

    def test_validate_name_valid_returns_stripped(self):
        """Valid name returns stripped string."""
        s = ProfileCreateSerializer()
        result = s.validate_name("  My Profile  ")
        self.assertEqual(result, "My Profile")

    def test_validate_ad_group_empty_raises(self):
        """Line 53: empty stripped ad_group → ValidationError."""
        s = ProfileCreateSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_ad_group("")

    def test_validate_ad_group_whitespace_only_raises(self):
        """Line 53: whitespace-only ad_group → ValidationError."""
        s = ProfileCreateSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_ad_group("   ")

    def test_validate_ad_group_valid_returns_stripped(self):
        """Valid ad_group returns stripped string."""
        s = ProfileCreateSerializer()
        result = s.validate_ad_group("  CN=group,DC=example  ")
        self.assertEqual(result, "CN=group,DC=example")


# ---------------------------------------------------------------------------
# ProfileUpdateSerializer — validate_name / validate_ad_group
# ---------------------------------------------------------------------------

class TestProfileUpdateSerializerValidators(TestCase):
    """Cover ProfileUpdateSerializer.validate_name/validate_ad_group (lines 66-78)."""

    def test_validate_name_none_returns_none(self):
        """Line 69: None → None."""
        s = ProfileUpdateSerializer()
        result = s.validate_name(None)
        self.assertIsNone(result)

    def test_validate_name_whitespace_returns_none(self):
        """Line 71: whitespace-only → None."""
        s = ProfileUpdateSerializer()
        result = s.validate_name("   ")
        self.assertIsNone(result)

    def test_validate_name_valid_returns_stripped(self):
        """Valid name → stripped."""
        s = ProfileUpdateSerializer()
        result = s.validate_name("  New Name  ")
        self.assertEqual(result, "New Name")

    def test_validate_ad_group_none_returns_none(self):
        """Line 75: None → None."""
        s = ProfileUpdateSerializer()
        result = s.validate_ad_group(None)
        self.assertIsNone(result)

    def test_validate_ad_group_whitespace_returns_none(self):
        """Lines 77-78: whitespace-only → None."""
        s = ProfileUpdateSerializer()
        result = s.validate_ad_group("   ")
        self.assertIsNone(result)

    def test_validate_ad_group_valid_returns_stripped(self):
        """Valid ad_group → stripped."""
        s = ProfileUpdateSerializer()
        result = s.validate_ad_group("  CN=grp  ")
        self.assertEqual(result, "CN=grp")


# ---------------------------------------------------------------------------
# ProfileListSerializer.to_representation
# ---------------------------------------------------------------------------

class TestProfileListSerializerToRepresentation(TestCase):
    """Cover ProfileListSerializer.to_representation (lines 93-98)."""

    def test_to_representation_converts_int_to_bool(self):
        """is_admin=0, is_auditor=1, is_approver=0 → False/True/False."""
        instance = MagicMock()
        instance.is_admin = 0
        instance.is_auditor = 1
        instance.is_approver = 0

        serializer = ProfileListSerializer()
        with patch.object(
            serializers.ModelSerializer,
            "to_representation",
            return_value={"is_admin": 0, "is_auditor": 1, "is_approver": 0},
        ):
            result = serializer.to_representation(instance)

        self.assertEqual(result["is_admin"], False)
        self.assertEqual(result["is_auditor"], True)
        self.assertEqual(result["is_approver"], False)


# ---------------------------------------------------------------------------
# ProfileActionPermissionsSerializer — validate_environments
# ---------------------------------------------------------------------------

class TestProfileActionPermissionsValidateEnvironments(TestCase):
    """Cover validate_environments (lines 128-145)."""

    def test_empty_value_returns_empty_list(self):
        """Line 133-134: None or empty → []."""
        s = ProfileActionPermissionsSerializer()
        self.assertEqual(s.validate_environments(None), [])
        self.assertEqual(s.validate_environments([]), [])

    @patch("profiles.validation.validate_environments_against_inventory")
    def test_valid_environments_returned(self, mock_validate):
        """Lines 136-140: valid environments → returned from validate function."""
        mock_validate.return_value = ["prod", "dev"]
        request = MagicMock()
        request.user.id = 42
        s = ProfileActionPermissionsSerializer(context={"request": request})
        result = s.validate_environments(["prod", "dev"])
        self.assertEqual(result, ["prod", "dev"])
        mock_validate.assert_called_once_with(["prod", "dev"], user_id=42)

    @patch("profiles.validation.validate_environments_against_inventory")
    def test_bad_request_error_raises_validation_error(self, mock_validate):
        """Line 141-142: BadRequestError → ValidationError."""
        from core.exceptions import BadRequestError
        mock_validate.side_effect = BadRequestError(
            message="Invalid environment: nonexistent",
            code="ENV_INVALID",
        )
        s = ProfileActionPermissionsSerializer(context={})
        with self.assertRaises(serializers.ValidationError):
            s.validate_environments(["nonexistent"])

    @patch("profiles.validation.validate_environments_against_inventory")
    def test_service_unavailable_error_re_raised(self, mock_validate):
        """Lines 143-145: ServiceUnavailableError re-raised as-is."""
        from core.exceptions import ServiceUnavailableError
        mock_validate.side_effect = ServiceUnavailableError(
            message="Inventory unavailable",
            code="INVENTORY_DOWN",
        )
        s = ProfileActionPermissionsSerializer(context={})
        with self.assertRaises(ServiceUnavailableError):
            s.validate_environments(["prod"])

    @patch("profiles.validation.validate_environments_against_inventory")
    def test_no_request_context_passes_none_user_id(self, mock_validate):
        """Line 137: no request context → user_id=None."""
        mock_validate.return_value = ["dev"]
        s = ProfileActionPermissionsSerializer(context={})
        s.validate_environments(["dev"])
        mock_validate.assert_called_once_with(["dev"], user_id=None)


# ---------------------------------------------------------------------------
# ProfileActionPermissionsSerializer — validate (XOR logic)
# ---------------------------------------------------------------------------

class TestProfileActionPermissionsValidate(TestCase):
    """Cover validate XOR logic (lines 147-183)."""

    def test_list_type_without_action_ids_raises(self):
        """Line 161-163: actions_type='list' + no action_ids → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({"actions_type": "list", "action_ids": None, "tag_patterns": None})
        self.assertIn("action_ids", str(ctx.exception))

    def test_list_type_empty_action_ids_raises(self):
        """Normalized empty list → None → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate({"actions_type": "list", "action_ids": [], "tag_patterns": None})

    def test_list_type_with_tag_patterns_raises(self):
        """Line 164-167: actions_type='list' + tag_patterns → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({
                "actions_type": "list",
                "action_ids": [1, 2],
                "tag_patterns": ["oracle:*"],
            })
        self.assertIn("tag_patterns", str(ctx.exception))

    def test_list_type_valid_passes(self):
        """actions_type='list' + action_ids + no tag_patterns → passes."""
        s = ProfileActionPermissionsSerializer()
        data = {"actions_type": "list", "action_ids": [1, 2], "tag_patterns": None}
        result = s.validate(data)
        self.assertEqual(result, data)

    def test_pattern_type_without_tag_patterns_raises(self):
        """Line 169-172: actions_type='pattern' + no tag_patterns → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({"actions_type": "pattern", "action_ids": None, "tag_patterns": None})
        self.assertIn("tag_patterns", str(ctx.exception))

    def test_pattern_type_with_action_ids_raises(self):
        """Line 173-176: actions_type='pattern' + action_ids → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({
                "actions_type": "pattern",
                "action_ids": [1],
                "tag_patterns": ["oracle:*"],
            })
        self.assertIn("action_ids", str(ctx.exception))

    def test_pattern_type_valid_passes(self):
        """actions_type='pattern' + tag_patterns + no action_ids → passes."""
        s = ProfileActionPermissionsSerializer()
        data = {"actions_type": "pattern", "action_ids": None, "tag_patterns": ["oracle:*"]}
        result = s.validate(data)
        self.assertEqual(result, data)

    def test_all_type_with_action_ids_raises(self):
        """Line 178-181: actions_type='all' + action_ids → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({"actions_type": "all", "action_ids": [1], "tag_patterns": None})
        self.assertIn("non_field_errors", str(ctx.exception))

    def test_all_type_with_tag_patterns_raises(self):
        """actions_type='all' + tag_patterns → error."""
        s = ProfileActionPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate({"actions_type": "all", "action_ids": None, "tag_patterns": ["x"]})

    def test_all_type_valid_passes(self):
        """actions_type='all' + no ids/patterns → passes."""
        s = ProfileActionPermissionsSerializer()
        data = {"actions_type": "all", "action_ids": None, "tag_patterns": None}
        result = s.validate(data)
        self.assertEqual(result, data)

    def test_empty_lists_normalized_to_none(self):
        """Empty action_ids=[] and tag_patterns=[] are normalized to None."""
        s = ProfileActionPermissionsSerializer()
        # After normalization, action_ids and tag_patterns become None → 'all' type passes
        data = {"actions_type": "all", "action_ids": [], "tag_patterns": []}
        result = s.validate(data)
        self.assertEqual(result, data)


# ---------------------------------------------------------------------------
# ProfileActionPermissionsSerializer — to_representation
# ---------------------------------------------------------------------------

class TestProfileActionPermissionsToRepresentation(TestCase):
    """Cover to_representation (lines 185-198)."""

    @patch("profiles.action_permission_repository.get_action_ids", return_value=[1, 2, 3])
    @patch("profiles.action_permission_repository.get_tag_patterns", return_value=[])
    @patch("profiles.action_permission_repository.get_environments", return_value=["prod"])
    def test_to_representation_with_profile_action_permission_instance(
        self, mock_envs, mock_patterns, mock_ids
    ):
        """Lines 187-197: ProfileActionPermission instance → dict."""
        from profiles.models import ProfileActionPermission

        instance = MagicMock(spec=ProfileActionPermission)
        instance.permission_type = "LIST"

        s = ProfileActionPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["actions_type"], "list")
        self.assertEqual(result["action_ids"], [1, 2, 3])
        self.assertEqual(result["tag_patterns"], [])
        self.assertEqual(result["environments"], ["prod"])

    @patch("profiles.action_permission_repository.get_action_ids", return_value=[])
    @patch("profiles.action_permission_repository.get_tag_patterns", return_value=["oracle:*", "pg:*"])
    @patch("profiles.action_permission_repository.get_environments", return_value=[])
    def test_to_representation_pattern_type(self, mock_envs, mock_patterns, mock_ids):
        """PATTERN permission_type → 'pattern'."""
        from profiles.models import ProfileActionPermission

        instance = MagicMock(spec=ProfileActionPermission)
        instance.permission_type = "PATTERN"

        s = ProfileActionPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["actions_type"], "pattern")
        self.assertEqual(result["tag_patterns"], ["oracle:*", "pg:*"])

    @patch("profiles.action_permission_repository.get_action_ids", return_value=[])
    @patch("profiles.action_permission_repository.get_tag_patterns", return_value=[])
    @patch("profiles.action_permission_repository.get_environments", return_value=[])
    def test_to_representation_all_type(self, mock_envs, mock_patterns, mock_ids):
        """ALL permission_type → 'all'."""
        from profiles.models import ProfileActionPermission

        instance = MagicMock(spec=ProfileActionPermission)
        instance.permission_type = "ALL"

        s = ProfileActionPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["actions_type"], "all")

    @patch("profiles.action_permission_repository.get_action_ids", return_value=[])
    @patch("profiles.action_permission_repository.get_tag_patterns", return_value=[])
    @patch("profiles.action_permission_repository.get_environments", return_value=[])
    def test_to_representation_unknown_type_defaults_to_all(
        self, mock_envs, mock_patterns, mock_ids
    ):
        """Unknown permission_type defaults to 'all'."""
        from profiles.models import ProfileActionPermission

        instance = MagicMock(spec=ProfileActionPermission)
        instance.permission_type = "UNKNOWN"

        s = ProfileActionPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["actions_type"], "all")

    def test_to_representation_non_model_instance_uses_super(self):
        """Line 198: non-ProfileActionPermission → super().to_representation()."""
        s = ProfileActionPermissionsSerializer()
        # Dict data (not a model instance) → raises AttributeError or calls super
        with patch.object(
            serializers.Serializer,
            "to_representation",
            return_value={"actions_type": "all"},
        ) as mock_super:
            _result = s.to_representation({"actions_type": "all"})
        mock_super.assert_called_once()


# ---------------------------------------------------------------------------
# ProfileTargetPermissionsSerializer — validate_filter_by_attribute
# ---------------------------------------------------------------------------

class TestValidateFilterByAttribute(TestCase):
    """Cover validate_filter_by_attribute (lines 238-275)."""

    def test_none_value_returned_as_none(self):
        """Line 243-244: None → None."""
        s = ProfileTargetPermissionsSerializer()
        result = s.validate_filter_by_attribute(None)
        self.assertIsNone(result)

    def test_empty_dict_raises(self):
        """Lines 247-250: empty dict → ValidationError."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate_filter_by_attribute({})
        self.assertIn("empty", str(ctx.exception).lower())

    @patch("inventory.mapper.InventoryMapper.get_available_concepts")
    def test_invalid_keys_raises(self, mock_concepts):
        """Lines 255-260: invalid key not in valid_concepts → ValidationError."""
        mock_concepts.return_value = ["environment", "engine_type", "os"]
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate_filter_by_attribute({
                "invalid_key": ["value1"],
                "environment": ["prod"],
            })
        self.assertIn("Invalid filter attributes", str(ctx.exception))

    @patch("inventory.mapper.InventoryMapper.get_available_concepts")
    def test_valid_keys_valid_values_passes(self, mock_concepts):
        """Lines 262-266: valid key with non-empty list → passes."""
        mock_concepts.return_value = ["environment", "engine_type", "os"]
        s = ProfileTargetPermissionsSerializer()
        value = {"environment": ["prod", "dev"], "engine_type": ["oracle"]}
        with patch("core.middleware.get_correlation_id", return_value="test-cid"):
            result = s.validate_filter_by_attribute(value)
        self.assertEqual(result, value)

    @patch("inventory.mapper.InventoryMapper.get_available_concepts")
    def test_non_list_value_raises(self, mock_concepts):
        """Lines 263-266: value is not a list → ValidationError."""
        mock_concepts.return_value = ["environment"]
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate_filter_by_attribute({"environment": "prod"})  # string, not list
        self.assertIn("non-empty list", str(ctx.exception))

    @patch("inventory.mapper.InventoryMapper.get_available_concepts")
    def test_empty_list_value_raises(self, mock_concepts):
        """Lines 263-266: value is empty list → ValidationError."""
        mock_concepts.return_value = ["environment"]
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate_filter_by_attribute({"environment": []})
        self.assertIn("non-empty list", str(ctx.exception))


# ---------------------------------------------------------------------------
# ProfileTargetPermissionsSerializer — validate_exclusion_patterns
# ---------------------------------------------------------------------------

class TestValidateExclusionPatterns(TestCase):
    """Cover validate_exclusion_patterns (lines 277-332)."""

    def test_none_returns_none(self):
        """Line 283-284: None → None."""
        s = ProfileTargetPermissionsSerializer()
        result = s.validate_exclusion_patterns(None)
        self.assertIsNone(result)

    def test_empty_list_returns_empty_list(self):
        """Empty list → empty stripped_patterns → empty list returned."""
        s = ProfileTargetPermissionsSerializer()
        with patch("core.middleware.get_correlation_id", return_value="test"):
            result = s.validate_exclusion_patterns([])
        self.assertEqual(result, [])

    def test_empty_string_pattern_raises(self):
        """Lines 293-295: empty string pattern → ValidationError."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate_exclusion_patterns(["PROD-*", ""])
        self.assertIn("Invalid exclusion patterns", str(ctx.exception))

    def test_whitespace_only_pattern_raises(self):
        """Lines 293-295: whitespace-only pattern → ValidationError."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_exclusion_patterns(["PROD-*", "   "])

    def test_valid_patterns_returned_stripped(self):
        """Lines 304: valid patterns returned stripped."""
        s = ProfileTargetPermissionsSerializer()
        with patch("core.middleware.get_correlation_id", return_value="test"):
            result = s.validate_exclusion_patterns(["PROD-*", "  DR-*  "])
        self.assertEqual(result, ["PROD-*", "DR-*"])

    def test_over_50_patterns_logs_warning(self):
        """Lines 315-322: >50 patterns → warning logged but no exception."""
        s = ProfileTargetPermissionsSerializer()
        patterns = [f"HOST-{i:03d}-*" for i in range(51)]
        with patch("core.middleware.get_correlation_id", return_value="test"):
            with patch("profiles.serializers.logger") as mock_logger:
                result = s.validate_exclusion_patterns(patterns)
        self.assertEqual(len(result), 51)
        mock_logger.warning.assert_called_once()
        warning_event = mock_logger.warning.call_args[0][0]
        self.assertEqual(warning_event, "profile_exclusion_patterns_high_count")

    def test_over_100_patterns_raises(self):
        """Lines 307-312: >100 patterns → ValidationError."""
        s = ProfileTargetPermissionsSerializer()
        patterns = [f"HOST-{i:03d}-*" for i in range(101)]
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate_exclusion_patterns(patterns)
        self.assertIn("Too many exclusion patterns", str(ctx.exception))


# ---------------------------------------------------------------------------
# ProfileTargetPermissionsSerializer — validate (XOR logic)
# ---------------------------------------------------------------------------

class TestProfileTargetPermissionsValidate(TestCase):
    """Cover validate XOR logic (lines 334-370)."""

    def test_list_type_without_target_names_raises(self):
        """Line 347-350: targets_type='list' + no target_names → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({"targets_type": "list", "target_names": None, "target_patterns": None})
        self.assertIn("target_names", str(ctx.exception))

    def test_list_type_empty_target_names_raises(self):
        """Normalized [] → None → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate({"targets_type": "list", "target_names": [], "target_patterns": None})

    def test_list_type_with_target_patterns_raises(self):
        """Line 351-354: targets_type='list' + target_patterns → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({
                "targets_type": "list",
                "target_names": ["host1"],
                "target_patterns": ["PROD-*"],
            })
        self.assertIn("target_patterns", str(ctx.exception))

    def test_list_type_valid_passes(self):
        """targets_type='list' + target_names + no patterns → passes."""
        s = ProfileTargetPermissionsSerializer()
        data = {"targets_type": "list", "target_names": ["host1"], "target_patterns": None}
        result = s.validate(data)
        self.assertEqual(result, data)

    def test_pattern_type_without_target_patterns_raises(self):
        """Lines 355-359: targets_type='pattern' + no target_patterns → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({"targets_type": "pattern", "target_names": None, "target_patterns": None})
        self.assertIn("target_patterns", str(ctx.exception))

    def test_pattern_type_with_target_names_raises(self):
        """Lines 360-363: targets_type='pattern' + target_names → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({
                "targets_type": "pattern",
                "target_names": ["host1"],
                "target_patterns": ["PROD-*"],
            })
        self.assertIn("target_names", str(ctx.exception))

    def test_pattern_type_valid_passes(self):
        """targets_type='pattern' + target_patterns + no target_names → passes."""
        s = ProfileTargetPermissionsSerializer()
        data = {"targets_type": "pattern", "target_names": None, "target_patterns": ["PROD-*"]}
        result = s.validate(data)
        self.assertEqual(result, data)

    def test_all_type_with_target_names_raises(self):
        """Line 364-368: targets_type='all' + target_names → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            s.validate({"targets_type": "all", "target_names": ["host1"], "target_patterns": None})
        self.assertIn("non_field_errors", str(ctx.exception))

    def test_all_type_with_target_patterns_raises(self):
        """targets_type='all' + target_patterns → error."""
        s = ProfileTargetPermissionsSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate({"targets_type": "all", "target_names": None, "target_patterns": ["x"]})

    def test_all_type_valid_passes(self):
        """targets_type='all' + no names/patterns → passes."""
        s = ProfileTargetPermissionsSerializer()
        data = {"targets_type": "all", "target_names": None, "target_patterns": None}
        result = s.validate(data)
        self.assertEqual(result, data)

    def test_empty_lists_normalized_to_none(self):
        """Empty lists are normalized to None."""
        s = ProfileTargetPermissionsSerializer()
        data = {"targets_type": "all", "target_names": [], "target_patterns": []}
        result = s.validate(data)
        self.assertEqual(result, data)


# ---------------------------------------------------------------------------
# ProfileTargetPermissionsSerializer — to_representation
# ---------------------------------------------------------------------------

class TestProfileTargetPermissionsToRepresentation(TestCase):
    """Cover to_representation (lines 372-386)."""

    @patch("profiles.target_permission_repository.get_target_names", return_value=["host1", "host2"])
    @patch("profiles.target_permission_repository.get_target_patterns", return_value=[])
    @patch("profiles.target_permission_repository.get_filter_by_attribute", return_value={"environment": ["prod"]})
    @patch("profiles.target_permission_repository.get_exclusion_patterns", return_value=["PROD-CRITICAL-*"])
    def test_to_representation_with_profile_target_permission_instance(
        self, mock_excl, mock_filter, mock_patterns, mock_names
    ):
        """Lines 374-385: ProfileTargetPermission instance → dict."""
        from profiles.models import ProfileTargetPermission

        instance = MagicMock(spec=ProfileTargetPermission)
        instance.permission_type = "LIST"

        s = ProfileTargetPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["targets_type"], "list")
        self.assertEqual(result["target_names"], ["host1", "host2"])
        self.assertEqual(result["target_patterns"], [])
        self.assertEqual(result["filter_by_attribute"], {"environment": ["prod"]})
        self.assertEqual(result["exclusion_patterns"], ["PROD-CRITICAL-*"])

    @patch("profiles.target_permission_repository.get_target_names", return_value=[])
    @patch("profiles.target_permission_repository.get_target_patterns", return_value=["PROD-*", "UAT-*"])
    @patch("profiles.target_permission_repository.get_filter_by_attribute", return_value=None)
    @patch("profiles.target_permission_repository.get_exclusion_patterns", return_value=[])
    def test_to_representation_pattern_type(
        self, mock_excl, mock_filter, mock_patterns, mock_names
    ):
        """PATTERN permission_type → 'pattern'."""
        from profiles.models import ProfileTargetPermission

        instance = MagicMock(spec=ProfileTargetPermission)
        instance.permission_type = "PATTERN"

        s = ProfileTargetPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["targets_type"], "pattern")
        self.assertEqual(result["target_patterns"], ["PROD-*", "UAT-*"])

    @patch("profiles.target_permission_repository.get_target_names", return_value=[])
    @patch("profiles.target_permission_repository.get_target_patterns", return_value=[])
    @patch("profiles.target_permission_repository.get_filter_by_attribute", return_value=None)
    @patch("profiles.target_permission_repository.get_exclusion_patterns", return_value=[])
    def test_to_representation_all_type(
        self, mock_excl, mock_filter, mock_patterns, mock_names
    ):
        """ALL permission_type → 'all'."""
        from profiles.models import ProfileTargetPermission

        instance = MagicMock(spec=ProfileTargetPermission)
        instance.permission_type = "ALL"

        s = ProfileTargetPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["targets_type"], "all")

    @patch("profiles.target_permission_repository.get_target_names", return_value=[])
    @patch("profiles.target_permission_repository.get_target_patterns", return_value=[])
    @patch("profiles.target_permission_repository.get_filter_by_attribute", return_value=None)
    @patch("profiles.target_permission_repository.get_exclusion_patterns", return_value=[])
    def test_to_representation_unknown_type_defaults_to_all(
        self, mock_excl, mock_filter, mock_patterns, mock_names
    ):
        """Unknown permission_type defaults to 'all'."""
        from profiles.models import ProfileTargetPermission

        instance = MagicMock(spec=ProfileTargetPermission)
        instance.permission_type = "UNKNOWN_TYPE"

        s = ProfileTargetPermissionsSerializer()
        result = s.to_representation(instance)

        self.assertEqual(result["targets_type"], "all")

    def test_to_representation_non_model_instance_uses_super(self):
        """Line 386: non-ProfileTargetPermission → super().to_representation()."""
        s = ProfileTargetPermissionsSerializer()
        with patch.object(
            serializers.Serializer,
            "to_representation",
            return_value={"targets_type": "all"},
        ) as mock_super:
            _result = s.to_representation({"targets_type": "all"})
        mock_super.assert_called_once()


# ---------------------------------------------------------------------------
# Story 57.14 — is_approver serialization/deserialization
# ---------------------------------------------------------------------------

class TestProfileSerializerIsApprover(TestCase):
    """Story 57.14 AC3: Test is_approver in ProfileSerializer.to_representation."""

    def test_to_representation_is_approver_int_to_bool(self):
        """is_approver=1 → True, is_approver=0 → False."""
        instance = MagicMock()
        instance.is_admin = 0
        instance.is_auditor = 0
        instance.is_approver = 1

        serializer = ProfileSerializer()
        with patch.object(
            serializers.ModelSerializer,
            "to_representation",
            return_value={"is_admin": 0, "is_auditor": 0, "is_approver": 1},
        ):
            result = serializer.to_representation(instance)

        self.assertEqual(result["is_approver"], True)

    def test_to_representation_is_approver_zero_to_false(self):
        """is_approver=0 → False."""
        instance = MagicMock()
        instance.is_admin = 0
        instance.is_auditor = 0
        instance.is_approver = 0

        serializer = ProfileSerializer()
        with patch.object(
            serializers.ModelSerializer,
            "to_representation",
            return_value={"is_admin": 0, "is_auditor": 0, "is_approver": 0},
        ):
            result = serializer.to_representation(instance)

        self.assertEqual(result["is_approver"], False)


class TestProfileListSerializerIsApprover(TestCase):
    """Story 57.14 AC3: Test is_approver in ProfileListSerializer.to_representation."""

    def test_to_representation_is_approver_int_to_bool(self):
        """is_approver=1 → True."""
        instance = MagicMock()
        instance.is_admin = 0
        instance.is_auditor = 0
        instance.is_approver = 1

        serializer = ProfileListSerializer()
        with patch.object(
            serializers.ModelSerializer,
            "to_representation",
            return_value={"is_admin": 0, "is_auditor": 0, "is_approver": 1},
        ):
            result = serializer.to_representation(instance)

        self.assertEqual(result["is_approver"], True)


class TestProfileCreateSerializerIsApprover(TestCase):
    """Story 57.14 AC3: Test is_approver in ProfileCreateSerializer."""

    def test_is_approver_defaults_to_false(self):
        """is_approver defaults to False in ProfileCreateSerializer."""
        s = ProfileCreateSerializer(data={"name": "test", "ad_group": "GRP-TEST"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertFalse(s.validated_data["is_approver"])

    def test_is_approver_true_accepted(self):
        """is_approver=True is accepted."""
        s = ProfileCreateSerializer(data={"name": "test", "ad_group": "GRP-TEST", "is_approver": True})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertTrue(s.validated_data["is_approver"])


class TestProfileUpdateSerializerIsApprover(TestCase):
    """Story 57.14 AC3: Test is_approver in ProfileUpdateSerializer."""

    def test_is_approver_optional(self):
        """is_approver is optional (not required) in ProfileUpdateSerializer."""
        s = ProfileUpdateSerializer(data={})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("is_approver", s.validated_data)

    def test_is_approver_null_accepted(self):
        """is_approver=null is accepted (allow_null=True)."""
        s = ProfileUpdateSerializer(data={"is_approver": None})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data["is_approver"])

    def test_is_approver_true_accepted(self):
        """is_approver=True is accepted."""
        s = ProfileUpdateSerializer(data={"is_approver": True})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertTrue(s.validated_data["is_approver"])
