"""
Module de scoring des prospects pour prioriser les meilleurs prospects.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ProspectScoring:
    """Système de scoring pour évaluer la qualité d'un prospect."""
    
    def __init__(self, service_propose: str = ""):
        """
        Initialise le système de scoring.
        
        Args:
            service_propose: Service proposé (pour adapter les poids du scoring)
        """
        self.service_propose = service_propose.lower() if service_propose else ""
        self._determiner_poids_par_service()
    
    def _determiner_poids_par_service(self):
        """Détermine les poids de scoring selon le service proposé."""
        # Poids par défaut (équilibrés)
        self.poids = {
            "email": 20,
            "telephone": 15,
            "linkedin": 10,
            "site_web": 10,
            "note_google": 10,
            "nb_avis": 5,
            "taille_entreprise": 10,
            "industrie_pertinente": 15,
            "technologies_detectees": 5
        }
        
        # Ajustement selon le service proposé
        if any(mot in self.service_propose for mot in ["site web", "website", "internet", "web", "développement", "développeur"]):
            # Services web/développement : site_web et technologies sont critiques
            self.poids["site_web"] = 15
            self.poids["technologies_detectees"] = 15
            self.poids["email"] = 18
            self.poids["note_google"] = 8
            logger.debug("Poids ajustés pour service web/développement")
            
        elif any(mot in self.service_propose for mot in ["marketing", "communication", "publicité", "seo", "réseaux sociaux"]):
            # Services marketing : note Google et avis sont critiques
            self.poids["note_google"] = 20
            self.poids["nb_avis"] = 15
            self.poids["linkedin"] = 15
            self.poids["email"] = 20
            logger.debug("Poids ajustés pour service marketing/communication")
            
        elif any(mot in self.service_propose for mot in ["conseil", "consulting", "accompagnement", "audit"]):
            # Services de conseil : LinkedIn et taille entreprise sont critiques
            self.poids["linkedin"] = 25
            self.poids["taille_entreprise"] = 20
            self.poids["industrie_pertinente"] = 20
            self.poids["email"] = 18
            logger.debug("Poids ajustés pour service conseil/consulting")
            
        elif any(mot in self.service_propose for mot in ["commerce", "e-commerce", "boutique", "vente"]):
            # Services e-commerce : note Google et avis sont critiques
            self.poids["note_google"] = 20
            self.poids["nb_avis"] = 15
            self.poids["telephone"] = 18
            self.poids["site_web"] = 12
            logger.debug("Poids ajustés pour service e-commerce")
    
    def _analyser_site_web(self, site_web: str, technologies: list) -> Dict[str, Any]:
        """
        Analyse le site web pour détecter des signaux d'opportunité.
        
        Args:
            site_web: URL du site web
            technologies: Liste des technologies détectées
        
        Returns:
            Dictionnaire avec signaux détectés
        """
        signaux = {
            "pas_de_site": False,
            "site_obsolète": False,
            "cms_ancien": False,
            "site_moderne": False,
            "opportunité_refonte": False
        }
        
        if not site_web or not site_web.startswith("http"):
            signaux["pas_de_site"] = True
            return signaux
        
        techs_lower = [t.lower() for t in technologies] if technologies else []
        
        # Détecter CMS anciens = opportunité
        cms_anciens = ["wordpress", "joomla", "drupal", "prestashop"]
        if any(cms in techs_lower for cms in cms_anciens):
            signaux["cms_ancien"] = True
            signaux["opportunité_refonte"] = True
        
        # Détecter technologies modernes
        techs_modernes = ["react", "vue", "angular", "next.js"]
        if any(tech in techs_lower for tech in techs_modernes):
            signaux["site_moderne"] = True
        
        return signaux
    
    def calculer_score(self, prospect: Dict[str, Any]) -> int:
        """
        Calcule le score total d'un prospect (0-100) avec analyse intelligente.
        
        Args:
            prospect: Dictionnaire contenant les données du prospect
        
        Returns:
            Score total entre 0 et 100
        """
        score_total = 0
        
        # Analyse préalable du site web
        site_web = prospect.get("site_web", "")
        technologies_str = prospect.get("technologies", "")
        if technologies_str:
            if isinstance(technologies_str, str):
                technologies = [t.strip() for t in technologies_str.split(",") if t.strip()]
            else:
                technologies = technologies_str if isinstance(technologies_str, list) else []
        else:
            technologies = []
        
        signaux_site = self._analyser_site_web(site_web, technologies)
        
        # 1. Email (20 points max)
        email = prospect.get("email")
        email_status = prospect.get("email_status")
        if email and email_status == "valid":
            score_total += self.poids["email"]
        elif email and email_status == "catch-all":
            score_total += self.poids["email"] * 0.7  # 70% des points
        elif email:
            score_total += self.poids["email"] * 0.5  # 50% des points si non vérifié
        elif not email:
            score_total += 0
        
        # 2. Téléphone (15 points max)
        telephone = prospect.get("telephone")
        if telephone:
            score_total += self.poids["telephone"]
        
        # 3. LinkedIn entreprise (10-25 points max selon service)
        linkedin = prospect.get("linkedin_entreprise")
        if linkedin:
            score_total += self.poids["linkedin"]
        
        # 4. Site web (10-15 points max) - Analyse intelligente selon service_propose
        service_lower = self.service_propose.lower()
        
        if signaux_site["pas_de_site"]:
            # Pas de site = GRANDE opportunité pour services web
            if any(mot in service_lower for mot in ["web", "site", "développement", "création site"]):
                score_total += self.poids["site_web"] + 10  # Bonus majeur : pas de site = besoin évident
            else:
                score_total += 0  # Pas de site = moins intéressant pour autres services
        elif site_web and site_web.startswith("http"):
            score_total += self.poids["site_web"]
            
            # Analyse selon le service proposé
            if any(mot in service_lower for mot in ["web", "site", "développement", "création site"]):
                # Services web : analyser l'état du site
                if signaux_site["opportunité_refonte"] or signaux_site["cms_ancien"]:
                    score_total += 8  # Bonus majeur : site obsolète = opportunité de refonte
                elif signaux_site["site_moderne"]:
                    score_total += 2  # Site moderne = moins d'opportunité mais bon signe
                elif not technologies:
                    score_total += 5  # Pas de technologies détectées = peut-être site statique/obsolète
            
            # Services marketing : site existant = bon signe
            elif any(mot in service_lower for mot in ["marketing", "communication", "seo", "visibilité"]):
                if signaux_site["site_moderne"]:
                    score_total += 4  # Site moderne = entreprise digitale = bon client
                elif technologies:
                    score_total += 3  # Technologies présentes = bon signe
                else:
                    score_total += 2  # Site basique = peut-être besoin d'aide marketing
        
        # 5. Note Google (8-20 points max selon service)
        note_google = prospect.get("note_google")
        if note_google:
            try:
                note = float(note_google)
                if note >= 4.5:
                    score_total += self.poids["note_google"]
                elif note >= 4.0:
                    score_total += self.poids["note_google"] * 0.8
                elif note >= 3.5:
                    score_total += self.poids["note_google"] * 0.6
                else:
                    score_total += self.poids["note_google"] * 0.4
            except (ValueError, TypeError):
                pass
        
        # 6. Nombre d'avis (5-15 points max)
        nb_avis = prospect.get("nb_avis")
        if nb_avis:
            try:
                nb = int(nb_avis)
                if nb >= 50:
                    score_total += self.poids["nb_avis"]
                elif nb >= 20:
                    score_total += self.poids["nb_avis"] * 0.8
                elif nb >= 10:
                    score_total += self.poids["nb_avis"] * 0.6
                else:
                    score_total += self.poids["nb_avis"] * 0.4
            except (ValueError, TypeError):
                pass
        
        # 7. Taille entreprise (10-20 points max)
        taille = prospect.get("taille_entreprise")
        if taille:
            taille_lower = str(taille).lower()
            if any(mot in taille_lower for mot in ["11-50", "51-200", "201-500"]):
                score_total += self.poids["taille_entreprise"]
            elif any(mot in taille_lower for mot in ["1-10", "2-10"]):
                score_total += self.poids["taille_entreprise"] * 0.8
            elif any(mot in taille_lower for mot in ["501-1000", "1001-5000"]):
                score_total += self.poids["taille_entreprise"] * 0.7  # Plus grandes = moins intéressantes pour certains services
            else:
                score_total += self.poids["taille_entreprise"] * 0.6
        
        # 8. Industrie pertinente (15-20 points max)
        industrie = prospect.get("industrie", "").lower()
        service_lower = self.service_propose.lower()
        if industrie:
            # Score selon pertinence avec le service proposé
            if any(mot in service_lower for mot in ["web", "site", "développement"]):
                if any(mot in industrie for mot in ["commerce", "retail", "restaurant", "hotel", "service"]):
                    score_total += self.poids["industrie_pertinente"]
                else:
                    score_total += self.poids["industrie_pertinente"] * 0.7
            elif any(mot in service_lower for mot in ["marketing", "communication"]):
                if any(mot in industrie for mot in ["commerce", "retail", "restaurant", "service", "professional"]):
                    score_total += self.poids["industrie_pertinente"]
                else:
                    score_total += self.poids["industrie_pertinente"] * 0.8
            else:
                score_total += self.poids["industrie_pertinente"] * 0.9  # Score moyen par défaut
        
        # 9. Technologies détectées (5-15 points max selon service) - Analyse intelligente
        technologies = prospect.get("technologies", "")
        if technologies:
            if isinstance(technologies, str):
                techs_list = [t.strip() for t in technologies.split(",") if t.strip()]
            elif isinstance(technologies, list):
                techs_list = technologies
            else:
                techs_list = []
        else:
            techs_list = []
        
        if techs_list:
            nb_techno = len(techs_list)
            service_lower = self.service_propose.lower()
            
            if any(mot in service_lower for mot in ["web", "site", "développement", "création site"]):
                # Pour services web : analyser les technologies
                # CMS obsolètes = opportunité de refonte
                cms_anciens = ["wordpress", "prestashop", "joomla", "drupal"]
                if any(tech.lower() in cms_anciens for tech in techs_list):
                    score_total += self.poids["technologies_detectees"]  # Opportunité de modernisation
                # Technologies modernes = peut-être moins besoin, mais bon signe
                elif any(tech.lower() in ["react", "vue", "angular"] for tech in techs_list):
                    score_total += self.poids["technologies_detectees"] * 0.6  # Moins d'opportunité
                else:
                    score_total += self.poids["technologies_detectees"] * 0.8
            else:
                # Pour autres services : avoir des technologies = entreprise digitale = bon signe
                score_total += self.poids["technologies_detectees"] * 0.9
        
        # Normaliser le score entre 0 et 100
        score_total = min(100, max(0, score_total))
        
        return int(score_total)
    
    def obtenir_categorie_score(self, score: int) -> str:
        """
        Retourne la catégorie d'un score.
        
        Args:
            score: Score entre 0 et 100
        
        Returns:
            Catégorie : "excellent", "bon", "moyen", "faible"
        """
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "bon"
        elif score >= 40:
            return "moyen"
        else:
            return "faible"

