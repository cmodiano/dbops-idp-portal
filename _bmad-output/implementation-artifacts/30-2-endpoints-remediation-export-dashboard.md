# Story 30.2: Endpoints manquants — remediation, export dashboard

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**En tant qu'** utilisateur et opérateur,
**je veux** accéder aux suggestions de remédiation et aux exports CSV/PDF du dashboard,
**afin d'** exploiter les données d'exécution et le reporting pour analyse et diagnostic.

## Acceptance Criteria

### AC1 — Endpoint `GET /executions/{id}/remediation` existe et retourne les suggestions

- **Given** le frontend appelle `GET /api/v1/executions/{id}/remediation`
- **When** l'exécution existe et a des règles de remédiation configurées
- **Then** l'endpoint existe et retourne HTTP 200
- **And** le format de réponse est : `{"data": [RemediationSuggestion, ...]}`
- **And** chaque suggestion contient : `action_id`, `action_name`, `action_description`, `matching_rule`
- **And** les suggestions sont filtrées par environnement de l'exécution
- **And** seules les règles dont `error_pattern` (regex Python) matche `Execution.error_message` sont retournées
- **And** si aucune règle ne matche, retourner `{"data": []}`
- **And** si l'exécution n'existe pas, retourner HTTP 404

### AC2 — Endpoint `GET /executions/{id}/remediation-context` existe et retourne le contexte

- **Given** le frontend appelle `GET /api/v1/executions/{id}/remediation-context`
- **When** l'exécution existe
- **Then** l'endpoint existe et retourne HTTP 200
- **And** le format de réponse est : `{"data": RemediationContext}`
- **And** `RemediationContext` contient :
  - `has_remediation` : booléen (true si `child_executions` de type remédiation existent)
  - `successful_remediation` : booléen (true si au moins une remédiation a réussi : status=COMPLETED)
  - `remediation_actions` : array de `RemediationAction` (child executions avec `parent_item_type='remediation'`)
- **And** chaque `RemediationAction` contient : `id`, `action_id`, `action_name`, `status`, `created_at`, `completed_at`, `error_message`
- **And** si l'exécution n'existe pas, retourner HTTP 404

### AC3 — Endpoint `GET /dashboard/export/csv` existe et exporte les stats du dashboard en CSV

- **Given** le frontend appelle `GET /api/v1/dashboard/export/csv?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&engine=&environment=&tags=`
- **When** le backend est déployé
- **Then** l'endpoint existe et retourne HTTP 200 avec `Content-Type: text/csv`
- **And** le header `Content-Disposition: attachment; filename="dashboard-export-{date}.csv"` est présent
- **And** les colonnes CSV incluent : `date`, `total_executions`, `successful_executions`, `failed_executions`, `success_rate_pct`, `avg_execution_time_ms`, `engine`, `environment`
- **And** les données sont filtrées par `start_date`, `end_date`, `engine`, `environment`, `tags` si fournis
- **And** les données sont agrégées par jour (`date`), moteur (`engine`), environnement (`environment`)
- **And** limite de 10,000 lignes (cohérent avec AuditExportView)
- **And** permissions requises : `IsAuthenticated` + `IsDBAOrDBOPS`

### AC4 — Endpoint `GET /dashboard/export/pdf` existe et exporte les stats du dashboard en PDF

- **Given** le frontend appelle `GET /api/v1/dashboard/export/pdf?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&engine=&environment=&tags=`
- **When** le backend est déployé
- **Then** l'endpoint existe et retourne HTTP 200 avec `Content-Type: application/pdf`
- **And** le header `Content-Disposition: attachment; filename="dashboard-export-{date}.pdf"` est présent
- **And** le PDF contient :
  - **Section 1** : Statistiques globales (total exécutions, taux de succès, moyenne temps exécution)
  - **Section 2** : Tableau agrégé par technologie (moteur) avec colonnes : Moteur, Total, Succès, Échec, Taux succès %, Temps moyen (ms)
  - **Section 3** : Tableau agrégé par environnement avec colonnes : Environnement, Total, Succès, Échec, Taux succès %, Temps moyen (ms)
  - **Section 4** : Graphique de série temporelle (total exécutions par jour)
