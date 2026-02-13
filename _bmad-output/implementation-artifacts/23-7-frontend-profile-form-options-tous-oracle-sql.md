# Story 23.7: Frontend — ProfileForm options Tous / Oracle / SQL

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBOPS créant ou modifiant un profil,
je veux pouvoir choisir rapidement "Tous les serveurs", "Tous les serveurs Oracle" ou "Tous les serveurs SQL",
afin d'octroyer l'accès à des groupes de serveurs par type de moteur sans avoir à lister individuellement chaque serveur.

## Acceptance Criteria

### AC1 : Section "Targets autorisés" avec options radio

**Given** je suis dans le formulaire d'édition d'un profil (ProfileForm)
**When** je consulte la section "Targets autorisés"
**Then** je vois un Radio.Group avec les options suivantes :
- "Tous les serveurs" (targets_type = 'all', filter_by_attribute = null)
- "Liste de serveurs" (targets_type = 'list', mode actuel)
- "Pattern de serveurs" (targets_type = 'pattern', mode actuel)
- **"Tous les serveurs Oracle"** (targets_type = 'all', filter_by_attribute = { "engine_type": ["oracle"] })
- **"Tous les serveurs SQL"** (targets_type = 'all', filter_by_attribute = { "engine_type": ["sqlserver"] })

**And** les options sont exclusives (un seul choix possible)
**And** les trois nouvelles options utilisent `targets_type='all'` avec différents filtres par attribut

### AC2 : Sélection "Tous les serveurs Oracle" crée filter_by_attribute

**Given** je modifie un profil
**When** je sélectionne "Tous les serveurs Oracle"
**Then** le formulaire prépare le payload suivant pour ProfileTargetPermissionsUpdate :
```json
{
  "targets_type": "all",
  "target_names": [],
  "target_patterns": [],
  "filter_by_attribute": {
    "engine_type": ["oracle"]
  }
}
```
**And** les champs `target_names` et `target_patterns` sont cachés (mode ALL)
**And** un message informatif explique : "Accès à tous les serveurs Oracle de tous les environnements"

### AC3 : Sélection "Tous les serveurs SQL" crée filter_by_attribute

**Given** je modifie un profil
**When** je sélectionne "Tous les serveurs SQL"
**Then** le formulaire prépare le payload suivant pour ProfileTargetPermissionsUpdate :
```json
{
  "targets_type": "all",
  "target_names": [],
  "target_patterns": [],
  "filter_by_attribute": {
    "engine_type": ["sqlserver"]
  }
}
```
**And** un message informatif explique : "Accès à tous les serveurs SQL de tous les environnements"

### AC4 : Option "Tous les serveurs" sans filtre

**Given** je modifie un profil
**When** je sélectionne "Tous les serveurs"
**Then** le formulaire prépare le payload suivant pour ProfileTargetPermissionsUpdate :
```json
{
  "targets_type": "all",
  "target_names": [],
  "target_patterns": [],
  "filter_by_attribute": null
}
```
**And** un message informatif explique : "Accès complet à tous les serveurs de tous les types et environnements"

### AC5 : Chargement initial — détecter filter_by_attribute et pré-sélectionner l'option

**Given** je charge un profil existant avec `filter_by_attribute = { "engine_type": ["oracle"] }`
**When** le formulaire se charge
**Then** l'option "Tous les serveurs Oracle" est pré-sélectionnée
**And** le `targets_type` indique 'all'

**Given** je charge un profil existant avec `filter_by_attribute = { "engine_type": ["sqlserver"] }`
**When** le formulaire se charge
**Then** l'option "Tous les serveurs SQL" est pré-sélectionnée

**Given** je charge un profil existant avec `filter_by_attribute = null` et `targets_type = 'all'`
**When** le formulaire se charge
**Then** l'option "Tous les serveurs" est pré-sélectionnée

**Given** je charge un profil existant avec `targets_type = 'list'`
**When** le formulaire se charge
**Then** l'option "Liste de serveurs" est pré-sélectionnée
**And** les champs `target_names` sont visibles et pré-remplis

**Given** je charge un profil existant avec `targets_type = 'pattern'`
**When** le formulaire se charge
**Then** l'option "Pattern de serveurs" est pré-sélectionnée
**And** les champs `target_patterns` sont visibles et pré-remplis

### AC6 : Validation backend compatible avec filter_by_attribute

**Given** le backend ProfileTargetPermissionsSerializer (Story 23.4 done)
**When** le frontend envoie `filter_by_attribute = { "engine_type": ["oracle"] }`
**Then** le backend accepte et valide que "engine_type" est un concept inventaire disponible
**And** la sauvegarde réussit sans erreur

**Given** le frontend envoie `filter_by_attribute = null`
**When** le profil est sauvegardé
**Then** le backend supprime le filtre par attribut (aucune restriction sur le type de moteur)

**Note** : AC6 est un rappel que Story 23.4 (done) a déjà implémenté la validation backend. Pas de travail backend dans cette story, seulement vérifier compatibilité frontend.

### AC7 : UX — Messages informatifs et clarté

**Given** l'interface ProfileForm à la section "Targets autorisés"
**When** une option est sélectionnée
**Then** :
- Option "Tous" → Alert info (type="info", showIcon) : "✓ Accès complet à tous les serveurs (tous types, tous environnements)"
- Option "Tous Oracle" → Alert info : "✓ Accès à tous les serveurs Oracle (tous environnements)"
- Option "Tous SQL" → Alert info : "✓ Accès à tous les serveurs SQL (tous environnements)"
- Option "Liste" → Champs Select multi-sélection visibles (target_names), pas d'Alert
- Option "Pattern" → Champs Select.Tags visibles (target_patterns), pas d'Alert

**And** les Alerts utilisent Ant Design `<Alert type="info" showIcon closable={false} />`
**And** les icônes sont ✓ (CheckCircleOutlined) pour renforcer la validation visuelle

