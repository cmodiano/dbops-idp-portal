# Workflow Mypy Baseline

## Pourquoi un baseline ?

Le codebase Django contient du code historique sans annotations de type complètes. Activer mypy en mode strict d'un coup bloquerait le développement avec des centaines d'erreurs. L'approche baseline permet de :

- **Bloquer les nouvelles erreurs** : empêcher les régressions de type
- **Tolérer les erreurs existantes** : ne pas bloquer le développement courant
- **Réduire progressivement** : corriger les erreurs legacy au fil du temps

## Fonctionnement

### Fichiers clés

| Fichier | Rôle |
|---------|------|
| `.mypy-baseline-count` | Nombre d'erreurs tolérées (commité dans git) |
| `scripts/generate_mypy_baseline.sh` | Générer/mettre à jour le baseline |
| `scripts/check_mypy_baseline.sh` | Vérifier que le count actuel <= baseline |
| `mypy-report.txt` | Rapport détaillé des erreurs (non commité) |

### Scénarios CI

| Scénario | Résultat |
|----------|----------|
| Aucune nouvelle erreur | PASS (exit 0) |
| Erreurs corrigées (count < baseline) | PASS + suggestion de mettre à jour baseline |
| Nouvelles erreurs (count > baseline) | FAIL (exit 1) |

## Comment mettre à jour le baseline

Après avoir corrigé des erreurs de type :

```bash
cd django_backend
scripts/generate_mypy_baseline.sh
git add .mypy-baseline-count
git commit -m 'chore: update mypy baseline'
```

## Comment interpréter un échec CI

Si le job `typecheck-backend` échoue :

1. Lire le message d'erreur (nombre d'erreurs nouvelles)
2. Télécharger l'artefact `mypy-report` pour voir les erreurs détaillées
3. Corriger les erreurs de type introduites
4. Pousser la correction

## Objectif

Réduire le baseline à 0 sur 6-12 mois en annotant progressivement le code existant.
