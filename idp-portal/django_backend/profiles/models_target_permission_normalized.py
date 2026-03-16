"""
Story 78.12: Normalized profile target permission models.

Maps the Flyway-managed tables PROFILE_TARGET_ALLOWLIST, PROFILE_TARGET_PATTERNS,
PROFILE_TARGET_ATTR_FILTERS, PROFILE_TARGET_EXCLUSIONS to Django ORM models (managed = False).
"""
from __future__ import annotations

from django.db import models


class ProfileTargetAllowlist(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileTargetPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='allowlist_entries',
    )
    target_name = models.CharField(max_length=255, db_column='TARGET_NAME')

    class Meta:
        managed = False
        db_table = 'PROFILE_TARGET_ALLOWLIST'
        unique_together = [['profile', 'target_name']]

    def __str__(self) -> str:
        return f"ProfileTargetAllowlist(profile_id={self.profile_id}, target_name={self.target_name})"


class ProfileTargetPattern(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileTargetPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='pattern_entries',
    )
    pattern = models.CharField(max_length=255, db_column='PATTERN')

    class Meta:
        managed = False
        db_table = 'PROFILE_TARGET_PATTERNS'
        unique_together = [['profile', 'pattern']]

    def __str__(self) -> str:
        return f"ProfileTargetPattern(profile_id={self.profile_id}, pattern={self.pattern})"


class ProfileTargetAttributeFilter(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileTargetPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='attribute_filter_entries',
    )
    attribute_key = models.CharField(max_length=255, db_column='ATTRIBUTE_KEY')
    attribute_value = models.CharField(max_length=255, db_column='ATTRIBUTE_VALUE')

    class Meta:
        managed = False
        db_table = 'PROFILE_TARGET_ATTR_FILTERS'
        unique_together = [['profile', 'attribute_key', 'attribute_value']]

    def __str__(self) -> str:
        return (
            f"ProfileTargetAttributeFilter(profile_id={self.profile_id}, "
            f"attribute_key={self.attribute_key}, attribute_value={self.attribute_value})"
        )


class ProfileTargetExclusion(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileTargetPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='exclusion_entries',
    )
    exclusion_pattern = models.CharField(max_length=255, db_column='EXCLUSION_PATTERN')

    class Meta:
        managed = False
        db_table = 'PROFILE_TARGET_EXCLUSIONS'
        unique_together = [['profile', 'exclusion_pattern']]

    def __str__(self) -> str:
        return f"ProfileTargetExclusion(profile_id={self.profile_id}, exclusion_pattern={self.exclusion_pattern})"