### AC8 : Gestion edge cases et rétrocompatibilité

**Given** je crée un nouveau profil
**When** le formulaire s'ouvre
**Then** l'option par défaut est "Tous les serveurs" (targets_type='all', filter_by_attribute=null)

**Given** je charge un profil existant avec `filter_by_attribute = { "zone": ["prod"] }` (filtre non supporté par l'UI)
**When** le formulaire se charge
**Then** l'option "Tous les serveurs" est sélectionnée (fallback conservateur)
**And** un message Warning info s'affiche : "Ce profil utilise des filtres avancés non supportés par l'interface. L'édition réinitialisera ces filtres."

**Given** je charge un profil avec `filter_by_attribute = { "engine_type": ["oracle", "sqlserver"] }` (multi-valeur)
**When** le formulaire se charge
**Then** l'option "Tous les serveurs" est sélectionnée (fallback)
**And** un message Warning : "Ce profil utilise des filtres avancés (plusieurs types de moteurs). L'édition réinitialisera ces filtres."

**Given** le backend retourne une erreur de validation sur `filter_by_attribute`
**When** je sauvegarde le profil
**Then** l'erreur est affichée dans une Alert error au-dessus du formulaire
**And** le formulaire reste ouvert pour correction

### AC9 : Tests unitaires frontend

**Given** la nouvelle fonctionnalité de filtrage par type de moteur
**When** les tests sont exécutés
**Then** ils couvrent :

**ProfileForm component tests** :
- Sélection "Tous Oracle" → form values = { targets_type: 'all', target_names: [], target_patterns: [], filter_by_attribute: { engine_type: ['oracle'] } }
- Sélection "Tous SQL" → form values = { targets_type: 'all', filter_by_attribute: { engine_type: ['sqlserver'] } }
- Sélection "Tous" → filter_by_attribute = null
- Sélection "Liste" → targets_type = 'list', champs target_names visibles
- Sélection "Pattern" → targets_type = 'pattern', champs target_patterns visibles
- Chargement profil avec filter_by_attribute = { engine_type: ['oracle'] } → option Oracle pré-sélectionnée
- Chargement profil avec filter_by_attribute = null et targets_type='all' → option Tous pré-sélectionnée
- Chargement profil avec filter_by_attribute inconnu → option Tous + Warning affiché
- Submit avec "Tous Oracle" → appel PUT /profiles/{id}/targets avec payload correct

**ProfileForm integration tests** :
- Création profil → sélection Oracle → sauvegarde → vérifier API call avec filter_by_attribute
- Édition profil Oracle existant → changement vers SQL → sauvegarde → vérifier mise à jour filter_by_attribute
- Édition profil Liste existant → changement vers Oracle → sauvegarde → vérifier targets_type='all' + filter

**Couverture** : ≥ 85% pour ProfileForm.tsx modifié

### AC10 : Documentation inline et commentaires

**Given** les fichiers modifiés (ProfileForm.tsx, types API, services)
**When** un développeur lit le code
**Then** :
- Commentaire JSDoc sur `filter_by_attribute` field : "Story 23.7 - Filter targets by inventory attributes (e.g., engine_type)"
- Commentaire inline dans ProfileForm : "Story 23.7 - Radio options for All servers / Oracle / SQL with filter_by_attribute"
- Commentaire dans putProfileTargets call : "Story 23.7 - Include filter_by_attribute in payload for engine-based filtering"
- Type `ProfileTargetPermissionsUpdate` étendu avec `filter_by_attribute?: Record<string, string[]> | null`

## Tasks / Subtasks

- [x] Task 1 : Étendre types TypeScript pour filter_by_attribute (AC6, AC10)
  - [x] 1.1 : Modifier `frontend/src/types/api/profiles.ts` — ajouté `filter_by_attribute?: Record<string, string[]> | null` à `ProfileTargetPermissionsUpdate` et `ProfileTargetPermissionsResponse`
  - [x] 1.2 : JSDoc sur `filter_by_attribute` : "Filter targets by inventory attributes (e.g., engine_type: ['oracle']). Story 23.7"
  - [x] 1.3 : filter_by_attribute calculé depuis targetsMode state (pas stocké dans form values — évite confusion)
  - [x] 1.4 : Types vérifiés par compilation TypeScript (build passe)

- [x] Task 2 : Créer helper pour détecter type de target permission (AC5)
  - [x] 2.1 : Créé `detectTargetsMode(targetsPerms: ProfileTargetPermissionsResponse): TargetsMode` exporté depuis ProfileForm.tsx
  - [x] 2.2 : TargetsMode = 'all' | 'all-oracle' | 'all-sql' | 'list' | 'pattern' | 'advanced'
  - [x] 2.3 : Logique détection implémentée
  - [x] 2.4 : Case-insensitive pour engine_type values (oracle/Oracle/ORACLE → all-oracle)
  - [x] 2.5 : Tests : 12 tests unitaires dans detectTargetsMode.test.ts (all, oracle, oracle-case, sql, sql-case, list, pattern, multi-value, unsupported-key, multi-key, unknown-value, undefined)

- [x] Task 3 : Modifier ProfileForm — ajouter Radio.Group avec 5 options (AC1, AC7)
  - [x] 3.1 : State `targetsMode: TargetsMode` initialisé à 'all' ou détecté depuis editProfile
  - [x] 3.2 : Radio.Group avec 5 options (all, all-oracle, all-sql, list, pattern)
  - [x] 3.3 : onChange → setTargetsMode + clear target_names/target_patterns pour modes ALL
  - [x] 3.4 : Layout vertical via flexbox
  - [x] 3.5 : Tests : rendu 5 options vérifié

- [x] Task 4 : Afficher champs conditionnels selon targetsMode (AC2, AC3, AC4, AC7)
  - [x] 4.1–4.4 : Conditional rendering basé sur targetsMode
  - [x] 4.5 : Tests couverts dans ProfileForm.test.tsx

- [x] Task 5 : Afficher Alerts informatifs selon targetsMode (AC7)
  - [x] 5.1–5.7 : Alerts info (CheckCircleOutlined) pour all/oracle/sql, warning (WarningOutlined) pour advanced
  - [x] 5.8 : Tests couverts

- [x] Task 6 : Calculer form values depuis targetsMode au submit (AC2, AC3, AC4)
  - [x] 6.1 : getFilterByAttribute(mode) et getTargetsTypeFromMode(mode) helpers
  - [x] 6.2 : putProfileTargets appelé avec payload incluant filter_by_attribute
  - [x] 6.3 : Erreur backend gérée via catch + setPermError
  - [x] 6.4 : Tests submit pour all/oracle/sql couverts

- [x] Task 7 : Chargement initial — détecter et pré-sélectionner targetsMode (AC5)
  - [x] 7.1 : detectTargetsMode appelé dans useEffect après getProfileTargets
  - [x] 7.2 : targetsMode initialisé depuis detectTargetsMode
  - [x] 7.3 : Default 'all' pour nouveau profil
  - [x] 7.4 : Tests chargement profil all/oracle/sql/advanced couverts

- [x] Task 8 : Gestion edge cases — filtres avancés (AC8)
  - [x] 8.1–8.3 : detectTargetsMode retourne 'advanced' pour multi-keys, multi-values, clés non supportées
  - [x] 8.4 : Warning Alert affiché pour mode 'advanced'
  - [x] 8.5 : Tests edge cases couverts (multi-valeur, zone non supportée, multi-critères)

- [x] Task 9 : Validation et gestion erreurs backend (AC6, AC8)
  - [x] 9.1 : Compatible avec ProfileTargetPermissionsSerializer (Story 23.4)
  - [x] 9.2–9.3 : Erreur 400 affichée via setPermError
  - [x] 9.4–9.5 : Tests erreur backend couverts

- [x] Task 10 : Tests unitaires ProfileForm (AC9)
  - [x] 10.1–10.9 : 19 tests Story 23.7 dans ProfileForm.test.tsx (sélection, chargement, submit, edge cases, transitions, erreurs)
  - [x] 10.10 : 33 tests total dans ProfileForm.test.tsx (14 existants + 19 Story 23.7)

- [x] Task 11 : Tests intégration ProfileForm (AC9)
  - [x] 11.1 : Test submit Oracle → vérifier putProfileTargets avec filter_by_attribute
  - [x] 11.2 : Test Oracle → SQL → submit correct payload
  - [x] 11.3 : Test List → Oracle → submit targets_type='all' + filter
  - [x] 11.4 : Test advanced → Warning → Tous → submit filter_by_attribute=null
  - [x] 11.5 : Tests intégration inclus dans ProfileForm.test.tsx (mêmes tests, couvrent le flow complet)

- [x] Task 12 : Documentation et commentaires (AC10)
  - [x] 12.1 : JSDoc sur `filter_by_attribute` dans types/api/profiles.ts
  - [x] 12.2 : JSDoc sur `detectTargetsMode` helper
  - [x] 12.3 : Inline comment dans Radio.Group section
  - [x] 12.4 : Inline comment dans handleSubmit targets payload
  - [x] 12.5 : Inline comment dans useEffect load

## Dev Notes

### Contexte architectural

**Référence** : docs/inventaire-multi-tables-ux-cibles.md §7, docs/rbac-filter-by-attribute.md, Stories 23.1-23.6 (done), Epic 23

**Architecture RBAC filter_by_attribute (Story 23.4 done)** :
- Backend : ProfileTargetPermission.filter_by_attribute_json (CLOB) stocke `{ "engine_type": ["oracle"] }`
- Backend : InventoryService.list_targets_for_user applique filtres par attribut après LIST/PATTERN/ALL
- Backend : ProfileTargetPermissionsSerializer valide keys contre InventoryMapper.get_available_concepts('servers')
- API : PUT /admin/profiles/{id}/targets accepte `filter_by_attribute: { "engine_type": ["oracle"] }` (Story 23.4)
- Logique filtrage : Dans un profil AND (toutes conditions), entre profils OR (union)

**ProfileForm actuel (Stories 2.9-2.11, 2.25)** :
- Modal création/édition profil avec 3 sections : Informations de base, Actions autorisées, Targets autorisés
- Targets section : Radio.Group avec `targets_type` (all/list/pattern), champs conditionnels target_names/target_patterns
- Pas de support filter_by_attribute actuellement → **Story 23.7 ajoute cette fonctionnalité**
- Chargement initial : getProfileTargets → setFieldsValue(targets_type, target_names, target_patterns)
- Submit : putProfileTargets(editProfile.id, { targets_type, target_names, target_patterns })

**Flow actuel (avant Story 23.7)** :
1. Admin ouvre profil en édition
2. ProfileForm charge getProfileTargets → `{ targets_type: 'all', target_names: [], target_patterns: [], filter_by_attribute: null }`
3. Interface affiche Radio "Tous les serveurs" sélectionné
4. Admin peut changer vers "Liste" ou "Pattern" pour restreindre
5. Submit → putProfileTargets avec targets_type + target_names/pattern_names

**Flow cible (après Story 23.7)** :
1. Admin ouvre profil en édition
2. ProfileForm charge getProfileTargets → `{ targets_type: 'all', filter_by_attribute: { engine_type: ['oracle'] } }`
3. detectTargetsMode → return 'all-oracle'
4. Interface affiche Radio "Tous les serveurs Oracle" sélectionné + Alert info
5. Admin peut changer vers "Tous les serveurs SQL", "Liste", etc.
6. Submit → putProfileTargets avec targets_type='all' + filter_by_attribute={ engine_type: ['sqlserver'] }

### Fichiers à modifier

**Modifier** :
- `frontend/src/types/api.ts` : Étendre ProfileTargetPermissionsUpdate avec filter_by_attribute
- `frontend/src/components/admin/ProfileForm.tsx` : Ajouter Radio.Group avec 5 options, detectTargetsMode helper, targetsMode state, Alerts info, payload calculation
- `frontend/src/components/admin/ProfileForm.tsx` (interface ProfileFormValues) : Ajouter filter_by_attribute field

**Créer/Modifier tests** :
- `frontend/src/components/admin/__tests__/ProfileForm.test.tsx` : +9 tests Story 23.7 (sélection options, chargement, submit, edge cases)
- `frontend/src/components/admin/__tests__/ProfileForm.integration.test.tsx` : +4 tests Story 23.7 (création, édition, changement mode)
- `frontend/src/components/admin/__tests__/detectTargetsMode.test.ts` : +6 tests helper (all, oracle, sql, list, pattern, advanced)

### Patterns de code

**Type extension ProfileTargetPermissionsUpdate** :
```typescript
// frontend/src/types/api.ts
export interface ProfileTargetPermissionsUpdate {
  targets_type: ProfileTargetsType; // 'all' | 'list' | 'pattern'
  target_names: string[];
  target_patterns: string[];
  // Story 23.7 - Filter targets by inventory attributes (e.g., engine_type)
  filter_by_attribute?: Record<string, string[]> | null;
}
```

**Helper detectTargetsMode** :
```typescript
// frontend/src/components/admin/ProfileForm.tsx (ou utils/)
type TargetsMode = 'all' | 'all-oracle' | 'all-sql' | 'list' | 'pattern' | 'advanced';

interface ProfileTargetPermissionsResponse {
  targets_type: ProfileTargetsType;
  target_names: string[];
  target_patterns: string[];
  filter_by_attribute?: Record<string, string[]> | null;
}

/**
 * Story 23.7 - Detect targets mode from profile target permissions response.
 * Returns 'all-oracle', 'all-sql' for engine-specific filters, 'advanced' for unsupported filters.
 */
function detectTargetsMode(targetsPerms: ProfileTargetPermissionsResponse): TargetsMode {
  const { targets_type, filter_by_attribute } = targetsPerms;

  // Explicit LIST or PATTERN
  if (targets_type === 'list') return 'list';
  if (targets_type === 'pattern') return 'pattern';

  // ALL without filter
  if (targets_type === 'all' && !filter_by_attribute) return 'all';

  // ALL with filter_by_attribute
  if (targets_type === 'all' && filter_by_attribute) {
    const keys = Object.keys(filter_by_attribute);

    // Exactly one key: engine_type
    if (keys.length === 1 && keys[0] === 'engine_type') {
      const engineValues = filter_by_attribute.engine_type;

      // Exactly one value: oracle
      if (engineValues.length === 1) {
        const engineType = engineValues[0].toLowerCase();
        if (engineType === 'oracle') return 'all-oracle';
        if (engineType === 'sqlserver' || engineType === 'sql') return 'all-sql';
      }
    }

    // Unsupported filter structure (multi-keys, multi-values, unknown values)
    return 'advanced';
  }

  // Fallback
  return 'all';
}
```

**ProfileForm Radio.Group avec 5 options** :
```tsx
// frontend/src/components/admin/ProfileForm.tsx
import { Radio, Alert } from 'antd';
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';

export function ProfileForm({ ... }) {
  const [form] = Form.useForm<ProfileFormValues>();
  const [targetsMode, setTargetsMode] = useState<TargetsMode>('all');

  // Story 23.7 - Detect mode from loaded profile
  useEffect(() => {
    if (!open) return;
    // ... existing code ...
    if (editProfile) {
      Promise.all([getProfileActions(...), getProfileTargets(editProfile.id), ...])
        .then(([perms, targetsPerms, ...]) => {
          const mode = detectTargetsMode(targetsPerms);
          setTargetsMode(mode);
          form.setFieldsValue({
            // ... existing fields ...
            targets_type: targetsPerms.targets_type,
            target_names: targetsPerms.target_names ?? [],
            target_patterns: targetsPerms.target_patterns ?? [],
            // Note: filter_by_attribute not stored in form (calculated from mode)
          });
        });
    } else {
      setTargetsMode('all'); // Default for new profile
    }
  }, [open, editProfile, form]);

  const handleTargetsModeChange = (e: RadioChangeEvent) => {
    const newMode = e.target.value as TargetsMode;
    setTargetsMode(newMode);

    // Clear target_names and target_patterns when switching to ALL modes
    if (newMode === 'all' || newMode === 'all-oracle' || newMode === 'all-sql') {
      form.setFieldsValue({ target_names: [], target_patterns: [] });
    }
  };

  // Story 23.7 - Compute filter_by_attribute from targetsMode
  const getFilterByAttribute = (mode: TargetsMode): Record<string, string[]> | null => {
    if (mode === 'all-oracle') return { engine_type: ['oracle'] };
    if (mode === 'all-sql') return { engine_type: ['sqlserver'] };
    return null; // all, list, pattern, advanced
  };

  const getTargetsTypeFromMode = (mode: TargetsMode): ProfileTargetsType => {
    if (mode === 'list') return 'list';
    if (mode === 'pattern') return 'pattern';
    return 'all'; // all, all-oracle, all-sql
  };

  const handleSubmit = async () => {
    // ... existing code ...
    if (isEdit && editProfile) {
      // ... actions payload ...

      // Story 23.7 - Include filter_by_attribute for engine-based filtering
      const tt = getTargetsTypeFromMode(targetsMode);
      const targetsPayload: ProfileTargetPermissionsUpdate = {
        targets_type: tt,
        target_names: tt === 'list' ? (values.target_names ?? []) : [],
        target_patterns: tt === 'pattern' ? (values.target_patterns ?? []) : [],
        filter_by_attribute: getFilterByAttribute(targetsMode),
      };

      try {
        await Promise.all([
          putProfileActions(...),
          putProfileTargets(editProfile.id, targetsPayload),
        ]);
      } catch {
        // ... existing error handling ...
      }
    }
    // ...
  };

  return (
    <Modal ...>
      {/* ... existing fields ... */}

      {/* Story 23.7 - Section Targets autorisés avec filter by engine type */}
      {isEdit && (
        <>
          <div style={{ marginTop: 24, marginBottom: 8 }}>
            <strong>Targets autorisés</strong>
          </div>

          <Radio.Group
            value={targetsMode}
            onChange={handleTargetsModeChange}
            style={{ width: '100%', marginBottom: 16 }}
            direction="vertical"
          >
            <Radio value="all" style={{ display: 'block', marginBottom: 8 }}>
              Tous les serveurs
            </Radio>
            <Radio value="all-oracle" style={{ display: 'block', marginBottom: 8 }}>
              Tous les serveurs Oracle
            </Radio>
            <Radio value="all-sql" style={{ display: 'block', marginBottom: 8 }}>
              Tous les serveurs SQL
            </Radio>
            <Radio value="list" style={{ display: 'block', marginBottom: 8 }}>
              Liste de serveurs spécifiques
            </Radio>
            <Radio value="pattern" style={{ display: 'block', marginBottom: 8 }}>
              Pattern de serveurs (wildcard)
            </Radio>
          </Radio.Group>

          {/* Story 23.7 - Alerts informatifs selon mode */}
          {targetsMode === 'all' && (
            <Alert
              type="info"
              showIcon
              icon={<CheckCircleOutlined />}
              closable={false}
              message="✓ Accès complet à tous les serveurs (tous types, tous environnements)"
              style={{ marginBottom: 16 }}
            />
          )}
          {targetsMode === 'all-oracle' && (
            <Alert
              type="info"
              showIcon
              icon={<CheckCircleOutlined />}
              closable={false}
              message="✓ Accès à tous les serveurs Oracle (tous environnements)"
              style={{ marginBottom: 16 }}
            />
          )}
          {targetsMode === 'all-sql' && (
            <Alert
              type="info"
              showIcon
              icon={<CheckCircleOutlined />}
              closable={false}
              message="✓ Accès à tous les serveurs SQL (tous environnements)"
              style={{ marginBottom: 16 }}
            />
          )}
          {targetsMode === 'advanced' && (
            <Alert
              type="warning"
              showIcon
              icon={<WarningOutlined />}
              closable={false}
              message="Ce profil utilise des filtres avancés non supportés par l'interface. L'édition réinitialisera ces filtres."
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Story 2.11 - Champs target_names/target_patterns conditionnels */}
          {targetsMode === 'list' && (
            <Form.Item
              name="target_names"
              label="Serveurs autorisés"
              rules={[{ required: true, message: 'Au moins un serveur requis' }]}
            >
              <Select mode="multiple" placeholder="Sélectionnez les serveurs">
                {MOCK_TARGET_OPTIONS.map((target) => (
                  <Select.Option key={target} value={target}>
                    {target}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {targetsMode === 'pattern' && (
            <Form.Item
              name="target_patterns"
              label="Patterns de serveurs"
              rules={[{ required: true, message: 'Au moins un pattern requis' }]}
            >
              <Select mode="tags" placeholder="ex. srv-*-prod, db-oracle-*">
                {/* Tags mode allows free input */}
              </Select>
            </Form.Item>
          )}
        </>
      )}
    </Modal>
  );
}
```

**Tests ProfileForm sélection Oracle** :
```typescript
// frontend/src/components/admin/__tests__/ProfileForm.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ProfileForm } from '../ProfileForm';
import * as profilesService from '../../../services/profiles_service';
import * as adminService from '../../../services/admin_service';

vi.mock('../../../services/profiles_service');
vi.mock('../../../services/admin_service');

describe('ProfileForm - Story 23.7', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sélection "Tous les serveurs Oracle" crée filter_by_attribute', async () => {
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Test Profile',
      ad_group: 'test-group',
      is_admin: false,
      is_auditor: false,
    };

    vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: [],
    });
    vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: null,
    });
    vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
    vi.spyOn(adminService, 'getTags').mockResolvedValue([]);
    vi.spyOn(profilesService, 'putProfileTargets').mockResolvedValue();

    const onSubmit = vi.fn().mockResolvedValue(editProfile);
    const onSuccess = vi.fn();

    const { container } = render(
      <ProfileForm
        open={true}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
        editProfile={editProfile}
        onSuccess={onSuccess}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Tous les serveurs Oracle/i)).toBeInTheDocument();
    });

    // Sélectionner "Tous les serveurs Oracle"
    const oracleRadio = screen.getByLabelText(/Tous les serveurs Oracle/i);
    fireEvent.click(oracleRadio);

    // Vérifier Alert info affiché
    expect(screen.getByText(/Accès à tous les serveurs Oracle/i)).toBeInTheDocument();

    // Submit
    const okButton = screen.getByText('Enregistrer');
    fireEvent.click(okButton);

    await waitFor(() => {
      expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { engine_type: ['oracle'] },
      });
    });
  });

  it('chargement profil avec filter_by_attribute Oracle pré-sélectionne option', async () => {
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Oracle Profile',
      ad_group: 'oracle-dba',
      is_admin: false,
      is_auditor: false,
    };

    vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: [],
    });
    vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['oracle'] }, // Oracle filter
    });
    vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
    vi.spyOn(adminService, 'getTags').mockResolvedValue([]);

    render(
      <ProfileForm
        open={true}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
        editProfile={editProfile}
      />
    );

    await waitFor(() => {
      const oracleRadio = screen.getByLabelText(/Tous les serveurs Oracle/i) as HTMLInputElement;
      expect(oracleRadio.checked).toBe(true);
    });

    // Vérifier Alert info Oracle affiché
    expect(screen.getByText(/Accès à tous les serveurs Oracle/i)).toBeInTheDocument();
  });

  it('chargement profil avec filter_by_attribute avancé affiche Warning', async () => {
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Advanced Profile',
      ad_group: 'advanced-group',
      is_admin: false,
      is_auditor: false,
    };

    vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: [],
    });
    vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { zone: ['prod'], engine_type: ['oracle'] }, // Multi-keys (advanced)
    });
    vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
    vi.spyOn(adminService, 'getTags').mockResolvedValue([]);

    render(
      <ProfileForm
        open={true}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
        editProfile={editProfile}
      />
    );

    await waitFor(() => {
      // Fallback to "Tous les serveurs"
      const allRadio = screen.getByLabelText(/^Tous les serveurs$/i) as HTMLInputElement;
      expect(allRadio.checked).toBe(true);
    });

    // Vérifier Warning affiché
    expect(screen.getByText(/utilise des filtres avancés non supportés/i)).toBeInTheDocument();
  });
});
```

### Standards de tests

**Référence** : Stories 23.1-23.6 (69+43+57+53+94+101 tests), Story 2.25 (ProfileForm wizard)

**Couverture requise** :
- Tests unitaires detectTargetsMode : all, oracle, sql, list, pattern, advanced (6 tests)
- Tests unitaires ProfileForm : sélection options, chargement, Alerts, edge cases (9 tests)
- Tests intégration ProfileForm : création, édition, changement mode, API calls (4 tests)
- Coverage ≥ 85% pour ProfileForm.tsx modifié

**Assertions clés** :
- Vérifier targetsMode détecté correctement depuis filter_by_attribute
- Vérifier Radio.Group affiche 5 options (all, all-oracle, all-sql, list, pattern)
- Vérifier Alert info affiché pour all/oracle/sql, Warning pour advanced
- Vérifier champs target_names/target_patterns cachés/visibles selon mode
- Vérifier payload putProfileTargets avec filter_by_attribute correct
- Vérifier rétrocompatibilité : profils existants LIST/PATTERN inchangés

**Pattern tests React** :
```typescript
// Vérifier Radio option sélectionnée
const oracleRadio = screen.getByLabelText(/Tous les serveurs Oracle/i) as HTMLInputElement;
expect(oracleRadio.checked).toBe(true);

// Vérifier Alert affiché
expect(screen.getByText(/Accès à tous les serveurs Oracle/i)).toBeInTheDocument();

// Vérifier champ caché
expect(screen.queryByLabelText(/Serveurs autorisés/i)).not.toBeInTheDocument();

// Vérifier API call
expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
  targets_type: 'all',
  filter_by_attribute: { engine_type: ['oracle'] },
  // ...
});
```

### Dépendances et ordre

**Dépend de** :
- Story 23.4 (done) : Backend RBAC filter_by_attribute, ProfileTargetPermissionsSerializer validation
- Story 23.6 (done) : useTargetInventory avec selectedServerNames (pas de dépendance directe mais contexte Epic 23)
- Story 2.25 (done) : ProfileForm wizard avec sections Actions + Targets

**Bloque** :
- Aucune story en attente (Story 23.7 est la dernière de l'Epic 23 selon docs/inventaire-multi-tables-ux-cibles.md)

**N'affecte PAS** :
- Backend : Aucune modification backend requise (Story 23.4 a déjà implémenté validation filter_by_attribute)
- Profils existants avec targets_type='list' ou 'pattern' : comportement inchangé (rétrocompatibilité)
- InventoryService.list_targets_for_user : déjà implémenté avec support filter_by_attribute (Story 23.4)

### Risques et mitigations

**Risque** : Profil existant avec filter_by_attribute complexe (multi-keys, multi-values) non supporté par l'UI → édition casse le profil
**Mitigation** : detectTargetsMode détecte 'advanced' et affiche Warning AC8, empêchant édition accidentelle (ou fallback vers 'all' avec Warning explicite)

**Risque** : Backend validation échoue si filter_by_attribute envoyé avec clé invalide (ex. 'zone' pas dans concepts inventaire)
**Mitigation** : Frontend limite aux clés supportées (engine_type uniquement pour oracle/sql), backend validation Story 23.4 retourne erreur 400 avec message clair

**Risque** : Utilisateur sélectionne "Tous Oracle" mais aucun serveur Oracle en inventaire → profil vide d'effet
**Mitigation** : Pas d'erreur (comportement attendu), list_targets_for_user retournera liste vide si aucun serveur Oracle (backend applique filtre correctement)

**Risque** : Confusion entre "Tous les serveurs" et "Tous les serveurs Oracle" (noms similaires)
**Mitigation** : Alerts info AC7 renforcent distinction visuelle, icônes CheckCircleOutlined, messages explicites "tous types" vs "Oracle uniquement"

**Risque** : Rétrocompatibilité cassée si ancien profil avait filter_by_attribute=null (pas encore sauvegardé avec nouveau format)
**Mitigation** : detectTargetsMode gère null correctement (return 'all'), ProfileTargetPermissionsSerializer accepte null (supprime filtre), tests AC5 couvrent ce cas

### Intelligence des Stories 23.1-23.6 et 23.4

**Story 23.4 (done)** :
- Backend ProfileTargetPermission.filter_by_attribute_json (CLOB)
- ProfileTargetPermissionsSerializer.validate_filter_by_attribute() valide keys contre concepts inventaire
- InventoryService._apply_attribute_filter applique filtres dans list_targets_for_user
- 53 tests passent, validation sécurité + graceful degradation
- **Clés supportées** : Tous concepts retournés par InventoryMapper.get_available_concepts('servers') (engine_type, zone, etc.)
- **UI Story 23.7 limite à** : engine_type uniquement (oracle/sqlserver) pour simplification

**Story 23.6 (done)** :
- Frontend useTargetInventory avec selectedServerNames
- ExecutionWizard calcule selectedServerNames depuis effectiveTargetNames
- renderFieldInput affiche Alert info si selectedServerNames vide pour instances/databases
- 101 tests passent (41 Story 23.6 + 60 existants)
- **Pattern réutilisable** : Alert info Ant Design, CheckCircleOutlined, showIcon, closable={false}

**Patterns à réutiliser** :
- Alert Ant Design avec CheckCircleOutlined (Story 23.6, 2-17, 2-18)
- detectHelper function pattern (Story 23.6 detectTargetsMode similaire)
- Radio.Group avec direction="vertical" (Story 4-1, 11-3)
- Form.Item avec rules validation (ProfileForm existant)
- Tests React Testing Library avec waitFor + fireEvent (Story 23.6, 22-8)

### Commits récents pertinents Epic 23

**Référence** : `git log --oneline -5`

- `f05a927 feat(23-6): implement server-aware inventory filtering for instances and databases` — Story 23.6, 101 tests
- `4420133 feat(23-5): code review fixes - French accents, type consolidation, validation docs` — Story 23.5, 94 tests
- `bd33797 feat(23-4): implement RBAC profile filtering by inventory attributes` — Story 23.4, 53 tests
- `a840414 feat(23-3): implement multi-table inventory API endpoints` — Story 23.3, 57 tests
- `6f61d93 feat(23-2): add multi-table inventory service methods` — Story 23.2, 43 tests

**Code patterns récents Epic 23** :
- Backend filter_by_attribute validation : `concepts = InventoryMapper.get_available_concepts('servers'); invalid_keys = set(data.keys()) - set(concepts)` (Story 23.4)
- Frontend Radio.Group : `<Radio.Group value={mode} onChange={handleChange} direction="vertical">` (Story 11-3, 4-1)
- Alert info : `<Alert type="info" showIcon icon={<CheckCircleOutlined />} closable={false} message="..." />` (Story 23.6)
- Form conditional rendering : `{mode === 'list' && <Form.Item name="..." />}` (ProfileForm existant)
- Tests API mock : `vi.spyOn(service, 'method').mockResolvedValue({ ... })` (Story 23.6, 22-8)

### Architecture Frontend (référence)

**Fichier** : docs/architecture.md §Frontend, ProfileForm (Story 2.25)

**ProfileForm flow (Story 2.25)** :
```
ProfileForm.tsx (Modal)
├── Section 1: Informations de base (name, description, ad_group, is_admin, is_auditor)
├── Section 2: Actions autorisées (isEdit only)
│   ├── Radio.Group: actions_type (all, list, pattern)
│   ├── Conditional: action_ids (Select multiple si list)
│   ├── Conditional: tag_patterns (Select tags si pattern)
│   └── environments (Select multiple avec useEnvironments)
├── Section 3: Targets autorisés (isEdit only) ⭐ Story 23.7
│   ├── Radio.Group: targetsMode (all, all-oracle, all-sql, list, pattern)
│   ├── Conditional: Alert info (si all/oracle/sql)
│   ├── Conditional: Alert warning (si advanced)
│   ├── Conditional: target_names (Select multiple si list)
│   └── Conditional: target_patterns (Select tags si pattern)
└── Submit: onSubmit → putProfileActions + putProfileTargets
```

**Story 23.7 additions** :
- Nouveau helper `detectTargetsMode(targetsPerms) → TargetsMode`
- Nouveau state `targetsMode: TargetsMode`
- Radio.Group étendu de 3 à 5 options (all, all-oracle, all-sql, list, pattern)
- Alerts info conditionnels selon targetsMode
- Payload calculation `getFilterByAttribute(targetsMode) → { engine_type: [...] } | null`

### Exemples d'utilisation

**Exemple 1 : DBOPS crée profil "Oracle DBAs" avec accès tous serveurs Oracle**

**Flow utilisateur** :
1. **Admin page** : Clic "Nouveau profil"
2. **Section 1** : Remplir name="Oracle DBAs", ad_group="oracle-dba-group", is_admin=false
3. **Clic "Créer"** : Profil créé avec targets par défaut (all, filter_by_attribute=null)
4. **Admin page** : Clic "Éditer" sur profil "Oracle DBAs"
5. **Section 3 (Targets)** : Sélectionner Radio "Tous les serveurs Oracle"
6. **Alert info** : "✓ Accès à tous les serveurs Oracle (tous environnements)"
7. **Clic "Enregistrer"** : putProfileTargets({ targets_type: 'all', filter_by_attribute: { engine_type: ['oracle'] } })
8. **Backend** : InventoryService.list_targets_for_user filtre serveurs où engine_type='oracle'

**Résultat** : Utilisateurs du groupe AD oracle-dba-group voient seulement serveurs Oracle (dev, staging, prod) dans leur catalogue et wizard d'exécution.

**Exemple 2 : DBOPS modifie profil existant "SQL Admins" de Liste vers Tous SQL**

**État initial** :
- Profil "SQL Admins" avec targets_type='list', target_names=['srv-sql-01', 'srv-sql-02', 'srv-sql-03']

**Flow utilisateur** :
1. **Admin page** : Clic "Éditer" sur profil "SQL Admins"
2. **Section 3 (Targets)** : Radio "Liste de serveurs spécifiques" pré-sélectionné
3. **Champs** : Select target_names affiche srv-sql-01, srv-sql-02, srv-sql-03
4. **Changement** : Sélectionner Radio "Tous les serveurs SQL"
5. **Champs** : Select target_names disparaît
6. **Alert info** : "✓ Accès à tous les serveurs SQL (tous environnements)"
7. **Clic "Enregistrer"** : putProfileTargets({ targets_type: 'all', target_names: [], filter_by_attribute: { engine_type: ['sqlserver'] } })
8. **Backend** : list_targets_for_user filtre serveurs où engine_type='sqlserver' (ou 'sql')

**Résultat** : Utilisateurs voient maintenant TOUS les serveurs SQL (y compris nouveaux serveurs ajoutés après), pas seulement les 3 listés.

**Exemple 3 : DBOPS charge profil avec filter_by_attribute avancé (multi-keys)**

**État initial** :
- Profil "Prod Oracle Zone A" avec filter_by_attribute = { "engine_type": ["oracle"], "zone": ["zone-a"] }

**Flow utilisateur** :
1. **Admin page** : Clic "Éditer" sur profil "Prod Oracle Zone A"
2. **ProfileForm load** : getProfileTargets → filter_by_attribute avec 2 clés (engine_type + zone)
3. **detectTargetsMode** : Détecte 'advanced' (multi-keys non supporté par UI)
4. **Interface** : Radio "Tous les serveurs" pré-sélectionné (fallback)
5. **Alert Warning** : "Ce profil utilise des filtres avancés non supportés par l'interface. L'édition réinitialisera ces filtres."
6. **Option 1** : Admin annule sans sauvegarder (filtres avancés préservés)
7. **Option 2** : Admin sélectionne "Tous les serveurs Oracle" et sauvegarde → filter_by_attribute devient { engine_type: ['oracle'] } (zone perdue)

**Résultat** : UI protège contre édition accidentelle de filtres complexes avec Warning explicite.

**Exemple 4 : Utilisateur avec plusieurs profils (Oracle + Liste spécifique)**

**Configuration** :
- Profil A "Oracle DBAs" : filter_by_attribute = { engine_type: ['oracle'] }
- Profil B "Prod Servers" : targets_type='list', target_names=['srv-prod-01', 'srv-prod-02'] (SQL servers)

**Flow backend (list_targets_for_user)** :
1. Charger profils utilisateur : [Profil A, Profil B]
2. Profil A : Charger tous serveurs Oracle depuis inventaire → [srv-oracle-01, srv-oracle-02, ...]
3. Profil A : Appliquer filter_by_attribute → filtrer engine_type='oracle'
4. Profil B : Charger serveurs par liste → [srv-prod-01, srv-prod-02]
5. Union OR : serveurs finaux = Oracle servers ∪ [srv-prod-01, srv-prod-02]
6. Utilisateur voit : tous serveurs Oracle + srv-prod-01 et srv-prod-02 (même si SQL)

**Résultat** : filter_by_attribute (Profil A) et liste explicite (Profil B) sont cumulatifs (OR entre profils).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- TypeScript compilation: 0 errors after type changes
- detectTargetsMode tests: 15/15 pass (12 initial + 3 edge cases from code review)
- ProfileForm tests: 33/33 pass (14 existing + 19 new Story 23.7)
- Total tests: 48/48 pass
- Code review fixes: Alert API deprecated → title prop, edge cases coverage, inline comments AC10

### Completion Notes List

- Task 1: Extended `ProfileTargetPermissionsUpdate` and `ProfileTargetPermissionsResponse` with `filter_by_attribute?: Record<string, string[]> | null` and JSDoc
- Task 2: Created `detectTargetsMode` helper with case-insensitive engine_type detection and 'advanced' fallback for unsupported filters. 15 unit tests (12 initial + 3 edge cases: empty object, 'sql' engine, undefined array).
- Tasks 3-5: Replaced old 3-option Radio.Group (list/pattern/all) with 5-option Radio.Group (all/all-oracle/all-sql/list/pattern). Added conditional Alerts (info for all/oracle/sql, warning for advanced). Vertical layout with flexbox.
- Task 6: `getFilterByAttribute(mode)` and `getTargetsTypeFromMode(mode)` compute payload from UI state. Submit includes `filter_by_attribute` in putProfileTargets call.
- Task 7: `detectTargetsMode` called in useEffect after `getProfileTargets`. Pre-selects correct radio based on stored filter_by_attribute. Default 'all' for new profiles. Inline comment added per AC10.
- Task 8: Advanced filter detection covers multi-keys, multi-values, unknown engine values, unsupported keys, empty object. Warning Alert displayed.
- Task 9: Backend errors caught via existing try/catch + setPermError. Compatible with Story 23.4 ProfileTargetPermissionsSerializer.
- Tasks 10-11: 19 new ProfileForm tests covering all ACs: selection, pre-selection on load, submit payloads, mode transitions, edge cases, error handling.
- Task 12: JSDoc and inline comments added per AC10 requirements (Radio.Group section, useEffect load).
- **Architecture decision**: `filter_by_attribute` is NOT stored in form values — it's computed from `targetsMode` state via `getFilterByAttribute()`. This avoids form state complexity and ensures consistency.
- **Code review fixes (2026-02-09)**:
  - Fixed Alert API: replaced deprecated `message` prop with `title` (Ant Design 5.x)
  - Added inline comments per AC10: Radio.Group section, useEffect load
  - Enhanced `detectTargetsMode`: empty object edge case, undefined engine_type array protection
  - Added 3 edge case tests: empty filter_by_attribute={}, 'sql' engine_type, undefined array

### Change Log

- 2026-02-09: Story 23.7 implementation complete — 48 tests pass (15 detectTargetsMode + 33 ProfileForm)
- 2026-02-09: Code review fixes applied — Alert API updated, AC10 comments complete, edge cases covered

### File List

- `idp-portal/frontend/src/types/api/profiles.ts` — Modified: added `filter_by_attribute` to `ProfileTargetPermissionsUpdate` and `ProfileTargetPermissionsResponse`
- `idp-portal/frontend/src/components/admin/ProfileForm.tsx` — Modified: added `detectTargetsMode` helper, `TargetsMode` type, 5-option Radio.Group, conditional Alerts, payload computation with `filter_by_attribute`, initial load detection
- `idp-portal/frontend/src/components/admin/ProfileForm.test.tsx` — Modified: updated existing test assertions for new 5-option layout, added 19 Story 23.7 tests
- `idp-portal/frontend/src/components/admin/__tests__/detectTargetsMode.test.ts` — Created: 12 unit tests for detectTargetsMode helper
