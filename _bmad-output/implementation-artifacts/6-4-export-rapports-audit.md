# Story 6.4 : Export rapports d'audit

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que spécialiste sécurité,
je veux exporter les données filtrées en CSV et PDF en un clic,
afin de générer les rapports d'audit SOC1 sans collecte manuelle.

## Acceptance Criteria

1. **AC1** — Given Nadia a appliqué des filtres sur la table d'audit, When elle clique sur « Exporter », Then un menu propose deux formats : CSV et PDF.
2. **AC2** — Given Nadia choisit CSV, When l'export se génère, Then un fichier CSV contenant toutes les colonnes de la table filtrée est téléchargé avec un nom standardisé (audit-export-YYYY-MM-DD.csv).
3. **AC3** — Given Nadia choisit PDF, When l'export se génère, Then un document PDF formaté est généré avec en-tête (date, filtres appliqués, nombre d'enregistrements) et les données tabulaires.
4. **AC4** — L'API GET /api/v1/audit/export accepte les query params : format=csv|pdf, from, to, environment, action_id, user_id, status (mêmes filtres que la table) et génère le fichier.
5. **AC5** — Le toast notification « Rapport exporté — Télécharger » s'affiche avec lien (ou confirmation de téléchargement).
6. **AC6** — FR34 est satisfaite.
7. **AC7** — Les exports supportent jusqu'à 10 000+ lignes sans dégradation (NFR24) ; au-delà, paginer ou limiter avec message explicite.

## Tasks / Subtasks

- [x] **Task 1** (AC: 4, 7) — Backend : endpoint export audit CSV/PDF
  - [x] 1.1 Réutiliser `audit_repository.list_execution_audit_entries` avec les mêmes paramètres de filtres (from_date, to_date, user_id, environment, action_id, status). Pour l'export, récupérer les lignes sans pagination stricte, avec une limite max (ex. 10 000) pour NFR24 ; au-delà retourner 400 ou 413 avec message explicite.
  - [x] 1.2 Ajouter route GET /api/v1/audit/export avec query params : format (csv | pdf), from, to, environment, action_id, user_id, status. Protéger par RBAC (is_auditor). Retourner StreamingResponse (CSV) ou génération PDF en mémoire puis FileResponse.
  - [x] 1.3 CSV : en-tête = colonnes de la table (action, utilisateur, environnement, statut, date, changement ServiceNow, etc.), encodage UTF-8 avec BOM pour Excel, nom fichier audit-export-YYYY-MM-DD.csv.
  - [x] 1.4 PDF : librairie légère (ex. reportlab ou weasyprint) ; en-tête avec date d'export, filtres appliqués, nombre d'enregistrements ; tableau des données ; nom fichier audit-export-YYYY-MM-DD.pdf.
- [x] **Task 2** (AC: 1, 2, 3, 5) — Frontend : bouton Exporter et téléchargement
  - [x] 2.1 Sur la page/section Audit (créée en 6.3), ajouter un bouton « Exporter » avec Dropdown (Ant Design) : option CSV, option PDF.
  - [x] 2.2 Au clic CSV/PDF : appeler GET /api/v1/audit/export?format=csv|pdf&… avec les mêmes query params que les filtres courants de la table (from, to, environment, action_id, user_id, status). Télécharger le fichier (blob + création lien download, ou window.open avec URL si backend renvoie URL temporaire — préférer blob pour cohérence).
  - [x] 2.3 Après téléchargement réussi : afficher toast « Rapport exporté — Télécharger » (ou « Rapport exporté » si le fichier est déjà téléchargé) avec design liquid glass / thème existant.
  - [x] 2.4 Gérer erreur (ex. limite 10 000 dépassée) : afficher message explicite dans un message/notification Ant Design.
- [x] **Task 3** (AC: 6) — RBAC et cohérence
  - [x] 3.1 S'assurer que seuls les utilisateurs is_auditor peuvent appeler GET /api/v1/audit/export (réutiliser _require_auditor comme en 6.3). Sinon 403.
  - [x] 3.2 Le bouton Exporter n'est visible que pour les auditeurs (même condition que la page Audit).
