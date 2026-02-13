# Checklist Standard — Nouvel Endpoint DRF

> **Objectif :** S'assurer que chaque nouvel endpoint respecte les standards de qualité, sécurité et maintenabilité du projet IDP Portal.
> **Usage :** Vérifier chaque point avant de soumettre une PR. Cocher les items applicables.

## 1. Validation des Paramètres

- [ ] Serializer DRF dédié avec validation exhaustive (pas de validation manuelle dans la vue)
- [ ] `ChoiceField` pour les enums (pas de strings libres)
- [ ] Validation des IDs : entier positif, existence en BD
- [ ] Paramètres de query validés (pagination, filtres)
- [ ] Champs JSON validés avec schéma si critique (`JSONField` + validation applicative)
- [ ] Messages d'erreur explicites en cas de validation échouée

## 2. Gestion des Erreurs

- [ ] Format de réponse erreur standard : `{"error": {"code": "...", "message": "...", "details": {...}}}`
- [ ] Codes HTTP appropriés : 400 (validation), 401 (non authentifié), 403 (non autorisé), 404 (ressource absente), 409 (conflit)
- [ ] Exceptions spécifiques (pas de `except Exception` générique) — cf. [exception-refactor-report](../story-17-6-exception-refactor-report.md)
- [ ] Logging structuré des erreurs avec `structlog` (pas de `print` ou `logging.error` brut)
- [ ] Pas de détails internes exposés dans les réponses 500

## 3. Permissions & RBAC

- [ ] Permission DRF appropriée (`DBOPSProfilePermission`, `IsAuthenticated`, custom)
- [ ] `require_profile` appliqué aux endpoints admin
- [ ] Tests 401 (non authentifié) et 403 (authentifié sans permission)
- [ ] Invalidation cache RBAC si modification des permissions/profils
- [ ] Pas de vérification RBAC manuelle dans la vue — utiliser les classes de permission DRF

## 4. Tests Unitaires & Intégration

- [ ] Tests pour chaque code HTTP attendu (200, 201, 400, 401, 403, 404)
- [ ] Utiliser `UserFactory` (jamais `User.objects.create` avec `is_staff`/`is_superuser`)
- [ ] Utiliser `ActionFactory` pour Actions avec champs JSON
- [ ] URLs avec trailing slash (`/api/v1/resource/` et non `/api/v1/resource`)
- [ ] Créer `RefEngine`/`RefPlatform` si nécessaire pour endpoints admin
- [ ] Tests edge cases : champs vides, valeurs limites, caractères spéciaux
- [ ] Tests de non-régression : vérifier que les endpoints existants ne sont pas cassés
- [ ] Conventions de nommage : `test_<action>_<scenario>` (ex: `test_create_action_invalid_status`)

## 5. Audit Trail

- [ ] Appel `AuditService` pour toute opération CRUD
- [ ] Utiliser `AuditActionType` enum (pas de strings hardcodées)
- [ ] `correlation_id` propagé dans les entrées d'audit
- [ ] `entity_type` et `entity_id` correctement renseignés
- [ ] Tests vérifiant la création d'entrées d'audit

## 6. Format de Réponse

- [ ] Enveloppe standard : `{"data": ...}` pour succès
- [ ] Pagination standard : `{"data": [...], "pagination": {"page", "page_size", "total", "total_pages"}}`
- [ ] Champs JSON désérialisés (pas de strings JSON dans la réponse)
- [ ] Dates au format ISO 8601 UTC
- [ ] IDs numériques (pas de strings)

## 7. Pagination & Filtrage (si applicable)

- [ ] `CustomPageNumberPagination` pour les endpoints de liste
- [ ] Paramètres de filtre documentés et validés
- [ ] `select_related()` / `prefetch_related()` pour éviter N+1 queries
- [ ] Cache TTL si endpoint fréquemment appelé (évaluer la pertinence)
- [ ] Invalidation cache si données mutées

## 8. Performance

- [ ] Pas de N+1 queries — utiliser `select_related()` et `prefetch_related()`
- [ ] `only()` / `defer()` pour limiter les colonnes si table large
- [ ] Logique métier dans le service (pas dans la vue ou le serializer)
- [ ] `@transaction.atomic` pour les opérations multi-tables

## 9. Documentation

- [ ] Docstring sur la vue/viewset décrivant l'endpoint
- [ ] Paramètres de query documentés si non évidents
- [ ] Notes dans les Dev Notes de la story si décision technique importante

---

**Références :**
- [Conventions de test](../../tests/README.md)
- [Issues connues](../../tests/KNOWN_ISSUES.md)
- [Notes migration DRF](../drf-api-migration-notes.md)
- [Conventions de logging](../logging-conventions.md)
- [Security pitfalls](../security/common-pitfalls.md)
- [Pre-PR security checklist](../security/pre-pr-checklist.md)