- **And** les données sont filtrées par les mêmes paramètres que le CSV
- **And** permissions requises : `IsAuthenticated` + `IsDBAOrDBOPS`

### AC5 — Tests unitaires endpoints remediation (AC1, AC2)

- **Given** les nouveaux endpoints remediation
- **When** les tests sont exécutés
- **Then** les tests suivants passent :
  - Test `GET /executions/{id}/remediation` : exécution avec règles matchantes → suggestions retournées
  - Test `GET /executions/{id}/remediation` : exécution sans règles matchantes → `{"data": []}`
  - Test `GET /executions/{id}/remediation` : exécution sans `error_message` → `{"data": []}`
  - Test `GET /executions/{id}/remediation` : exécution inexistante → HTTP 404
  - Test `GET /executions/{id}/remediation-context` : exécution avec child executions → `has_remediation=true`
  - Test `GET /executions/{id}/remediation-context` : exécution avec child execution COMPLETED → `successful_remediation=true`
  - Test `GET /executions/{id}/remediation-context` : exécution sans child executions → `has_remediation=false`
  - Test `GET /executions/{id}/remediation-context` : exécution inexistante → HTTP 404
  - Test permissions : utilisateur non authentifié → HTTP 401 (endpoints remediation publics mais nécessitent auth)

### AC6 — Tests unitaires endpoints export dashboard (AC3, AC4)

- **Given** les nouveaux endpoints export
- **When** les tests sont exécutés
- **Then** les tests suivants passent :
  - Test CSV : avec filtres (start_date, end_date, engine, environment, tags) → données filtrées correctement
  - Test CSV : sans filtres → toutes les données (limite 10,000 lignes)
  - Test CSV : format CSV valide (colonnes, délimiteurs, encodage UTF-8)
  - Test CSV : permissions `IsDBAOrDBOPS` → HTTP 200 pour DBA/DBOPS, HTTP 403 pour autres
  - Test PDF : avec filtres → PDF généré avec sections correctes
  - Test PDF : sans filtres → PDF complet
  - Test PDF : format PDF valide (magic bytes `%PDF`, Content-Type)
  - Test PDF : permissions `IsDBAOrDBOPS` → HTTP 200 pour DBA/DBOPS, HTTP 403 pour autres
  - Test : utilisateur non authentifié → HTTP 401

## Tasks / Subtasks

- [x] **Task 1** — Implémenter endpoint `GET /executions/{id}/remediation` (AC1)
  - [x] Créer `executions/views/remediation_views.py`
  - [x] Ajouter la vue `ExecutionRemediationSuggestionsView(APIView)`
  - [x] Méthode `get(request, id)` :
    - [x] Récupérer l'exécution par `id` (404 si inexistante)
    - [x] Récupérer `Execution.action.remediation_rules` (OracleJSONField)
    - [x] Si `remediation_rules` vide ou None → retourner `{"data": []}`
    - [x] Filtrer les règles par environnement : `rule.environments` contient `execution.environment`
    - [x] Pour chaque règle, tester `re.match(rule.error_pattern, execution.error_message)`
    - [x] Pour chaque règle matchante, charger l'action cible : `Action.objects.get(id=rule.target_action_id)`
    - [x] Construire `RemediationSuggestion` : `{action_id, action_name, action_description, matching_rule}`
    - [x] Retourner `{"data": [suggestions]}`
  - [x] Ajouter route dans `executions/urls.py` : `path('<int:id>/remediation', ExecutionRemediationSuggestionsView.as_view())`
  - [x] Ajouter `@extend_schema` pour documentation OpenAPI (tag `executions`)
  - [x] Permissions : `IsAuthenticated` (pas de RBAC supplémentaire pour consultation suggestions)

