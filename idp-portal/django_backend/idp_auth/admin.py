from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User as AuthUser
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest
from django.utils import timezone

from idp_auth.models import APIKey
from idp_auth.models import User as IDPUser


# ─── Auth User Admin (django.contrib.auth.User) ───────────────────────────────
admin.site.unregister(AuthUser)


@admin.register(AuthUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active', 'date_joined')
    # Simplifié par rapport au défaut Django (is_staff, is_superuser, is_active, groups) :
    # is_superuser et groups retirés — usage DBOPS interne, seuls is_staff/is_active pertinents
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')


# ─── Auth Group Admin (django.contrib.auth.Group) ─────────────────────────────
admin.site.unregister(Group)


@admin.register(Group)
class CustomGroupAdmin(GroupAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# ─── IDP User Admin (idp_auth.User — utilisateurs SAML/DBOPS) ─────────────────
@admin.register(IDPUser)
class IDPUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'display_name', 'profile', 'created_at')
    list_filter = ('profile',)
    search_fields = ('username', 'display_name')
    readonly_fields = ('created_at', 'updated_at', 'saml_subject')

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Utilisateurs gérés exclusivement via SAML — la création manuelle créerait des comptes orphelins
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        # Utilisateurs gérés exclusivement via SAML — ne pas permettre la suppression manuelle
        return False


# ─── APIKey Admin (idp_auth.APIKey) ───────────────────────────────────────────
class CreateAPIKeyForm(forms.ModelForm):
    class Meta:
        model = APIKey
        fields = ['user', 'name', 'scope', 'expires_at']


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'scope', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'scope', 'user')
    search_fields = ('name', 'user__username')
    readonly_fields = ('key_hash', 'created_at', 'updated_at')
    actions = ['revoke_api_keys']

    def has_add_permission(self, request: HttpRequest) -> bool:
        return True

    def get_form(self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any) -> type[ModelForm[Any]]:
        if obj is None:
            kwargs.setdefault('form', CreateAPIKeyForm)
        return super().get_form(request, obj, change=change, **kwargs)

    def save_model(self, request: HttpRequest, obj: Any, form: ModelForm[Any], change: bool) -> None:
        if not change:
            instance, raw_key = APIKey.objects.create_key(
                user=obj.user,
                name=obj.name,
                scope=obj.scope or None,
            )
            if obj.expires_at:
                instance.expires_at = obj.expires_at
                instance.save(update_fields=['expires_at', 'updated_at'])
            obj.pk = instance.pk
            obj.id = instance.id
            obj.expires_at = instance.expires_at
            obj.updated_at = getattr(instance, 'updated_at', None)
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