- [x] **Task 4** — Tests
  - [x] 4.1 Tests unitaires backend : route GET /api/v1/audit/export avec format=csv et format=pdf, vérification des filtres, 403 si non-auditeur, limite 10 000 (comportement attendu au-delà).
  - [x] 4.2 Tests unitaires : contenu CSV (en-têtes, encodage UTF-8), contenu PDF (en-tête avec filtres et count).
  - [x] 4.3 Tests frontend : bouton Exporter, dropdown CSV/PDF, appel API avec bons params, toast après succès, gestion erreur.

## Dev Notes

- **Contexte Epic 6** : Les stories 6.1 à 6.3 ont mis en place AUDIT_LOG immutable, traces EXECUTION_*, liste filtrée GET /api/v1/audit/executions et page Audit avec table + filtres. La story 6.4 ajoute uniquement l’export des mêmes données (mêmes filtres) en CSV et PDF.
- **Réutilisation** : Réutiliser `audit_repository.list_execution_audit_entries` (et éventuellement une variante sans limit/offset pour export, avec cap 10 000). Ne pas dupliquer la logique de filtres ; les paramètres d’export doivent être identiques à ceux de la liste (from, to, environment, action_id, user_id, status).
- **Architecture** : L’architecture (doc) indique « Export CSV/PDF — Génération côté serveur (volume potentiel 10 000+ executions) ». Génération côté backend obligatoire ; pas d’export côté client à partir de la table déjà chargée (pour cohérence et volume).
- **NFR24** : Historique 10 000+ exécutions sans dégradation. Pour l’export : soit limiter à 10 000 lignes avec message si plus, soit streamer par lots ; documenter le choix (recommandation : limite 10 000 + message clair).

### Project Structure Notes

- **Backend** : `app/api/v1/audit.py` — ajouter la route GET /export (préfixe router déjà /audit → GET /api/v1/audit/export). Réutiliser `audit_repository.list_execution_audit_entries`. Pas de nouveau repository ; optionnel service d’export (audit_export_service) pour génération PDF si on veut garder la route fine.
- **Frontend** : Page/section Audit existante (6.3) — ajouter bouton Exporter + Dropdown dans la barre d’outils de la table. Service `audit_service.ts` (ou équivalent) : méthode `exportAuditReport(format, filters)` appelant GET /api/v1/audit/export et déclenchant le téléchargement.
- **Pas de migration Flyway** : pas de changement de schéma ; lecture seule sur AUDIT_LOG comme en 6.3.

### Developer context — garde-fous

- **Stack** : Backend Python 3.12+, FastAPI, python-oracledb, Oracle. Frontend React, TypeScript, Ant Design 6.2. Réutiliser _require_auditor, audit_repository, et patterns de la page Audit (6.3).
- **DB** : Lecture seule sur AUDIT_LOG. Aucune écriture. Même logique de filtres que GET /api/v1/audit/executions.
- **API** : Un seul nouvel endpoint GET /api/v1/audit/export. Réponse : body binaire (fichier CSV ou PDF) avec Content-Disposition et Content-Type appropriés (text/csv; charset=utf-8, application/pdf). Query params alignés sur /audit/executions.
- **RBAC** : Accès réservé aux profils avec is_auditor=true. Réutiliser _require_auditor de audit.py.
- **Fichiers** : Nom de fichier standardisé audit-export-YYYY-MM-DD.csv ou .pdf (date du jour ou date de la plage exportée — préciser : date du jour recommandée pour simplicité).

### Previous Story Intelligence (6.3)

