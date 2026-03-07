---
short: "Configurez la création automatique d'un changement ServiceNow avant l'exécution, par environnement."
---
# Changement ServiceNow par environnement

Cette section permet de configurer la **création automatique d'un changement ServiceNow** avant l'exécution d'une action sur un environnement donné.

## Fonctionnement

1. Activez le changement ServiceNow pour les environnements souhaités.
2. Sélectionnez l'intégration ServiceNow à utiliser (configurée dans Admin > Intégrations).
3. Choisissez le type de changement : **Normal** ou **Standard (pré-approuvé)**.
4. Pour les changements standard, spécifiez le **code modèle** ServiceNow.

## Types de changement

| Type | Description |
|------|-------------|
| **Normal** | Requiert une approbation dans ServiceNow avant exécution |
| **Standard** | Pré-approuvé, l'exécution peut démarrer immédiatement |

## Bonnes pratiques

- Utilisez un changement **standard** pour les actions à faible risque (ex. consultation, redémarrage service non-prod).
- Utilisez un changement **normal** pour les actions impactant la production.
- Le code modèle doit correspondre à un template existant dans votre instance ServiceNow.
