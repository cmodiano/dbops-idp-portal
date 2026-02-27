from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User as AuthUser
from django.http import HttpRequest

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

