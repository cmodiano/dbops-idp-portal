# Story 11.8 : Cron expressions pour recurrence avancee

Status: in-progress

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **DBA power user**,
je veux **utiliser des expressions cron complètes pour définir des patterns de récurrence complexes**,
afin de **planifier des exécutions avec des fréquences avancées (ex: tous les 2 jours, le premier lundi du mois)**.

## Contexte

**Contexte Epic 11 - Scheduling & Maintenance Planifiée:**

Le système permet de planifier des exécutions d'actions pour une date/heure future ou selon des patterns de récurrence. Les exécutions planifiées sont gérées via un modèle de données et des APIs, mais l'exécution effective est déléguée à un scheduler externe (Control-M ou Django scheduler) pour éviter la charge backend supplémentaire.

**Approche technique :**
- Modèle de données + UI/API complètes, mais PAS de scheduler intégré (Celery)
- Les schedules sont récupérés et exécutés par un scheduler externe
- Pas de seconde base de données, pas de charge backend supplémentaire pour le polling
- Le scheduler externe interroge l'API pour obtenir les exécutions à lancer via `NEXT_EXECUTION_DATE`

**État actuel:**

Stories précédentes complétées dans Epic 11 :
- **Story 11.1** (done) : Modèle de données SCHEDULED_EXECUTIONS et RECURRING_PATTERNS créé (migration V038)
  - Table RECURRING_PATTERNS avec pattern_type (one_time, daily, weekly, **cron**)
  - PATTERN_CONFIG CLOB JSON flexible pour supporter tout type de configuration
  - Colonne NEXT_EXECUTION_DATE pour scheduler externe
  - Index composite optimisé sur (IS_ACTIVE, NEXT_EXECUTION_DATE)
- **Story 11.3** (done) : API `POST /api/v1/scheduled-executions` pour créer une exécution planifiée one-time
  - Validation timezone avec Pydantic
  - Validation paramètres avec jsonschema
  - Traçabilité audit avec correlation_id
- **Story 11.5** (done) : UI scheduler dans le wizard d'exécution avec option "Exécuter maintenant" vs "Planifier"
  - DatePicker avec showTime et validation date future
  - Display timezone UTC avec tooltip
  - Tests complets (45 tests passent)
- **Story 11.6** (done) : Liste des exécutions planifiées et annulation
  - Page Admin avec liste filtrée par RBAC
  - Annulation des exécutions pending avec PATCH endpoint
  - Modal détails avec correlation_id et execution_id
- **Story 11.7** (done) : Patterns de récurrence simples (Daily et Weekly)
  - API étendue avec recurring_pattern pour daily/weekly
  - UI wizard avec Radio.Group pour choisir le type
  - Calcul automatique de next_execution_date via `recurrence.py`
  - Activation/désactivation des récurrences avec PATCH endpoint
  - 22 tests unitaires + 14 tests intégration + 9 tests frontend

**Objectif de cette story:**

Permettre aux DBAs power users de créer des exécutions récurrentes avec des **expressions cron complètes** pour des patterns avancés que daily/weekly ne peuvent pas exprimer :
1. **Expressions cron standard** : Format 5 champs (minute hour day month day_of_week)
2. **Validation robuste** : Validation syntaxique et sémantique des expressions cron
3. **Calcul automatique** du `NEXT_EXECUTION_DATE` avec la bibliothèque croniter
4. **Helper UI** : Guide et exemples pour aider l'utilisateur à construire des expressions valides
5. **Preview** : Affichage des 5 prochaines exécutions pour validation visuelle

Cette story étend l'API et l'UI du wizard d'exécution pour supporter les expressions cron avancées. Les patterns daily/weekly (Story 11.7) restent disponibles pour les utilisateurs non-techniques.

## Acceptance Criteria

### AC1 - Option "Récurrence avancée (cron)" dans le wizard

**Given** le DBA ouvre le wizard d'exécution et clique sur "Planifier"
**When** il voit les options de récurrence
**Then** il voit quatre options : "One-time", "Daily", "Weekly", "Avancé (cron)"

**Given** le DBA sélectionne "Avancé (cron)"
**When** l'interface s'ajuste
**Then** il voit :
- Un champ texte Input pour saisir l'expression cron
- Un bouton "?" avec tooltip expliquant le format : "minute hour day month day_of_week"
- Un lien vers crontab.guru pour aide externe
- Des exemples courants (presets) : "Tous les jours à 2h", "Premier lundi du mois", etc.

### AC2 - Validation en temps réel de l'expression cron

**Given** le DBA saisit une expression cron dans le champ texte
**When** il tape l'expression (ex: "0 2 * * 1-5")
**Then** la validation s'exécute en temps réel (debounce 500ms)

**Given** l'expression cron est **valide**
**When** la validation se termine
**Then** :
- Un indicateur vert s'affiche avec icône checkmark
- Une Card "Prochaines exécutions" affiche les 5 prochaines dates/heures calculées
- Format : "DD/MM/YYYY à HH:mm (UTC)"

**Given** l'expression cron est **invalide**
**When** la validation se termine
**Then** :
- Un indicateur rouge s'affiche avec icône error
- Un message d'erreur explicatif apparaît : "Expression cron invalide. Format attendu : minute hour day month day_of_week"
- Le bouton "Confirmer" est désactivé

### AC3 - Presets d'expressions cron courantes

**Given** le DBA sélectionne "Avancé (cron)"
**When** l'interface s'affiche
**Then** un Select "Expressions courantes" est disponible avec les options suivantes :
- "Chaque jour à 02:00" → "0 2 * * *"
- "Chaque lundi à 14:00" → "0 14 * * 1"
- "Chaque vendredi à 18:00" → "0 18 * * 5"
- "Tous les jours à 9h et 17h" → "0 9,17 * * *"
- "Le 1er de chaque mois à minuit" → "0 0 1 * *"
- "Toutes les 15 minutes" → "*/15 * * * *"
- "Tous les jours ouvrables à 2h" → "0 2 * * 1-5"
- "Personnalisé" → vide le champ

**Given** le DBA sélectionne un preset
**When** il clique sur un preset
**Then** le champ Input est rempli automatiquement avec l'expression correspondante
**And** la validation se déclenche automatiquement
**And** les prochaines exécutions sont affichées

### AC4 - Création d'une exécution récurrente avec expression cron

**Given** le DBA saisit une expression cron valide "0 2 * * 1-5" (tous les jours ouvrables à 2h)
**When** il confirme la création
**Then** l'API `POST /api/v1/scheduled-executions` est appelée avec :
```json
{
  "action_id": 123,
  "environment": "prod",
  "parameters": {...},
  "recurring_pattern": {
    "pattern_type": "cron",
    "pattern_config": {
      "cron_expression": "0 2 * * 1-5"
    }
  }
}
```

**And** une entrée SCHEDULED_EXECUTIONS est créée avec scheduled_at=NULL (récurrent, pas de date unique)
**And** une entrée RECURRING_PATTERNS est créée avec :
- pattern_type="cron"
- pattern_config={"cron_expression": "0 2 * * 1-5"}
- next_execution_date = prochaine occurrence calculée par croniter
- is_active=true

### AC5 - Validation backend de l'expression cron

**Given** l'API POST reçoit une recurring_pattern avec pattern_type="cron"
**When** la validation backend s'exécute
**Then** :
- L'expression cron est validée avec `croniter.is_valid()`
- Si invalide → erreur 400 avec message "Expression cron invalide : [détails]"
- Si valide → calcul de next_execution_date avec croniter
- Audit log créé avec action_type : "SCHEDULED_EXECUTION_RECURRING_CREATED"

**Given** le DBA envoie une expression cron invalide "99 99 * * *"
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec message :
```json
{
  "error": {
    "message": "Expression cron invalide : hour must be in 0-23",
    "code": "VALIDATION_ERROR"
  }
}
```

### AC6 - Calcul de next_execution_date avec croniter

**Given** une récurrence cron avec expression "0 2 * * 1-5" (tous les jours ouvrables à 2h)
**When** la récurrence est créée le lundi 2026-02-02 à 15:00 UTC
**Then** next_execution_date est calculé pour le mardi 2026-02-03 à 02:00 UTC (prochain jour ouvrable à 2h)

**Given** une récurrence cron avec expression "0 0 1 * *" (le 1er de chaque mois à minuit)
**When** la récurrence est créée le 2026-02-15 à 10:00 UTC
**Then** next_execution_date est calculé pour le 2026-03-01 à 00:00 UTC (prochain 1er du mois)

**Given** une récurrence cron avec expression "*/15 * * * *" (toutes les 15 minutes)
**When** la récurrence est créée le 2026-02-02 à 14:08 UTC
**Then** next_execution_date est calculé pour le 2026-02-02 à 14:15 UTC (prochain multiple de 15 minutes)