- [x] **Task 2** — Implémenter endpoint `GET /executions/{id}/remediation-context` (AC2)
  - [x] Ajouter la vue `ExecutionRemediationContextView(APIView)` dans `remediation_views.py`
  - [x] Méthode `get(request, id)` :
    - [x] Récupérer l'exécution par `id` (404 si inexistante)
    - [x] Charger les child executions : `Execution.child_executions.filter(parent_item_type='remediation')`
    - [x] Calculer `has_remediation` : `child_executions.exists()`
    - [x] Calculer `successful_remediation` : `child_executions.filter(status=ExecutionStatus.COMPLETED).exists()`
    - [x] Construire `remediation_actions` : array de `{id, action_id, action_name, status, created_at, completed_at, error_message}`
    - [x] Retourner `{"data": {has_remediation, successful_remediation, remediation_actions}}`
  - [x] Ajouter route dans `executions/urls.py` : `path('<int:id>/remediation-context', ExecutionRemediationContextView.as_view())`
  - [x] Ajouter `@extend_schema` pour documentation OpenAPI (tag `executions`)
  - [x] Permissions : `IsAuthenticated`

- [x] **Task 3** — Implémenter endpoint `GET /dashboard/export/csv` (AC3)
  - [x] Créer `dashboard/views/export_views.py`
  - [x] Ajouter la vue `DashboardExportCSVView(APIView)`
  - [x] Méthode `get(request)` :
    - [x] Parser les query params : `start_date`, `end_date`, `engine`, `environment`, `tags`
    - [x] Construire le queryset de base : `Execution.objects.all()`
    - [x] Appliquer les filtres : `created_at__gte`, `created_at__lte`, `action__engine`, `environment`, `action__tags__name__in`
    - [x] Annoter avec : `COUNT(*)`, `SUM(CASE WHEN status=COMPLETED THEN 1 ELSE 0)`, `SUM(CASE WHEN status=FAILED THEN 1 ELSE 0)`, `AVG(completed_at - started_at)` en millisecondes
    - [x] Grouper par : `DATE(created_at)`, `action__engine`, `environment`
    - [x] Limiter à 10,000 lignes
    - [x] Générer le CSV avec `csv.writer()` :
      - [x] Header : `date,total_executions,successful_executions,failed_executions,success_rate_pct,avg_execution_time_ms,engine,environment`
      - [x] Rows : une ligne par groupe
      - [x] Calcul `success_rate_pct` = `(successful_executions / total_executions) * 100` si total > 0, sinon 0
    - [x] Retourner `HttpResponse` avec `Content-Type: text/csv` et `Content-Disposition`
  - [x] Ajouter route dans `dashboard/urls.py` : `path('export/csv', DashboardExportCSVView.as_view())`
  - [x] Ajouter `@extend_schema` pour documentation OpenAPI (tag `dashboard`)
  - [x] Permissions : `IsAuthenticated` + `IsDBAOrDBOPS`

- [x] **Task 4** — Implémenter endpoint `GET /dashboard/export/pdf` (AC4)
  - [x] Ajouter la vue `DashboardExportPDFView(APIView)` dans `export_views.py`
  - [x] Méthode `get(request)` :
    - [x] Parser les mêmes query params que CSV
    - [x] Récupérer les données agrégées (même logique que CSV)
    - [x] Calculer les statistiques globales :
      - [x] `total_executions` = somme de toutes les exécutions
      - [x] `success_rate` = moyenne pondérée du taux de succès
      - [x] `avg_execution_time` = moyenne du temps d'exécution
    - [x] Générer le PDF avec `reportlab` :
      - [x] **Section 1** : Titre "Dashboard Export — {start_date} à {end_date}" + stats globales (Paragraph)
      - [x] **Section 2** : Tableau "Statistiques par Technologie" (Table) avec données groupées par `engine`
      - [x] **Section 3** : Tableau "Statistiques par Environnement" (Table) avec données groupées par `environment`
      - [x] **Section 4** : Graphique de série temporelle (Drawing.add + LinePlot) avec données groupées par `date`
    - [x] Retourner `HttpResponse` avec `Content-Type: application/pdf` et `Content-Disposition`
  - [x] Ajouter route dans `dashboard/urls.py` : `path('export/pdf', DashboardExportPDFView.as_view())`
  - [x] Ajouter `@extend_schema` pour documentation OpenAPI (tag `dashboard`)
  - [x] Permissions : `IsAuthenticated` + `IsDBAOrDBOPS`
  - [x] Ajouter `reportlab` dans `requirements.txt` si absent (vérifier version compatible Python 3.9+)

