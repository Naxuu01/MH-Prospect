"""
Module client pour OpenAI - Génération de messages personnalisés.
"""
import json
import openai
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client pour interroger l'API OpenAI."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialise le client OpenAI.
        
        Args:
            api_key: Clé API OpenAI
            model: Modèle à utiliser (par défaut: gpt-4o-mini)
        """
        self.api_key = api_key
        self.model = model
    
    def generer_message_personnalise(self, entreprise_data: Dict[str, Any], 
                                    message_base: str, 
                                    proposition_valeur: str) -> Dict[str, str]:
        """
        Génère un message de prospection personnalisé avec GPT.
        
        Args:
            entreprise_data: Dictionnaire contenant les données de l'entreprise
            message_base: Template de message de base
            proposition_valeur: Proposition de valeur à inclure
        
        Returns:
            Dictionnaire contenant le message personnalisé et le point spécifique identifié
        """
        try:
            nom_entreprise = entreprise_data.get("nom_entreprise", "cette entreprise")
            site_web = entreprise_data.get("site_web", "")
            description = entreprise_data.get("description", "")
            
            # Échapper les accolades pour éviter les problèmes avec f-strings
            message_base_escaped = message_base.replace("{", "{{").replace("}", "}}")
            proposition_valeur_escaped = proposition_valeur.replace("{", "{{").replace("}", "}}")
            
            prompt = f"""Tu es un expert en prospection B2B. Analyse les informations suivantes sur une entreprise et génère un message de prospection ultra-personnalisé.

INFORMATIONS DE L'ENTREPRISE:
- Nom: {nom_entreprise}
- Site web: {site_web}
- Description: {description}

TEMPLATE DE MESSAGE:
{message_base_escaped}

PROPOSITION DE VALEUR: {proposition_valeur_escaped}

TÂCHES:
1. Identifie UN point spécifique et positif sur cette entreprise (ex: "votre expertise en rénovation de salles de bain", "vos 15 ans d'expérience", "votre présence sur 3 villes", etc.)
2. Génère un message personnalisé en remplaçant les placeholders {{nom_entreprise}} par le vrai nom, {{point_specifique}} par le point identifié, et {{proposition_valeur}} par la proposition fournie.

IMPORTANT:
- Sois naturel et authentique
- Inclus le point spécifique identifié
- Reste professionnel et concis
- Termine par un appel à l'action clair

Réponds UNIQUEMENT avec un JSON au format suivant (sans markdown, sans code block):
{{
    "point_specifique": "le point identifié ici",
    "message_personnalise": "le message complet ici"
}}
"""
            
            client = openai.OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en prospection B2B. Tu génères toujours des réponses au format JSON valide."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Nettoyer le contenu si il contient des markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            logger.info(f"Message personnalisé généré pour {nom_entreprise}")
            return {
                "message_personnalise": result.get("message_personnalise", message_base),
                "point_specifique": result.get("point_specifique", "expertise dans votre domaine")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            # Retourner un message par défaut
            return {
                "message_personnalise": message_base.replace("{nom_dirigeant}", "Monsieur/Madame")
                    .replace("{nom_entreprise}", nom_entreprise)
                    .replace("{point_specifique}", "votre expertise")
                    .replace("{proposition_valeur}", proposition_valeur),
                "point_specifique": "expertise dans votre domaine"
            }
        except Exception as e:
            logger.error(f"Erreur lors de la génération du message pour {nom_entreprise}: {e}")
            # Retourner un message par défaut
            return {
                "message_personnalise": message_base.replace("{nom_dirigeant}", "Monsieur/Madame")
                    .replace("{nom_entreprise}", nom_entreprise)
                    .replace("{point_specifique}", "votre expertise")
                    .replace("{proposition_valeur}", proposition_valeur),
                "point_specifique": "expertise dans votre domaine"
            }
    
    def analyser_entreprise_pertinence(self, entreprise_data: Dict[str, Any], 
                                      service_propose: str, 
                                      secteur_entreprise: str) -> Dict[str, str]:
        """
        Analyse une entreprise pour expliquer pourquoi elle est pertinente et ce qu'on peut lui proposer.
        
        Args:
            entreprise_data: Dictionnaire contenant les données de l'entreprise
            service_propose: Service que nous proposons
            secteur_entreprise: Secteur dans lequel nous travaillons
        
        Returns:
            Dictionnaire contenant:
            - raison_choix: Pourquoi cette entreprise a été choisie
            - proposition_service: Ce qu'on peut vraiment leur proposer
        """
        try:
            nom_entreprise = entreprise_data.get("nom_entreprise", "cette entreprise")
            site_web = entreprise_data.get("site_web", "")
            description = entreprise_data.get("description", "")
            adresse = entreprise_data.get("adresse_complete", "")
            industrie = entreprise_data.get("industrie", "")
            taille = entreprise_data.get("taille_entreprise", "")
            note_google = entreprise_data.get("note_google")
            nb_avis = entreprise_data.get("nb_avis_google")
            
            prompt = f"""Tu es un expert en prospection B2B ultra-spécialisé. Analyse cette entreprise en profondeur et génère une proposition UNIQUE et PERSONNALISÉE.

INFORMATIONS DE L'ENTREPRISE:
- Nom: {nom_entreprise}
- Site web: {site_web}
- Description: {description}
- Adresse: {adresse}
- Industrie: {industrie}
- Taille: {taille}
- Note Google: {note_google}
- Nombre d'avis: {nb_avis}

NOTRE SERVICE PROPOSÉ: {service_propose}
NOTRE SECTEUR: {secteur_entreprise}

