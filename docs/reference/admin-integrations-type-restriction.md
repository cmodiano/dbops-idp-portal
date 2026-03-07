# Admin Intégrations — Restriction des types via catalogue backend

**Story:** 24.2 — Frontend Admin — Restriction types actions
**Date:** 2026-02-10
**Epic:** 24 — Intégrations Admin alignées sur le backend

## Contexte du changement

### Avant (Story 4.9)
- Le champ **Type** dans le formulaire d'intégration était un `AutoComplete` libre
- Les suggestions étaient hardcodées dans `SUGGESTED_INTEGRATION_TYPES` (aap, servicenow, terraform...)
- Aucune validation que le type existe réellement dans le backend
- Les utilisateurs pouvaient saisir n'importe quelle valeur → erreurs d'exécution silencieuses

### Après (Story 24.2)
- Le champ **Type** est désormais un `Select` alimenté dynamiquement par le catalogue backend
- Les types disponibles proviennent de `GET /api/v1/integrations/types` (Story 24.1)
- Seuls les types **actifs** (`is_active: true`) sont proposés
- Les actions supportées par chaque type sont affichées dans une section dédiée
- Le type est **non modifiable** après la création d'une intégration
- Validation frontend : le type sélectionné doit exister et être actif

## Guide utilisateur DBOPS

### Créer une nouvelle intégration

1. Cliquer sur **"Nouvelle intégration"** dans l'onglet Admin Intégrations
2. **Sélectionner un type** dans la liste déroulante :
   - Les types sont chargés depuis le backend (ex: "Ansible Automation Platform", "ServiceNow ITSM")
   - La recherche est supportée : taper les premières lettres pour filtrer
3. **Consulter les actions disponibles** qui s'affichent sous le type sélectionné :
   - Chaque action montre son code, sa description et le nombre de paramètres requis
   - Cliquer sur le chevron d'expansion pour voir le détail des paramètres (nom, type, description)
4. Remplir les champs restants (Nom, URL, credentials, etc.)
5. Cliquer **"Créer"**

### Modifier une intégration existante

- Le champ Type est **verrouillé** en mode édition (grisé avec message explicatif)
- Les actions disponibles sont affichées en lecture seule pour référence
- Les autres champs (Nom, URL, credentials, auth flow, icône) restent modifiables

### Mode dégradé

Si l'API des types est temporairement indisponible :
- Un **warning jaune** s'affiche en haut du formulaire
- Deux types de secours sont proposés (AAP et ServiceNow) sans actions associées
- La création reste possible mais avec une liste incomplète

## Architecture technique

### Fichiers créés
| Fichier | Rôle |
|---------|------|
| `hooks/useIntegrationTypes.ts` | Hook React pour fetch + cache sessionStorage (TTL 1h) |
| `components/admin/AvailableActionsPanel.tsx` | Composant table actions avec expand paramètres |

### Fichiers modifiés
| Fichier | Modification |
|---------|-------------|
| `types/api/integrations.ts` | Ajout `IntegrationTypeCatalogue`, `IntegrationAction`, `FALLBACK_INTEGRATION_TYPES` ; suppression `SUGGESTED_INTEGRATION_TYPES` |
| `services/integrations_service.ts` | Ajout `getIntegrationTypes()` service |
| `components/admin/IntegrationForm.tsx` | Remplacement `AutoComplete` → `Select`, ajout actions panel, mode édition disabled, validation type actif |

### API backend
- **Endpoint :** `GET /api/v1/integrations/types`
- **Réponse :** `{ data: IntegrationTypeCatalogue[] }`
- **Documenté dans :** Story 24.1

### Cache sessionStorage
- **Clé :** `integration_types_cache`
- **Format :** `{ data: IntegrationTypeCatalogue[], timestamp: number }`
- **TTL :** 1 heure (3 600 000 ms)
- **Invalidation automatique** à l'expiration du TTL

## Notes de migration (référence Story 24.4)

Les intégrations existantes créées avec des types libres (ex: "terraform", "custom-platform") **ne sont pas impactées** par ce changement frontend :
- Les intégrations existantes conservent leur type tel quel
- En mode édition, le type s'affiche mais ne peut pas être modifié
- La migration complète des types existants est planifiée dans la Story 24.4

**Important :** Les nouveaux types d'intégration doivent être créés dans le catalogue backend (Story 24.1) **avant** de pouvoir être utilisés dans le formulaire frontend.
