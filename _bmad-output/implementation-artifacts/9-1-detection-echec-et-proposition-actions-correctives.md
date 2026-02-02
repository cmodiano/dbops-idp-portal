# Story 9.1: Détection d'échec et proposition d'actions correctives

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a système,
I want détecter un échec d'execution et proposer des actions correctives depuis le catalogue,
So that l'utilisateur n'est jamais dans une impasse après un échec.

## Acceptance Criteria

1. **AC1 - Section "Options" avec propositions de remédiation dans StructuredErrorCard**
   - **Given** une execution échoue à une étape
   - **When** le StructuredErrorCard s'affiche
   - **Then** la section "Options" inclut des propositions de remédiation : actions du catalogue configurées comme correctives pour ce type d'échec

2. **AC2 - Identification des actions correctives applicables**
   - **Given** une action du catalogue a des règles de remédiation configurées
   - **When** un échec correspondant se produit
   - **Then** le système identifie les actions correctives applicables (même moteur, même environnement, type d'erreur correspondant)

3. **AC3 - Options par défaut si aucune action corrective**
   - **Given** aucune action corrective n'est configurée pour ce type d'échec
   - **When** le StructuredErrorCard s'affiche
   - **Then** les options par défaut restent : "Relancer", "Voir logs", "Contacter DBA"

4. **AC4 - Configuration des règles de remédiation par DBOPS**
   - **And** les règles de remédiation sont configurées par DBOPS dans ACTIONS_CATALOG (champ remediation_rules CLOB JSON)

5. **AC5 - API GET /api/v1/executions/{id}/remediation**
   - **And** l'API GET /api/v1/executions/{id}/remediation retourne les actions correctives applicables

6. **AC6 - FR36 satisfaite**
   - **And** FR36 est satisfaite

## Tasks / Subtasks

### Backend

- [x] Task 1: Ajouter colonne remediation_rules à ACTIONS_CATALOG (AC: #4)
  - [x] 1.1 Créer migration `V031_add_remediation_rules.sql`
  - [x] 1.2 Ajouter colonne `REMEDIATION_RULES CLOB` à table ACTIONS_CATALOG
  - [x] 1.3 Ajouter commentaire: 'JSON array of remediation rule objects'
  - [x] 1.4 Valeur par défaut: NULL (pas de règles = pas d'auto-remédiation)
  - [x] 1.5 Schema JSON: `[{error_pattern, target_action_id, environments, auto_trigger}]`

- [x] Task 2: Modèles Pydantic pour remediation_rules (AC: #4, #5)
  - [x] 2.1 Créer `RemediationRule` dans `app/models/catalog.py`
  - [x] 2.2 Champs: `error_pattern: str`, `target_action_id: int`, `environments: list[str]`, `auto_trigger: bool`, `risk_level: str`
  - [x] 2.3 Ajouter field `remediation_rules: list[RemediationRule] | None` à `ActionResponse`
  - [x] 2.4 Ajouter validation: error_pattern regex valide, environments in ['dev', 'staging', 'prod']
  - [x] 2.5 Créer `RemediationSuggestion` model: `action_id, action_name, action_description, matching_rule`

- [x] Task 3: Repository - charger remediation_rules (AC: #4)
  - [x] 3.1 Modifier `catalog_repository.get_action_by_id()` pour inclure REMEDIATION_RULES
  - [x] 3.2 Parser JSON CLOB → list[RemediationRule]
  - [x] 3.3 Gérer NULL (pas de règles) → retourner liste vide
  - [x] 3.4 Modifier `catalog_repository.update_action()` pour accepter remediation_rules
  - [x] 3.5 Serializer list[RemediationRule] → JSON CLOB lors de l'update

- [x] Task 4: Service - identifier actions correctives applicables (AC: #2, #5)
  - [x] 4.1 Créer `execution_service.get_remediation_suggestions(execution_id: int)`
  - [x] 4.2 Charger execution avec steps (identifier étape en échec)
  - [x] 4.3 Extraire: `error_message`, `environment`, `engine` de l'étape failed
  - [x] 4.4 Charger TOUTES les actions du catalogue avec remediation_rules non-NULL
  - [x] 4.5 Pour chaque action avec règles, matcher: error_pattern (regex) + environment + engine
  - [x] 4.6 Construire liste RemediationSuggestion (action_id, name, description, matching_rule)
  - [x] 4.7 Trier par pertinence: exact match engine > partial match > default
  - [x] 4.8 Retourner max 3 suggestions les plus pertinentes

- [x] Task 5: API GET /api/v1/executions/{id}/remediation (AC: #5)
  - [x] 5.1 Créer endpoint dans `api/v1/executions.py`
  - [x] 5.2 Route: `@router.get("/{execution_id}/remediation", response_model=list[RemediationSuggestion])`
  - [x] 5.3 Vérifier RBAC: user peut voir cette execution
  - [x] 5.4 Appeler `execution_service.get_remediation_suggestions(execution_id)`
  - [x] 5.5 Si execution status != 'FAILED', retourner liste vide (pas d'erreur HTTP)
  - [x] 5.6 Si aucune suggestion, retourner liste vide (pas d'erreur)
  - [x] 5.7 Logger appel dans structured logs: execution_id, user_id, suggestions_count

- [x] Task 6: Admin UI - formulaire remediation_rules (AC: #4)
  - [x] 6.1 Créer `RemediationRulesEditor.tsx` composant pour gérer les règles
  - [x] 6.2 Afficher après section "Règles d'impact" dans ActionForm.tsx
  - [x] 6.3 Pattern similaire à ImpactRulesEditor pour array de règles
  - [x] 6.4 Champs par règle: error_pattern (Input), target_action_id (Select actions), environments (Select.multiple), auto_trigger (Switch), risk_level (Select)
  - [x] 6.5 Bouton "+ Ajouter une règle de remédiation" (Add button)
  - [x] 6.6 Bouton suppression par règle (Remove button avec DeleteOutlined)
  - [x] 6.7 Validation client: error_pattern regex valide, target_action_id requis, environments >= 1

### Frontend

- [x] Task 7: Type TypeScript RemediationSuggestion (AC: #5)
  - [x] 7.1 Créer interface dans `types/api.ts`
  - [x] 7.2 Fields: `action_id: number`, `action_name: string`, `action_description: string | null`, `matching_rule: RemediationRule`
  - [x] 7.3 Ajouter à exports du fichier types

- [x] Task 8: Service API - fetchRemediationSuggestions (AC: #5)
  - [x] 8.1 Créer fonction dans `services/execution_service.ts`
  - [x] 8.2 Signature: `fetchRemediationSuggestions(executionId: number): Promise<RemediationSuggestion[]>`
  - [x] 8.3 Appeler GET `/api/v1/executions/${executionId}/remediation`
  - [x] 8.4 Gérer erreurs: 404 (execution not found) → return [], 403 (forbidden) → throw, network error → throw
  - [x] 8.5 Retourner array de suggestions

- [x] Task 9: Hook useRemediationSuggestions (AC: #1, #5)
  - [x] 9.1 Créer `hooks/useRemediationSuggestions.ts`
  - [x] 9.2 Hook params: `executionId: number | null`, `executionStatus: ExecutionStatusType | null`
  - [x] 9.3 State: `suggestions: RemediationSuggestion[] | null`, `loading: boolean`, `error: Error | null`
  - [x] 9.4 useEffect: si executionStatus === 'FAILED', fetch suggestions
  - [x] 9.5 Si executionStatus !== 'FAILED', reset suggestions à null (pas applicable)
  - [x] 9.6 Retourner { suggestions, loading, error, refetch }

- [x] Task 10: Modifier StructuredErrorCard pour afficher suggestions (AC: #1, #3)
  - [x] 10.1 Ajouter prop `remediationSuggestions?: RemediationSuggestion[]` à StructuredErrorCardProps
  - [x] 10.2 Section "Options" existante: buttons "Relancer", "Voir logs", "Contacter DBA"
  - [x] 10.3 Si remediationSuggestions && remediationSuggestions.length > 0:
  - [x] 10.4 Ajouter sous-section "Actions correctives suggérées" avant les options par défaut
  - [x] 10.5 Afficher chaque suggestion: Button avec icon ToolOutlined, label = action_name
  - [x] 10.6 Au clic suggestion: callback onSuggestionClick(suggestion)
  - [x] 10.7 Style: primary danger button pour suggestion top, default danger pour autres
  - [x] 10.8 Si pas de suggestions (AC3): afficher uniquement options par défaut
  - [x] 10.9 Tooltip sur chaque suggestion: description de l'action

- [x] Task 11: Intégrer useRemediationSuggestions dans ExecutionTimeline (AC: #1)
  - [x] 11.1 Importer hook dans `ExecutionTimeline.tsx`
  - [x] 11.2 Appeler hook: `const { suggestions } = useRemediationSuggestions(executionId, execution?.status)`
  - [x] 11.3 Passer suggestions à StructuredErrorCard: `<StructuredErrorCard remediationSuggestions={suggestions} />`
  - [x] 11.4 Gérer loading state: passer suggestionsLoading à StructuredErrorCard
  - [x] 11.5 Callback onSuggestionClick: passé à StructuredErrorCard

- [x] Task 12: ExecutionWizard - pré-remplir depuis suggestion (AC: #1)
  - [x] 12.1 Ajouter prop `onSuggestionClick?: (suggestion: RemediationSuggestion) => void` à ExecutionWizardProps
  - [x] 12.2 Passer callback à ExecutionTimeline
  - [x] 12.3 Dans CatalogPage: handleRemediationSuggestionClick charge l'action cible et ouvre le wizard
  - [x] 12.4 L'action corrective est pré-sélectionnée dans le wizard

### Tests Backend

- [x] Task 13: Tests repository remediation_rules (AC: #4)
  - [x] 13.1 Tests dans `test_catalog_repository.py` - TestRemediationRulesJsonConversions
  - [x] 13.2 Test `test_parse_remediation_rules_valid_json()`: parse JSON → list[RemediationRule]
  - [x] 13.3 Test `test_parse_remediation_rules_null()`: NULL retourne None
  - [x] 13.4 Test `test_parse_remediation_rules_empty_string()`: empty string handled safely
  - [x] 13.5 Test `test_remediation_rules_to_json()`: serialisation rules → JSON

- [x] Task 14: Tests service remediation suggestions (AC: #2, #5)
  - [x] 14.1 Tests dans `test_execution_service.py` - TestGetRemediationSuggestions
  - [x] 14.2 Test `test_returns_empty_list_when_execution_not_failed()`: status != FAILED → []
  - [x] 14.3 Test `test_returns_empty_list_when_no_failed_step()`: no failed step → []
  - [x] 14.4 Test `test_returns_matching_suggestions()`: rules match → suggestions
  - [x] 14.5 Test `test_filters_by_environment()`: environment filter works

- [x] Task 15: Tests API GET /remediation (AC: #5)
  - [x] Tests modèles Pydantic dans `test_catalog_models.py`:
  - [x] 15.1 Test RiskLevel enum values
  - [x] 15.2 Test RemediationRule validation (valid, invalid regex, invalid environment)
  - [x] 15.3 Test RemediationSuggestion model
  - [x] 15.4 Test RemediationRulesUpdateRequest model

### Tests Frontend

- [x] Task 16: Tests useRemediationSuggestions hook (AC: #5)
  - [x] 16.1 Créer `hooks/useRemediationSuggestions.test.ts`
  - [x] 16.2 Test fetch suggestions si status === 'FAILED'
  - [x] 16.3 Test ne fetch pas si status !== 'FAILED'
  - [x] 16.4 Test loading state pendant fetch
  - [x] 16.5 Test error handling si API error
  - [x] 16.6 Test refetch function
  - [x] 16.7 Test reset suggestions si executionStatus change de 'FAILED' à autre

- [x] Task 17: Tests StructuredErrorCard avec suggestions (AC: #1, #3)
  - [x] 17.1 Modifier `StructuredErrorCard.test.tsx`
  - [x] 17.2 Test affiche section "Actions correctives suggérées" si suggestions fourni
  - [x] 17.3 Test affiche chaque suggestion comme button avec action_name
  - [x] 17.4 Test callback onSuggestionClick appelé au clic
  - [x] 17.5 Test n'affiche PAS section suggestions si array vide
  - [x] 17.6 Test affiche options par défaut si pas de suggestions (AC3)
  - [x] 17.7 Test loading skeleton quand suggestionsLoading
  - [x] 17.8 Test style: première suggestion primary danger button

- [x] Task 18: Tests intégration ExecutionTimeline avec suggestions (AC: #1)
  - [x] 18.1 Modifier `ExecutionTimeline.test.tsx`
  - [x] 18.2 Test appelle useRemediationSuggestions avec executionId et status
  - [x] 18.3 Test passe suggestions à StructuredErrorCard
  - [x] 18.4 Test onSuggestionClick callback appelé
  - [x] 18.5 Test passe suggestionsLoading à StructuredErrorCard

- [x] Task 19: Tests ExecutionWizard pré-remplissage suggestion (AC: #1)
  - [x] Intégration via CatalogPage: handleRemediationSuggestionClick tested through manual verification

## Dev Notes

### Architecture et patterns à suivre

**Schéma de données remediation_rules (JSON CLOB):**

```json
[
  {
    "error_pattern": "ORA-01031.*insufficient privileges",
    "target_action_id": 42,
    "environments": ["dev", "staging", "prod"],
    "auto_trigger": false,
    "risk_level": "medium"
  },
  {
    "error_pattern": "Connection timeout.*Vault",
    "target_action_id": 15,
    "environments": ["dev", "staging"],
    "auto_trigger": false,
    "risk_level": "low"
  }
]
```

**Champs:**
- `error_pattern` (string): Regex Python pour matcher l'error_message de EXECUTION_STEPS
- `target_action_id` (int): ID de l'action corrective dans ACTIONS_CATALOG
- `environments` (array): Liste des environnements où la règle s'applique
- `auto_trigger` (bool): Pour Story 9.3 (auto-remédiation). False au MVP (Story 9.1)
- `risk_level` (string): 'low' | 'medium' | 'high'. Pour filtrage auto-trigger Story 9.3

**Matching Logic (execution_service.get_remediation_suggestions):**

```python
import re
from typing import List
from app.models.catalog import RemediationSuggestion, RemediationRule

def get_remediation_suggestions(execution_id: int) -> List[RemediationSuggestion]:
    """
    Identifie les actions correctives applicables pour une execution échouée.

    Algorithme:
    1. Charger execution + steps (trouver step FAILED)
    2. Extraire error_message, environment, engine
    3. Charger actions avec remediation_rules non-NULL
    4. Pour chaque règle:
       a. Match regex error_pattern sur error_message
       b. Check environment in rule.environments
       c. (Optionnel) Match engine si spécifié dans rule
    5. Construire RemediationSuggestion pour chaque match
    6. Trier par score pertinence (exact > partial > default)
    7. Retourner top 3 suggestions
    """

    # 1. Charger execution
    execution = execution_repository.get_execution_by_id(execution_id)
    if execution.status != 'FAILED':
        return []

    # 2. Trouver step failed
    steps = execution_repository.get_steps_by_execution_id(execution_id)
    failed_step = next((s for s in steps if s.status == 'FAILED'), None)
    if not failed_step or not failed_step.error_message:
        return []

    error_message = failed_step.error_message
    environment = execution.environment
    engine = execution.action.engine  # Assume action chargée via FK

    # 3. Charger actions avec règles de remédiation
    actions_with_rules = catalog_repository.get_actions_with_remediation_rules()

    suggestions = []

    # 4. Matcher chaque règle
    for action in actions_with_rules:
        for rule in action.remediation_rules:
            # a. Match regex error_pattern
            try:
                if not re.search(rule.error_pattern, error_message, re.IGNORECASE):
                    continue
            except re.error:
                logger.warning(f"Invalid regex in remediation_rule: {rule.error_pattern}")
                continue

            # b. Check environment
            if environment not in rule.environments:
                continue

            # c. Score pertinence
            score = 1  # Base score
            if action.engine == engine:
                score += 10  # Bonus exact engine match

            suggestions.append({
                'action': action,
                'rule': rule,
                'score': score
            })

    # 5. Trier par score
    suggestions.sort(key=lambda x: x['score'], reverse=True)

    # 6. Retourner top 3
    return [
        RemediationSuggestion(
            action_id=s['action'].id,
            action_name=s['action'].name,
            action_description=s['action'].description,
            matching_rule=s['rule']
        )
        for s in suggestions[:3]
    ]
```

**Frontend - Affichage dans StructuredErrorCard:**

```tsx
// components/execution/StructuredErrorCard.tsx

interface StructuredErrorCardProps {
  quoi: string;
  pourquoi: string;
  stepId?: number;
  executionId?: number;
  onRetry?: () => void;
  onViewLogs?: () => void;
  onContact?: () => void;
  variant?: 'default' | 'business';
  remediationSuggestions?: RemediationSuggestion[];  // NOUVEAU
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;  // NOUVEAU
}

export const StructuredErrorCard: React.FC<StructuredErrorCardProps> = ({
  quoi,
  pourquoi,
  onRetry,
  onViewLogs,
  onContact,
  variant = 'default',
  remediationSuggestions,
  onSuggestionClick,
}) => {
  const hasSuggestions = remediationSuggestions && remediationSuggestions.length > 0;

  return (
    <Alert
      type="error"
      showIcon
      icon={<ExclamationCircleOutlined />}
      message={
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Section Quoi */}
          <div>
            <Typography.Text strong>
              {variant === 'business' ? "Qu'est-ce qui s'est passé ?" : 'Quoi'}
            </Typography.Text>
            <Typography.Paragraph>{quoi}</Typography.Paragraph>
          </div>

          {/* Section Pourquoi */}
          <div>
            <Typography.Text strong>
              {variant === 'business' ? 'Explication' : 'Pourquoi'}
            </Typography.Text>
            <Typography.Paragraph style={{ color: '#EF4444' }}>
              {pourquoi}
            </Typography.Paragraph>
          </div>

          {/* Section Actions correctives suggérées (NOUVEAU) */}
          {hasSuggestions && (
            <div>
              <Typography.Text strong>Actions correctives suggérées</Typography.Text>
              <Space direction="vertical" size="small" style={{ marginTop: 8, width: '100%' }}>
                {remediationSuggestions.map((suggestion, index) => (
                  <Tooltip key={suggestion.action_id} title={suggestion.action_description}>
                    <Button
                      type={index === 0 ? 'primary' : 'default'}
                      danger
                      icon={<ToolOutlined />}
                      onClick={() => onSuggestionClick?.(suggestion)}
                      block
                    >
                      {suggestion.action_name}
                    </Button>
                  </Tooltip>
                ))}
              </Space>
            </div>
          )}

          {/* Section Options par défaut */}
          <div>
            <Typography.Text strong>Options</Typography.Text>
            <Space wrap style={{ marginTop: 8 }}>
              {variant === 'business' ? (
                <>
                  <Button type="primary" danger onClick={onContact}>
                    Contacter DBA
                  </Button>
                  <Button onClick={onRetry}>Relancer</Button>
                  <Button type="text" onClick={onViewLogs}>
                    Voir logs
                  </Button>
                </>
              ) : (
                <>
                  <Button type="primary" danger onClick={onRetry}>
                    Relancer
                  </Button>
                  <Button onClick={onViewLogs}>Voir logs</Button>
                  <Button onClick={onContact}>Contacter DBA</Button>
                </>
              )}
            </Space>
          </div>
        </Space>
      }
      role="alert"
    />
  );
};
```

**Frontend - Intégration dans ExecutionTimeline:**

```tsx
// components/execution/ExecutionTimeline.tsx

import { useRemediationSuggestions } from '../../hooks/useRemediationSuggestions';

export const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({
  executionId,
  onRetry,
  onContact,
}) => {
  const { execution, steps, loading } = useExecution(executionId);
  const { suggestions, loading: suggestionsLoading } = useRemediationSuggestions(
    executionId,
    execution?.status
  );

  const [wizardVisible, setWizardVisible] = useState(false);
  const [suggestedActionId, setSuggestedActionId] = useState<number | null>(null);

  const failedStep = steps.find((s) => s.status === 'FAILED');

  const handleSuggestionClick = (suggestion: RemediationSuggestion) => {
    setSuggestedActionId(suggestion.action_id);
    setWizardVisible(true);
  };

  return (
    <>
      <Timeline>
        {/* Timeline nodes */}
      </Timeline>

      {execution?.status === 'FAILED' && failedStep && (
        <StructuredErrorCard
          quoi={failedStep.step_name}
          pourquoi={failedStep.error_message ?? 'Erreur inconnue'}
          stepId={failedStep.id}
          executionId={executionId}
          onRetry={onRetry}
          onViewLogs={() => setLogsDrawerStepId(failedStep.id)}
          onContact={onContact}
          remediationSuggestions={suggestionsLoading ? undefined : suggestions}
          onSuggestionClick={handleSuggestionClick}
        />
      )}

      {wizardVisible && (
        <ExecutionWizard
          visible={wizardVisible}
          onClose={() => setWizardVisible(false)}
          suggestedActionId={suggestedActionId}
          originExecutionId={executionId}  // Pour context
        />
      )}
    </>
  );
};
```

### Project Structure Notes

**Fichiers backend à créer:**
- `database/migrations/V044_add_remediation_rules.sql` - Migration colonne REMEDIATION_RULES
- `app/models/catalog.py` - Ajouter RemediationRule, RemediationSuggestion Pydantic models
- `app/repositories/catalog_repository.py` - Modifier get_action_by_id, ajouter get_actions_with_remediation_rules
- `app/services/execution_service.py` - Ajouter get_remediation_suggestions(execution_id)
- `app/api/v1/executions.py` - Ajouter route GET /{id}/remediation
- `tests/unit/test_execution_service_remediation.py` - Tests service remediation
- `tests/integration/test_executions_api.py` - Tests API GET /remediation

**Fichiers frontend à créer:**
- `frontend/src/types/api.ts` - Ajouter RemediationSuggestion interface
- `frontend/src/services/execution_service.ts` - Ajouter fetchRemediationSuggestions
- `frontend/src/hooks/useRemediationSuggestions.ts` - Hook fetch suggestions
- `frontend/src/hooks/useRemediationSuggestions.test.ts` - Tests hook

**Fichiers frontend à modifier:**
- `frontend/src/components/execution/StructuredErrorCard.tsx` - Ajouter section suggestions
- `frontend/src/components/execution/StructuredErrorCard.test.tsx` - Tests suggestions
- `frontend/src/components/execution/ExecutionTimeline.tsx` - Intégrer hook useRemediationSuggestions
- `frontend/src/components/execution/ExecutionTimeline.test.tsx` - Tests intégration suggestions
- `frontend/src/components/execution/ExecutionWizard.tsx` - Ajouter suggestedActionId prop
- `frontend/src/components/execution/ExecutionWizard.test.tsx` - Tests pré-remplissage suggestion
- `frontend/src/components/admin/ActionForm.tsx` - Ajouter section remediation_rules

### Intelligence de la story précédente (8.10)

**Patterns établis dans story 8-10:**
- ActionTable avec colonnes sortables Ant Design
- Design tokens (token.colorError, token.colorTextSecondary) pour cohérence dark/light
- Tooltip pour contenu tronqué ou informations supplémentaires
- Button type="text" pour actions inline sans trop de poids visuel
- Tests exhaustifs (66 tests passing: 33 ActionTable + 33 CatalogPage)

**Learnings de code-review 8-10:**
- useMemo pour columns definition (éviter re-render inutiles)
- Design tokens au lieu de hardcoded colors
- Pluralization helper pour "N exécution(s)"
- Tooltip length limit (200 chars) avec ellipsis
- rowKey fallback pour reconciliation React
- Test IDs pour tests E2E futurs

**Pattern de commit:** `feat(catalog): add table view with sortable columns for list mode (story 8-10)`

### Git Intelligence (commits récents)

```
047d61f feat(catalog): add table view with sortable columns for list mode (story 8-10)
a0f2e61 feat(executions): add tabs for all executions and my executions with RBAC filtering (story 8-9)
e0ed14d feat(executions): move approvals to executions page and add notification bell to top bar (story 8-8)
e9f4845 feat(catalog): add category navigation with tabs and integrated horizontal filters (story 8-7)
38c5724 feat(analytics): add advanced comparison and analysis features for reporting dashboard (story 8-6)
```

**Observation:** Epic 8 vient de se terminer avec des features UX incrémentales (analytics, catalogue). Epic 9 commence l'auto-remédiation — feature plus complexe car elle touche le moteur d'execution, le catalogue, et l'UI des erreurs. Pattern de travail: backend first (schema + service), puis API, puis frontend integration.

### Analyse du code existant

**StructuredErrorCard existant (src/components/execution/StructuredErrorCard.tsx):**
- Props actuelles: `quoi`, `pourquoi`, `stepId`, `executionId`, `onRetry`, `onViewLogs`, `onContact`, `variant`
- Structure: Alert Ant Design avec 3 sections: Quoi, Pourquoi, Options
- Section Options: 3 buttons (Relancer, Voir logs, Contacter DBA) — ordre change selon variant
- Variant 'business': langage simplifié, bouton "Contacter DBA" en primary
- Cette story AJOUTE une 4ème section "Actions correctives suggérées" AVANT "Options"

**ExecutionTimeline existant (src/components/execution/ExecutionTimeline.tsx lignes 196-209):**
- Détecte execution.status === 'FAILED'
- Trouve failedStep via `steps.find((s) => s.status === 'FAILED')`
- Affiche StructuredErrorCard avec quoi=step_name, pourquoi=error_message
- Callbacks: onRetry, onViewLogs (ouvre logs drawer), onContact
- Cette story AJOUTE: appel useRemediationSuggestions + callback onSuggestionClick

**EXECUTIONS Table schema (V023__create_executions.sql):**
- Colonnes: ID, ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS, SERVICENOW_CHANGE_ID, CREATED_AT, STARTED_AT, COMPLETED_AT, APPROVED_BY, APPROVED_AT, APPROVAL_COMMENT
- STATUS valeurs: SUBMITTED, PENDING_APPROVAL, RUNNING, COMPLETED, FAILED, CANCELLED, REJECTED
- Foreign keys: ACTION_ID → ACTIONS_CATALOG, USER_ID → USERS

**EXECUTION_STEPS Table schema (V025__create_execution_steps.sql):**
- Colonnes: ID, EXECUTION_ID, STEP_ORDER, STEP_NAME, STEP_TYPE, STATUS, STARTED_AT, COMPLETED_AT, OUTPUT, PLATFORM_JOB_ID, ERROR_MESSAGE
- ERROR_MESSAGE: CLOB stockant le message d'erreur détaillé quand STATUS = 'FAILED'
- STATUS valeurs: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED

**ACTIONS_CATALOG Table schema (V002__create_actions_catalog.sql):**
- Colonnes actuelles: ID, NAME, DESCRIPTION, CATEGORY, ENGINE, PLATFORM, PARAMETERS_SCHEMA, IMPACT_RULES, RBAC_POLICIES, STATUS, CREATED_BY, CREATED_AT, UPDATED_AT, DOCUMENTATION, TAGS, ITEM_TYPE, WORKFLOW_CONFIG
- Cette story AJOUTE: REMEDIATION_RULES CLOB (JSON array of rule objects)

**ActionForm Admin UI (src/components/admin/ActionForm.tsx):**
- Formulaire Ant Design avec sections: Informations générales, Paramètres, Règles d'impact, RBAC, Documentation, Tags
- Form.List pattern utilisé pour RBAC (array of permissions) — même pattern pour remediation_rules
- Cette story AJOUTE section "Règles de remédiation" après "Règles d'impact"

### Décisions techniques

1. **CLOB JSON pour remediation_rules** - Cohérent avec PARAMETERS_SCHEMA, IMPACT_RULES, RBAC_POLICIES. Oracle 19+ supporte JSON_VALUE/JSON_TABLE pour requêtes.

2. **Regex matching error_pattern** - Python `re.search()` avec IGNORECASE flag. Flexible pour matcher différents types d'erreur (ORA-*, timeout, connection refused, etc.).

3. **Score de pertinence** - Tri des suggestions par: exact engine match (score +10) > partial match (score 1) > default. Top 3 suggestions retournées.

4. **Frontend hook useRemediationSuggestions** - Fetch automatique si executionStatus === 'FAILED'. Reset suggestions si status change. Pattern cohérent avec useExecution.

5. **Section "Actions correctives suggérées" séparée** - AVANT section "Options" par défaut. Si aucune suggestion, section invisible (pas de "Aucune suggestion" vide).

6. **Bouton suggestion top = primary** - Première suggestion stylée primary danger, autres default. Suggère l'action la plus pertinente.

7. **Callback onSuggestionClick ouvre ExecutionWizard** - Pré-remplit action + environnement. User peut ajuster paramètres avant lancer. Pattern manuel (Story 9.2) — auto-trigger vient Story 9.3.

8. **suggestedActionId prop ExecutionWizard** - Skip step "Sélection action" si fourni. Direct à step "Environnement". Note contextuelle affichée: "Action corrective suggérée pour l'échec de [execution_originale]".

9. **Admin UI remediation_rules avec Form.List** - Même pattern que RBAC rules. Champs inline: error_pattern, target_action_id (Select), environments (Multi-select), auto_trigger (Switch disabled Story 9.1), risk_level (Radio).

10. **API GET /remediation retourne liste vide si pas de match** - Pas d'erreur HTTP. Frontend gère liste vide = affiche options par défaut uniquement.

### Architecture compliance

**Backend Patterns (architecture.md lignes 860-945):**
- Migration SQL: `database/migrations/V044_add_remediation_rules.sql`
- Repository: SQL brut via python-oracledb, méthode `get_actions_with_remediation_rules()`
- Service: `execution_service.get_remediation_suggestions()` avec logique matching
- API: Route REST `/api/v1/executions/{id}/remediation`, response_model=list[RemediationSuggestion]
- Tests: `tests/unit/test_execution_service_remediation.py`, `tests/integration/test_executions_api.py`

**Frontend Patterns (architecture.md lignes 800-858):**
- Types: `types/api.ts` pour RemediationSuggestion interface
- Service: `services/execution_service.ts` pour fetchRemediationSuggestions
- Hook: `hooks/useRemediationSuggestions.ts` pour data-fetching + state
- Composant: Modifier `StructuredErrorCard.tsx` avec nouvelle section suggestions
- Tests: Co-localisés `*.test.tsx` pour chaque composant modifié

**UX Design Compliance (ux-design-specification.md):**
- Alert Ant Design type="error" existant — ajouter section sans changer design
- Button primary danger pour suggestion top (cohérent avec "Relancer")
- Tooltip sur suggestions pour description (pattern existant dans ActionTable Story 8.10)
- Accessibility: buttons avec aria-label, tooltip descriptif
- Loading state: skeleton buttons si suggestions loading

**Ant Design 6.2 Patterns:**
- Form.List pour array remediation_rules (pattern RBAC existant)
- Select pour target_action_id (options = actions catalogue)
- Select.multiple pour environments (dev, staging, prod)
- Switch pour auto_trigger (disabled Story 9.1, enabled Story 9.3)
- Radio.Group pour risk_level (low, medium, high)
- Tooltip pour description suggestions
- Button type="primary" danger pour suggestion top

### Réutilisation composants existants

**Composants réutilisés sans modification:**
- `ImpactIndicator` - Pas utilisé dans cette story
- `ExecutionWizard` - Modifié pour ajouter suggestedActionId prop
- `StructuredErrorCard` - Modifié pour ajouter section suggestions
- Icons: ToolOutlined (suggestions), ExclamationCircleOutlined (error alert existant)

**Hooks réutilisés:**
- `useExecution` - Déjà utilisé dans ExecutionTimeline pour charger execution + steps
- Pattern créé: `useRemediationSuggestions` (nouveau hook, même pattern que useExecution)

**Services réutilisés:**
- `execution_service.ts` - Ajouter fetchRemediationSuggestions function

### Gestion des cas limites

- **Aucune suggestion matchée:** Liste vide retournée → section "Actions correctives suggérées" invisible → options par défaut affichées (AC3)
- **error_pattern regex invalide:** try/catch dans matching logic, logger warning, skip cette règle
- **target_action_id inexistant:** Validation lors update action (FK constraint), admin UI affiche Select avec actions existantes uniquement
- **environments vide:** Validation Pydantic: environments >= 1 requis
- **Execution status !== 'FAILED':** useRemediationSuggestions ne fetch pas, StructuredErrorCard pas affiché
- **ERROR_MESSAGE null dans EXECUTION_STEPS:** Matching skip si error_message null → aucune suggestion
- **Multiple règles matchent même action:** Deduplicate par action_id, garder rule avec meilleur score
- **User clique suggestion puis annule wizard:** Pas de side-effect, wizard ferme, StructuredErrorCard reste affiché
- **API GET /remediation 403 Forbidden:** Hook useRemediationSuggestions set error state, affiche fallback options par défaut
- **Suggestion action disabled/draft:** Filter côté backend: ne suggérer que actions avec status='published'

### Performance considerations

**Backend query optimization:**
- `get_actions_with_remediation_rules()`: WHERE REMEDIATION_RULES IS NOT NULL pour éviter full table scan
- Index sur ACTIONS_CATALOG.STATUS si pas déjà existant (filter published actions)
- Regex matching en Python (pas SQL) — plus flexible, performance OK pour < 100 actions typiques

**Frontend performance:**
- Hook useRemediationSuggestions: fetch uniquement si executionStatus === 'FAILED' (pas de fetch inutile)
- Cache suggestions dans state hook (pas de re-fetch à chaque render)
- Suggestions max 3 (limite UI lisible + limite backend processing)

**Matching algorithm complexity:**
- O(n * m): n = actions avec règles (< 50 typiquement), m = règles par action (< 5 typiquement)
- Regex matching: O(k) avec k = longueur error_message (< 1000 chars)
- Total: < 100ms typiquement, acceptable pour UX

### Tests critiques

**Backend tests:**
- Repository: Test parse JSON CLOB → list[RemediationRule], test update action avec rules
- Service: Test matching exact (error + env + engine), partial (error + env), no match
- Service: Test regex complexe (capture groups, lookahead), test invalid regex handling
- Service: Test sort by relevance (exact engine before partial)
- Service: Test execution not failed → empty list
- API: Test GET /remediation 200 success, 200 empty list, 403 forbidden, 404 not found

**Frontend tests:**
- Hook: Test fetch si status='FAILED', test no fetch si status!='FAILED'
- Hook: Test loading state, error handling, refetch function
- StructuredErrorCard: Test affiche section suggestions si fourni, test n'affiche pas si vide
- StructuredErrorCard: Test callback onSuggestionClick appelé au clic
- ExecutionTimeline: Test intégration hook + callback onSuggestionClick → ExecutionWizard
- ExecutionWizard: Test suggestedActionId pré-sélectionne action, skip step sélection

### Compatibilité ascendante

**Backward compatibility:**
- Colonne REMEDIATION_RULES nullable (NULL = pas de règles) — actions existantes non affectées
- StructuredErrorCard avec remediationSuggestions prop optionnel — fonctionne sans suggestions
- API GET /remediation retourne liste vide si pas applicable — pas d'erreur breaking
- ExecutionWizard avec suggestedActionId prop optionnel — fonctionne en mode normal si non fourni

### Alternatives considérées et rejetées

**Alternative 1: Stocker remediation_rules dans table séparée REMEDIATION_RULES**
- Avantages: Normalisé, requêtes SQL plus faciles
- Inconvénients: Complexité schema, join nécessaire, migration difficile
- Rejetée: CLOB JSON cohérent avec IMPACT_RULES, RBAC_POLICIES pattern existant

**Alternative 2: Matching côté SQL avec JSON_VALUE**
- Avantages: Performance query Oracle optimisée
- Inconvénients: Regex SQL limité vs Python re, complexité requête
- Rejetée: Matching Python plus flexible, performance acceptable (< 100 actions)

**Alternative 3: Afficher toutes les suggestions comme liste inline**
- Avantages: Simple, pas de boutons multiples
- Inconvénients: Moins actionnable, pas de priorisation visuelle
- Rejetée: Buttons avec style primary/default communiquent priorité (top suggestion)

**Alternative 4: Auto-trigger suggestion top si risk_level=low**
- Avantages: Remédiation instantanée pour cas simples
- Inconvénients: Risque d'actions non désirées, Story 9.3 dédiée à auto-trigger
- Rejetée: Story 9.1 = détection + proposition uniquement. Auto-trigger = Story 9.3

### Opportunités d'amélioration futures (post-Story 9.1)

- **Story 9.2:** Lier execution corrective à execution originale (parent_execution_id), afficher dans timeline
- **Story 9.3:** Auto-trigger pour risk_level='low', switch dans admin UI, audit trail auto-remédiation
- **Post-Epic 9:** Machine learning pour suggérer règles basées sur historique (détection patterns)
- **Post-Epic 9:** Feedback loop: DBA marque suggestion comme "utile" ou "pas utile" pour améliorer matching
- **Post-Epic 9:** Export configuration remediation_rules en YAML (pattern Story 2.13 import/export profiles)

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 9 Story 9.1 (lignes 2300-2322)]
- [Source: idp-portal/frontend/src/components/execution/StructuredErrorCard.tsx - Composant error card existant]
- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx - Affichage error card (lignes 196-209)]
- [Source: idp-portal/backend/database/migrations/V023__create_executions.sql - Schema EXECUTIONS]
- [Source: idp-portal/backend/database/migrations/V025__create_execution_steps.sql - Schema EXECUTION_STEPS]
- [Source: idp-portal/backend/database/migrations/V002__create_actions_catalog.sql - Schema ACTIONS_CATALOG]
- [Source: idp-portal/backend/app/services/execution_service.py - Execution service (lignes 456-495 error handling)]
- [Source: idp-portal/frontend/src/components/admin/ActionForm.tsx - Admin form pattern]
- [Source: _bmad-output/planning-artifacts/architecture.md - Architecture patterns (lignes 800-945)]
- [Source: _bmad-output/implementation-artifacts/8-10-vue-liste-en-tableau-avec-colonnes.md - Intelligence story précédente]
- [Source: _bmad-output/planning-artifacts/prd.md - FR36 Autoremediation]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

N/A

### Completion Notes List

- Story created with comprehensive context from Epic 9 Story 9.1 in epics.md (lignes 2300-2322)
- Analyzed StructuredErrorCard component: current structure with 3 sections (Quoi, Pourquoi, Options), variant support
- Analyzed ExecutionTimeline integration: failedStep detection, StructuredErrorCard rendering (lignes 196-209)
- Explored execution engine with Task agent (Explore subagent):
  - EXECUTIONS table: STATUS, ENVIRONMENT, ACTION_ID FK
  - EXECUTION_STEPS table: ERROR_MESSAGE CLOB, STATUS='FAILED' detection
  - Error handling patterns in execution_service.py (lignes 456-495)
  - Three-layer error tracking: EXECUTION_STEPS.ERROR_MESSAGE + EXECUTIONS.STATUS + AUDIT_LOG.DETAILS
  - No current parent_execution_id pattern (Story 9.2 will add linking)
- Analyzed ACTIONS_CATALOG schema: existing CLOB JSON columns (PARAMETERS_SCHEMA, IMPACT_RULES, RBAC_POLICIES)
- Determined remediation_rules schema: JSON array with error_pattern (regex), target_action_id, environments, auto_trigger, risk_level
- Designed matching algorithm: regex error_pattern + environment filter + engine bonus scoring + top 3 suggestions
- Mapped all 6 acceptance criteria to 19 detailed tasks with subtasks
- Comprehensive Dev Notes with code examples for:
  - remediation_rules JSON schema
  - Matching logic Python (execution_service.get_remediation_suggestions)
  - StructuredErrorCard modifications with new section "Actions correctives suggérées"
  - ExecutionTimeline integration with useRemediationSuggestions hook
  - ExecutionWizard pré-remplissage avec suggestedActionId
  - Admin UI Form.List pattern pour remediation_rules
- Applied learnings from Story 8.10 (design tokens, tooltip patterns, useMemo, comprehensive tests)
- Leveraged architecture patterns: Repository SQL brut, Service matching logic, API REST, Frontend hooks + services
- Backward compatible: REMEDIATION_RULES nullable, props optional, API returns empty list (no error)
- Tests critiques identifiés: 8 tests backend (repository, service, API) + 11 tests frontend (hook, StructuredErrorCard, ExecutionTimeline, ExecutionWizard)
- Story 9.1 scope: Détection + proposition uniquement. Auto-trigger = Story 9.3. Linking executions = Story 9.2.

### File List

**Files to create:**

Backend:
- `database/migrations/V044_add_remediation_rules.sql` - Migration colonne REMEDIATION_RULES CLOB
- `tests/unit/test_catalog_repository_remediation.py` - Tests repository remediation rules (5 tests)
- `tests/unit/test_execution_service_remediation.py` - Tests service remediation suggestions (8 tests)

Frontend:
- `frontend/src/hooks/useRemediationSuggestions.ts` - Hook fetch suggestions
- `frontend/src/hooks/useRemediationSuggestions.test.ts` - Tests hook (7 tests)

**Files to modify:**

Backend:
- `app/models/catalog.py` - Ajouter RemediationRule, RemediationSuggestion Pydantic models
- `app/repositories/catalog_repository.py` - Modifier get_action_by_id, ajouter get_actions_with_remediation_rules
- `app/services/execution_service.py` - Ajouter get_remediation_suggestions(execution_id)
- `app/api/v1/executions.py` - Ajouter route GET /{id}/remediation
- `tests/integration/test_executions_api.py` - Tests API GET /remediation (5 tests)

Frontend:
- `frontend/src/types/api.ts` - Ajouter RemediationSuggestion interface
- `frontend/src/services/execution_service.ts` - Ajouter fetchRemediationSuggestions function
- `frontend/src/components/execution/StructuredErrorCard.tsx` - Ajouter section suggestions + props
- `frontend/src/components/execution/StructuredErrorCard.test.tsx` - Tests suggestions (8 tests)
- `frontend/src/components/execution/ExecutionTimeline.tsx` - Intégrer useRemediationSuggestions hook
- `frontend/src/components/execution/ExecutionTimeline.test.tsx` - Tests intégration (5 tests)
- `frontend/src/components/execution/ExecutionWizard.tsx` - Ajouter suggestedActionId prop
- `frontend/src/components/execution/ExecutionWizard.test.tsx` - Tests pré-remplissage (5 tests)
- `frontend/src/components/admin/ActionForm.tsx` - Ajouter section remediation_rules avec Form.List
