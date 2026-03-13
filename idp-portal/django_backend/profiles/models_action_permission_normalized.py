"""
Story 78.11: Normalized profile action permission models.

Maps the Flyway-managed tables PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS,
PROFILE_ACTION_ENVS to Django ORM models (managed = False).
"""
from __future__ import annotations

from django.db import models


class ProfileActionAllowlist(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileActionPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='allowlist_entries',
    )
    action_id = models.IntegerField(db_column='ACTION_ID')

    class Meta:
        managed = False
        db_table = 'PROFILE_ACTION_ALLOWLIST'
        unique_together = [['profile', 'action_id']]

    def __str__(self) -> str:
        return f"ProfileActionAllowlist(profile_id={self.profile_id}, action_id={self.action_id})"


class ProfileActionTagPattern(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileActionPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='tag_pattern_entries',
    )
    tag_pattern = models.CharField(max_length=255, db_column='TAG_PATTERN')

    class Meta:
        managed = False
        db_table = 'PROFILE_ACTION_TAG_PATTERNS'
        unique_together = [['profile', 'tag_pattern']]

    def __str__(self) -> str:
        return f"ProfileActionTagPattern(profile_id={self.profile_id}, tag_pattern={self.tag_pattern})"


class ProfileActionEnv(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    profile = models.ForeignKey(
        'profiles.ProfileActionPermission',
        on_delete=models.CASCADE,
        db_column='PROFILE_ID',
        related_name='env_entries',
    )
    environment = models.CharField(max_length=255, db_column='ENVIRONMENT')

    class Meta:
        managed = False
        db_table = 'PROFILE_ACTION_ENVS'
        unique_together = [['profile', 'environment']]

    def __str__(self) -> str:
        return f"ProfileActionEnv(profile_id={self.profile_id}, environment={self.environment})"
