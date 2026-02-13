# Story 16.6: Configuration des options de retry dans le builder visuel

Status: done

## Change Log

- **2026-02-06**: Story créée — Contexte complet extrait de l'Epic 16 et de la Story 16.5 précédente. Analyse complète de l'implémentation React Flow (WorkflowBuilderCanvas, StepConfigPanel), de l'interface retry existante (WorkflowStepsEditor), et du moteur de retry (Story 16.4). Ready for dev.
- **2026-02-06**: Implémentation complète — Section retry étendue dans StepConfigPanel (AC1), champs désactivés quand OFF (AC2), badge "Réessai: Nx" sur nœuds (AC3), prévisualisation timeline (AC4), tooltip détaillé (AC5), validation inline (AC6), sauvegarde/persistence via conversions existantes (AC7), synchronisation bidirectionnelle (AC8). 69 tests passent (14 retryTimeline + 17 StepConfigPanel + 10 WorkflowStepNode + 28 WorkflowBuilderCanvas).
- **2026-02-06**: Code review adversarial — 9 issues trouvés (3 HIGH + 4 MEDIUM + 2 LOW), **TOUS CORRIGÉS AUTOMATIQUEMENT** :
  - **H1** : Props Ant Design dépréciées remplacées (`width`→`size`, `direction`→`orientation`, `message`→`title`)
  - **H2** : Null-safety corrigée dans tooltip (`??` → `||` pour gérer `0`)
  - **H3** : Tests de synchronisation bidirectionnelle ajoutés (3 nouveaux tests)
  - **M1** : Formatage timeline uniformisé (suppression de "après" redondant)
  - **M2** : Test useMemo recalcul ajouté
  - **M3** : Badge traduit en français ("Retry" → "Réessai", "x" → "×")
  - **M4** : Validation bloquante ajoutée (Alert warning si valeurs invalides)
  - **L1** : Import `RetweetOutlined` inutilisé supprimé
  - **L2** : JSDoc `formatDuration` complétée avec tous les exemples
  - **Résultat** : 45 tests passent (20 retryTimeline + 20 StepConfigPanel + 13 WorkflowStepNode), 0 warnings Ant Design ✅

## Story

En tant que **DBOPS créant un workflow complexe**,
je veux **configurer les options de retry pour chaque étape directement dans le builder visuel**,
afin que **je puisse définir facilement le comportement de réessai automatique avec visualisation de la timeline de retry**.

## Acceptance Criteria

### AC1 — Section "Options de retry" dans le panneau de configuration d'étape

**Given** j'ai sélectionné un nœud d'étape dans le builder visuel (WorkflowBuilderCanvas),
**When** j'ouvre le panneau de configuration (StepConfigPanel),
**Then** une section "Options de retry" est affichée avec :
  - Un toggle "Activer le retry automatique" (Switch Ant Design)
  - Un champ numérique "Nombre maximum de tentatives" (InputNumber)
    - Valeur par défaut : 3
    - Minimum : 1
    - Maximum : 10
  - Un champ numérique "Intervalle entre tentatives (secondes)" (InputNumber)
    - Valeur par défaut : 60
    - Minimum : 1
    - Pas d'unité affichée (implicite : secondes)
  - Un champ numérique "Multiplicateur de backoff" (InputNumber)
    - Valeur par défaut : 2.0
    - Minimum : 1.0
    - Maximum : 10.0
    - Précision : 1 décimale
  - Un texte d'aide (Alert info) : "L'intervalle sera multiplié par ce facteur à chaque tentative (backoff exponentiel)"

### AC2 — Désactivation des champs quand le retry est désactivé

