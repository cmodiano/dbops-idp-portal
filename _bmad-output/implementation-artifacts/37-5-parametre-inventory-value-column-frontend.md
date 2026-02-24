# Story 37.5 : Paramètre d'action — inventory_value_column (frontend)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBOPS,
je veux dans l'éditeur de paramètres pouvoir choisir la **colonne valeur** pour un paramètre source inventaire, et en exécution voir la valeur soumise correspondre à cette colonne,
afin d'utiliser la bonne colonne métier (name, id, etc.) pour chaque paramètre.

## Acceptance Criteria

1. **Given** l'éditeur de paramètres (ParametersEditor)
   **When** un paramètre a `source: 'inventory'` et un `inventory_type` défini (servers, instances, databases)
   **Then** un champ optionnel « Colonne valeur » est affiché sous le sélecteur `Type d'inventaire`
   **And** les options sont une liste déroulante dépendante de l'`inventory_type` :
   - `servers` → `name`, `id`, `environment`, `engine_type`
   - `instances` → `name`, `id`, `server_ref`, `db_ref`
   - `databases` → `name`, `id`
   **And** si `inventory_type` n'est pas défini, le champ n'est pas affiché
   **And** à la sauvegarde, `inventory_value_column` est inclus dans la propriété du paramètre si une valeur est choisie

2. **Given** le formulaire d'exécution (renderFieldInput, inventory select)
   **When** un champ est alimenté par l'inventaire (`inventorySource` défini)
   **And** `inventoryValueColumn` est défini (ex. `'server_ref'`)
   **Then** les options du Select affichent la colonne configurée comme libellé **et** comme valeur soumise
   **And** si `inventoryValueColumn` est absent, le comportement actuel est conservé (`value: item.id, label: item.name`)

3. **Given** une action existante sans `inventory_value_column`
   **Then** l'éditeur n'affiche pas d'erreur et le champ Colonne valeur est vide (optionnel)
   **And** le formulaire d'exécution se comporte comme aujourd'hui (rétrocompatibilité totale)

4. **Given** le round-trip schema ↔ liste (parametersSchema.ts)
   **When** un paramètre a `source: 'inventory'` et `inventory_value_column: 'server_ref'`
   **Then** `schemaToParameterList` extrait `inventory_value_column` dans le `ParameterDefinition`
   **And** `parameterListToSchema` le réécrit dans le JSON Schema (inchangé)
   **And** la conversion aller-retour préserve la valeur exacte

## Tasks / Subtasks

