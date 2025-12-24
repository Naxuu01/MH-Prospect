# 📋 Guide de Configuration de l'Agent

## Nouveau Fonctionnement : Recherche de Prospects Qualifiés

L'agent fonctionne maintenant différemment : au lieu de chercher une "niche" d'entreprises, vous définissez **votre secteur** et **votre service**, et l'agent trouve des prospects qui pourraient avoir besoin de ce service.

## Configuration dans `config.yaml`

### Paramètres Principaux

```yaml
# Votre entreprise
secteur_entreprise: "Marketing Digital"  # Le secteur dans lequel vous travaillez
service_propose: "création de sites web et visibilité en ligne"  # Ce que vous proposez

# Zone de prospection
ville: "Genève"
pays: "Suisse"
```

### Exemples de Configuration

#### Exemple 1 : Création de Sites Web
```yaml
secteur_entreprise: "Développement Web"
service_propose: "création de sites web professionnels"
ville: "Genève"
pays: "Suisse"
```

#### Exemple 2 : Marketing Digital
```yaml
secteur_entreprise: "Marketing Digital"
service_propose: "stratégies marketing et gestion des réseaux sociaux"
ville: "Lausanne"
pays: "Suisse"
```

#### Exemple 3 : Conseil en Comptabilité
```yaml
secteur_entreprise: "Conseil Financier"
service_propose: "conseil comptable et gestion administrative"
ville: "Zurich"
pays: "Suisse"
```

#### Exemple 4 : Services IT
```yaml
secteur_entreprise: "Informatique"
service_propose: "support technique et maintenance informatique"
ville: "Bâle"
pays: "Suisse"
```

## Comment l'Agent Trouve les Prospects

L'agent analyse votre `service_propose` et adapte sa recherche :

- **Si service = "site web"** → Cherche des entreprises locales (souvent sans site ou avec site obsolète)
- **Si service = "marketing"** → Cherche des PME et commerces locaux
- **Si service = "conseil"** → Cherche des entreprises dans votre secteur
- **Sinon** → Cherche des PME et entreprises locales génériques

## Résultat

L'agent trouvera des entreprises qualifiées qui correspondent à votre zone de prospection et qui pourraient avoir besoin de votre service, plutôt que de chercher un type d'entreprise spécifique.