**Given** une exécution cron est exécutée par le scheduler externe
**When** elle se termine et le scheduler appelle l'API de mise à jour
**Then** next_execution_date est incrémenté selon l'expression cron (croniter.get_next())

### AC7 - Affichage des récurrences cron dans la liste

**Given** un DBA consulte la page "Exécutions planifiées" (Story 11.6)
**When** une exécution récurrente avec pattern_type="cron" est affichée
**Then** la colonne "Date/heure planifiée" affiche :
- "Récurrence : 0 2 * * 1-5" (affichage direct de l'expression cron)
- Avec en dessous : "Prochaine : 03/02/2026 à 02:00"

**And** la colonne "Type" affiche un badge "Récurrent - Cron" en violet (distinct de Daily/Weekly en bleu)
**And** le statut peut être "pending" (active, next_execution_date dans le futur)

### AC8 - Modal de détails pour exécutions cron

**Given** le DBA clique sur "Voir détails" pour une exécution récurrente cron
**When** la modal s'ouvre
**Then** elle affiche :
- ID de l'exécution planifiée
- Action (nom + ID)
- Type : "Récurrent - Cron"
- Expression cron : "0 2 * * 1-5"
- Description lisible : "Tous les jours ouvrables à 2h00" (générée par helper)
- Prochaines 3 exécutions :
  - "03/02/2026 à 02:00 (UTC)"
  - "04/02/2026 à 02:00 (UTC)"
  - "05/02/2026 à 02:00 (UTC)"
- Statut : "Actif" (si is_active=true) ou "Désactivé" (si is_active=false)
- Date de création
- Correlation ID

**And** si l'exécution est active (is_active=true), un bouton "Désactiver" est affiché
**And** si l'exécution est désactivée (is_active=false), un bouton "Réactiver" est affiché

### AC9 - Helper pour comprendre l'expression cron

**Given** le DBA clique sur le bouton "?" ou "Aide" dans le wizard
**When** la modal helper s'ouvre
**Then** elle affiche :
- Explication du format : "minute hour day month day_of_week"
- Tableau des valeurs possibles :
  - Minute : 0-59 ou * (tous) ou */15 (tous les 15)
  - Hour : 0-23 ou * (tous)
  - Day : 1-31 ou * (tous)
  - Month : 1-12 ou * (tous)
  - Day of week : 0-6 (0=Dimanche, 1=Lundi, ..., 6=Samedi) ou * (tous)
- Exemples annotés :
  - "0 2 * * *" → Tous les jours à 2h00
  - "0 14 * * 1" → Tous les lundis à 14h00
  - "0 0 1 * *" → Le 1er de chaque mois à minuit
  - "*/15 * * * *" → Toutes les 15 minutes
  - "0 9,17 * * 1-5" → Jours ouvrables à 9h et 17h
- Lien externe vers crontab.guru pour validation interactive

### AC10 - Gestion des expressions cron existantes (réactivation)

**Given** une exécution récurrente cron désactivée (is_active=false)
**When** le DBA clique sur "Réactiver" dans la modal de détails
**Then** l'API `PATCH /api/v1/scheduled-executions/{id}/recurring-pattern` est appelée avec `{ "is_active": true }`
**And** is_active est mis à true
**And** next_execution_date est recalculé avec croniter selon l'expression cron existante
**And** une notification success s'affiche : "Récurrence réactivée avec succès"

### AC11 - Audit des opérations sur récurrences cron

**Given** une récurrence cron est créée, désactivée ou réactivée
**When** l'opération est effectuée
**Then** un log est créé dans audit_log avec :
- action_type : "SCHEDULED_EXECUTION_RECURRING_CREATED", "SCHEDULED_EXECUTION_RECURRING_DISABLED", "SCHEDULED_EXECUTION_RECURRING_ENABLED"
- resource_type : "scheduled_execution"
- resource_id : ID de la scheduled execution
- details : pattern_type="cron", pattern_config={"cron_expression": "..."}, next_execution_date
- correlation_id

### AC12 - Compatibilité avec daily/weekly existants

**Given** des exécutions récurrentes daily et weekly existent déjà (Story 11.7)
**When** le système gère des récurrences cron
**Then** :
- Les récurrences daily et weekly continuent de fonctionner sans changement
- Les trois types (daily, weekly, cron) coexistent dans la liste
- Le calcul de next_execution_date utilise la logique appropriée selon pattern_type
- Les badges de type sont distincts : "Récurrent" (bleu) pour daily/weekly, "Récurrent - Cron" (violet) pour cron

## Tasks / Subtasks

- [ ] Task 1: Ajouter la dépendance croniter au backend (AC4, AC5, AC6)
  - [ ] Subtask 1.1: Ajouter `croniter>=3.0` dans `backend/pyproject.toml`
  - [ ] Subtask 1.2: Exécuter `pip install croniter` dans l'environnement backend
  - [ ] Subtask 1.3: Vérifier l'import `from croniter import croniter` fonctionne

- [ ] Task 2: Étendre les modèles backend pour supporter pattern cron (AC4, AC5)
  - [ ] Subtask 2.1: Créer modèle Pydantic `CronPatternConfig` dans `backend/app/models/scheduled_execution.py`
  - [ ] Subtask 2.2: Ajouter field_validator pour valider cron_expression avec `croniter.is_valid()`
  - [ ] Subtask 2.3: Étendre `RecurringPatternType` enum avec valeur "cron"
  - [ ] Subtask 2.4: Étendre `RecurringPatternRequest` pour accepter pattern_type="cron"
  - [ ] Subtask 2.5: Ajouter model_validator pour valider cron_expression présent si pattern_type="cron"

- [ ] Task 3: Implémenter le calcul de next_execution_date pour cron (AC6)
  - [ ] Subtask 3.1: Étendre `backend/app/utils/recurrence.py` avec fonction `_calculate_cron_next_execution()`
  - [ ] Subtask 3.2: Utiliser `croniter(cron_expression, reference_datetime)` pour calculer next
  - [ ] Subtask 3.3: Appeler `cron.get_next(datetime)` pour obtenir la prochaine occurrence
  - [ ] Subtask 3.4: Gérer les erreurs croniter (ValueError, KeyError) et lever ValueError avec message explicite
  - [ ] Subtask 3.5: Ajouter logging structlog avec cron_expression, reference_datetime, next_execution
  - [ ] Subtask 3.6: Ajouter tests unitaires pour _calculate_cron_next_execution (15+ tests)

- [ ] Task 4: Étendre l'API POST pour accepter pattern cron (AC4, AC5)
  - [ ] Subtask 4.1: Modifier endpoint POST `/api/v1/scheduled-executions` pour accepter pattern_type="cron"
  - [ ] Subtask 4.2: Valider cron_expression avec `croniter.is_valid()` avant création
  - [ ] Subtask 4.3: Si invalide → retourner erreur 400 avec message explicatif
  - [ ] Subtask 4.4: Calculer next_execution_date avec `calculate_next_execution_date()` étendu
  - [ ] Subtask 4.5: Créer SCHEDULED_EXECUTIONS avec scheduled_at=NULL et RECURRING_PATTERNS avec pattern_type="cron"
  - [ ] Subtask 4.6: Tracer dans audit_log : SCHEDULED_EXECUTION_RECURRING_CREATED

- [ ] Task 5: Étendre le wizard d'exécution pour option "Avancé (cron)" (AC1, AC2, AC3)
  - [ ] Subtask 5.1: Modifier `ExecutionWizard.tsx` pour ajouter option "cron" dans Radio.Group
  - [ ] Subtask 5.2: Si "cron" sélectionné → afficher Input pour cron_expression
  - [ ] Subtask 5.3: Ajouter Tooltip avec icône QuestionCircleOutlined expliquant le format
  - [ ] Subtask 5.4: Créer Select "Expressions courantes" avec presets (7 options)
  - [ ] Subtask 5.5: Implémenter handleCronChange avec debounce 500ms pour validation temps réel
  - [ ] Subtask 5.6: Appeler API backend GET /api/v1/scheduled-executions/validate-cron?expression={expr} pour validation
  - [ ] Subtask 5.7: Si valide → appeler GET /api/v1/scheduled-executions/cron-next-executions?expression={expr}&count=5
  - [ ] Subtask 5.8: Afficher Card "Prochaines exécutions" avec les 5 prochaines dates/heures
  - [ ] Subtask 5.9: Si invalide → afficher Alert error avec message d'erreur
  - [ ] Subtask 5.10: Désactiver bouton "Confirmer" si expression invalide

- [ ] Task 6: Créer les endpoints backend pour validation et preview (AC2)
  - [ ] Subtask 6.1: Créer endpoint GET `/api/v1/scheduled-executions/validate-cron`
  - [ ] Subtask 6.2: Accepter query param `expression: str`
  - [ ] Subtask 6.3: Valider avec `croniter.is_valid()` et retourner `{"valid": true/false, "error": "..."}`
  - [ ] Subtask 6.4: Créer endpoint GET `/api/v1/scheduled-executions/cron-next-executions`
  - [ ] Subtask 6.5: Accepter query params `expression: str`, `count: int = 5`
  - [ ] Subtask 6.6: Calculer les N prochaines exécutions avec croniter
  - [ ] Subtask 6.7: Retourner liste de datetimes ISO 8601 : `{"executions": ["2026-02-03T02:00:00+00:00", ...]}`

- [ ] Task 7: Créer la modal helper pour comprendre les expressions cron (AC9)
  - [ ] Subtask 7.1: Créer composant `CronExpressionHelper.tsx` dans `frontend/src/components/common/`
  - [ ] Subtask 7.2: Afficher tableau des champs cron (minute, hour, day, month, dow) avec valeurs possibles
  - [ ] Subtask 7.3: Afficher exemples annotés avec explication en français
  - [ ] Subtask 7.4: Ajouter lien externe vers crontab.guru avec target="_blank"
  - [ ] Subtask 7.5: Intégrer modal dans ExecutionWizard avec bouton "Aide" à côté du champ cron

- [ ] Task 8: Étendre l'affichage dans ScheduledExecutionsPage pour cron (AC7, AC8)
  - [ ] Subtask 8.1: Modifier fonction `formatRecurrenceDisplay()` pour gérer pattern_type="cron"
  - [ ] Subtask 8.2: Si cron → afficher "Récurrence : {cron_expression}" directement
  - [ ] Subtask 8.3: Modifier colonne "Type" pour afficher Badge "Récurrent - Cron" en violet (#722ed1)
  - [ ] Subtask 8.4: Étendre modal de détails pour afficher expression cron + description lisible
  - [ ] Subtask 8.5: Appeler API GET /cron-next-executions pour afficher les 3 prochaines exécutions dans la modal
  - [ ] Subtask 8.6: Afficher description lisible générée par helper (ex: "Tous les jours ouvrables à 2h00")

- [ ] Task 9: Implémenter helper pour description lisible des expressions cron (AC8)
  - [ ] Subtask 9.1: Créer fonction `describeCronExpression(expression: string): string` dans utils frontend
  - [ ] Subtask 9.2: Parser l'expression cron (split sur espaces)
  - [ ] Subtask 9.3: Analyser chaque champ (minute, hour, day, month, dow) et générer description
  - [ ] Subtask 9.4: Exemples :
    - "0 2 * * *" → "Tous les jours à 2h00"
    - "0 14 * * 1" → "Tous les lundis à 14h00"
    - "0 0 1 * *" → "Le 1er de chaque mois à minuit"
    - "*/15 * * * *" → "Toutes les 15 minutes"
    - "0 9,17 * * 1-5" → "Jours ouvrables à 9h00 et 17h00"
  - [ ] Subtask 9.5: Si expression trop complexe → afficher l'expression brute

- [ ] Task 10: Créer le service frontend pour validation et preview cron (AC2)
  - [ ] Subtask 10.1: Étendre `scheduled_execution_service.ts` avec fonction `validateCronExpression(expression)`
  - [ ] Subtask 10.2: Appeler GET /api/v1/scheduled-executions/validate-cron
  - [ ] Subtask 10.3: Créer fonction `getCronNextExecutions(expression, count = 5)`
  - [ ] Subtask 10.4: Appeler GET /api/v1/scheduled-executions/cron-next-executions
  - [ ] Subtask 10.5: Retourner tableau de strings ISO 8601

- [ ] Task 11: Tests backend pour pattern cron (AC4, AC5, AC6)
  - [ ] Subtask 11.1: Test unitaire `test_calculate_cron_weekdays_2am` - "0 2 * * 1-5"
  - [ ] Subtask 11.2: Test unitaire `test_calculate_cron_first_of_month` - "0 0 1 * *"
  - [ ] Subtask 11.3: Test unitaire `test_calculate_cron_every_15_minutes` - "*/15 * * * *"
  - [ ] Subtask 11.4: Test unitaire `test_calculate_cron_complex_expression` - "0 9,17 * * 1-5"
  - [ ] Subtask 11.5: Test unitaire `test_invalid_cron_raises_error` - "99 99 * * *"
  - [ ] Subtask 11.6: Test intégration `test_create_cron_recurring_execution` - POST avec pattern cron
  - [ ] Subtask 11.7: Test intégration `test_cron_pattern_validation_invalid_expression`
  - [ ] Subtask 11.8: Test intégration `test_list_includes_cron_patterns`
  - [ ] Subtask 11.9: Test intégration `test_cron_execution_has_null_scheduled_at`
  - [ ] Subtask 11.10: Test intégration `test_audit_log_cron_created`
  - [ ] Subtask 11.11: Test endpoint `test_validate_cron_endpoint_valid`
  - [ ] Subtask 11.12: Test endpoint `test_validate_cron_endpoint_invalid`
  - [ ] Subtask 11.13: Test endpoint `test_cron_next_executions_endpoint`

- [ ] Task 12: Tests frontend pour pattern cron (AC1, AC2, AC3)
  - [ ] Subtask 12.1: Test `test_wizard_shows_cron_option` - Radio.Group affiche "Avancé (cron)"
  - [ ] Subtask 12.2: Test `test_wizard_cron_selected_shows_input` - Cron sélectionné → Input affiché
  - [ ] Subtask 12.3: Test `test_cron_presets_populate_input` - Sélection preset remplit le champ
  - [ ] Subtask 12.4: Test `test_cron_validation_valid_expression` - Expression valide → checkmark vert
  - [ ] Subtask 12.5: Test `test_cron_validation_invalid_expression` - Expression invalide → erreur affichée
  - [ ] Subtask 12.6: Test `test_cron_next_executions_displayed` - Prochaines exécutions affichées
  - [ ] Subtask 12.7: Test `test_create_cron_execution_api_called` - Clic confirmer → API appelée avec pattern cron
  - [ ] Subtask 12.8: Test `test_cron_helper_modal_opens` - Clic "?" → modal helper s'ouvre
  - [ ] Subtask 12.9: Test service `test_validateCronExpression_service`
  - [ ] Subtask 12.10: Test service `test_getCronNextExecutions_service`

- [ ] Task 13: Validation manuelle et documentation (AC11, AC12)
  - [ ] Subtask 13.1: Tester création cron "0 2 * * 1-5" → succès
  - [ ] Subtask 13.2: Tester validation "99 99 * * *" → erreur 400
  - [ ] Subtask 13.3: Tester presets → remplissage automatique
  - [ ] Subtask 13.4: Tester preview 5 prochaines exécutions
  - [ ] Subtask 13.5: Tester modal helper → affichage correct
  - [ ] Subtask 13.6: Tester coexistence daily/weekly/cron dans la liste
  - [ ] Subtask 13.7: Tester désactivation/réactivation d'une récurrence cron
  - [ ] Subtask 13.8: Vérifier audit logs pour toutes les opérations cron
  - [ ] Subtask 13.9: Story file mis à jour avec status=done
  - [ ] Subtask 13.10: Sprint status mis à jour

## Dev Notes

### Architecture et contraintes techniques

**Stack technique frontend :**
- Framework : React 19
- UI Library : Ant Design 6.2
- Date manipulation : Dayjs (inclus avec Ant Design)
- Routing : React Router 7
- TypeScript : 5.x
- Build tool : Vite 7

**Stack technique backend :**
- Backend : FastAPI + python-oracledb (async)
- Base de données : Oracle 19c
- Migration : Flyway (V038 déjà appliquée en Story 11.1 avec RECURRING_PATTERNS)
- **Bibliothèque cron : croniter 3.0+** (à installer)
- Pattern : SQL brut via repositories
- Authentification : JWT via `Depends(get_current_user)`
- RBAC : Vérification des rôles DBA/DBOPS
- Date/time : datetime.timezone.utc pour tous les calculs

**Tables utilisées :**
- `SCHEDULED_EXECUTIONS` (créée en V038) : Stocke les exécutions planifiées
  - scheduled_at devient NULL pour exécutions récurrentes (pas de date unique)
- `RECURRING_PATTERNS` (créée en V038) : Stocke les patterns de récurrence
  - pattern_type : 'daily', 'weekly', **'cron'** (nouveau en Story 11.8)
  - pattern_config : CLOB JSON avec configuration spécifique au type
    - Pour cron : `{"cron_expression": "0 2 * * 1-5"}`
  - next_execution_date : TIMESTAMP WITH TIME ZONE utilisé par scheduler externe
  - is_active : NUMBER(1) booléen pour activer/désactiver
- `ACTIONS_CATALOG` : Détails des actions (JOIN pour action_name)
- `AUDIT_LOG` : Traçabilité des opérations sur récurrences

**Composants UI à modifier :**
- `ExecutionWizard.tsx` (Story 11.5, 11.7) - Ajouter option "cron" dans Radio.Group
- `ScheduledExecutionsPage.tsx` (Story 11.6, 11.7) - Afficher récurrences cron avec badge violet
- `Input` (Ant Design) - Champ texte pour saisie expression cron
- `Select` (Ant Design) - Sélection presets cron
- `Card` (Ant Design) - Preview prochaines exécutions
- `Alert` (Ant Design) - Messages d'erreur validation
- `Modal` (Ant Design) - Helper pour comprendre les expressions cron

**Bibliothèque cron recommandée : croniter**

Après analyse approfondie (voir contexte de recherche), croniter est le choix optimal pour ce projet :
- **Validation robuste** : `croniter.is_valid()` pour syntaxe et sémantique
- **Calcul next_execution** : `croniter(expr, ref).get_next(datetime)` retourne datetime
- **Timezone UTC** : Support natif timezone.utc
- **Performance** : Gestion des edge cases avec `max_years_between_matches`
- **Maintenance** : Bibliothèque mature et activement maintenue

### Patterns de code à suivre

**Pattern 1 : Modèles Pydantic pour cron pattern**

Source : `/idp-portal/backend/app/models/scheduled_execution.py` (à étendre)

```python
# backend/app/models/scheduled_execution.py

from pydantic import BaseModel, Field, field_validator
from typing import Literal
from croniter import croniter

class CronPatternConfig(BaseModel):
    """Configuration for cron recurring pattern (Story 11.8)."""
    cron_expression: str = Field(
        ...,
        description="Cron expression (5 fields: minute hour day month dow)",
        example="0 2 * * 1-5",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        """Validate cron expression format using croniter."""
        if not v:
            raise ValueError("Expression cron requise")

        if not croniter.is_valid(v):
            raise ValueError(
                "Expression cron invalide. Format attendu : minute hour day month day_of_week"
            )

        return v

class RecurringPatternType(str, Enum):
    """Recurring pattern types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    CRON = "cron"  # NEW in Story 11.8

class RecurringPatternRequest(BaseModel):
    """Recurring pattern in creation request (Stories 11.7, 11.8)."""
    pattern_type: Literal["daily", "weekly", "cron"]
    pattern_config: dict[str, Any]

    @model_validator(mode="after")
    def validate_pattern_config_matches_type(self):
        """Validate pattern_config matches pattern_type."""
        pattern_type = self.pattern_type
        pattern_config = self.pattern_config

        if pattern_type == "cron":
            if "cron_expression" not in pattern_config:
                raise ValueError(
                    "Pattern config incomplet : cron_expression requis pour pattern cron"
                )
            # Additional validation: parse with croniter
            cron_expr = pattern_config["cron_expression"]
            if not croniter.is_valid(cron_expr):
                raise ValueError(f"Expression cron invalide : {cron_expr}")

        elif pattern_type == "daily":
            # Existing validation from Story 11.7
            if "hour" not in pattern_config or "minute" not in pattern_config:
                raise ValueError("Pattern config incomplet : hour et minute requis")

        elif pattern_type == "weekly":
            # Existing validation from Story 11.7
            if "day_of_week" not in pattern_config:
                raise ValueError("Pattern config incomplet : day_of_week requis")

        return self
```

**Pattern 2 : Calcul next_execution_date avec croniter**

Source : Nouveau code dans `/idp-portal/backend/app/utils/recurrence.py`

```python
# backend/app/utils/recurrence.py

from datetime import datetime, timezone
from croniter import croniter
import structlog

logger = structlog.get_logger(__name__)

def calculate_next_execution_date(
    pattern_type: str,
    pattern_config: dict[str, Any],
    reference_datetime: datetime | None = None,
) -> datetime:
    """
    Calculate next execution date for recurring pattern (Stories 11.7, 11.8).

    Args:
        pattern_type: Type of pattern ("daily", "weekly", or "cron")
        pattern_config: Pattern configuration dict
        reference_datetime: Reference time (defaults to now in UTC)

    Returns:
        Next execution datetime in UTC

    Raises:
        ValueError: If pattern_type or pattern_config is invalid
    """
    if reference_datetime is None:
        reference_datetime = datetime.now(timezone.utc)

    # Ensure reference_datetime is in UTC
    if reference_datetime.tzinfo is None:
        reference_datetime = reference_datetime.replace(tzinfo=timezone.utc)

    if pattern_type == "daily":
        return _calculate_daily_next_execution(pattern_config, reference_datetime)
    elif pattern_type == "weekly":
        return _calculate_weekly_next_execution(pattern_config, reference_datetime)
    elif pattern_type == "cron":
        return _calculate_cron_next_execution(pattern_config, reference_datetime)
    else:
        raise ValueError(f"Type de pattern non supporté : {pattern_type}")

def _calculate_cron_next_execution(
    pattern_config: dict[str, Any],
    reference_datetime: datetime,
) -> datetime:
    """
    Calculate next execution for cron pattern (Story 11.8).

    Args:
        pattern_config: Dict with "cron_expression" key
        reference_datetime: Reference datetime in UTC

    Returns:
        Next execution datetime in UTC

    Raises:
        ValueError: If cron expression is missing or invalid
    """
    cron_expression = pattern_config.get("cron_expression")

    if not cron_expression:
        raise ValueError("Pattern config incomplet : cron_expression requis pour pattern cron")

    # Validate cron expression
    if not croniter.is_valid(cron_expression):
        raise ValueError(f"Expression cron invalide : {cron_expression}")

    try:
        # Create croniter instance
        cron = croniter(cron_expression, reference_datetime)

        # Get next execution datetime
        next_execution = cron.get_next(datetime)

        logger.info(
            "calculated_cron_next_execution",
            cron_expression=cron_expression,
            reference_datetime=reference_datetime.isoformat(),
            next_execution=next_execution.isoformat(),
        )

        return next_execution

    except (ValueError, KeyError) as e:
        raise ValueError(f"Erreur lors du calcul de la prochaine exécution cron : {str(e)}")

def increment_next_execution_date(
    pattern_type: str,
    pattern_config: dict[str, Any],
    current_next_execution: datetime,
) -> datetime:
    """
    Increment next_execution_date for recurring pattern (used by scheduler).

    For cron patterns, this recalculates from current_next_execution.

    Args:
        pattern_type: Type of pattern
        pattern_config: Pattern configuration
        current_next_execution: Current next_execution_date

    Returns:
        New next_execution_date
    """
    if pattern_type == "cron":
        # For cron, recalculate from current_next_execution
        return calculate_next_execution_date(
            pattern_type="cron",
            pattern_config=pattern_config,
            reference_datetime=current_next_execution,
        )
    elif pattern_type == "daily":
        # Existing logic from Story 11.7
        return current_next_execution + timedelta(days=1)
    elif pattern_type == "weekly":
        # Existing logic from Story 11.7
        return current_next_execution + timedelta(weeks=1)
    else:
        raise ValueError(f"Type de pattern non supporté : {pattern_type}")
```

**Pattern 3 : Endpoints backend pour validation et preview**

Source : Nouveau code dans `/idp-portal/backend/app/api/v1/scheduled_executions.py`

```python
# backend/app/api/v1/scheduled_executions.py

from fastapi import APIRouter, Depends, Query
from croniter import croniter
from datetime import datetime, timezone
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/scheduled-executions/validate-cron")
async def validate_cron_expression(
    expression: str = Query(..., description="Cron expression to validate"),
    current_user: User = Depends(get_current_user),
):
    """
    Validate a cron expression (Story 11.8).

    Returns:
        {"valid": true/false, "error": "error message if invalid"}
    """
    try:
        if not croniter.is_valid(expression):
            return {
                "valid": False,
                "error": "Expression cron invalide. Format attendu : minute hour day month day_of_week",
            }

        # Additional semantic validation: try to get next execution
        reference = datetime.now(timezone.utc)
        cron = croniter(expression, reference)
        _ = cron.get_next(datetime)  # Test iteration

        return {"valid": True, "error": ""}

    except Exception as e:
        return {
            "valid": False,
            "error": f"Expression cron invalide : {str(e)}",
        }

@router.get("/scheduled-executions/cron-next-executions")
async def get_cron_next_executions(
    expression: str = Query(..., description="Cron expression"),
    count: int = Query(5, ge=1, le=10, description="Number of next executions to return"),
    current_user: User = Depends(get_current_user),
):
    """
    Get next N executions for a cron expression (Story 11.8).

    Returns:
        {"executions": ["2026-02-03T02:00:00+00:00", ...]}
    """
    try:
        # Validate expression
        if not croniter.is_valid(expression):
            raise ValueError("Expression cron invalide")

        # Calculate next executions
        reference = datetime.now(timezone.utc)
        cron = croniter(expression, reference)

        executions = []
        for _ in range(count):
            next_exec = cron.get_next(datetime)
            executions.append(next_exec.isoformat())

        return {"executions": executions}

    except Exception as e:
        raise InvalidStateError(message=f"Erreur lors du calcul des prochaines exécutions : {str(e)}")
```

**Pattern 4 : Extension du wizard pour cron**

Source : Extension de `/idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx`

```tsx
// frontend/src/components/catalog/ExecutionWizard.tsx

import { Radio, Select, Input, Button, Space, Card, Alert, Tooltip } from 'antd';
import { QuestionCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { RecurringPatternRequest } from '../../types/api';
import { validateCronExpression, getCronNextExecutions } from '../../services/scheduled_execution_service';
import { debounce } from 'lodash';

// Presets d'expressions cron courantes
const CRON_PRESETS = [
  { label: "Chaque jour à 02:00", value: "0 2 * * *" },
  { label: "Chaque lundi à 14:00", value: "0 14 * * 1" },
  { label: "Chaque vendredi à 18:00", value: "0 18 * * 5" },
  { label: "Tous les jours à 9h et 17h", value: "0 9,17 * * *" },
  { label: "Le 1er de chaque mois à minuit", value: "0 0 1 * *" },
  { label: "Toutes les 15 minutes", value: "*/15 * * * *" },
  { label: "Tous les jours ouvrables à 2h", value: "0 2 * * 1-5" },
  { label: "Personnalisé", value: "custom" },
];

const ExecutionWizard: React.FC<ExecutionWizardProps> = ({ action, onClose }) => {
  // Existing state from Story 11.7
  const [schedulingType, setSchedulingType] = useState<'one-time' | 'daily' | 'weekly' | 'cron'>('one-time');

  // New state for cron pattern
  const [cronExpression, setCronExpression] = useState<string>('');
  const [cronIsValid, setCronIsValid] = useState<boolean | null>(null);
  const [cronError, setCronError] = useState<string>('');
  const [nextExecutions, setNextExecutions] = useState<string[]>([]);
  const [validating, setValidating] = useState<boolean>(false);
  const [showCronHelper, setShowCronHelper] = useState<boolean>(false);

  // Debounced validation of cron expression
  const validateCronDebounced = useCallback(
    debounce(async (expression: string) => {
      if (!expression) {
        setCronIsValid(null);
        setNextExecutions([]);
        return;
      }

      setValidating(true);

      try {
        // Validate expression
        const validation = await validateCronExpression(expression);

        if (validation.valid) {
          setCronIsValid(true);
          setCronError('');

          // Get next executions for preview
          const nextExecs = await getCronNextExecutions(expression, 5);
          setNextExecutions(nextExecs);
        } else {
          setCronIsValid(false);
          setCronError(validation.error || 'Expression cron invalide');
          setNextExecutions([]);
        }
      } catch (error: any) {
        setCronIsValid(false);
        setCronError(error.message || 'Erreur de validation');
        setNextExecutions([]);
      } finally {
        setValidating(false);
      }
    }, 500),
    []
  );

  const handleCronChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const expression = e.target.value;
    setCronExpression(expression);
    validateCronDebounced(expression);
  };

  const handleCronPresetChange = (value: string) => {
    if (value === 'custom') {
      setCronExpression('');
      setCronIsValid(null);
      setNextExecutions([]);
    } else {
      setCronExpression(value);
      validateCronDebounced(value);
    }
  };

  const handleSchedule = async () => {
    if (!isScheduling) {
      // Immediate execution (existing logic)
      await executeAction();
    } else {
      // Scheduled execution
      let recurringPattern: RecurringPatternRequest | undefined;

      if (schedulingType === 'cron') {
        if (!cronIsValid || !cronExpression) {
          notification.error({
            message: 'Erreur',
            description: 'L\'expression cron est invalide ou manquante',
          });
          return;
        }

        recurringPattern = {
          pattern_type: 'cron',
          pattern_config: {
            cron_expression: cronExpression,
          },
        };
      }
      // ... existing logic for daily/weekly/one-time

      await createScheduledExecution({
        action_id: action.id,
        environment: selectedEnvironment,
        parameters: formData,
        scheduled_at: schedulingType === 'one-time' ? scheduledDateTime?.toISOString() : undefined,
        recurring_pattern: recurringPattern,
      });

      notification.success({
        message: 'Exécution planifiée',
        description: recurringPattern
          ? 'L\'exécution récurrente a été créée avec succès'
          : `Exécution planifiée pour le ${scheduledDateTime?.format('DD/MM/YYYY à HH:mm')}`,
      });

      onClose();
    }
  };

  return (
    <Modal>
      {/* Step 3: Confirmation & Scheduling */}
      {currentStep === 2 && (
        <div>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button onClick={handleSchedule}>Exécuter maintenant</Button>
            <Button onClick={() => setIsScheduling(true)}>Planifier</Button>

            {isScheduling && (
              <div>
                <Radio.Group
                  value={schedulingType}
                  onChange={(e) => setSchedulingType(e.target.value)}
                >
                  <Radio value="one-time">Une seule fois</Radio>
                  <Radio value="daily">Tous les jours</Radio>
                  <Radio value="weekly">Toutes les semaines</Radio>
                  <Radio value="cron">Avancé (cron)</Radio>
                </Radio.Group>

                {/* Existing one-time, daily, weekly UI from Story 11.7 */}

                {schedulingType === 'cron' && (
                  <Card title="Expression Cron" size="small" style={{ marginTop: 16 }}>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {/* Presets */}
                      <Select
                        placeholder="Expressions courantes"
                        onChange={handleCronPresetChange}
                        style={{ width: '100%' }}
                      >
                        {CRON_PRESETS.map((preset) => (
                          <Select.Option key={preset.value} value={preset.value}>
                            {preset.label}
                          </Select.Option>
                        ))}
                      </Select>

                      {/* Cron expression input */}
                      <Input
                        placeholder="Ex: 0 2 * * 1-5"
                        value={cronExpression}
                        onChange={handleCronChange}
                        suffix={
                          validating ? (
                            <LoadingOutlined />
                          ) : cronIsValid === true ? (
                            <CheckCircleOutlined style={{ color: '#52c41a' }} />
                          ) : cronIsValid === false ? (
                            <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                          ) : null
                        }
                        addonAfter={
                          <Tooltip title="Format: minute hour day month day_of_week">
                            <QuestionCircleOutlined onClick={() => setShowCronHelper(true)} />
                          </Tooltip>
                        }
                      />

                      {/* Error message */}
                      {cronIsValid === false && (
                        <Alert message={cronError} type="error" showIcon />
                      )}

                      {/* Next executions preview */}
                      {cronIsValid === true && nextExecutions.length > 0 && (
                        <Card size="small" title="Prochaines exécutions">
                          {nextExecutions.map((exec, idx) => (
                            <div key={idx}>
                              {dayjs(exec).format('DD/MM/YYYY à HH:mm')} (UTC)
                            </div>
                          ))}
                        </Card>
                      )}

                      {/* Helper link */}
                      <Button
                        type="link"
                        href="https://crontab.guru/"
                        target="_blank"
                        icon={<QuestionCircleOutlined />}
                      >
                        Assistant cron (crontab.guru)
                      </Button>
                    </Space>
                  </Card>
                )}
              </div>
            )}
          </Space>
        </div>
      )}

      {/* Cron Helper Modal */}
      <CronExpressionHelper
        visible={showCronHelper}
        onClose={() => setShowCronHelper(false)}
      />
    </Modal>
  );
};
```

**Pattern 5 : Helper pour description lisible des expressions cron**

Source : Nouveau fichier `/idp-portal/frontend/src/utils/cronHelper.ts`

```typescript
// frontend/src/utils/cronHelper.ts

/**
 * Generate human-readable description for a cron expression.
 *
 * @param expression - Cron expression (5 fields)
 * @returns Human-readable description in French
 */
export function describeCronExpression(expression: string): string {
  try {
    const parts = expression.trim().split(/\s+/);

    if (parts.length !== 5) {
      return expression; // Return raw if not 5 fields
    }

    const [minute, hour, day, month, dow] = parts;

    // Common patterns
    if (expression === "0 2 * * *") return "Tous les jours à 2h00";
    if (expression === "0 14 * * 1") return "Tous les lundis à 14h00";
    if (expression === "0 0 1 * *") return "Le 1er de chaque mois à minuit";
    if (expression === "*/15 * * * *") return "Toutes les 15 minutes";
    if (expression === "0 2 * * 1-5") return "Tous les jours ouvrables à 2h00";
    if (expression === "0 9,17 * * *") return "Tous les jours à 9h00 et 17h00";
    if (expression === "0 9,17 * * 1-5") return "Jours ouvrables à 9h00 et 17h00";

    // Build description dynamically
    let description = "";

    // Frequency (day of week or day of month)
    if (dow !== "*") {
      const dayNames: Record<string, string> = {
        "0": "dimanche",
        "1": "lundi",
        "2": "mardi",
        "3": "mercredi",
        "4": "jeudi",
        "5": "vendredi",
        "6": "samedi",
        "1-5": "jours ouvrables",
        "0,6": "week-ends",
      };
      description += `Tous les ${dayNames[dow] || dow}`;
    } else if (day !== "*") {
      if (day === "1") {
        description += "Le 1er de chaque mois";
      } else {
        description += `Le ${day} de chaque mois`;
      }
    } else {
      description += "Tous les jours";
    }

    // Time (hour:minute)
    if (hour.startsWith("*/")) {
      const interval = hour.substring(2);
      description += ` toutes les ${interval} heures`;
    } else if (hour.includes(",")) {
      const hours = hour.split(",").join("h, ") + "h";
      description += ` à ${hours}`;
    } else if (hour !== "*") {
      const hourFormatted = hour.padStart(2, "0");
      const minuteFormatted = minute.padStart(2, "0");
      description += ` à ${hourFormatted}h${minuteFormatted}`;
    } else if (minute.startsWith("*/")) {
      const interval = minute.substring(2);
      description += ` toutes les ${interval} minutes`;
    }

    return description;
  } catch (e) {
    // Fallback: return raw expression
    return expression;
  }
}
```

**Pattern 6 : Extension de ScheduledExecutionsPage pour affichage cron**

Source : Extension de `/idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx`

```tsx
// frontend/src/components/admin/ScheduledExecutionsPage.tsx

// Helper function (extended from Story 11.7)
const formatRecurrenceDisplay = (recurringPattern: RecurringPatternResponse): string => {
  if (recurringPattern.pattern_type === 'daily') {
    const { hour, minute } = recurringPattern.pattern_config;
    return `Tous les jours à ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} (UTC)`;
  } else if (recurringPattern.pattern_type === 'weekly') {
    const { day_of_week, hour, minute } = recurringPattern.pattern_config;
    const dayNames = {
      1: 'lundis',
      2: 'mardis',
      3: 'mercredis',
      4: 'jeudis',
      5: 'vendredis',
      6: 'samedis',
      7: 'dimanches',
    };
    const dayName = dayNames[day_of_week as keyof typeof dayNames];
    return `Tous les ${dayName} à ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} (UTC)`;
  } else if (recurringPattern.pattern_type === 'cron') {
    // NEW for Story 11.8
    const cronExpr = recurringPattern.pattern_config.cron_expression;
    const description = describeCronExpression(cronExpr);
    return `Récurrence : ${cronExpr} (${description})`;
  }
  return '';
};

const columns: ColumnsType<ScheduledExecutionListItem> = [
  {
    title: 'Type',
    key: 'type',
    render: (_, record) => {
      if (record.recurring_pattern) {
        if (record.recurring_pattern.pattern_type === 'cron') {
          return <Badge color="purple" text="Récurrent - Cron" />;
        }
        return <Badge status="processing" text="Récurrent" />;
      }
      return <Badge status="default" text="Unique" />;
    },
  },
  // ... other columns
];

// Details modal (extended from Story 11.7)
const DetailsModal = ({ selectedExecution, visible, onClose }) => {
  const [nextExecutions, setNextExecutions] = useState<string[]>([]);

  useEffect(() => {
    if (selectedExecution?.recurring_pattern?.pattern_type === 'cron') {
      // Fetch next 3 executions for cron patterns
      const cronExpr = selectedExecution.recurring_pattern.pattern_config.cron_expression;
      getCronNextExecutions(cronExpr, 3).then((execs) => {
        setNextExecutions(execs);
      });
    }
  }, [selectedExecution]);

  return (
    <Modal
      title="Détails de l'exécution planifiée"
      open={visible}
      onCancel={onClose}
      footer={[...]} // Same as Story 11.7
      width={700}
    >
      {selectedExecution && (
        <Descriptions column={1} bordered size="small">
          {/* Existing fields ... */}

          {selectedExecution.recurring_pattern?.pattern_type === 'cron' && (
            <>
              <Descriptions.Item label="Type">
                Récurrent - Cron
              </Descriptions.Item>
              <Descriptions.Item label="Expression cron">
                <code>{selectedExecution.recurring_pattern.pattern_config.cron_expression}</code>
              </Descriptions.Item>
              <Descriptions.Item label="Description">
                {describeCronExpression(selectedExecution.recurring_pattern.pattern_config.cron_expression)}
              </Descriptions.Item>
              <Descriptions.Item label="Prochaines exécutions">
                {nextExecutions.map((exec, idx) => (
                  <div key={idx}>
                    {dayjs(exec).format('DD/MM/YYYY à HH:mm')} (UTC)
                  </div>
                ))}
              </Descriptions.Item>
              <Descriptions.Item label="Statut">
                {selectedExecution.recurring_pattern.is_active ? (
                  <Badge status="success" text="Actif" />
                ) : (
                  <Badge status="default" text="Désactivé" />
                )}
              </Descriptions.Item>
            </>
          )}

          {/* Existing daily/weekly display from Story 11.7 */}
        </Descriptions>
      )}
    </Modal>
  );
};
```

