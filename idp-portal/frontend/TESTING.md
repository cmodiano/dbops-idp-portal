# Tests Frontend — IDP Portal

## Baseline (2026-02-13)

| Métrique | Valeur |
|---|---|
| **Total tests** | 2018 |
| **Fichiers de test** | 147 |
| **Taux de réussite** | 100% (2018/2018) |
| **Durée d'exécution** | ~124s (sans coverage), ~162s (avec coverage) |
| **Couverture lignes** | 76.22% |
| **Couverture statements** | 74.25% |
| **Couverture branches** | 68.67% |
| **Couverture fonctions** | 66.77% |
| **Erreurs non capturées** | 0 |
| **Tests skip** | 0 (vérifié via grep -r "\.skip\|\.todo\|\.only") |

## Stack de test

- **Vitest 4.0.18** — Test runner (Vite-native)
- **Testing Library React 16.3.2** — Rendering et queries
- **Testing Library User Event 14.6.1** — Simulation interactions utilisateur
- **happy-dom 20.4.0** — DOM environnement (installé, JSDOM utilisé par défaut)
- **jsdom 28.0.0** — DOM environnement actuel
- **@vitest/coverage-v8 4.0.18** — Couverture de code

## Commandes

```bash
# Exécuter tous les tests
npm test

# Exécuter les tests en mode watch
npm run test:watch

# Exécuter les tests avec couverture
npx vitest run --coverage

# Exécuter un fichier de test spécifique
npx vitest run src/path/to/MyComponent.test.tsx
```

## Configuration

- **vite.config.ts** — Configuration Vitest (testTimeout: 10000ms)
- **Environnement** — jsdom (global)

## Known Limitations

### d3-zoom / d3-drag en JSDOM

`WorkflowExecutionGraph.test.tsx` utilise des mocks pour `d3-drag` et `d3-zoom` car JSDOM ne fournit pas `ownerDocument` correctement pour les événements simulés. Les mocks reproduisent l'API suffisamment pour tester le rendu et les interactions sans le comportement zoom/drag réel.

### Tests avec timeout etendu (coverage)

Certains tests d'intégration lourds nécessitent un timeout étendu (20s) lorsque le coverage est activé, car l'instrumentation ralentit l'exécution :

- `CatalogPage.story19_4.integration.test.tsx` — AC8 (reset wizard state)
- `ActionForm.test.tsx` — validation duplicate environment

## Conventions

- Tests co-localisés : `Component.test.tsx` à côté de `Component.tsx`
- Factories/mocks partagés dans `src/test/` ou `src/__mocks__/`
- Utiliser `screen.getByRole()` pour accessibilité
- Envelopper les mises à jour d'état async dans `act()` (React 19)
- Documenter tout test skip avec justification
- Ne pas utiliser de props Ant Design dépréciées (voir FRONTEND-STANDARDS.md)
