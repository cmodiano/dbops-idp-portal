from __future__ import annotations

import logging
from typing import Any
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Subquery
from idp_auth.models import User
from integrations.models import Integration
from core.fields import OracleJSONField

logger = logging.getLogger(__name__)


class ActionCategory(models.TextChoices):
    """Action category enum matching Oracle CHECK constraint."""
    PROVISIONING = 'Provisioning', 'Provisioning'
    PATCHING = 'Patching', 'Patching'
    ADMINISTRATION = 'Administration', 'Administration'
    MONITORING = 'Monitoring', 'Monitoring'


class ActionEngine(models.TextChoices):
    """Action engine enum matching Oracle CHECK constraint."""
    ORACLE = 'Oracle', 'Oracle'
    SQL_SERVER = 'SQL Server', 'SQL Server'
    DB2 = 'DB2', 'DB2'


class ActionPlatform(models.TextChoices):
    """Action platform enum matching Oracle CHECK constraint."""
    AAP = 'AAP', 'AAP'
    GITHUB_ACTIONS = 'GitHub Actions', 'GitHub Actions'
    AZURE_DEVOPS = 'Azure DevOps', 'Azure DevOps'
    TERRAFORM = 'Terraform', 'Terraform'


class ActionStatus(models.TextChoices):
    """Action status enum matching Oracle CHECK constraint."""
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    DISABLED = 'disabled', 'Disabled'


class ActionItemType(models.TextChoices):
    """Action item type enum matching Oracle CHECK constraint (V027)."""
    ACTION = 'action', 'Action'
    WORKFLOW = 'workflow', 'Workflow'


def normalize_tag_name(name: str) -> str:
    """Normalize tag name: lowercase, strip, replace spaces with nothing."""
    if not name or not isinstance(name, str):
        return ""
    return name.strip().lower().replace(" ", "")


class ActionQuerySet(models.QuerySet):
    """
    Custom QuerySet for Action model.
    Exposes chainable helpers (works after .filter()).
    """

    def list_published(self) -> ActionQuerySet:
        """Return QuerySet of published actions only."""
        return self.filter(status=ActionStatus.PUBLISHED)

    def list_by_status(self, status: str) -> ActionQuerySet:
        """
        Filter actions by status.

        Args:
            status: Status value (draft, published, disabled)

        Returns:
            QuerySet filtered by status
        """
        return self.filter(status=status)

    def search_by_tags(self, tag_names: list[str]) -> ActionQuerySet:
        """
        Search actions by tags (AND logic - action must have all specified tags).

        Args:
            tag_names: List of tag names to search for

        Returns:
            QuerySet of actions matching all tags, distinct
        """
        queryset = self.filter(status=ActionStatus.PUBLISHED)

        # Normalize / drop empties
        tag_names = [t for t in (tag_names or []) if t and str(t).strip()]
        if not tag_names:
            return queryset

        # IMPORTANT (Oracle): avoid DISTINCT over Action rows because Action has CLOB columns.
        # Use a subquery on ACTION_TAGS to get matching action IDs, then filter by id__in.
        # AND semantics: action must have *all* specified tag names.
        from catalog.models import ActionTag  # local import (model defined later in this module)

        unique_tag_names = sorted(set(tag_names))
        action_ids_subq = (
            ActionTag.objects.filter(
                tag__name__in=unique_tag_names,
                action__status=ActionStatus.PUBLISHED,
            )
            .values("action_id")
            .annotate(matched=Count("tag_id", distinct=True))
            .filter(matched=len(unique_tag_names))
            .values("action_id")
        )
        return queryset.filter(id__in=Subquery(action_ids_subq))

    def with_tags(self) -> ActionQuerySet:
        """Prefetch tags to avoid N+1 queries."""
        return self.prefetch_related('actiontag_set__tag')

    def with_creator(self) -> ActionQuerySet:
        """Select related creator to avoid N+1 queries."""
        return self.select_related('created_by')


class ActionManager(models.Manager.from_queryset(ActionQuerySet)):  # type: ignore[misc]
    """
    Custom manager for Action model.
    Provides query methods for common action queries (and keeps them chainable).
    """


