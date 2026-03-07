# Partitionnement et rétention — Exécutions et logs (performance)

**Contexte :** Forte volumétrie attendue sur les exécutions et les logs (audit, steps). Faut-il partitionner pour n’avoir que le dernier mois (ou une plage de dates récente) en partition « active » ?

**Références existantes :** comparatif idp-portal vs dbops, Epic 14 Story 14.8, convergence-dbops-idp-portal.

---

## 1. Ce que disent les docs existantes

### Comparatif schémas — `docs/db-schema-comparison-idp-vs-dbops.md`

- **dbops** (repo dont on s’est inspiré) a déjà :
  - **Partitionnement** (ex. `operation_request` par mois) pour la volumétrie.
  - **Rétention / maintenance** : `pkg_maintenance.purge_old_data`, logs `ops_maintenance_log`, jobs DBMS_SCHEDULER.
- Pour **idp-portal** : il manque « **Rétention/partitionnement/MViews** si volumétrie élevée côté exécutions/logs ».

### Epic 14 — `_bmad-output/planning-artifacts/epic-14-moteur-ops-et-scalabilite.md`

- **Story 14.8** (Scalabilité Oracle — partitionnement, rétention, indexation) prévoit :
  - **Partitionnement recommandé** :
    - `EXECUTIONS` par **`CREATED_AT` (mensuel)**,
    - `EXECUTION_STEPS` partitionné par référence à `EXECUTIONS` (si Oracle le permet selon FK),
    - **`AUDIT_LOG`** par **`TIMESTAMP` (mensuel)**.
  - **Politique de rétention** (ex. 24 mois exécutions, 3 mois logs/steps détaillés).
  - Purge par **« drop partitions »** quand possible (système reste disponible).

### Convergence DBOps — `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md`

- **Partitionnement Oracle** : « À évaluer plus tard **si les volumes l’exigent** (pas critique au départ) ».
- Dès que la volumétrie exécutions/logs devient importante, la recommandation Epic 14.8 s’applique.

---

## 2. Réponse courte : oui, partitionnement par range (date) avec « dernier mois » chaud

- **Oui**, il est pertinent de **partitionner** les tables à forte croissance (**EXECUTIONS**, **EXECUTION_STEPS**, **AUDIT_LOG**) et d’avoir une **partition « active »** limitée à une plage de dates récente (ex. dernier mois).
- En **partitionnement range par mois** :
  - La partition **active** (chaude) = mois en cours (et éventuellement le mois précédent selon les requêtes).
  - Les requêtes typiques (liste exécutions, audit, timeline) qui filtrent sur les **derniers 7/30 jours** ne scannent qu’**une ou deux partitions** au lieu de toute la table.
- **Rétention** : garder par exemple 24 mois pour les en-têtes d’exécutions (métadonnées), et une rétention plus courte pour les steps détaillés / logs si besoin (ex. 3 mois comme dans Epic 14.8). La purge = **drop** des partitions au-delà de la rétention (pas de delete ligne à ligne).

---

## 3. Recommandation synthétique

| Table            | Clé de partitionnement   | Partition « active » (chaud) | Rétention suggérée (ex.) |
|------------------|--------------------------|------------------------------|---------------------------|
| **EXECUTIONS**   | `CREATED_AT` (range, mois) | Dernier mois (mois courant)  | 24 mois (drop partitions) |
| **EXECUTION_STEPS** | Référence à EXECUTIONS (FK) ou date dérivée | Idem (alignée exécutions) | 3–12 mois (à définir avec métier) |
| **AUDIT_LOG**    | `TIMESTAMP` (range, mois) | Dernier mois                 | 12–24 mois (conformité)    |

- **Range de dates** : partitionnement **mensuel** (ou hebdo si volume très élevé) ; la partition active correspond au **range du mois courant** (et éventuellement mois précédent pour les requêtes « 30 derniers jours »).
- **Implémentation** : à faire en Phase 3 Epic 14 (scalabilité selon volumétrie), avec validation DBA (contraintes FK, index, requêtes existantes). Voir Story 14.8 pour les critères d’acceptation et la procédure de purge.

---

## 4. Références

- `docs/db-schema-comparison-idp-vs-dbops.md` — § Observabilité & exploitation BD (dbops), § Impacts idp-portal.
- `_bmad-output/planning-artifacts/epic-14-moteur-ops-et-scalabilite.md` — Story 14.8, notes d’implémentation, risques (partitionnement).
- `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md` — tableau « Ce qu’on NE reprend PAS » (partitionnement à évaluer si volumes).
