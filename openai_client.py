"""
Module client pour OpenAI - Génération de messages personnalisés.
"""
import json
import os
import openai
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Désactiver les proxies pour OpenAI (certaines configs système causent des erreurs)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)


class OpenAIClient:
    """Client pour interroger l'API OpenAI."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialise le client OpenAI.
        
        Args:
            api_key: Clé API OpenAI
            model: Modèle à utiliser (par défaut: gpt-4o-mini)
        """
        self.api_key = api_key
        self.model = model
    
    def generer_message_personnalise(self, entreprise_data: Dict[str, Any], 
                                    message_base: str, 
                                    proposition_valeur: str,
                                    service_propose: str = "",
                                    secteur_entreprise: str = "") -> Dict[str, str]:
        """
        Génère un message de prospection personnalisé avec GPT.
        
        Args:
            entreprise_data: Dictionnaire contenant les données de l'entreprise
            message_base: Template de message de base
            proposition_valeur: Proposition de valeur à inclure
        
        Returns:
            Dictionnaire contenant le message personnalisé et le point spécifique identifié
        """
        try:
            nom_entreprise = entreprise_data.get("nom_entreprise", "cette entreprise")
            site_web = entreprise_data.get("site_web", "")
            description = entreprise_data.get("description", "")
            
            # Échapper les accolades pour éviter les problèmes avec f-strings
            message_base_escaped = message_base.replace("{", "{{").replace("}", "}}")
            proposition_valeur_escaped = proposition_valeur.replace("{", "{{").replace("}", "}}")
            
            # Ajouter contexte du secteur/service si fourni
            contexte_service = ""
            if service_propose:
                contexte_service += f"\nNOTRE SERVICE: {service_propose}"
            if secteur_entreprise:
                contexte_service += f"\nNOTRE SECTEUR: {secteur_entreprise}"
            
            prompt = f"""Tu es un expert en prospection B2B universel. Analyse les informations suivantes et génère un message de prospection ultra-personnalisé adapté à NOTRE service.

INFORMATIONS DE L'ENTREPRISE CIBLE:
- Nom: {nom_entreprise}
- Site web: {site_web}
- Description: {description}
{contexte_service}

TEMPLATE DE MESSAGE:
{message_base_escaped}

PROPOSITION DE VALEUR: {proposition_valeur_escaped}

TÂCHES:
1. Identifie UN point spécifique et positif sur cette entreprise qui montre leur qualité/expertise (ex: "votre expertise en rénovation de salles de bain", "vos 15 ans d'expérience", "votre présence sur 3 villes", "vos excellents avis clients", "votre spécialisation en [domaine]", etc.)
2. Génère un message personnalisé en remplaçant:
   - {{nom_entreprise}} par le vrai nom
   - {{point_specifique}} par le point identifié
   - {{proposition_valeur}} par la proposition fournie
   - Adapte le ton selon le secteur et le type d'entreprise (plus formel pour cabinets, plus accessible pour commerces)

IMPORTANT:
- Sois naturel, authentique et professionnel
- Inclus le point spécifique identifié pour montrer que tu connais leur entreprise
- Adapte le langage à leur secteur d'activité
- Reste concis et impactant
- Termine par un appel à l'action clair et engageant

Réponds UNIQUEMENT avec un JSON au format suivant (sans markdown, sans code block):
{{
    "point_specifique": "le point identifié ici",
    "message_personnalise": "le message complet ici"
            }}
"""
            
            # Créer le client OpenAI sans proxies
            client = openai.OpenAI(
                api_key=self.api_key,
                # S'assurer qu'aucun proxy n'est utilisé
                http_client=None
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en prospection B2B. Tu génères toujours des réponses au format JSON valide."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Nettoyer le contenu si il contient des markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            logger.info(f"Message personnalisé généré pour {nom_entreprise}")
            return {
                "message_personnalise": result.get("message_personnalise", message_base),
                "point_specifique": result.get("point_specifique", "expertise dans votre domaine")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            # Retourner un message par défaut
            return {
                "message_personnalise": message_base.replace("{nom_dirigeant}", "Monsieur/Madame")
                    .replace("{nom_entreprise}", nom_entreprise)
                    .replace("{point_specifique}", "votre expertise")
                    .replace("{proposition_valeur}", proposition_valeur),
                "point_specifique": "expertise dans votre domaine"
            }
        except Exception as e:
            logger.error(f"Erreur lors de la génération du message pour {nom_entreprise}: {e}")
            # Retourner un message par défaut
            return {
                "message_personnalise": message_base.replace("{nom_dirigeant}", "Monsieur/Madame")
                    .replace("{nom_entreprise}", nom_entreprise)
                    .replace("{point_specifique}", "votre expertise")
                    .replace("{proposition_valeur}", proposition_valeur),
                "point_specifique": "expertise dans votre domaine"
            }
    
    def analyser_entreprise_pertinence(self, entreprise_data: Dict[str, Any], 
                                      service_propose: str, 
                                      secteur_entreprise: str) -> Dict[str, str]:
        """
        Analyse une entreprise pour expliquer pourquoi elle est pertinente et ce qu'on peut lui proposer.
        
        Args:
            entreprise_data: Dictionnaire contenant les données de l'entreprise
            service_propose: Service que nous proposons
            secteur_entreprise: Secteur dans lequel nous travaillons
        
        Returns:
            Dictionnaire contenant:
            - raison_choix: Pourquoi cette entreprise a été choisie
            - proposition_service: Ce qu'on peut vraiment leur proposer
        """
        try:
            nom_entreprise = entreprise_data.get("nom_entreprise", "cette entreprise")
            site_web = entreprise_data.get("site_web", "")
            description = entreprise_data.get("description", "")
            adresse = entreprise_data.get("adresse_complete", "")
            industrie = entreprise_data.get("industrie", "")
            taille = entreprise_data.get("taille_entreprise", "")
            note_google = entreprise_data.get("note_google")
            nb_avis = entreprise_data.get("nb_avis_google")
            
            prompt = f"""Tu es un expert en prospection B2B universel. Analyse cette entreprise et génère une proposition UNIQUE et PERSONNALISÉE adaptée à NOTRE service spécifique.

INFORMATIONS DE L'ENTREPRISE À PROSPECTER:
- Nom: {nom_entreprise}
- Site web: {site_web}
- Description: {description}
- Adresse: {adresse}
- Industrie: {industrie}
- Taille: {taille}
- Note Google: {note_google}
- Nombre d'avis: {nb_avis}

NOTRE ENTREPRISE (LE VENDEUR):
- Secteur d'activité: {secteur_entreprise}
- Service que nous proposons: {service_propose}

⚠️ MISSION: Expliquer pourquoi cette entreprise a BESOIN de notre service spécifique et comment nous pouvons les aider.

ANALYSE INTELLIGENTE ET ADAPTATIVE:

1. POURQUOI CETTE ENTREPRISE (raison_choix):
   a) Identifie le type d'entreprise (ex: boulangerie, garage, cabinet comptable, restaurant, plombier, architecte, agence, etc.)
   
   b) Analyse les SIGNaux DE BESOIN CONCRETS selon notre service "{service_propose}":
      
      **ANALYSE APPROFONDIE POUR SERVICES WEB/DIGITAUX** (développeurs web, agences web, agences de com):
      
      **POUR SERVICES WEB/DÉVELOPPEMENT:**
      
      🔍 **Analyse du site web (si existe):**
      - Site web: {site_web}
      - Vérifie si le site existe réellement, s'il est accessible, s'il charge vite
      - Design obsolète (style années 2010, couleurs passées, typographie datée)
      - Site non responsive (ne s'adapte pas au mobile/tablette) = 60%+ des visiteurs perdus
      - Site lent (temps de chargement >3 secondes) = perte de conversions
      - Pas de HTTPS/SSL = problème de sécurité et SEO
      - Interface utilisateur confuse ou peu intuitive
      - Pas de formulaire de contact visible
      - Navigation peu claire ou désorganisée
      - Site WordPress/Shopify/Prestashop ancien (version obsolète) = risques sécurité
      
      🎯 **Opportunités techniques identifiables:**
      - Pas de site web = perte massive de clients et crédibilité
      - Site sans e-commerce alors que commerce physique = manque de revenus en ligne
      - Site vitrine statique alors que besoin de fonctionnalités dynamiques
      - Pas de système de réservation en ligne (restaurants, hôtels, services)
      - Pas de formulaire de devis/devis automatique (artisans, services)
      - Pas d'intégration Google Maps (localisation pour commerces locaux)
      - Pas de blog/contenu = manque de SEO et autorité
      - Pas de système d'avis clients intégré
      - Pas de chat en ligne ou support client digital
      
      📱 **Analyse mobile/digital:**
      - Site pas optimisé mobile = perte de 50-70% du trafic
      - Pas d'app mobile alors que concurrents en ont
      - Pas de présence sur Google My Business optimisée
      - Pas d'intégration réseaux sociaux (liens, widgets)
      
      🔎 **Analyse SEO/Visibilité:**
      - Site pas optimisé SEO = invisible sur Google
      - Pas de référencement local (Google Maps, avis)
      - Contenu pauvre ou daté = mauvais classement Google
      - Pas de mots-clés locaux ("[ville] [métier]")
      - Pas de backlinks ou stratégie de netlinking
      - Site indexé mais mal classé = opportunité SEO
      
      **POUR SERVICES MARKETING DIGITAL/COMMUNICATION:**
      
      📊 **Analyse de visibilité digitale:**
      - Faible présence en ligne = manque de crédibilité et clients
      - Peu ou pas d'avis clients Google = manque de confiance
      - Note Google <4.5 = opportunité d'amélioration réputation
      - Pas de stratégie réseaux sociaux active = perte d'engagement
      - Pas de contenu régulier (blog, posts) = faible autorité
      - Pas de publicité en ligne (Google Ads, Facebook Ads) = perte de leads
      - Concurrents mieux visibles = opportunité de rattrapage
      
      🎯 **Opportunités marketing identifiables:**
      - Pas de présence Instagram/Facebook alors que secteur l'exige (restaurants, boutiques)
      - Pas de stratégie email marketing = perte d'opportunités de fidélisation
      - Pas de campagnes saisonnières ou événementielles
      - Pas de partenariats locaux ou influenceurs locaux
      - Pas de stratégie de collecte d'avis clients
      - Pas de système de parrainage ou programme fidélité digital
      
      💰 **Analyse ROI/Trafic:**
      - Site avec peu de trafic = opportunité croissance
      - Pas d'analyse de données (Google Analytics) = décisions non éclairées
      - Taux de conversion faible = optimisation nécessaire
      - Pas de suivi des leads/contacts = perte d'opportunités
      
      **POUR CONSEIL/ACCOMPAGNEMENT DIGITAL:**
      - Manque d'expertise digitale visible = besoin d'accompagnement
      - Transition digitale incomplète ou mal menée
      - Défis identifiables dans leur secteur digital
      - Besoin de stratégie digitale globale
      
      ⚠️ **Analyse contextuelle:**
      - Utilise TOUTES les informations disponibles: description, site web, note Google, nombre d'avis, adresse, type d'entreprise
      - Identifie des signaux SPECIFIQUES et FACTUELS, pas des suppositions
      - Combine plusieurs signaux pour une analyse solide
      - Adapte l'analyse au secteur d'activité (commerce local ≠ service B2B ≠ industrie)
   
   c) Utilise les informations disponibles (description, site web, note, etc.) pour être FACTUEL
   
   d) Format: 3-4 phrases, ultra-spécifique à CETTE entreprise et à NOTRE service

2. PROPOSITION DE SERVICE (proposition_service):
   Adapte notre service "{service_propose}" au contexte de cette entreprise spécifique.
   
   a) IDENTIFIE comment notre service s'applique à leur type d'entreprise avec DÉTAILS TECHNIQUES:
      
      **PROPOSITIONS APPROFONDIES PAR TYPE D'ENTREPRISE** (développeurs web, agences web, agences de com):
      
      🏪 **COMMERCES LOCAUX** (restaurants, boutiques, artisans, plombiers, électriciens, coiffeurs, boulangeries, etc.):
      
      **Si service web/développement:**
      - "Site web moderne et responsive avec: système de réservation/commande en ligne intégré, carte interactive avec Google Maps pour localisation, horaires d'ouverture dynamiques, galerie photos produits/prestations, formulaire de devis/contact optimisé, intégration Google My Business, SEO local ultra-optimisé pour apparaître en première page Google lors des recherches '[ville] [métier]' ou '[votre métier] près de moi', blog avec conseils pour générer du trafic organique, système d'avis clients intégré, chat en ligne pour conversion immédiate, et optimisation mobile-first pour capturer 60%+ du trafic mobile"
      
      - "E-commerce léger (pour boutiques): catalogue produits, panier sécurisé, paiement en ligne, gestion stocks basique, intégration transporteurs locaux, commande et retrait en magasin"
      
      **Si service marketing digital:**
      - "Stratégie marketing digitale complète: optimisation Google My Business pour apparaître en map pack Google, stratégie de collecte d'avis clients (objectif 4.7+ étoiles), campagnes Google Ads locales ciblées '[ville] [métier]', campagnes Facebook/Instagram avec géolocalisation, partenariats avec influenceurs locaux, email marketing pour fidélisation, contenu Instagram/Facebook régulier (stories, posts, reels), campagnes saisonnières et événementielles, système de parrainage digital"
      
      🏢 **SERVICES PROFESSIONNELS** (cabinets comptables, fiduciaires, avocats, architectes, consultants, agences):
      
      **Si service web/développement:**
      - "Site web corporate professionnel avec: présentation détaillée de l'équipe et expertise, blog régulier avec conseils/contenus de valeur (SEO + autorité), formulaire de contact avancé avec qualification leads, section témoignages clients, présentation des services avec cas d'études, intégration calendrier pour prise de RDV en ligne, zone membres/client privée si nécessaire, SEO professionnel pour '[ville] [service]', intégration LinkedIn pour crédibilité, newsletter pour nurturing, et design premium qui inspire confiance"
      
      **Si service marketing digital:**
      - "Stratégie B2B digitale: LinkedIn company page optimisée + LinkedIn Ads ciblés dirigeants, content marketing avec articles LinkedIn/Medium, stratégie de référencement professionnel, email marketing B2B ciblé, webinaires ou événements en ligne, partenariats stratégiques B2B, stratégie de pensée leadership, génération de leads qualifiés via formulaires/gated content"
      
      🏨 **HÔTELS/RESTAURANTS:**
      
      **Si service web/développement:**
      - "Site web haut de gamme avec: système de réservation en ligne intégré (Booking.com, Airbnb, ou système propriétaire), galerie photos immersives (chambres, plats, ambiance), menu interactif en ligne (restaurants), intégration avis clients (TripAdvisor, Google), système de newsletter pour offres spéciales, blog voyage/culinaire pour SEO, optimisation mobile ultra-importante, intégration Google Maps avec itinéraires, multilingue si zone touristique, booking calendar pour disponibilités en temps réel"
      
      **Si service marketing digital:**
      - "Stratégie digitale hôtellerie/restauration: présence Instagram forte (photos plats/chambres, stories quotidiennes), campagnes Google Ads 'hôtel [ville]' et 'restaurant [ville]', gestion proactive des avis (répondre à tous, améliorer notes), partenariats avec blogueurs voyage/food, stratégie TripAdvisor, email marketing avec offres exclusives, campagnes saisonnières (été, Noël, etc.), influencer marketing local, live Instagram/Facebook pour engagement"
      
      🏭 **INDUSTRIES/MANUFACTURING:**
      
      **Si service web/développement:**
      - "Site vitrine professionnel avec: présentation complète produits/services avec fiches techniques, catalogue téléchargeable, formulaire de devis professionnel, zone d'intervention claire (si services), section actualités/projets, présentation équipements/capacités, intégration vidéos/tours virtuels, blog industriel, SEO technique pour '[ville] [service industriel]', version multilingue si export, zone clients fournisseurs si nécessaire"
      
      **Si service marketing digital:**
      - "Stratégie B2B industrielle: LinkedIn Ads ciblés décideurs, content marketing technique (blancs livres, études de cas), référencement pour recherches professionnelles, email marketing B2B sectoriel, présence salons/professionnels en ligne, génération de leads qualifiés B2B, stratégie de pensée leadership industrielle"
      
      🛍️ **E-COMMERCE/BOUTIQUES EN LIGNE:**
      
      **Si service web/développement:**
      - "Boutique e-commerce complète avec: catalogue produits avec filtres avancés, système de paiement sécurisé multi-moyens, gestion stocks en temps réel, intégration transporteurs, suivi commandes client, système d'avis produits, recommandations produits (upsell/cross-sell), blog mode/conseils, SEO e-commerce pour produits + marques, optimisation conversion (A/B testing), version mobile parfaite, système de fidélité/codes promo"
      
      **Si service marketing digital:**
      - "Stratégie e-commerce: Google Shopping Ads, Facebook/Instagram Shopping, campagnes retargeting, email marketing transactionnel + marketing, influenceurs mode/lifestyle, SEO produits, Google Ads saisonniers, stratégie contenu Instagram/Pinterest, partenariats avec marques complémentaires"
      
      🎨 **ARTISANS/MÉTIERS (plombiers, électriciens, maçons, menuisiers, etc.):**
      
      **Si service web/développement:**
      - "Site web artisan professionnel avec: galerie photos avant/après réalisations, présentation services avec prix indicatifs, formulaire de devis rapide et simple, zone d'intervention claire sur carte, intégration appels d'urgence, système de rendez-vous en ligne, avis clients intégrés, blog conseils/astuces, SEO local pour '[ville] [métier] urgence', optimisation mobile (chercheurs sur mobile)"
      
      **Si service marketing digital:**
      - "Stratégie digitale artisan: Google Ads '[métier] [ville] urgence', optimisation Google My Business (photos, horaires, avis), Facebook local avec réalisations, partenariats avec artisans complémentaires, système collecte avis clients, email marketing maintenance/prévention, campagnes saisonnières (chauffage, climatisation, etc.)"
      
      💼 **CABINETS MÉDICAUX/SANTÉ:**
      
      **Si service web/développement:**
      - "Site web médical professionnel avec: prise de rendez-vous en ligne, présentation équipe médicale, spécialités/services, blog santé/conseils, formulaire contact, intégration Google My Business, respect RGPD et confidentialité, version multilingue si nécessaire, section urgences, horaires et disponibilités"
      
      **Si service marketing digital:**
      - "Stratégie digitale santé: référencement local, gestion avis Google, campagnes Google Ads locaux, emailing patients (rappel RDV, prévention), contenu éducatif santé, partenariats autres professionnels santé, respect réglementation publicité médicale"
      
      ⚡ **POUR TOUT AUTRE TYPE D'ENTREPRISE:**
      - Analyse intelligemment le secteur, la taille, et les besoins spécifiques
      - Adapte les fonctionnalités web/marketing à leur contexte unique
      - Identifie les opportunités digitales spécifiques à leur industrie
   
   b) MENTIONNE des bénéfices CONCRETS, MESURABLES et TECHNIQUES adaptés aux services web/digitaux:
      
      **Pour services web/développement (bénéfices techniques et business):**
      
      📈 **Visibilité et Trafic:**
      - "Site optimisé qui apparaît en première page Google pour '[votre métier] [ville]' et génère 20-50 leads qualifiés/mois"
      - "Amélioration du trafic organique de 200-400% en 6 mois grâce au SEO local"
      - "Site mobile-first qui capture 60-70% du trafic mobile (vs 30% actuellement)"
      - "Temps de chargement <2 secondes = réduction du taux de rebond de 40-60%"
      
      💰 **Conversions et Revenus:**
      - "Site responsive optimisé qui convertit 25-35% de vos visiteurs en contacts/devis"
      - "E-commerce qui génère 5'000-15'000€ de ventes en ligne/mois (selon secteur)"
      - "Formulaire de devis optimisé qui génère 2-3x plus de demandes qu'actuellement"
      - "Système de réservation en ligne qui augmente les réservations de 30-50%"
      
      🎯 **Fonctionnalités et UX:**
      - "Chat en ligne qui convertit 15-25% des visiteurs en leads qualifiés"
      - "Blog SEO qui génère 500-2000 visiteurs/mois organiques supplémentaires"
      - "Intégration Google Maps qui augmente les appels locaux de 40-60%"
      - "Système d'avis clients intégré qui améliore la confiance et les conversions"
      
      🏆 **Crédibilité et Image:**
      - "Site moderne qui reflète votre expertise et augmente la confiance de 50-70%"
      - "Design professionnel qui différencie de la concurrence et attire clients premium"
      - "Site HTTPS sécurisé qui rassure les clients et améliore le référencement"
      
      **Pour services marketing digital/communication (ROI et métriques):**
      
      📊 **Visibilité et Notoriété:**
      - "Stratégie digitale complète qui augmente votre visibilité de 300-500% en 3-6 mois"
      - "Optimisation Google My Business qui génère 30-80 appels/demandes/mois"
      - "Stratégie SEO qui positionne votre site sur 50-100+ mots-clés locaux"
      - "Collecte d'avis clients qui améliore votre note Google de 4.2 à 4.7-4.9 étoiles"
      
      💵 **Leads et Ventes:**
      - "Campagnes Google Ads avec ROI 3:1 à 5:1 (3-5€ de CA pour 1€ investi)"
      - "Campagnes Facebook/Instagram qui génèrent 100-300 leads qualifiés/mois"
      - "Email marketing qui génère 10-20% de revenus récurrents supplémentaires"
      - "Stratégie de retargeting qui convertit 10-20% des visiteurs en clients"
      
      👥 **Engagement et Communauté:**
      - "Gestion réseaux sociaux qui attire 500-2000 nouveaux abonnés/mois"
      - "Stratégie Instagram/Facebook qui génère 50-150 interactions/jour"
      - "Content marketing qui positionne comme expert et génère leads organiques"
      - "Community management qui améliore l'engagement de 200-400%"
      
      📱 **Réseaux Sociaux Spécifiques:**
      - "Stratégie LinkedIn qui génère 20-50 contacts B2B qualifiés/mois (pour services pro)"
      - "Campagnes Instagram Shopping qui génèrent 200-500€ ventes/mois (e-commerce)"
      - "Stratégie TikTok/Reels qui augmente la notoriété jeune génération"
      
      🎯 **Métriques Avancées:**
      - "Taux de conversion optimisé de 2% à 5-8% (multiplication par 2.5-4x)"
      - "Coût par lead réduit de 30-50% grâce à l'optimisation continue"
      - "Lifetime value client augmentée de 20-40% via stratégie de fidélisation"
      - "Taux de rebond réduit de 40-60% grâce à l'optimisation UX"
      
      ⚡ **Métriques spécifiques par secteur:**
      - Restaurants: "Réservations en ligne qui génèrent 30-50 réservations/semaine supplémentaires"
      - E-commerce: "Google Shopping Ads qui génèrent 2-5% du CA mensuel"
      - Services locaux: "Appels générés via Google Ads qui représentent 40-60% des nouveaux clients"
      - B2B: "LinkedIn Ads qui génèrent 10-30 rendez-vous qualifiés/mois"
      
      - Sois ULTRA-SPÉCIFIQUE, avec des CHIFFRES RÉALISTES adaptés au secteur et à la taille d'entreprise
      - Mentionne des MÉTRIQUES TECHNIQUES (temps chargement, SEO, taux conversion, ROI)
      - Adapte les chiffres selon si c'est une PME locale, entreprise moyenne, ou grande entreprise
   
   c) UTILISE un langage adapté:
      - Professionnel pour cabinets/services B2B
      - Accessible pour commerces locaux
      - Technique si notre service est technique
      - Business si notre service est business
   
   d) INNOVE: Trouve un angle unique pour chaque entreprise
   
   e) Format: 4-5 phrases, détaillé, unique, adapté à notre service ET leur contexte

RÈGLES CRITIQUES:
- ✅ ADAPTE toujours à NOTRE service spécifique "{service_propose}"
- ✅ Reste dans NOTRE secteur "{secteur_entreprise}" mais explique l'applicabilité
- ✅ Chaque proposition doit être UNIQUE (jamais du texte copié-collé)
- ✅ Sois CRÉATIF mais FACTUEL (pas de promesses non fondées)
- ✅ Mentionne des bénéfices CONCRETS et MESURABLES quand possible

Réponds UNIQUEMENT avec un JSON valide (sans markdown, sans code block):
{{
    "raison_choix": "Pourquoi cette entreprise a besoin de notre service spécifique (3-4 phrases, factuel)",
    "proposition_service": "Comment notre service s'applique à leur contexte (4-5 phrases, concret et mesurable)"
}}
"""
            
            # Créer le client OpenAI sans proxies
            client = openai.OpenAI(
                api_key=self.api_key,
                # S'assurer qu'aucun proxy n'est utilisé
                http_client=None
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en prospection B2B ultra-créatif. Tu génères TOUJOURS des propositions UNIQUES et DIFFÉRENTES pour chaque entreprise. JAMAIS de texte identique ou similaire. Chaque entreprise mérite une proposition personnalisée adaptée à son type exact et ses besoins spécifiques. Sois créatif et inventif. Tu génères toujours des réponses au format JSON valide."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,  # Température plus élevée pour plus de créativité et d'unicité
                max_tokens=700    # Plus de tokens pour des propositions détaillées et uniques
            )
            
            content = response.choices[0].message.content.strip()
            
            # Nettoyer le contenu si il contient des markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            logger.info(f"Analyse de pertinence générée pour {nom_entreprise}")
            return {
                "raison_choix": result.get("raison_choix", "PME locale qui pourrait bénéficier de nos services"),
                "proposition_service": result.get("proposition_service", f"Amélioration de leur présence digitale avec {service_propose}")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON dans analyse: {e}")
            return {
                "raison_choix": f"PME locale qui pourrait bénéficier de {service_propose}",
                "proposition_service": f"Amélioration de leur présence digitale avec {service_propose}"
            }
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de pertinence pour {nom_entreprise}: {e}")
            return {
                "raison_choix": f"PME locale qui pourrait bénéficier de {service_propose}",
                "proposition_service": f"Amélioration de leur présence digitale avec {service_propose}"
            }