### Source tree components to touch

**Fichiers à créer :**
```
idp-portal/backend/tests/unit/test_recurrence_cron.py                   # Tests unitaires calcul cron (15+ tests)
idp-portal/backend/tests/integration/test_scheduled_executions_cron_api.py  # Tests API cron (13+ tests)
idp-portal/frontend/src/components/common/CronExpressionHelper.tsx      # Modal helper pour comprendre cron
idp-portal/frontend/src/utils/cronHelper.ts                             # Helper description lisible cron
idp-portal/frontend/src/services/__tests__/scheduled_execution_service_cron.test.ts  # Tests service cron (10+ tests)
```

**Fichiers à modifier :**
```
idp-portal/backend/pyproject.toml                                       # Ajouter croniter>=3.0
idp-portal/backend/app/models/scheduled_execution.py                    # Ajouter CronPatternConfig, étendre RecurringPatternType
idp-portal/backend/app/utils/recurrence.py                              # Ajouter _calculate_cron_next_execution
idp-portal/backend/app/api/v1/scheduled_executions.py                   # Ajouter endpoints validate-cron, cron-next-executions
idp-portal/backend/app/repositories/scheduled_execution_repository.py   # Aucune modification (supporte déjà cron via CLOB JSON)
idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx          # Ajouter option "cron", presets, validation temps réel
idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx    # Afficher badge violet, modal détails cron
idp-portal/frontend/src/services/scheduled_execution_service.ts         # Ajouter validateCronExpression, getCronNextExecutions
idp-portal/frontend/src/types/api.ts                                    # Étendre RecurringPatternType avec "cron"
```

