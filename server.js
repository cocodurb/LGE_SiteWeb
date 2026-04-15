'use strict';

const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path    = require('path');

const app            = express();
const PORT           = process.env.PORT || 8000;
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'LaGrappe2025';
const DB_FILE = path.join(__dirname, 'database.sqlite');

// ─── OPEN DB ──────────────────────────────────────────────────────────────────
const db = new sqlite3.Database(DB_FILE);

// ─── PROMISIFY HELPERS ────────────────────────────────────────────────────────
const run  = (sql, p=[]) => new Promise((res, rej) => db.run(sql, p, function(e){ e ? rej(e) : res(this); }));
const all  = (sql, p=[]) => new Promise((res, rej) => db.all(sql, p, (e,r)=> e ? rej(e) : res(r)));
const get  = (sql, p=[]) => new Promise((res, rej) => db.get(sql, p, (e,r)=> e ? rej(e) : res(r)));

// ─── INIT DB ──────────────────────────────────────────────────────────────────
async function initDb() {
  await run('PRAGMA journal_mode=WAL');

  await run(`CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL DEFAULT '',
    shotgun_date    TEXT    NOT NULL,
    total_spots     INTEGER NOT NULL,
    available_spots INTEGER NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    categories      TEXT    NOT NULL DEFAULT '[]'
  )`);

  await run(`CREATE TABLE IF NOT EXISTS participants (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id          INTEGER NOT NULL,
    prenom            TEXT    NOT NULL,
    nom               TEXT    NOT NULL,
    email             TEXT    NOT NULL,
    categorie         TEXT    NOT NULL,
    registration_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id),
    UNIQUE(event_id, email)
  )`);

  const DEFAULT_CATS = JSON.stringify(['Sénior Homme','Sénior Femme','Vétéran Homme','Vétéran Femme']);
  for (const [col, def] of [
    ['is_active',   "INTEGER NOT NULL DEFAULT 1"],
    ['description', "TEXT NOT NULL DEFAULT ''"],
    ['categories',  `TEXT NOT NULL DEFAULT '${DEFAULT_CATS}'`],
  ]) {
    try { await run(`ALTER TABLE events ADD COLUMN ${col} ${def}`); } catch(_) {}
  }
}

// ─── PARSE EVENT ──────────────────────────────────────────────────────────────
function parseEvent(row) {
  let categories = [];
  try { categories = JSON.parse(row.categories || '[]'); } catch(_) {}
  return { ...row, categories };
}

// ─── MIDDLEWARE ───────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.static(path.join(__dirname)));

// ─── AUTH ─────────────────────────────────────────────────────────────────────
// Endpoint public de connexion
app.post('/api/login', (req, res) => {
  const { password } = req.body || {};
  if (password === ADMIN_PASSWORD) {
    res.json({ success: true, token: ADMIN_PASSWORD });
  } else {
    res.status(401).json({ success: false, message: 'Mot de passe incorrect' });
  }
});

// Middleware qui protège toutes les routes /api/admin/*
app.use('/api/admin', (req, res, next) => {
  const auth = req.headers['authorization'];
  if (auth === `Bearer ${ADMIN_PASSWORD}`) return next();
  res.status(401).json({ error: 'Non autorisé — veuillez vous connecter.' });
});

