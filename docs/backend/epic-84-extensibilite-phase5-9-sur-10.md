# Epic 84: Extensibilité phase 5 — atteindre 9/10 par composant

**Réf principale :** [docs/reference/extensibility-remaining-work-state-of-the-art.md](../reference/extensibility-remaining-work-state-of-the-art.md) — section « Roadmap cible - atteindre 9/10 par composant »

**Contexte :** Epic 83 a livré les Phases 1 à 4. Ce document couvre le **travail restant** pour atteindre la note **9/10** sur chaque composant (plateformes, services, gates, workflow UI, runtime).

---

## Objectif

Atteindre **9/10** sur l'ensemble des composants d'extensibilité :

- **9/10** = ajout localisé, compréhensible, peu de couplage, faible risque de dérive
- Architecture simple, lisible, robuste, exploitable au quotidien

---

## Mapping 9/10 → Stories

Chaque story ci-dessous est explicitement liée aux critères « ce qui manque pour 9/10 » du document de référence.

| Composant | État actuel | Critères 9/10 manquants | Stories Epic 84 |
|-----------|-------------|-------------------------|-----------------|
| **Plateformes** | 8/10 | P1–P4 | 84-6, 84-7, 84-8 |
| **Services** | 8/10 | S1–S4 | 84-4 |
| **Gates** | 6.5/10 | G1–G4 | 84-2, 84-5 |
| **Workflow UI** | 6.5/10 | W1–W5 | 84-3 |
| **Runtime backend** | 7/10 | R1–R3 | 84-1, 84-2 |
| **SchemaFormRenderer** | — | B.5 | 84-9 |

---

## Stories (détail)

### Phase 1 — Runtime et orchestration (priorité maximale)

| Story | Critères 9/10 | Description | Fichiers |
|-------|---------------|-------------|----------|
| **84-1** | R1, R2, W5 | **Registre de handlers runtime pour step types.** Remplacer le `match step_type` central dans `container_workflow_runtime.py` par un registre de handlers. Aligner definitions et execution : ce qui est déclarable dans capabilities doit correspondre à un chemin runtime clair. Un step type exposé au frontend = handler runtime connu. | `container_workflow_runtime.py`, nouveau module `executions/step_handlers/` ou équivalent |
| **84-2** | G1, G3, G4, R3 | **Résolution manuelle générique pour gates.** Supprimer le couplage dur à `approval_granted`. Permettre à un gate manuel de déclarer sa `resolution_strategy` ou son mode de résolution. Réduire les références legacy dans approval_views, outbox, events, runtime. Un nouveau gate manuel = definition + mécanisme de résolution dédié, pas de chasse au trésor dans views/services/tasks. | `approval_views.py`, `gates/definitions.py`, outbox, services, runtime |

### Phase 2 — Workflow UI dérivé des capabilities

| Story | Critères 9/10 | Description | Fichiers |
|-------|---------------|-------------|----------|
| **84-3** | W1, W2, W3, W4 | **Workflow UI backend-driven.** (1) Palette : `ActionPalette` dérivée de `workflow_step_registry`, plus de liste locale des special steps. (2) Titres/labels unifiés : `StepConfigPanel`, `workflowStepLabels`, `WorkflowStepNode` consomment le même vocabulaire backend. (3) Validation : `workflowValidation.ts` lit les contraintes depuis capabilities, plus de `switch(stepType)` métier. (4) Typing frontend plus souple : éviter qu'un nouveau step type exige une cascade de modifications TypeScript purement descriptives. | `ActionPalette.tsx`, `StepConfigPanel.tsx`, `workflowStepLabels.ts`, `WorkflowStepNode.tsx`, `workflowValidation.ts`, `types/api/catalog.ts` |

### Phase 3 — Services et formulaires schema-driven

| Story | Critères 9/10 | Description | Fichiers |
|-------|---------------|-------------|----------|
| **84-4** | S1, S2, S3, S4 | **Formulaires service schema-driven complets.** (1) Rendre les champs depuis `input_schema` quand le schema le permet, au-delà du key/value editor. (2) Validation frontend/backend convergée : erreurs de saisie visibles avant submit. (3) Normaliser et mieux utiliser `ui_hints`. (4) Clarifier les services non opérationnels (health check, consommation interne sans service_call) : rôle explicite dans capabilities. | `ServiceCallStepConfig.tsx`, `capabilities/views.py`, `services/definitions.py` |

