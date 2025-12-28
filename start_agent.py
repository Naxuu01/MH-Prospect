"""
Script de démarrage pour lancer l'agent ET l'interface web en parallèle.
Utilisé avec Pterodactyl pour démarrer les deux services.
"""
import os
import sys
import subprocess
import logging
from threading import Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_agent():
    """Lance l'agent de prospection."""
    logger.info("🚀 Démarrage de l'agent de prospection...")
    try:
        from main import main as agent_main
        agent_main()
    except KeyboardInterrupt:
        logger.info("⏹️  Agent arrêté")
    except Exception as e:
        logger.error(f"❌ Erreur agent: {e}", exc_info=True)


def run_web_interface():
    """Lance l'interface web."""
    logger.info("🌐 Démarrage de l'interface web...")
    try:
        from web_interface import main as web_main
        # La fonction main() gère automatiquement le port (SERVER_PORT, PORT, etc.)
        # et écoute sur 0.0.0.0 pour accepter les connexions externes
        web_main()
    except KeyboardInterrupt:
        logger.info("⏹️  Interface web arrêtée")
    except Exception as e:
        logger.error(f"❌ Erreur interface web: {e}", exc_info=True)
        raise


def main():
    """Lance les deux services en parallèle."""
    logger.info("="*60)
    logger.info("🚀 Démarrage MH Prospect - Agent + Interface Web")
    logger.info("="*60)
    
    # Lancer l'interface web dans un thread séparé
    web_thread = Thread(target=run_web_interface, daemon=True)
    web_thread.start()
    
    # Lancer l'agent dans le thread principal (pour gérer Ctrl+C correctement)
    try:
        run_agent()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Arrêt demandé par l'utilisateur")
        sys.exit(0)


if __name__ == "__main__":
    main()

