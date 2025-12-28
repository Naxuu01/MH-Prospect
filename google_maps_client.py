"""
Module client pour l'API Google Maps Places - Recherche d'entreprises locales avec téléphones vérifiés.
"""
import requests
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """Client pour interroger l'API Google Maps Places."""
    
    def __init__(self, api_key: str):
        """
        Initialise le client Google Maps.
        
        Args:
            api_key: Clé API Google Maps
        """
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place"
    
    def rechercher_commerces_locaux(self, ville: str, pays: str = "Suisse", 
                                     nombre_resultats: int = 20,
                                     cibles: List[str] = None,
                                     service_propose: str = "",
                                     proposition_valeur: str = "") -> List[Dict[str, Any]]:
        """
        Recherche des commerces et PME locales via Google Maps Places API.
        Exclut l'immobilier et cible les vraies petites entreprises locales.
        
        Args:
            ville: Ville de recherche
            pays: Pays de recherche
            nombre_resultats: Nombre de résultats souhaités
        
        Returns:
            Liste de commerces locaux trouvés
        """
        try:
            commerces = []
            
            # Construire les requêtes à partir des cibles de la config avec localisation précise
            localisation_precise = self._construire_localisation_maps(ville, pays)
            
            if cibles and len(cibles) > 0:
                # Grouper les cibles par catégorie pour équilibrer les résultats
                query_groups = []
                
                # Créer des groupes logiques à partir des cibles avec localisation précise et renforcement
                # Adapter les requêtes selon le service proposé pour mieux qualifier
                
                # Analyser le service pour ajouter des termes de qualification
                service_lower = service_propose.lower() if service_propose else ""
                termes_qualification = self._extraire_termes_qualification(service_lower, proposition_valeur)
                
                restauration = [c for c in cibles if any(mot in c.lower() for mot in ["restaurant", "crêperie", "creperie", "boulangerie"])]
                if restauration:
                    # Pour restauration : ajouter des termes selon le service
                    if "site web" in service_lower:
                        query_groups.append([f"{c} {localisation_precise}" for c in restauration])
                    else:
                        query_groups.append([f"{c} local {localisation_precise}" for c in restauration])
                
                hebergement = [c for c in cibles if any(mot in c.lower() for mot in ["hôtel", "hotel"])]
                if hebergement:
                    # Pour hôtels : chercher des hôtels indépendants qui pourraient avoir besoin du service
                    query_groups.append([f"{c} indépendant {localisation_precise}" for c in hebergement])
                
                services_pro = [c for c in cibles if any(mot in c.lower() for mot in ["fiduciaire", "cabinet comptable", "cabinet", "agence"])]
                if services_pro:
                    # Pour services pro : recherche directe avec localisation
                    query_groups.append([f"{c} {localisation_precise}" for c in services_pro])
                
                architecture = [c for c in cibles if any(mot in c.lower() for mot in ["architecte", "architecture"])]
                if architecture:
                    query_groups.append([f"{c} {localisation_precise}" for c in architecture])
                
                artisans = [c for c in cibles if any(mot in c.lower() for mot in ["plombier", "électricien", "artisan", "plomberie", "électricité"])]
                if artisans:
                    # Pour artisans : recherche locale avec le métier précis
                    query_groups.append([f"{c} {localisation_precise}" for c in artisans])
                
                autres = [c for c in cibles if c not in restauration + hebergement + services_pro + architecture + artisans]
                if autres:
                    # Pour les autres : ajouter "local" pour éviter les chaînes
                    query_groups.append([f"{c} local {localisation_precise}" for c in autres])
                
                # Si aucune catégorie trouvée, utiliser toutes les cibles directement
                if not query_groups:
                    query_groups = [[f"{c} {localisation_precise}" for c in cibles]]
            else:
                # Fallback si pas de cibles définies
                query_groups = [
                    [f"commerces {localisation_precise}", f"PME {localisation_precise}"]
                ]
            
            place_ids_trouves = set()
            
            # Calculer le nombre max de résultats par type pour avoir de la diversité
            # Si on cherche 20 résultats sur 7 groupes, on prend max 3-4 par groupe
            max_per_type = max(2, nombre_resultats // len(query_groups) + 1)
            
            # Parcourir chaque groupe pour équilibrer les résultats
            for query_group in query_groups:
                if len(commerces) >= nombre_resultats:
                    break
                
                for query in query_group:
                    if len(commerces) >= nombre_resultats:
                        break
                    
                    try:
                        # Limiter à max_per_type résultats par type pour avoir de la diversité
                        place_ids = self._recherche_textuelle_multiple(query, max_results=max_per_type, pays=pays)
                        
                        for place_id in place_ids:
                            if place_id in place_ids_trouves or len(commerces) >= nombre_resultats:
                                continue
                            place_ids_trouves.add(place_id)
                            
                            try:
                                details = self._obtenir_details(place_id)
                                if details and self._est_commerce_local_valide(details, pays):
                                    commerce = {
                                        "nom_entreprise": details.get("name", ""),
                                        "adresse": details.get("formatted_address"),
                                        "telephone": details.get("formatted_phone_number") or details.get("international_phone_number"),
                                        "site_web": details.get("website"),
                                        "note": details.get("rating"),
                                        "nb_avis": details.get("user_ratings_total"),
                                        "types": details.get("types", []),
                                        "google_maps_url": details.get("url")
                                    }
                                    
                                    # Vérifier qu'on n'a pas déjà ce commerce
                                    if not any(c.get("nom_entreprise") == commerce["nom_entreprise"] for c in commerces):
                                        commerces.append(commerce)
                            except Exception as e:
                                logger.debug(f"Erreur lors de l'obtention des détails pour {place_id}: {e}")
                                continue
                    except Exception as e:
                        logger.debug(f"Erreur lors de la recherche '{query}': {e}")
                        continue
                
                if len(commerces) >= nombre_resultats:
                    break
            
            logger.info(f"{len(commerces)} commerces locaux trouvés via Google Maps à {ville}")
            return commerces
            
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche Google Maps commerces: {e}")
            return []
    
    def _detecter_pays_resultat(self, details: Dict[str, Any]) -> Optional[str]:
        """
        Détecte le pays/région d'un résultat à partir de ses données.
        
        Args:
            details: Détails du commerce depuis Google Maps
        
        Returns:
            Code pays normalisé (ex: "ch", "fr", "ca", "qc") ou None
        """
        address_components = details.get("address_components", [])
        adresse = (details.get("formatted_address") or "").lower()
        site_web = (details.get("website") or "").lower()
        
        # 1. Vérifier d'abord les composants d'adresse (le plus fiable)
        for comp in address_components:
            if comp.get("types") and "country" in comp.get("types", []):
                country_code = comp.get("short_name", "").lower()
                # Si on détecte le Canada, chercher la province pour distinguer Québec
                if country_code == "ca":
                    # Chercher la province dans les composants
                    for comp_prov in address_components:
                        if comp_prov.get("types") and "administrative_area_level_1" in comp_prov.get("types", []):
                            prov_code = comp_prov.get("short_name", "").lower()
                            if prov_code == "qc":
                                return "qc"  # Québec spécifiquement
                    return "ca"  # Canada (autre province)
                return country_code
        
        # 2. Vérifier le domaine du site web
        if ".ch" in site_web or "suisse" in adresse or "switzerland" in adresse:
            return "ch"
        if ".fr" in site_web or ("france" in adresse and "quebec" not in adresse):
            return "fr"
        if ".qc.ca" in site_web or ("quebec" in adresse and "canada" in adresse):
            return "qc"
        if ".ca" in site_web and ".qc.ca" not in site_web:
            return "ca"
        
        # 3. Vérifier les mots-clés dans l'adresse
        adresse_lower = adresse.lower()
        if "québec" in adresse_lower or "quebec" in adresse_lower:
            if "montréal" in adresse_lower or "montreal" in adresse_lower:
                return "qc"
            if "canada" in adresse_lower:
                return "qc"
        if "montréal" in adresse_lower or "montreal" in adresse_lower:
            if "canada" in adresse_lower or "qc" in adresse_lower:
                return "qc"
        if "suisse" in adresse_lower or "switzerland" in adresse_lower or ", ch" in adresse_lower:
            return "ch"
        if "france" in adresse_lower and "quebec" not in adresse_lower:
            return "fr"
        if "canada" in adresse_lower:
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
        
        # Normalisations
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
        
        # Par défaut, retourner le pays tel quel (normalisé en lowercase)
        return pays_lower
    
    def _est_commerce_local_valide(self, details: Dict[str, Any], pays: str = "") -> bool:
        """Vérifie si un commerce est une vraie PME locale valide."""
        types = details.get("types", [])
        name = details.get("name", "").lower()
        
        # FILTRE GÉOGRAPHIQUE DYNAMIQUE : Exclure seulement si le pays ne correspond pas
        if pays:
            pays_cible_normalise = self._normaliser_pays_cible(pays)
            pays_resultat = self._detecter_pays_resultat(details)
            
            if pays_resultat:
                # Comparer intelligemment
                if pays_cible_normalise == "qc":
                    # Si on cherche Québec, accepter seulement Québec
                    if pays_resultat != "qc":
                        logger.debug(f"❌ Commerce exclu (pays={pays_resultat} au lieu de {pays_cible_normalise}): {name}")
                        return False
                elif pays_cible_normalise == "ca":
                    # Si on cherche Canada, accepter Canada mais pas Québec seul
                    if pays_resultat not in ["ca", "qc"]:
                        logger.debug(f"❌ Commerce exclu (pays={pays_resultat} au lieu de {pays_cible_normalise}): {name}")
                        return False
                elif pays_cible_normalise == "ch":
                    # Si on cherche Suisse, exclure tout ce qui n'est pas Suisse
                    if pays_resultat != "ch":
                        logger.debug(f"❌ Commerce exclu (pays={pays_resultat} au lieu de {pays_cible_normalise}): {name}")
                        return False
                elif pays_cible_normalise == "fr":
                    # Si on cherche France, exclure tout ce qui n'est pas France
                    if pays_resultat != "fr":
                        logger.debug(f"❌ Commerce exclu (pays={pays_resultat} au lieu de {pays_cible_normalise}): {name}")
                        return False
                else:
                    # Pour les autres pays, comparaison stricte
                    if pays_resultat != pays_cible_normalise:
                        logger.debug(f"❌ Commerce exclu (pays={pays_resultat} au lieu de {pays_cible_normalise}): {name}")
                        return False
        
        # Exclure l'immobilier
        if "real_estate_agency" in types or any(mot in name for mot in ["immobilier", "immobilière", "real estate", "agence immobilière"]):
            return False
        
        # Exclure les grandes chaînes, franchises et filiales
        grandes_chaines = [
            # Grandes surfaces suisses
            "coop", "migros", "denner", "aldi", "lidl", "manor", "globus",
            # E-commerce
            "galaxus", "digitec", "amazon", "booking", "comparis", "ricardo",
            # Grandes chaînes hôtels/restaurants/groups
            "accor", "expedia", "tripadvisor", "airbnb", "trivago", "hotels.com",
            # Restauration rapide
            "mcdonald", "burger king", "kfc", "subway", "pizza hut", "domino",
            "starbucks", "nespresso", "pret a manger",
            # Mode
            "zara", "h&m", "mango", "bershka", "c&a", "primark",
            # Meubles/Décoration
            "ikea", "conforama", "pfister", "micasa", "möbel pfister",
            # Électronique
            "media markt", "fnac", "saturn", "interdiscount",
            # Télécom/Banque
            "poste", "swisscom", "orange", "sunrise", "salt",
            "ubs", "credit suisse", "raiffeisen", "postfinance",
            # Autres grandes marques
            "nike", "adidas", "puma", "decathlon", "interio",
            # Indicateurs de filiales
            "filiale", "succursale", "branch", "subsidiary"
        ]
        if any(chain in name for chain in grandes_chaines):
            return False
        
        # Exclure les grandes banques mais permettre les petites fiduciaires/cabinets comptables (PME)
        grandes_banques = ["ubs", "credit suisse", "raiffeisen bank", "postfinance", "bnp paribas", "societe generale"]
        if any(banque in name for banque in grandes_banques):
            return False
        # Permettre les fiduciaires et cabinets comptables (sont des PME valides)
        
        return True
    
    def rechercher_entreprise_locale(self, nom_entreprise: str, ville: str, pays: str = "France") -> Optional[Dict[str, Any]]:
        """
        Recherche une entreprise locale via Google Maps Places API.
        
        Args:
            nom_entreprise: Nom de l'entreprise
            ville: Ville de recherche
            pays: Pays de recherche
        
        Returns:
            Données de l'entreprise trouvée ou None
        """
        try:
            # 1. Recherche textuelle avec ciblage géographique précis
            query = f"{nom_entreprise} {ville} {pays}"
            place_id = self._recherche_textuelle(query, ville, pays)
            
            if not place_id:
                return None
            
            # 2. Détails de l'établissement
            details = self._obtenir_details(place_id)
            
            if details:
                entreprise_data = {
                    "nom_entreprise": details.get("name", nom_entreprise),
                    "adresse": details.get("formatted_address"),
                    "telephone": details.get("formatted_phone_number") or details.get("international_phone_number"),
                    "site_web": details.get("website"),
                    "note": details.get("rating"),
                    "nb_avis": details.get("user_ratings_total"),
                    "horaires": self._formater_horaires(details.get("opening_hours")),
                    "types": details.get("types", []),
                    "google_maps_url": details.get("url"),
                    "latitude": details.get("geometry", {}).get("location", {}).get("lat"),
                    "longitude": details.get("geometry", {}).get("location", {}).get("lng")
                }
                
                logger.info(f"Entreprise trouvée sur Google Maps: {entreprise_data['nom_entreprise']}")
                return entreprise_data
            
            return None
            
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche Google Maps pour {nom_entreprise}: {e}")
            return None
    
    def _recherche_textuelle(self, query: str, ville: str = "", pays: str = "") -> Optional[str]:
        """
        Effectue une recherche textuelle pour trouver le place_id.
        
        Args:
            query: Requête de recherche
            ville: Ville pour le ciblage géographique (optionnel)
            pays: Pays pour le ciblage géographique (optionnel)
        
        Returns:
            Place ID ou None
        """
        try:
            url = f"{self.base_url}/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key,
                "language": "fr"
            }
            
            # Améliorer le ciblage géographique avec le paramètre region
            region_code = self._determiner_code_region(pays)
            if region_code:
                params["region"] = region_code
            
            try:
                response = requests.get(url, params=params, timeout=(10, 30))
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.Timeout:
                logger.debug(f"⏱️  Timeout recherche textuelle Google Maps")
                return None
            except requests.exceptions.ConnectionError:
                logger.debug(f"🔌 Erreur de connexion recherche textuelle Google Maps")
                return None
            except requests.exceptions.RequestException as e:
                logger.debug(f"❌ Erreur requête recherche textuelle Google Maps: {e}")
                return None
            
            if data.get("status") == "OK" and data.get("results"):
                # Prendre le premier résultat
                return data["results"][0].get("place_id")
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur inattendue recherche textuelle: {e}")
            return None
    
    def _obtenir_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtient les détails d'un établissement via son place_id.
        
        Args:
            place_id: ID de l'établissement
        
        Returns:
            Détails de l'établissement ou None
        """
        try:
            url = f"{self.base_url}/details/json"
            params = {
                "place_id": place_id,
                "key": self.api_key,
                "language": "fr",
                "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,opening_hours,types,geometry,url"
            }
            
            try:
                response = requests.get(url, params=params, timeout=(10, 30))
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.Timeout:
                logger.debug(f"⏱️  Timeout détails Google Maps")
                return None
            except requests.exceptions.ConnectionError:
                logger.debug(f"🔌 Erreur de connexion détails Google Maps")
                return None
            except requests.exceptions.RequestException as e:
                logger.debug(f"❌ Erreur requête détails Google Maps: {e}")
                return None
            
            if data.get("status") == "OK" and data.get("result"):
                return data["result"]
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur inattendue détails: {e}")
            return None
    
    def _formater_horaires(self, opening_hours: Optional[Dict[str, Any]]) -> Optional[str]:
        """Formate les horaires d'ouverture."""
        try:
            if not opening_hours:
                return None
            
            weekdays = {
                "Monday": "Lundi",
                "Tuesday": "Mardi",
                "Wednesday": "Mercredi",
                "Thursday": "Jeudi",
                "Friday": "Vendredi",
                "Saturday": "Samedi",
                "Sunday": "Dimanche"
            }
            
            periods = opening_hours.get("periods", [])
            if not periods:
                return None
            
            # Simplifier : retourner juste les heures du premier jour
            if periods and len(periods) > 0:
                first_period = periods[0]
                open_time = first_period.get("open", {}).get("time", "")
                close_time = first_period.get("close", {}).get("time", "")
                
                if open_time and close_time:
                    # Formater l'heure (HHMM -> HH:MM)
                    open_formatted = f"{open_time[:2]}:{open_time[2:]}"
                    close_formatted = f"{close_time[:2]}:{close_time[2:]}"
                    return f"{open_formatted} - {close_formatted}"
            
            return None
            
        except Exception:
            return None
    
    def _recherche_textuelle_multiple(self, query: str, max_results: int = 5, pays: str = "") -> List[str]:
        """Recherche textuelle qui retourne plusieurs place_ids avec ciblage géographique."""
        try:
            url = f"{self.base_url}/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key,
                "language": "fr"
            }
            
            # Améliorer le ciblage géographique avec le paramètre region
            region_code = self._determiner_code_region(pays)
            if region_code:
                params["region"] = region_code
            
            try:
                response = requests.get(url, params=params, timeout=(10, 30))
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.Timeout:
                logger.debug(f"⏱️  Timeout recherche textuelle multiple Google Maps")
                return []
            except requests.exceptions.ConnectionError:
                logger.debug(f"🔌 Erreur de connexion recherche textuelle multiple Google Maps")
                return []
            except requests.exceptions.RequestException as e:
                logger.debug(f"❌ Erreur requête recherche textuelle multiple Google Maps: {e}")
                return []
            
            place_ids = []
            if data.get("status") == "OK" and data.get("results"):
                for result in data["results"][:max_results]:
                    place_id = result.get("place_id")
                    if place_id:
                        place_ids.append(place_id)
            
            return place_ids
            
        except Exception as e:
            logger.debug(f"Erreur recherche textuelle multiple: {e}")
            return []
    
    def _construire_localisation_maps(self, ville: str, pays: str) -> str:
        """
        Construit une chaîne de localisation précise pour les requêtes Google Maps.
        
        Args:
            ville: Nom de la ville
            pays: Nom du pays
        
        Returns:
            Chaîne de localisation formatée pour Google Maps
        """
        ville_clean = ville.strip()
        pays_lower = pays.lower()
        
        # Normaliser le nom du pays pour Google Maps
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
        
        # Format : "Ville, Pays" pour Google Maps
        return f"{ville_clean}, {pays_normalise}"
    
    def _determiner_code_region(self, pays: str) -> Optional[str]:
        """
        Détermine le code de région Google Maps selon le pays.
        
        Args:
            pays: Nom du pays
        
        Returns:
            Code de région (ex: "ch", "fr") ou None
        """
        pays_lower = pays.lower()
        
        if pays_lower in ["suisse", "switzerland", "schweiz"]:
            return "ch"
        elif pays_lower in ["france"]:
            return "fr"
        elif pays_lower in ["belgium", "belgique", "belgie"]:
            return "be"
        elif pays_lower in ["luxembourg"]:
            return "lu"
        elif pays_lower in ["germany", "allemagne", "deutschland"]:
            return "de"
        elif pays_lower in ["italy", "italie", "italia"]:
            return "it"
        else:
            return None
    
    def _extraire_termes_qualification(self, service_propose: str, proposition_valeur: str = "") -> List[str]:
        """
        Extrait des termes de qualification selon le service proposé et la proposition de valeur.
        Optimisé pour développeurs web, agences web et agences de com.
        
        Args:
            service_propose: Service proposé
            proposition_valeur: Proposition de valeur
        
        Returns:
            Liste de termes de qualification
        """
        termes = []
        service_lower = (service_propose or "").lower()
        prop_lower = (proposition_valeur or "").lower()
        
        # PRIORITÉ #1: Services web/développement (optimisé pour développeurs web, agences web)
        if any(mot in service_lower for mot in ["site web", "website", "web", "développement", "developpement", 
                                                  "création site", "creation site", "refonte", "wordpress", "shopify"]):
            # Chercher des commerces locaux et PME qui pourraient avoir besoin d'un site
            termes.extend(["local", "indépendant", "PME"])
        
        # PRIORITÉ #2: Marketing digital/Communication (optimisé pour agences de com, marketing)
        elif any(mot in service_lower for mot in ["marketing", "visibilité", "référencement", "seo", "communication",
                                                   "réseaux sociaux", "social media", "digital", "publicité"]):
            # Chercher des PME et commerces qui pourraient améliorer leur visibilité digitale
            termes.extend(["local", "PME", "indépendant", "commerce"])
        
        # Conseil/Consulting digital
        elif any(mot in service_lower for mot in ["conseil", "consulting", "stratégie digitale"]):
            termes.extend(["cabinet", "consultant", "entreprise", "PME"])
        
        return termes
