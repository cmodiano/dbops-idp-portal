---
short: "Choisissez l'intégration d'exécution pour cette action. Seules les intégrations configurées dans Admin > Intégrations sont proposées."
---
# Intégration d'exécution

L'**intégration** correspond à l'instance de plateforme (ex. AAP Production, ServiceNow Prod) qui sera appelée lors de l'exécution de cette action.

## Pourquoi ce champ est important

- Seules les intégrations **configurées et actives** sont proposées.
- Si aucune intégration n'est disponible, créez-en une dans **Admin > Intégrations**.
- La valeur envoyée au backend est l'`integration_id` ; la plateforme est déduite du type de l'intégration.

## Cas particuliers

- **Workflows** : chaque étape du workflow peut utiliser une intégration différente.
- **Actions désactivées** : si l'intégration associée est supprimée, l'action est automatiquement désactivée (Story 31.2).
