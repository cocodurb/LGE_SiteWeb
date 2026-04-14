from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import os

app = Flask(__name__, static_folder='.')
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), 'database.sqlite')
DEFAULT_CATEGORIES = json.dumps(['Sénior Homme', 'Sénior Femme', 'Vétéran Homme', 'Vétéran Femme'])

# ─── INIT DB ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('PRAGMA journal_mode=WAL')

    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            shotgun_date TEXT NOT NULL,
            total_spots INTEGER NOT NULL,
            available_spots INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            categories TEXT NOT NULL DEFAULT '[]'
        )
    ''')

    for col, default in [
        ('is_active', '1'),
        ('description', "''"),
        ('categories', f"'{DEFAULT_CATEGORIES}'"),
    ]:
        try:
            c.execute(f'ALTER TABLE events ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}')
            conn.commit()
        except sqlite3.OperationalError:
            pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            prenom TEXT NOT NULL,
            nom TEXT NOT NULL,
            email TEXT NOT NULL,
            categorie TEXT NOT NULL,
            registration_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id),
            UNIQUE(event_id, email)
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def parse_event(row):
    try:
        cats = json.loads(row['categories']) if row['categories'] else []
    except Exception:
        cats = []
    return {
        'id': row['id'],
        'name': row['name'],
        'description': row['description'],
        'shotgun_date': row['shotgun_date'],
        'total_spots': row['total_spots'],
        'available_spots': row['available_spots'],
        'is_active': row['is_active'],
        'categories': cats,
    }

# ─── STATIC FILES ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# ─── GET /api/events/active ───────────────────────────────────────────────────
@app.route('/api/events/active')
def get_active_events():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM events WHERE is_active = 1 ORDER BY shotgun_date ASC'
    ).fetchall()
    conn.close()
    return jsonify([parse_event(r) for r in rows])

# ─── GET /api/admin/events ────────────────────────────────────────────────────
@app.route('/api/admin/events')
def get_all_events():
    conn = get_db()
    rows = conn.execute('SELECT * FROM events ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([parse_event(r) for r in rows])

# ─── GET /api/admin/participants ──────────────────────────────────────────────
@app.route('/api/admin/participants')
def get_participants():
    event_id = request.args.get('event_id')
    conn = get_db()
    if event_id:
        rows = conn.execute(
            'SELECT id, prenom, nom, email, categorie, registration_time FROM participants WHERE event_id = ? ORDER BY id ASC',
            (event_id,)
        ).fetchall()
    else:
        evt = conn.execute(
            'SELECT id FROM events WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()
        if not evt:
            conn.close()
            return jsonify([])
        rows = conn.execute(
            'SELECT id, prenom, nom, email, categorie, registration_time FROM participants WHERE event_id = ? ORDER BY id ASC',
            (evt['id'],)
        ).fetchall()
    conn.close()
    return jsonify([{
        'id': r['id'], 'prenom': r['prenom'], 'nom': r['nom'],
        'email': r['email'], 'categorie': r['categorie'], 'time': r['registration_time']
    } for r in rows])

# ─── POST /api/events/register ────────────────────────────────────────────────
@app.route('/api/events/register', methods=['POST'])
def register():
    data = request.get_json(force=True) or {}
    prenom = (data.get('prenom') or '').strip()
    nom = (data.get('nom') or '').strip()
    email = (data.get('email') or '').strip().lower()
    categorie = (data.get('categorie') or '').strip()
    event_id = data.get('event_id')

    if not all([prenom, nom, email, categorie, event_id]):
        return jsonify({'success': False, 'message': 'Champs manquants'}), 400

    try:
        conn = sqlite3.connect(DB_FILE, isolation_level='EXCLUSIVE')
        c = conn.cursor()
        c.execute('BEGIN EXCLUSIVE')

        c.execute('SELECT COUNT(*) FROM participants WHERE email = ? AND event_id = ?', (email, event_id))
        if c.fetchone()[0] > 0:
            conn.rollback(); conn.close()
            return jsonify({'success': False, 'message': 'Cet email est déjà inscrit à cet événement.'}), 400

        c.execute('SELECT available_spots, is_active FROM events WHERE id = ?', (event_id,))
        evt = c.fetchone()
        if not evt or not evt[1]:
            conn.rollback(); conn.close()
            return jsonify({'success': False, 'message': 'Événement introuvable ou archivé.'}), 404

        c.execute('UPDATE events SET available_spots = available_spots - 1 WHERE id = ? AND available_spots > 0', (event_id,))
        if c.rowcount == 1:
            c.execute('INSERT INTO participants (event_id, prenom, nom, email, categorie) VALUES (?, ?, ?, ?, ?)',
                      (event_id, prenom, nom, email, categorie))
            conn.commit(); conn.close()
            return jsonify({'success': True})
        else:
            conn.rollback(); conn.close()
            return jsonify({'success': False, 'message': 'Désolé, toutes les places ont été prises !'}), 403
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ─── POST /api/admin/events ───────────────────────────────────────────────────
@app.route('/api/admin/events', methods=['POST'])
def create_event():
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    shotgun_date = (data.get('shotgun_date') or '').strip()
    total_spots = int(data.get('total_spots') or 0)
    categories = data.get('categories', [])
    if not isinstance(categories, list):
        categories = []
    categories_json = json.dumps([str(c).strip() for c in categories if str(c).strip()])

    if not name or not shotgun_date or total_spots <= 0:
        return jsonify({'success': False, 'message': 'Données invalides'}), 400

    try:
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO events (name, description, shotgun_date, total_spots, available_spots, is_active, categories) VALUES (?, ?, ?, ?, ?, 1, ?)',
            (name, description, shotgun_date, total_spots, total_spots, categories_json)
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return jsonify({'success': True, 'id': new_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ─── PUT /api/admin/events ────────────────────────────────────────────────────
@app.route('/api/admin/events', methods=['PUT'])
def update_event():
    data = request.get_json(force=True) or {}
    event_id = data.get('event_id')
    diff = int(data.get('diff', 0))
    is_active = data.get('is_active')
    categories = data.get('categories')

    if not event_id:
        return jsonify({'success': False, 'message': 'event_id manquant'}), 400

    try:
        conn = sqlite3.connect(DB_FILE, isolation_level='EXCLUSIVE')
        c = conn.cursor()
        c.execute('BEGIN EXCLUSIVE')

        if diff != 0:
            c.execute('UPDATE events SET total_spots = total_spots + ?, available_spots = available_spots + ? WHERE id = ?',
                      (diff, diff, event_id))
        if is_active is not None:
            c.execute('UPDATE events SET is_active = ? WHERE id = ?', (1 if is_active else 0, event_id))
        if categories is not None and isinstance(categories, list):
            cats_json = json.dumps([str(x).strip() for x in categories if str(x).strip()])
            c.execute('UPDATE events SET categories = ? WHERE id = ?', (cats_json, event_id))

        conn.commit(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ─── DELETE /api/admin/participants ───────────────────────────────────────────
@app.route('/api/admin/participants', methods=['DELETE'])
def delete_participant():
    data = request.get_json(force=True) or {}
    participant_id = data.get('participant_id')
    if not participant_id:
        return jsonify({'success': False, 'message': 'participant_id manquant'}), 400

    try:
        conn = sqlite3.connect(DB_FILE, isolation_level='EXCLUSIVE')
        c = conn.cursor()
        c.execute('BEGIN EXCLUSIVE')
        c.execute('SELECT event_id FROM participants WHERE id = ?', (participant_id,))
        row = c.fetchone()
        if row:
            c.execute('DELETE FROM participants WHERE id = ?', (participant_id,))
            c.execute('UPDATE events SET available_spots = available_spots + 1 WHERE id = ?', (row[0],))
            conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ─── DELETE /api/admin/events ─────────────────────────────────────────────────
@app.route('/api/admin/events', methods=['DELETE'])
def delete_event():
    data = request.get_json(force=True) or {}
    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'success': False, 'message': 'event_id manquant'}), 400

    try:
        conn = get_db()
        conn.execute('DELETE FROM participants WHERE event_id = ?', (event_id,))
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


if __name__ == '__main__':
    print('✅ Serveur démarré sur http://localhost:8000')
    app.run(host='0.0.0.0', port=8000, debug=False)
