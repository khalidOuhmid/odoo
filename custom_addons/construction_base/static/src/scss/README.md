# 🎨 Styles SCSS - Construction Base

## 📁 Structure des fichiers

### `construction_kanban.scss`
**Style moderne et épuré pour la vue Kanban des chantiers**

#### 🎯 Fonctionnalités principales
- **Design moderne** : Cartes avec bordures arrondies, ombres subtiles
- **Indicateurs visuels** : Codes couleur pour urgence/état des projets
- **Animations fluides** : Hover effects, transitions CSS3
- **Responsive** : Optimisé mobile et desktop
- **Thème sombre** : Support automatique du mode sombre

#### 🎨 Codes couleur
- **🔴 Urgent** (`urgent`) : Projets en retard - `#dc3545`
- **🟡 Attention** (`warning`) : Échéance proche (<7 jours) - `#ffc107`
- **🟢 Terminé** (`completed`) : Progression 100% - `#28a745`
- **🔵 Normal** (`normal`) : Progression standard - `#007bff`

#### 📱 Classes CSS disponibles
```scss
.blg_modern_kanban          // Container principal
  .o_kanban_group          // Groupes/colonnes
    .blg_card              // Cartes individuelles
      .card-header         // En-tête avec nom/chapitre
      .card-body           // Corps avec métriques
      .card-footer         // Pied avec équipe/dates

// Classes d'état
.urgent                    // Projet en retard
.warning                   // Échéance proche  
.completed                 // Terminé
.normal                    // En cours normal

// Mode compact
.compact-mode              // Version condensée
```

#### 🎬 Animations incluses
- `pulse-urgent` : Pulsation rouge pour projets en retard
- `pulse-warning` : Pulsation orange pour urgences
- `shimmer` : Effet brillant sur barres de progression
- `float` : Flottement pour empty state

### `chantier_views.scss`
**Styles complémentaires pour les vues formulaire et liste**

## 🚀 Utilisation

### Dans le XML
```xml
<kanban class="blg_modern_kanban o_kanban_with_chapters">
  <!-- Contenu kanban -->
</kanban>
```

### Mode compact
```xml
<kanban class="blg_modern_kanban compact-mode">
  <!-- Version condensée -->
</kanban>
```

### Classes d'état dynamiques
```xml
<div t-attf-class="blg_card #{
  record.days_remaining.raw_value < 0 ? 'urgent' :
  record.days_remaining.raw_value < 7 ? 'warning' :
  record.progress.raw_value === 100 ? 'completed' : 'normal'
}">
```

## 🎛️ Personnalisation

### Variables CSS (optionnel)
```scss
:root {
  --kanban-card-radius: 12px;
  --kanban-header-gradient: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
  --kanban-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  --kanban-hover-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}
```

### Responsive breakpoints
- **Desktop** : > 768px - Vue complète
- **Mobile** : ≤ 768px - Version compacte automatique

## 🎨 Exemples visuels

### 🔴 Carte urgente (en retard)
```
┌─ [Rouge] ────────────────────┐
│ 🏗️ Rénovation Villa Dupont   │
│ 📋 Gros œuvre                │
│ 📍 12 rue des Lilas         │
│ 💰 25,000€ | ⏰ 3j retard    │
│ ████████████ 85%            │
│ 👤👤 | 🔔 | 📅 15/01        │
└──────────────────────────────┘
```

### 🟢 Carte terminée
```
┌─ [Vert] ─────────────────────┐
│ 🏗️ Extension Martin         │
│ 📋 Finitions                │
│ 📍 8 avenue de la Paix      │
│ 💰 18,500€ | ⏰ Terminé ✓   │
│ ████████████ 100%           │
│ 👤 | 🎉 | 📅 20/01          │
└──────────────────────────────┘
```

## 🔧 Maintenance

### Performance
- **Animations** : `will-change` pour GPU acceleration
- **Scrollbar** : Custom styling pour webkit
- **Images** : Lazy loading automatique

### Accessibilité
- **Contrastes** : WCAG AA compliant
- **Focus** : Indicateurs visuels clairs
- **Screen readers** : ARIA labels préservés

### Browser support
- ✅ Chrome 80+
- ✅ Firefox 75+
- ✅ Safari 13+
- ✅ Edge 80+
- ⚠️ IE11 (dégradé gracieusement)

---

*Développé par l'équipe BLG IT - 2024* 