- **Fichiers modifiés en 6.3** : `app/api/v1/audit.py` (GET /executions), `app/repositories/audit_repository.py` (list_execution_audit_entries, count_execution_audit_entries), page Audit frontend, audit_service, TopNav conditionné is_auditor.
- **Pattern à réutiliser** : Mêmes paramètres de filtre (from, to, environment, action_id, user_id, status). Même vérification is_auditor. Pour l’export, appeler list_execution_audit_entries avec limit élevé (ou nouvelle méthode list_*_for_export avec cap 10 000) pour éviter de charger toute la table.
- **Code review 6.3** : Pagination 25, index (ENTITY_TYPE, TIMESTAMP), count séparé. Pour l’export, pas de pagination côté client ; un seul appel qui retourne le fichier.

### Architecture Compliance

- **AUDIT_LOG** : Append-only conservé ; aucune écriture. Lecture avec mêmes filtres que 6.3.
- **Repository** : audit_repository : pas de nouvelle méthode obligatoire ; réutilisation de list_execution_audit_entries avec limit=10000 (ou paramètre export=True) pour cap. Si préféré, méthode dédiée list_execution_audit_entries_for_export(...) qui appelle la même SQL avec limit 10 000.
- **REST** : GET /api/v1/audit/export en lecture seule, aligné sur les conventions (query params snake_case, réponse binaire avec headers appropriés).
- **Frontend** : Alignement avec page Audit (6.3), Ant Design Dropdown/Button, toast notification (design system liquid glass).

### Library / framework requirements

- **Backend PDF** : Choisir une librairie légère (reportlab ou weasyprint). reportlab : dépendance pure Python, génération PDF programmatique. Vérifier compatibilité Python 3.12 et ajouter dans pyproject.toml.
- **CSV** : Module standard csv + io.StringIO ou BytesIO ; pas de dépendance externe. UTF-8 avec BOM pour Excel (\\ufeff en début de stream).
- **Frontend** : Aucune librairie d’export côté client ; le backend renvoie le fichier, le frontend fait blob + URL.createObjectURL + <a download> ou équivalent.

### File structure requirements

- **Backend** : `app/api/v1/audit.py` — ajouter fonction get_export_audit ou export_audit_report. Optionnel : `app/services/audit_export_service.py` pour génération PDF (tableau + en-tête) si on veut garder la route HTTP fine.
- **Frontend** : Même page/route que 6.3 (Audit). Composant existant : ajouter bouton + dropdown. Service : étendre audit_service (ou équivalent) avec exportAuditReport(format, filters).

### Testing requirements

- **Backend** : Tests unitaires pour GET /api/v1/audit/export : format=csv et format=pdf ; vérifier que les filtres sont appliqués (mock repository ou DB test) ; 403 si user non auditeur ; cas limite > 10 000 lignes (message ou 413/400).
- **Backend** : Vérifier contenu CSV (première ligne = en-têtes, encodage UTF-8). Vérifier PDF (présence en-tête avec date/filtres/count, présence des données).
- **Frontend** : Test bouton Exporter, choix CSV/PDF, appel API avec les bons query params, affichage toast après succès, gestion erreur (message utilisateur).

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 6, Story 6.4]
- [Source: idp-portal/backend/app/api/v1/audit.py — GET /executions, _require_auditor]
- [Source: idp-portal/backend/app/repositories/audit_repository.py — list_execution_audit_entries, count_execution_audit_entries]
- [Source: architecture.md — Export CSV/PDF côté serveur, NFR24]
- [Source: idp-portal/frontend — page Audit (6.3), patterns table + filtres]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

**2026-01-31** — Implémentation complète de l'export CSV/PDF des rapports d'audit

**Backend (Task 1)** :
- Endpoint GET /api/v1/audit/export implémenté dans `app/api/v1/audit.py`
- Réutilisation de `audit_repository.list_execution_audit_entries` avec limite max 10 000 lignes (NFR24)
- Génération CSV avec UTF-8 BOM pour Excel, colonnes complètes
- Génération PDF avec reportlab : en-tête avec date, filtres appliqués, nombre d'enregistrements, tableau formaté
- Protection RBAC via `_require_auditor`
- Gestion erreur 400 si limite dépassée avec message explicite
- Ajout de `BadRequestError` dans `app/core/exceptions.py`
- Ajout de `reportlab>=4.0` dans `pyproject.toml`