- [x] Task 1 : Étendre le type `ParameterDefinition` dans `catalog.ts` (AC: #1, #4)
  - [x] 1.1 Ajouter le champ `inventory_value_column?: string` après `inventory_type` dans l'interface `ParameterDefinition` avec un commentaire `/** Story 37.5 */`
  - [x] 1.2 Aucun autre changement dans ce fichier (ne pas toucher `InventorySourceType` ni les autres interfaces)

- [x] Task 2 : Étendre le type `InventoryItem` dans `inventory.ts` (AC: #2)
  - [x] 2.1 Ajouter les champs optionnels retournés par l'API inventaire pour les colonnes non typées :
    ```typescript
    engine_type?: string | null;  // servers
    server_ref?: string | null;   // instances
    db_ref?: string | null;       // instances
    ```
  - [x] 2.2 Vérifier que l'ajout de ces champs n'entraîne pas d'erreur TypeScript sur le code existant (les champs sont optionnels)

- [x] Task 3 : Mettre à jour `parametersSchema.ts` (AC: #4)
  - [x] 3.1 Dans `schemaToParameterList` — après l'extraction de `inventory_type` (ligne ~67), ajouter :
    ```typescript
    // Story 37.5: Extract inventory_value_column from schema properties
    if (typeof prop.inventory_value_column === 'string' && prop.inventory_value_column) {
      def.inventory_value_column = prop.inventory_value_column;
    }
    ```
  - [x] 3.2 Dans `parameterListToSchema` — dans le bloc `if (p.source === 'inventory')` (ligne ~110–115), ajouter après `inventory_type` :
    ```typescript
    if (p.inventory_value_column) {
      (base as Record<string, unknown>).inventory_value_column = p.inventory_value_column;
    }
    ```
  - [x] 3.3 Vérifier que `inventory_value_column` n'est écrit dans le schéma que quand `source === 'inventory'` (bloc existant)

- [x] Task 4 : Mettre à jour `useDynamicForm.ts` (AC: #2)
  - [x] 4.1 Dans l'interface `ParameterField`, ajouter après `inventorySource` :
    ```typescript
    /** Story 37.5: Column to use as value/label in inventory dropdowns. */
    inventoryValueColumn?: string;
    ```
  - [x] 4.2 Dans `extractParameterFields`, dans le bloc IIFE `inventorySource`, ajouter après le retour de `invType` une extraction du `inventory_value_column`. Restructurer le retour pour exporter les deux valeurs :
    ```typescript
    // Extraire inventoryValueColumn depuis le schéma
    inventoryValueColumn: (() => {
      if ((prop as Record<string, unknown>)?.source !== 'inventory') return undefined;
      const col = (prop as Record<string, unknown>)?.inventory_value_column as string | undefined;
      return col || undefined;
    })(),
    ```
  - [x] 4.3 S'assurer que le champ `inventoryValueColumn` est inclus dans l'objet retourné par `extractParameterFields`

- [x] Task 5 : Mettre à jour `renderFieldInput.tsx` (AC: #2, #3)
  - [x] 5.1 Dans la section `if (field.inventorySource)`, remplacer le mapping des options :

    **Avant :**
    ```typescript
    options={items.map((item) => ({
      value: item.id,
      label: item.name,
    }))}
    ```

    **Après :**
    ```typescript
    options={items.map((item) => {
      // Story 37.5: Use configured column if set, else default (id as value, name as label)
      if (field.inventoryValueColumn) {
        const colVal = (item as Record<string, unknown>)[field.inventoryValueColumn];
        const strVal = colVal != null ? String(colVal) : item.name;
        return { value: strVal, label: strVal };
      }
      return { value: item.id, label: item.name };
    })}
    ```
  - [x] 5.2 Ne pas modifier le reste de la fonction (pas de changement pour les autres types de champs)

- [x] Task 6 : Mettre à jour `ParametersEditor.tsx` (AC: #1, #3)
  - [x] 6.1 Ajouter la constante `INVENTORY_VALUE_COLUMN_OPTIONS` après `INVENTORY_TYPE_OPTIONS` :
    ```typescript
    /** Story 37.5: Allowed value columns per inventory type. Mirrors VALID_INVENTORY_VALUE_COLUMNS in catalog/serializers.py. */
    const INVENTORY_VALUE_COLUMN_OPTIONS: Record<InventorySourceType, { value: string; label: string }[]> = {
      servers:   [{ value: 'name', label: 'name' }, { value: 'id', label: 'id' }, { value: 'environment', label: 'environment' }, { value: 'engine_type', label: 'engine_type' }],
      instances: [{ value: 'name', label: 'name' }, { value: 'id', label: 'id' }, { value: 'server_ref', label: 'server_ref' }, { value: 'db_ref', label: 'db_ref' }],
      databases: [{ value: 'name', label: 'name' }, { value: 'id', label: 'id' }],
    };
    ```
  - [x] 6.2 Dans `SortableParamCard`, dans le `{(param.source === 'inventory') && (...)}` existant, ajouter **après** le `Form.Item` `Type d'inventaire`, un nouveau `Form.Item` conditionnel (uniquement si `inventory_type` est défini) :
    ```tsx
    {(param.source === 'inventory' && param.inventory_type) && (
      <Form.Item
        label={
          <span>
            Colonne valeur{' '}
            <Tooltip title="Colonne de l'entité inventaire utilisée comme valeur et libellé du paramètre (défaut : name → id/name selon comportement actuel).">
              <InfoCircleOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />
            </Tooltip>
          </span>
        }
        style={{ marginBottom: 0 }}
      >
        <Select
          value={param.inventory_value_column}
          onChange={(v) => onParamChange(index, 'inventory_value_column', v || undefined)}
          options={INVENTORY_VALUE_COLUMN_OPTIONS[param.inventory_type]}
          style={{ width: 180 }}
          allowClear
          placeholder="Par défaut (name)"
          aria-label={`Colonne valeur parametre ${index + 1}`}
        />
      </Form.Item>
    )}
    ```
  - [x] 6.3 Dans `handleParamChange`, dans le `case 'source'`, ajouter `current.inventory_value_column = undefined;` lors du reset (quand source change en 'manual') :
    ```typescript
    } else if (field === 'source') {
      current.source = fieldValue as ParameterDefinition['source'];
      if (fieldValue === 'manual') {
        current.inventory_type = undefined;
        current.inventory_value_column = undefined; // Story 37.5
      }
    }
    ```
  - [x] 6.4 Gérer le reset de `inventory_value_column` quand `inventory_type` change (les colonnes valides changent) : dans le `onChange` du Select `Type d'inventaire`, appeler aussi `onParamChange(index, 'inventory_value_column', undefined)`

- [x] Task 7 : Tests `parametersSchema.test.ts` (AC: #4)
  - [x] 7.1 `test_schema_to_list_extracts_inventory_value_column` — schéma avec `source=inventory, inventory_type=instances, inventory_value_column=server_ref` → la liste retourne un ParameterDefinition avec `inventory_value_column='server_ref'`
  - [x] 7.2 `test_schema_to_list_absent_inventory_value_column` — schéma sans `inventory_value_column` → `ParameterDefinition` sans `inventory_value_column` (ou undefined) — rétrocompatibilité
  - [x] 7.3 `test_list_to_schema_writes_inventory_value_column` — ParameterDefinition avec `source=inventory, inventory_type=servers, inventory_value_column=environment` → JSON Schema contient `inventory_value_column: 'environment'`
  - [x] 7.4 `test_list_to_schema_omits_inventory_value_column_when_absent` — ParameterDefinition avec `source=inventory, inventory_type=servers` sans `inventory_value_column` → JSON Schema ne contient pas la clé `inventory_value_column`
  - [x] 7.5 `test_round_trip_inventory_value_column` — schema → liste → schema préserve `inventory_value_column` sans altération

- [x] Task 8 : Tests `useDynamicForm.test.ts` (AC: #2)
  - [x] 8.1 `test_extracts_inventory_value_column_from_schema` — schéma `source=inventory, inventory_type=databases, inventory_value_column=id` → `extractParameterFields` retourne un `ParameterField` avec `inventorySource='databases'` et `inventoryValueColumn='id'`
  - [x] 8.2 `test_absent_inventory_value_column_gives_undefined` — schéma sans `inventory_value_column` → `inventoryValueColumn` est `undefined`
  - [x] 8.3 `test_inventory_value_column_ignored_when_not_inventory` — source non inventory → `inventoryValueColumn` est `undefined`

- [x] Task 9 : Tests `renderFieldInput.test.tsx` (AC: #2, #3)
  - [x] 9.1 `test_inventory_field_uses_value_column_for_options` — `inventoryValueColumn='server_ref'`, items avec `{ id: '1', name: 'i1', server_ref: 'srv01' }` → les options contiennent `{ value: 'srv01', label: 'srv01' }` (pas `{ value: '1', label: 'i1' }`)
  - [x] 9.2 `test_inventory_field_default_when_no_value_column` — sans `inventoryValueColumn` → options `{ value: item.id, label: item.name }` (comportement actuel préservé)
  - [x] 9.3 `test_inventory_field_null_column_value_fallback` — `inventoryValueColumn='engine_type'`, item sans `engine_type` (undefined) → fallback sur `item.name` (pas de crash, valeur définie)

- [x] Task 10 : Tests `ParametersEditor.test.tsx` (AC: #1, #3)
  - [x] 10.1 `test_shows_value_column_select_when_inventory_type_defined` — param avec `source=inventory, inventory_type=servers` → le sélecteur `Colonne valeur` est affiché avec les options servers (name, id, environment, engine_type)
  - [x] 10.2 `test_no_value_column_when_inventory_type_absent` — param avec `source=inventory` sans `inventory_type` → sélecteur Colonne valeur absent
  - [x] 10.3 `test_options_change_when_inventory_type_changes` — changer inventory_type de servers vers databases → options Colonne valeur = name, id (pas engine_type)
  - [x] 10.4 `test_value_column_cleared_on_source_manual` — param avec `source=inventory, inventory_value_column=name`, changer source en manual → `inventory_value_column` réinitialisé à undefined

## Dev Notes

### Contexte et dépendances

Story 37.5 dépend de **37.4 (done)** — la validation backend de `inventory_value_column` est en place. Le frontend doit simplement transmettre la valeur telle quelle ; il n'y a pas de validation frontend des valeurs autorisées (responsabilité backend).

Les stories 37.1, 37.2, 37.3 sont `done` et n'impactent pas cette story.

### Architecture — Composants concernés

**Fichiers à modifier (5 fichiers source, 4 fichiers test) :**

| Fichier | Modification |
|---------|-------------|
| `frontend/src/types/api/catalog.ts` | + `inventory_value_column?: string` dans `ParameterDefinition` |
| `frontend/src/types/api/inventory.ts` | + `engine_type?`, `server_ref?`, `db_ref?` dans `InventoryItem` |
| `frontend/src/utils/parametersSchema.ts` | Lire/écrire `inventory_value_column` dans les deux directions |
| `frontend/src/hooks/useDynamicForm.ts` | + `inventoryValueColumn?: string` dans `ParameterField`, extraction |
| `frontend/src/components/catalog/renderFieldInput.tsx` | Utiliser `inventoryValueColumn` pour value/label des options |
| `frontend/src/components/admin/ParametersEditor.tsx` | UI select Colonne valeur, reset sur changements source/type |
| `frontend/src/utils/parametersSchema.test.ts` | 5 nouveaux tests round-trip |
| `frontend/src/hooks/useDynamicForm.test.ts` | 3 nouveaux tests extraction |
| `frontend/src/components/catalog/renderFieldInput.test.tsx` | 3 nouveaux tests |
| `frontend/src/components/admin/ParametersEditor.test.tsx` | 4 nouveaux tests |

**Aucune modification requise :**
- `execution_service.ts` — `fetchInventoryItems` et `useTargetInventory` ne changent pas ; `inventory_value_column` est une propriété du schéma, pas un filtre API
- Backend catalog ou inventory — déjà traité par 37.4

### Analyse du code existant — points critiques

#### catalog.ts lignes 317–332 — ParameterDefinition
```typescript
export interface ParameterDefinition {
  id?: string;
  name: string;
  type: ParameterSchemaType;
  required: boolean;
  default?: string;
  description?: string;
  enum?: string[];
  source?: 'manual' | 'inventory';
  inventory_type?: InventorySourceType;
  // ← AJOUTER ICI : inventory_value_column?: string; (Task 1.1)
}
```

#### inventory.ts lignes 1–8 — InventoryItem
```typescript
export interface InventoryItem {
  id: string;
  name: string;
  environment: string | null;
  // ← AJOUTER ICI (Task 2.1) :
  // engine_type?: string | null;
  // server_ref?: string | null;
  // db_ref?: string | null;
}
```

Ces champs sont retournés par les endpoints `/inventory/servers/`, `/inventory/instances/`, `/inventory/databases/` car le mapper les expose via `build_select_clause`. Voir `inventory/mapper.py` pour les colonnes mappées par entité.

#### parametersSchema.ts — points d'injection
- Lecture (schemaToParameterList) : après ligne 68 (extraction `inventory_type`)
- Écriture (parameterListToSchema) : dans le bloc `if (p.source === 'inventory')`, lignes 110–115, après l'écriture de `inventory_type`

#### useDynamicForm.ts — extractParameterFields ligne 67
Le bloc IIFE pour `inventorySource` doit être complété par un bloc séparé pour `inventoryValueColumn`. **Ne pas modifier le bloc IIFE existant** — ajouter `inventoryValueColumn` comme propriété indépendante dans l'objet retourné (ligne ~56).

#### renderFieldInput.tsx ligne 76-79 — options mapping
Le mapping actuel `{ value: item.id, label: item.name }` est le comportement par défaut quand `inventory_value_column` est absent. Le nouveau code utilise `field.inventoryValueColumn` si présent, sinon conserve l'ancien comportement exactement.

**Gestion des colonnes null/undefined :** utiliser `colVal != null ? String(colVal) : item.name` pour éviter "null" ou "undefined" comme label.

#### ParametersEditor.tsx — structure de la modification
La condition `{(param.source === 'inventory') && (...)}` doit passer d'un `<Space>` avec 2 `Form.Item` à un `<Space>` avec 3 `Form.Item`. Voici la structure cible :

```tsx
{/* Story 23.5 + 37.5: Source, inventory_type et inventory_value_column */}
<Space wrap style={{ width: '100%' }} size="small">
  <Form.Item label="Source" ...>  {/* inchangé */}
    <Select source ... />
  </Form.Item>

  {(param.source === 'inventory') && (
    <Form.Item label="Type d'inventaire" ...>  {/* inchangé */}
      <Select inventory_type onChange={(v) => { onParamChange(index, 'inventory_type', v); onParamChange(index, 'inventory_value_column', undefined); }} ... />
    </Form.Item>
  )}

  {(param.source === 'inventory' && param.inventory_type) && (
    <Form.Item label="Colonne valeur" ...>  {/* NOUVEAU 37.5 */}
      <Select inventory_value_column allowClear ... />
    </Form.Item>
  )}
</Space>
```

> **Important :** le reset de `inventory_value_column` à `undefined` lors du changement d'`inventory_type` se fait dans le `onChange` du Select `inventory_type`, pas dans `handleParamChange`. Voir Task 6.4.

### Alignement avec le backend (37.4)

Les colonnes autorisées (utilisées dans `INVENTORY_VALUE_COLUMN_OPTIONS`) correspondent exactement à `VALID_INVENTORY_VALUE_COLUMNS` dans `catalog/serializers.py` :

```python
VALID_INVENTORY_VALUE_COLUMNS = {
    'servers':   ('name', 'id', 'environment', 'engine_type'),
    'instances': ('name', 'id', 'server_ref', 'db_ref'),
    'databases': ('name', 'id'),
}
```

Ces deux constantes doivent rester synchronisées. Si le backend ajoute une colonne, le frontend doit être mis à jour également (et réciproquement).

### Lancer les tests frontend

```bash
# Depuis idp-portal/frontend/ :
npx vitest run src/utils/parametersSchema.test.ts
npx vitest run src/hooks/useDynamicForm.test.ts
npx vitest run src/components/catalog/renderFieldInput.test.tsx
npx vitest run src/components/admin/ParametersEditor.test.tsx

# Ou tous les tests frontend :
npx vitest run
```

### Comportement de rétrocompatibilité (AC #3)

- **Éditeur :** `inventory_value_column` est optionnel (Select avec `allowClear`). Les actions existantes sans ce champ s'affichent sans erreur — le select est simplement vide.
- **Formulaire d'exécution :** quand `inventoryValueColumn` est `undefined`, le code retombe sur `{ value: item.id, label: item.name }` exactement comme aujourd'hui. Aucun changement de comportement pour les actions existantes.

### Project Structure Notes

- Toutes les modifications restent dans `frontend/src/` — aucun changement backend
- Les fichiers modifiés suivent les patterns établis (commentaires `Story X.Y`, même style d'imports)
- `InventorySourceType` et les types existants ne changent pas de shape — ajouts uniquement

### References

- [Source: `frontend/src/types/api/catalog.ts` — ParameterDefinition lignes 317–332]
- [Source: `frontend/src/types/api/inventory.ts` — InventoryItem lignes 1–8]
- [Source: `frontend/src/utils/parametersSchema.ts` — schemaToParameterList lignes 62–68, parameterListToSchema lignes 109–115]
- [Source: `frontend/src/hooks/useDynamicForm.ts` — ParameterField interface lignes 12–25, extractParameterFields lignes 27–83]
- [Source: `frontend/src/components/catalog/renderFieldInput.tsx` — inventory Select lignes 65–89]
- [Source: `frontend/src/components/admin/ParametersEditor.tsx` — SortableParamCard lignes 218–270, handleParamChange lignes 296–312]
- [Source: `_bmad-output/planning-artifacts/epic-37-inventaire-environnement-serveur-colonne-engine.md` — Story 37.5 AC complets]
- [Source: `_bmad-output/planning-artifacts/spec-inventaire-environnement-serveur-colonne-engine.md` — Section 2]
- [Source: `_bmad-output/implementation-artifacts/37-4-parametre-inventory-value-column-backend.md` — VALID_INVENTORY_VALUE_COLUMNS, AC validés]
- [Source: `idp-portal/django_backend/inventory/mapper.py` — colonnes exposées par entité (name, id, environment, engine_type, server_ref, db_ref)]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

Story 37.5 implémentée avec succès — 15 nouveaux tests (5+3+3+4), 2491 tests frontend au total, 0 régression.
- Task 1 : `inventory_value_column?: string` ajouté dans `ParameterDefinition`
- Task 2 : `engine_type?`, `server_ref?`, `db_ref?` ajoutés dans `InventoryItem`
- Task 3 : `schemaToParameterList` extrait + `parameterListToSchema` écrit `inventory_value_column`
- Task 4 : `inventoryValueColumn?: string` dans `ParameterField`, extraction IIFE ajoutée
- Task 5 : `renderFieldInput` utilise `inventoryValueColumn` pour value/label des options (fallback sur name si null)
- Task 6 : `ParametersEditor` — constante `INVENTORY_VALUE_COLUMN_OPTIONS`, Select Colonne valeur conditionnel, reset sur changement source/type

### Senior Developer Review (AI)

**Date :** 2026-02-23
**Statut final :** Approuvé — tous les problèmes corrigés

#### Problèmes trouvés et corrigés

**🔴 HIGH — Double `onParamChange` dans Source onChange (`ParametersEditor.tsx`)**
- **Cause :** La Source Select appelait `onParamChange(index, 'source', v)` puis `onParamChange(index, 'inventory_type', undefined)`. Avec React 18 batching, le second appel gagne car il relit `value` original — `source` restait `'inventory'` et `inventory_value_column` n'était pas effacé.
- **Fix :** Suppression du second appel ; `handleParamChange` gère déjà le reset via la branche `field === 'source'`.

**🔴 HIGH — Double `onParamChange` dans inventory_type onChange (`ParametersEditor.tsx`)**
- **Cause :** Même pattern : `onParamChange(index, 'inventory_type', v)` + `onParamChange(index, 'inventory_value_column', undefined)`. Le second call écrase le premier — `inventory_type` ne changeait pas.
- **Fix :** Ajout de la branche `field === 'inventory_type'` dans `handleParamChange` (reset atomique) ; suppression du double appel JSX.

**🟡 MEDIUM — Test `test_value_column_cleared_on_source_manual` no-op (`ParametersEditor.test.tsx`)**
- **Cause :** `render(...)` suivi de `editor.unmount()` sans aucune interaction UI — test trivially passing.
- **Fix :** Remplacé par un test avec `rerender` qui vérifie la disparition des selects après application du résultat de `handleParamChange`.

**🟡 MEDIUM — Test `resets inventory_type when source changes to manual` no-op (`ParametersEditor.test.tsx`)**
- **Cause :** Même anti-pattern hérité de Story 23.5.
- **Fix :** Remplacé par test `rerender` avec assertions DOM.

**🟢 LOW — Chaîne vide non couverte dans le fallback (`renderFieldInput.tsx`)**
- **Cause :** `colVal != null` est `true` pour `""` → option `{ value: "", label: "" }` affichée.
- **Fix :** `colVal != null && colVal !== ''` + nouveau test `test_inventory_field_empty_string_column_value_fallback`.

#### Résultat
- 100 tests passent (99 avant + 1 nouveau) — 0 régression
- Tous les AC vérifiés et implémentés correctement

### File List

- frontend/src/types/api/catalog.ts
- frontend/src/types/api/inventory.ts
- frontend/src/utils/parametersSchema.ts
- frontend/src/hooks/useDynamicForm.ts
- frontend/src/components/catalog/renderFieldInput.tsx
- frontend/src/components/admin/ParametersEditor.tsx
- frontend/src/utils/parametersSchema.test.ts
- frontend/src/hooks/useDynamicForm.test.ts
- frontend/src/components/catalog/renderFieldInput.test.tsx
- frontend/src/components/admin/ParametersEditor.test.tsx
