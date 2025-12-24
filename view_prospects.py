"""
Script utilitaire pour consulter les prospects sauvegardés dans la base de données.
"""
import sqlite3
import sys
from datetime import datetime
from typing import List, Dict, Any


def afficher_prospects(db_path: str = "prospects.db", limite: int = 10):
    """
    Affiche les prospects de la base de données.
    
    Args:
        db_path: Chemin vers la base de données
        limite: Nombre maximum de prospects à afficher
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtenir le total
        cursor.execute("SELECT COUNT(*) FROM prospects")
        total = cursor.fetchone()[0]
        
        # Obtenir les derniers prospects
        cursor.execute("""
            SELECT * FROM prospects 
            ORDER BY date_traitement DESC 
            LIMIT ?
        """, (limite,))
        
        prospects = cursor.fetchall()
        
        print(f"\n{'='*100}")
        print(f"📊 PROSPECTS EN BASE DE DONNÉES - Total: {total} | Affichés: {len(prospects)}")
        print(f"{'='*100}\n")
        
        if not prospects:
            print("Aucun prospect trouvé dans la base de données.")
            conn.close()
            return
        
        for idx, prospect in enumerate(prospects, 1):
            print(f"\n{'─'*100}")
            print(f"#{idx} - {prospect['nom_entreprise']}")
            print(f"{'─'*100}")
            print(f"🌐 Site web: {prospect['site_web'] or 'N/A'}")
            print(f"📞 Téléphone: {prospect['telephone'] or 'N/A'}")
            print(f"✉️  Email: {prospect['email'] or 'N/A'}")
            print(f"🔗 LinkedIn Entreprise: {prospect['linkedin_entreprise'] or 'N/A'}")
            print(f"💡 Point spécifique: {prospect['point_specifique'] or 'N/A'}")
            print(f"📅 Date traitement: {prospect['date_traitement'] or 'N/A'}")
            if prospect['message_personnalise']:
                print(f"\n📝 Message personnalisé:\n{prospect['message_personnalise']}")
        
        print(f"\n{'='*100}\n")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Erreur de base de données: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)


def afficher_statistiques(db_path: str = "prospects.db"):
    """
    Affiche les statistiques de la base de données.
    
    Args:
        db_path: Chemin vers la base de données
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM prospects")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE email IS NOT NULL AND email != ''")
        avec_email = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE linkedin_entreprise IS NOT NULL")
        avec_linkedin = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE message_personnalise IS NOT NULL")
        avec_message = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n{'='*80}")
        print("📈 STATISTIQUES")
        print(f"{'='*80}")
        print(f"Total prospects: {total}")
        print(f"Avec email: {avec_email} ({avec_email/total*100 if total > 0 else 0:.1f}%)")
        print(f"Avec LinkedIn: {avec_linkedin} ({avec_linkedin/total*100 if total > 0 else 0:.1f}%)")
        print(f"Avec message: {avec_message} ({avec_message/total*100 if total > 0 else 0:.1f}%)")
        print(f"{'='*80}\n")
        
    except sqlite3.Error as e:
        print(f"❌ Erreur de base de données: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)


def exporter_csv(db_path: str = "prospects.db", output_file: str = "prospects_export.csv"):
    """
    Exporte les prospects en CSV.
    
    Args:
        db_path: Chemin vers la base de données
        output_file: Fichier de sortie CSV
    """
    try:
        import csv
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM prospects ORDER BY date_traitement DESC")
        prospects = cursor.fetchall()
        
        if not prospects:
            print("Aucun prospect à exporter.")
            conn.close()
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # En-têtes
            writer.writerow([
                'ID', 'Nom Entreprise', 'Site Web', 'Téléphone', 'Email',
                'LinkedIn Entreprise', 'Point Spécifique', 'Message Personnalisé',
                'Date Ajout', 'Date Traitement', 'Statut'
            ])
            
            # Données
            for prospect in prospects:
                writer.writerow([
                    prospect['id'], prospect['nom_entreprise'], prospect['site_web'],
                    prospect['telephone'], prospect['email'], prospect['linkedin_entreprise'],
                    prospect['point_specifique'], prospect['message_personnalise'],
                    prospect['date_ajout'], prospect['date_traitement'], prospect['statut']
                ])
        
        conn.close()
        print(f"✅ {len(prospects)} prospects exportés vers {output_file}")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Consulter les prospects de la base de données")
    parser.add_argument("--limite", type=int, default=10, help="Nombre de prospects à afficher (défaut: 10)")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")
    parser.add_argument("--export", type=str, help="Exporter en CSV (spécifier le nom du fichier)")
    parser.add_argument("--db", type=str, default="prospects.db", help="Chemin vers la base de données (défaut: prospects.db)")
    
    args = parser.parse_args()
    
    if args.stats:
        afficher_statistiques(args.db)
    elif args.export:
        exporter_csv(args.db, args.export)
    else:
        afficher_prospects(args.db, args.limite)