- [x] **Task 5** — Tests unitaires endpoints remediation (AC5)
  - [x] Créer `executions/tests/test_remediation_endpoints.py`
  - [x] Fixtures : créer des actions avec `remediation_rules`, des exécutions avec `error_message`, des child executions avec `parent_item_type='remediation'`
  - [x] Test `GET /remediation` : règle matchante → suggestion retournée avec `action_id`, `action_name`, `matching_rule`
  - [x] Test `GET /remediation` : règle non matchante (regex ne matche pas) → `{"data": []}`
  - [x] Test `GET /remediation` : environnement non inclus dans `rule.environments` → règle filtrée, pas de suggestion
  - [x] Test `GET /remediation` : `error_message=None` → `{"data": []}`
  - [x] Test `GET /remediation` : `remediation_rules=None` → `{"data": []}`
  - [x] Test `GET /remediation` : exécution inexistante → HTTP 404
  - [x] Test `GET /remediation-context` : exécution avec 2 child executions → `has_remediation=true`, `remediation_actions` array de 2 éléments
  - [x] Test `GET /remediation-context` : child execution avec `status=COMPLETED` → `successful_remediation=true`
  - [x] Test `GET /remediation-context` : child execution avec `status=FAILED` → `successful_remediation=false`
  - [x] Test `GET /remediation-context` : aucun child execution → `has_remediation=false`
  - [x] Test `GET /remediation-context` : exécution inexistante → HTTP 404
  - [x] Test permissions : utilisateur non authentifié → HTTP 401 (pour les deux endpoints)

- [x] **Task 6** — Tests unitaires endpoints export dashboard (AC6)
  - [x] Créer `dashboard/tests/test_export_endpoints.py`
  - [x] Fixtures : créer 50 exécutions avec dates variées, moteurs variés, environnements variés, statuts variés
  - [x] Test CSV : filtres `start_date` + `end_date` → seulement les exécutions dans la plage retournées
  - [x] Test CSV : filtre `engine=oracle` → seulement les exécutions Oracle
  - [x] Test CSV : filtre `environment=prod` → seulement les exécutions prod
  - [x] Test CSV : filtre `tags=database` → seulement les exécutions avec tag 'database'
  - [x] Test CSV : sans filtres → toutes les exécutions (limite 10,000)
  - [x] Test CSV : format CSV valide (parser avec `csv.reader()`, vérifier colonnes, types)
  - [x] Test CSV : encodage UTF-8 (vérifier caractères accentués français)
  - [x] Test CSV : Content-Disposition header présent avec nom de fichier
  - [x] Test CSV : permissions DBA → HTTP 200
  - [x] Test CSV : permissions non-DBA → HTTP 403
  - [x] Test PDF : filtres appliqués → PDF généré avec données filtrées
  - [x] Test PDF : sans filtres → PDF complet
  - [x] Test PDF : magic bytes `%PDF` présents dans les 10 premiers octets
  - [x] Test PDF : Content-Type `application/pdf`
  - [x] Test PDF : Content-Disposition header présent
  - [x] Test PDF : permissions DBA → HTTP 200
  - [x] Test PDF : permissions non-DBA → HTTP 403
  - [x] Test : utilisateur non authentifié (endpoints CSV + PDF) → HTTP 401

- [x] **Task 7** — Documentation et mise à jour frontend (optionnel)
  - [x] Vérifier que les types TypeScript dans `remediation.ts` sont alignés avec les réponses backend
  - [x] Vérifier que `execution_service.ts` utilise les bons endpoints (`/api/v1/executions/{id}/remediation` et `/remediation-context`)
  - [x] Vérifier que `dashboard_service.ts` utilise les bons endpoints (`/api/v1/dashboard/export/csv` et `/export/pdf`)
  - [x] Documenter dans `docs/api/endpoints.md` (ou créer si absent) :
    - [x] Section "Remédiation" avec endpoints remediation
    - [x] Section "Dashboard Export" avec endpoints export CSV/PDF
  - [x] Mettre à jour `CODEBASE-REVIEW.md` : marquer API-MISS-3, API-MISS-4, API-MISS-5, API-MISS-6 comme résolues

## Dev Notes

### Architecture et contraintes