**Fichiers de référence (patterns) :**
```
idp-portal/backend/app/utils/recurrence.py                              # Pattern calcul daily/weekly (Story 11.7)
idp-portal/backend/app/api/v1/scheduled_executions.py                   # Pattern API validation (Story 11.3, 11.7)
idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx          # Pattern Radio.Group, Select (Story 11.7)
idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx    # Pattern liste, modal détails (Story 11.7)
```

### Testing standards summary

**Tests backend (pytest) :**

1. **Tests unitaires (test_recurrence_cron.py) :**
   - `test_calculate_cron_weekdays_2am` - "0 2 * * 1-5" → prochain jour ouvrable à 2h
   - `test_calculate_cron_first_of_month` - "0 0 1 * *" → prochain 1er du mois
   - `test_calculate_cron_every_15_minutes` - "*/15 * * * *" → prochain multiple de 15 min
   - `test_calculate_cron_complex_expression` - "0 9,17 * * 1-5" → jours ouvrables 9h et 17h
   - `test_calculate_cron_before_time_same_day` - Si créé avant l'heure → aujourd'hui
   - `test_calculate_cron_after_time_next_occurrence` - Si créé après → prochaine occurrence
   - `test_invalid_cron_raises_error` - "99 99 * * *" → ValueError
   - `test_invalid_cron_format_raises_error` - "invalid cron" → ValueError
   - `test_cron_missing_expression_raises_error` - pattern_config sans cron_expression → ValueError
   - `test_cron_expression_empty_raises_error` - cron_expression="" → ValueError
   - `test_increment_cron_next_execution` - increment_next_execution_date pour cron

