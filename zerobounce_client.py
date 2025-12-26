"""
Module client pour l'API ZeroBounce - Vérification d'emails.
"""
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ZeroBounceClient:
    """Client pour interroger l'API ZeroBounce."""
    
    def __init__(self, api_key: str):
        """
        Initialise le client ZeroBounce.
        
        Args:
            api_key: Clé API ZeroBounce
        """
        self.api_key = api_key
        self.base_url = "https://api.zerobounce.net/v2"
    
    def verifier_email(self, email: str, ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Vérifie la validité d'un email avec ZeroBounce.
        
        Args:
            email: Email à vérifier
            ip_address: Adresse IP de l'utilisateur (optionnel, pour meilleure précision)
        
        Returns:
            Dictionnaire contenant:
            - status: "valid", "invalid", "catch-all", "unknown", "spam", "do_not_mail", "abuse", "role"
            - sub_status: Détails supplémentaires
            - account: Nom du compte (si trouvé)
            - domain: Domaine
            - did_you_mean: Suggestion de correction (si email invalide)
            - result: Résultat détaillé
            - credits_remaining: Crédits restants
        """
        try:
            url = f"{self.base_url}/validate"
            params = {
                "api_key": self.api_key,
                "email": email
            }
            
            if ip_address:
                params["ip_address"] = ip_address
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            status = data.get("status", "unknown")
            
            # Convertir les crédits en entiers
            credits_remaining = data.get("credits_remaining", 0)
            credits_used = data.get("credits_used", 0)
            try:
                credits_remaining = int(credits_remaining) if credits_remaining else 0
            except (ValueError, TypeError):
                credits_remaining = 0
            try:
                credits_used = int(credits_used) if credits_used else 0
            except (ValueError, TypeError):
                credits_used = 0
            
            logger.info(f"Email {email} vérifié: {status} (crédits restants: {credits_remaining})")
            
            return {
                "status": status,
                "sub_status": data.get("sub_status", ""),
                "account": data.get("account", ""),
                "domain": data.get("domain", ""),
                "did_you_mean": data.get("did_you_mean"),
                "result": data.get("result", "unknown"),
                "credits_remaining": credits_remaining,
                "credits_used": credits_used
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la vérification ZeroBounce pour {email}: {e}")
            return {
                "status": "unknown",
                "error": str(e),
                "credits_remaining": 0
            }
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la vérification ZeroBounce: {e}")
            return {
                "status": "unknown",
                "error": str(e),
                "credits_remaining": 0
            }
    
    def est_email_valide(self, email: str, ip_address: Optional[str] = None) -> bool:
        """
        Vérifie si un email est valide (méthode simplifiée).
        
        Args:
            email: Email à vérifier
            ip_address: Adresse IP (optionnel)
        
        Returns:
            True si l'email est valide, False sinon
        """
        resultat = self.verifier_email(email, ip_address)
        status = resultat.get("status", "unknown")
        
        # Emails considérés comme valides
        status_valides = ["valid", "catch-all"]
        
        return status in status_valides
    
    def obtenir_credits(self) -> int:
        """
        Récupère le nombre de crédits ZeroBounce restants.
        
        Returns:
            Nombre de crédits restants ou 0 en cas d'erreur
        """
        try:
            url = f"{self.base_url}/getcredits"
            params = {
                "api_key": self.api_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            credits = data.get("Credits", 0)
            # Convertir en entier si c'est une chaîne
            try:
                credits = int(credits) if credits else 0
            except (ValueError, TypeError):
                credits = 0
            logger.info(f"Crédits ZeroBounce restants: {credits}")
            return credits
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des crédits ZeroBounce: {e}")
            return 0

