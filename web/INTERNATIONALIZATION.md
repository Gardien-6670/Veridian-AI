# 🌍 Veridian AI - Système d'internationalisation (i18n)

## Vue d'ensemble

Le système i18n détecte automatiquement la langue du navigateur et charge les traductions appropriées. Il supporte **15 langues majeures** avec fallback automatique sur l'anglais.

## 🗣️ Langues supportées

| Code | Langue | Code | Langue |
|------|--------|------|--------|
| `fr` | Français | `ko` | Coréen |
| `en` | Anglais | `ar` | Arabe |
| `es` | Espagnol | `pl` | Polonais |
| `de` | Allemand | `th` | Thaï |
| `ru` | Russe | `bn` | Bengali |
| `pt` | Portugais | `hi` | Hindi |
| `it` | Italien | `ja` | Japonais |
| `zh` | Chinois (simplifié) | | |

## 📁 Structure

```
web/
├── js/
│   └── i18n.js           # Script principal i18n
├── locales/
│   ├── fr.json           # Traductions Français
│   ├── en.json           # Traductions Anglais
│   ├── es.json, de.json, ru.json, ...
│   └── (14 fichiers JSON supplémentaires)
└── index.html / dashboard.html
```

## 🚀 Utilisation

### 1. Ajouter le script dans le `<head>`

```html
<script src="js/i18n.js" defer></script>
```

### 2. Utiliser `data-i18n` sur les éléments HTML

#### Texte contenu
```html
<a href="#features" data-i18n="nav_features">Fonctionnalités</a>
```

Le script cherche la clé `nav_features` dans le fichier JSON actif et remplace le texte.

#### Attributs
```html
<!-- Placeholder -->
<input type="text" data-i18n-placeholder="search_placeholder" />

<!-- Title -->
<button data-i18n-title="btn_tooltip" title="...">Click</button>

<!-- Value -->
<input type="text" data-i18n-value="default_value" value="..." />

<!-- HTML (attention XSS) -->
<div data-i18n-html="rich_content">...</div>
```

### 3. Détection automatique

Le système :
1. **Vérifie localStorage** : Si l'utilisateur a déjà choisi une langue → l'utilise
2. **Détecte le navigateur** : Lit `navigator.language` (ex: `fr-FR` → `fr`)
3. **Fallback** : Si la langue n'existe pas → bascule sur l'anglais

### 4. Sélecteur de langue (optionnel)

```html
<div class="lang-switcher">
  <button data-lang-btn="fr" onclick="switchLanguage('fr')">FR</button>
  <button data-lang-btn="en" onclick="switchLanguage('en')">EN</button>
  <button data-lang-btn="de" onclick="switchLanguage('de')">DE</button>
  ...
</div>
```

**Style CSS :** les boutons actifs reçoivent la classe `.active`

```css
[data-lang-btn].active {
  background-color: var(--accent);
  color: white;
}
```

## 📝 Ajouter une nouvelle traduction

### 1. Ajouter la clé dans **tous** les fichiers JSON

**`locales/fr.json`** :
```json
{
  "new_key": "Valeur française",
  ...
}
```

**`locales/en.json`** :
```json
{
  "new_key": "English value",
  ...
}
```

### 2. Utiliser dans l'HTML

```html
<button data-i18n="new_key">Default text</button>
```

## 🎯 Ajouter une nouvelle langue

### 1. Créer `locales/XX.json`

```json
{
  "nav_features": "Traduction en langue XX",
  "nav_how": "...",
  ...
}
```

### 2. Ajouter au tableau `SUPPORTED_LANGS`

Dans `js/i18n.js` :
```javascript
const SUPPORTED_LANGS = ['fr', 'en', 'es', 'de', 'ru', ..., 'xx'];
```

### 3. Ajouter le bouton au sélecteur (optionnel)

```html
<button data-lang-btn="xx" onclick="switchLanguage('xx')">XX</button>
```

## 💡 Fonctions JavaScript disponibles

### `switchLanguage(lang)`
Change manuellement de langue
```javascript
switchLanguage('es'); // Bascule vers l'espagnol
```

### `t(key)`
Récupère la traduction d'une clé (utile pour le contenu dynamique)
```javascript
const message = t('welcome_message');
document.getElementById('output').textContent = message;
```

### `initI18n()`
Initialise le système (appelé automatiquement au chargement)
```javascript
await initI18n();
```

## ⚙️ Configuration

### Langue par défaut
Dans `js/i18n.js` :
```javascript
const DEFAULT_LANG = 'en';
```

### Format des clés JSON
- **Hiérarchique** : `nav_features`, `section_features`, `feature_tickets_desc`
- **Constante** : pas de majuscules, traits d'union pour les espaces
- **Descriptive** : `btn_add_discord` plutôt que `button1`

## 🔍 Débogage

Ouvrez la console du navigateur et vérifiez :

```javascript
// Voir la langue actuelle
console.log(document.documentElement.lang);

// Voir les traductions chargées
console.log(currentTranslations);

// Voir la préférence sauvegardée
console.log(localStorage.getItem('vai_lang'));
```

## ⚡ Performance

- **Lazy loading** : les JSON sont chargés uniquement quand nécessaire
- **Cache localStorage** : la préférence est mémorisée
- **Fallback rapide** : basculement instantané sur l'anglais en cas d'erreur
- **Pas de dépendances** : pur JavaScript vanilla

## 🔒 Sécurité

⚠️ **Attention** : `data-i18n-html` insère du HTML brut. À utiliser UNIQUEMENT avec du contenu de confiance (pas d'input utilisateur).

Pour du contenu utilisateur, utiliser `data-i18n` (textContent) à la place.

## 📌 Checklist d'intégration

- [ ] Script `i18n.js` chargé dans le `<head>`
- [ ] Fichiers JSON dans `/locales`
- [ ] Attributs `data-i18n` ajoutés aux éléments
- [ ] Sélecteur de langue implémenté (optionnel)
- [ ] Styles CSS pour `.active` sur les boutons
- [ ] Testé dans au moins 2 langues différentes
- [ ] Vérification du fallback (désactiver les locales dans DevTools)

---

**Version** : 1.0  
**Dernière mise à jour** : 2025-02-24  
**Maintenu par** : Veridian AI Team