2. **Tests intégration (test_scheduled_executions_cron_api.py) :**
   - `test_create_cron_recurring_execution` - POST avec pattern cron → 201, RECURRING_PATTERNS créée
   - `test_cron_pattern_validation_invalid_expression` - POST avec "99 99 * * *" → 400
   - `test_cron_execution_has_null_scheduled_at` - Vérifie scheduled_at=NULL pour cron
   - `test_list_includes_cron_patterns` - GET /scheduled-executions inclut recurring_pattern cron
   - `test_audit_log_cron_created` - Vérifie SCHEDULED_EXECUTION_RECURRING_CREATED
   - `test_validate_cron_endpoint_valid` - GET /validate-cron?expression=0 2 * * * → {"valid": true}
   - `test_validate_cron_endpoint_invalid` - GET /validate-cron?expression=99 99 * * * → {"valid": false}
   - `test_cron_next_executions_endpoint` - GET /cron-next-executions?expression=...&count=5 → {"executions": [...]}
   - `test_cron_next_executions_endpoint_invalid` - Endpoint avec expression invalide → erreur
   - `test_disable_cron_pattern` - PATCH is_active=false pour cron → is_active=false
   - `test_enable_cron_pattern_recalculates_next` - PATCH is_active=true → next_execution_date recalculé
   - `test_cron_pattern_missing_expression` - POST sans cron_expression → 400
   - `test_audit_log_cron_disabled` - Vérifie SCHEDULED_EXECUTION_RECURRING_DISABLED

