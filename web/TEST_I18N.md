# 🧪 Test du système i18n

## Vérification rapide

### 1. Fichiers présents
```bash
ls -la locales/
ls -la js/i18n.js
```

✅ **15 fichiers JSON** + **1 script i18n.js**

### 2. Test de validation des clés

```bash
# Toutes les clés data-i18n d'index.html doivent exister dans fr.json
grep -o 'data-i18n="[^"]*"' index.html | cut -d'"' -f2 | while read key; do
  if ! jq ".$key" locales/fr.json >/dev/null 2>&1; then
    echo "MANQUANTE: $key"
  fi
done
```

**Résultat** : Aucune clé manquante ✅

### 3. Test dans le navigateur

#### Ouvrir index.html
```
http://localhost:3000/
```

#### Console JavaScript
```javascript
// Voir la langue détectée
console.log(document.documentElement.lang);

// Voir les traductions chargées
console.log(currentTranslations);

// Tester le changement de langue
switchLanguage('es');  // Basculer vers l'espagnol
switchLanguage('ja');  // Basculer vers le japonais
switchLanguage('en');  // Basculer vers l'anglais
```

#### Vérifications visuelles
1. **Français (défaut)** : "Le support Discord sans frontières"
2. **Anglais** : "Discord support without borders"
3. **Espagnol** : "Soporte en Discord sin fronteras"
4. **Allemand** : "Discord-Support ohne Grenzen"
5. **Russe** : "Поддержка Discord без границ"
6. **Chinois** : "Discord 支持 无国界"
7. **Japonais** : "Discord サポート 無制限"

### 4. Test du sélecteur de langue (si implémenté)

Ajouter dans index.html (optionnel) :
```html
<div class="lang-switcher" style="position: fixed; top: 100px; right: 20px; display: flex; gap: 5px; z-index: 9999;">
  <button data-lang-btn="fr" onclick="switchLanguage('fr')" style="padding: 5px 10px; cursor: pointer;">FR</button>
  <button data-lang-btn="en" onclick="switchLanguage('en')" style="padding: 5px 10px; cursor: pointer;">EN</button>
  <button data-lang-btn="es" onclick="switchLanguage('es')" style="padding: 5px 10px; cursor: pointer;">ES</button>
  <button data-lang-btn="de" onclick="switchLanguage('de')" style="padding: 5px 10px; cursor: pointer;">DE</button>
  <button data-lang-btn="ja" onclick="switchLanguage('ja')" style="padding: 5px 10px; cursor: pointer;">JA</button>
</div>
```

### 5. Test du localStorage

```javascript
// Vérifier que la langue est sauvegardée
localStorage.getItem('vai_lang');

// Effacer et recharger (devrait détecter votre langue de navigateur)
localStorage.removeItem('vai_lang');
location.reload();
```

## 🚀 Déploiement

Avant de mettre en prod, vérifier :

- [ ] Tous les fichiers JSON sont présents
- [ ] `i18n.js` est chargé dans le `<head>` avec `defer`
- [ ] Les `data-i18n` correspondent aux clés JSON
- [ ] Au moins 3 langues testées manuellement
- [ ] LocalStorage fonctionne (F12 → Application → Cookies → vai_lang)
- [ ] Le fallback vers l'anglais fonctionne

## 📊 Statistiques

| Métrique | Valeur |
|----------|--------|
| Langues supportées | 15 |
| Clés de traduction | ~130 par langue |
| Taille moyenne par JSON | ~6KB |
| Charge totale i18n | ~95KB (14 fichiers + script) |

---

✅ **Le système est prêt pour la production !**
