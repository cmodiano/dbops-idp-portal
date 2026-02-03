import json
import logging
from django.db import models
from idp_auth.models import User
from integrations.models import Integration

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


class Action(models.Model):
    """
    Action model mapping to Oracle ACTIONS_CATALOG table (V002, V017, V019, V022, V027, V031, V036).
    Represents an action or workflow in the catalog.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    description = models.CharField(max_length=4000, null=True, blank=True, db_column='DESCRIPTION')
    category = models.CharField(
        max_length=50,
        choices=ActionCategory.choices,
        db_column='CATEGORY'
    )
    engine = models.CharField(
        max_length=50,
        choices=ActionEngine.choices,
        db_column='ENGINE'
    )
    platform = models.CharField(
        max_length=50,
        choices=ActionPlatform.choices,
        db_column='PLATFORM'
    )
    # CLOB fields - using TextField with JSON serialization helpers
    parameters_schema = models.TextField(null=True, blank=True, db_column='PARAMETERS_SCHEMA')
    impact_rules = models.TextField(null=True, blank=True, db_column='IMPACT_RULES')
    change_type_config = models.TextField(null=True, blank=True, db_column='CHANGE_TYPE_CONFIG')
    documentation_md = models.TextField(null=True, blank=True, db_column='DOCUMENTATION_MD')
    remediation_rules = models.TextField(null=True, blank=True, db_column='REMEDIATION_RULES')
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

    class Meta:
        db_table = 'ACTIONS_CATALOG'
        ordering = ['name']

    def __str__(self):
        return self.name

    # JSON field helpers for CLOB fields
    def get_parameters_schema(self):
        """Deserialize JSON from CLOB."""
        if self.parameters_schema:
            try:
                return json.loads(self.parameters_schema)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize parameters_schema for Action {self.id}: {e}")
                return None
        return None

    def set_parameters_schema(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.parameters_schema = json.dumps(value)
        else:
            self.parameters_schema = None

    def get_impact_rules(self):
        """Deserialize JSON from CLOB."""
        if self.impact_rules:
            try:
                return json.loads(self.impact_rules)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize impact_rules for Action {self.id}: {e}")
                return None
        return None

    def set_impact_rules(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.impact_rules = json.dumps(value)
        else:
            self.impact_rules = None

    def get_change_type_config(self):
        """Deserialize JSON from CLOB."""
        if self.change_type_config:
            try:
                return json.loads(self.change_type_config)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize change_type_config for Action {self.id}: {e}")
                return None
        return None

    def set_change_type_config(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.change_type_config = json.dumps(value)
        else:
            self.change_type_config = None

    def get_remediation_rules(self):
        """Deserialize JSON from CLOB."""
        if self.remediation_rules:
            try:
                return json.loads(self.remediation_rules)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize remediation_rules for Action {self.id}: {e}")
                return None
        return None

    def set_remediation_rules(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.remediation_rules = json.dumps(value)
        else:
            self.remediation_rules = None


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

    def __str__(self):
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

    def __str__(self):
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

    def __str__(self):
        return f"{self.user.username} - {self.action.name}"