class BusinessRulePolicy(models.Model):
    """
    Story 28.4: Règle métier prédéfinie réutilisable par plusieurs actions.
    Maps to Oracle BUSINESS_RULE_POLICIES table (V074).
    """
    id = models.AutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=200, unique=True, db_column='NAME')
    description = models.TextField(max_length=500, null=True, blank=True, db_column='DESCRIPTION')
    policy_json = OracleJSONField(db_column='POLICY_JSON')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column='CREATED_BY_ID')

    class Meta:
        db_table = 'BUSINESS_RULE_POLICIES'
        ordering = ['name']

    def clean(self) -> None:
        """Validate policy_json with validate_business_rule_policies()."""
        from catalog.validators import validate_business_rule_policies
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_business_rule_policies(self.policy_json)
        except (DjangoValidationError, ValueError, TypeError, KeyError) as e:
            raise ValidationError({'policy_json': str(e)})

    def __str__(self) -> str:
        return self.name

    @property
    def step_type(self) -> str | None:
        """Extract the primary step_type from policy_json (for UI filters)."""
        if not self.policy_json or not isinstance(self.policy_json, dict):
            return None
        rules = self.policy_json.get('on_step_output')
        if rules and isinstance(rules, list) and len(rules) > 0:
            return rules[0].get('when', {}).get('step_type')
        return None


class Action(models.Model):
    """
    Action model mapping to Oracle ACTIONS_CATALOG table (V002, V017, V019, V022, V027, V031, V036, V046).
    Represents an action or workflow in the catalog.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    description = models.CharField(max_length=4000, null=True, blank=True, db_column='DESCRIPTION')
    category = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column='CATEGORY',
        help_text='Category code (must exist in REF_CATEGORIES.CODE). Validated by application logic.'
    )
    engine = models.CharField(
        max_length=50,
        db_column='ENGINE',
        help_text='Engine code (must exist in REF_ENGINES.CODE). Validated by application logic.'
    )
    platform = models.CharField(
        max_length=50,
        db_column='PLATFORM',
        help_text='Platform code (must exist in REF_PLATFORMS.CODE). Validated by application logic.'
    )
    # CLOB fields - using OracleJSONField with automatic JSON handling (Story 17.4)
    parameters_schema = OracleJSONField(null=True, blank=True, db_column='PARAMETERS_SCHEMA')
    impact_rules = OracleJSONField(null=True, blank=True, db_column='IMPACT_RULES')
    execution_steps = OracleJSONField(null=True, blank=True, db_column='EXECUTION_STEPS')
    change_type_config = OracleJSONField(null=True, blank=True, db_column='CHANGE_TYPE_CONFIG')
    documentation_md = models.TextField(null=True, blank=True, db_column='DOCUMENTATION_MD')
    remediation_rules = OracleJSONField(null=True, blank=True, db_column='REMEDIATION_RULES')
    # Story 28.1: Business rule policies evaluated on step output (post-step, before gate evaluation)
    business_rule_policies = OracleJSONField(
        null=True, blank=True, db_column='BUSINESS_RULE_POLICIES',
        help_text='JSON schema defining business rule policies evaluated on step output (legacy inline)'
    )
    # Story 28.4: FK to predefined business rule policy (catalogue)
    business_rule_policy = models.ForeignKey(
        BusinessRulePolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actions',
        db_column='BUSINESS_RULE_POLICY_ID',
    )
    default_impact_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        null=True,
        blank=True,
        db_column='DEFAULT_IMPACT_LEVEL'
    )
    status = models.CharField(
        max_length=20,
        choices=ActionStatus.choices,
        default=ActionStatus.DRAFT,
        db_column='STATUS'
    )
    item_type = models.CharField(
        max_length=20,
        choices=ActionItemType.choices,
        default=ActionItemType.ACTION,
        db_column='ITEM_TYPE'
    )
    # Story 13.2, AC3: Whether action requires target selection (V046)
    requires_target = models.BooleanField(default=True, db_column='REQUIRES_TARGET')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='CREATED_BY'
    )
    integration = models.ForeignKey(
        Integration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='INTEGRATION_ID'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='UPDATED_AT')
    # Story 18.1: Soft-delete columns for action deactivation
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='DELETED_BY',
        related_name='deleted_actions',
    )
    deleted_at = models.DateTimeField(null=True, blank=True, db_column='DELETED_AT')
    deletion_reason = models.CharField(max_length=500, null=True, blank=True, db_column='DELETION_REASON')

    # Custom manager
    objects = ActionManager()

    class Meta:
        db_table = 'ACTIONS_CATALOG'
        ordering = ['name']
        indexes = [
            models.Index(fields=['status'], name='idx_actions_status'),
            models.Index(fields=['status', 'engine'], name='idx_actions_status_engine'),
            models.Index(fields=['status', 'created_at'], name='idx_actions_status_created'),
            # Story 18.1: Index for soft-delete queries
            models.Index(fields=['deleted_at'], name='idx_actions_deleted_at'),
        ]
        constraints = [
            # Story 18.1: Ensure consistency between status and deleted_at
            models.CheckConstraint(
                check=(
                    models.Q(status='disabled', deleted_at__isnull=False)
                    | models.Q(status__in=['draft', 'published'], deleted_at__isnull=True)
                ),
                name='ck_actions_soft_delete_consistency',
            ),
        ]

    @property
    def effective_business_rule_policies(self) -> dict | None:
        """
        Story 28.4: Return effective business rule policies for this action.
        Priority: FK predefined > inline legacy > None.
        """
        if self.business_rule_policy_id:
            policy = self.business_rule_policy
            if policy and policy.is_active:
                return policy.policy_json
            logger.warning(
                "business_rule_policy_inactive: action_id=%s, policy_id=%s",
                self.id, self.business_rule_policy_id,
            )
            return None
        return self.business_rule_policies

    def clean(self) -> None:
        """Validate model fields before save."""
        super().clean()
        # Story 28.4: XOR constraint — only one of FK or inline
        if self.business_rule_policy_id and self.business_rule_policies:
            raise ValidationError(
                'Une action ne peut avoir à la fois business_rule_policy_id et '
                'business_rule_policies. Utilisez soit la règle prédéfinie (FK), '
                'soit la règle inline (JSON).'
            )
        if self.business_rule_policies:
            from catalog.validators import validate_business_rule_policies
            validate_business_rule_policies(self.business_rule_policies)

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    """
    Tag model mapping to Oracle TAGS table (V007).
    Tags for categorizing actions.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'TAGS'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class ActionTag(models.Model):
    """
    ActionTag model mapping to Oracle ACTION_TAGS table (V007).
    Many-to-many relationship between Action and Tag.
    """
    action = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        db_column='ACTION_ID'
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        db_column='TAG_ID'
    )

    class Meta:
        db_table = 'ACTION_TAGS'
        unique_together = [['action', 'tag']]

    def __str__(self) -> str:
        return f"{self.action.name} - {self.tag.name}"


