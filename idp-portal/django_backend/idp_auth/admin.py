from django.contrib import admin
from django.http import HttpRequest

from idp_auth.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'scope', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'scope')
    search_fields = ('name', 'user__username')
    readonly_fields = ('key_hash', 'created_at', 'updated_at')

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Block creation from admin UI; keys must be created via APIKeyManager.create_key()."""
        return False