**Frontend (Task 2)** :
- Bouton "Exporter" avec Dropdown (CSV/PDF) ajouté dans `AuditPage.tsx`
- Fonction `exportAuditReport` dans `audit_service.ts` : téléchargement blob avec création lien temporaire
- Toast de succès après export réussi
- Gestion erreur avec message Ant Design explicite
- Bouton visible uniquement pour auditeurs (condition existante de la page)

**Tests (Task 4)** :
- Tests backend dans `test_audit_api.py` : TestAuditExportEndpoint avec 10 cas de test
  - 403 si non-auditeur
  - Export CSV/PDF réussis
  - Filtres passés correctement
  - Limite 10 000 respectée
  - Format filename correct
  - Contenu CSV (BOM UTF-8)
  - Contenu PDF (magic bytes)
- Tests frontend dans `AuditPage.test.tsx` : 7 nouveaux tests pour export
  - Bouton visible
  - Dropdown CSV/PDF
  - Appel API avec bons params
  - Toast succès
  - Gestion erreur
  - Filtres passés à l'export

**Décisions techniques** :
- Choix de reportlab pour PDF (dépendance pure Python, compatible Python 3.12)
- Limite 10 000 lignes avec détection via limit+1 pour éviter de charger toutes les données
- CSV avec BOM UTF-8 pour compatibilité Excel
- PDF avec en-tête structuré incluant date, filtres, count

**2026-01-31 — Code Review Fixes (10 issues fixed: 3 HIGH + 4 MEDIUM + 3 LOW)** :

**HIGH Severity Fixes** :
- HIGH-1: Ajout de `action_name` dans CSV export (enrichissement via catalog_repository comme dans /executions)
- HIGH-2: Ajout de `servicenow_change_id` dans CSV export (colonne manquante de la table)
- HIGH-3: Ajout de `action_name` et `servicenow_change_id` dans PDF export (cohérence avec table)

**MEDIUM Severity Fixes** :
- MEDIUM-1: Enrichissement des entrées avec `action_name` dans export_audit_report (réutilisation logique de /executions)
- MEDIUM-2: Déplacement de `MAX_EXPORT_ROWS` en constante de module (meilleure maintenabilité)
- MEDIUM-3: Passage de tous les filtres disponibles dans frontend export (action_id, user_id pour compatibilité future)
- MEDIUM-4: Amélioration tests CSV pour vérifier explicitement présence de `action_name` et `servicenow_change_id`

**LOW Severity Fixes** :
- LOW-2: Ajout gestion d'erreur spécifique pour génération PDF (try/except avec message explicite)

**Fichiers modifiés lors du code review** :
- `idp-portal/backend/app/api/v1/audit.py` — Enrichissement action_name, ajout servicenow_change_id, constante MAX_EXPORT_ROWS, gestion erreur PDF
- `idp-portal/frontend/src/pages/AuditPage.tsx` — Passage de tous les filtres à l'export
- `idp-portal/backend/tests/unit/test_audit_api.py` — Mock catalog_repository, vérification action_name dans CSV

### File List

**Backend** :
- `idp-portal/backend/app/api/v1/audit.py` — Ajout endpoint GET /export, fonctions _generate_csv_response et _generate_pdf_response
- `idp-portal/backend/app/core/exceptions.py` — Ajout BadRequestError
- `idp-portal/backend/pyproject.toml` — Ajout dépendance reportlab>=4.0
- `idp-portal/backend/tests/unit/test_audit_api.py` — Ajout TestAuditExportEndpoint (10 tests)

**Frontend** :
- `idp-portal/frontend/src/pages/AuditPage.tsx` — Ajout bouton Exporter avec Dropdown, handler export, toast
- `idp-portal/frontend/src/services/audit_service.ts` — Ajout fonction exportAuditReport
- `idp-portal/frontend/src/pages/AuditPage.test.tsx` — Ajout tests export (7 nouveaux tests)
