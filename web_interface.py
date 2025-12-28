"""
Interface web Flask pour visualiser et gérer les prospects.
Compatible avec Pterodactyl (utilise le port automatique via SERVER_PORT ou 5000 par défaut).
"""
import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, send_file, redirect, url_for

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Déterminer le chemin de la base de données (compatible Pterodactyl)
# Pterodactyl utilise /home/container comme répertoire de travail
if os.path.exists("/home/container"):
    BASE_DIR = Path("/home/container")
elif os.path.exists("/mnt/server"):
    BASE_DIR = Path("/mnt/server")
else:
    BASE_DIR = Path(__file__).parent

DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "prospects.db"))
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

logger.info(f"📁 Base de données: {DB_PATH}")
logger.info(f"📁 Dossier exports: {EXPORT_DIR}")


def get_db_connection():
    """Crée une connexion à la base de données avec gestion d'erreurs."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"❌ Erreur connexion DB: {e}")
        raise


# Template HTML principal
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - MH Prospect</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .header p { opacity: 0.9; }
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 1rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stat-card .value {
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }
        .filters {
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1rem;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: center;
        }
        .filters input, .filters select {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 0.9rem;
        }
        .filters button {
            padding: 0.5rem 1.5rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .filters button:hover { background: #5568d3; }
        .export-buttons {
            display: flex;
            gap: 0.5rem;
            margin-left: auto;
        }
        .export-buttons a {
            padding: 0.5rem 1rem;
            background: #10b981;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.85rem;
        }
        .export-buttons a:hover { background: #059669; }
        .table-container {
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #f8f9fa;
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            color: #555;
            cursor: pointer;
            user-select: none;
        }
        th:hover { background: #e9ecef; }
        td {
            padding: 1rem;
            border-top: 1px solid #eee;
        }
        tr:hover { background: #f8f9fa; }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .badge-excellent { background: #d1fae5; color: #065f46; }
        .badge-bon { background: #dbeafe; color: #1e40af; }
        .badge-moyen { background: #fef3c7; color: #92400e; }
        .badge-faible { background: #fee2e2; color: #991b1b; }
        .badge-valid { background: #d1fae5; color: #065f46; }
        .badge-invalid { background: #fee2e2; color: #991b1b; }
        .badge-unknown { background: #e5e7eb; color: #374151; }
        .score-cell {
            font-weight: bold;
            font-size: 1.1rem;
        }
        .actions {
            display: flex;
            gap: 0.5rem;
        }
        .btn-small {
            padding: 0.25rem 0.75rem;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85rem;
        }
        .btn-edit {
            background: #667eea;
            color: white;
        }
        .btn-edit:hover { background: #5568d3; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }
        .modal-content {
            background: white;
            margin: 5% auto;
            padding: 2rem;
            border-radius: 10px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        .close { font-size: 2rem; cursor: pointer; color: #999; }
        .close:hover { color: #333; }
        .form-group {
            margin-bottom: 1rem;
        }
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 0.9rem;
        }
        .form-group textarea {
            min-height: 100px;
            resize: vertical;
        }
        .loading {
            text-align: center;
            padding: 2rem;
            color: #666;
        }
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #999;
        }
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #10b981;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
            display: none;
        }
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        .new-prospect {
            animation: highlightNew 3s ease-out;
            border-left: 4px solid #10b981 !important;
        }
        @keyframes highlightNew {
            0% { 
                background: #fef3c7 !important;
                transform: scale(1.02);
            }
            30% { 
                background: #d1fae5 !important;
                transform: scale(1.01);
            }
            100% { 
                background: white !important;
                transform: scale(1);
            }
        }
        .auto-refresh-indicator {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(102, 126, 234, 0.9);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.85rem;
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .auto-refresh-indicator .dot {
            width: 8px;
            height: 8px;
            background: white;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Dashboard MH Prospect</h1>
        <p>Gestion et visualisation des prospects - Mise à jour automatique</p>
    </div>
    
    <!-- Toast pour notifications -->
    <div id="toast" class="toast"></div>
    
    <!-- Indicateur de rafraîchissement automatique -->
    <div class="auto-refresh-indicator">
        <span class="dot"></span>
        <span>Mise à jour automatique</span>
    </div>
    
    <div class="container">
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <h3>Total Prospects</h3>
                <div class="value" id="stat-total">-</div>
            </div>
            <div class="stat-card">
                <h3>Avec Email</h3>
                <div class="value" id="stat-email">-</div>
            </div>
            <div class="stat-card">
                <h3>Avec Téléphone</h3>
                <div class="value" id="stat-phone">-</div>
            </div>
            <div class="stat-card">
                <h3>Score Moyen</h3>
                <div class="value" id="stat-score">-</div>
            </div>
        </div>
        
        <div class="filters">
            <input type="text" id="search" placeholder="🔍 Rechercher..." onkeyup="filterProspects()">
            <select id="filter-score" onchange="filterProspects()">
                <option value="">Tous les scores</option>
                <option value="excellent">Excellent (80+)</option>
                <option value="bon">Bon (60-79)</option>
                <option value="moyen">Moyen (40-59)</option>
                <option value="faible">Faible (<40)</option>
            </select>
            <select id="filter-status" onchange="filterProspects()">
                <option value="">Tous les statuts</option>
                <option value="nouveau">Nouveau</option>
                <option value="traite">Traité</option>
                <option value="contacté">Contacté</option>
                <option value="intéressé">Intéressé</option>
            </select>
            <button onclick="filterProspects()">Filtrer</button>
            <div class="export-buttons">
                <a href="/export/csv">📥 CSV</a>
                <a href="/export/excel">📊 Excel</a>
                <a href="/export/pdf">📄 PDF</a>
                <a href="/export/json">📦 JSON</a>
            </div>
        </div>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th onclick="sortTable('score')">Score ⬍</th>
                        <th onclick="sortTable('nom_entreprise')">Entreprise</th>
                        <th onclick="sortTable('email')">Email</th>
                        <th onclick="sortTable('telephone')">Téléphone</th>
                        <th>Technologies</th>
                        <th onclick="sortTable('statut')">Statut</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="prospects-table">
                    <tr><td colspan="7" class="loading">Chargement...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- Modal pour édition -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Éditer Prospect</h2>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>
            <form id="editForm" onsubmit="saveProspect(event)">
                <input type="hidden" id="edit-id">
                <div class="form-group">
                    <label>Statut</label>
                    <select id="edit-statut" required>
                        <option value="nouveau">Nouveau</option>
                        <option value="traite">Traité</option>
                        <option value="contacté">Contacté</option>
                        <option value="répondu">Répondu</option>
                        <option value="intéressé">Intéressé</option>
                        <option value="non_intéressé">Non intéressé</option>
                        <option value="qualifié">Qualifié</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Note/Commentaire</label>
                    <textarea id="edit-note"></textarea>
                </div>
                <button type="submit" class="btn-edit btn-small" style="width: 100%;">Enregistrer</button>
            </form>
        </div>
    </div>
    
    <script>
        let prospects = [];
        let previousProspectIds = new Set();
        let sortColumn = 'score';
        let sortDirection = 'desc';
        let isInitialLoad = true;
        
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.style.display = 'block';
            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        }
        
        async function loadData() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                const oldTotal = parseInt(document.getElementById('stat-total').textContent) || 0;
                document.getElementById('stat-total').textContent = stats.total;
                document.getElementById('stat-email').textContent = stats.avec_email;
                document.getElementById('stat-phone').textContent = stats.avec_telephone;
                document.getElementById('stat-score').textContent = stats.score_moyen ? Math.round(stats.score_moyen) : '-';
                
                // Notification si nouveau prospect détecté via stats
                if (!isInitialLoad && stats.total > oldTotal) {
                    showToast(`🎉 ${stats.total - oldTotal} nouveau(x) prospect(s) ajouté(s) !`);
                }
            } catch (e) {
                console.error('Erreur chargement stats:', e);
            }
            
            try {
                const response = await fetch('/api/prospects');
                const newProspects = await response.json();
                
                // Détecter les nouveaux prospects
                if (!isInitialLoad) {
                    const newProspectIds = new Set(newProspects.map(p => p.id));
                    const newIds = [...newProspectIds].filter(id => !previousProspectIds.has(id));
                    
                    if (newIds.length > 0) {
                        const count = newIds.length;
                        showToast(`✨ ${count} nouveau(x) prospect(s) détecté(s) !`);
                        // Marquer les nouveaux prospects pour animation après rendu
                        setTimeout(() => {
                            newIds.forEach((id, index) => {
                                const row = document.querySelector(`tr[data-prospect-id="${id}"]`);
                                if (row) {
                                    row.classList.add('new-prospect');
                                    // Faire défiler vers le premier nouveau prospect
                                    if (index === 0) {
                                        setTimeout(() => {
                                            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        }, 200);
                                    }
                                    // Retirer la classe après l'animation
                                    setTimeout(() => {
                                        row.classList.remove('new-prospect');
                                    }, 3000);
                                }
                            });
                        }, 100);
                    }
                }
                
                prospects = newProspects;
                previousProspectIds = new Set(prospects.map(p => p.id));
                renderTable();
                isInitialLoad = false;
            } catch (e) {
                console.error('Erreur chargement prospects:', e);
                document.getElementById('prospects-table').innerHTML = 
                    '<tr><td colspan="7" class="empty-state">Erreur lors du chargement</td></tr>';
            }
        }
        
        function renderTable(filteredProspects = null) {
            const data = filteredProspects || prospects;
            const tbody = document.getElementById('prospects-table');
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Aucun prospect trouvé</td></tr>';
                return;
            }
            
            tbody.innerHTML = data.map(p => {
                const scoreBadge = getScoreBadge(p.score || 0);
                const emailBadge = getEmailBadge(p.email_status);
                const techs = p.technologies ? p.technologies.split(',').slice(0, 2).join(', ') : '-';
                
                return `
                    <tr data-prospect-id="${p.id}">
                        <td class="score-cell">${scoreBadge}</td>
                        <td><strong>${escapeHtml(p.nom_entreprise || '-')}</strong><br>
                            <small style="color: #999;">${escapeHtml(p.site_web || '')}</small></td>
                        <td>${p.email ? escapeHtml(p.email) + ' ' + emailBadge : '-'}</td>
                        <td>${p.telephone || '-'}</td>
                        <td><small>${escapeHtml(techs)}</small></td>
                        <td><span class="badge">${escapeHtml(p.statut || 'nouveau')}</span></td>
                        <td class="actions">
                            <button class="btn-small btn-edit" onclick="editProspect(${p.id})">✏️</button>
                        </td>
                    </tr>
                `;
            }).join('');
        }
        
        function getScoreBadge(score) {
            if (score >= 80) return `<span class="badge badge-excellent">${score}</span>`;
            if (score >= 60) return `<span class="badge badge-bon">${score}</span>`;
            if (score >= 40) return `<span class="badge badge-moyen">${score}</span>`;
            return `<span class="badge badge-faible">${score}</span>`;
        }
        
        function getEmailBadge(status) {
            if (!status) return '';
            if (status === 'valid') return '<span class="badge badge-valid">✓</span>';
            if (status === 'invalid') return '<span class="badge badge-invalid">✗</span>';
            return '<span class="badge badge-unknown">?</span>';
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function filterProspects() {
            const search = document.getElementById('search').value.toLowerCase();
            const scoreFilter = document.getElementById('filter-score').value;
            const statusFilter = document.getElementById('filter-status').value;
            
            let filtered = prospects.filter(p => {
                const matchSearch = !search || 
                    (p.nom_entreprise && p.nom_entreprise.toLowerCase().includes(search)) ||
                    (p.email && p.email.toLowerCase().includes(search));
                
                const matchScore = !scoreFilter || (() => {
                    const score = p.score || 0;
                    if (scoreFilter === 'excellent') return score >= 80;
                    if (scoreFilter === 'bon') return score >= 60 && score < 80;
                    if (scoreFilter === 'moyen') return score >= 40 && score < 60;
                    if (scoreFilter === 'faible') return score < 40;
                    return true;
                })();
                
                const matchStatus = !statusFilter || (p.statut || 'nouveau') === statusFilter;
                
                return matchSearch && matchScore && matchStatus;
            });
            
            renderTable(filtered);
        }
        
        function sortTable(column) {
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = 'desc';
            }
            
            prospects.sort((a, b) => {
                let aVal = a[column] || '';
                let bVal = b[column] || '';
                
                if (column === 'score') {
                    aVal = parseInt(aVal) || 0;
                    bVal = parseInt(bVal) || 0;
                } else {
                    aVal = String(aVal).toLowerCase();
                    bVal = String(bVal).toLowerCase();
                }
                
                if (sortDirection === 'asc') {
                    return aVal > bVal ? 1 : -1;
                } else {
                    return aVal < bVal ? 1 : -1;
                }
            });
            
            renderTable();
        }
        
        async function editProspect(id) {
            const prospect = prospects.find(p => p.id === id);
            if (!prospect) return;
            
            document.getElementById('edit-id').value = id;
            document.getElementById('edit-statut').value = prospect.statut || 'nouveau';
            document.getElementById('editModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('editModal').style.display = 'none';
        }
        
        async function saveProspect(event) {
            event.preventDefault();
            const id = document.getElementById('edit-id').value;
            const statut = document.getElementById('edit-statut').value;
            
            try {
                const response = await fetch(`/api/prospects/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ statut })
                });
                
                if (response.ok) {
                    const updated = await response.json();
                    const index = prospects.findIndex(p => p.id === id);
                    if (index !== -1) {
                        prospects[index] = updated;
                    }
                    renderTable();
                    closeModal();
                }
            } catch (e) {
                alert('Erreur lors de la sauvegarde');
            }
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target === modal) {
                closeModal();
            }
        }
        
        // Charger les données au démarrage
        loadData();
        // Rafraîchir toutes les 2 secondes pour mise à jour en temps réel
        setInterval(loadData, 2000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Page principale avec le dashboard."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/stats')
def api_stats():
    """Retourne les statistiques."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM prospects")
        total = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE email IS NOT NULL AND email != ''")
        avec_email = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE telephone IS NOT NULL AND telephone != ''")
        avec_telephone = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT AVG(score) FROM prospects WHERE score > 0")
        result = cursor.fetchone()[0]
        score_moyen = float(result) if result else 0
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE score >= 80")
        excellent = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE score >= 60 AND score < 80")
        bon = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'total': total,
            'avec_email': avec_email,
            'avec_telephone': avec_telephone,
            'score_moyen': round(score_moyen, 1),
            'excellent': excellent,
            'bon': bon
        })
    except sqlite3.Error as e:
        logger.error(f"Erreur DB API stats: {e}")
        return jsonify({'error': f'Erreur base de données: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Erreur API stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/prospects')
def api_prospects():
    """Retourne tous les prospects."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer avec gestion des colonnes manquantes
        cursor.execute("PRAGMA table_info(prospects)")
        columns_info = cursor.fetchall()
        available_columns = [col[1] for col in columns_info]
        
        # Construire la requête avec seulement les colonnes existantes
        cursor.execute("""
            SELECT * FROM prospects 
            ORDER BY COALESCE(score, 0) DESC, date_traitement DESC
            LIMIT 500
        """)
        
        prospects = []
        for row in cursor.fetchall():
            prospect_dict = {}
            for col in available_columns:
                try:
                    prospect_dict[col] = row[col]
                except (KeyError, IndexError):
                    prospect_dict[col] = None
            prospects.append(prospect_dict)
        
        conn.close()
        
        return jsonify(prospects)
    except sqlite3.Error as e:
        logger.error(f"Erreur DB API prospects: {e}")
        return jsonify({'error': f'Erreur base de données: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Erreur API prospects: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/prospects/<int:prospect_id>', methods=['PUT'])
def update_prospect(prospect_id):
    """Met à jour un prospect."""
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE prospects 
            SET statut = ?, date_traitement = ?
            WHERE id = ?
        """, (data.get('statut'), datetime.now().isoformat(), prospect_id))
        
        conn.commit()
        
        cursor.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,))
        updated = dict(cursor.fetchone())
        conn.close()
        
        return jsonify(updated)
    except Exception as e:
        logger.error(f"Erreur update prospect: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/export/<format_type>')
def export_prospects(format_type):
    """Exporte les prospects dans le format demandé."""
    try:
        # Importer les fonctions d'export avec gestion d'erreurs
        try:
            from export_prospects import exporter_csv, exporter_excel, exporter_pdf, exporter_json
        except ImportError as e:
            logger.error(f"Erreur import export_prospects: {e}")
            return jsonify({'error': f'Module export non disponible: {e}'}), 500
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_type == 'csv':
            filename = exporter_csv(DB_PATH, str(EXPORT_DIR / f"prospects_{timestamp}.csv"))
            return send_file(filename, as_attachment=True, download_name=f"prospects_{timestamp}.csv")
        elif format_type == 'excel':
            filename = exporter_excel(DB_PATH, str(EXPORT_DIR / f"prospects_{timestamp}.xlsx"))
            return send_file(filename, as_attachment=True, download_name=f"prospects_{timestamp}.xlsx")
        elif format_type == 'pdf':
            filename = exporter_pdf(DB_PATH, str(EXPORT_DIR / f"prospects_{timestamp}.pdf"))
            return send_file(filename, as_attachment=True, download_name=f"prospects_{timestamp}.pdf")
        elif format_type == 'json':
            filename = exporter_json(DB_PATH, str(EXPORT_DIR / f"prospects_{timestamp}.json"))
            return send_file(filename, as_attachment=True, download_name=f"prospects_{timestamp}.json")
        else:
            return jsonify({'error': 'Format non supporté'}), 400
    except Exception as e:
        logger.error(f"Erreur export {format_type}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def main():
    """Lance le serveur Flask."""
    # Pterodactyl fournit le port via SERVER_PORT ou dans les variables d'environnement
    # Essayer plusieurs variables d'environnement possibles
    port = None
    for env_var in ["SERVER_PORT", "PORT", "SERVER_PORT_0", "SERVER_PORT_1"]:
        port_str = os.getenv(env_var)
        if port_str:
            try:
                port = int(port_str)
                logger.info(f"Port trouvé via {env_var}: {port}")
                break
            except ValueError:
                continue
    
    if not port:
        port = 5000
        logger.warning(f"⚠️  Aucun port trouvé dans les variables d'environnement, utilisation du port par défaut: {port}")
    
    host = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 pour accepter les connexions externes
    
    # Vérifier que la base de données existe
    if not os.path.exists(DB_PATH):
        logger.warning(f"⚠️  Base de données non trouvée: {DB_PATH}")
        logger.info("💡 La base sera créée automatiquement au premier ajout de prospect")
    
    logger.info(f"🌐 Interface web démarrée sur http://{host}:{port}")
    logger.info(f"📊 Accédez au dashboard: http://localhost:{port}")
    logger.info(f"📁 Base de données: {DB_PATH}")
    
    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error(f"❌ Port {port} déjà utilisé. Changez le port dans Pterodactyl ou arrêtez le processus qui l'utilise.")
        else:
            logger.error(f"❌ Erreur lors du démarrage: {e}")
        raise


if __name__ == "__main__":
    main()

