# Epic 83: Extensibilité state-of-the-art — achèvement architecture data-driven

**Réf principale :** [docs/reference/extensibility-remaining-work-state-of-the-art.md](../reference/extensibility-remaining-work-state-of-the-art.md)

**Réf complémentaire :** [docs/reference/extensibility-plan-gates-services-platforms.md](../reference/extensibility-plan-gates-services-platforms.md)

---

## Objectif

Atteindre une architecture moderne, simple et durable autour des **plateformes**, **services** et **gates** :

- **aucune logique métier hard-codée dans le frontend**
- **le backend est la source de vérité unique**
- **le frontend consomme des APIs de capacités et de schémas**
- **le code reste lisible et auto-explicatif**
- **l'extensibilité ne repose pas sur des branches spéciales dispersées**

---

## Vision cible

Chaîne de flux simple à suivre :

```
definition → capability API → UI renderer → payload → runtime strategy
```

Si cette chaîne est simple, le système sera : extensible, lisible, stable, beaucoup moins fragile.

---

## Principes de design non négociables

1. **Backend source de vérité** : code canonique, display name, aliases, role, operations, schemas, hints UI, contraintes, etc.
2. **Frontend thin client** : charger capacités, rendre selects/forms/labels, afficher erreurs, poster payloads.
3. **Schémas avant branches spéciales** : nouveau type = schema + définition, pas nouvelle branche codée en dur.
4. **Canonical codes only** : un type a un code canonique, des aliases uniquement côté backend.
5. **Code auto-explicatif** : dataclasses simples, noms explicites, peu d'indirections.

---

## Stories (détail)

### Phase 1 — Finir la source de vérité backend

| Story | Description | Fichiers |
|-------|-------------|----------|
| 83-1 | Supprimer `IntegrationType.choices` comme verrou métier. Remplacer par validation dérivée du catalogue actif ou registre/capability backend. | `integrations/serializers.py` |
| 83-2 | GateEvaluator : déplacer la logique d'évaluation dans les définitions/stratégies de gate. Faire du GateEvaluator un simple orchestrateur. | `executions/gate_evaluator.py` |
| 83-3 | Introduire `WorkflowStepDefinition`. Centraliser les step definitions. Supprimer `_STEP_TYPES_STATIC` dans capabilities. | `capabilities/views.py` |
| 83-4 | Enrichir `PlatformDefinition`, `ServiceDefinition`, `GateDefinition` (schemas, runtime_config, action_config, etc.). | `platforms/definitions.py`, `services/definitions.py`, `gates/` |
| 83-6 | Faire dériver les capabilities depuis les définitions uniquement. Toute nouvelle capacité visible dans l'API sans mapping supplémentaire. | `capabilities/` |

### Phase 2 — Exposer des schémas complets

| Story | Description | Fichiers |
|-------|-------------|----------|
| 83-5 | Exposer input_schema, output_schema, ui_hints, contraintes, defaults par opération/service/gate. Le frontend peut générer un formulaire sans liste locale. | `capabilities/views.py` |

### Phase 3 — Rendre le frontend déclaratif

| Story | Description | Fichiers |
|-------|-------------|----------|
| 83-7 | Créer `SchemaFormRenderer` pour string, number, boolean, enum, array, object, mapping key/value. Couvrir 80% des besoins. | `frontend/src/` |
| 83-8 | ActionWizard : remplacer blocs plateforme-spécifiques (AAP) par rendu de `action_config_schema`. | `ActionWizard.tsx` |
| 83-9 | GateStepConfig : construire formulaire à partir de `config_schema`. Supprimer dépendance à `approval` etc. | `GateStepConfig.tsx` |
| 83-10 | ServiceCallStepConfig : complètement schema-driven. Supprimer logique locale labels/operations. | `ServiceCallStepConfig.tsx` |
| 83-11 | WorkflowStepNode : labels/variants dérivés du backend. Titre et badge dépendants de metadata. | `WorkflowStepNode.tsx` |

### Phase 4 — Simplifier et supprimer le legacy

| Story | Description | Fichiers |
|-------|-------------|----------|
| 83-12 | Supprimer fallbacks métier frontend. Limiter aux fallbacks de résilience technique. | `useWorkflowStepCapabilities.ts` |
| 83-13 | Clarifier/supprimer `ActionPlatform`. Supprimer ou dériver automatiquement. | Backend |
| 83-14 | Supprimer helpers de mapping devenus inutiles. Réduire aliases résiduels. | Divers |

---

## Definition of done (succès final)

On pourra considérer l'architecture comme proche de la cible "state of the art" quand :

- le frontend ne porte plus de logique métier sur les types supportés
- le backend expose toutes les capacités nécessaires via API
- une nouvelle opération déclarative n'exige pas de modification frontend
- une nouvelle plateforme/service exécutable n'exige du code que dans sa logique runtime et sa définition
- le code se lit naturellement en suivant : `definition → capability API → UI renderer → payload → runtime strategy`

---

## Règles de revue de code futures

Une PR future doit être **refusée** si elle ajoute :

- une nouvelle constante frontend de type métier déjà disponible via API
- un nouveau mapping plateforme/service/gate hors des définitions backend
- une nouvelle allowlist locale dupliquée
- un nouveau `if/elif/switch` central pour un type qui devrait être déclaratif

Une PR future est dans la **bonne direction** si elle :

- supprime un mapping
- remplace une branche par un schema
- centralise une définition
- rend le frontend plus passif

---

## Références

- [extensibility-remaining-work-state-of-the-art.md](../reference/extensibility-remaining-work-state-of-the-art.md) — document source
- [extensibility-plan-gates-services-platforms.md](../reference/extensibility-plan-gates-services-platforms.md) — plan général
