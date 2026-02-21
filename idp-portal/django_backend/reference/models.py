"""
Reference models for REF_ENGINES and REF_CATEGORIES tables.
Story 13.7 - Reference table for engines.
Story 2.30 - Reference table for categories.
Story 31.9 - RefPlatform removed (replaced by IntegrationTypeCatalogue).
"""

from django.db import models


class RefEngineQuerySet(models.QuerySet):
    """Custom QuerySet for RefEngine model."""

    def active(self) -> models.QuerySet["RefEngine"]:
        """Return only active engines."""
        return self.filter(is_active=1)

    def ordered(self) -> models.QuerySet["RefEngine"]:  # type: ignore[override]
        """Return engines ordered by display_order."""
        return self.order_by('display_order', 'code')


class RefEngineManager(models.Manager.from_queryset(RefEngineQuerySet)):  # type: ignore[misc]
    """Custom manager for RefEngine model."""


class RefEngine(models.Model):
    """
    Reference table for database engines/technologies.
    Maps to Oracle REF_ENGINES table (V049).
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    code = models.CharField(max_length=50, unique=True, db_column='CODE')
    label = models.CharField(max_length=100, db_column='LABEL')
    display_order = models.IntegerField(default=0, db_column='DISPLAY_ORDER')
    is_active = models.IntegerField(default=1, db_column='IS_ACTIVE')
    icon_url = models.CharField(max_length=500, null=True, blank=True, db_column='ICON_URL')

    objects = RefEngineManager()

    class Meta:
        db_table = 'REF_ENGINES'
        ordering = ['display_order', 'code']
        verbose_name = 'Engine Reference'
        verbose_name_plural = 'Engine References'

    def __str__(self) -> str:
        return f"{self.code} ({'active' if self.is_active else 'inactive'})"


class RefCategoryQuerySet(models.QuerySet):
    """Custom QuerySet for RefCategory model."""

    def active(self) -> models.QuerySet["RefCategory"]:
        """Return only active categories."""
        return self.filter(is_active=1)

    def ordered(self) -> models.QuerySet["RefCategory"]:  # type: ignore[override]
        """Return categories ordered by display_order, code."""
        return self.order_by('display_order', 'code')


RefCategoryManager = models.Manager.from_queryset(RefCategoryQuerySet)


class RefCategory(models.Model):
    """
    Reference table for action categories.
    Maps to Oracle REF_CATEGORIES table (V059).
    Story 2.30 - Administrable categories for catalog organization.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    code = models.CharField(max_length=50, unique=True, db_column='CODE')
    label = models.CharField(max_length=100, db_column='LABEL')
    display_order = models.IntegerField(default=0, db_column='DISPLAY_ORDER')
    is_active = models.IntegerField(default=1, db_column='IS_ACTIVE')

    objects = RefCategoryManager()

    class Meta:
        db_table = 'REF_CATEGORIES'
        ordering = ['display_order', 'code']
        verbose_name = 'Category Reference'
        verbose_name_plural = 'Category References'

    def __str__(self) -> str:
        return f"{self.code} ({'active' if self.is_active else 'inactive'})"