// ─── GET /api/events/active ───────────────────────────────────────────────────
app.get('/api/events/active', async (req, res) => {
  try {
    const rows = await all('SELECT * FROM events WHERE is_active = 1 ORDER BY shotgun_date ASC');
    res.json(rows.map(parseEvent));
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ─── GET /api/admin/events ────────────────────────────────────────────────────
app.get('/api/admin/events', async (req, res) => {
  try {
    const rows = await all('SELECT * FROM events ORDER BY id DESC');
    res.json(rows.map(parseEvent));
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ─── GET /api/admin/participants ──────────────────────────────────────────────
app.get('/api/admin/participants', async (req, res) => {
  try {
    const { event_id } = req.query;
    const cols = 'id, prenom, nom, email, categorie, registration_time AS time';
    let rows;
    if (event_id) {
      rows = await all(`SELECT ${cols} FROM participants WHERE event_id = ? ORDER BY id ASC`, [event_id]);
    } else {
      const evt = await get('SELECT id FROM events WHERE is_active = 1 ORDER BY id DESC LIMIT 1');
      rows = evt ? await all(`SELECT ${cols} FROM participants WHERE event_id = ? ORDER BY id ASC`, [evt.id]) : [];
    }
    res.json(rows);
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ─── POST /api/events/register ────────────────────────────────────────────────
app.post('/api/events/register', async (req, res) => {
  const { prenom, nom, email, categorie, event_id } = req.body || {};
  const p = (prenom    || '').trim();
  const n = (nom       || '').trim();
  const e = (email     || '').trim().toLowerCase();
  const c = (categorie || '').trim();

  if (!p || !n || !e || !event_id)
    return res.status(400).json({ success: false, message: 'Champs manquants' });

  try {
    // Vérifier doublon
    const dup = await get('SELECT COUNT(*) AS cnt FROM participants WHERE email = ? AND event_id = ?', [e, event_id]);
    if (dup.cnt > 0)
      return res.status(400).json({ success: false, message: 'Cet email est déjà inscrit à cet événement.' });

    // Vérifier que l'event existe et est actif
    const evt = await get('SELECT available_spots, is_active, categories FROM events WHERE id = ?', [event_id]);
    if (!evt || !evt.is_active)
      return res.status(404).json({ success: false, message: 'Événement introuvable ou archivé.' });

    let eventCategories = [];
    try { eventCategories = JSON.parse(evt.categories || '[]'); } catch(_) {}
    if (eventCategories.length > 0 && !c) {
      return res.status(400).json({ success: false, message: 'Catégorie requise pour cet événement.' });
    }

    // Tenter de décrémenter
    const info = await run(
      'UPDATE events SET available_spots = available_spots - 1 WHERE id = ? AND available_spots > 0',
      [event_id]
    );
    if (info.changes !== 1)
      return res.status(403).json({ success: false, message: 'Désolé, toutes les places ont été prises !' });

    await run('INSERT INTO participants (event_id, prenom, nom, email, categorie) VALUES (?,?,?,?,?)',
              [event_id, p, n, e, c]);
    res.json({ success: true });
  } catch(err) { res.status(500).json({ success: false, message: err.message }); }
});

// ─── POST /api/admin/events ───────────────────────────────────────────────────
app.post('/api/admin/events', async (req, res) => {
  const { name, description, shotgun_date, total_spots, categories } = req.body || {};
  const n    = (name         || '').trim();
  const d    = (description  || '').trim();
  const sd   = (shotgun_date || '').trim();
  const ts   = parseInt(total_spots) || 0;
  const cats = JSON.stringify((Array.isArray(categories) ? categories : []).map(x => String(x).trim()).filter(Boolean));

  if (!n || !sd || ts <= 0)
    return res.status(400).json({ success: false, message: 'Données invalides' });

  try {
    const info = await run(
      'INSERT INTO events (name, description, shotgun_date, total_spots, available_spots, is_active, categories) VALUES (?,?,?,?,?,1,?)',
      [n, d, sd, ts, ts, cats]
    );
    res.json({ success: true, id: info.lastID });
  } catch(err) { res.status(500).json({ success: false, message: err.message }); }
});

// ─── PUT /api/admin/events ────────────────────────────────────────────────────
app.put('/api/admin/events', async (req, res) => {
  const { event_id, diff, is_active, categories } = req.body || {};
  if (!event_id) return res.status(400).json({ success: false, message: 'event_id manquant' });

  try {
    const diffN = parseInt(diff) || 0;
    if (diffN !== 0)
      await run('UPDATE events SET total_spots = total_spots + ?, available_spots = available_spots + ? WHERE id = ?',
                [diffN, diffN, event_id]);
    if (is_active !== undefined)
      await run('UPDATE events SET is_active = ? WHERE id = ?', [is_active ? 1 : 0, event_id]);
    if (Array.isArray(categories)) {
      const cats = JSON.stringify(categories.map(x => String(x).trim()).filter(Boolean));
      await run('UPDATE events SET categories = ? WHERE id = ?', [cats, event_id]);
    }
    res.json({ success: true });
  } catch(err) { res.status(500).json({ success: false, message: err.message }); }
});

// ─── DELETE /api/admin/participants ───────────────────────────────────────────
app.delete('/api/admin/participants', async (req, res) => {
  const { participant_id } = req.body || {};
  if (!participant_id) return res.status(400).json({ success: false, message: 'participant_id manquant' });

  try {
    const row = await get('SELECT event_id FROM participants WHERE id = ?', [participant_id]);
    if (row) {
      await run('DELETE FROM participants WHERE id = ?', [participant_id]);
      await run('UPDATE events SET available_spots = available_spots + 1 WHERE id = ?', [row.event_id]);
    }
    res.json({ success: true });
  } catch(err) { res.status(500).json({ success: false, message: err.message }); }
});

// ─── DELETE /api/admin/events ─────────────────────────────────────────────────
app.delete('/api/admin/events', async (req, res) => {
  const { event_id } = req.body || {};
  if (!event_id) return res.status(400).json({ success: false, message: 'event_id manquant' });

  try {
    await run('DELETE FROM participants WHERE event_id = ?', [event_id]);
    await run('DELETE FROM events WHERE id = ?', [event_id]);
    res.json({ success: true });
  } catch(err) { res.status(500).json({ success: false, message: err.message }); }
});

// ─── START ────────────────────────────────────────────────────────────────────
initDb().then(() => {
  app.listen(PORT, () => console.log(`✅ Serveur démarré sur http://localhost:${PORT}`));
}).catch(err => {
  console.error('❌ Erreur init base de données :', err);
  process.exit(1);
});