**Tests frontend (vitest + React Testing Library) :**

1. `test_wizard_shows_cron_option` - Radio.Group affiche "Avancé (cron)"
2. `test_wizard_cron_selected_shows_input` - Cron sélectionné → Input et Select presets affichés
3. `test_cron_presets_populate_input` - Sélection preset "Chaque jour à 02:00" → champ rempli avec "0 2 * * *"
4. `test_cron_validation_valid_expression` - Expression valide "0 2 * * 1-5" → checkmark vert + prochaines exécutions
5. `test_cron_validation_invalid_expression` - Expression invalide "99 99 * * *" → erreur affichée, bouton désactivé
6. `test_cron_next_executions_displayed` - Expressions valides → Card "Prochaines exécutions" affiche 5 dates
7. `test_create_cron_execution_api_called` - Clic confirmer avec cron → API appelée avec recurring_pattern cron
8. `test_cron_helper_modal_opens` - Clic "?" → modal CronExpressionHelper s'ouvre
9. `test_list_displays_cron_badge` - Badge "Récurrent - Cron" en violet affiché pour cron patterns
10. `test_list_displays_cron_expression` - Liste affiche "Récurrence : 0 2 * * 1-5"
11. `test_details_modal_shows_cron_info` - Modal affiche expression cron, description lisible, prochaines 3 exécutions
12. `test_describe_cron_expression_common_patterns` - Helper génère descriptions correctes
13. `test_validate_cron_service` - Service validateCronExpression appelle endpoint correct
14. `test_get_cron_next_executions_service` - Service getCronNextExecutions retourne tableau de dates

