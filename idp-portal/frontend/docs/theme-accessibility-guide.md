# Guide des bonnes pratiques — Tokens du thème et accessibilité

Ce guide explique comment utiliser correctement les tokens du thème Ant Design dans le portail IDP pour garantir l'accessibilité en mode clair et sombre.

## Pourquoi éviter les couleurs hardcodées ?

Les couleurs hardcodées (ex. `#1f1f1f`, `rgba(26, 26, 36, 0.8)`) ne s'adaptent pas au changement de thème :
- Un background dark hardcodé sera invisible en thème clair
- Un texte gris clair sera illisible en thème clair sur fond blanc
- Le contraste WCAG AA (4.5:1 pour texte normal) ne sera pas garanti

## Comment utiliser `theme.useToken()`

```typescript
import { theme } from 'antd';

function MonComposant() {
  const { token } = theme.useToken();

  return (
    <div style={{
      background: token.colorBgContainer,
      color: token.colorText,
      borderColor: token.colorBorder,
    }}>
      {/* contenu */}
    </div>
  );
}
```

## Tokens recommandés par type de couleur

### Backgrounds

| Token | Usage |
|-------|-------|
| `token.colorBgContainer` | Surfaces principales (cards, modals, drawers) |
| `token.colorBgElevated` | Éléments surélevés (tooltips, popovers, blocs code) |
| `token.colorBgLayout` | Background du layout |
| `token.colorFillQuaternary` | Fill subtil pour backgrounds secondaires |

### Texte

| Token | Usage |
|-------|-------|
| `token.colorText` | Texte principal (haute priorité) |
| `token.colorTextSecondary` | Labels, descriptions, légendes |
| `token.colorTextTertiary` | Placeholders, hints |
| `token.colorTextQuaternary` | Texte le plus subtil |

### Bordures

| Token | Usage |
|-------|-------|
| `token.colorBorder` | Bordure par défaut |
| `token.colorBorderSecondary` | Bordure plus subtile |

### Couleurs de statut

| Token | Usage |
|-------|-------|
| `token.colorSuccess` | Succès (vert) |
| `token.colorWarning` | Avertissement (orange) |
| `token.colorError` | Erreur (rouge) |
| `token.colorInfo` | Information (bleu) |

## Exemples de migration

### Avant (hardcodé)
```typescript
// Background dark-theme uniquement
background: '#1f1f1f',
color: '#e8e8e8',
borderBottom: '1px solid #303030',
```

### Après (tokens)
```typescript
const { token } = theme.useToken();

background: token.colorBgContainer,
color: token.colorText,
borderBottom: `1px solid ${token.colorBorder}`,
```

### Avant (texte hardcodé)
```typescript
color: '#374151',  // Illisible en dark mode
color: '#1f2937',  // Contraste insuffisant en dark mode
```

### Après (tokens)
```typescript
const { token } = theme.useToken();

color: token.colorTextSecondary,  // Adapté au thème
color: token.colorText,           // Contraste garanti
```

## Contraste WCAG AA garanti par les tokens

Les tokens du thème Desjardins garantissent le contraste WCAG AA :

- **Light :** `colorText` (#1a1a2e) sur `colorBgContainer` (#FFFFFF) = 15.8:1
- **Dark :** `colorText` (#f5f5f7) sur `colorBgContainer` (#1e1e2a) = 15.11:1

## Cas particulier : fonctions utilitaires (non-composants)

Les fonctions utilitaires qui retournent du JSX (ex. `renderXxx()`) ne peuvent pas utiliser `useToken()` directement car ce n'est pas un hook React valide dans un contexte non-composant.

**Solution :** Convertir en composant React :

```typescript
// Avant : fonction utilitaire
export function renderStatus(status: string): React.ReactNode {
  return <Tag style={{ background: 'rgba(26, 26, 36, 0.8)' }}>{status}</Tag>;
}

// Après : composant React avec useToken()
function StatusIndicator({ status }: { status: string }) {
  const { token } = theme.useToken();
  return <Tag style={{ background: token.colorBgElevated }}>{status}</Tag>;
}

export function renderStatus(status: string): React.ReactNode {
  return <StatusIndicator status={status} />;
}
```

## Couleurs métier (exceptions)

Certaines couleurs sont intentionnellement fixes car elles représentent des codes métier :

- `ERROR_COLOR = '#EF4444'` — Rouge erreur (constant entre thèmes)
- `STYLE_TOKENS.engineIconColor.*` — Couleurs des logos vendeurs
- `STYLE_TOKENS.platformIconColor.*` — Couleurs des icônes de plateforme

Ces couleurs ne dépendent pas du thème et ne doivent pas être remplacées par des tokens.
