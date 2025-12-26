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
                                         cibles: List[str] = None,
                                         proposition_valeur: str = "") -> List[Dict[str, Any]]:
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
            
            # EXCLUSIONS GÉOGRAPHIQUES STRICTES : Si Suisse, exclure explicitement tout ce qui est Québec/Canada
            if pays.lower() in ["suisse", "switzerland"]:
                exclusions += (
                    " -site:.qc.ca -site:.ca -Québec -Montréal -Canada -quebec -montreal -canada "
                    "-toronto -vancouver -ottawa -calgary -edmonton "
                    "-site:quebec -site:montreal -site:canada"
                )
            
            # Construire des requêtes intelligentes et contextuelles
            localisation = self._construire_localisation(ville, pays)
            exclusions += self._ajouter_exclusions_geographiques(pays)
            
            # Construire des requêtes optimisées avec contexte selon le service
            query = self._construire_requete_qualifiee(
                cibles=cibles,
                ville=ville,
                localisation=localisation,
                service_propose=service_propose,
                secteur_entreprise=secteur_entreprise,
                proposition_valeur=proposition_valeur,
                exclusions=exclusions
            )
            
            logger.info(f"🔍 Requête Serper qualifiée: {query[:200]}...")
            
            # Ajuster le code pays et langue pour Google selon la région
            gl_code, hl_code = self._determiner_codes_geo(pays)
            
            # Construire la localisation précise pour le paramètre location (format: "Ville, Pays")
            ville_clean = ville.strip()
            pays_lower = pays.lower()
            if pays_lower in ["suisse", "switzerland", "schweiz"]:
                pays_normalise = "Suisse"
            elif pays_lower in ["france"]:
                pays_normalise = "France"
            elif pays_lower in ["belgium", "belgique", "belgie"]:
                pays_normalise = "Belgique"
            elif pays_lower in ["luxembourg"]:
                pays_normalise = "Luxembourg"
            else:
                pays_normalise = pays
            location_precise = f"{ville_clean}, {pays_normalise}"
            
            payload = {
                "q": query,
                "num": nombre_resultats,
                "gl": gl_code,  # Code pays Google (force la région)
                "hl": hl_code,   # Langue
                "location": location_precise  # Localisation précise pour améliorer la pertinence
            }
            
            logger.debug(f"Payload Serper: gl={gl_code}, hl={hl_code}, location={location_precise}, query={query[:100]}...")
            
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
                    
                    # FILTRE GÉOGRAPHIQUE DYNAMIQUE : Exclure seulement si le pays ne correspond pas
                    if pays:
                        pays_resultat = self._detecter_pays_resultat(titre, description, link)
                        if pays_resultat and not self._pays_correspond(pays, pays_resultat):
                            logger.debug(f"❌ Résultat Serper exclu (pays={pays_resultat} au lieu de {pays}): {titre}")
                            continue
                    
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
    
    def _construire_localisation(self, ville: str, pays: str) -> str:
        """
        Construit une chaîne de localisation précise pour les requêtes de recherche.
        
        Args:
            ville: Nom de la ville
            pays: Nom du pays
        
        Returns:
            Chaîne de localisation formatée pour Google
        """
        ville_clean = ville.strip()
        pays_lower = pays.lower()
        
        # Normaliser le nom du pays
        if pays_lower in ["suisse", "switzerland", "schweiz"]:
            pays_normalise = "Suisse"
        elif pays_lower in ["france"]:
            pays_normalise = "France"
        elif pays_lower in ["belgium", "belgique", "belgie"]:
            pays_normalise = "Belgique"
        elif pays_lower in ["luxembourg"]:
            pays_normalise = "Luxembourg"
        else:
            pays_normalise = pays
        
        # Construire la localisation avec guillemets pour plus de précision
        return f'"{ville_clean}" "{pays_normalise}"'
    
    def _ajouter_exclusions_geographiques(self, pays: str) -> str:
        """
        Ajoute des exclusions géographiques selon le pays ciblé.
        
        Args:
            pays: Pays de recherche
        
        Returns:
            Chaîne d'exclusions géographiques
        """
        pays_lower = pays.lower()
        exclusions_geo = ""
        
        if pays_lower in ["suisse", "switzerland", "schweiz"]:
            # Exclure explicitement Québec/Canada et autres régions confuses
            exclusions_geo = (
                " -site:.qc.ca -site:.ca -Québec -Montréal -Canada -quebec -montreal -canada "
                "-toronto -vancouver -ottawa -calgary -edmonton "
                "-site:quebec -site:montreal -site:canada "
                "-site:quebec.ca -site:montreal.ca"
            )
        elif pays_lower in ["france"]:
            # Exclure Québec/Canada et autres régions francophones non françaises
            exclusions_geo = (
                " -Québec -Montréal -Canada -quebec -montreal -canada "
                "-site:.qc.ca -site:.ca"
            )
        elif pays_lower in ["belgium", "belgique", "belgie"]:
            # Exclure les régions francophones hors Belgique
            exclusions_geo = (
                " -Québec -Montréal -Canada -quebec -montreal -canada "
                "-site:.qc.ca"
            )
        
        return exclusions_geo
    
    def _determiner_codes_geo(self, pays: str) -> tuple:
        """
        Détermine les codes géographiques Google (gl) et langue (hl) selon le pays.
        
        Args:
            pays: Nom du pays
        
        Returns:
            Tuple (gl_code, hl_code)
        """
        pays_lower = pays.lower()
        
        if pays_lower in ["suisse", "switzerland", "schweiz"]:
            return ("ch", "fr")  # Suisse, langue française
        elif pays_lower in ["france"]:
            return ("fr", "fr")  # France, langue française
        elif pays_lower in ["belgium", "belgique", "belgie"]:
            return ("be", "fr")  # Belgique, langue française
        elif pays_lower in ["luxembourg"]:
            return ("lu", "fr")  # Luxembourg, langue française
        elif pays_lower in ["germany", "allemagne", "deutschland"]:
            return ("de", "de")  # Allemagne, langue allemande
        elif pays_lower in ["italy", "italie", "italia"]:
            return ("it", "it")  # Italie, langue italienne
        else:
            # Par défaut : Suisse/français
            return ("ch", "fr")
    
    def _construire_requete_qualifiee(self, cibles: List[str], ville: str, localisation: str,
                                     service_propose: str, secteur_entreprise: str,
                                     proposition_valeur: str, exclusions: str) -> str:
        """
        Construit une requête de recherche qualifiée et contextuelle selon le service proposé.
        
        Args:
            cibles: Liste des types d'entreprises à cibler
            ville: Ville de recherche
            localisation: Localisation formatée (ex: "Genève" "Suisse")
            service_propose: Service proposé (ex: "création de sites web")
            secteur_entreprise: Secteur de l'entreprise
            proposition_valeur: Proposition de valeur
            exclusions: Chaîne d'exclusions déjà construite
        
        Returns:
            Requête Google optimisée et qualifiée
        """
        service_lower = service_propose.lower()
        proposition_lower = proposition_valeur.lower() if proposition_valeur else ""
        
        # Identifier les signaux de besoin selon le service proposé
        # OPTIMISATION PRINCIPALE: Services web/digitaux (développeurs web, agences web, agences de com)
        signaux_besoin = []
        termes_qualification = '"PME" OR "commerce local" OR "artisan" OR "indépendant" OR "entreprise"'
        
        # Détection intelligente des services pour identifier les besoins
        service_lower = service_propose.lower()
        
        # PRIORITÉ #1: Services numériques/web/développement (optimisé pour développeurs web, agences web, agences de com)
        if any(mot in service_lower for mot in ["site web", "website", "internet", "web", "e-commerce", "ecommerce", 
                                                  "application", "app", "développement", "développeur", "developpeur",
                                                  "création site", "creation site", "refonte", "design", "ui/ux",
                                                  "wordpress", "shopify", "prestashop", "woocommerce", "landing page",
                                                  "vitrine", "portfolio", "blog", "cms", "frontend", "backend"]):
            signaux_besoin.extend([
                '"pas de site web"',
                '"sans site"',
                '"site obsolète"',
                '"besoin site"',
                '"pas de présence en ligne"',
                '"site pas responsive"',
                '"site ancien"',
                '"refonte site"',
                '"besoin site vitrine"',
                '"site e-commerce"',
                '"site pas mobile"',
                '"site lent"',
                '"moderniser site"',
                '"besoin site professionnel"',
                '"site pas optimisé"',
                '"pas de site responsive"',
                '"site à refaire"',
                '"besoin application"',
                '"site daté"',
                '"site non sécurisé"'
            ])
            termes_qualification = '"commerce local" OR "PME" OR "artisan" OR "indépendant" OR "entreprise" OR "boutique" OR "restaurant" OR "hôtel" OR "cabinet" OR "agence" OR "consultant"'
        
        # PRIORITÉ #2: Marketing digital/Communication (optimisé pour agences de com, marketing digital)
        elif any(mot in service_lower for mot in ["marketing", "visibilité", "communication", "référencement", "seo", 
                                                   "réseaux sociaux", "social media", "publicité", "publicite", "annonce",
                                                   "campagne", "content marketing", "marketing digital", "digital marketing",
                                                   "google ads", "facebook ads", "instagram", "linkedin", "community management",
                                                   "growth hacking", "lead generation", "conversion", "branding", "stratégie digitale"]):
            signaux_besoin.extend([
                '"faible visibilité"',
                '"pas visible"',
                '"référencement"',
                '"besoin clients"',
                '"augmenter ventes"',
                '"manque de visibilité"',
                '"pas de stratégie digitale"',
                '"réseaux sociaux"',
                '"SEO"',
                '"pas de publicité en ligne"',
                '"faible trafic"',
                '"pas de leads"',
                '"pas d\'avis clients"',
                '"note google basse"',
                '"concurrents mieux visibles"',
                '"pas de présence instagram"',
                '"pas de stratégie social media"',
                '"manque de notoriété"',
                '"besoin visibilité locale"',
                '"pas de campagne publicitaire"'
            ])
            termes_qualification = '"commerce" OR "PME" OR "entreprise locale" OR "indépendant" OR "boutique" OR "restaurant" OR "hôtel" OR "artisan" OR "cabinet" OR "consultant"'
        
        # Marketing/Visibilité
        elif any(mot in service_lower for mot in ["marketing", "visibilité", "communication", "référencement", "seo", "réseaux sociaux", "social media", "publicité", "publicite", "annonce"]):
            signaux_besoin.extend([
                '"faible visibilité"',
                '"pas visible"',
                '"référencement"',
                '"besoin clients"',
                '"augmenter ventes"'
            ])
            termes_qualification = '"commerce" OR "PME" OR "entreprise locale" OR "indépendant" OR "boutique"'
        
        # Conseil/Consulting
        elif any(mot in service_lower for mot in ["conseil", "consulting", "accompagnement", "stratégie", "strategie", "audit", "formation"]):
            termes_qualification = '"cabinet" OR "consultant" OR "entreprise" OR "PME" OR "directeur" OR "dirigeant"'
            signaux_besoin.extend([
                '"besoin conseil"',
                '"accompagnement"',
                '"optimisation"'
            ])
        
        # Services financiers/comptables
        elif any(mot in service_lower for mot in ["comptable", "fiscal", "financier", "expertise comptable", "gestion", "paie"]):
            termes_qualification = '"PME" OR "entreprise" OR "commerçant" OR "artisan" OR "chef d\'entreprise"'
            signaux_besoin.extend([
                '"gestion comptable"',
                '"déclaration fiscale"',
                '"comptabilité"'
            ])
        
        # Services juridiques
        elif any(mot in service_lower for mot in ["juridique", "droit", "avocat", "juriste", "contrat", "conformité"]):
            termes_qualification = '"entreprise" OR "PME" OR "startup" OR "dirigeant" OR "patron"'
            signaux_besoin.extend([
                '"conseil juridique"',
                '"besoin avocat"',
                '"contrat"'
            ])
        
        # Services RH/Recrutement
        elif any(mot in service_lower for mot in ["rh", "ressources humaines", "recrutement", "recrut", "paie", "paye", "salaire"]):
            termes_qualification = '"entreprise" OR "PME" OR "chef d\'entreprise" OR "directeur"'
            signaux_besoin.extend([
                '"recrutement"',
                '"gestion paie"',
                '"ressources humaines"'
            ])
        
        # Services immobiliers
        elif any(mot in service_lower for mot in ["immobilier", "immobilier", "location", "vente", "bien"]):
            termes_qualification = '"entreprise" OR "PME" OR "commerçant"'
            signaux_besoin.extend([
                '"bureau immobilier"',
                '"agence immobilière"'
            ])
        
        # Services de nettoyage/entretien
        elif any(mot in service_lower for mot in ["nettoyage", "entretien", "ménage", "propreté"]):
            termes_qualification = '"entreprise" OR "bureau" OR "commerce" OR "restaurant" OR "hôtel"'
            signaux_besoin.extend([
                '"nettoyage"',
                '"entretien"',
                '"propreté"'
            ])
        
        # Services de sécurité
        elif any(mot in service_lower for mot in ["sécurité", "securite", "alarme", "surveillance", "gardiennage"]):
            termes_qualification = '"entreprise" OR "commerce" OR "bureau" OR "magasin"'
            signaux_besoin.extend([
                '"sécurité"',
                '"surveillance"',
                '"alarme"'
            ])
        
        # Services de transport/logistique
        elif any(mot in service_lower for mot in ["transport", "livraison", "logistique", "livreur", "coursier"]):
            termes_qualification = '"entreprise" OR "commerce" OR "e-commerce" OR "boutique"'
            signaux_besoin.extend([
                '"livraison"',
                '"transport"',
                '"logistique"'
            ])
        
        # Services génériques (fallback intelligent)
        else:
            # Analyse intelligente: extraire des mots-clés du service pour trouver des besoins
            mots_cles_service = [mot for mot in service_lower.split() if len(mot) > 3]
            # Chercher des entreprises qui pourraient avoir besoin de ce type de service
            signaux_besoin.extend([
                f'"{service_propose.split()[0]}"' if service_propose else '"service"',
                '"besoin"',
                '"amélioration"'
            ])
            termes_qualification = '"PME" OR "entreprise" OR "commerce local" OR "artisan" OR "indépendant"'
        
        # Analyser la proposition de valeur pour affiner
        termes_proposition = []
        if "leads" in proposition_lower or "clients" in proposition_lower:
            termes_proposition.append('"nouveaux clients"')
        if "visibilité" in proposition_lower or "visible" in proposition_lower:
            termes_proposition.append('"visibilité"')
        if "online" in proposition_lower or "ligne" in proposition_lower:
            termes_proposition.append('"présence en ligne"')
        
        # Construire la partie cibles
        if cibles and len(cibles) > 0:
            # Grouper les cibles intelligemment avec variantes automatiques
            cibles_groupes = []
            for cible in cibles:
                cible_lower = cible.lower()
                # Ajouter des variantes intelligentes pour améliorer les résultats
                if any(mot in cible_lower for mot in ["restaurant", "restauration", "bistrot", "brasserie"]):
                    cibles_groupes.append(f'"{cible}" OR "restaurant {ville}" OR "restauration {ville}"')
                elif any(mot in cible_lower for mot in ["hôtel", "hotel", "hébergement", "hebergement"]):
                    cibles_groupes.append(f'"{cible}" OR "hôtel {ville}" OR "hébergement {ville}"')
                elif any(mot in cible_lower for mot in ["plombier", "plomberie"]):
                    cibles_groupes.append(f'"{cible}" OR "plomberie {ville}" OR "plombier {ville}"')
                elif any(mot in cible_lower for mot in ["fiduciaire", "fiduciaire", "fiduc"]):
                    cibles_groupes.append(f'"{cible}" OR "fiduciaire {ville}" OR "cabinet fiduciaire {ville}"')
                elif any(mot in cible_lower for mot in ["architecte", "architecture"]):
                    cibles_groupes.append(f'"{cible}" OR "architecture {ville}" OR "bureau d\'architecture {ville}"')
                elif any(mot in cible_lower for mot in ["électricien", "electricien", "électricité", "electricite"]):
                    cibles_groupes.append(f'"{cible}" OR "électricien {ville}" OR "électricité {ville}"')
                elif any(mot in cible_lower for mot in ["comptable", "comptabilité", "comptabilite"]):
                    cibles_groupes.append(f'"{cible}" OR "comptable {ville}" OR "cabinet comptable {ville}"')
                elif any(mot in cible_lower for mot in ["garage", "mécanique", "mecanique", "auto"]):
                    cibles_groupes.append(f'"{cible}" OR "garage {ville}" OR "mécanique {ville}"')
                elif any(mot in cible_lower for mot in ["coiffeur", "coiffure", "salon"]):
                    cibles_groupes.append(f'"{cible}" OR "coiffeur {ville}" OR "salon de coiffure {ville}"')
                elif any(mot in cible_lower for mot in ["boulanger", "boulangerie", "pâtisserie", "patisserie"]):
                    cibles_groupes.append(f'"{cible}" OR "boulangerie {ville}" OR "pâtisserie {ville}"')
                elif any(mot in cible_lower for mot in ["avocat", "juriste", "cabinet juridique"]):
                    cibles_groupes.append(f'"{cible}" OR "avocat {ville}" OR "cabinet d\'avocat {ville}"')
                elif any(mot in cible_lower for mot in ["médecin", "medecin", "docteur", "cabinet médical"]):
                    cibles_groupes.append(f'"{cible}" OR "médecin {ville}" OR "cabinet médical {ville}"')
                elif any(mot in cible_lower for mot in ["pharmacie", "pharmacien"]):
                    cibles_groupes.append(f'"{cible}" OR "pharmacie {ville}"')
                elif any(mot in cible_lower for mot in ["vétérinaire", "veterinaire", "vétérinaire"]):
                    cibles_groupes.append(f'"{cible}" OR "vétérinaire {ville}" OR "clinique vétérinaire {ville}"')
                else:
                    # Pour les autres cibles, ajouter simplement la ville
                    cibles_groupes.append(f'"{cible} {ville}"')
            
            types_pme = f'({" OR ".join(cibles_groupes)})'
        else:
            types_pme = f'({termes_qualification})'
        
        # Construire la requête selon le contexte
        # Format : (types d'entreprises) (localisation) (signaux de besoin OU termes qualification) (exclusions)
        
        if signaux_besoin:
            # Requête avec signaux de besoin explicites pour cibler les entreprises qui en ont besoin
            signaux_str = " OR ".join(signaux_besoin[:2])  # Limiter à 2 signaux pour éviter trop de complexité
            query = f'{types_pme} {localisation} ({signaux_str} OR {termes_qualification}) {exclusions}'
        else:
            # Requête standard mais qualifiée selon la proposition de valeur
            if termes_proposition:
                prop_str = " OR ".join(termes_proposition[:2])
                query = f'{types_pme} {localisation} ({termes_qualification}) {exclusions}'
            else:
                query = f'{types_pme} {localisation} ({termes_qualification}) {exclusions}'
        
        return query
    
    def _detecter_pays_resultat(self, titre: str, description: str, link: str) -> Optional[str]:
        """
        Détecte le pays/région d'un résultat Serper à partir de son titre, description et lien.
        
        Args:
            titre: Titre du résultat
            description: Description du résultat
            link: Lien du résultat
        
        Returns:
            Code pays normalisé (ex: "ch", "fr", "ca", "qc") ou None
        """
        texte_complet = (titre + " " + description + " " + link).lower()
        
        # Vérifier le domaine du site web (le plus fiable)
        if ".qc.ca" in link.lower() or ".quebec" in link.lower():
            return "qc"
        if ".ch" in link.lower():
            return "ch"
        if ".fr" in link.lower() and ".qc.ca" not in link.lower():
            return "fr"
        if ".ca" in link.lower() and ".qc.ca" not in link.lower():
            return "ca"
        if ".be" in link.lower():
            return "be"
        if ".lu" in link.lower():
            return "lu"
        
        # Vérifier les mots-clés géographiques dans le texte
        if "québec" in texte_complet or "quebec" in texte_complet:
            if "montréal" in texte_complet or "montreal" in texte_complet:
                return "qc"
            if "canada" in texte_complet:
                return "qc"
        if ("montréal" in texte_complet or "montreal" in texte_complet) and "canada" in texte_complet:
            return "qc"
        if "suisse" in texte_complet or "switzerland" in texte_complet or ", ch" in texte_complet:
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
        pays_lower = pays.lower().strip()
        
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
