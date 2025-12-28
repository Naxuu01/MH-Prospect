# 🌐 Interface Web avec Pterodactyl

## Réponse à votre question

**Oui, c'est tout à fait possible de faire une interface web avec Pterodactyl !** Voici comment :

## ✅ Solutions Possibles

### Option 1 : Interface Web dans le même conteneur (Recommandée)

L'agent Python peut exposer une interface web Flask/FastAPI qui tourne dans le même conteneur Pterodactyl :

```python
# web_interface.py
from flask import Flask, render_template, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/')
def dashboard():
    # Afficher les prospects
    return render_template('dashboard.html')

@app.route('/api/prospects')
def api_prospects():
    conn = sqlite3.connect('prospects.db')
    # ... récupérer les prospects
    return jsonify(prospects)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Modifications nécessaires dans l'egg Pterodactyl :**
1. Dans la commande `startup`, lancer l'interface web ET l'agent :
   ```json
   "startup": "python3 web_interface.py & python3 main.py"
   ```

2. Ouvrir un port dans Pterodactyl :
   - Aller dans "Settings" du serveur
   - Ajouter un port (ex: 5000)
   - Configurer le mapping réseau

**Avantages :**
- ✅ Simple à mettre en place
- ✅ Un seul conteneur
- ✅ Pas besoin de configuration complexe

**Inconvénients :**
- ⚠️ Si l'agent crash, l'interface web aussi (mais on peut les séparer)

### Option 2 : Deux serveurs Pterodactyl

1. **Serveur 1** : Agent de prospection (`main.py`)
2. **Serveur 2** : Interface web (Flask/FastAPI)

Les deux partagent la même base de données SQLite via un volume partagé ou une base de données distante (PostgreSQL, MySQL).

**Avantages :**
- ✅ Séparation des responsabilités
- ✅ L'interface web peut tourner indépendamment

**Inconvénients :**
- ⚠️ Nécessite deux serveurs
- ⚠️ Configuration plus complexe

### Option 3 : Interface web externe (recommandée pour production)

Déployer l'interface web sur un hébergeur web classique (Heroku, Railway, VPS) qui se connecte à la base SQLite via un système de synchronisation ou une API.

## 🚀 Implémentation Recommandée pour Pterodactyl

### Étape 1 : Créer l'interface web

Créer un fichier `web_interface.py` qui expose :
- Dashboard avec statistiques
- Liste des prospects avec filtres
- Export CSV/Excel/PDF
- Édition des statuts

### Étape 2 : Modifier le startup command

Dans `egg-mhprospect.json` :
```json
"startup": "bash -c \"cd /home/container && if ! python3 -c 'import yaml' 2>/dev/null; then python3 -m pip install --upgrade pip --break-system-packages 2>&1 && python3 -m pip install -r requirements.txt --break-system-packages 2>&1; fi && python3 web_interface.py & python3 main.py\""
```

### Étape 3 : Configurer le port dans Pterodactyl

1. Aller dans les paramètres du serveur
2. Aller dans "Network"
3. Ajouter un port alloué (ex: 5000)
4. Configurer le mapping : `127.0.0.1:5000` → `container:5000`

### Étape 4 : Accéder à l'interface

Accédez via : `http://votre-serveur-ip:5000`

## 📝 Note Importante

**Pour un environnement Pterodactyl, je recommande :**
- Interface web simple (Flask minimaliste)
- Port configuré dans Pterodactyl
- Les deux processus (web + agent) dans le même conteneur

**Si vous voulez que je crée l'interface web complète, dites-le moi !** Je peux créer :
- Dashboard avec statistiques
- Liste des prospects triable/filtrable
- Export intégré
- Édition des statuts

---

**Réponse courte : Oui, c'est possible et même assez simple avec Pterodactyl !** 🎉