**Validation manuelle :**
1. Installer croniter : `pip install croniter>=3.0`
2. Tester création cron "0 2 * * 1-5" → succès, prochaines exécutions affichées
3. Tester validation "99 99 * * *" → erreur 400 backend, erreur affichée frontend
4. Tester presets → sélection remplit champ automatiquement, validation se déclenche
5. Tester preview 5 prochaines exécutions → dates correctes, format DD/MM/YYYY HH:mm (UTC)
6. Tester modal helper → tableau champs, exemples, lien crontab.guru
7. Tester coexistence daily/weekly/cron dans la liste → badges distincts (bleu vs violet)
8. Tester modal détails cron → expression, description lisible, 3 prochaines exécutions
9. Tester désactivation/réactivation cron → is_active change, next_execution_date recalculé
10. Vérifier audit logs → SCHEDULED_EXECUTION_RECURRING_CREATED, DISABLED, ENABLED
11. Tester expressions complexes : "*/15 * * * *", "0 9,17 * * 1-5", "0 0 1 * *"

### Learnings from previous stories (11-1, 11-3, 11-5, 11-6, 11-7)

**Story 11.1 (Modèle de données) :**
- Table RECURRING_PATTERNS déjà créée avec support pour daily, weekly, **cron**
- PATTERN_CONFIG est CLOB JSON → **flexible pour tout type de config**, pas besoin de migration
- Index composite `(IS_ACTIVE, NEXT_EXECUTION_DATE)` optimisé pour scheduler externe
- Relation 1-to-0..1 avec UNIQUE constraint sur SCHEDULED_EXECUTION_ID

**Story 11.3 (API création one-time) :**
- Validation timezone obligatoire avec Pydantic
- Deep copy de schema pour éviter mutations
- Correlation ID pour tracing distribué
- Audit logging systématique pour toutes les opérations
- Log validation failures pour debugging

**Story 11.5 (UI scheduler wizard) :**
- DatePicker avec showTime nécessite plugin dayjs utc
- DisabledDate validation côté client + validation côté serveur
- Format date : `DD/MM/YYYY HH:mm` pour affichage, ISO 8601 pour API
- Messages d'erreur en français, user-friendly
- 45 tests pour couverture complète

**Story 11.6 (Liste et annulation) :**
- Pattern Table avec filtres réutilisable pour affichage récurrences
- RBAC : DBA voit ses propres, DBOPS voit toutes
- JOIN avec ACTIONS_CATALOG et USERS pour enrichissement
- Modal détails avec toutes les informations
- Correlation ID et execution_id ajoutés

**Story 11.7 (Patterns daily/weekly) :**
- Calcul next_execution_date en backend avec datetime.timezone.utc
- Pattern Radio.Group pour choix du type de récurrence
- Validation stricte des valeurs (hour 0-23, minute 0-59, day_of_week 1-7)
- Tests complets : 22 unitaires + 14 intégration + 9 frontend
- Activation/désactivation avec recalcul next_execution_date

**Patterns à éviter :**
- ❌ Ne pas oublier validation cron_expression avant création
- ❌ Ne pas utiliser scheduled_at pour récurrences (doit être NULL)
- ❌ Ne pas calculer next_execution_date côté frontend (toujours backend)
- ❌ Ne pas oublier de recalculer next_execution_date lors de la réactivation
- ❌ Ne pas utiliser timezone locale (toujours UTC)
- ❌ Ne pas parser manuellement les expressions cron (utiliser croniter)

**Patterns à suivre :**
- ✅ Utiliser croniter pour validation et calcul (pas de parsing manuel)
- ✅ Validation syntaxique ET sémantique avec `croniter.is_valid()` + `get_next()`
- ✅ Preview des prochaines exécutions pour validation visuelle utilisateur
- ✅ Presets d'expressions courantes pour éviter erreurs utilisateur
- ✅ Helper/documentation intégrée pour comprendre le format cron
- ✅ Audit log pour toutes les opérations (created, disabled, enabled)
- ✅ Tests complets (unitaires + intégration + frontend)
- ✅ Coexistence avec daily/weekly (badges distincts, logique séparée)

**Learnings spécifiques croniter :**
- `croniter.is_valid(expression)` valide syntaxe ET sémantique
- `croniter(expression, reference).get_next(datetime)` retourne datetime objet
- Gère automatiquement UTC si reference_datetime a timezone
- Support expressions 5 champs (standard cron) : minute hour day month dow
- Exceptions : ValueError (syntaxe invalide), KeyError (valeurs out of range)

### Project Structure Notes

**Alignement avec unified project structure :**
- Frontend React : `/idp-portal/frontend/src/` (components/catalog, components/admin, components/common, services, types, utils)
- Tests frontend : Co-localisés avec composant ou dans `__tests__/`
- Backend FastAPI : `/idp-portal/backend/app/` (api/v1, repositories, models, utils/recurrence.py)
- Tests backend : `/idp-portal/backend/tests/` (unit/test_recurrence_cron.py, integration/test_scheduled_executions_cron_api.py)
- Migrations Oracle : `/idp-portal/database/migrations/` (V038 déjà créée en Story 11.1, **aucune nouvelle migration requise**)

**Conventions de nommage :**
- TypeScript : camelCase (variables locales), PascalCase (composants, interfaces)
- Fichiers composants : PascalCase.tsx (`ExecutionWizard.tsx`, `CronExpressionHelper.tsx`)
- Fichiers services : snake_case.ts (`scheduled_execution_service.ts`)
- Fichiers utils : camelCase.ts (`cronHelper.ts`)
- API JSON fields : snake_case (`recurring_pattern`, `pattern_type`, `cron_expression`)
- Props React : camelCase (`onClose`, `recurringPattern`, `cronExpression`)
- Python : snake_case pour tout (fonctions, variables, modules)

**Detected conflicts or variances :**
- ✅ Aucun conflit - Cette story étend Story 11.7 sans modifier daily/weekly
- ✅ Pattern cohérent avec approche externe scheduler (NEXT_EXECUTION_DATE calculé backend)
- ✅ Réutilise les patterns de validation et audit établis en Stories 11.3, 11.6, 11.7
- ✅ Suit le pattern wizard existant (Radio.Group pour choix, Input pour cron)
- ✅ Badge distinct (violet) pour différencier cron des patterns simples (bleu)
- ⚠️ **Attention** : Expression cron doit être validée avec croniter AVANT création (erreur 400 si invalide)
- ⚠️ **Attention** : Helper description lisible peut ne pas couvrir toutes les expressions complexes → fallback à expression brute
- ⚠️ **Attention** : Presets facilitent la saisie mais ne couvrent pas tous les cas → option "Personnalisé" obligatoire
- ⚠️ **Attention** : Format cron standard 5 champs (pas 6 avec secondes) → documenter dans helper

