from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest
from django.utils import timezone

from idp_auth.models import APIKey


class CreateAPIKeyForm(forms.ModelForm):
    class Meta:
        model = APIKey
        fields = ['user', 'name', 'scope', 'expires_at']
        # key_hash est exclu — auto-généré par create_key()


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'scope', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'scope')
    search_fields = ('name', 'user__username')
    readonly_fields = ('key_hash', 'created_at', 'updated_at')
    actions = ['revoke_api_keys']

    def has_add_permission(self, request: HttpRequest) -> bool:
        return True

    def get_form(self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any) -> type[ModelForm[Any]]:
        if obj is None:  # Ajout (création)
            kwargs.setdefault('form', CreateAPIKeyForm)
        return super().get_form(request, obj, change=change, **kwargs)

    def save_model(self, request: HttpRequest, obj: Any, form: ModelForm[Any], change: bool) -> None:
        if not change:  # Création uniquement
            instance, raw_key = APIKey.objects.create_key(
                user=obj.user,
                name=obj.name,
                scope=obj.scope or None,
            )
            if obj.expires_at:
                instance.expires_at = obj.expires_at
                instance.save(update_fields=['expires_at', 'updated_at'])
            self.message_user(
                request,
                f"Clé créée (ID={instance.id}). Copiez-la MAINTENANT — elle ne sera plus affichée : {raw_key}",
                messages.SUCCESS,
            )
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description='Révoquer les clés sélectionnées')
    def revoke_api_keys(self, request: HttpRequest, queryset: QuerySet[APIKey]) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        level = messages.SUCCESS if updated > 0 else messages.WARNING
        self.message_user(request, f"{updated} clé(s) révoquée(s).", level)
