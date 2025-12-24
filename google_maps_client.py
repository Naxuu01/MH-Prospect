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
                                     cibles: List[str] = None) -> List[Dict[str, Any]]:
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
            
            # Construire les requêtes à partir des cibles de la config
            if cibles and len(cibles) > 0:
                # Grouper les cibles par catégorie pour équilibrer les résultats
                query_groups = []
                
                # Créer des groupes logiques à partir des cibles
                restauration = [c for c in cibles if any(mot in c.lower() for mot in ["restaurant", "crêperie", "creperie", "boulangerie"])]
                if restauration:
                    query_groups.append([f"{c} {ville} {pays}" for c in restauration])
                
                hebergement = [c for c in cibles if any(mot in c.lower() for mot in ["hôtel", "hotel"])]
                if hebergement:
                    query_groups.append([f"{c} {ville} {pays}" for c in hebergement])
                
                services_pro = [c for c in cibles if any(mot in c.lower() for mot in ["fiduciaire", "cabinet comptable", "cabinet", "agence"])]
                if services_pro:
                    query_groups.append([f"{c} {ville} {pays}" for c in services_pro])
                
                architecture = [c for c in cibles if any(mot in c.lower() for mot in ["architecte", "architecture"])]
                if architecture:
                    query_groups.append([f"{c} {ville} {pays}" for c in architecture])
                
                autres = [c for c in cibles if c not in restauration + hebergement + services_pro + architecture]
                if autres:
                    query_groups.append([f"{c} {ville} {pays}" for c in autres])
                
                # Si aucune catégorie trouvée, utiliser toutes les cibles directement
                if not query_groups:
                    query_groups = [[f"{c} {ville} {pays}" for c in cibles]]
            else:
                # Fallback si pas de cibles définies
                query_groups = [
                    [f"commerces {ville} {pays}", f"PME {ville} {pays}"]
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
                        place_ids = self._recherche_textuelle_multiple(query, max_results=max_per_type)
                        
                        for place_id in place_ids:
                            if place_id in place_ids_trouves or len(commerces) >= nombre_resultats:
                                continue
                            place_ids_trouves.add(place_id)
                            
                            try:
                                details = self._obtenir_details(place_id)
                                if details and self._est_commerce_local_valide(details):
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
    
    def _est_commerce_local_valide(self, details: Dict[str, Any]) -> bool:
        """Vérifie si un commerce est une vraie PME locale valide."""
        types = details.get("types", [])
        name = details.get("name", "").lower()
        
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
            # 1. Recherche textuelle
            query = f"{nom_entreprise} {ville} {pays}"
            place_id = self._recherche_textuelle(query)
            
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
    
    def _recherche_textuelle(self, query: str) -> Optional[str]:
        """
        Effectue une recherche textuelle pour trouver le place_id.
        
        Args:
            query: Requête de recherche
        
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
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                # Prendre le premier résultat
                return data["results"][0].get("place_id")
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Erreur recherche textuelle Google Maps: {e}")
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
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("result"):
                return data["result"]
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Erreur détails Google Maps: {e}")
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
    
    def _recherche_textuelle_multiple(self, query: str, max_results: int = 5) -> List[str]:
        """Recherche textuelle qui retourne plusieurs place_ids."""
        try:
            url = f"{self.base_url}/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key,
                "language": "fr"
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
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