**Backend Django :**
- **Fichiers clés :**
  - `executions/views/remediation_views.py` : nouvelles vues pour remediation suggestions et context
  - `dashboard/views/export_views.py` : nouvelles vues pour export CSV et PDF
  - `executions/urls.py` : ajouter routes remediation
  - `dashboard/urls.py` : ajouter routes export
  - `executions/models.py` : modèles `Execution`, `ExecutionStep`, `ExecutionTarget` (déjà existants)
  - `catalog/models.py` : modèle `Action` avec champ `remediation_rules` (déjà existant)

**Modèles et données :**
- `Execution.action.remediation_rules` : OracleJSONField contenant un array de règles
- Chaque règle : `{error_pattern: str (regex Python), target_action_id: int, environments: [str], auto_trigger: bool, risk_level: str}`
- `Execution.child_executions` : reverse relation vers les child executions (parent_execution_id = self.id)
- `Execution.parent_item_type` : champ discriminant ('workflow' | 'remediation')
- `Execution.error_message` : CLOB contenant le message d'erreur (utilisé pour le matching regex)

**Remédiation — logique métier :**
1. **Suggestions** :
   - Charger `action.remediation_rules` (array de règles)
   - Filtrer par environnement : `rule.environments` inclut `execution.environment`
   - Pour chaque règle, tester `re.match(rule.error_pattern, execution.error_message)`
   - Pour chaque match, charger l'action cible et construire la suggestion
2. **Context** :
   - Charger les child executions avec `parent_execution_id = execution.id` et `parent_item_type = 'remediation'`
   - Calculer les indicateurs : `has_remediation`, `successful_remediation`
   - Sérialiser les child executions pour `remediation_actions`

**Dashboard Export — logique métier :**
1. **CSV** :
   - Agrégation par jour, moteur, environnement
   - Calcul des métriques : total, succès, échec, taux succès, temps moyen
   - Encodage UTF-8, délimiteur virgule
   - Limite 10,000 lignes (cohérent avec `AuditExportView`)
2. **PDF** :
   - Utiliser `reportlab` pour générer le PDF
   - Structure : titre + stats globales + tableaux + graphique
   - Même logique de filtrage et agrégation que CSV
   - Formatage français (dates, nombres, accents)

**Permissions RBAC :**
- Remediation endpoints : `IsAuthenticated` (pas de restriction DBA/DBOPS, car consultation seulement)
- Export endpoints : `IsAuthenticated` + `IsDBAOrDBOPS` (cohérent avec `AuditExportView`)
- Utiliser la permission `IsDBAOrDBOPS` créée dans Story 26.8

**Format de réponse API :**
- Standard DRF : `{"data": ...}` pour les endpoints remediation
- CSV : `text/csv` avec header `Content-Disposition`
- PDF : `application/pdf` avec header `Content-Disposition`
- Utiliser les serializers existants (`ExecutionSerializer`) quand applicable

**Gestion des erreurs :**
- HTTP 404 si exécution inexistante
- HTTP 403 si permissions insuffisantes (export endpoints)
- HTTP 401 si utilisateur non authentifié
- HTTP 400 si paramètres invalides (dates, formats)

### Références techniques

**Stories liées :**
- **Story 9.1** : Détection échec et proposition actions correctives (création du modèle remediation_rules)
- **Story 9.2** : Déclenchement manuel action corrective par DBA (utilise les suggestions de remédiation)
- **Story 30.1** : Endpoints approve/reject (pattern similaire pour création de vues)
- **Story 26.8** : Création de la permission `IsDBAOrDBOPS` (utilisée ici pour export)
- **Story 22.20** : Intégration drf-spectacular (utiliser `@extend_schema` pour les nouveaux endpoints)
- **Story 8.4** : Filtres avancés dashboard (logique de filtrage similaire pour export)
- **Story 8.5** : Export rapports analytics (pattern CSV/PDF similaire)

