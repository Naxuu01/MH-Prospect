# 🌐 Guide d'Installation - Interface Web

## ✅ Ce qui a été créé

1. **`web_interface.py`** : Interface web Flask complète
2. **`start_agent.py`** : Script pour lancer agent + interface web ensemble
3. **`requirements.txt`** : Mis à jour avec Flask

## 🚀 Installation dans Pterodactyl

### Option 1 : Utiliser start_agent.py (Recommandée)

Modifier la commande `startup` dans l'egg Pterodactyl :

```json
"startup": "bash -c \"cd /home/container && if ! python3 -c 'import yaml' 2>/dev/null; then echo 'Installing Python packages...' && python3 -m pip install --upgrade pip --break-system-packages 2>&1 && python3 -m pip install -r requirements.txt --break-system-packages 2>&1 || echo 'Package installation completed'; fi && python3 start_agent.py\""
```

**Avantages :**
- ✅ Lance automatiquement l'agent ET l'interface web
- ✅ L'interface web utilise le port automatique de Pterodactyl
- ✅ Tout fonctionne dans le même conteneur

### Option 2 : Lancer seulement l'interface web

Si vous voulez juste l'interface web (pour visualiser des prospects existants) :

```json
"startup": "bash -c \"cd /home/container && if ! python3 -c 'import flask' 2>/dev/null; then python3 -m pip install --upgrade pip --break-system-packages 2>&1 && python3 -m pip install -r requirements.txt --break-system-packages 2>&1; fi && python3 web_interface.py\""
```

### Option 3 : Garder main.py seul

Si vous ne voulez PAS l'interface web, gardez l'ancien startup :

```json
"startup": "bash -c \"cd /home/container && if ! python3 -c 'import yaml' 2>/dev/null; then echo 'Installing Python packages...' && python3 -m pip install --upgrade pip --break-system-packages 2>&1 && python3 -m pip install -r requirements.txt --break-system-packages 2>&1 || echo 'Package installation completed'; fi && python3 main.py\""
```

## 📋 Configuration du Port dans Pterodactyl

**Pterodactyl gère automatiquement le port !** Vous n'avez rien à faire :

1. Quand vous créez un serveur, Pterodactyl alloue automatiquement un port
2. Ce port est disponible via la variable d'environnement `SERVER_PORT`
3. L'interface web lit automatiquement cette variable
4. Si pas disponible, elle utilise le port 5000 par défaut

**Vérifier le port :**
- Dans Pterodactyl, allez dans les paramètres du serveur
- Onglet "Network" → vous verrez le port alloué
- Accédez à l'interface via : `http://votre-ip:PORT`

## 🎯 Fonctionnalités de l'Interface

### Dashboard
- ✅ Statistiques en temps réel : Total, Emails, Téléphones, Score moyen
- ✅ Rafraîchissement automatique toutes les 30 secondes

### Liste des Prospects
- ✅ Tri par colonne (Score, Nom, Email, etc.)
- ✅ Recherche en temps réel
- ✅ Filtres par score (Excellent, Bon, Moyen, Faible)
- ✅ Filtres par statut (Nouveau, Traité, Contacté, etc.)
- ✅ Affichage des technologies détectées
- ✅ Badges de score colorés
- ✅ Statut email (valide/invalide)

### Export
- ✅ Boutons d'export direct : CSV, Excel, PDF, JSON
- ✅ Fichiers téléchargeables immédiatement

### Édition
- ✅ Édition du statut d'un prospect
- ✅ Modal d'édition rapide

## 🎨 Design

L'interface est :
- ✅ Moderne et responsive
- ✅ Compatible mobile/tablette
- ✅ Design épuré et professionnel
- ✅ Couleurs et badges pour faciliter la lecture

## 🔧 Personnalisation

Si vous voulez modifier l'interface :

1. Éditez `web_interface.py`
2. La section CSS est dans `HTML_TEMPLATE`
3. Les routes API sont en bas du fichier
4. Redémarrez le serveur pour voir les changements

## ⚠️ Notes Importantes

1. **Performance** : L'interface affiche max 500 prospects par défaut (ligne 236 de web_interface.py)
2. **Sécurité** : L'interface est ouverte sans authentification (ajoutez-en une si nécessaire pour production)
3. **Base de données** : Utilise la même DB (`prospects.db`) que l'agent
4. **Concurrence** : SQLite gère bien la lecture simultanée, mais l'écriture est séquentielle

## 🐛 Dépannage

### L'interface ne démarre pas
- Vérifiez que Flask est installé : `pip install flask`
- Vérifiez les logs dans Pterodactyl
- Vérifiez que le port est bien alloué

### Erreur "Address already in use"
- Le port est peut-être déjà utilisé
- Vérifiez qu'un autre processus n'utilise pas le port
- Changez le port dans Pterodactyl ou utilisez une variable d'environnement

### L'interface ne charge pas les prospects
- Vérifiez que `prospects.db` existe
- Vérifiez les permissions de lecture
- Regardez les logs de l'interface web dans Pterodactyl

## 📞 Support

Pour toute question ou problème, vérifiez :
1. Les logs dans Pterodactyl
2. Que toutes les dépendances sont installées
3. Que le port est bien configuré

---

**Profitez de votre nouvelle interface web ! 🎉**

