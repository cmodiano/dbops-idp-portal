# Validation du Statut des Intégrations

> Story 24.3 — Système de validation `valid` / `invalid` / `deprecated` pour les intégrations.

## Architecture

### Flux de Validation

```
IntegrationTypeCatalogue (is_active?)
         │
         ▼
IntegrationValidationService
  ├── validate_integration()        → IntegrationStatus
  ├── validate_all_integrations()   → stats {valid, invalid, deprecated, updated}
  └── get_integration_validation_details() → détails structurés
         │
         ▼
Integration.status (CharField, indexé)
  ├── valid      → Type existe et actif
  ├── deprecated → Type existe mais is_active=False
  └── invalid    → Type absent du catalogue
```

### Points d'entrée

| Déclencheur | Mécanisme | Mise à jour DB |
|-------------|-----------|----------------|
| Création d'intégration | `IntegrationService.create_integration()` | Oui |
| Modification d'intégration | `IntegrationService.update_integration()` | Oui |
| Validation à la demande | `GET /api/v1/admin/integrations/{id}/validate/` | Oui |
| Validation batch | `POST /api/v1/admin/integrations/validate-all/` | Oui |
| Cron quotidien | `python manage.py validate_integrations` | Oui (sauf --dry-run) |

## Signification des Statuts

| Statut | Condition | Couleur UI | Impact |
|--------|-----------|------------|--------|
| `valid` | Type existe dans `IntegrationTypeCatalogue` ET `is_active=True` | Vert | Utilisation normale |
| `deprecated` | Type existe dans catalogue ET `is_active=False` | Orange | Warning affiché, modification permise, utilisation dans nouveaux workflows bloquée (Story 24.4) |
| `invalid` | Type n'existe PAS dans le catalogue | Rouge | Modification bloquée, utilisation impossible |

## Règles de Calcul

```python
def validate_integration(integration) -> IntegrationStatus:
    catalogue_type = IntegrationTypeCatalogue.objects.filter(code=integration.type).first()

    if not catalogue_type:
        return INVALID       # Type absent du catalogue
    if not catalogue_type.is_active:
        return DEPRECATED    # Type désactivé
    return VALID             # Type actif et supporté
```

## Guide de Résolution

### Intégration Invalide (`status=invalid`)

**Cause :** Le type de l'intégration n'existe pas (ou plus) dans le catalogue `IntegrationTypeCatalogue`.

**Actions :**
1. Vérifier le type de l'intégration : `Integration.objects.get(id=<id>).type`
2. Vérifier le catalogue : `IntegrationTypeCatalogue.objects.filter(code='<type>')`
3. Si le type n'existe pas, l'ajouter au catalogue ou migrer l'intégration vers un type existant
4. Relancer la validation : `GET /api/v1/admin/integrations/{id}/validate/`

### Intégration Dépréciée (`status=deprecated`)

**Cause :** Le type existe mais `is_active=False` dans le catalogue.

**Actions :**
1. Identifier le nouveau type de remplacement
2. Mettre à jour l'intégration vers le nouveau type
3. Si le type doit être réactivé : `IntegrationTypeCatalogue.objects.filter(code='<type>').update(is_active=True)`

## API Endpoints

### GET /api/v1/admin/integrations/{id}/validate/

Valide une intégration et met à jour son statut si nécessaire.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/admin/integrations/5/validate/
```

**Réponse 200 :**
```json
{
  "integration_id": 5,
  "integration_name": "AAP Dev",
  "integration_type": "aap",
  "current_status": "valid",
  "validation_details": {
    "status": "valid",
    "type_exists": true,
    "type_is_active": true,
    "catalogue_version": "1.0",
    "validation_message": "Type 'aap' is active and supported"
  }
}
```

**Réponse 404 :** Intégration non trouvée.

### POST /api/v1/admin/integrations/validate-all/

Valide toutes les intégrations en batch.

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/admin/integrations/validate-all/
```

**Réponse 200 :**
```json
{
  "valid": 12,
  "invalid": 2,
  "deprecated": 3,
  "updated": 5
}
```

## Commande Management

### validate_integrations

Valide toutes les intégrations depuis la ligne de commande.

```bash
# Validation complète (met à jour la DB)
python manage.py validate_integrations

# Mode lecture seule
python manage.py validate_integrations --dry-run
```

**Sortie console :**
```
========================================
Integration Validation Report
========================================
Valid: 12
Invalid: 2
Deprecated: 3
Updated: 5 integrations status changed
========================================
```

**Codes de sortie :**
- `0` : Toutes les intégrations sont valides
- `1` : Au moins une intégration invalide

**Usage cron (quotidien) :**
```bash
0 2 * * * cd /path/to/django_backend && .venv/bin/python manage.py validate_integrations >> /var/log/idp/validate_integrations.log 2>&1
```

## Audit Trail

Chaque changement de statut crée une entrée d'audit :

| Champ | Valeur |
|-------|--------|
| `action_type` | `INTEGRATION_STATUS_UPDATED` |
| `entity_type` | `INTEGRATION` |
| `entity_id` | ID de l'intégration |
| `user_id` | Utilisateur (ou NULL si automatique) |
| `metadata` | `{"previous_status": "valid", "new_status": "deprecated", ...}` |

## Impact sur les Workflows (Story 24.4)

- Les nouveaux workflows ne peuvent référencer que des intégrations `status=valid`
- Intégration `deprecated` dans un workflow existant : warning, exécution autorisée (grace period)
- Intégration `invalid` dans un workflow : exécution bloquée avec erreur explicite

## Voir aussi

- [Catalogue des Types d'Intégration](integration-type-catalogue.md)
