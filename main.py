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
        self.intervalle_traitement = 10  # 2 minutes (120 secondes)
        self.secteur_entreprise = self.config.get("secteur_entreprise", "Marketing Digital")
        self.service_propose = self.config.get("service_propose", "services digitaux")
        self.ville = self.config.get("ville", "Genève")
        self.pays = self.config.get("pays", "Suisse")
        self.message_base = self.config.get("message_base", "")
        self.proposition_valeur = self.config.get("proposition_valeur", "")
        self.nombre_resultats = self.config.get("nombre_resultats_serper", 10)
        
        # Charger les cibles depuis la config (types d'entreprises à cibler)
        self.cibles = self.config.get("cibles", [
            "PME", "commerce", "artisan", "cabinet", "restaurant", "hôtel"
        ])
        if not isinstance(self.cibles, list):
            self.cibles = [self.cibles]
    
    def charger_prospects_initiaux(self):
        """Charge une liste initiale de prospects qualifiés (PME privées locales)."""
        logger.info(f"🎯 Recherche de prospects qualifiés (PME privées locales)")
        logger.info(f"   Service proposé: {self.service_propose}")
        logger.info(f"   Secteur: {self.secteur_entreprise}")
        logger.info(f"   Zone: {self.ville}, {self.pays}")
        
        entreprises = []
        
        # Méthode 1: Google Maps Places (prioritaire - trouve de vrais commerces locaux)
        if self.google_maps:
            logger.info("📍 Recherche via Google Maps Places (commerces locaux)...")
            try:
                commerces_gmaps = self.google_maps.rechercher_commerces_locaux(
                    ville=self.ville,
                    pays=self.pays,
                    nombre_resultats=min(self.nombre_resultats, 10),  # Limiter à 10 pour éviter trop de requêtes
                    cibles=self.cibles  # Passer les cibles depuis la config
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
        logger.info("🔍 Recherche complémentaire via Serper...")
        entreprises_serper = self.serper.rechercher_entreprises_qualifiees(
            service_propose=self.service_propose,
            secteur_entreprise=self.secteur_entreprise,
            ville=self.ville,
            pays=self.pays,
            nombre_resultats=self.nombre_resultats,
            cibles=self.cibles  # Passer les cibles depuis la config
        )
        entreprises.extend(entreprises_serper)
        
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
        return len(nouvelles_entreprises)
    
    def _est_entreprise_non_pertinente(self, nom: str, site_web: str) -> bool:
        """Vérifie si une entreprise doit être exclue (grande entreprise, immobilier, sites génériques, etc.)."""
        nom_lower = (nom or "").lower()
        site_lower = (site_web or "").lower()
        texte_complet = f"{nom_lower} {site_lower}"
        
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
    
    def traiter_prospect(self, entreprise: Dict[str, Any]) -> Dict[str, Any]:
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
                
                prospect_complet["email_status"] = verification.get("status", "unknown")
                prospect_complet["email_sub_status"] = verification.get("sub_status", "")
                prospect_complet["email_did_you_mean"] = verification.get("did_you_mean")
                
                status = verification.get("status", "unknown")
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
                else:
                    logger.warning(f"⚠️ Statut email incertain ({status}): {email_trouve}")
                    
            except Exception as e:
                logger.warning(f"Erreur lors de la vérification ZeroBounce: {e}")
                prospect_complet["email_status"] = "unknown"
        
        # Plus de recherche de dirigeant - supprimé
        
        # Enrichir avec les données entreprise (Apollo)
        if donnees_entreprise:
            if donnees_entreprise.get("taille"):
                prospect_complet["taille_entreprise"] = donnees_entreprise["taille"]
            if donnees_entreprise.get("industrie"):
                prospect_complet["industrie"] = donnees_entreprise["industrie"]
            if donnees_entreprise.get("revenue"):
                prospect_complet["revenue_estime"] = donnees_entreprise["revenue"]
        
        # 2. Recherche LinkedIn via Serper (seulement si pas déjà trouvé par Apollo)
        if not prospect_complet.get("linkedin_entreprise") and prospect_complet["nom_entreprise"]:
            linkedin_entreprise = self.serper.rechercher_linkedin(
                prospect_complet["nom_entreprise"],
                prospect_complet.get("site_web", ""),
                self.ville
            )
            if linkedin_entreprise:
                prospect_complet["linkedin_entreprise"] = linkedin_entreprise
        
        # 3. Analyse de pertinence avec OpenAI (pourquoi cette entreprise et ce qu'on peut leur proposer)
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
        
        # 4. Génération du message personnalisé avec OpenAI
        # On génère toujours un message, même sans dirigeant (utilise "Monsieur/Madame" par défaut)
        try:
            resultat_ia = self.openai_client.generer_message_personnalise(
                prospect_complet,
                self.message_base,
                self.proposition_valeur
            )
            prospect_complet["message_personnalise"] = resultat_ia.get("message_personnalise", "")
            prospect_complet["point_specifique"] = resultat_ia.get("point_specifique", "")
        except Exception as e:
            logger.warning(f"Erreur lors de la génération du message pour {prospect_complet['nom_entreprise']}: {e}")
            # Message par défaut sans IA
            prospect_complet["message_personnalise"] = self.message_base.replace(
                "{nom_dirigeant}", "Monsieur/Madame"
            ).replace(
                "{nom_entreprise}", prospect_complet["nom_entreprise"]
            ).replace(
                "{point_specifique}", "votre expertise"
            ).replace(
                "{proposition_valeur}", self.proposition_valeur
            )
            prospect_complet["point_specifique"] = "expertise dans votre domaine"
        
        # 5. Sauvegarde en base de données
        prospect_id = self.db.ajouter_prospect(prospect_complet)
        
        if prospect_id:
            logger.info(f"✅ Prospect sauvegardé avec l'ID: {prospect_id}")
        else:
            logger.warning(f"⚠️ Le prospect {prospect_complet['nom_entreprise']} n'a pas pu être sauvegardé")
        
        return prospect_complet
    
    def afficher_resume(self, prospect: Dict[str, Any]):
        """
        Affiche un résumé complet du prospect traité dans la console.
        
        Args:
            prospect: Dictionnaire contenant les données du prospect
        """
        print("\n" + "="*80)
        print(f"📊 PROSPECT TRAITÉ - {prospect['nom_entreprise']}")
        print("="*80)
        print(f"🌐 Site web: {prospect.get('site_web', 'N/A')}")
        print(f"📞 Téléphone: {prospect.get('telephone', 'N/A')}")
        email = prospect.get('email', 'N/A')
        email_status = prospect.get('email_status')
        if email_status:
            status_icon = "✅" if email_status == "valid" else "❌" if email_status == "invalid" else "⚠️"
            print(f"✉️  Email: {email} {status_icon} ({email_status})")
            if prospect.get('email_did_you_mean'):
                print(f"   💡 Suggestion: {prospect.get('email_did_you_mean')}")
        else:
            print(f"✉️  Email: {email}")
        print(f"🔗 LinkedIn Entreprise: {prospect.get('linkedin_entreprise', 'N/A')}")
        print(f"\n🎯 POURQUOI CETTE ENTREPRISE:")
        print(f"   {prospect.get('raison_choix', 'N/A')}")
        print(f"\n💡 PROPOSITION DE SERVICE:")
        print(f"   {prospect.get('proposition_service', 'N/A')}")
        print(f"\n💡 Point spécifique identifié: {prospect.get('point_specifique', 'N/A')}")
        print(f"\n📝 Message personnalisé:\n{'-'*80}")
        if prospect.get('message_personnalise'):
            print(prospect['message_personnalise'])
        else:
            print("Message non généré (données insuffisantes)")
        print("-"*80)
        print("="*80 + "\n")
    
    def lancer(self):
        """Lance la boucle principale de l'agent."""
        logger.info("🚀 Démarrage de l'agent de prospection B2B")
        logger.info(f"⏱️  Intervalle de traitement: {self.intervalle_traitement} secondes ({self.intervalle_traitement//60} minutes)")
        logger.info(f"🎯 Service proposé: {self.service_propose}")
        logger.info(f"📊 Secteur: {self.secteur_entreprise} | Zone: {self.ville}, {self.pays}")
        
        # Charger les prospects initiaux
        self.charger_prospects_initiaux()
        
        if self.file_attente.empty():
            logger.warning("⚠️  Aucun nouveau prospect trouvé. Relancez une recherche ou vérifiez la configuration.")
            return
        
        # Afficher les statistiques initiales
        stats = self.db.obtenir_statistiques()
        logger.info(f"📈 Statistiques initiales - Total: {stats['total']} | Avec email: {stats['avec_email']}")
        
        # Boucle principale
        compteur = 0
        while True:
            try:
                if self.file_attente.empty():
                    logger.info("📭 File d'attente vide. Chargement de nouveaux prospects...")
                    nouveaux = self.charger_prospects_initiaux()
                    
                    if nouveaux == 0:
                        logger.warning("⚠️  Aucun nouveau prospect trouvé. Attente de 5 minutes avant nouvelle tentative...")
                        time.sleep(60)  # Attendre 1 minute
                        continue
                
                # Récupérer le prochain prospect
                entreprise = self.file_attente.get()
                compteur += 1
                
                logger.info(f"\n🔄 Traitement du prospect #{compteur}")
                
                # Traiter le prospect
                prospect_traite = self.traiter_prospect(entreprise)
                
                # Afficher le résumé
                self.afficher_resume(prospect_traite)
                
                # Afficher les statistiques mises à jour
                stats = self.db.obtenir_statistiques()
                logger.info(f"📊 Statistiques - Total: {stats['total']} | Avec email: {stats['avec_email']} | Traités: {stats['traites']}")
                
                # Attendre avant de traiter le suivant
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
