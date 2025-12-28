"""
Module de détection des technologies web utilisées par les sites.
"""
import re
import logging
import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TechnologyDetector:
    """Détecte les technologies utilisées sur un site web."""
    
    def __init__(self, timeout: int = 10):
        """
        Initialise le détecteur de technologies.
        
        Args:
            timeout: Timeout pour les requêtes HTTP en secondes
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Patterns de détection
        self.patterns = {
            "wordpress": [
                r'wp-content|wp-includes|wordpress',
                r'/wp-admin/',
                r'wp-json',
                r'WordPress'
            ],
            "shopify": [
                r'shopify\.com',
                r'shopifycdn\.com',
                r'cdn\.shopify',
                r'Shopify\.themes'
            ],
            "prestashop": [
                r'prestashop',
                r'/modules/',
                r'PrestaShop'
            ],
            "woocommerce": [
                r'woocommerce',
                r'wc-api',
                r'WooCommerce'
            ],
            "magento": [
                r'magento',
                r'Mage\.Cookies',
                r'/magento/'
            ],
            "drupal": [
                r'drupal',
                r'/sites/default/',
                r'Drupal\.settings'
            ],
            "joomla": [
                r'joomla',
                r'/components/',
                r'Joomla!'
            ],
            "squarespace": [
                r'squarespace',
                r'.squarespace\.com'
            ],
            "wix": [
                r'wix\.com',
                r'wixpress\.com',
                r'Wix\.'
            ],
            "react": [
                r'React',
                r'react-dom',
                r'_next/static'
            ],
            "vue": [
                r'Vue\.',
                r'vue\.js',
                r'__vue__'
            ],
            "angular": [
                r'Angular',
                r'ng-',
                r'angular\.js'
            ],
            "bootstrap": [
                r'bootstrap',
                r'bootstrap\.css'
            ],
            "jquery": [
                r'jquery',
                r'\$\(\)',
                r'jQuery'
            ]
        }
    
    def detecter(self, site_web: str) -> List[str]:
        """
        Détecte les technologies utilisées sur un site web.
        
        Args:
            site_web: URL du site web
        
        Returns:
            Liste des technologies détectées
        """
        if not site_web or not site_web.startswith("http"):
            return []
        
        technologies = []
        
        try:
            # Normaliser l'URL
            if not site_web.startswith("http"):
                site_web = f"https://{site_web}"
            
            # Récupérer le contenu HTML
            response = requests.get(site_web, timeout=self.timeout, headers=self.headers, allow_redirects=True)
            response.raise_for_status()
            
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Vérifier les meta tags
            meta_tags = soup.find_all('meta')
            meta_content = " ".join([tag.get('content', '') + " " + tag.get('name', '') for tag in meta_tags])
            
            # Vérifier les scripts
            scripts = soup.find_all('script')
            script_content = " ".join([script.get('src', '') + " " + script.string if script.string else '' for script in scripts])
            
            # Vérifier les liens CSS
            links = soup.find_all('link', rel='stylesheet')
            css_content = " ".join([link.get('href', '') for link in links])
            
            # Vérifier les commentaires HTML
            html_comments = re.findall(r'<!--.*?-->', html_content, re.DOTALL)
            comments_content = " ".join(html_comments)
            
            # Combiner tout le contenu pour recherche
            full_content = (html_content + " " + meta_content + " " + script_content + 
                          " " + css_content + " " + comments_content).lower()
            
            # Vérifier les headers HTTP
            headers_content = str(response.headers).lower()
            
            # Détecter chaque technologie
            for tech_name, patterns in self.patterns.items():
                for pattern in patterns:
                    if re.search(pattern, full_content, re.IGNORECASE) or \
                       re.search(pattern, headers_content, re.IGNORECASE):
                        if tech_name not in technologies:
                            technologies.append(tech_name)
                            logger.debug(f"Technologie détectée: {tech_name} sur {site_web}")
                        break
            
            # Détecter le serveur web (si visible)
            server = response.headers.get('Server', '').lower()
            if 'nginx' in server:
                technologies.append('nginx')
            elif 'apache' in server:
                technologies.append('apache')
            elif 'cloudflare' in server:
                technologies.append('cloudflare')
            
            # Détecter PHP
            if any(tech in technologies for tech in ['wordpress', 'prestashop', 'woocommerce', 'magento', 'drupal', 'joomla']):
                technologies.append('php')
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Impossible de détecter les technologies pour {site_web}: {e}")
        except Exception as e:
            logger.warning(f"Erreur lors de la détection de technologies pour {site_web}: {e}")
        
        return technologies
    
    def obtenir_description_technologies(self, technologies: List[str]) -> str:
        """
        Retourne une description lisible des technologies.
        
        Args:
            technologies: Liste des technologies détectées
        
        Returns:
            Description formatée
        """
        if not technologies:
            return "Technologies non détectées"
        
        # Catégoriser
        cms = []
        frameworks = []
        autres = []
        
        cms_list = ['wordpress', 'shopify', 'prestashop', 'woocommerce', 'magento', 
                    'drupal', 'joomla', 'squarespace', 'wix']
        framework_list = ['react', 'vue', 'angular', 'bootstrap', 'jquery']
        
        for tech in technologies:
            tech_lower = tech.lower()
            if tech_lower in cms_list:
                cms.append(tech.capitalize())
            elif tech_lower in framework_list:
                frameworks.append(tech.capitalize())
            else:
                autres.append(tech.capitalize())
        
        descriptions = []
        if cms:
            descriptions.append(f"CMS: {', '.join(cms)}")
        if frameworks:
            descriptions.append(f"Frameworks: {', '.join(frameworks)}")
        if autres:
            descriptions.append(f"Autres: {', '.join(autres)}")
        
        return " | ".join(descriptions) if descriptions else "Technologies non identifiées"

