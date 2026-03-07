---
short: "Les gates sont des conditions préalables à l'exécution d'une action (fenêtre de maintenance, approbation, etc.)."
---
# Gates — Conditions préalables à l'exécution

Les **gates** sont des vérifications automatiques effectuées avant le lancement d'une action. Elles permettent de s'assurer que les conditions opérationnelles sont réunies.

## Types de gates disponibles

| Gate | Description |
|------|-------------|
| **Fenêtre de maintenance** | L'exécution ne démarre que pendant une plage horaire définie |
| **Approbation** | Un approbateur doit valider avant l'exécution |
| **Changement ServiceNow** | Un changement ServiceNow doit être créé et approuvé |

## Configuration par environnement

Chaque gate peut être activée ou désactivée indépendamment par environnement. Par exemple :
- **Production** : toutes les gates activées (maintenance + approbation + ServiceNow)
- **Staging** : uniquement la fenêtre de maintenance
- **Développement** : aucune gate

## Comportement à l'exécution

Lorsqu'une gate est activée, l'exécution passe en statut **En attente** jusqu'à ce que la condition soit remplie. Le système évalue périodiquement les conditions et lance l'exécution dès que toutes les gates sont satisfaites.
