import json
import logging
from django.db import models

logger = logging.getLogger(__name__)


class AuthFlow(models.TextChoices):
    """Authentication flow enum matching FastAPI model."""
    TOKEN = 'token', 'Token'
    BASIC = 'basic', 'Basic'
    BASIC_THEN_TOKEN = 'basic_then_token', 'Basic Then Token'
    PAT = 'pat', 'Personal Access Token'


class IntegrationType(models.TextChoices):
    """Integration type enum. DB allows free-form type (V024); these are suggested values."""
    AAP = 'aap', 'AAP'
    SERVICENOW = 'servicenow', 'ServiceNow'
    TERRAFORM = 'terraform', 'Terraform'
    AZUREDEVOPS = 'azuredevops', 'Azure DevOps'
    JIRA = 'jira', 'Jira'
    GITHUB_ACTIONS = 'github_actions', 'GitHub Actions'
    # Epic 13: inventory source for targets (serveurs, bases). inventory = API, inventory_db = schema DBOPS_INVENTORY
    INVENTORY = 'inventory', 'Inventaire (API)'
    INVENTORY_DB = 'inventory_db', 'Inventaire (schéma BD)'


class IntegrationManager(models.Manager):
    """
    Custom manager for Integration model.
    Provides query methods for common integration queries.
    """
    
    def list_active(self):
        """
        List active integrations.
        Note: Currently no 'active' field in model, so returns all integrations.
        Can be extended when active field is added.
        
        Returns:
            QuerySet of all integrations ordered by name
        """
        return self.all().order_by('name')
    
    def get_by_type(self, integration_type: str):
        """
        Get integration by type.
        Returns the most recently created integration of the given type.
        
        Args:
            integration_type: Type of integration (aap, servicenow, etc.)
        
        Returns:
            Integration instance or None
        """
        return self.filter(type=integration_type).order_by('-created_at').first()


class Integration(models.Model):
    """
    Integration model mapping to Oracle INTEGRATIONS table (V020).
    Represents remote platform configuration for execution.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    type = models.CharField(
        max_length=50,
        choices=IntegrationType.choices,
        db_column='TYPE'
    )
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    base_url = models.CharField(max_length=2000, db_column='BASE_URL')
    credential_ref = models.CharField(max_length=500, null=True, blank=True, db_column='CREDENTIAL_REF')
    icon = models.CharField(max_length=500, null=True, blank=True, db_column='ICON')
    auth_flow = models.CharField(
        max_length=50,
        choices=AuthFlow.choices,
        null=True,
        blank=True,
        db_column='AUTH_FLOW'
    )
    token_url = models.CharField(max_length=2000, null=True, blank=True, db_column='TOKEN_URL')
    # CLOB field - using TextField with JSON serialization helper
    config = models.TextField(null=True, blank=True, db_column='CONFIG')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    
    # Custom manager
    objects = IntegrationManager()

    class Meta:
        db_table = 'INTEGRATIONS'
        ordering = ['name']

    def __str__(self):
        return self.name
    
    # JSON field helper for config
    def get_config(self):
        """Deserialize JSON from CLOB."""
        if self.config:
            try:
                return json.loads(self.config)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize config for Integration {self.id}: {e}")
                return None
        return None
    
    def set_config(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.config = json.dumps(value)
        else:
            self.config = None
