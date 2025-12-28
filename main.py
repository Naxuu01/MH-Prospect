"""
Agent de prospection B2B autonome.
Traite une entreprise toutes les 15 secondes.
"""
import os
import time
import logging
import yaml
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from queue import Queue

from database import ProspectDatabase
from serper_client import SerperClient
from hunter_client import HunterClient
from openai_client import OpenAIClient
from apollo_client import ApolloClient
from google_maps_client import GoogleMapsClient
from zerobounce_client import ZeroBounceClient
from scoring import ProspectScoring
from tech_detector import TechnologyDetector

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()


class AgentProspection:
    """Agent de prospection B2B autonome."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialise l'agent de prospection.
        
        Args:
            config_path: Chemin vers le fichier de configuration
        """
        # Charger la configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Initialiser les clients API
        serper_key = os.getenv("SERPER_API_KEY")
        hunter_key = os.getenv("HUNTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        apollo_key = os.getenv("APOLLO_API_KEY")
        google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
        zerobounce_key = os.getenv("ZEROBOUNCE_API_KEY")
        
        if not all([serper_key, hunter_key, openai_key]):
            raise ValueError("Les clés API SERPER, HUNTER et OPENAI doivent être définies dans le fichier .env")
        
        self.serper = SerperClient(serper_key)
        self.hunter = HunterClient(hunter_key)
        self.openai_client = OpenAIClient(openai_key)
        
        # APIs optionnelles mais recommandées
        if apollo_key:
            self.apollo = ApolloClient(apollo_key)
            logger.info("✅ Apollo.io activé")
        else:
            self.apollo = None
            logger.warning("⚠️  Apollo.io non configuré (recommandé pour meilleurs résultats)")
        
        if google_maps_key:
            self.google_maps = GoogleMapsClient(google_maps_key)
            logger.info("✅ Google Maps activé")
        else:
            self.google_maps = None
            logger.info("ℹ️  Google Maps non configuré (optionnel)")
        
        if zerobounce_key:
            self.zerobounce = ZeroBounceClient(zerobounce_key)
            # Vérifier les crédits disponibles
            credits = self.zerobounce.obtenir_credits()
            # Conversion sécurisée en entier (double sécurité)
            try:
                credits = int(credits) if credits else 0
            except (ValueError, TypeError):
                credits = 0
            if credits > 0:
                logger.info(f"✅ ZeroBounce activé ({credits} crédits restants)")
            else:
                logger.warning("⚠️  ZeroBounce activé mais aucun crédit disponible")
        else:
            self.zerobounce = None
            logger.info("ℹ️  ZeroBounce non configuré (optionnel pour vérification emails)")
        
        # Initialiser la base de données
        self.db = ProspectDatabase()
        
        # File d'attente pour les prospects
        self.file_attente = Queue()
        
        # Configuration
        self.intervalle_traitement = 2  # 2 secondes entre chaque traitement
        self.secteur_entreprise = self.config.get("secteur_entreprise", "Marketing Digital")
        self.service_propose = self.config.get("service_propose", "services digitaux")
        self.ville = self.config.get("ville", "Genève")
        self.pays = self.config.get("pays", "Suisse")
        self.message_base = self.config.get("message_base", "")
        # Templates multiples
        self.message_commerce = self.config.get("message_commerce", self.message_base)
        self.message_b2b = self.config.get("message_b2b", self.message_base)
        self.message_artisan = self.config.get("message_artisan", self.message_base)
        self.proposition_valeur = self.config.get("proposition_valeur", "")
        self.nombre_resultats = self.config.get("nombre_resultats_serper", 10)
        
        # Initialiser le scoring et la détection de technologies
        self.scoring = ProspectScoring(service_propose=self.service_propose)
        self.tech_detector = TechnologyDetector()
        
        # Charger les cibles depuis la config (types d'entreprises à cibler)
        self.cibles = self.config.get("cibles", [
            "PME", "commerce", "artisan", "cabinet", "restaurant", "hôtel"
        ])
        if not isinstance(self.cibles, list):
            self.cibles = [self.cibles]
    
    def charger_prospects_initiaux(self):
        """Charge une liste initiale de prospects qualifiés (PME privées locales)."""
        from display_utils import print_section, print_info, Colors
        print_section("Recherche de prospects", width=100, icon="🔍", color=Colors.CYAN)
        logger.info(f"🎯 Recherche de prospects qualifiés (PME privées locales)")
        logger.info(f"   Service proposé: {self.service_propose}")
        logger.info(f"   Secteur: {self.secteur_entreprise}")
        logger.info(f"   Zone: {self.ville}, {self.pays}")
        
        entreprises = []
        
        # Méthode 1: Google Maps Places (prioritaire - trouve de vrais commerces locaux)
        if self.google_maps:
            from display_utils import print_info, Colors
            print_info("📍 Source", "Google Maps Places (commerces locaux)", width=100, value_color=Colors.GREEN)
            logger.info("📍 Recherche via Google Maps Places (commerces locaux)...")
            try:
                commerces_gmaps = self.google_maps.rechercher_commerces_locaux(
                    ville=self.ville,
                    pays=self.pays,
                    nombre_resultats=min(self.nombre_resultats, 10),  # Limiter à 10 pour éviter trop de requêtes
                    cibles=self.cibles,  # Passer les cibles depuis la config
                    service_propose=self.service_propose,  # Passer le service pour qualifier
                    proposition_valeur=self.proposition_valeur  # Passer la proposition de valeur
                )
            except Exception as e:
                logger.warning(f"Erreur lors de la recherche Google Maps: {e}")
                commerces_gmaps = []
            
            # Convertir au format standard et filtrer
            for commerce in commerces_gmaps:
                nom = commerce.get("nom_entreprise", "")
                site_web = commerce.get("site_web", "")
                
                # Filtrer les entreprises non pertinentes
                if self._est_entreprise_non_pertinente(nom, site_web or ""):
                    logger.debug(f"Entreprise Google Maps exclue: {nom} - {site_web}")
                    continue
                
                entreprises.append({
                    "nom_entreprise": nom,
                    "site_web": site_web,
                    "telephone": commerce.get("telephone"),
                    "description": f"Commerce local - Note: {commerce.get('note', 'N/A')}",
                    "source": "google_maps_places"
                })
        
        # Méthode 2: Serper (complémentaire)
        from display_utils import print_info, Colors
        print_info("🔍 Source", "Serper.dev (recherche web complémentaire)", width=100, value_color=Colors.CYAN)
        logger.info("🔍 Recherche complémentaire via Serper...")
        try:
            entreprises_serper = self.serper.rechercher_entreprises_qualifiees(
                service_propose=self.service_propose or "",
                secteur_entreprise=self.secteur_entreprise or "",
                ville=self.ville or "",
                pays=self.pays or "",
                nombre_resultats=self.nombre_resultats,
                cibles=self.cibles,  # Passer les cibles depuis la config
                proposition_valeur=self.proposition_valeur or ""  # Passer la proposition de valeur
            )
            if entreprises_serper:
                entreprises.extend(entreprises_serper)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Serper: {e}", exc_info=True)
            # Continuer même en cas d'erreur pour ne pas bloquer le processus
        
        # Filtrer et nettoyer les résultats
        nouvelles_entreprises = []
        for entreprise in entreprises:
            site_web = entreprise.get("site_web") or ""  # S'assurer que ce n'est jamais None
            nom = entreprise.get("nom_entreprise") or ""  # S'assurer que ce n'est jamais None
            
            # Filtres stricts : exclure grandes entreprises, immobilier, gouvernemental
            if self._est_entreprise_non_pertinente(nom, site_web):
                logger.debug(f"Entreprise exclue: {nom} - {site_web}")
                continue
            
            if not self.db.prospect_existe(nom, site_web):
                nouvelles_entreprises.append(entreprise)
                self.file_attente.put(entreprise)
        
        logger.info(f"✅ {len(nouvelles_entreprises)} nouvelles PME privées ajoutées à la file d'attente")
        
        # Ne pas afficher de message si aucun nouveau prospect (pour éviter le spam)
        if len(nouvelles_entreprises) > 0:
            from display_utils import print_success
            print_success(f"{len(nouvelles_entreprises)} nouveaux prospects trouvés et ajoutés à la file d'attente !")
        
        return len(nouvelles_entreprises)
    
    def _est_entreprise_non_pertinente(self, nom: str, site_web: str) -> bool:
        """Vérifie si une entreprise doit être exclue (grande entreprise, immobilier, sites génériques, etc.)."""
        nom_lower = (nom or "").lower()
        site_lower = (site_web or "").lower()
        texte_complet = f"{nom_lower} {site_lower}"
        
        # FILTRE GÉOGRAPHIQUE DYNAMIQUE : Exclure seulement si le pays ne correspond pas
        if self.pays:
            pays_resultat = self._detecter_pays_entreprise(nom, site_web)
            if pays_resultat and not self._pays_correspond(self.pays, pays_resultat):
                logger.debug(f"❌ Entreprise exclue (pays={pays_resultat} au lieu de {self.pays}): {nom} - {site_web}")
                return True
        
        # Exclure les sites de grandes chaînes/groupes (accor, booking, etc.)
        domaines_exclus = [
            "accor.com", "booking.com", "expedia.com", "tripadvisor.com",
            "airbnb.com", "trivago.com", "agoda.com", "hotels.com",
            "groupon.com", "uber.com", "deliveroo.com", "justeat.com"
        ]
        if any(domaine in site_lower for domaine in domaines_exclus):
            return True
        
        # Exclure les URLs avec des patterns suspects (sites génériques de groupes)
        patterns_exclus = [
            "/restaurant-", "/hotel-", "/shop-", "/store-", "/location-",
            ".accor.com", ".booking.", ".expedia.", ".tripadvisor.",
            "/fr/restaurant", "/fr/hotel", "/en/restaurant", "/en/hotel"
        ]
        if any(pattern in site_lower for pattern in patterns_exclus):
            return True
        
        # Exclure l'immobilier
        if any(mot in texte_complet for mot in ["immobilier", "real estate", "agence immobilière", 
                                                  "homegate", "immoscout", "immoweb"]):
            return True
        
        # Exclure les grandes chaînes/plateformes et leurs filiales (mais permettre les PME indépendantes)
        grandes_entreprises = [
            # Grandes surfaces suisses
            "coop", "migros", "denner", "aldi", "lidl", "manor", "globus",
            # E-commerce/Marketplaces
            "galaxus", "digitec", "amazon", "booking", "trivago", "expedia",
            "comparis", "ricardo", "anibis", "homegate", "immoscout", "immoweb",
            # Grandes chaînes hôtels/restaurants/groups (mais permettre les petits hôtels/restaurants indépendants)
            "accor", "expedia", "tripadvisor", "airbnb", "trivago", "hotels.com",
            "marriott", "hilton", "hyatt", "novotel", "ibis", "mercure", "sofitel",
            # Restauration rapide/Franchises
            "mcdonald", "burger king", "kfc", "subway", "pizza hut", "domino",
            "starbucks", "nespresso", "pret a manger",
            # Mode/Grandes chaînes
            "zara", "h&m", "mango", "bershka", "pull & bear", "stradivarius",
            "c&a", "primark", "new look", "river island",
            # Décoration/Meubles
            "ikea", "conforama", "pfister", "micasa", "möbel pfister",
            # Électronique
            "media markt", "fnac", "saturn", "boulanger", "darty",
            # Services bancaires/Télécom
            "ubs", "credit suisse", "raiffeisen", "postfinance", "swisscom",
            "sunrise", "orange", "salt", "telecom",
            # Autres grandes marques
            "nike", "adidas", "puma", "decathlon", "interdiscount", "interio",
            # Médias (sites de presse)
            "rts", "24heures", "lematin", "20min", "letemps", "tdg", "blick", "srf", "nzz",
            # Indicateurs de filiales
            "filiale", "succursale", "branch", "subsidiary"
        ]
        if any(chain in texte_complet for chain in grandes_entreprises):
            return True
        
        # Exclure gouvernemental/public
        if any(mot in texte_complet for mot in ["ville-", "commune-", "administration", 
                                                  "canton", "ge.ch", "admin.ch", ".gov"]):
            return True
        
        # Exclure les sites médias (presse)
        if any(mot in texte_complet for mot in ["rts.ch", "24heures.ch", "lematin.ch", "20min.ch", 
                                                  "letemps.ch", "tdg.ch", "blick.ch", "srf.ch", "nzz.ch",
                                                  "rts", "24heures", "20 minutes"]):
            return True
        
        return False
    
    def _detecter_pays_entreprise(self, nom: str, site_web: str) -> Optional[str]:
        """
        Détecte le pays/région d'une entreprise à partir de son nom et site web.
        
        Args:
            nom: Nom de l'entreprise
            site_web: Site web de l'entreprise
        
        Returns:
            Code pays normalisé (ex: "ch", "fr", "ca", "qc") ou None
        """
        nom_safe = nom or ""
        site_web_safe = site_web or ""
        texte_complet = f"{nom_safe} {site_web_safe}".lower()
        
        # Vérifier le domaine du site web (le plus fiable)
        if ".qc.ca" in site_web_safe.lower() or ".quebec" in site_web_safe.lower():
            return "qc"
        if ".ch" in site_web_safe.lower():
            return "ch"
        if ".fr" in site_web_safe.lower() and ".qc.ca" not in site_web_safe.lower():
            return "fr"
        if ".ca" in site_web_safe.lower() and ".qc.ca" not in site_web_safe.lower():
            return "ca"
        if ".be" in site_web_safe.lower():
            return "be"
        if ".lu" in site_web_safe.lower():
            return "lu"
        
        # Vérifier les mots-clés géographiques
        if "québec" in texte_complet or "quebec" in texte_complet:
            if "montréal" in texte_complet or "montreal" in texte_complet:
                return "qc"
            if "canada" in texte_complet:
                return "qc"
        if ("montréal" in texte_complet or "montreal" in texte_complet) and "canada" in texte_complet:
            return "qc"
        if "suisse" in texte_complet or "switzerland" in texte_complet:
            return "ch"
        if "france" in texte_complet and "quebec" not in texte_complet:
            return "fr"
        if "canada" in texte_complet and "québec" not in texte_complet and "quebec" not in texte_complet:
            return "ca"
        
        return None
    
    def _normaliser_pays_cible(self, pays: str) -> str:
        """
        Normalise le nom du pays ciblé pour comparaison.
        
        Args:
            pays: Nom du pays/région ciblé
        
        Returns:
            Code pays normalisé
        """
        pays_lower = (pays or "").lower().strip()
        
        if pays_lower in ["suisse", "switzerland", "schweiz", "ch"]:
            return "ch"
        if pays_lower in ["france", "fr"]:
            return "fr"
        if pays_lower in ["québec", "quebec", "qc", "montréal", "montreal"]:
            return "qc"
        if pays_lower in ["canada", "ca"]:
            return "ca"
        if pays_lower in ["belgium", "belgique", "belgie", "be"]:
            return "be"
        if pays_lower in ["luxembourg", "lu"]:
            return "lu"
        
        return pays_lower
    
    def _pays_correspond(self, pays_cible: str, pays_resultat: str) -> bool:
        """
        Vérifie si le pays résultat correspond au pays ciblé.
        
        Args:
            pays_cible: Pays/région ciblé
            pays_resultat: Pays/région détecté dans le résultat
        
        Returns:
            True si le pays correspond, False sinon
        """
        cible_normalise = self._normaliser_pays_cible(pays_cible)
        
        # Comparaisons intelligentes
        if cible_normalise == "qc":
            # Si on cherche Québec, accepter seulement Québec
            return pays_resultat == "qc"
        elif cible_normalise == "ca":
            # Si on cherche Canada, accepter Canada et Québec
            return pays_resultat in ["ca", "qc"]
        elif cible_normalise == "ch":
            # Si on cherche Suisse, accepter seulement Suisse
            return pays_resultat == "ch"
        elif cible_normalise == "fr":
            # Si on cherche France, accepter seulement France
            return pays_resultat == "fr"
        else:
            # Comparaison stricte pour les autres pays
            return pays_resultat == cible_normalise
    
    def traiter_prospect(self, entreprise: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Traite un prospect complet: enrichissement + analyse IA + sauvegarde.
        
        Args:
            entreprise: Dictionnaire contenant les données de base de l'entreprise
        
        Returns:
            Dictionnaire complet du prospect traité
        """
        logger.info(f"Traitement de: {entreprise['nom_entreprise']}")
        
        prospect_complet = {
            "nom_entreprise": entreprise["nom_entreprise"],
            "site_web": entreprise.get("site_web", ""),
            "telephone": entreprise.get("telephone"),
            "description": entreprise.get("description", "")
        }
        
        # 1. Recherche d'email, téléphone et données entreprise
        # Ordre de priorité: Apollo.io > Hunter.io > Google Maps
        
        email_trouve = None
        telephone_trouve = None
        donnees_entreprise = None
        
        # 1.1. Apollo.io (priorité - meilleur taux de succès)
        if self.apollo and (prospect_complet.get("site_web") or prospect_complet["nom_entreprise"]):
            logger.info(f"Recherche Apollo.io pour {prospect_complet['nom_entreprise']}")
            entreprise_apollo, _ = self.apollo.rechercher_entreprise_et_dirigeant(
                prospect_complet["nom_entreprise"],
                prospect_complet.get("site_web", ""),
                self.ville
            )
            
            if entreprise_apollo:
                donnees_entreprise = entreprise_apollo
                # Utiliser le téléphone d'Apollo si disponible
                if entreprise_apollo.get("telephone"):
                    telephone_trouve = entreprise_apollo["telephone"]
                # Utiliser le LinkedIn d'Apollo si disponible
                if entreprise_apollo.get("linkedin_entreprise"):
                    prospect_complet["linkedin_entreprise"] = entreprise_apollo["linkedin_entreprise"]
                # Mettre à jour le site web si plus précis
                if entreprise_apollo.get("site_web") and not prospect_complet.get("site_web"):
                    prospect_complet["site_web"] = entreprise_apollo["site_web"]
        
        # 1.2. Hunter.io (fallback si Apollo n'a pas trouvé)
        if not email_trouve and prospect_complet.get("site_web"):
            logger.info(f"Recherche Hunter.io pour {prospect_complet['nom_entreprise']}")
            email_hunter, _ = self.hunter.trouver_email_dirigeant(
                prospect_complet["site_web"],
                prospect_complet["nom_entreprise"]
            )
            
            if email_hunter:
                email_trouve = email_hunter
        
        # 1.3. Google Maps (pour téléphone vérifié si manquant)
        if self.google_maps and not telephone_trouve:
            logger.info(f"Recherche Google Maps pour {prospect_complet['nom_entreprise']}")
            entreprise_gmaps = self.google_maps.rechercher_entreprise_locale(
                prospect_complet["nom_entreprise"],
                self.ville,
                self.pays
            )
            
            if entreprise_gmaps:
                if entreprise_gmaps.get("telephone") and not telephone_trouve:
                    telephone_trouve = entreprise_gmaps["telephone"]
                if entreprise_gmaps.get("site_web") and not prospect_complet.get("site_web"):
                    prospect_complet["site_web"] = entreprise_gmaps["site_web"]
                # Enrichir avec les données Google Maps
                if entreprise_gmaps.get("adresse"):
                    prospect_complet["adresse_complete"] = entreprise_gmaps["adresse"]
                if entreprise_gmaps.get("note"):
                    prospect_complet["note_google"] = entreprise_gmaps["note"]
                if entreprise_gmaps.get("nb_avis"):
                    prospect_complet["nb_avis_google"] = entreprise_gmaps["nb_avis"]
        
        # Assigner les résultats
        prospect_complet["email"] = email_trouve
        prospect_complet["telephone"] = telephone_trouve or prospect_complet.get("telephone")
        
        # 1.5. Vérification de l'email avec ZeroBounce (si email trouvé)
        if email_trouve and self.zerobounce:
            try:
                logger.info(f"Vérification ZeroBounce pour {email_trouve}")
                verification = self.zerobounce.verifier_email(email_trouve)
                
                # S'assurer que le statut n'est jamais None
                status = verification.get("status") or "unknown"
                prospect_complet["email_status"] = status
                prospect_complet["email_sub_status"] = verification.get("sub_status") or ""
                prospect_complet["email_did_you_mean"] = verification.get("did_you_mean")
                
                credits_remaining = verification.get("credits_remaining", 0)
                # Convertir en entier si c'est une chaîne
                try:
                    credits_remaining = int(credits_remaining) if credits_remaining else 0
                except (ValueError, TypeError):
                    credits_remaining = 0
                
                if status == "valid":
                    logger.info(f"✅ Email valide: {email_trouve} ({credits_remaining} crédits restants)")
                elif status == "invalid":
                    logger.warning(f"❌ Email invalide: {email_trouve}")
                    if verification.get("did_you_mean"):
                        logger.info(f"💡 Suggestion: {verification['did_you_mean']}")
                elif status == "catch-all":
                    logger.info(f"⚠️ Email catch-all (valide mais moins fiable): {email_trouve}")
                elif status != "unknown":
                    logger.warning(f"⚠️ Statut email: {status} pour {email_trouve}")
                else:
                    logger.debug(f"Statut email inconnu pour {email_trouve}")
                    
            except Exception as e:
                logger.warning(f"Erreur lors de la vérification ZeroBounce: {e}")
                prospect_complet["email_status"] = "unknown"
        elif email_trouve:
            # Email trouvé mais ZeroBounce non configuré
            prospect_complet["email_status"] = None  # Sera affiché comme "Non vérifié"
        
        # Plus de recherche de dirigeant - supprimé
        
        # Enrichir avec les données entreprise (Apollo)
        if donnees_entreprise:
            if donnees_entreprise.get("taille"):
                prospect_complet["taille_entreprise"] = donnees_entreprise["taille"]
            if donnees_entreprise.get("industrie"):
                prospect_complet["industrie"] = donnees_entreprise["industrie"]
            if donnees_entreprise.get("revenue"):
                prospect_complet["revenue_estime"] = donnees_entreprise["revenue"]
        
        # 2. Détection des technologies web utilisées
        site_web = prospect_complet.get("site_web", "")
        if site_web:
            try:
                logger.info(f"Détection des technologies pour {site_web}")
                technologies = self.tech_detector.detecter(site_web)
                prospect_complet["technologies"] = ",".join(technologies) if technologies else ""
                if technologies:
                    logger.info(f"✅ Technologies détectées: {', '.join(technologies)}")
            except Exception as e:
                logger.debug(f"Erreur lors de la détection de technologies: {e}")
                prospect_complet["technologies"] = ""
        
        # 3. Recherche LinkedIn via Serper (seulement si pas déjà trouvé par Apollo)
        if not prospect_complet.get("linkedin_entreprise") and prospect_complet["nom_entreprise"]:
            linkedin_entreprise = self.serper.rechercher_linkedin(
                prospect_complet["nom_entreprise"],
                prospect_complet.get("site_web", ""),
                self.ville
            )
            if linkedin_entreprise:
                prospect_complet["linkedin_entreprise"] = linkedin_entreprise
        
        # 4. Calcul du score du prospect
        try:
            score = self.scoring.calculer_score(prospect_complet)
            prospect_complet["score"] = score
            categorie = self.scoring.obtenir_categorie_score(score)
            logger.info(f"📊 Score prospect: {score}/100 ({categorie})")
        except Exception as e:
            logger.warning(f"Erreur lors du calcul du score: {e}")
            prospect_complet["score"] = 0
        
        # 5. Analyse de pertinence avec OpenAI (pourquoi cette entreprise et ce qu'on peut leur proposer)
        try:
            analyse_pertinence = self.openai_client.analyser_entreprise_pertinence(
                prospect_complet,
                self.service_propose,
                self.secteur_entreprise
            )
            prospect_complet["raison_choix"] = analyse_pertinence.get("raison_choix", "")
            prospect_complet["proposition_service"] = analyse_pertinence.get("proposition_service", "")
            logger.info(f"✅ Analyse de pertinence générée pour {prospect_complet['nom_entreprise']}")
        except Exception as e:
            logger.warning(f"Erreur lors de l'analyse de pertinence pour {prospect_complet['nom_entreprise']}: {e}")
            prospect_complet["raison_choix"] = f"PME locale qui pourrait bénéficier de {self.service_propose}"
            prospect_complet["proposition_service"] = f"Amélioration de leur présence digitale avec {self.service_propose}"
        
        # 6. Sélection du template de message selon le type d'entreprise
        template_a_utiliser = self._selectionner_template_message(prospect_complet)
        prospect_complet["template_utilise"] = template_a_utiliser
        
        # 7. Génération du message personnalisé avec OpenAI
        # On génère toujours un message, même sans dirigeant (utilise "Monsieur/Madame" par défaut)
        try:
            resultat_ia = self.openai_client.generer_message_personnalise(
                prospect_complet,
                template_a_utiliser,
                self.proposition_valeur,
                service_propose=self.service_propose,
                secteur_entreprise=self.secteur_entreprise
            )
            prospect_complet["message_personnalise"] = resultat_ia.get("message_personnalise", "")
            prospect_complet["point_specifique"] = resultat_ia.get("point_specifique", "")
        except Exception as e:
            logger.warning(f"Erreur lors de la génération du message pour {prospect_complet['nom_entreprise']}: {e}")
            # Message par défaut sans IA
            prospect_complet["message_personnalise"] = template_a_utiliser.replace(
                "{nom_dirigeant}", "Monsieur/Madame"
            ).replace(
                "{nom_entreprise}", prospect_complet["nom_entreprise"]
            ).replace(
                "{point_specifique}", "votre expertise"
            ).replace(
                "{proposition_valeur}", self.proposition_valeur
            )
            prospect_complet["point_specifique"] = "expertise dans votre domaine"
        
        # 5. Validation : s'assurer qu'il y a au moins email OU téléphone
        email = prospect_complet.get("email")
        telephone = prospect_complet.get("telephone")
        
        if not email and not telephone:
            logger.warning(f"❌ Prospect {prospect_complet['nom_entreprise']} ignoré : aucun email ni téléphone trouvé")
            return None
        
        # 6. Sauvegarde en base de données
        prospect_id = self.db.ajouter_prospect(prospect_complet)
        
        if prospect_id:
            logger.info(f"✅ Prospect sauvegardé avec l'ID: {prospect_id}")
        else:
            logger.warning(f"⚠️ Le prospect {prospect_complet['nom_entreprise']} n'a pas pu être sauvegardé")
        
        return prospect_complet
    
    def _selectionner_template_message(self, prospect: Dict[str, Any]) -> str:
        """
        Sélectionne le template de message approprié selon le type d'entreprise.
        
        Args:
            prospect: Dictionnaire contenant les données du prospect
        
        Returns:
            Template de message à utiliser
        """
        nom = (prospect.get("nom_entreprise") or "").lower()
        industrie = (prospect.get("industrie") or "").lower()
        description = (prospect.get("description") or "").lower()
        technologies = (prospect.get("technologies") or "").lower()
        
        # Détecter le type d'entreprise
        commerce_keywords = ["restaurant", "boutique", "commerce", "retail", "magasin", "épicerie", "boulangerie", "coiffeur", "salon"]
        artisan_keywords = ["plombier", "électricien", "maçon", "menuisier", "charpentier", "peintre", "chauffagiste", "artisan"]
        b2b_keywords = ["cabinet", "fiduciaire", "consultant", "conseil", "avocat", "comptable", "agence", "bureau", "société"]
        
        # Vérifier dans différents champs
        texte_complet = f"{nom} {industrie} {description}".lower()
        
        if any(mot in texte_complet for mot in artisan_keywords):
            logger.debug(f"Template artisan sélectionné pour {prospect.get('nom_entreprise')}")
            return self.message_artisan
        elif any(mot in texte_complet for mot in commerce_keywords):
            logger.debug(f"Template commerce sélectionné pour {prospect.get('nom_entreprise')}")
            return self.message_commerce
        elif any(mot in texte_complet for mot in b2b_keywords):
            logger.debug(f"Template B2B sélectionné pour {prospect.get('nom_entreprise')}")
            return self.message_b2b
        else:
            # Template par défaut
            logger.debug(f"Template base sélectionné pour {prospect.get('nom_entreprise')}")
            return self.message_base
    
    def afficher_resume(self, prospect: Dict[str, Any]):
        """
        Affiche un résumé complet du prospect traité dans la console avec un rendu visuel amélioré.
        
        Args:
            prospect: Dictionnaire contenant les données du prospect
        """
        from display_utils import (
            print_header, print_section, print_info, print_box, 
            print_separator, wrap_text, Colors, print_success, print_warning
        )
        
        nom_entreprise = prospect.get('nom_entreprise', 'N/A')
        score = prospect.get('score', 0)
        
        # Afficher le score dans l'en-tête
        from scoring import ProspectScoring
        scoring_temp = ProspectScoring(self.service_propose)
        categorie = scoring_temp.obtenir_categorie_score(score)
        
        # En-tête principal simplifié avec score
        print_header(f"📊 {nom_entreprise} - Score: {score}/100 ({categorie})", width=100, color=Colors.CYAN)
        
        # Section Informations de Contact
        print_section("Contact", width=100, icon="📞", color=Colors.BLUE)
        
        # Afficher le score en premier
        if score > 0:
            score_color = Colors.GREEN if score >= 60 else Colors.YELLOW if score >= 40 else Colors.RED
            print_info("⭐ Score", f"{score}/100 ({categorie.capitalize()})", width=100, value_color=score_color)
        
        # Site web
        site_web = prospect.get('site_web') or 'N/A'
        if site_web and site_web != 'N/A':
            print_info("🌐 Site web", site_web, width=100)
        else:
            print_info("🌐 Site web", "Non disponible", width=100, value_color=Colors.DIM)
        
        # Téléphone
        telephone = prospect.get('telephone') or 'N/A'
        if telephone and telephone != 'N/A':
            print_info("📞 Téléphone", telephone, width=100, value_color=Colors.GREEN)
        else:
            print_info("📞 Téléphone", "Non disponible", width=100, value_color=Colors.DIM)
        
        # Email avec statut
        email = prospect.get('email') or 'N/A'
        email_status = prospect.get('email_status')
        if email and email != 'N/A':
            # Gérer le cas où email_status est None ou vide
            if email_status == "valid":
                status_display = f"✅ Valide"
                value_color = Colors.GREEN
            elif email_status == "invalid":
                status_display = f"❌ Invalide"
                value_color = Colors.RED
            elif email_status == "catch-all":
                status_display = f"⚠️  Catch-all (moins fiable)"
                value_color = Colors.YELLOW
            elif email_status and email_status != "unknown":
                # Statut valide mais non standard
                status_display = f"⚠️  Statut: {email_status}"
                value_color = Colors.YELLOW
            else:
                # Pas de vérification effectuée ou statut inconnu
                status_display = "⏳ Non vérifié"
                value_color = Colors.DIM
            
            print_info("✉️  Email", f"{email} - {status_display}", width=100, value_color=value_color)
            
            if prospect.get('email_did_you_mean'):
                print_info("💡 Suggestion", prospect.get('email_did_you_mean'), width=100, value_color=Colors.CYAN)
        else:
            print_info("✉️  Email", "Non disponible", width=100, value_color=Colors.DIM)
        
        # LinkedIn
        linkedin = prospect.get('linkedin_entreprise') or 'N/A'
        if linkedin and linkedin != 'N/A':
            print_info("🔗 LinkedIn Entreprise", linkedin, width=100)
        else:
            print_info("🔗 LinkedIn Entreprise", "Non disponible", width=100, value_color=Colors.DIM)
        
        # Informations supplémentaires
        taille = prospect.get('taille_entreprise')
        industrie = prospect.get('industrie')
        if taille or industrie:
            print_separator(width=100)
            if taille:
                print_info("🏢 Taille", taille, width=100)
            if industrie:
                print_info("📋 Industrie", industrie, width=100)
        
        # Section Analyse simplifiée
        raison_choix = prospect.get('raison_choix', 'N/A')
        if raison_choix != 'N/A':
            print_section("Pourquoi cette entreprise", width=100, icon="🎯", color=Colors.MAGENTA)
            print_box(raison_choix, width=100, border_color=Colors.MAGENTA)
        
        # Section Proposition de Service
        proposition_service = prospect.get('proposition_service', 'N/A')
        if proposition_service != 'N/A':
            print_section("Proposition de service", width=100, icon="💡", color=Colors.YELLOW)
            print_box(proposition_service, width=100, border_color=Colors.YELLOW)
        
        # Technologies détectées
        technologies = prospect.get('technologies', '')
        if technologies:
            techs_list = technologies.split(',')
            print_info("🔧 Technologies", ', '.join(techs_list[:5]), width=100, value_color=Colors.CYAN)
        
        # Point spécifique
        point_specifique = prospect.get('point_specifique', 'N/A')
        if point_specifique != 'N/A':
            print_info("Point spécifique", point_specifique, width=100, value_color=Colors.CYAN)
        
        # Section Message Personnalisé
        print_section("Message personnalisé", width=100, icon="📝", color=Colors.GREEN)
        
        message = prospect.get('message_personnalise')
        if message:
            # Formater le message avec indentation
            lines = wrap_text(message, width=96, indent=2)
            print_box('\n'.join(lines), title="Message prêt à envoyer", width=100,
                     border_color=Colors.GREEN, title_color=Colors.GREEN + Colors.BOLD)
        else:
            print_warning("Message non généré (données insuffisantes)")
        
        # Footer simplifié
        print()
    
    def lancer(self):
        """Lance la boucle principale de l'agent."""
        from display_utils import print_header, print_info, print_separator, Colors, print_success
        
        # En-tête de démarrage visuel simplifié
        print_header("🚀 Agent de Prospection B2B", width=100, color=Colors.CYAN)
        print_info("Service", self.service_propose, width=100, value_color=Colors.GREEN)
        print_info("Zone", f"{self.ville}, {self.pays}", width=100)
        print_info("Intervalle", f"{self.intervalle_traitement}s", width=100)
        print()
        
        logger.info("🚀 Démarrage de l'agent de prospection B2B")
        logger.info(f"⏱️  Intervalle de traitement: {self.intervalle_traitement} secondes ({self.intervalle_traitement//60} minutes)")
        logger.info(f"🎯 Service proposé: {self.service_propose}")
        logger.info(f"📊 Secteur: {self.secteur_entreprise} | Zone: {self.ville}, {self.pays}")
        
        # Charger les prospects initiaux
        try:
            self.charger_prospects_initiaux()
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des prospects initiaux: {e}", exc_info=True)
            logger.warning("⚠️  Continuation avec les prospects déjà existants dans la base de données...")
        
        if self.file_attente.empty():
            logger.warning("⚠️  Aucun nouveau prospect trouvé. Relancez une recherche ou vérifiez la configuration.")
            # Ne pas arrêter complètement - continuer avec les prospects existants
            logger.info("ℹ️  L'agent continuera de fonctionner et tentera de charger de nouveaux prospects plus tard.")
            return
        
        # Afficher les statistiques initiales
        stats = self.db.obtenir_statistiques()
        from display_utils import print_success
        print_success(f"Statistiques initiales - Total: {stats['total']} prospects | Avec email: {stats['avec_email']}")
        
        # Boucle principale
        compteur = 0
        tentatives_echouees = 0
        while True:
            try:
                if self.file_attente.empty():
                    logger.debug("📭 File d'attente vide. Chargement de nouveaux prospects...")
                    nouveaux = self.charger_prospects_initiaux()
                    
                    if nouveaux == 0:
                        tentatives_echouees += 1
                        # Afficher un message seulement toutes les 5 tentatives pour éviter le spam
                        if tentatives_echouees % 5 == 1:
                            logger.debug(f"⏳ Aucun nouveau prospect trouvé (tentative {tentatives_echouees}). Recherche en cours...")
                        time.sleep(60)  # Attendre 1 minute
                        continue
                    else:
                        # Réinitialiser le compteur si on trouve des prospects
                        tentatives_echouees = 0
                
                # Récupérer le prochain prospect
                entreprise = self.file_attente.get()
                compteur += 1
                
                from display_utils import print_section, Colors
                print_section(f"Prospect #{compteur}", width=100, icon="🔄", color=Colors.BLUE)
                logger.info(f"\n🔄 Traitement du prospect #{compteur}")
                
                # Traiter le prospect
                prospect_traite = self.traiter_prospect(entreprise)
                
                # Si le prospect n'a pas pu être traité (pas d'email ni téléphone), passer au suivant
                if prospect_traite is None:
                    from display_utils import print_warning
                    print_warning(f"Prospect #{compteur} ignoré (pas de contact valide). Passage au suivant...")
                    logger.info("⏭️  Prospect ignoré (pas de contact). Passage au suivant...")
                    continue
                
                # Afficher le résumé
                self.afficher_resume(prospect_traite)
                
                # Afficher les statistiques mises à jour
                stats = self.db.obtenir_statistiques()
                from display_utils import print_success
                print_success(f"Statistiques mises à jour - Total: {stats['total']} | Avec email: {stats['avec_email']} | Traités: {stats['traites']}")
                logger.info(f"📊 Statistiques - Total: {stats['total']} | Avec email: {stats['avec_email']} | Traités: {stats['traites']}")
                
                # Attendre avant de traiter le suivant
                from display_utils import print_separator
                print_separator(width=100, style="─", color=Colors.DIM + Colors.WHITE)
                logger.info(f"⏳ Attente de {self.intervalle_traitement} secondes avant le prochain traitement...")
                time.sleep(self.intervalle_traitement)
                
            except KeyboardInterrupt:
                logger.info("\n⏹️  Arrêt demandé par l'utilisateur")
                break
            except Exception as e:
                logger.error(f"❌ Erreur lors du traitement: {e}", exc_info=True)
                logger.info(f"⏳ Attente de {self.intervalle_traitement} secondes avant nouvelle tentative...")
                time.sleep(self.intervalle_traitement)


def main():
    """Point d'entrée principal."""
    try:
        agent = AgentProspection()
        agent.lancer()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
