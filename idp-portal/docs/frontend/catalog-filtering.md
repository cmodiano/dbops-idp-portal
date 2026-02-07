# Filtrage du Catalogue — Décisions Techniques

## Historique

- **Story 8.7:** Ajout du filtre Environnement dans HorizontalFilters (layout 3 colonnes sm=8)
- **Stories 13.1-13.4:** Implémentation du modèle target-first (environnement = propriété du target)
- **Story 18.4:** Suppression du filtre Environnement obsolète (layout 2 colonnes sm=12)

## Modèle Target-First (Stories 13.1–13.4)

L'environnement est une propriété du **target**, pas de l'action :

```
Action (catalogue)
  ↓
Execution (sélection targets)
  ↓
Target (inventaire)
  └─ environment: 'dev' | 'staging' | 'prod'
```

Une action est générique. C'est le **target sélectionné** qui définit l'environnement d'exécution.

Exemple : « Apply Oracle Patch » peut s'exécuter sur dev, staging ou prod selon le target choisi.

**Diagramme visuel :** Voir [catalog-filtering-diagram.excalidraw.json](./catalog-filtering-diagram.excalidraw.json) pour une visualisation du modèle target-first.

## Suppression du filtre Environnement (Story 18.4)

**Problème :** Le filtre Environnement dans le catalogue suggérait que l'action possède un environnement, ce qui est faux depuis les stories 13.x.

**Décision :** Retirer complètement le filtre Environnement du catalogue (`HorizontalFilters`, `ActiveFiltersChips`, `CatalogPage`).

**Filtres restants :** Moteur et Impact (layout 2 colonnes `sm=12`).

## Alternatives pour filtrer par environnement

Le filtrage par environnement reste disponible dans d'autres contextes :

| Composant | Page | Hook | Usage |
|---|---|---|---|
| `TargetSelector` | ExecutionWizard | `useEnvironments` | Filtre targets par environnement lors de l'exécution |
| `AdvancedFiltersPanel` | ExecutionsPage | `useEnvironments` | Filtre exécutions passées par environnement du target |
| `CalendarFiltersPanel` | CalendarPage | `useEnvironments` | Filtre exécutions planifiées par environnement |

Le hook `useEnvironments` est conservé pour ces composants.

## Paramètre API backend

Le paramètre `?environment=` reste supporté côté backend (`GET /api/v1/catalog/actions`). Le frontend catalogue ne l'envoie plus, mais les pages Exécutions et Calendrier continuent de l'utiliser.
