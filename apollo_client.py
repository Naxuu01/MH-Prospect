"""
Module client pour l'API Apollo.io - Recherche d'emails, téléphones, LinkedIn et données entreprise.
"""
import requests
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ApolloClient:
    """Client pour interroger l'API Apollo.io."""
    
    def __init__(self, api_key: str):
        """
        Initialise le client Apollo.io.
        
        Args:
            api_key: Clé API Apollo.io
        """
        self.api_key = api_key
        self.base_url = "https://api.apollo.io/v1"
        self.headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json"
        }
    
    def rechercher_entreprise_et_dirigeant(self, nom_entreprise: str, site_web: str = "", 
                                          ville: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Recherche une entreprise et son dirigeant via Apollo.io.
        
        Args:
            nom_entreprise: Nom de l'entreprise
            site_web: Site web de l'entreprise (optionnel)
            ville: Ville de l'entreprise (optionnel)
        
        Returns:
            Tuple (donnees_entreprise, dirigeant_info)
        """
        try:
            # 1. Rechercher l'entreprise
            entreprise_data = self._rechercher_entreprise(nom_entreprise, site_web, ville)
            
            if not entreprise_data:
                return None, None
            
            # 2. Rechercher le dirigeant dans cette entreprise
            dirigeant_data = self._rechercher_dirigeant(entreprise_data.get("id"), nom_entreprise)
            
            return entreprise_data, dirigeant_data
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Apollo.io pour {nom_entreprise}: {e}")
            return None, None
    
    def _rechercher_entreprise(self, nom_entreprise: str, site_web: str = "", ville: str = "") -> Optional[Dict[str, Any]]:
        """
        Recherche une entreprise sur Apollo.io.
        
        Args:
            nom_entreprise: Nom de l'entreprise
            site_web: Site web de l'entreprise
            ville: Ville de l'entreprise
        
        Returns:
            Données de l'entreprise ou None
        """
        try:
            # Filtrer les noms d'entreprises invalides (requêtes de recherche, etc.)
            if len(nom_entreprise) > 100 or "demander" in nom_entreprise.lower() or "permis" in nom_entreprise.lower():
                logger.debug(f"Nom d'entreprise suspect, skip Apollo: {nom_entreprise}")
                return None
            
            url = f"{self.base_url}/organizations/search"
            
            # Construire la requête
            query_params = {
                "api_key": self.api_key,
                "q_keywords": nom_entreprise[:50],  # Limiter la longueur
                "per_page": 5
            }
            
            if site_web:
                # Nettoyer le site web
                domaine = site_web.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                domaine_lower = domaine.lower()
                
                # Ignorer les domaines gouvernementaux qui ne sont pas des entreprises
                if domaine.endswith(".gov") or domaine.endswith(".ch") and "ge.ch" in domaine:
                    logger.debug(f"Domaine gouvernemental détecté, skip Apollo: {domaine}")
                    return None
                
                # Ignorer les domaines de grandes chaînes/groups problématiques
                domaines_exclus_apollo = [
                    "accor.com", "booking.com", "expedia.com", "tripadvisor.com",
                    "airbnb.com", "trivago.com", "hotels.com"
                ]
                if any(exclu in domaine_lower for exclu in domaines_exclus_apollo):
                    logger.debug(f"Domaine grande chaîne détecté, skip Apollo: {domaine}")
                    return None
                
                query_params["website_url"] = domaine
            
            if ville:
                query_params["q_organization_locations"] = ville
            
            try:
                response = requests.post(url, json=query_params, headers=self.headers, timeout=(10, 30))
            except requests.exceptions.Timeout:
                logger.debug(f"⏱️  Timeout Apollo.io pour {nom_entreprise}")
                return None
            except requests.exceptions.ConnectionError:
                logger.debug(f"🔌 Erreur de connexion Apollo.io pour {nom_entreprise}")
                return None
            except requests.exceptions.RequestException as e:
                logger.debug(f"❌ Erreur requête Apollo.io pour {nom_entreprise}: {e}")
                return None
            
            # Ne pas lever d'exception pour 422, juste logger
            if response.status_code == 422:
                logger.debug(f"Apollo.io: Requête non valide pour {nom_entreprise} (422)")
                return None
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                logger.debug(f"❌ Erreur HTTP Apollo.io: {e}")
                return None
            data = response.json()
            
            if "organizations" in data and len(data["organizations"]) > 0:
                org = data["organizations"][0]
                
                entreprise_data = {
                    "id": org.get("id"),
                    "nom_entreprise": org.get("name", nom_entreprise),
                    "site_web": org.get("website_url", site_web),
                    "telephone": org.get("phone_number"),
                    "taille": org.get("estimated_num_employees"),
                    "industrie": org.get("industry"),
                    "revenue": org.get("estimated_annual_revenue"),
                    "adresse": self._formater_adresse(org),
                    "linkedin_entreprise": org.get("linkedin_url"),
                    "twitter": org.get("twitter_url"),
                    "facebook": org.get("facebook_url")
                }
                
                logger.info(f"Entreprise trouvée sur Apollo.io: {entreprise_data['nom_entreprise']}")
                return entreprise_data
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erreur API Apollo.io pour recherche entreprise {nom_entreprise}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche entreprise: {e}")
            return None
    
    def _rechercher_dirigeant(self, organization_id: Optional[str], nom_entreprise: str) -> Optional[Dict[str, Any]]:
        """
        Recherche le dirigeant d'une entreprise.
        
        Args:
            organization_id: ID de l'entreprise sur Apollo.io
            nom_entreprise: Nom de l'entreprise (fallback)
        
        Returns:
            Informations du dirigeant ou None
        """
        try:
            if not organization_id:
                # Essayer une recherche par nom d'entreprise
                return self._rechercher_dirigeant_par_entreprise(nom_entreprise)
            
            url = f"{self.base_url}/mixed_people/search"
            
            # Postes recherchés
            postes_recherches = [
                "ceo", "chief executive officer", "directeur général", "directrice générale",
                "fondateur", "founder", "président", "president", "gérant", "gérante",
                "directeur", "directrice", "manager"
            ]
            
            dirigeant_trouve = None
            
            for poste in postes_recherches:
                query_params = {
                    "api_key": self.api_key,
                    "person_titles": [poste],
                    "organization_id": organization_id,
                    "per_page": 5
                }
                
                try:
                    response = requests.post(url, json=query_params, headers=self.headers, timeout=(10, 30))
                    response.raise_for_status()
                    data = response.json()
                except requests.exceptions.Timeout:
                    logger.debug(f"⏱️  Timeout Apollo.io recherche dirigeant")
                    continue
                except requests.exceptions.ConnectionError:
                    logger.debug(f"🔌 Erreur de connexion Apollo.io recherche dirigeant")
                    continue
                except requests.exceptions.RequestException as e:
                    logger.debug(f"❌ Erreur requête Apollo.io recherche dirigeant: {e}")
                    continue
                
                if "people" in data and len(data["people"]) > 0:
                    personne = data["people"][0]
                    dirigeant_trouve = {
                        "nom": f"{personne.get('first_name', '')} {personne.get('last_name', '')}".strip(),
                        "prenom": personne.get("first_name", ""),
                        "nom_famille": personne.get("last_name", ""),
                        "poste": personne.get("title", poste),
                        "email": personne.get("email"),
                        "telephone": personne.get("phone_numbers", [{}])[0].get("raw_number") if personne.get("phone_numbers") else None,
                        "linkedin": personne.get("linkedin_url"),
                        "twitter": personne.get("twitter_url")
                    }
                    
                    logger.info(f"Dirigeant trouvé sur Apollo.io: {dirigeant_trouve['nom']} ({dirigeant_trouve['poste']})")
                    break
            
            return dirigeant_trouve
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erreur API Apollo.io pour recherche dirigeant: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche dirigeant: {e}")
            return None
    
    def _rechercher_dirigeant_par_entreprise(self, nom_entreprise: str) -> Optional[Dict[str, Any]]:
        """
        Recherche un dirigeant par nom d'entreprise (fallback).
        
        Args:
            nom_entreprise: Nom de l'entreprise
        
        Returns:
            Informations du dirigeant ou None
        """
        try:
            url = f"{self.base_url}/mixed_people/search"
            
            query_params = {
                "api_key": self.api_key,
                "q_keywords": f"{nom_entreprise} CEO",
                "per_page": 3
            }
            
            try:
                response = requests.post(url, json=query_params, headers=self.headers, timeout=(10, 30))
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.Timeout:
                logger.debug(f"⏱️  Timeout Apollo.io recherche dirigeant par entreprise")
                return None
            except requests.exceptions.ConnectionError:
                logger.debug(f"🔌 Erreur de connexion Apollo.io recherche dirigeant par entreprise")
                return None
            except requests.exceptions.RequestException as e:
                logger.debug(f"❌ Erreur requête Apollo.io recherche dirigeant par entreprise: {e}")
                return None
            
            if "people" in data and len(data["people"]) > 0:
                personne = data["people"][0]
                
                # Vérifier que c'est bien lié à l'entreprise
                org_name = personne.get("organization", {}).get("name", "").lower()
                if nom_entreprise.lower()[:5] in org_name or org_name[:5] in nom_entreprise.lower()[:5]:
                    return {
                        "nom": f"{personne.get('first_name', '')} {personne.get('last_name', '')}".strip(),
                        "prenom": personne.get("first_name", ""),
                        "nom_famille": personne.get("last_name", ""),
                        "poste": personne.get("title", "Dirigeant"),
                        "email": personne.get("email"),
                        "telephone": personne.get("phone_numbers", [{}])[0].get("raw_number") if personne.get("phone_numbers") else None,
                        "linkedin": personne.get("linkedin_url")
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de la recherche dirigeant par entreprise: {e}")
            return None
    
    def _formater_adresse(self, org: Dict[str, Any]) -> Optional[str]:
        """Formate l'adresse de l'entreprise."""
        try:
            address_parts = []
            
            street = org.get("street_address")
            city = org.get("city")
            state = org.get("state")
            postal_code = org.get("postal_code")
            country = org.get("country")
            
            if street:
                address_parts.append(street)
            if city:
                address_parts.append(city)
            if state:
                address_parts.append(state)
            if postal_code:
                address_parts.append(postal_code)
            if country:
                address_parts.append(country)
            
            return ", ".join(address_parts) if address_parts else None
            
        except Exception:
            return None