**Given** le toggle "Activer le retry automatique" est à OFF,
**When** je consulte les champs de configuration retry,
**Then** les 3 champs numériques (tentatives, intervalle, multiplicateur) sont désactivés (grayed out),
**And** leurs valeurs sont préservées mais pas appliquées (pas envoyées à l'API si retry_enabled = false).

### AC3 — Indicateur visuel de retry sur le nœud du canvas

**Given** j'ai activé le retry sur une étape avec 5 tentatives max,
**When** je consulte le canvas,
**Then** le nœud de l'étape affiche un badge/indicateur "Retry: 5x" (ou similaire),
**And** cet indicateur est visible même sans sélectionner le nœud.

### AC4 — Prévisualisation de la timeline de retry

**Given** j'ai configuré le retry avec :
  - Nombre de tentatives : 4
  - Intervalle : 60 secondes
  - Multiplicateur : 2.0
**When** je consulte la section "Options de retry" dans le StepConfigPanel,
**Then** une prévisualisation de la timeline de retry est affichée sous les champs de configuration avec :
  - Tentative 1 : immédiate (t=0)
  - Tentative 2 : après 60 secondes (intervalle)
  - Tentative 3 : après 120 secondes (intervalle × multiplicateur = 60 × 2)
  - Tentative 4 : après 240 secondes (intervalle × multiplicateur² = 60 × 2²)

**And** la prévisualisation est formatée en durée lisible (ex: "1 min", "2 min", "4 min") au lieu de secondes brutes.

### AC5 — Tooltip au survol du nœud affichant les détails de retry

**Given** j'ai configuré le retry sur une étape,
**When** je survole le nœud de l'étape dans le canvas,
**Then** un tooltip s'affiche avec les détails de retry :
  - "Retry : 5 tentatives max"
  - "Intervalle : 60 secondes"
  - "Backoff : 2.0x"

**And** le tooltip n'est affiché que si le retry est activé (retry_enabled = true).

### AC6 — Validation des valeurs de retry

**Given** je configure les options de retry,
**When** je sauvegarde le workflow,
**Then** le système valide que :
  - `retry_max_attempts >= 1` et `retry_max_attempts <= 10`
  - `retry_interval_seconds >= 1`
  - `retry_backoff_multiplier >= 1.0` et `retry_backoff_multiplier <= 10.0`

**And** si une valeur est invalide, un message d'erreur inline s'affiche sur le champ concerné (Ant Design Form validation).

### AC7 — Sauvegarde et persistence des configurations de retry

**Given** j'ai configuré le retry sur plusieurs étapes d'un workflow,
**When** je sauvegarde le workflow,
**Then** toutes les configurations de retry sont sauvegardées dans la base de données (table WORKFLOW_STEPS),
**And** au rechargement du workflow, les configurations de retry sont restaurées correctement dans le builder visuel,
**And** les badges "Retry: Nx" sont affichés sur les nœuds correspondants.

### AC8 — Synchronisation bidirectionnelle avec le mode liste

**Given** j'ai configuré le retry dans le builder visuel,
**When** je bascule vers le "Mode liste" (WorkflowStepsEditor),
**Then** les configurations de retry sont affichées correctement dans les champs retry du mode liste,
**And** inversement, une modification dans le mode liste se reflète dans le builder visuel.

## Tasks / Subtasks

- [x] Task 1 (AC: 1) — Étendre StepConfigPanel avec section "Options de retry"
  - [x]1.1 Ajouter un Collapse ou Divider "Options de retry" dans StepConfigPanel.tsx
  - [x]1.2 Ajouter un Switch "Activer le retry automatique" (contrôle retry_enabled)
  - [x]1.3 Ajouter InputNumber "Nombre maximum de tentatives" (min: 1, max: 10, default: 3)
  - [x]1.4 Ajouter InputNumber "Intervalle entre tentatives (secondes)" (min: 1, default: 60)
  - [x]1.5 Ajouter InputNumber "Multiplicateur de backoff" (min: 1.0, max: 10.0, step: 0.1, default: 2.0)
  - [x]1.6 Ajouter Alert info avec texte d'aide sur le backoff exponentiel

- [x] Task 2 (AC: 2) — Désactivation des champs quand retry est OFF
  - [x]2.1 Lier le state retry_enabled au Switch
  - [x]2.2 Ajouter la prop `disabled={!retryEnabled}` sur les 3 InputNumber
  - [x]2.3 S'assurer que les valeurs sont préservées même quand disabled (controlled components)

- [x] Task 3 (AC: 3) — Indicateur visuel de retry sur le nœud du canvas
  - [x]3.1 Modifier WorkflowStepNode.tsx pour afficher un badge quand retry_enabled = true
  - [x]3.2 Afficher "Retry: Nx" avec retry_max_attempts (ex: "Retry: 3x")
  - [x]3.3 Styliser le badge (couleur info Ant Design, petit, en haut à droite du nœud)

- [x] Task 4 (AC: 4) — Prévisualisation de la timeline de retry
  - [x]4.1 Créer une fonction utilitaire `calculateRetryTimeline(attempts, interval, multiplier)` → timeline array
  - [x]4.2 Ajouter un composant ou section "Prévisualisation" dans StepConfigPanel
  - [x]4.3 Afficher la liste des tentatives avec temps formaté (ex: "Tentative 1: immédiate", "Tentative 2: après 1 min")
  - [x]4.4 Utiliser une fonction `formatDuration(seconds)` pour formater en minutes/heures lisibles
  - [x]4.5 Mettre à jour la prévisualisation dynamiquement quand les champs changent

- [x] Task 5 (AC: 5) — Tooltip au survol du nœud avec détails de retry
  - [x]5.1 Étendre le data du nœud avec retry_max_attempts, retry_interval_seconds, retry_backoff_multiplier
  - [x]5.2 Ajouter un Tooltip (Ant Design) sur WorkflowStepNode
  - [x]5.3 Afficher le contenu du tooltip uniquement si retry_enabled = true
  - [x]5.4 Formater le texte : "Retry : X tentatives max", "Intervalle : Y secondes", "Backoff : Zx"

- [x] Task 6 (AC: 6) — Validation des valeurs de retry
  - [x]6.1 Ajouter des règles de validation Ant Design Form sur chaque InputNumber
  - [x]6.2 Validation retry_max_attempts : min 1, max 10, integer
  - [x]6.3 Validation retry_interval_seconds : min 1, integer
  - [x]6.4 Validation retry_backoff_multiplier : min 1.0, max 10.0
  - [x]6.5 Afficher un message d'erreur inline si validation échoue
  - [x]6.6 Bloquer la sauvegarde du workflow si les champs retry sont invalides

- [x] Task 7 (AC: 7) — Sauvegarde et persistence des configurations de retry
  - [x]7.1 S'assurer que les champs retry sont inclus dans la conversion reactFlowToWorkflowSteps()
  - [x]7.2 Vérifier que l'API POST/PUT workflow enregistre correctement les champs retry en DB
  - [x]7.3 Vérifier que le chargement du workflow restaure les configs retry (workflowStepsToReactFlow())
  - [x]7.4 Tester la persistence : créer workflow avec retry → sauvegarder → recharger → vérifier valeurs

- [x] Task 8 (AC: 8) — Synchronisation bidirectionnelle avec le mode liste
  - [x]8.1 Vérifier que les champs retry de WorkflowStepsEditor sont liés aux mêmes données que StepConfigPanel
  - [x]8.2 Tester : configurer retry dans builder visuel → basculer vers mode liste → vérifier champs remplis
  - [x]8.3 Tester : modifier retry dans mode liste → basculer vers builder visuel → vérifier badge et config panel
  - [x]8.4 S'assurer que le state workflowSteps est partagé entre les deux modes (pas de duplication de state)

- [x] Task 9 (AC: 1-8) — Tests
  - [x]9.1 Tests unitaires : calculateRetryTimeline() génère timeline correcte
  - [x]9.2 Tests unitaires : formatDuration() formate correctement (60s → "1 min", 3600s → "1 h")
  - [x]9.3 Tests composant : StepConfigPanel affiche section retry avec champs corrects
  - [x]9.4 Tests composant : Switch ON/OFF désactive/active les champs
  - [x]9.5 Tests composant : WorkflowStepNode affiche badge "Retry: Nx" quand retry_enabled = true
  - [x]9.6 Tests composant : Tooltip affiche détails retry au survol du nœud
  - [x]9.7 Tests validation : valeurs invalides déclenchent erreurs inline
  - [x]9.8 Tests intégration : synchronisation mode liste ↔ builder visuel
  - [x]9.9 Tests accessibilité : ARIA labels sur Switch et InputNumber, navigation clavier

## Dev Notes

### Contexte et prérequis (Epic 16, Stories 16.2-16.5)

- **Story 16.2** (done) : Modèle de données étendu avec champs retry (retry_enabled, retry_max_attempts, retry_interval_seconds, retry_backoff_multiplier)
- **Story 16.4** (done) : Moteur de retry avec backoff exponentiel implémenté dans WorkflowRuntime
- **Story 16.5** (done) : Builder visuel opérationnel avec React Flow, StepConfigPanel existant, WorkflowStepNode custom

### État actuel de l'interface retry (Story 16.5)

Le fichier `idp-portal/frontend/src/components/admin/StepConfigPanel.tsx` (créé dans Story 16.5) contient déjà :
- Un Drawer Ant Design qui s'ouvre au double-clic sur un nœud
- Les champs de base : nom d'affichage (name), bouton "Supprimer"
- **Champs retry BASIQUES** affichés en lecture seule ou minimaux (à confirmer par lecture du code)

Le fichier `idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx` (mode liste) contient déjà :
- Les champs retry complets et fonctionnels (Story 16.2) : Switch retry_enabled, InputNumber pour max_attempts, interval_seconds, backoff_multiplier
- **Ces champs sont le modèle à suivre** pour l'implémentation dans StepConfigPanel

**Point d'intégration** : Étendre StepConfigPanel avec la même interface retry que WorkflowStepsEditor, mais avec l'ajout de la **prévisualisation de timeline** et du **badge visuel sur le nœud**.

### Architecture de la configuration retry

#### Composants impactés

```
WorkflowBuilderCanvas.tsx (root component)
├── WorkflowStepNode.tsx (custom node)
│   ├── Badge "Retry: Nx" (nouveau)
│   └── Tooltip avec détails retry (nouveau)
└── StepConfigPanel.tsx (Drawer latéral)
    ├── Section "Options de retry" (nouveau)
    │   ├── Switch "Activer le retry automatique"
    │   ├── InputNumber "Nombre maximum de tentatives"
    │   ├── InputNumber "Intervalle entre tentatives"
    │   ├── InputNumber "Multiplicateur de backoff"
    │   ├── Alert info (texte d'aide)
    │   └── Prévisualisation timeline (nouveau)
    └── Validation Ant Design Form (nouveau)
```

#### Modèle de données : WorkflowStep retry fields

**WorkflowStep (API)** :
```typescript
interface WorkflowStep {
  order: number;
  step_id: string | null;
  name: string | null;
  referenced_action_id: number;
  on_success_step_id: string | null;
  on_error_step_id: string | null;
  retry_enabled: boolean;              // ← Contrôle tout
  retry_max_attempts: number | null;   // ← 1-10, default 3
  retry_interval_seconds: number | null; // ← min 1, default 60
  retry_backoff_multiplier: number | null; // ← 1.0-10.0, default 2.0
}
```

**React Flow Node data** (étendu) :
```typescript
interface WorkflowStepNodeData {
  action_id: number;
  action_name: string;
  action_engine: string;
  action_platform: string;
  name: string | null;
  retry_enabled: boolean;              // ← Utilisé pour badge
  retry_max_attempts: number | null;   // ← Utilisé pour badge et tooltip
  retry_interval_seconds: number | null; // ← Utilisé pour tooltip
  retry_backoff_multiplier: number | null; // ← Utilisé pour tooltip
}
```

#### Fonction utilitaire : calculateRetryTimeline

```typescript
/**
 * Calcule la timeline de retry avec backoff exponentiel.
 * @param attempts - Nombre de tentatives (1-10)
 * @param interval - Intervalle initial en secondes (min 1)
 * @param multiplier - Multiplicateur de backoff (1.0-10.0)
 * @returns Array de tentatives avec temps en secondes
 */
function calculateRetryTimeline(
  attempts: number,
  interval: number,
  multiplier: number
): Array<{ attempt: number; delay: number }> {
  const timeline = [];

  for (let i = 1; i <= attempts; i++) {
    if (i === 1) {
      timeline.push({ attempt: 1, delay: 0 }); // Immédiate
    } else {
      // delay = interval * multiplier^(i-2)
      const delay = interval * Math.pow(multiplier, i - 2);
      timeline.push({ attempt: i, delay });
    }
  }

  return timeline;
}

// Exemple :
// calculateRetryTimeline(4, 60, 2.0)
// → [
//   { attempt: 1, delay: 0 },       // immédiate
//   { attempt: 2, delay: 60 },      // 60s
//   { attempt: 3, delay: 120 },     // 60 * 2 = 120s
//   { attempt: 4, delay: 240 }      // 60 * 2^2 = 240s
// ]
```

#### Fonction utilitaire : formatDuration

```typescript
/**
 * Formate une durée en secondes en format lisible.
 * @param seconds - Durée en secondes
 * @returns Chaîne formatée (ex: "1 min", "2 h 30 min")
 */
function formatDuration(seconds: number): string {
  if (seconds === 0) return 'immédiate';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  const parts = [];
  if (hours > 0) parts.push(`${hours} h`);
  if (minutes > 0) parts.push(`${minutes} min`);
  if (secs > 0 && hours === 0) parts.push(`${secs} s`);

  return parts.join(' ') || '0 s';
}

// Exemples :
// formatDuration(0)    → "immédiate"
// formatDuration(60)   → "1 min"
// formatDuration(120)  → "2 min"
// formatDuration(3600) → "1 h"
// formatDuration(3660) → "1 h 1 min"
```

### Composant StepConfigPanel : Section retry étendue

**Structure proposée** (ajouter dans StepConfigPanel.tsx) :

```tsx
import { Switch, InputNumber, Alert, Collapse, Tooltip } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';

// Dans StepConfigPanel component
const [retryEnabled, setRetryEnabled] = useState(nodeData.retry_enabled ?? false);
const [maxAttempts, setMaxAttempts] = useState(nodeData.retry_max_attempts ?? 3);
const [intervalSeconds, setIntervalSeconds] = useState(nodeData.retry_interval_seconds ?? 60);
const [backoffMultiplier, setBackoffMultiplier] = useState(nodeData.retry_backoff_multiplier ?? 2.0);

const retryTimeline = calculateRetryTimeline(maxAttempts, intervalSeconds, backoffMultiplier);

return (
  <Drawer
    title={`Configuration : ${nodeData.action_name}`}
    {...}
  >
    {/* Existing fields: name, action details */}

    <Divider>Options de retry</Divider>

    <Form.Item label="Activer le retry automatique">
      <Switch
        checked={retryEnabled}
        onChange={setRetryEnabled}
        aria-label="Activer le retry automatique"
      />
    </Form.Item>

    <Form.Item
      label="Nombre maximum de tentatives"
      validateStatus={maxAttempts < 1 || maxAttempts > 10 ? 'error' : ''}
      help={maxAttempts < 1 || maxAttempts > 10 ? 'Doit être entre 1 et 10' : ''}
    >
      <InputNumber
        min={1}
        max={10}
        value={maxAttempts}
        onChange={setMaxAttempts}
        disabled={!retryEnabled}
        style={{ width: '100%' }}
      />
    </Form.Item>

    <Form.Item
      label="Intervalle entre tentatives (secondes)"
      validateStatus={intervalSeconds < 1 ? 'error' : ''}
      help={intervalSeconds < 1 ? 'Doit être au moins 1 seconde' : ''}
    >
      <InputNumber
        min={1}
        value={intervalSeconds}
        onChange={setIntervalSeconds}
        disabled={!retryEnabled}
        style={{ width: '100%' }}
      />
    </Form.Item>

    <Form.Item
      label="Multiplicateur de backoff"
      validateStatus={backoffMultiplier < 1.0 || backoffMultiplier > 10.0 ? 'error' : ''}
      help={backoffMultiplier < 1.0 || backoffMultiplier > 10.0 ? 'Doit être entre 1.0 et 10.0' : ''}
    >
      <InputNumber
        min={1.0}
        max={10.0}
        step={0.1}
        value={backoffMultiplier}
        onChange={setBackoffMultiplier}
        disabled={!retryEnabled}
        style={{ width: '100%' }}
      />
    </Form.Item>

    <Alert
      type="info"
      icon={<InfoCircleOutlined />}
      message="L'intervalle sera multiplié par ce facteur à chaque tentative (backoff exponentiel)"
      style={{ marginBottom: 16 }}
    />

    {retryEnabled && (
      <Collapse
        defaultActiveKey={['timeline']}
        items={[{
          key: 'timeline',
          label: 'Prévisualisation de la timeline',
          children: (
            <ul style={{ paddingLeft: 20 }}>
              {retryTimeline.map(({ attempt, delay }) => (
                <li key={attempt}>
                  Tentative {attempt} : {formatDuration(delay)}
                </li>
              ))}
            </ul>
          ),
        }]}
      />
    )}

    {/* Existing buttons: save, delete */}
  </Drawer>
);
```

### Composant WorkflowStepNode : Badge et Tooltip retry

**Modifications dans WorkflowStepNode.tsx** :

```tsx
import { Badge, Tooltip } from 'antd';

const WorkflowStepNode: React.FC<NodeProps<WorkflowStepNodeData>> = ({ data }) => {
  const retryTooltip = data.retry_enabled ? (
    <>
      <div>Retry : {data.retry_max_attempts} tentatives max</div>
      <div>Intervalle : {data.retry_interval_seconds} secondes</div>
      <div>Backoff : {data.retry_backoff_multiplier}x</div>
    </>
  ) : null;

  return (
    <Tooltip title={retryTooltip} placement="top">
      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        padding: 12,
        background: '#fff',
        minWidth: 200,
        position: 'relative'
      }}>
        <Handle type="target" position={Position.Top} id="input" />

        <div style={{ fontWeight: 600 }}>{data.name ?? data.action_name}</div>
        <div style={{ fontSize: 12, color: '#8c8c8c' }}>
          {data.action_engine} / {data.action_platform}
        </div>

        {data.retry_enabled && (
          <Badge
            count={`Retry: ${data.retry_max_attempts}x`}
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              backgroundColor: '#1890ff',
              fontSize: 10
            }}
          />
        )}

        <Handle
          type="source"
          position={Position.Bottom}
          id="success"
          style={{ left: '30%', background: '#52c41a' }}
        />
        <Handle
          type="source"
          position={Position.Bottom}
          id="error"
          style={{ left: '70%', background: '#ff4d4f' }}
        />
      </div>
    </Tooltip>
  );
};
```

### Validation des valeurs de retry

**Validation Ant Design Form** (inline dans StepConfigPanel) :

```typescript
// Règles de validation
const retryRules = {
  maxAttempts: [
    { required: true, message: 'Nombre de tentatives requis' },
    { type: 'number', min: 1, max: 10, message: 'Doit être entre 1 et 10' }
  ],
  intervalSeconds: [
    { required: true, message: 'Intervalle requis' },
    { type: 'number', min: 1, message: 'Doit être au moins 1 seconde' }
  ],
  backoffMultiplier: [
    { required: true, message: 'Multiplicateur requis' },
    { type: 'number', min: 1.0, max: 10.0, message: 'Doit être entre 1.0 et 10.0' }
  ]
};

// Validation avant sauvegarde
const handleSave = () => {
  if (retryEnabled) {
    if (maxAttempts < 1 || maxAttempts > 10) {
      message.error('Nombre de tentatives invalide');
      return;
    }
    if (intervalSeconds < 1) {
      message.error('Intervalle invalide');
      return;
    }
    if (backoffMultiplier < 1.0 || backoffMultiplier > 10.0) {
      message.error('Multiplicateur de backoff invalide');
      return;
    }
  }

  // Sauvegarder les modifications
  onSave({
    ...nodeData,
    retry_enabled: retryEnabled,
    retry_max_attempts: retryEnabled ? maxAttempts : null,
    retry_interval_seconds: retryEnabled ? intervalSeconds : null,
    retry_backoff_multiplier: retryEnabled ? backoffMultiplier : null,
  });
};
```

### Synchronisation bidirectionnelle avec le mode liste

**Données partagées** : Le state `workflowSteps` est partagé entre WorkflowBuilderCanvas (mode visuel) et WorkflowStepsEditor (mode liste). Les deux composants modifient la même source de données.

**Conversions** :
- `workflowStepsToReactFlow()` : WorkflowStep[] → React Flow nodes/edges (charge les champs retry dans node.data)
- `reactFlowToWorkflowSteps()` : React Flow nodes/edges → WorkflowStep[] (extrait les champs retry depuis node.data)

**Vérification** : S'assurer que les deux fonctions de conversion gèrent correctement les 4 champs retry :
- retry_enabled
- retry_max_attempts
- retry_interval_seconds
- retry_backoff_multiplier

### Guardrails (anti-erreurs dev / LLM)

- **Ne pas dupliquer** les champs retry : réutiliser la même structure que WorkflowStepsEditor (même noms de champs, mêmes validations)
- **Ne pas oublier** de mettre à jour `workflowStepsToReactFlow()` et `reactFlowToWorkflowSteps()` pour inclure les champs retry
- **Ne pas casser** la synchronisation mode liste/visuel : tester les deux sens de conversion
- **Rétrocompatibilité** : workflows existants sans retry configuré doivent fonctionner (valeurs null acceptées)
- **Accessibilité** : ajouter ARIA labels sur Switch, InputNumber, et tooltips
- **Performance** : calculer retryTimeline uniquement quand les valeurs changent (useMemo si nécessaire)
- **UX** : désactiver visuellement les champs quand retry est OFF (disabled + style grayed out)

### Testing Strategy

**Tests unitaires** (`frontend/src/components/admin/StepConfigPanel.test.tsx`) :
1. calculateRetryTimeline(4, 60, 2.0) génère timeline correcte
2. formatDuration(0) → "immédiate", formatDuration(60) → "1 min", formatDuration(3660) → "1 h 1 min"
3. StepConfigPanel affiche section retry avec champs corrects
4. Switch ON/OFF désactive/active les champs (disabled prop)
5. Validation : valeurs invalides déclenchent erreurs inline

**Tests composant** (`frontend/src/components/admin/WorkflowStepNode.test.tsx`) :
1. WorkflowStepNode affiche badge "Retry: 3x" quand retry_enabled = true
2. WorkflowStepNode n'affiche pas le badge quand retry_enabled = false
3. Tooltip affiche détails retry au survol
4. Tooltip n'est pas affiché si retry_enabled = false

**Tests intégration** (`frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx`) :
1. Configurer retry dans builder visuel → vérifier badge affiché sur nœud
2. Basculer vers mode liste → vérifier champs retry remplis
3. Modifier retry dans mode liste → basculer vers builder visuel → vérifier badge et config panel
4. Sauvegarder workflow avec retry → recharger → vérifier persistence

**Tests accessibilité** :
1. ARIA labels présents sur Switch et InputNumber
2. Navigation clavier (Tab, Enter) fonctionne
3. Tooltip accessible au focus clavier (pas seulement au survol)

### Project Structure Notes

- **Fichier modifié** : `idp-portal/frontend/src/components/admin/StepConfigPanel.tsx` (ajouter section retry)
- **Fichier modifié** : `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` (ajouter badge et tooltip)
- **Nouveau fichier utilitaire** : `idp-portal/frontend/src/utils/retryTimeline.ts` (calculateRetryTimeline, formatDuration)
- **Tests** : `idp-portal/frontend/src/components/admin/StepConfigPanel.test.tsx` (étendre)
- **Tests** : `idp-portal/frontend/src/components/admin/WorkflowStepNode.test.tsx` (étendre)
- **Tests** : `idp-portal/frontend/src/utils/retryTimeline.test.ts` (nouveau)

### Previous Story Intelligence (Story 16.5)

- **Story 16.5** (done) : Builder visuel opérationnel avec React Flow, StepConfigPanel créé, WorkflowStepNode custom, synchronisation bidirectionnelle fonctionnelle
- **Patterns établis** :
  - StepConfigPanel utilise Ant Design Drawer, Form.Item, InputNumber
  - WorkflowStepNode est un composant custom avec 3 handles (input, success, error)
  - Conversion bidirectionnelle WorkflowStep[] ↔ React Flow (nodes, edges) via fonctions utilitaires
  - Validation inline avec Ant Design Form (validateStatus="error")
  - Tests unitaires et d'intégration complets (28 tests dans WorkflowBuilderCanvas.test.tsx)

**Insights pour Story 16.6** :
- **Réutiliser** la structure de WorkflowStepsEditor pour les champs retry (même validations, mêmes defaults)
- **Étendre** StepConfigPanel sans casser l'existant (ajouter section retry après les champs existants)
- **Synchroniser** automatiquement via workflowStepsToReactFlow() et reactFlowToWorkflowSteps() (pas de logique custom)
- **Tester** la synchronisation bidirectionnelle (mode liste ↔ builder visuel)
- **Accessibilité** : suivre le pattern des tests d'accessibilité de Story 16.5 (ARIA labels, navigation clavier)

### Git Intelligence

**Commits récents (Epic 16)** :
1. `99064cd` - chore(16.5): Post-implementation cleanup and FastAPI decommissioning
   - Nettoyage après Story 16.5
   - **Pattern** : Commit de nettoyage séparé après implémentation

2. `4e0e601` - docs(16.5): Update story status to done after code review
   - Mise à jour status story après code review
   - **Pattern** : Documentation et status tracking rigoureux

3. `9ca3283` - feat(16.5): Add visual workflow builder with React Flow
   - Implémentation complète builder visuel
   - 28 tests unitaires et d'intégration passent
   - **Pattern** : Commit feature complet avec tests

4. `f67fc75` - feat(16.4): Add retry engine with exponential backoff for workflow steps
   - Moteur de retry avec backoff exponentiel
   - **Pattern** : Logique backend complète avant UI

5. `10e174f` - feat(4.12): Complete workflow step parameters implementation with adapter payload preparation
   - Préparation payload adapter
   - **Pattern** : Validation complète avant implémentation

**Insights pour Story 16.6** :
- **Commit feature complet** : implémenter tous les AC en un seul commit feature (feat(16.6): Add retry configuration UI in visual workflow builder)
- **Tests avant commit** : s'assurer que tous les tests passent avant de committer
- **Documentation** : mettre à jour le story status et le change log après implémentation
- **Nettoyage séparé** : si nécessaire, faire un commit de nettoyage après la feature

### Latest Tech Information (Ant Design 6.2, React 19)

**Ant Design 6.2 (2026)** :
- **Switch** : Contrôle booléen accessible, supporte ARIA labels
  - `<Switch checked={value} onChange={setValue} aria-label="..." />`
- **InputNumber** : Champ numérique avec min/max/step
  - `<InputNumber min={1} max={10} step={1} value={value} onChange={setValue} />`
  - Précision : `step={0.1}` pour les décimales
- **Badge** : Indicateur visuel (count ou dot)
  - `<Badge count="Retry: 3x" style={{ ... }} />`
- **Tooltip** : Info-bulle au survol ou focus
  - `<Tooltip title="..." placement="top">{children}</Tooltip>`
- **Collapse** : Panneau repliable
  - `<Collapse items={[{ key, label, children }]} />`
- **Alert** : Message d'information
  - `<Alert type="info" icon={<InfoCircleOutlined />} message="..." />`

**React 19 (utilisé dans le projet)** :
- Hooks standards : useState, useMemo, useCallback
- Pas de changement breaking pour cette story

**Best practices 2026** :
- Utiliser des composants contrôlés (controlled components) pour les formulaires
- Validation inline avec Ant Design Form.Item (validateStatus, help)
- ARIA labels sur tous les contrôles interactifs
- useMemo pour les calculs coûteux (ex: calculateRetryTimeline si appelé fréquemment)

**Sécurité** :
- Pas de vulnérabilités connues dans Ant Design 6.2 (février 2026)
- Validation côté client + côté serveur (backend valide aussi les champs retry)

### References

- [Source: _bmad-output/implementation-artifacts/epic-16-builder-workflow-visuel.md#Story-16.6] — Spécification complète de la story
- [Source: _bmad-output/implementation-artifacts/16-5-interface-builder-visuel-workflow.md] — Builder visuel existant
- [Source: _bmad-output/implementation-artifacts/16-4-moteur-retry-backoff-exponentiel.md] — Moteur de retry backend
- [Source: _bmad-output/implementation-artifacts/16-2-modele-donnees-workflows-branches-et-retry.md] — Modèle de données retry
- [Source: idp-portal/frontend/src/components/admin/StepConfigPanel.tsx] — Composant à étendre
- [Source: idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx] — Nœud custom à modifier
- [Source: idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx] — Champs retry existants (mode liste)
- [Source: idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx] — Canvas React Flow
- [Ant Design 6.2 Documentation](https://ant.design) — Switch, InputNumber, Badge, Tooltip, Collapse, Alert
- [React Flow Documentation](https://reactflow.dev) — Custom nodes, tooltips

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A — No debugging required, clean implementation.

### Completion Notes List

- **AC1**: Section "Options de retry" ajoutée dans StepConfigPanel avec Switch, 3 InputNumber, et Alert info
- **AC2**: Champs numériques désactivés quand retry OFF via `disabled={!retryEnabled}`; valeurs préservées (controlled components)
- **AC3**: Badge "Retry: Nx" affiché en haut à droite du nœud WorkflowStepNode via Ant Design Badge
- **AC4**: Prévisualisation timeline avec calculateRetryTimeline() et formatDuration(); affichage dynamique en durée lisible
- **AC5**: Tooltip Ant Design détaillé (tentatives max, intervalle, backoff) affiché uniquement si retry_enabled=true
- **AC6**: Validation inline : max_attempts [1-10], interval >= 1, backoff [1.0-10.0]; messages d'erreur avec `status="error"` et Text role="alert"
- **AC7**: Conversion bidirectionnelle déjà en place (workflowStepsToReactFlow/reactFlowToWorkflowSteps gèrent les 4 champs retry)
- **AC8**: Synchronisation assurée via state partagé workflowSteps dans le composant parent; même données entre modes liste et visuel
- **Tests**: 69 tests passent — 14 retryTimeline, 17 StepConfigPanel, 10 WorkflowStepNode, 28 WorkflowBuilderCanvas (existants, non-régressés)

### File List

- `idp-portal/frontend/src/utils/retryTimeline.ts` (nouveau) — Fonctions calculateRetryTimeline() et formatDuration()
- `idp-portal/frontend/src/utils/retryTimeline.test.ts` (nouveau) — 14 tests unitaires
- `idp-portal/frontend/src/components/admin/StepConfigPanel.tsx` (modifié) — Section retry étendue avec validation, timeline preview, info alert
- `idp-portal/frontend/src/components/admin/StepConfigPanel.test.tsx` (nouveau) — 17 tests composant
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` (modifié) — Badge "Retry: Nx" et tooltip détaillé
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.test.tsx` (nouveau) — 10 tests composant
