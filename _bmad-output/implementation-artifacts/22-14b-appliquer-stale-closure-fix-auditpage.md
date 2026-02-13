# Story 22.14b: Appliquer le fix stale closure à AuditPage

Status: todo

## Story

En tant que développeur,
je veux appliquer le même pattern refetchCurrentState à AuditPage,
afin d'éviter les stale closures identifiées dans ExecutionsPage.

## Context

Story 22.14 a identifié et corrigé des stale closures dans `ExecutionsPage.tsx`. Le fichier `AuditPage.tsx` (ligne 160) utilise le même pattern problématique où `fetchData(currentPage, activeScope)` est capturé dans des callbacks.

## Acceptance Criteria

1. **Given** AuditPage utilise le même pattern de callbacks avec fetchData
   - **When** l'utilisateur change de pagination ou de scope pendant une opération
   - **Then** le refetch utilise les valeurs actuelles, pas celles capturées dans la closure

2. **Given** AuditPage a des callbacks similaires (refresh, filter changes)
   - **When** ces callbacks s'exécutent
   - **Then** ils utilisent `refetchCurrentState()` avec refs au lieu de state capturé

3. **Given** des opérations concurrentes sur AuditPage
   - **When** plusieurs refetch se déclenchent simultanément
   - **Then** un guard `isRefreshingRef` prévient les doublons

## Tasks / Subtasks

- [ ] Analyser AuditPage pour identifier tous les callbacks affectés
- [ ] Implémenter le pattern refetchCurrentState (refs + useEffect sync)
- [ ] Ajouter guards isRefreshingRef pour prévenir doublons
- [ ] Ajouter tests unitaires pour stale closure scenarios
- [ ] Mettre à jour la documentation

## Dev Notes

### Références
- Story 22.14: `/Users/cyrille/Documents/Dev/test/_bmad-output/implementation-artifacts/22-14-corriger-high-7-stale-closure-executionspage.md`
- Pattern de solution: lignes 343-377 dans ExecutionsPage.tsx
- Tests références: ExecutionsPage.test.tsx lignes 1479-1926

### Fichiers à Analyser
- `/Users/cyrille/Documents/Dev/test/idp-portal/frontend/src/pages/AuditPage.tsx` (ligne 160)
- Pattern similaire identifié dans code-quality-assessment ligne 344

### Complexité Estimée
- **Effort**: Petit (1-2h) — pattern déjà établi dans Story 22.14
- **Risque**: Faible — même solution déjà validée
