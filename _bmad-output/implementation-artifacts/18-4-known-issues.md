# Story 18.4 — Issues Connus

## Test Échoué Pré-Existant

### Test: "returns focus to clicked card after drawer closes (AC2)"

**Fichier:** `idp-portal/frontend/src/pages/CatalogPage.test.tsx:352`

**Statut:** ❌ ÉCHEC (pré-existant, NON causé par Story 18.4)

**Erreur:**
```
TestingLibraryElementError: Unable to find an accessible element with the role "button" and name `/Voir détails: Create PDB Oracle/i`
```

**Cause racine:**
Le test cherche un `role="button"` (ligne 360):
```typescript
const cardContainer = screen.getByRole('button', { name: /Voir détails: Create PDB Oracle/i });
```

Mais `ActionCard` utilise `role="article"` (ActionCard.tsx:113):
```typescript
role="article"
```

**Impact sur Story 18.4:** AUCUN

Cette erreur est **pré-existante** et **non liée** au retrait du filtre Environnement. Le test échoue parce qu'une refactorisation antérieure d'ActionCard (probablement Story 17.2 — refactorisation composants frontend volumineux) a changé `role="button"` en `role="article"` pour améliorer la sémantique HTML.

**Fix recommandé (hors scope Story 18.4):**

Modifier le test ligne 360 :
```typescript
// AVANT
const cardContainer = screen.getByRole('button', { name: /Voir détails: Create PDB Oracle/i });

// APRÈS
const cardContainer = screen.getByRole('article', { name: /Voir détails: Create PDB Oracle/i });
```

**Action prise:** Documenté dans ce fichier. Fix à effectuer dans une story de correction de tests (Story 18.7: Correction tests en échec).

---

## Résumé

Story 18.4 : **37/38 tests CatalogPage passent**

1 test échoue : "returns focus to clicked card after drawer closes" — **pré-existant, NON causé par Story 18.4**

Tous les tests **spécifiques à Story 18.4** (filtres Environnement retirés) **passent avec succès** :
- HorizontalFilters.test.tsx : 8/8 ✅
- ActiveFiltersChips.test.tsx : 12/12 ✅
- CatalogPage.test.tsx : 37/38 ✅ (1 échec pré-existant)