### References

**Epic et stories connexes :**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 11] - Contexte complet Epic 11 Scheduling
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.1] - Modèle de données SCHEDULED_EXECUTIONS et RECURRING_PATTERNS
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.3] - API créer exécution planifiée one-time
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.5] - UI scheduler dans wizard execution
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.6] - Liste des exécutions planifiées et annulation
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.7] - Patterns de récurrence simples (daily/weekly)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.8] - Cron expressions pour récurrence avancée (cette story)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.10] - API integration scheduler externe (next story)

**Architecture et patterns :**
- [Source: idp-portal/backend/app/utils/recurrence.py:1-586] - Pattern calcul next_execution_date (Story 11.7)
- [Source: idp-portal/backend/app/api/v1/scheduled_executions.py:1-903] - Pattern API avec validation et RBAC
- [Source: idp-portal/backend/app/models/scheduled_execution.py:1-460] - Modèles Pydantic pour scheduled executions
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx:1-1063] - Pattern wizard avec Radio.Group
- [Source: idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx:1-1225] - Pattern liste et modal détails
- [Source: idp-portal/backend/app/repositories/scheduled_execution_repository.py:1-842] - Pattern repository avec CLOB JSON

**Stories récentes (context et patterns) :**
- [Source: _bmad-output/implementation-artifacts/11-7-patterns-recurrence-simples-daily-weekly.md] - Story précédente (daily/weekly)
- [Source: _bmad-output/implementation-artifacts/11-6-liste-executions-planifiees-et-annulation.md] - Liste et annulation
- [Source: _bmad-output/implementation-artifacts/11-5-ui-scheduler-dans-wizard-execution.md] - UI scheduling dans wizard
- [Source: _bmad-output/implementation-artifacts/11-3-api-creer-execution-planifiee-one-time.md] - API création scheduled execution
- [Source: _bmad-output/implementation-artifacts/11-1-modele-donnees-scheduled-executions-et-recurrence.md] - Modèle de données

**Commits récents (Git intelligence) :**
- Commit `bda6f78` : feat(scheduling): add daily and weekly recurring patterns (story 11-7)
  - Fichiers : recurrence.py (_calculate_daily/weekly_next_execution), API POST/PATCH, ExecutionWizard (Radio.Group), ScheduledExecutionsPage (formatRecurrenceDisplay)
  - Learnings : Calcul next_execution_date avec datetime.timezone.utc, validation pattern_config, tests complets
- Commit `e286f13` : feat(scheduling): add scheduled executions list and cancellation (story 11-6)
  - Fichiers : ScheduledExecutionsPage.tsx, API GET/PATCH, repository list/cancel
  - Learnings : RBAC filtering, enriched JOINs, modal détails complets
- Commit `078b814` : feat(scheduling): add schedule option in execution wizard (story 11-5)
  - Fichiers : ExecutionWizard.tsx (DatePicker, validation)
  - Learnings : Pattern DatePicker avec timezone, validation date future
- Commit `316cdd2` : feat(scheduling): add one-time scheduled execution API (story 11-3)
  - Learnings : Validation timezone, correlation_id, audit logging
- Commit `40cff25` : feat(scheduling): add scheduled executions data model with recurrence support (story 11-1)
  - Migration V038 : Tables SCHEDULED_EXECUTIONS et RECURRING_PATTERNS avec index optimisés, PATTERN_CONFIG CLOB JSON flexible

**Bibliothèques utilisées :**
- **Backend** : FastAPI, Pydantic, python-oracledb, datetime (timezone.utc), structlog, jsonschema, **croniter 3.0+** (nouveau)
- **Frontend** : React, Ant Design (Radio, Select, Input, Card, Alert, Modal, Badge, Tooltip), dayjs, TypeScript, lodash (debounce)
- **Tests** : pytest, pytest-asyncio, vitest, @testing-library/react

**Ressources techniques cron :**
- [croniter · PyPI](https://pypi.org/project/croniter/) - Bibliothèque Python pour parsing cron
- [Crontab.guru](https://crontab.guru/) - Outil interactif pour comprendre et tester expressions cron
- [NG-ZORRO CronExpression](https://ng.ant.design/experimental/cron-expression/en) - Exemple de composant UI pour cron
- [react-js-cron](https://github.com/xrutayisire/react-js-cron) - Composant React pour expressions cron

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5-20250929

### Debug Log References

N/A

### Completion Notes List

Story créée avec contexte complet via analyse exhaustive du codebase et recherche web (agent Explore).

**Contexte analysé :**
- Modèle de données V038 (SCHEDULED_EXECUTIONS, RECURRING_PATTERNS avec support cron)
- API existante POST /api/v1/scheduled-executions (Story 11.3)
- Calcul next_execution_date existant (recurrence.py, Story 11.7)
- UI ExecutionWizard avec Radio.Group (Story 11.7)
- Liste ScheduledExecutionsPage avec modal détails (Story 11.6, 11.7)
- Patterns de validation, RBAC, audit, tests

**Recherche technique effectuée :**
- Comparaison bibliothèques Python : **croniter (recommandé)** vs cron-converter
- Best practices 2026 pour parsing cron en Python
- UI/UX patterns pour input cron : presets, validation temps réel, preview
- Helper patterns : crontab.guru style, description lisible

**Approche recommandée :**
1. Installer croniter dans backend (pyproject.toml)
2. Étendre modèles Pydantic avec CronPatternConfig + validation
3. Étendre recurrence.py avec _calculate_cron_next_execution utilisant croniter
4. Créer endpoints backend : validate-cron, cron-next-executions
5. Étendre ExecutionWizard : option "cron", presets, Input avec validation temps réel
6. Créer CronExpressionHelper modal avec exemples et documentation
7. Étendre ScheduledExecutionsPage : badge violet, affichage expression + description
8. Créer helper describeCronExpression pour description lisible
9. Tests complets : 15+ unitaires + 13+ intégration + 10+ frontend

**Points critiques :**
- Validation avec `croniter.is_valid()` avant création (AC5)
- Calcul next_execution_date avec `croniter().get_next(datetime)` (AC6)
- Preview des 5 prochaines exécutions pour validation visuelle (AC2)
- Presets d'expressions courantes pour faciliter la saisie (AC3)
- Coexistence avec daily/weekly : badges distincts, logique séparée (AC12)
- Audit logging pour created, disabled, enabled (AC11)

**Dépendances techniques :**
- croniter>=3.0 (à installer dans backend/pyproject.toml)
- lodash (déjà présent) pour debounce validation temps réel
- Ant Design components : Input, Select, Card, Alert, Modal, Badge, Tooltip

**Compatibilité :**
- ✅ Coexiste avec daily/weekly (Story 11.7) sans modification
- ✅ Utilise PATTERN_CONFIG CLOB JSON existant (pas de migration)
- ✅ Réutilise endpoints PATCH toggle existants (Story 11.7)
- ✅ Suit les mêmes patterns de validation, RBAC, audit

### File List

**Fichiers créés :**
- `idp-portal/backend/tests/unit/test_recurrence_cron.py` - Tests unitaires calcul cron (20 tests - ALL PASS ✅)
- `idp-portal/backend/tests/integration/test_scheduled_executions_cron_api.py` - Tests API cron (14 tests - ALL PASS ✅)
- `idp-portal/frontend/src/components/shared/CronExpressionHelper.tsx` - Modal helper cron (⚠️ Note: shared/ not common/)
- `idp-portal/frontend/src/utils/cronHelper.ts` - Helper description lisible
- `idp-portal/frontend/src/utils/cronHelper.test.ts` - Tests helper (26 tests - ALL PASS ✅)

**Fichiers à modifier :**
- `idp-portal/backend/pyproject.toml` - Ajouter croniter>=3.0
- `idp-portal/backend/app/models/scheduled_execution.py` - CronPatternConfig, RecurringPatternType.CRON
- `idp-portal/backend/app/utils/recurrence.py` - _calculate_cron_next_execution
- `idp-portal/backend/app/api/v1/scheduled_executions.py` - Endpoints validate-cron, cron-next-executions
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` - Option cron, presets, validation temps réel
- `idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx` - Badge violet, affichage cron
- `idp-portal/frontend/src/services/scheduled_execution_service.ts` - validateCronExpression, getCronNextExecutions
- `idp-portal/frontend/src/types/api.ts` - Étendre RecurringPatternType
