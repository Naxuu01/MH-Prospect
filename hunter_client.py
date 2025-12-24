"""
Module client pour l'API Hunter.io - Recherche d'emails et d'informations de dirigeants.
"""
import requests
import logging
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HunterClient:
    """Client pour interroger l'API Hunter.io."""
    
    def __init__(self, api_key: str):
        """
        Initialise le client Hunter.io.
        
        Args:
            api_key: Clé API Hunter.io
        """
        self.api_key = api_key
        self.base_url = "https://api.hunter.io/v2"
    
    def trouver_email_dirigeant(self, site_web: str, nom_entreprise: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """
        Trouve l'email du dirigeant (CEO/Fondateur) d'une entreprise.
        Combine Hunter.io et scraping direct du site web.
        
        Args:
            site_web: URL du site web de l'entreprise
            nom_entreprise: Nom de l'entreprise
        
        Returns:
            Tuple (email, infos_dirigeant) où infos_dirigeant contient nom et poste
        """
        try:
            # Méthode 1: Scraping direct du site web (prioritaire si trouvé)
            logger.info(f"Scraping du site web pour trouver le dirigeant: {site_web}")
            dirigeant_scrape, email_scrape = self._scraper_dirigeant_site_web(site_web)
            
            if dirigeant_scrape and email_scrape:
                logger.info(f"Dirigeant trouvé via scraping: {dirigeant_scrape['nom']} ({dirigeant_scrape['poste']})")
                return email_scrape, dirigeant_scrape
            
            # Méthode 2: Domain Search via Hunter.io
            domain = self._extraire_domaine(site_web)
            if domain:
                email, dirigeant_info = self._chercher_dirigeant_par_domaine(domain, nom_entreprise)
                
                if email and dirigeant_info:
                    logger.info(f"Dirigeant trouvé via Hunter.io: {dirigeant_info['nom']} ({dirigeant_info['poste']})")
                    return email, dirigeant_info
                
                # Si on a un email mais pas de dirigeant, utiliser le dirigeant du scraping s'il existe
                if email and dirigeant_scrape:
                    return email, dirigeant_scrape
                
                if email:
                    return email, None
            
            # Méthode 3: Si pas de résultat, chercher un email générique
            logger.warning(f"Aucun email de dirigeant trouvé pour {nom_entreprise}, recherche d'email générique...")
            email_generique = self._chercher_email_generique(site_web)
            
            # Si on a trouvé un dirigeant via scraping mais pas d'email, retourner le dirigeant quand même
            if email_generique and dirigeant_scrape:
                return email_generique, dirigeant_scrape
            
            return email_generique, dirigeant_scrape if dirigeant_scrape else None
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'email pour {site_web}: {e}")
            return None, None
    
    def _chercher_dirigeant_par_domaine(self, domain: str, nom_entreprise: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """
        Cherche un dirigeant via l'API Hunter.io.
        
        Args:
            domain: Domaine de l'entreprise
            nom_entreprise: Nom de l'entreprise
        
        Returns:
            Tuple (email, infos_dirigeant)
        """
        try:
            # Domain Search
            url = f"{self.base_url}/domain-search"
            params = {
                "domain": domain,
                "api_key": self.api_key,
                "seniority": "executive",  # Hunter.io n'accepte qu'une valeur à la fois
                "limit": 10
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("data") and "emails" in data["data"]:
                emails = data["data"]["emails"]
                
                # Chercher un CEO/Fondateur/Directeur
                postes_recherches = ["ceo", "fondateur", "founder", "directeur", "président", "president", "manager", "gérant"]
                
                for email_info in emails:
                    poste = email_info.get("position", "").lower()
                    prenom = email_info.get("first_name", "")
                    nom = email_info.get("last_name", "")
                    
                    for poste_recherche in postes_recherches:
                        if poste_recherche in poste:
                            email = email_info.get("value")
                            dirigeant_info = {
                                "nom": f"{prenom} {nom}".strip(),
                                "poste": email_info.get("position", "")
                            }
                            logger.info(f"Email de dirigeant trouvé: {email} ({dirigeant_info['nom']} - {dirigeant_info['poste']})")
                            return email, dirigeant_info
                
                # Si aucun dirigeant trouvé, prendre le premier email avec un nom
                for email_info in emails:
                    if email_info.get("first_name") and email_info.get("last_name"):
                        email = email_info.get("value")
                        dirigeant_info = {
                            "nom": f"{email_info.get('first_name')} {email_info.get('last_name')}".strip(),
                            "poste": email_info.get("position", "Contact")
                        }
                        return email, dirigeant_info
            
            return None, None
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erreur API Hunter.io pour {domain}: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche Hunter: {e}")
            return None, None
    
    def _chercher_email_generique(self, site_web: str) -> Optional[str]:
        """
        Cherche un email générique (contact@, info@, etc.) sur le site web.
        
        Args:
            site_web: URL du site web
        
        Returns:
            Email générique trouvé ou None
        """
        try:
            # Scraper le site pour trouver des emails
            response = requests.get(site_web, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            texte = soup.get_text()
            
            # Patterns d'emails génériques
            pattern = r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
            emails = re.findall(pattern, texte)
            
            # Filtrer les emails génériques préférés
            emails_preferes = ["contact", "info", "hello", "bonjour", "commercial"]
            
            for email in emails:
                local_part = email.split("@")[0].lower()
                if any(pref in local_part for pref in emails_preferes):
                    logger.info(f"Email générique trouvé: {email}")
                    return email
            
            # Si aucun email préféré, retourner le premier email valide du domaine
            domaine = self._extraire_domaine(site_web)
            if domaine:
                for email in emails:
                    if domaine in email:
                        logger.info(f"Email du domaine trouvé: {email}")
                        return email
            
            return None
            
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche d'email générique sur {site_web}: {e}")
            return None
    
    def _scraper_dirigeant_site_web(self, site_web: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
        """
        Scrape le site web pour trouver les informations d'un contact (dirigeant ou responsable).
        Visite les pages "À propos", "Équipe", "Contact", etc.
        Cherche aussi les profils LinkedIn directement sur le site.
        
        Args:
            site_web: URL du site web
        
        Returns:
            Tuple (contact_info, email) où contact_info contient nom, poste et linkedin
        """
        try:
            if not site_web.startswith("http"):
                site_web = "https://" + site_web
            
            # Pages à visiter pour trouver les contacts
            pages_a_visiter = [
                "",  # Page d'accueil
                "/a-propos", "/about", "/about-us", "/qui-sommes-nous", "/qui-sommes-nous/",
                "/equipe", "/team", "/equipe/", "/team/",
                "/contact", "/nous-contacter", "/contactez-nous", "/contact-us",
                "/management", "/direction", "/leadership"
            ]
            
            base_url = site_web.rstrip('/')
            postes_recherches = [
                "directeur général", "directrice générale", "dg", "ceo", "chief executive officer",
                "fondateur", "fondatrice", "founder", "président", "présidente", "president",
                "gérant", "gérante", "manager", "directeur", "directrice", "pdg",
                "propriétaire", "owner", "responsable", "head of"
            ]
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            meilleur_contact = None
            meilleur_email = None
            
            # PRIORITÉ 0: Chercher directement dans les pages de contact (emails + noms)
            # Les pages de contact contiennent souvent des contacts facilement extractibles
            pages_contact = ["/contact", "/nous-contacter", "/contactez-nous", "/contact-us", "/contakt"]
            for page_contact in pages_contact:
                try:
                    url_contact = f"{base_url}{page_contact}"
                    response = requests.get(url_contact, timeout=15, headers=headers, allow_redirects=True)
                    
                    if response.status_code == 200:
                        soup_contact = BeautifulSoup(response.text, 'html.parser')
                        # Chercher directement des contacts (emails + noms) sur la page de contact
                        contact_direct = self._extraire_contact_depuis_page_contact(soup_contact)
                        if contact_direct:
                            logger.info(f"✅ Contact trouvé directement sur page contact {url_contact}: {contact_direct.get('nom', 'Contact')}")
                            return contact_direct, contact_direct.get('email')
                except:
                    continue
            
            for page in pages_a_visiter:
                try:
                    url = f"{base_url}{page}" if page else base_url
                    response = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
                    
                    if response.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    texte_complet = soup.get_text().lower()
                    
                    # PRIORITÉ 1: Chercher des contacts avec LinkedIn (le plus fiable)
                    contact_linkedin = self._chercher_contacts_linkedin_ameliore(soup)
                    if contact_linkedin:
                        email = self._extraire_email_du_texte(soup, contact_linkedin["nom"])
                        logger.info(f"✅ Contact LinkedIn trouvé sur {url}: {contact_linkedin['nom']} - {contact_linkedin.get('poste', 'Contact')}")
                        return contact_linkedin, email
                    
                    # PRIORITÉ 2: Chercher directement des emails avec noms sur toutes les pages
                    # (pas seulement dans des structures spécifiques)
                    contact_email = self._extraire_contact_par_email(soup)
                    if contact_email:
                        linkedin = self._chercher_linkedin_contact(soup, contact_email["nom"])
                        if linkedin:
                            contact_email["linkedin"] = linkedin
                        if not meilleur_contact:
                            meilleur_contact = contact_email
                            meilleur_email = contact_email.get("email")
                    
                    # PRIORITÉ 2b: Chercher dans les structures HTML courantes (cards, team members)
                    contact_structure = self._chercher_contact_dans_structures(soup)
                    if contact_structure:
                        email = self._extraire_email_du_texte(soup, contact_structure["nom"])
                        linkedin = self._chercher_linkedin_contact(soup, contact_structure["nom"])
                        if linkedin:
                            contact_structure["linkedin"] = linkedin
                        if not meilleur_contact:
                            meilleur_contact = contact_structure
                            meilleur_email = email
                    
                    # PRIORITÉ 3: Chercher les patterns de dirigeants dans le texte
                    for poste_recherche in postes_recherches:
                        if poste_recherche in texte_complet:
                            dirigeant = self._extraire_nom_dirigeant_texte_ameliore(soup, poste_recherche)
                            if dirigeant:
                                email = self._extraire_email_du_texte(soup, dirigeant["nom"])
                                linkedin = self._chercher_linkedin_contact(soup, dirigeant["nom"])
                                if linkedin:
                                    dirigeant["linkedin"] = linkedin
                                if not meilleur_contact:
                                    meilleur_contact = dirigeant
                                    meilleur_email = email
                    
                    # PRIORITÉ 4: Chercher dans les balises spécifiques
                    dirigeant_balises = self._chercher_dirigeant_balises(soup, postes_recherches)
                    if dirigeant_balises:
                        email = self._extraire_email_du_texte(soup, dirigeant_balises["nom"])
                        linkedin = self._chercher_linkedin_contact(soup, dirigeant_balises["nom"])
                        if linkedin:
                            dirigeant_balises["linkedin"] = linkedin
                        if not meilleur_contact:
                            meilleur_contact = dirigeant_balises
                            meilleur_email = email
                    
                except requests.exceptions.RequestException:
                    continue
                except Exception as e:
                    logger.debug(f"Erreur lors du scraping de {url}: {e}")
                    continue
            
            # Retourner le meilleur contact trouvé
            if meilleur_contact:
                logger.info(f"✅ Contact trouvé: {meilleur_contact['nom']} - {meilleur_contact.get('poste', 'Contact')}")
                return meilleur_contact, meilleur_email
            
            return None, None
            
        except Exception as e:
            logger.warning(f"Erreur lors du scraping du site web {site_web}: {e}")
            return None, None
    
    def _extraire_nom_dirigeant_texte(self, soup: BeautifulSoup, texte_complet: str, poste: str) -> Optional[Dict[str, str]]:
        """
        Extrait le nom d'un dirigeant depuis le texte autour d'un poste.
        
        Args:
            soup: BeautifulSoup object
            texte_complet: Texte complet en minuscules
            poste: Poste recherché
        
        Returns:
            Dict avec nom et poste ou None
        """
        try:
            # Chercher dans les éléments HTML pour trouver le nom proche du poste
            elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span', 'strong', 'b'])
            
            for element in elements:
                texte_elem = element.get_text().lower()
                if poste in texte_elem:
                    # Essayer d'extraire un nom (généralement en majuscules ou titre)
                    nom_complet = element.get_text().strip()
                    
                    # Pattern pour trouver un nom (prénom + nom, généralement 2-4 mots)
                    mots = nom_complet.split()
                    if 2 <= len(mots) <= 4:
                        # Vérifier que ça ressemble à un nom (contient des lettres, pas seulement le poste)
                        nom_candidat = " ".join(mots[:2]).strip()
                        if len(nom_candidat) > 5 and nom_candidat.lower() != poste.lower():
                            # Trouver le poste réel dans le texte
                            poste_reel = poste
                            for mot in mots:
                                if any(p in mot.lower() for p in ["directeur", "ceo", "fondateur", "président", "gérant"]):
                                    poste_reel = mot
                                    break
                            
                            return {
                                "nom": nom_candidat,
                                "poste": poste_reel.title()
                            }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'extraction du nom: {e}")
            return None
    
    def _chercher_dirigeant_balises(self, soup: BeautifulSoup, postes_recherches: list) -> Optional[Dict[str, str]]:
        """
        Cherche un dirigeant dans les balises HTML spécifiques.
        
        Args:
            soup: BeautifulSoup object
            postes_recherches: Liste des postes à rechercher
        
        Returns:
            Dict avec nom et poste ou None
        """
        try:
            # Chercher dans les sections "team", "about", etc.
            sections = soup.find_all(['section', 'div'], class_=re.compile(r'team|about|equipe|management|direction', re.I))
            
            for section in sections:
                texte_section = section.get_text().lower()
                
                for poste in postes_recherches:
                    if poste in texte_section:
                        # Chercher les noms dans cette section (généralement en strong, h3, etc.)
                        noms = section.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                        
                        for nom_elem in noms:
                            nom_texte = nom_elem.get_text().strip()
                            mots = nom_texte.split()
                            
                            # Un nom de dirigeant fait généralement 2-3 mots
                            if 2 <= len(mots) <= 3 and len(nom_texte) > 5:
                                # Vérifier qu'on est dans un contexte de dirigeant
                                parent_text = nom_elem.find_parent().get_text().lower() if nom_elem.find_parent() else ""
                                if any(p in parent_text for p in postes_recherches):
                                    return {
                                        "nom": nom_texte,
                                        "poste": poste.title()
                                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de la recherche dans les balises: {e}")
            return None
    
    def _extraire_email_du_texte(self, soup: BeautifulSoup, nom_dirigeant: str) -> Optional[str]:
        """
        Extrait l'email associé à un nom de dirigeant depuis le HTML.
        
        Args:
            soup: BeautifulSoup object
            nom_dirigeant: Nom du dirigeant
        
        Returns:
            Email trouvé ou None
        """
        try:
            # Chercher tous les emails dans la page
            texte_complet = soup.get_text()
            emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', texte_complet)
            
            if not emails:
                return None
            
            # Essayer de trouver l'email associé au nom (chercher près du nom dans le HTML)
            mots_nom = nom_dirigeant.lower().split()
            if len(mots_nom) >= 2:
                prenom = mots_nom[0]
                nom = mots_nom[-1]
                
                # Chercher un email qui contient le prénom ou le nom
                for email in emails:
                    email_lower = email.lower()
                    if prenom[:3] in email_lower or nom[:4] in email_lower:
                        return email
                
                # Si pas de match exact, prendre le premier email professionnel (pas info@, contact@, etc.)
                for email in emails:
                    email_lower = email.lower()
                    if not any(generic in email_lower for generic in ["info@", "contact@", "hello@", "noreply@", "no-reply@", "webmaster@"]):
                        return email
            
            # Si pas de nom donné, retourner le premier email non générique trouvé
            if not nom_dirigeant:
                for email in emails:
                    email_lower = email.lower()
                    if not any(generic in email_lower for generic in ["info@", "contact@", "hello@", "noreply@", "no-reply@", "webmaster@", "support@"]):
                        return email
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'extraction de l'email: {e}")
            return None
    
    def _chercher_contacts_linkedin_ameliore(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Cherche des liens LinkedIn avec extraction améliorée du nom et poste.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Dict avec nom, poste et linkedin ou None
        """
        try:
            # Chercher tous les liens LinkedIn personnels (pas les pages company)
            linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com/in/[^/]+/?$', re.I))
            
            if not linkedin_links:
                return None
            
            for link in linkedin_links[:5]:  # Examiner jusqu'à 5 liens
                linkedin_url = link.get('href', '').strip()
                
                # Nettoyer l'URL (enlever les paramètres)
                if '?' in linkedin_url:
                    linkedin_url = linkedin_url.split('?')[0]
                
                if not linkedin_url.startswith('http'):
                    linkedin_url = 'https://' + linkedin_url
                
                # Chercher le nom dans le contexte du lien
                contexte = self._extraire_contexte_linkedin(link)
                
                if contexte and contexte.get("nom"):
                    return {
                        "nom": contexte["nom"],
                        "poste": contexte.get("poste", "Contact"),
                        "linkedin": linkedin_url
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de la recherche LinkedIn améliorée: {e}")
            return None
    
    def _extraire_contexte_linkedin(self, link_element) -> Optional[Dict[str, str]]:
        """
        Extrait le nom et le poste depuis le contexte autour d'un lien LinkedIn.
        
        Args:
            link_element: Élément BeautifulSoup du lien LinkedIn
        
        Returns:
            Dict avec nom et poste ou None
        """
        try:
            # Chercher dans le texte du lien
            texte_lien = link_element.get_text().strip()
            
            # Chercher dans le parent immédiat
            parent = link_element.parent
            if parent:
                texte_parent = parent.get_text().strip()
                
                # Chercher dans la structure HTML courante : nom dans h3/h4/strong, poste dans p/span
                # Pattern 1: Card de team member
                nom_elem = parent.find(['h3', 'h4', 'h5', 'strong', 'b'])
                poste_elem = parent.find(['p', 'span', 'div'], class_=re.compile(r'role|title|poste|position', re.I))
                
                if nom_elem:
                    nom = nom_elem.get_text().strip()
                    # Nettoyer le nom (enlever les caractères spéciaux)
                    nom = re.sub(r'[^\w\s\-\.]', '', nom).strip()
                    mots_nom = nom.split()
                    
                    if 2 <= len(mots_nom) <= 4:
                        nom_propre = " ".join(mots_nom[:2])
                        
                        # Trouver le poste
                        poste = None
                        if poste_elem:
                            poste = poste_elem.get_text().strip()
                        else:
                            # Chercher dans les siblings ou les enfants
                            for sibling in parent.find_all(['p', 'span', 'div']):
                                texte = sibling.get_text().strip().lower()
                                if any(mot in texte for mot in ["directeur", "ceo", "fondateur", "président", 
                                                                 "gérant", "manager", "responsable", "owner"]):
                                    poste = sibling.get_text().strip()
                                    break
                        
                        return {
                            "nom": nom_propre,
                            "poste": poste or "Contact"
                        }
                
                # Pattern 2: Texte simple avec nom et poste
                if not texte_lien or len(texte_lien) < 3:
                    # Chercher dans les siblings
                    for sibling in parent.find_next_siblings(['div', 'p', 'span']):
                        texte_sibling = sibling.get_text().strip()
                        mots = texte_sibling.split()
                        if 2 <= len(mots) <= 5:
                            # Vérifier si ça ressemble à un nom + poste
                            if any(mot.lower() in ["directeur", "ceo", "fondateur", "président", 
                                                    "gérant", "manager", "responsable"] for mot in mots):
                                nom_candidat = " ".join(mots[:2])
                                poste_candidat = " ".join(mots[2:]) if len(mots) > 2 else "Contact"
                                return {
                                    "nom": nom_candidat,
                                    "poste": poste_candidat
                                }
                
                # Pattern 3: Extraire depuis le texte du parent si simple
                if texte_parent and len(texte_parent) < 100:
                    mots = texte_parent.split()
                    if 2 <= len(mots) <= 6:
                        # Chercher un nom (mots en majuscule ou titre)
                        nom_candidat = None
                        for i in range(len(mots) - 1):
                            if mots[i][0].isupper() and mots[i+1][0].isupper():
                                nom_candidat = f"{mots[i]} {mots[i+1]}"
                                break
                        
                        if nom_candidat:
                            return {
                                "nom": nom_candidat,
                                "poste": "Contact"
                            }
            
            # Fallback: utiliser le texte du lien si ça ressemble à un nom
            if texte_lien:
                mots = texte_lien.split()
                if 2 <= len(mots) <= 3 and all(mot[0].isupper() for mot in mots):
                    return {
                        "nom": " ".join(mots[:2]),
                        "poste": "Contact"
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'extraction du contexte LinkedIn: {e}")
            return None
    
    def _extraire_contact_par_email(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Extrait un contact en cherchant d'abord les emails, puis les noms associés.
        Approche plus large : trouve n'importe quel contact, pas seulement les dirigeants.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Dict avec nom, email et poste (optionnel) ou None
        """
        try:
            # 1. Chercher tous les emails sur la page
            texte_complet = soup.get_text()
            emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', texte_complet)
            
            if not emails:
                return None
            
            # Filtrer les emails génériques (mais être moins restrictif)
            emails_pertinents = []
            for email in emails:
                email_lower = email.lower()
                # Exclure vraiment génériques, mais garder contact@ si c'est le seul
                if not any(generic in email_lower for generic in 
                    ["noreply@", "no-reply@", "webmaster@", "support@", "sales@", "admin@", "automated@"]):
                    emails_pertinents.append(email)
            
            if not emails_pertinents:
                # Prendre le premier email même s'il est générique
                emails_pertinents = [emails[0]]
            
            email_trouve = emails_pertinents[0]
            
            # 2. Chercher un nom près de cet email dans le HTML
            nom_trouve = None
            
            # Chercher l'élément qui contient cet email
            for email in emails_pertinents[:3]:  # Essayer les 3 premiers
                # Chercher dans le HTML
                email_pattern = re.compile(re.escape(email), re.I)
                elements = soup.find_all(string=email_pattern)
                
                for elem_text in elements:
                    # Chercher dans le parent et les éléments voisins
                    parent = elem_text.parent
                    if not parent:
                        continue
                    
                    # Chercher dans un rayon de 200 caractères autour de l'email
                    try:
                        # Obtenir le texte du parent et de ses siblings proches
                        contexte_elem = parent
                        for _ in range(3):  # Remonter jusqu'à 3 niveaux
                            parent_text = contexte_elem.get_text()
                            
                            # Pattern pour nom (2-4 mots, majuscules)
                            pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b')
                            matches = pattern.findall(parent_text)
                            
                            for match in matches[:5]:
                                mots = match.split()
                                # Vérifier que c'est un vrai nom
                                if 2 <= len(mots) <= 4 and len(match) > 5:
                                    # Vérifier que ce n'est pas un mot répété
                                    if mots[0].lower() != mots[-1].lower():
                                        # Vérifier que ce n'est pas juste "Contact Nous" ou similaire
                                        if not any(common in match.lower() for common in 
                                            ["contact nous", "nous contacter", "qui sommes", "about us"]):
                                            nom_trouve = match
                                            break
                            
                            if nom_trouve:
                                break
                            
                            contexte_elem = contexte_elem.parent
                            if not contexte_elem:
                                break
                    except:
                        continue
                    
                    if nom_trouve:
                        break
                
                if nom_trouve:
                    break
            
            # 3. Si pas de nom trouvé, essayer d'extraire depuis l'email
            if not nom_trouve and email_trouve:
                partie_locale = email_trouve.split('@')[0].lower()
                if '.' in partie_locale or '_' in partie_locale:
                    parties = re.split('[._]', partie_locale)
                    if len(parties) >= 2:
                        # Filtrer les parties trop courtes ou génériques
                        parties_valides = [p for p in parties[:3] if len(p) > 2 and p not in ['contact', 'info', 'admin']]
                        if len(parties_valides) >= 2:
                            nom_trouve = ' '.join([p.capitalize() for p in parties_valides[:2]])
            
            if email_trouve:
                return {
                    "nom": nom_trouve or "Contact",
                    "poste": "Contact",
                    "email": email_trouve
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'extraction contact par email: {e}")
            return None
    
    def _chercher_contact_dans_structures(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Cherche un contact dans les structures HTML courantes (cards, team members, etc.).
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Dict avec nom et poste ou None
        """
        try:
            # Chercher dans les structures de team member
            structures = [
                # Cards de team
                soup.find_all(['div', 'article', 'section'], class_=re.compile(r'team|member|person|staff|employee', re.I)),
                # Sections about
                soup.find_all(['div', 'section'], class_=re.compile(r'about|qui-sommes', re.I)),
            ]
            
            for structure_list in structures:
                for elem in structure_list[:10]:  # Limiter à 10 pour performance
                    # Chercher nom dans h1-h5, strong, b
                    nom_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b'])
                    if not nom_elem:
                        continue
                    
                    nom = nom_elem.get_text().strip()
                    # Nettoyer
                    nom = re.sub(r'[^\w\s\-\.]', '', nom).strip()
                    mots_nom = nom.split()
                    
                    if 2 <= len(mots_nom) <= 4:
                        nom_propre = " ".join(mots_nom[:2])
                        
                        # Chercher poste dans p, span, div avec classes spécifiques
                        poste_elem = elem.find(['p', 'span', 'div'], 
                                              class_=re.compile(r'role|title|poste|position|job', re.I))
                        poste = poste_elem.get_text().strip() if poste_elem else None
                        
                        # Si pas de poste trouvé, chercher dans le texte
                        if not poste:
                            texte_elem = elem.get_text().lower()
                            postes_cherches = ["directeur", "ceo", "fondateur", "président", 
                                              "gérant", "manager", "responsable", "owner"]
                            for poste_cherche in postes_cherches:
                                if poste_cherche in texte_elem:
                                    # Extraire le poste du texte
                                    idx = texte_elem.find(poste_cherche)
                                    contexte = elem.get_text()[max(0, idx-20):idx+40]
                                    poste = contexte.strip()
                                    break
                        
                        return {
                            "nom": nom_propre,
                            "poste": poste or "Contact"
                        }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de la recherche dans structures: {e}")
            return None
    
    def _extraire_nom_dirigeant_texte_ameliore(self, soup: BeautifulSoup, poste: str) -> Optional[Dict[str, str]]:
        """
        Extrait le nom d'un dirigeant depuis le texte avec améliorations.
        
        Args:
            soup: BeautifulSoup object
            poste: Poste recherché
        
        Returns:
            Dict avec nom et poste ou None
        """
        try:
            # Chercher dans les éléments structurés d'abord
            for elem in soup.find_all(['div', 'section', 'article', 'li']):
                texte = elem.get_text().lower()
                if poste in texte:
                    # Chercher un nom dans cet élément
                    nom_elems = elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b'])
                    for nom_elem in nom_elems:
                        nom_texte = nom_elem.get_text().strip()
                        mots = nom_texte.split()
                        if 2 <= len(mots) <= 4 and all(mot[0].isupper() or mot.isupper() for mot in mots if mot.isalpha()):
                            return {
                                "nom": " ".join(mots[:2]),
                                "poste": poste.title()
                            }
                    
                    # Chercher dans le texte complet de l'élément
                    texte_complet = elem.get_text()
                    # Pattern: "Prénom NOM - Poste" ou "Poste: Prénom NOM"
                    pattern = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', re.MULTILINE)
                    matches = pattern.findall(texte_complet)
                    if matches:
                        for match in matches[:3]:
                            mots_match = match.split()
                            if 2 <= len(mots_match) <= 4:
                                return {
                                    "nom": " ".join(mots_match[:2]),
                                    "poste": poste.title()
                                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'extraction améliorée: {e}")
            return None
    
    def _chercher_linkedin_contact(self, soup: BeautifulSoup, nom_contact: str) -> Optional[str]:
        """
        Cherche un lien LinkedIn pour un contact spécifique dans le HTML.
        
        Args:
            soup: BeautifulSoup object
            nom_contact: Nom du contact recherché
        
        Returns:
            URL LinkedIn ou None
        """
        try:
            # Extraire les premières lettres du nom pour matching
            mots_nom = nom_contact.lower().split()
            if len(mots_nom) >= 2:
                prenom = mots_nom[0][:3]
                nom = mots_nom[-1][:4]
                
                # Chercher tous les liens LinkedIn
                linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com/in/', re.I))
                
                for link in linkedin_links:
                    # Vérifier si le contexte autour du lien contient le nom
                    parent_text = link.parent.get_text().lower() if link.parent else ""
                    if prenom in parent_text or nom in parent_text:
                        return link.get('href', '')
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de la recherche LinkedIn pour {nom_contact}: {e}")
            return None
    
    def _extraire_contact_depuis_page_contact(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Extrait un contact directement depuis une page de contact.
        Cherche emails + noms associés de manière plus large et moins restrictive.
        
        Args:
            soup: BeautifulSoup object de la page de contact
        
        Returns:
            Dict avec nom, email et poste (optionnel) ou None
        """
        try:
            # 1. Chercher tous les emails sur la page
            texte_complet = soup.get_text()
            emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', texte_complet)
            
            if not emails:
                return None
            
            # Filtrer les emails génériques
            emails_pertinents = [e for e in emails if not any(generic in e.lower() for generic in 
                ["info@", "contact@", "hello@", "noreply@", "no-reply@", "webmaster@", "support@", "sales@", "admin@"])]
            
            if not emails_pertinents:
                # Si seulement des emails génériques, prendre le premier
                emails_pertinents = [emails[0]]
            
            email_trouve = emails_pertinents[0]
            
            # 2. Chercher un nom associé à cet email dans le HTML
            # Chercher autour de l'email (dans le même élément ou parent)
            nom_trouve = None
            poste_trouve = None
            
            # Chercher l'email dans le HTML
            for email in emails_pertinents:
                # Chercher dans les balises qui contiennent cet email
                elements_avec_email = soup.find_all(string=re.compile(re.escape(email), re.I))
                
                for elem_text in elements_avec_email:
                    parent = elem_text.parent
                    if not parent:
                        continue
                    
                    # Chercher dans le texte autour de l'email (dans le parent et ses siblings)
                    texte_contexte = parent.get_text()
                    
                    # Pattern pour trouver un nom (2-4 mots, commençant par majuscule)
                    pattern_nom = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b')
                    matches_nom = pattern_nom.findall(texte_contexte)
                    
                    for match_nom in matches_nom[:3]:  # Prendre les 3 premiers candidats
                        mots = match_nom.split()
                        # Vérifier que ça ressemble à un nom (pas un mot isolé, pas trop long)
                        if 2 <= len(mots) <= 4 and len(match_nom) > 5:
                            # Vérifier que ce n'est pas juste un mot répété
                            if mots[0].lower() != mots[-1].lower():
                                nom_trouve = match_nom
                                break
                    
                    # Chercher aussi dans les balises voisines (h1-h6, strong, b, p)
                    for tag in parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'p']):
                        texte_tag = tag.get_text().strip()
                        matches_tag = pattern_nom.findall(texte_tag)
                        for match in matches_tag[:2]:
                            mots = match.split()
                            if 2 <= len(mots) <= 4 and len(match) > 5:
                                nom_trouve = match
                                break
                    
                    if nom_trouve:
                        # Chercher un poste dans le contexte
                        texte_lower = texte_contexte.lower()
                        postes = ["directeur", "gérant", "fondateur", "président", "ceo", "manager", "responsable", "propriétaire"]
                        for poste_mot in postes:
                            if poste_mot in texte_lower:
                                poste_trouve = poste_mot.title()
                                break
                        break
                
                if nom_trouve:
                    break
            
            # 3. Si pas de nom trouvé, essayer d'extraire depuis l'email
            if not nom_trouve:
                # Extraire la partie locale de l'email (avant @)
                partie_locale = email_trouve.split('@')[0].lower()
                # Si c'est prénom.nom ou prénom_nom, essayer d'extraire
                if '.' in partie_locale or '_' in partie_locale:
                    parties = re.split('[._]', partie_locale)
                    if len(parties) >= 2:
                        # Capitaliser pour faire un nom
                        nom_trouve = ' '.join([p.capitalize() for p in parties[:2]])
            
            if email_trouve:
                return {
                    "nom": nom_trouve or "Contact",
                    "poste": poste_trouve or "Contact",
                    "email": email_trouve
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de l'extraction depuis page contact: {e}")
            return None
    
    def _extraire_domaine(self, url: str) -> Optional[str]:
        """
        Extrait le domaine d'une URL.
        
        Args:
            url: URL complète
        
        Returns:
            Domaine extrait ou None
        """
        try:
            if not url.startswith("http"):
                url = "https://" + url
            
            parsed = urlparse(url)
            domaine = parsed.netloc.replace("www.", "")
            return domaine
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du domaine de {url}: {e}")
            return None
    
    def chercher_linkedin_dirigeant(self, email: str, nom_dirigeant: str) -> Optional[str]:
        """
        Tente de trouver le LinkedIn d'un dirigeant via son email.
        Note: Cette fonction utilise une recherche web car Hunter.io ne fournit pas directement LinkedIn.
        
        Args:
            email: Email du dirigeant
            nom_dirigeant: Nom du dirigeant
        
        Returns:
            URL LinkedIn ou None
        """
        # Cette fonction pourrait être implémentée avec une recherche Serper
        # Pour l'instant, on retourne None car elle sera gérée par serper_client
        return None