class UserFavorite(models.Model):
    """
    UserFavorite model mapping to Oracle USER_FAVORITES table (V021).
    Many-to-many relationship between User and Action for favorites.
    """
    user = models.ForeignKey(
        'idp_auth.User',
        on_delete=models.CASCADE,
        db_column='USER_ID'
    )
    action = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        db_column='ACTION_ID'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'USER_FAVORITES'
        unique_together = [['user', 'action']]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.user.username} - {self.action.name}"


class ActionMutex(models.Model):
    """
    ActionMutex model mapping to Oracle ACTION_MUTEX table (V070).
    Story 25.5: Defines mutual exclusion rules between actions.
    Prevents incompatible operations from running simultaneously.
    """
    action = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        db_column='ACTION_ID',
        related_name='mutex_rules'
    )
    incompatible_with = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        db_column='INCOMPATIBLE_WITH_ID',
        related_name='incompatible_mutex_rules'
    )
    same_target = models.BooleanField(
        db_column='SAME_TARGET',
        help_text='If True: mutex applies only when targeting same target_id. If False: mutex applies globally.'
    )
    description = models.CharField(
        max_length=500,
        db_column='DESCRIPTION',
        blank=True,
        null=True,
        help_text='Human-readable explanation of why these actions are incompatible'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='CREATED_AT'
    )

    class Meta:
        db_table = 'ACTION_MUTEX'
        unique_together = [['action', 'incompatible_with']]
        ordering = ['action', 'incompatible_with']

    def __str__(self) -> str:
        scope = "same target" if self.same_target else "global"
        return f"{self.action.name} ⊗ {self.incompatible_with.name} ({scope})"
