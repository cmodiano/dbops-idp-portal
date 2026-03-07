# Architecture Greenfield — Auth & RBAC

**Document type:** Architecture vision (hypothetical from-scratch design)  
**Date:** 2026-02-27  
**Purpose:** Document architectural choices that would be made if building the IDP Portal auth and RBAC system from scratch. Serves as a reference for future refactoring or greenfield projects.

---

## 1. Framework

**Choice: Django + Django REST Framework**

- Mature ecosystem, admin, ORM, auth primitives
- Good fit for internal portals with API + admin needs
- No change from current stack

---

## 2. Single User Model

**Choice: One user model for both admin and API**

- `AUTH_USER_MODEL` = custom `User` extending `AbstractBaseUser` (or `AbstractUser`)
- Same table for:
  - SAML users (no password, `saml_subject` set)
  - LDAP service accounts (no password)
  - Admin users (password or LDAP backend)
- Avoid dual tables (`USERS` vs `AUTH_USER`); single source of truth

**Benefits:**
- Simpler mental model
- No sync between two user stores
- Admin and API share the same user records

---

## 3. Auth Stack

| Need | Choice |
|------|--------|
| **SAML SSO** | `django-saml2-auth` or `python3-saml` |
| **LDAP admin** | `django-auth-ldap` if admins log in via LDAP |
| **LDAP service accounts** | Custom `LDAPService` with `ldap3` for JWT service-login flow |
| **JWT** | `djangorestframework-simplejwt` |
| **Auth backends** | `['django_saml2_auth.backends.Saml2Backend', 'django_auth_ldap.backend.LDAPBackend', 'django.contrib.auth.backends.ModelBackend']` |

**Rationale:**
- Use standard packages where they fit
- Custom LDAP service for service-account JWT flow (django-auth-ldap is session-oriented)
- `simplejwt` for token lifecycle, refresh, blacklisting

---

## 4. Profile & RBAC

**Choice: Keep custom Profile model**

Django's `Group` + `Permission` are model-level (add/change/delete). They cannot express:
- "Profile DBA can run actions [1, 2, 3] in envs [dev, prod]"
- "Profile DBA can target names matching `prod-*`"
- "Profile DBOPS has ALL actions and ALL targets"

**Models:**
- `Profile` (name, ad_group, is_admin, is_auditor)
- `ProfileActionPermission` (LIST/PATTERN/ALL, action_ids, tag_patterns, environments)
- `ProfileTargetPermission` (LIST/PATTERN/ALL, target_names, target_patterns, filter_by_attribute, exclusion_patterns)

**Schema change:** Use PostgreSQL `JSONField` instead of CLOB + manual JSON:

```python
action_ids = models.JSONField(default=list)       # [1, 2, 3]
tag_patterns = models.JSONField(default=list)    # ["prod-*"]
environments = models.JSONField(default=list)    # ["dev", "prod"]
```

---

## 5. Database

**Choice: PostgreSQL (when possible)**

- Native JSON/JSONB for permission arrays
- Real booleans (no NUMBER(1) workarounds)
- Django migrations only (no Flyway)
- Easier local development

**If Oracle is mandatory:** Keep it; the rest of the design still applies. Use `TextField` + JSON serialization for Oracle compatibility.

---

## 6. Admin

**Choice: Use Django admin for profile management**

- Register `Profile`, `ProfileActionPermission`, `ProfileTargetPermission`
- Inline editing of permissions on the Profile change page
- Custom form fields or widgets for JSON arrays
- Single place to manage profiles instead of a separate admin REST API

---

## 7. User ↔ Profile

**Choice: ForeignKey from User to Profile**

```python
class User(AbstractBaseUser):
    username = models.CharField(max_length=150, unique=True)
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    saml_subject = models.CharField(max_length=512, unique=True, null=True, blank=True)
    # ...
```

- SAML/LDAP: resolve AD groups → Profile → set `user.profile`
- Permissions: `user.profile` → `ProfileActionPermission` / `ProfileTargetPermission`

---

## 8. JWT Flow

1. **SAML callback:** Create/update `User`, set `profile`, issue JWT (e.g. via `simplejwt`)
2. **LDAP service login:** Bind → fetch groups → resolve Profile → create/update `User` → issue JWT
3. **API:** Validate JWT, load `request.user` from token

---

## 9. Comparison: Current vs Greenfield

| Area | Current | Greenfield |
|------|---------|------------|
| User model | Separate `USERS` + `AUTH_USER` | Single custom `AUTH_USER_MODEL` |
| Profile RBAC | Custom Profile + permissions | Same concept, `JSONField` for arrays |
| LDAP | Custom `LDAPService` | Same for service-login JWT flow |
| SAML | Custom flow | Same or `django-saml2-auth` |
| JWT | Custom | `djangorestframework-simplejwt` |
| DB | Oracle + Flyway | PostgreSQL + Django migrations (if possible) |
| Admin | Profiles via REST API | Profiles in Django admin |

---

## 10. Summary

- **Single user model** for admin and API
- **Custom Profile RBAC** (Django Group/Permission don't fit the domain)
- **Standard packages** for SAML, JWT, LDAP where applicable
- **PostgreSQL + JSONField** for simpler schema and permissions
- **Django admin** for profile and permission management

The main shift from the current implementation is unifying users and leaning more on Django's auth and admin, while keeping the custom Profile and RBAC model.

---

## References

- [architecture.md](architecture.md) — Current architecture
- [sso-architecture.md](sso-architecture.md) — SSO flows
- [security-architecture.md](security-architecture.md) — Security design
