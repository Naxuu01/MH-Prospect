"""
Module client pour l'API Serper.dev - Recherche d'entreprises.
"""
import requests
import logging
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SerperClient:
    """Client pour interroger l'API Serper.dev."""
    
    def __init__(self, api_key: str):
        """
        Initialise le client Serper.
        
        Args:
            api_key: Clé API Serper.dev
        """
        self.api_key = api_key
        self.base_url = "https://google.serper.dev"
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
    
    def rechercher_entreprises_qualifiees(self, service_propose: str, secteur_entreprise: str, 
                                         ville: str, pays: str = "Suisse", 
                                         nombre_resultats: int = 10,
                                         cibles: List[str] = None) -> List[Dict[str, Any]]:
        """
        Recherche des entreprises qualifiées qui pourraient avoir besoin du service proposé.
        
        Args:
            service_propose: Service que vous proposez (ex: "création de sites web")
            secteur_entreprise: Secteur dans lequel vous travaillez (ex: "Marketing Digital")
            ville: Ville de recherche
            pays: Pays de recherche
            nombre_resultats: Nombre de résultats souhaités
        
        Returns:
            Liste de dictionnaires contenant les informations des entreprises
        """
        try:
            # Construire une requête intelligente pour trouver des PME privées locales
            # Exclusion explicite des grandes plateformes, sites immobiliers, sites gouvernementaux
            
            # Analyser le service proposé pour créer des requêtes ciblées
            service_lower = service_propose.lower()
            
            # Exclusions massives : grandes plateformes, immobilier, gouvernemental, grandes marques, filiales et médias
            exclusions = (
                "-site:.gov -site:.gouv -site:.ch/administration -site:.ch/ville -site:.ch/commune "
                "-site:ge.ch -site:admin.ch -site:wikipedia.org -site:facebook.com -site:linkedin.com "
                "-site:homegate.ch -site:immoscout24.ch -site:immoweb.ch -site:anibis.ch "
                "-site:comparis.ch -site:ricardo.ch -site:digitec.ch -site:galaxus.ch "
                "-site:booking.com -site:trivago.ch -site:tripadvisor.com "
                "-site:amazon.ch -site:coop.ch -site:migros.ch -site:denner.ch -site:manor.ch "
                "-site:ikea.ch -site:zara.ch -site:fnac.ch -site:media-markt.ch "
                "-site:rts.ch -site:24heures.ch -site:lematin.ch -site:20min.ch -site:letemps.ch "
                "-site:tdg.ch -site:blick.ch -site:srf.ch -site:nzz.ch "
                "-immobilier -agence immobilière -real estate -rent -achat maison -location appartement "
                "-filiale -succursale -franchise -coop -migros -manor -ikea -zara -mcdonald -starbucks"
            )
            
            # Construire la requête avec les cibles depuis la config
            if cibles and len(cibles) > 0:
                # Utiliser les cibles de la config, formatées pour la requête Google
                cibles_quoted = ' OR '.join([f'"{cible}"' for cible in cibles])
                types_pme = f'({cibles_quoted})'
            else:
                # Fallback si pas de cibles définies
                types_pme = '"PME" OR "petite entreprise" OR "commerce" OR "artisan"'
            
            if "site web" in service_lower or "website" in service_lower or "internet" in service_lower:
                # Chercher des commerces et PME locales qui pourraient avoir besoin d'un site
                query = f'{types_pme} {ville} {pays} {exclusions}'
            elif "marketing" in service_lower or "visibilité" in service_lower or "communication" in service_lower:
                # Chercher des PME et commerces locaux
                query = f'{types_pme} {ville} {pays} {exclusions}'
            elif "conseil" in service_lower or "consulting" in service_lower:
                # Chercher des cabinets et consultants
                query = f'{types_pme} {secteur_entreprise.lower()} {ville} {pays} {exclusions}'
            else:
                # Requête générique : PME et commerces locaux diversifiés
                query = f'{types_pme} {ville} {pays} {exclusions}'
            
            # Ajuster le code pays pour Google
            gl_code = "ch" if pays.lower() in ["suisse", "switzerland"] else "fr"
            hl_code = "fr" if pays.lower() in ["suisse", "france"] else "en"
            
            payload = {
                "q": query,
                "num": nombre_resultats,
                "gl": gl_code,  # Code pays Google
                "hl": hl_code   # Langue
            }
            
            response = requests.post(
                f"{self.base_url}/search",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            entreprises = []
            
            # Traiter les résultats organiques et filtrer les sites non pertinents
            if "organic" in data:
                for result in data["organic"]:
                    link = result.get("link", "")
                    
                    # Filtrer les sites gouvernementaux, publics et non pertinents
                    if self._est_site_non_pertinent(link):
                        logger.debug(f"Site exclu (gouvernemental/public): {link}")
                        continue
                    
                    titre = result.get("title", "")
                    description = result.get("snippet", "")
                    
                    # Filtrer aussi selon le titre et la description
                    if self._est_resultat_non_pertinent(titre, description):
                        logger.debug(f"Résultat exclu (non PME privée): {titre}")
                        continue
                    
                    entreprise = {
                        "nom_entreprise": self._extraire_nom_entreprise(titre),
                        "site_web": link,
                        "description": description,
                        "telephone": None,
                        "source": "serper_organic"
                    }
                    
                    # Essayer d'extraire le téléphone de la description
                    entreprise["telephone"] = self._extraire_telephone(description)
                    
                    entreprises.append(entreprise)
            
            logger.info(f"{len(entreprises)} entreprises qualifiées trouvées pour le service '{service_propose}' à {ville}")
            return entreprises
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la recherche Serper: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche: {e}")
            return []
    
    def _est_site_non_pertinent(self, url: str) -> bool:
        """
        Vérifie si un site web est non pertinent (gouvernemental, public, etc.).
        
        Args:
            url: URL du site web
        
        Returns:
            True si le site doit être exclu, False sinon
        """
        url_lower = url.lower()
        
        # Domaines à exclure : gouvernementaux, grandes plateformes, immobilier, groupes/hôtels, etc.
        domaines_exclus = [
            # Gouvernemental/Public
            ".gov", ".gouv", ".admin.ch", "ge.ch", "ville-", "commune-",
            "administration", "canton", "service-public", "public-",
            "/ville/", "/commune/", "/administration/", "portail-public",
            # Grandes plateformes/Annuaires
            "wikipedia.org", "facebook.com", "linkedin.com", "twitter.com",
            "instagram.com", "youtube.com", "google.com", "maps.google",
            "pagesjaunes", "annuaire", "annuaire-", "comparis.ch",
            # Médias (sites de presse)
            "rts.ch", "24heures.ch", "lematin.ch", "20min.ch", "letemps.ch",
            "tdg.ch", "blick.ch", "srf.ch", "nzz.ch",
            # Immobilier
            "homegate.ch", "immoscout24.ch", "immoweb.ch", "anibis.ch",
            "immobilier", "real-estate", "agence-immobiliere",
            # Grandes chaînes/Groups (hôtels, restaurants de chaînes)
            "accor.com", "booking.com", "expedia.com", "tripadvisor.com",
            "airbnb.com", "trivago.com", "agoda.com", "hotels.com",
            "groupon.com", "uber.com", "deliveroo.com", "justeat.com",
            # E-commerce/Marketplaces
            "amazon", "galaxus.ch", "digitec.ch", "ricardo.ch",
            "coop.ch", "migros.ch",
            # Voyages
            "booking.com", "trivago", "tripadvisor",
            # Autres grandes bases de données
            "ch.ch", "search.ch", "local.ch"
        ]
        
        for domaine in domaines_exclus:
            if domaine in url_lower:
                return True
        
        # Exclure les URLs avec des patterns suspects (sites génériques de groupes)
        # Exemples: restaurants.accor.com, hotels.booking.com, etc.
        patterns_exclus = [
            "/restaurant-", "/hotel-", "/shop-", "/store-", "/location-",
            "/fr/restaurant", "/fr/hotel", "/en/restaurant", "/en/hotel",
            "/restaurant/", "/hotel/", "/location/",
            ".accor.", ".booking.", ".expedia.", ".tripadvisor.",
            "restaurants.", "hotels.", "shops."
        ]
        if any(pattern in url_lower for pattern in patterns_exclus):
            return True
            
            return False
    
    def _est_resultat_non_pertinent(self, titre: str, description: str) -> bool:
        """
        Vérifie si un résultat de recherche est non pertinent (pas une PME privée).
        
        Args:
            titre: Titre du résultat
            description: Description du résultat
        
        Returns:
            True si le résultat doit être exclu, False sinon
        """
        texte_complet = (titre + " " + description).lower()
        
        # Mots-clés qui indiquent un site non pertinent (gouvernemental, grande entreprise, immobilier)
        mots_exclus = [
            # Gouvernemental/Public
            "ville de", "commune de", "administration", "canton", "canton de",
            "service public", "gouvernement", "municipalité", "mairie",
            "préfecture", "département", "région", "office cantonal",
            "office fédéral", "portail public", "guichet", "annuaire officiel",
            # Immobilier
            "immobilier", "agence immobilière", "real estate", "location", "achat",
            "vendre", "louer", "appartement", "maison", "bien immobilier",
            # Grandes plateformes/Annuaires
            "wikipedia", "encyclopédie", "comparis", "homegate", "immoscout",
            "immoweb", "anibis", "pages jaunes", "annuaire téléphonique",
            # Médias (sites de presse)
            "rts", "24heures", "lematin", "20min", "letemps", "tdg", "blick", "srf", "nzz",
            # Grandes entreprises et leurs filiales
            "coop", "migros", "denner", "manor", "globus", "galaxus", "digitec", "amazon",
            "mcdonald", "burger king", "kfc", "starbucks", "zara", "h&m", "ikea",
            "media markt", "fnac", "swisscom", "sunrise", "ubs", "credit suisse",
            "accor", "expedia", "tripadvisor", "airbnb", "trivago",
            "filiale", "succursale", "branch", "subsidiary", "franchise"
        ]
        
        for mot in mots_exclus:
            if mot in texte_complet:
                return True
        
        return False
    
    def _extraire_nom_entreprise(self, titre: str) -> str:
        """
        Extrait le nom de l'entreprise depuis le titre du résultat.
        
        Args:
            titre: Titre du résultat de recherche
        
        Returns:
            Nom de l'entreprise
        """
        # Nettoyer le titre (enlever les suffixes communs)
        nom = titre.split(" - ")[0].split(" | ")[0].strip()
        
        # Nettoyer les préfixes communs de sites gouvernementaux
        prefixes_a_enlever = [
            "Ville de ", "Commune de ", "Administration de ", "Office de ",
            "Service de ", "Canton de "
        ]
        
        for prefix in prefixes_a_enlever:
            if nom.startswith(prefix):
                nom = nom[len(prefix):].strip()
        
        return nom
    
    def _extraire_telephone(self, texte: str) -> Optional[str]:
        """
        Tente d'extraire un numéro de téléphone français depuis un texte.
        
        Args:
            texte: Texte à analyser
        
        Returns:
            Numéro de téléphone trouvé ou None
        """
        import re
        
        # Patterns pour numéros français
        patterns = [
            r'0[1-9](?:[.\s-]?[0-9]{2}){4}',  # Format standard
            r'\+33[1-9](?:[.\s-]?[0-9]{2}){4}',  # Format international
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texte)
            if match:
                return match.group(0).replace(".", "").replace(" ", "").replace("-", "")
        
        return None
    
    def rechercher_linkedin(self, nom_entreprise: str, site_web: str = "", ville: str = "") -> Optional[str]:
        """
        Recherche le profil LinkedIn d'une entreprise avec meilleur filtrage.
        
        Args:
            nom_entreprise: Nom de l'entreprise
            site_web: Site web de l'entreprise (pour validation)
            ville: Ville de l'entreprise (optionnel)
        
        Returns:
            URL LinkedIn ou None
        """
        try:
            # Construire une requête plus précise
            query = f'"{nom_entreprise}" site:linkedin.com/company'
            if ville:
                query = f'"{nom_entreprise}" {ville} site:linkedin.com/company'
            
            payload = {
                "q": query,
                "num": 10
            }
            
            response = requests.post(
                f"{self.base_url}/search",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "organic" in data:
                # Extraire le domaine du site web pour validation
                domaine_site = None
                if site_web:
                    from urllib.parse import urlparse
                    parsed = urlparse(site_web if site_web.startswith("http") else f"https://{site_web}")
                    domaine_site = parsed.netloc.replace("www.", "").lower()
                
                # Normaliser le nom de l'entreprise pour comparaison
                nom_normalise = nom_entreprise.lower().replace(" ", "").replace("-", "").replace("_", "")
                
                for result in data["organic"]:
                    link = result.get("link", "")
                    title = result.get("title", "").lower()
                    snippet = result.get("snippet", "").lower()
                    
                    # Vérifier que c'est bien une page company LinkedIn
                    if "linkedin.com/company" in link:
                        # Validation supplémentaire : vérifier que le nom de l'entreprise apparaît
                        if nom_normalise[:5] in title.replace(" ", "").replace("-", "") or \
                           nom_normalise[:5] in snippet.replace(" ", "").replace("-", ""):
                            logger.info(f"LinkedIn trouvé et validé: {link}")
                            return link
                
                # Si aucune correspondance exacte, prendre le premier résultat LinkedIn company
                for result in data["organic"]:
                    link = result.get("link", "")
                    if "linkedin.com/company" in link:
                        logger.info(f"LinkedIn trouvé (première correspondance): {link}")
                        return link
            
            return None
            
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche LinkedIn pour {nom_entreprise}: {e}")
            return None
