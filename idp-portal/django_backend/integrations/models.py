from django.db import models


class IntegrationType(models.TextChoices):
    """Integration type enum matching Oracle CHECK constraint."""
    AAP = 'aap', 'AAP'
    SERVICENOW = 'servicenow', 'ServiceNow'
    TERRAFORM = 'terraform', 'Terraform'
    AZUREDEVOPS = 'azuredevops', 'Azure DevOps'
    JIRA = 'jira', 'Jira'
    GITHUB_ACTIONS = 'github_actions', 'GitHub Actions'


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
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'INTEGRATIONS'
        ordering = ['name']

    def __str__(self):
        return self.name
