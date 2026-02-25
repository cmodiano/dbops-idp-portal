from django.contrib import admin

from idp_auth.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'scope', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'scope')
    search_fields = ('name', 'user__username')
    readonly_fields = ('key_hash', 'created_at', 'updated_at')
