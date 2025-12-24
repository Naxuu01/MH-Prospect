# Agent de Prospection B2B Autonome 🤖

Agent Python autonome qui recherche, enrichit et génère des messages de prospection personnalisés pour des entreprises B2B.

## 🎯 Fonctionnalités

- **Recherche automatique** : Trouve des entreprises selon une niche et une ville via Serper.dev
- **Enrichissement de données** : Récupère emails, téléphones, informations dirigeants via Hunter.io
- **Recherche LinkedIn** : Localise les profils LinkedIn des entreprises et dirigeants
- **Génération IA** : Crée des messages de prospection ultra-personnalisés avec GPT-4o-mini
- **Stockage SQLite** : Sauvegarde tous les prospects dans une base de données
- **Boucle autonome** : Traite une entreprise toutes les 2 minutes (120 secondes)

## 📋 Prérequis

1. **Clés API nécessaires** :
   - [Serper.dev](https://serper.dev) - API de recherche Google
   - [Hunter.io](https://hunter.io) - Recherche d'emails B2B
   - [OpenAI](https://openai.com) - Génération de messages IA

2. **Python 3.8+**

## 🚀 Installation

1. **Cloner ou télécharger le projet**

2. **Installer les dépendances** :
```bash
pip install -r requirements.txt
```

3. **Configurer les clés API** :
   - Créez un fichier `.env` à la racine du projet
   - Ajoutez vos clés API :
```env
SERPER_API_KEY=votre_cle_serper
HUNTER_API_KEY=votre_cle_hunter
OPENAI_API_KEY=votre_cle_openai
```

4. **Configurer le fichier `config.yaml`** :
```yaml
niche: "Plombiers"  # Type d'entreprises recherchées
ville: "Paris"       # Ville de recherche
pays: "France"       # Pays de recherche
message_base: |      # Template de votre message
  Bonjour {nom_dirigeant},
  ...
proposition_valeur: "votre proposition de valeur"
nombre_resultats_serper: 10
```

## 💻 Utilisation

**Lancer l'agent** :
```bash
python main.py
```

L'agent va :
1. Charger une liste initiale de prospects depuis Serper
2. Traiter chaque prospect toutes les 2 minutes :
   - Rechercher email et dirigeant via Hunter.io
   - Rechercher LinkedIn
   - Générer un message personnalisé avec OpenAI
   - Sauvegarder dans la base SQLite (`prospects.db`)
   - Afficher un résumé complet dans la console
3. Si la file d'attente est vide, relancer une nouvelle recherche automatiquement

**Arrêter l'agent** : `Ctrl+C`

## 📊 Structure de la base de données

La base `prospects.db` contient une table `prospects` avec les champs suivants :
- `nom_entreprise` : Nom de l'entreprise
- `site_web` : URL du site web
- `telephone` : Numéro de téléphone
- `email` : Email du dirigeant ou email générique
- `nom_dirigeant` : Nom du dirigeant
- `poste_dirigeant` : Poste du dirigeant (CEO, Fondateur, etc.)
- `linkedin_entreprise` : URL LinkedIn de l'entreprise
- `linkedin_dirigeant` : URL LinkedIn du dirigeant
- `message_personnalise` : Message généré par l'IA
- `point_specifique` : Point identifié par l'IA sur l'entreprise
- `date_ajout` : Date d'ajout du prospect
- `date_traitement` : Date de traitement
- `statut` : Statut du prospect

## 🔧 Personnalisation

### Modifier l'intervalle de traitement

Dans `main.py`, modifiez la valeur de `self.intervalle_traitement` :
```python
self.intervalle_traitement = 120  # En secondes (2 minutes par défaut)
```

### Modifier le message de base

Éditez le fichier `config.yaml` et modifiez le champ `message_base`. Utilisez les placeholders suivants :
- `{nom_dirigeant}` : Nom du dirigeant
- `{nom_entreprise}` : Nom de l'entreprise
- `{point_specifique}` : Point spécifique identifié par l'IA
- `{proposition_valeur}` : Proposition de valeur

## 🛡️ Gestion d'erreurs

L'agent est conçu pour être robuste :
- Si Hunter.io ne trouve pas d'email de dirigeant, recherche un email générique sur le site web
- Si une erreur survient, l'agent attend 2 minutes avant de traiter le prospect suivant
- Les prospects déjà traités sont automatiquement exclus des nouvelles recherches
- En cas d'erreur API, l'agent continue avec les données disponibles

## 📈 Stratégie des 2 minutes

Le délai de 2 minutes entre chaque prospect est stratégique :
- ✅ **Évite le spam** : Un rythme naturel et humain
- ✅ **Faible consommation** : Le script passe 99% du temps en sommeil
- ✅ **Valeur perçue** : Le tableau de bord se remplit progressivement
- ✅ **Respect des limites API** : Évite les rate limits

## 📝 Logs

L'agent affiche des logs détaillés dans la console avec :
- Progression du traitement
- Statistiques (total, avec email, traités)
- Résumés complets de chaque prospect traité
- Messages d'erreur si nécessaire

## 🔍 Consultation de la base de données

Pour consulter les prospects sauvegardés, vous pouvez utiliser SQLite :
```bash
sqlite3 prospects.db
SELECT * FROM prospects;
```

Ou utiliser un outil graphique comme [DB Browser for SQLite](https://sqlitebrowser.org/).

## ⚠️ Notes importantes

- Assurez-vous d'avoir des quotas suffisants sur vos APIs
- Respectez les conditions d'utilisation de Serper.dev, Hunter.io et OpenAI
- Les emails génériques (contact@, info@) sont utilisés si aucun dirigeant n'est trouvé
- L'agent peut être arrêté et relancé : il ne retraitera pas les entreprises déjà en base

## 📞 Support

Pour toute question ou problème, vérifiez :
1. Que toutes les clés API sont correctement configurées dans `.env`
2. Que le fichier `config.yaml` est bien formaté (YAML valide)
3. Les logs pour identifier les erreurs spécifiques

---

**Développé avec ❤️ pour la prospection B2B automatisée**