### Phase 4 — Gates et plateformes (nettoyage cible)

| Story | Critères 9/10 | Description | Fichiers |
|-------|---------------|-------------|----------|
| **84-5** | G2 | **GateStepConfig renderer générique.** Brancher davantage `GateStepConfig` sur un renderer de schema. Ne garder du code conditionnel que si la valeur UX est évidente. | `GateStepConfig.tsx` |
| **84-6** | P1 | **Réduire l'exception AAP au strict minimum.** Conserver uniquement le renderer spécialisé si la recherche de templates AAP reste un besoin UX unique. Sinon aligner AAP sur le même chemin déclaratif que les autres plateformes. | `ActionWizard.tsx`, `WizardStep2Automatisme.tsx` |
| **84-7** | P2, P3 | **Simplifier ActionPlatform et conversions legacy.** Réduire les conversions entre code integration, `connector_type`, code action. Utiliser davantage `PlatformDefinition` pour éviter tout mapping ou règle résiduelle hors definition. Un seul code métier, dériver le reste au plus près de la persistence/runtime. | Backend : `ActionPlatform`, mappings, `integrations/`, `actions/` |
| **84-8** | P4 | **Compléter l'usage des schemas plateformes.** Exploiter davantage `runtime_config_schema` et `health_check_policy`. Clarifier ce qui est purement descriptif vs effectivement appliqué. | `platforms/definitions.py`, `capabilities/`, runtime config |

### Phase 5 — SchemaFormRenderer usage partout

| Story | Critères 9/10 | Description | Fichiers |
|-------|---------------|-------------|----------|
| **84-9** | B.5 | **SchemaFormRenderer utilisé partout où les schemas le permettent.** Réutiliser le renderer générique dans `WizardStep2Automatisme`, et tout flux restant. Réserver les renderers spécifiques aux cas UX justifiés. | `SchemaFormRenderer.tsx`, `WizardStep2Automatisme.tsx`, autres composants config |

---

## Ordre d'exécution recommandé

Conformément au document de référence (§ 6. Objectif global) :

1. **84-1** — Runtime workflow handler registry
2. **84-2** — Manual gate resolution generic path
3. **84-3** — Workflow UI dérivé des capabilities
4. **84-4** — Service forms plus schema-driven
5. **84-5** à **84-9** — Réduction finale (gates, plateformes, SchemaFormRenderer)

---

## Definition of done par composant (9/10 atteint)

### Plateformes
- Ajouter une nouvelle plateforme = écrire l'adapter + déclarer la definition
- Pas de nouvelle constante frontend, pas de nouveau helper de mapping
- Pas de nouveau branchement hors exception runtime réellement justifiée

### Services
- Ajouter un nouveau service = écrire le client + déclarer les operations
- Si les operations ont un schema standard, aucune modification frontend supplémentaire
- Labels, champs et validations viennent de l'API backend

### Gates
- Ajouter un nouveau gate auto-évalué = definition + stratégie
- Ajouter un nouveau gate manuel = definition + mécanisme de résolution dédié
- Pas de nouveau `if gate_type == ...` dispersé dans plusieurs couches

### Workflow UI
- Ajouter un nouveau step type standard = déclaration backend + handler runtime + eventuel schema
- Palette, panneau, labels et validation frontend s'adaptent sans duplication locale majeure

### Runtime
- definition → validation → execution suit la même structure mentale
- On peut suivre un step type sans changer de paradigme entre capabilities et runtime

---

## Références

- [extensibility-remaining-work-state-of-the-art.md](../reference/extensibility-remaining-work-state-of-the-art.md) — document source, sections « Roadmap cible - atteindre 9/10 » et « État actuel - ce qu'il reste à enlever »
- [epic-83-extensibilite-state-of-the-art.md](epic-83-extensibilite-state-of-the-art.md) — Epic précédent (Phases 1–4)
