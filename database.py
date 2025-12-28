"""
Module de gestion de la base de données SQLite pour stocker les prospects.
"""
import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_database_path() -> str:
    """
    Détermine le chemin de la base de données de manière cohérente.
    Compatible avec Pterodactyl et isolation par serveur.
    
    IMPORTANT: Dans Pterodactyl, /mnt/server est le répertoire monté qui persiste
    entre les redémarrages. Chaque serveur a son propre /mnt/server isolé.
    
    Returns:
        Chemin complet vers le fichier de base de données
    """
    # PRIORITÉ: /mnt/server (persiste entre redémarrages dans Pterodactyl)
    # Chaque serveur Pterodactyl a son propre /mnt/server monté = isolation complète
    if os.path.exists("/mnt/server"):
        base_dir = Path("/mnt/server")
    elif os.path.exists("/home/container"):
        # /home/container est souvent un lien vers /mnt/server, mais vérifions d'abord /mnt/server
        base_dir = Path("/home/container")
    else:
        # Mode développement local
        base_dir = Path(__file__).parent
    
    # S'assurer que le répertoire existe
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Permettre de surcharger via variable d'environnement
    db_path = os.getenv("DB_PATH", str(base_dir / "prospects.db"))
    
    # Logger pour debug
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📁 Chemin base de données déterminé: {db_path} (répertoire: {base_dir})")
    
    return db_path


class ProspectDatabase:
    """Gestion de la base de données SQLite pour les prospects."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise la connexion à la base de données.
        
        Args:
            db_path: Chemin vers le fichier de base de données (None = détermination automatique)
        """
        if db_path is None:
            self.db_path = get_database_path()
        else:
            self.db_path = db_path
        
        logger.info(f"📁 Base de données utilisée: {self.db_path}")
        self._init_database()
    
    def _init_database(self):
        """Initialise la structure de la base de données."""
        try:
            # S'assurer que le répertoire parent existe
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Vérifier si la base existe déjà
            db_exists = os.path.exists(self.db_path)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prospects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_entreprise TEXT NOT NULL,
                    site_web TEXT,
                    telephone TEXT,
                    email TEXT,
                    nom_dirigeant TEXT,
                    poste_dirigeant TEXT,
                    linkedin_entreprise TEXT,
                    linkedin_dirigeant TEXT,
                    message_personnalise TEXT,
                    point_specifique TEXT,
                    raison_choix TEXT,
                    proposition_service TEXT,
                    date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_traitement TIMESTAMP,
                    statut TEXT DEFAULT 'nouveau',
                    UNIQUE(nom_entreprise, site_web)
                )
            """)
            
            # Ajouter les colonnes si elles n'existent pas (pour les bases existantes)
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN raison_choix TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN proposition_service TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN email_status TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN email_sub_status TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN email_did_you_mean TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN score INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN technologies TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            try:
                cursor.execute("ALTER TABLE prospects ADD COLUMN template_utilise TEXT")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
            
            conn.commit()
            conn.close()
            
            if db_exists:
                logger.info(f"✅ Base de données existante chargée: {self.db_path}")
            else:
                logger.info(f"✅ Nouvelle base de données créée: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
            logger.error(f"   Chemin: {self.db_path}")
            raise
    
    def ajouter_prospect(self, prospect_data: Dict[str, Any]) -> Optional[int]:
        """
        Ajoute un prospect à la base de données.
        
        Args:
            prospect_data: Dictionnaire contenant les données du prospect
        
        Returns:
            ID du prospect ajouté ou None en cas d'erreur
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO prospects 
                (nom_entreprise, site_web, telephone, email, nom_dirigeant, 
                 poste_dirigeant, linkedin_entreprise, linkedin_dirigeant, 
                 message_personnalise, point_specifique, raison_choix, proposition_service,
                 email_status, email_sub_status, email_did_you_mean,
                 score, technologies, template_utilise,
                 date_traitement, statut)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prospect_data.get('nom_entreprise'),
                prospect_data.get('site_web'),
                prospect_data.get('telephone'),
                prospect_data.get('email'),
                prospect_data.get('nom_dirigeant'),
                prospect_data.get('poste_dirigeant'),
                prospect_data.get('linkedin_entreprise'),
                prospect_data.get('linkedin_dirigeant'),
                prospect_data.get('message_personnalise'),
                prospect_data.get('point_specifique'),
                prospect_data.get('raison_choix'),
                prospect_data.get('proposition_service'),
                prospect_data.get('email_status'),
                prospect_data.get('email_sub_status'),
                prospect_data.get('email_did_you_mean'),
                prospect_data.get('score', 0),
                prospect_data.get('technologies'),
                prospect_data.get('template_utilise'),
                datetime.now().isoformat(),
                'traite'
            ))
            
            prospect_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Prospect '{prospect_data.get('nom_entreprise')}' ajouté avec succès")
            return prospect_id
            
        except sqlite3.IntegrityError:
            logger.warning(f"Le prospect '{prospect_data.get('nom_entreprise')}' existe déjà")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du prospect: {e}")
            return None
    
    def prospect_existe(self, nom_entreprise: str, site_web: Optional[str] = None) -> bool:
        """
        Vérifie si un prospect existe déjà dans la base.
        
        Args:
            nom_entreprise: Nom de l'entreprise
            site_web: Site web de l'entreprise (optionnel)
        
        Returns:
            True si le prospect existe, False sinon
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if site_web:
                cursor.execute("""
                    SELECT COUNT(*) FROM prospects 
                    WHERE nom_entreprise = ? OR site_web = ?
                """, (nom_entreprise, site_web))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM prospects 
                    WHERE nom_entreprise = ?
                """, (nom_entreprise,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du prospect: {e}")
            return False
    
    def obtenir_statistiques(self) -> Dict[str, int]:
        """
        Récupère les statistiques de la base de données.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM prospects")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM prospects WHERE email IS NOT NULL AND email != ''")
            avec_email = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM prospects WHERE statut = 'traite'")
            traites = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total': total,
                'avec_email': avec_email,
                'traites': traites
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return {'total': 0, 'avec_email': 0, 'traites': 0}
