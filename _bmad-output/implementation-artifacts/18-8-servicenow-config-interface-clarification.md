# Story 18.8 : ServiceNow — revue interface et clarification code modèle / template

Status: backlog

## Story

En tant que **DBOPS ou DBA**,
je veux **une interface claire pour configurer le changement ServiceNow par environnement** dans la modification d’action,
afin de **comprendre facilement quels champs renseigner et éviter la confusion entre « code modèle » et « template ID »**.

## Contexte

- La section « Changement ServiceNow par environnement » (Story 2.24, 25.4) dans ActionForm et ActionWizard est peu claire.
- Les champs `change_model_code` et `template_id` semblent redondants pour les utilisateurs ; en pratique, seul `change_model_code` est utilisé côté exécution (`env_config_resolver.py`).
- `change_type` et `template_id` sont stockés mais non consommés par le flux d’exécution actuel.
- Référence : `idp-portal/docs/backend/change-type-config.md`, `ChangeTypeConfig.tsx`.

## Acceptance Criteria

**AC1 : Clarifier la sémantique code modèle vs template ID**
```gherkin
Given l’équipe produit et/ou l’équipe ServiceNow
When on valide l’usage réel des champs côté ServiceNow ITSM
Then on documente la différence (ou l’équivalence) entre change_model_code et template_id
And si redondants → on fusionne en un seul champ côté modèle et UI
And si distincts → on ajoute des tooltips explicites et labels clairs
```

**AC2 : Revoir l’interface ChangeTypeConfig**
```gherkin
Given le composant ChangeTypeConfig (ActionForm / ActionWizard)
When j’accède à la section ServiceNow par environnement
Then les colonnes sont ordonnées par pertinence (Autorisé, Changement requis, Code modèle/Template en premier)
And chaque colonne a un label clair (pas d’abréviation type « Co/de mo/dèl/e »)
And des tooltips expliquent la finalité de chaque champ
And la grille reste responsive (scroll horizontal si nécessaire sur petits écrans)
```

**AC3 : Simplifier les champs selon la décision AC1**
```gherkin
Given la décision AC1 (fusion ou distinction)
When on fusionne change_model_code et template_id
Then un seul champ « Code modèle / template ServiceNow » est affiché
And le backend migre/conserve les données existantes (rétrocompatibilité)
When on conserve les deux champs distincts
Then les labels et tooltips distinguent clairement : modèle de changement vs ID template
```

**AC4 : Nettoyer les champs non utilisés**
```gherkin
Given change_type et template_id sont actuellement stockés mais non utilisés en exécution
When l’équipe valide qu’ils ne sont pas requis pour le flux ServiceNow futur
Then on documente dans change-type-config.md leur statut (réserve future / deprecated)
And on retire ou masque les champs correspondants de l’UI si non utiles
```

**AC5 : Documentation et tests**
```gherkin
Given les changements UI et modèle
When on met à jour la documentation (change-type-config.md)
Then la structure JSON et les champs sont documentés à jour
And des tests (unitaire + intégration) couvrent le nouveau comportement
```

## Fichiers concernés

- `idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx`
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` (section ServiceNow)
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` (étape Impact & Changement)
- `idp-portal/docs/backend/change-type-config.md`
- `idp-portal/django_backend/executions/validators/env_config_resolver.py`
- `idp-portal/django_backend/catalog/validators.py` (validate_change_type_config)

## Références

- Story 2.24 : Changement ServiceNow conditionnel par environnement
- Story 25.4 : Overrides par environnement (change_type_config enrichi)
- Epic 18 : Améliorations UX et corrections issues du feedback utilisateurs