⚠️ RÈGLE CRITIQUE: Chaque entreprise doit avoir une proposition DIFFÉRENTE et UNIQUE selon son type et ses besoins spécifiques.

TÂCHES D'ANALYSE ULTRA-DÉTAILLÉE:

1. POURQUOI CETTE ENTREPRISE (raison_choix):
   - Identifie le type d'entreprise précis (boulangerie, pâtisserie, garage auto, mécanique générale, fiduciaire, cabinet comptable, salon de coiffure, restaurant, café, pharmacie, etc.)
   - Identifie des signaux CONCRETS et SPÉCIFIQUES de besoin basés sur les informations disponibles:
     * Si pas de site web: "n'a pas de présence en ligne"
     * Si site web existe: analyse-le (design obsolète, pas responsive, pas de SEO, contenu daté, etc.)
     * Si note Google existe: "très bien noté mais pourrait améliorer sa visibilité"
     * Si description: utilise-la pour identifier les besoins
   - Sois PRÉCIS et FACTUEL (pas de suppositions)
   - 3-4 phrases maximum, ultra-spécifique à CETTE entreprise

2. PROPOSITION DE SERVICE (proposition_service):
   - Génère une proposition UNIQUE pour cette entreprise spécifique
   - Adapte au type exact d'entreprise identifié:
     
     * BOULANGERIE/PÂTISSERIE:
       - "Création d'un site web avec carte interactive des produits, horaires d'ouverture en temps réel, possibilité de commander en ligne pour retrait, et optimisation SEO locale pour apparaître dans 'boulangerie [ville]'"
     
     * GARAGE/MÉCANIQUE:
       - "Site web professionnel avec système de prise de rendez-vous en ligne, formulaire de devis automatique, présentation des services et équipements, et référencement local pour 'garage [ville]'"
     
     * FIDUCIAIRE/CABINET COMPTABLE:
       - "Site web corporate avec présentation de l'équipe, témoignages clients, blog avec conseils fiscaux et comptables, et optimisation pour recherches professionnelles '[ville] comptable'"
     
     * SALON DE COIFFURE/ESTHÉTIQUE:
       - "Site moderne avec galerie photo avant/après, réservation en ligne intégrée, présentation des prestations et tarifs, et visibilité locale sur 'coiffeur [ville]'"
     
     * RESTAURANT/CAFÉ:
       - "Site attractif avec menu interactif, système de réservation, photos de plats, avis clients, et optimisation pour 'restaurant [ville]' ou '[type cuisine] [ville]'"
     
     * ARTISAN (plombier, électricien, etc.):
       - "Site web avec présentation des réalisations, formulaire de devis rapide, zone d'intervention claire, et référencement pour '[métier] [ville]' en urgence"
     
     * COMMERCE DE PROXIMITÉ:
       - "Site e-commerce léger ou vitrine avec catalogue produits, horaires, contact, et visibilité locale pour '[type commerce] [ville]'"
   
   - INVENTE quelque chose de NOUVEAU et SPÉCIFIQUE à cette entreprise
   - Mentionne des fonctionnalités CONCRÈTES (formulaire de devis, réservation en ligne, carte interactive, etc.)
   - Adapte le langage au type d'entreprise (professionnel pour cabinet, accessible pour commerce)
   - 4-5 phrases, ultra-détaillé et UNIQUE

RÈGLES ABSOLUES:
- ❌ JAMAIS de texte identique ou similaire entre deux entreprises
- ❌ PAS de phrases génériques ("amélioration digitale", "meilleure visibilité")
- ✅ Chaque proposition doit être UNIQUE et adaptée au type d'entreprise
- ✅ Sois CRÉATIF et SPÉCIFIQUE
- ✅ Mentionne des fonctionnalités CONCRÈTES et ACTIONNABLES

Réponds UNIQUEMENT avec un JSON au format suivant (sans markdown, sans code block):
{{
    "raison_choix": "Analyse précise et spécifique à CETTE entreprise (3-4 phrases)",
    "proposition_service": "Proposition UNIQUE, détaillée et adaptée au type exact d'entreprise (4-5 phrases avec fonctionnalités concrètes)"
}}
"""
            
            client = openai.OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en prospection B2B ultra-créatif. Tu génères TOUJOURS des propositions UNIQUES et DIFFÉRENTES pour chaque entreprise. JAMAIS de texte identique ou similaire. Chaque entreprise mérite une proposition personnalisée adaptée à son type exact et ses besoins spécifiques. Sois créatif et inventif. Tu génères toujours des réponses au format JSON valide."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,  # Température plus élevée pour plus de créativité et d'unicité
                max_tokens=700    # Plus de tokens pour des propositions détaillées et uniques
            )
            
            content = response.choices[0].message.content.strip()
            
            # Nettoyer le contenu si il contient des markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            logger.info(f"Analyse de pertinence générée pour {nom_entreprise}")
            return {
                "raison_choix": result.get("raison_choix", "PME locale qui pourrait bénéficier de nos services"),
                "proposition_service": result.get("proposition_service", f"Amélioration de leur présence digitale avec {service_propose}")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON dans analyse: {e}")
            return {
                "raison_choix": f"PME locale qui pourrait bénéficier de {service_propose}",
                "proposition_service": f"Amélioration de leur présence digitale avec {service_propose}"
            }
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de pertinence pour {nom_entreprise}: {e}")
            return {
                "raison_choix": f"PME locale qui pourrait bénéficier de {service_propose}",
                "proposition_service": f"Amélioration de leur présence digitale avec {service_propose}"
            }