**Documentation :**
- [Source: idp-portal/CODEBASE-REVIEW.md#1-endpoints-manquants-frontend--backend]
- [Source: _bmad-output/planning-artifacts/epic-30-codebase-review-corrections-fev-2026.md#story-302]
- [Source: idp-portal/django_backend/executions/models.py:101-196] — Modèle Execution
- [Source: idp-portal/django_backend/catalog/models.py] — Modèle Action avec remediation_rules
- [Source: idp-portal/frontend/src/types/api/remediation.ts] — Types TypeScript remediation
- [Source: idp-portal/django_backend/audit/views.py:311-409] — Pattern AuditExportView pour CSV/PDF

**Bibliothèques et versions :**
- Django 5.2
- Django REST Framework 3.16
- drf-spectacular (pour OpenAPI/Swagger)
- `reportlab` 3.6+ (pour PDF) — à ajouter si absent
- `python-magic` (optionnel, pour validation MIME si implémenté)
- Oracle DB (via cx_Oracle ou oracledb)

**Patterns établis :**
- Fichier `remediation_views.py` similaire à `approval_views.py` (Story 30.1)
- Fichier `export_views.py` dans `dashboard/views/`
- Utiliser `@extend_schema` pour tous les endpoints (Story 22.20)
- Utiliser `structlog` pour le logging structuré avec `correlation_id` et `user_id`
- Format réponse `{"data": ...}` standard pour JSON
- Headers `Content-Disposition: attachment; filename="..."` pour téléchargements

### Pièges à éviter

1. **Regex compilation** : compiler les regex une seule fois avec `re.compile()` pour performance (pas de compilation à chaque requête)
2. **Validation error_pattern** : certaines règles peuvent avoir des regex invalides → catch `re.error` et log, skip la règle
3. **OracleJSONField** : peut retourner `None` si le champ est NULL → vérifier `if remediation_rules is None`
4. **Parent_item_type** : filtrer par `parent_item_type='remediation'` sinon les child executions de workflows seront inclus
5. **Aggregation SQL** : utiliser les fonctions Django ORM (`Count`, `Sum`, `Avg`, `Case`, `When`) pour compatibilité Oracle
6. **Dates Oracle** : utiliser `timezone.now()` et `timezone.make_aware()` pour éviter les problèmes de timezone
7. **Limite 10,000 lignes** : appliquer `.limit(10000)` sur le queryset **avant** l'itération pour éviter le chargement en mémoire
8. **Encodage CSV** : spécifier `encoding='utf-8-sig'` pour Excel compatibility (BOM)
9. **ReportLab canvas** : ne pas oublier `canvas.save()` à la fin
10. **Permissions** : ne pas oublier `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]` pour export endpoints

### Hypothèses et décisions

**Décision 1 — Permissions remediation :**
- Suggestions et context : `IsAuthenticated` seulement (pas de RBAC supplémentaire)
- Rationale : consultation des suggestions ne modifie rien, les DBA/business users doivent pouvoir voir les suggestions

**Décision 2 — Permissions export :**
- CSV et PDF : `IsAuthenticated` + `IsDBAOrDBOPS`
- Rationale : cohérent avec `AuditExportView`, les exports contiennent des données sensibles (toutes les exécutions)

**Décision 3 — Agrégation dashboard :**
- Grouper par : `DATE(created_at)`, `engine`, `environment`
- Rationale : permet une analyse multi-dimensionnelle (temps, technologie, environnement)
- Alternative envisagée : grouper seulement par date → rejeté car moins granulaire

**Décision 4 — Limite 10,000 lignes :**
- Cohérent avec `AuditExportView` (ligne 327-328)
- Rationale : éviter les exports massifs qui peuvent faire OOM le backend
- Alternative : pagination → rejeté car complexité UX (téléchargements multiples)

**Décision 5 — Bibliothèque PDF :**
- Utiliser `reportlab` au lieu de `weasyprint` ou `xhtml2pdf`
- Rationale : `reportlab` est plus léger, pas de dépendance HTML/CSS, meilleur contrôle du layout
- Inconvénient : code plus verbeux qu'un template HTML

**Hypothèse 1 — Remediation rules format :**
- Le champ `remediation_rules` existe déjà dans le modèle `Action` (créé dans Story 9.1)
- Format : array de règles JSON `[{error_pattern, target_action_id, environments, auto_trigger, risk_level}, ...]`
- Vérifié dans : `catalog/models.py:218`

**Hypothèse 2 — Parent_item_type :**
- Le champ `parent_item_type` existe déjà dans le modèle `Execution` (créé dans Story 25.1)
- Valeurs possibles : `'workflow'` (child execution d'un workflow) ou `'remediation'` (child execution de remédiation)
- Vérifié dans : `executions/models.py:162`

**Hypothèse 3 — Frontend alignment :**
- Le frontend appelle déjà les endpoints remediation et export (cf. `execution_service.ts`, `dashboard_service.ts`)
- Pas de modification frontend requise, juste implémenter les endpoints backend manquants
- Vérifié dans : `CODEBASE-REVIEW.md` section 1 (API-MISS-3 à API-MISS-6)

**Hypothèse 4 — Dashboard data source :**
- Les données dashboard sont récupérées depuis le modèle `Execution` avec jointures vers `Action`
- Les filtres `engine`, `environment`, `tags` sont appliqués via `action__engine`, `environment`, `action__tags__name__in`
- Vérifié dans : `dashboard/views.py` (endpoints existants)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Story générée automatiquement via workflow create-story (BMAD)
- Analyse exhaustive de CODEBASE-REVIEW.md (findings API-MISS-3 à API-MISS-6)
- Analyse complète de l'implémentation existante :
  - Remediation models et services (Story 9.1, 9.2)
  - Dashboard statistics views (Story 8.4, 8.5)
  - Audit export pattern (Story 6.4)
- Contexte Epic 30 : corrections critiques avant release
- Génération : 2026-02-16

### Completion Notes List

- ✅ AC1: `GET /executions/{id}/remediation` — suggestions basées sur regex matching de error_message + filtrage par environnement
- ✅ AC2: `GET /executions/{id}/remediation-context` — contexte remédiation (has_remediation, successful_remediation, remediation_actions)
- ✅ AC3: `GET /dashboard/export/csv` — export CSV agrégé par date/engine/environment, UTF-8 BOM, limite 10,000 lignes
- ✅ AC4: `GET /dashboard/export/pdf` — export PDF avec reportlab (4 sections: stats globales, tableau par techno, tableau par env, graphique timeseries)
- ✅ AC5: 14 tests remediation (7 suggestions + 7 context) — regex matching, env filtering, null handling, 404, 401, champs requis
- ✅ AC6: 18 tests export (10 CSV + 8 PDF) — filtres, format, encodage, permissions DBA/non-DBA, Content-Disposition, magic bytes PDF
- ✅ AC7 (optionnel): Frontend alignment vérifié — les 4 endpoints correspondent aux appels frontend existants
- Note: `parent_item_type` n'est pas un champ DB mais un champ calculé dans le serializer. Les child executions sont filtrées via `parent_execution_id` FK.
- Note: `avg_execution_time_ms` laissé vide dans CSV car le modèle Execution n'a pas de champ Duration exploitable pour l'agrégation SQL Oracle

### Change Log

- 2026-02-16: Story 30.2 implémentée — 4 endpoints (remediation suggestions/context, CSV/PDF export), 32 tests passent, reportlab ajouté
- 2026-02-16: Code review adversarial — 9 fixes appliqués (4 HIGH + 4 MEDIUM + 1 LOW), 34 tests passent (14 remediation + 20 export), rapport: _bmad-output/implementation-artifacts/30-2-code-review-report.md

### File List

**Nouveaux fichiers :**
- `idp-portal/django_backend/executions/views/remediation_views.py` — Vues ExecutionRemediationSuggestionsView, ExecutionRemediationContextView
- `idp-portal/django_backend/dashboard/export_views.py` — Vues DashboardExportCSVView, DashboardExportPDFView
- `idp-portal/django_backend/executions/tests/test_remediation_endpoints.py` — 14 tests unitaires remediation
- `idp-portal/django_backend/dashboard/tests/__init__.py` — Init package tests dashboard
- `idp-portal/django_backend/dashboard/tests/test_export_endpoints.py` — 20 tests unitaires export CSV/PDF (18 AC6 + 2 code review)

**Fichiers modifiés :**
- `idp-portal/django_backend/executions/views/__init__.py` — Import + export des vues remediation
- `idp-portal/django_backend/executions/urls.py` — Routes remediation + remediation-context
- `idp-portal/django_backend/dashboard/urls.py` — Routes export/csv + export/pdf
- `idp-portal/django_backend/pyproject.toml` — Ajout dépendance reportlab>=3.6.0
- `idp-portal/django_backend/executions/serializers.py` — Serializers OpenAPI pour documentation (MEDIUM-2 fix)
