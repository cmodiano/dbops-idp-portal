"""
Reference models for REF_ENGINES and REF_PLATFORMS tables.
Story 13.7 - Reference tables for engines and platforms.
"""

from django.db import models


class RefEngineQuerySet(models.QuerySet):
    """Custom QuerySet for RefEngine model."""

    def active(self):
        """Return only active engines."""
        return self.filter(is_active=1)

    def ordered(self):
        """Return engines ordered by display_order."""
        return self.order_by('display_order', 'code')


class RefEngineManager(models.Manager.from_queryset(RefEngineQuerySet)):
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

    objects = RefEngineManager()

    class Meta:
        db_table = 'REF_ENGINES'
        ordering = ['display_order', 'code']
        verbose_name = 'Engine Reference'
        verbose_name_plural = 'Engine References'

    def __str__(self):
        return f"{self.code} ({'active' if self.is_active else 'inactive'})"


class RefPlatformQuerySet(models.QuerySet):
    """Custom QuerySet for RefPlatform model."""

    def active(self):
        """Return only active platforms."""
        return self.filter(is_active=1)

    def ordered(self):
        """Return platforms ordered by display_order."""
        return self.order_by('display_order', 'code')


class RefPlatformManager(models.Manager.from_queryset(RefPlatformQuerySet)):
    """Custom manager for RefPlatform model."""


class RefPlatform(models.Model):
    """
    Reference table for execution platforms.
    Maps to Oracle REF_PLATFORMS table (V051).
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    code = models.CharField(max_length=50, unique=True, db_column='CODE')
    label = models.CharField(max_length=100, db_column='LABEL')
    display_order = models.IntegerField(default=0, db_column='DISPLAY_ORDER')
    is_active = models.IntegerField(default=1, db_column='IS_ACTIVE')

    objects = RefPlatformManager()

    class Meta:
        db_table = 'REF_PLATFORMS'
        ordering = ['display_order', 'code']
        verbose_name = 'Platform Reference'
        verbose_name_plural = 'Platform References'

    def __str__(self):
        return f"{self.code} ({'active' if self.is_active else 'inactive'})"
