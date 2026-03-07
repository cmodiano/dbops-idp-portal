## Description

<!-- Décrivez brièvement les changements apportés -->

## Type de changement

- [ ] Nouvel endpoint DRF
- [ ] Modification d'endpoint existant
- [ ] Bug fix
- [ ] Refactoring
- [ ] Documentation
- [ ] Tests

## Checklists

### Checklist endpoint DRF (si applicable)

> Voir [checklist complète](../docs/backend/standards/endpoint-checklist.md)

- [ ] Validation des paramètres (serializer avec types, min/max, required)
- [ ] Gestion des erreurs (NotFoundError, InvalidStateError, etc.)
- [ ] RBAC vérifié (`permission_classes` avec `AdminProfilePermission` si admin)
- [ ] Audit trail implémenté via `AuditService.create_entry()`
- [ ] Tests unitaires couvrant : happy path, 401, 403, 404, 400
- [ ] Format de réponse : `{"data": ...}` ou `{"error": {"code": ..., "message": ..., "details": ...}}`

### Checklist sécurité

> Voir [pièges courants](../docs/backend/security-django/common-pitfalls.md) et [checklist sécurité](../docs/backend/security-django/pre-pr-checklist.md)

- [ ] Pas de SQL brut (utiliser Django ORM)
- [ ] Pas de secrets dans les logs
- [ ] Pas de N+1 queries (vérifier avec `select_related`/`prefetch_related`)
- [ ] Validation des fichiers uploadés (MIME type, taille)

### Tests

- [ ] Tests ajoutés/mis à jour pour les changements
- [ ] Coverage ≥80% sur les fichiers modifiés
- [ ] `pytest` passe sans erreur

## ADRs concernés

<!-- Listez les ADRs pertinents si applicable -->
<!-- Voir: ../docs/backend/decisions/README.md -->
