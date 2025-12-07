# 🎨 Guide des Styles Kanban - Construction Base

## 🚀 Application rapide

### Dans votre vue XML
```xml
<kanban class="blg_modern_kanban o_kanban_with_chapters">
    <!-- Votre contenu kanban -->
</kanban>
```

### Classes d'état automatiques
```xml
<div t-attf-class="blg_card #{
    record.days_remaining.raw_value &lt; 0 ? 'urgent' :
    record.days_remaining.raw_value &lt; 7 ? 'warning' :
    record.progress.raw_value === 100 ? 'completed' : 'normal'
}">
```

## 🎯 Résultat visuel

### 🟢 **Projets terminés** (`completed`)
- ✅ Badge de réussite vert
- 🎉 Effet de célébration
- 📊 Barre de progression verte

### 🔴 **Projets urgents** (`urgent`)
- ⚠️ Bordure rouge pulsante
- 🚨 Animation d'alerte
- 📅 Indicateur de retard

### 🟡 **Projets en alerte** (`warning`)
- ⏰ Bordure orange
- 📊 Métriques en surbrillance
- 🔔 Animation subtile

### 🔵 **Projets normaux** (`normal`)
- 📋 Bordure bleue BLG
- 🏗️ Icônes de construction
- 📈 Progression standard

## 🎨 Personnalisation

### Variables CSS disponibles
```css
:root {
    --blg-primary: #007bff;
    --blg-success: #28a745;
    --blg-warning: #ffc107;
    --blg-danger: #dc3545;
}
```

### Mode compact (optionnel)
```xml
<kanban class="blg_modern_kanban compact-mode">
```

## ✨ Fonctionnalités automatiques

### 📱 **Responsive**
- Desktop : Cartes larges avec détails complets
- Mobile : Version compacte automatique

### 🎬 **Animations**
- Hover effects sur les cartes
- Barres de progression animées
- Pulsations pour urgences

### 🎯 **Accessibilité**
- Support des préférences utilisateur
- Mode contraste élevé
- Réduction de mouvement

### 🖨️ **Mode impression**
- Optimisé pour PDF/impression
- Couleurs préservées
- Mise en page adaptée

## 🔧 Support

- **Compatible** : Chrome, Firefox, Safari, Edge
- **Responsive** : Mobile, tablette, desktop
- **Performance** : GPU acceleration, CSS optimisé

---

*Styles créés par l'équipe BLG IT - 2024* 