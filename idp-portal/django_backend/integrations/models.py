import json
import structlog
from django.db import models
from django.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)


def _validate_json_schema(value: dict) -> None:
    """
    Validate that a dictionary represents a valid JSON Schema structure.
    Code Review Fix Issue #4: Ensure required_params/optional_params are valid JSON Schema.

    Raises:
        ValidationError: If the value is not a valid JSON Schema structure
    """
    if not isinstance(value, dict):
        raise ValidationError("JSON Schema must be a dictionary")

    # Basic JSON Schema validation - must have 'type' field
    if 'type' not in value:
        raise ValidationError("JSON Schema must have a 'type' field")

    valid_types = ['object', 'array', 'string', 'number', 'integer', 'boolean', 'null']
    if value['type'] not in valid_types:
        raise ValidationError(f"JSON Schema 'type' must be one of: {', '.join(valid_types)}")

    # If type is 'object', should have 'properties' or be empty
    if value['type'] == 'object' and 'properties' in value:
        if not isinstance(value['properties'], dict):
            raise ValidationError("JSON Schema 'properties' must be a dictionary")


class HealthStatus(models.TextChoices):
    """Story 51.1: Health check status for Integration model."""
    OK = 'ok', 'OK'
    ERROR = 'error', 'Erreur'
    UNKNOWN = 'unknown', 'Inconnu'


class AuthFlow(models.TextChoices):
    """Authentication flow enum."""
    TOKEN = 'token', 'Token'
    BASIC = 'basic', 'Basic'
    BASIC_THEN_TOKEN = 'basic_then_token', 'Basic Then Token'
    PAT = 'pat', 'Personal Access Token'
    OAUTH2_CLIENT_CREDENTIALS = 'oauth2_client_credentials', 'OAuth2 Client Credentials'  # Story 31.12
    API_KEY = 'api_key', 'API Key (header personnalisé)'  # Story 31.12  # pragma: allowlist secret


class IntegrationStatus(models.TextChoices):
    """Story 24.3: Integration validation status against type catalogue."""
    VALID = 'valid', 'Valide'
    INVALID = 'invalid', 'Invalide'
    DEPRECATED = 'deprecated', 'Déprécié'


class IntegrationType(models.TextChoices):
    """Integration type enum. DB allows free-form type (V024); these are suggested values."""
    AAP = 'aap', 'AAP'
    SERVICENOW = 'servicenow', 'ServiceNow'
    TERRAFORM = 'terraform', 'Terraform'
    TERRAFORM_CLOUD = 'terraform_cloud', 'Terraform Cloud'
    AZUREDEVOPS = 'azuredevops', 'Azure DevOps'
    AZURE_DEVOPS = 'azure_devops', 'Azure DevOps Pipelines'
    JIRA = 'jira', 'Jira'
    GITHUB_ACTIONS = 'github_actions', 'GitHub Actions'
    TOWER = 'tower', 'Ansible Tower'
    VAULT = 'vault', 'HashiCorp Vault'
    # Epic 13: inventory source for targets (serveurs, bases). inventory = API, inventory_db = schema DBOPS_INVENTORY
    INVENTORY = 'inventory', 'Inventaire (API)'
    INVENTORY_DB = 'inventory_db', 'Inventaire (schéma BD)'


class IntegrationRole(models.TextChoices):
    """Story 29.1: Integration role — platform (execution) vs service (consumption)."""
    PLATFORM = 'platform', "Plateforme d'exécution"
    SERVICE = 'service', 'Service consommé'


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
    # Story 27.11: FK vers intégration Vault pour résoudre les secrets (NULL = Vault par défaut)
    secret_service = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_integrations',
        db_column='SECRET_SERVICE_ID',
        limit_choices_to={'type': IntegrationType.VAULT},
    )
    # Story 24.3: Validation status against type catalogue
    status = models.CharField(
        max_length=20,
        choices=IntegrationStatus.choices,
        default=IntegrationStatus.VALID,
        db_column='STATUS',
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    # Story 51.1: Health check fields
    health_status = models.CharField(
        max_length=10,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
        db_column='HEALTH_STATUS',
        db_index=True,
    )
    health_checked_at = models.DateTimeField(null=True, blank=True, db_column='HEALTH_CHECKED_AT')
    health_error_message = models.TextField(null=True, blank=True, db_column='HEALTH_ERROR_MESSAGE')

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


class IntegrationTypeCatalogue(models.Model):
    """
    Story 24.1: Formal catalogue of integration types.
    Defines supported integration types (AAP, ServiceNow, etc.) with metadata.
    Maps to Oracle INTEGRATION_TYPE_CATALOGUE table.
    """
    code = models.CharField(max_length=50, primary_key=True, db_column='CODE')
    name = models.CharField(max_length=255, db_column='NAME')
    description = models.TextField(blank=True, default='', db_column='DESCRIPTION')
    version = models.CharField(max_length=20, default='1.0', db_column='VERSION')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    integration_role = models.CharField(
        max_length=20,
        choices=IntegrationRole.choices,
        default=IntegrationRole.PLATFORM,
        db_column='INTEGRATION_ROLE',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'INTEGRATION_TYPE_CATALOGUE'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.name})"


class IntegrationAction(models.Model):
    """
    Story 24.1: Actions supported by an integration type.
    Each action defines required/optional params and response format.
    Maps to Oracle INTEGRATION_ACTIONS table.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    integration_type = models.ForeignKey(
        IntegrationTypeCatalogue,
        on_delete=models.CASCADE,
        related_name='actions',
        db_column='INTEGRATION_TYPE_CODE'
    )
    action_code = models.CharField(max_length=100, db_column='ACTION_CODE')
    action_label = models.CharField(max_length=255, db_column='ACTION_LABEL')
    description = models.TextField(blank=True, default='', db_column='DESCRIPTION')
    required_params = models.TextField(blank=True, default='{}', db_column='REQUIRED_PARAMS')
    optional_params = models.TextField(blank=True, default='{}', db_column='OPTIONAL_PARAMS')
    response_format = models.TextField(blank=True, default='{}', db_column='RESPONSE_FORMAT')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'INTEGRATION_ACTIONS'
        ordering = ['action_code']
        unique_together = [('integration_type', 'action_code')]

    def __str__(self):
        # Fix Issue #11: Use human-readable code instead of ID
        return f"{self.integration_type.code}:{self.action_code}"

    def get_required_params(self):
        """Deserialize required_params JSON."""
        if self.required_params:
            try:
                return json.loads(self.required_params)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize required_params for IntegrationAction {self.id}: {e}")
                return {}
        return {}

    def set_required_params(self, value):
        """Serialize required_params to JSON with validation."""
        if value is not None and value != {}:
            _validate_json_schema(value)  # Fix Issue #4
        self.required_params = json.dumps(value) if value is not None else '{}'

    def get_optional_params(self):
        """Deserialize optional_params JSON."""
        if self.optional_params:
            try:
                return json.loads(self.optional_params)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize optional_params for IntegrationAction {self.id}: {e}")
                return {}
        return {}

    def set_optional_params(self, value):
        """Serialize optional_params to JSON with validation."""
        if value is not None and value != {}:
            _validate_json_schema(value)  # Fix Issue #4
        self.optional_params = json.dumps(value) if value is not None else '{}'

    def get_response_format(self):
        """Deserialize response_format JSON."""
        if self.response_format:
            try:
                return json.loads(self.response_format)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize response_format for IntegrationAction {self.id}: {e}")
                return {}
        return {}

    def set_response_format(self, value):
        """Serialize response_format to JSON."""
        self.response_format = json.dumps(value) if value is not None else '{}'
