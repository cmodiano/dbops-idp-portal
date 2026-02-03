from django.db import models


class User(models.Model):
    """
    User model mapping to Oracle USERS table (V001).
    Custom user model (not django.contrib.auth.User).
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    username = models.CharField(max_length=255, unique=True, db_column='USERNAME')
    display_name = models.CharField(max_length=255, null=True, blank=True, db_column='DISPLAY_NAME')
    profile = models.CharField(max_length=50, db_column='PROFILE')
    saml_subject = models.CharField(max_length=512, null=True, blank=True, db_column='SAML_SUBJECT')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'USERS'
        ordering = ['username']

    def __str__(self):
        return self.username
