import type { Request } from 'express';
import { Router, text } from 'express';
import type { File as MulterFile } from 'multer';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import sharp from 'sharp';
import { parse } from 'csv-parse/sync';
import { v4 as uuidv4 } from 'uuid';
import { db, nowIso } from '../db';
import { requireAuth, requireAdmin } from '../middleware/auth';
import { composeMap } from '../utils/mapComposer';
import { notifyPatchNote, notifyMapExport, notifyWhitelist } from '../utils/webhooks';
import { APP_CONFIG } from '../config';
import { enqueueWhitelistSync, getPendingSyncs, updateSyncStatus } from '../services/botSync';
import { botSyncStatusSchema, whitelistSchema } from '../utils/validation';

const router = Router();
const ensureDir = (dir: string) => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
};

const toRelative = (filePath: string) => path.relative(process.cwd(), filePath).replace(/\\/g, '/');

ensureDir(APP_CONFIG.mapAssets.overlaysDir);
ensureDir(APP_CONFIG.mapAssets.awaitingDir);

const uploadDir = APP_CONFIG.mapAssets.overlaysDir;

const upload = multer({
  storage: multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, uploadDir),
    filename: (_req, file, cb) => cb(null, `${uuidv4()}${path.extname(file.originalname)}`),
  }),
  fileFilter: (_req, file, cb) => {
    if (file.mimetype !== 'image/png') return cb(new Error('Only PNG allowed'));
    cb(null, true);
  },
  limits: { fileSize: 2 * 1024 * 1024 },
});

type FileUploadRequest = Request & { file?: MulterFile };

router.get('/seasons/current', (_req, res) => {
  const season = db.prepare('SELECT * FROM seasons WHERE is_current = 1 ORDER BY start_date DESC LIMIT 1').get();
  res.json(season || null);
});

router.get('/seasons', (_req, res) => {
  const seasons = db.prepare('SELECT * FROM seasons ORDER BY start_date DESC').all();
  res.json(seasons);
});

router.post('/seasons', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  const result = db
    .prepare(
      'INSERT INTO seasons (name, map_name, difficulty, start_date, end_date, is_current, flags, lore_blurb, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
    )
    .run(body.name, body.map_name, body.difficulty, body.start_date, body.end_date, body.is_current ? 1 : 0, body.flags || null, body.lore_blurb || null, now);
  res.json({ id: result.lastInsertRowid });
});

router.put('/seasons/:id', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  db.prepare(
    'UPDATE seasons SET name=?, map_name=?, difficulty=?, start_date=?, end_date=?, is_current=?, flags=?, lore_blurb=? WHERE id=?',
  ).run(body.name, body.map_name, body.difficulty, body.start_date, body.end_date, body.is_current ? 1 : 0, body.flags || null, body.lore_blurb || null, req.params.id);
  res.json({ ok: true });
});

router.get('/patch-notes', (req, res) => {
  const seasonId = req.query.seasonId as string | undefined;
  const rows = seasonId
    ? db.prepare('SELECT * FROM patch_notes WHERE season_id = ? ORDER BY created_at DESC').all(seasonId)
    : db.prepare('SELECT * FROM patch_notes ORDER BY created_at DESC').all();
  res.json(rows);
});

router.post('/patch-notes', requireAuth, requireAdmin, async (req, res) => {
  const body = req.body;
  const now = nowIso();
  const result = db
    .prepare('INSERT INTO patch_notes (season_id, title, body_markdown, tags, created_at) VALUES (?, ?, ?, ?, ?)')
    .run(body.season_id || null, body.title, body.body_markdown, body.tags || null, now);
  await notifyPatchNote(body.title);
  res.json({ id: result.lastInsertRowid });
});

router.get('/stories', (req, res) => {
  const { seasonId, status } = req.query;
  const statusFilter = (status as string) || 'approved';
  const rows = seasonId
    ? db.prepare('SELECT * FROM stories WHERE season_id = ? AND status = ? ORDER BY created_at DESC').all(seasonId, statusFilter)
    : db.prepare('SELECT * FROM stories WHERE status = ? ORDER BY created_at DESC').all(statusFilter);
  res.json(rows);
});

router.post('/stories', requireAuth, (req, res) => {
  const body = req.body;
  const user = (req as any).user;
  const now = nowIso();
  const result = db
    .prepare(
      'INSERT INTO stories (season_id, title, author_name, author_user_id, body_markdown, screenshot_url, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    )
    .run(body.season_id || null, body.title, body.author_name || user.display_name || user.discord_username, user.id, body.body_markdown, body.screenshot_url || null, 'pending', now);
  res.json({ id: result.lastInsertRowid, status: 'pending' });
});

router.get('/stories/pending', requireAuth, requireAdmin, (_req, res) => {
  const rows = db.prepare('SELECT * FROM stories WHERE status = ? ORDER BY created_at ASC').all('pending');
  res.json(rows);
});

router.patch('/stories/:id', requireAuth, requireAdmin, (req, res) => {
  const { status } = req.body;
  const now = nowIso();
  db.prepare('UPDATE stories SET status = ?, approved_at = ?, approved_by_user_id = ? WHERE id = ?')
    .run(status, now, (req as any).user.id, req.params.id);
  res.json({ ok: true });
});

router.post('/whitelist', requireAuth, (req, res) => {
  const parsed = whitelistSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }

  const user = (req as any).user;
  const id = enqueueWhitelistSync({
    discordId: user.discord_id,
    discordUsername: user.discord_username,
    steam64Id: parsed.data.steam64Id,
    region: parsed.data.region || null,
    notes: parsed.data.notes || null,
  });

  res.json({ id, status: 'pending' });
});

router.get('/whitelist/pending', requireAuth, requireAdmin, (_req, res) => {
  const rows = getPendingSyncs();
  res.json(rows);
});

router.patch('/whitelist/:id', requireAuth, requireAdmin, async (req, res) => {
  const parsed = botSyncStatusSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }

  const { status, errorMessage } = parsed.data;
  const existing = db.prepare('SELECT * FROM bot_sync_queue WHERE id = ?').get(req.params.id);
  updateSyncStatus(Number(req.params.id), status, errorMessage || null);
  if (existing) await notifyWhitelist(existing.discord_username, status);
  res.json({ ok: true });
});

router.get('/status', (_req, res) => {
  res.json({ online: true, players: 12, maxPlayers: 60, lastRestart: 'recent', map: 'Chernarus' });
});

router.get('/timeline', (req, res) => {
  const { seasonId } = req.query;
  const rows = seasonId
    ? db.prepare('SELECT * FROM timeline_events WHERE season_id = ? ORDER BY event_time DESC').all(seasonId)
    : db.prepare('SELECT * FROM timeline_events ORDER BY event_time DESC').all();
  res.json(rows);
});

router.post('/timeline', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  const result = db
    .prepare('INSERT INTO timeline_events (season_id, title, description, type, event_time, created_at) VALUES (?, ?, ?, ?, ?, ?)')
    .run(body.season_id || null, body.title, body.description, body.type, body.event_time, now);
  res.json({ id: result.lastInsertRowid });
});

router.put('/timeline/:id', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  db.prepare('UPDATE timeline_events SET title=?, description=?, type=?, event_time=?, season_id=? WHERE id=?')
    .run(body.title, body.description, body.type, body.event_time, body.season_id || null, req.params.id);
  res.json({ ok: true });
});

router.delete('/timeline/:id', requireAuth, requireAdmin, (req, res) => {
  db.prepare('DELETE FROM timeline_events WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

router.get('/guide', (req, res) => {
  const { seasonId } = req.query;
  const rows = seasonId
    ? db.prepare('SELECT * FROM guide_sections WHERE season_id = ? ORDER BY display_order ASC').all(seasonId)
    : db.prepare('SELECT * FROM guide_sections WHERE season_id IS NULL OR season_id = ? ORDER BY display_order ASC').all(null);
  res.json(rows);
});

router.post('/guide', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  const result = db
    .prepare('INSERT INTO guide_sections (season_id, title, body_markdown, display_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)')
    .run(body.season_id || null, body.title, body.body_markdown, body.display_order || 0, now, now);
  res.json({ id: result.lastInsertRowid });
});

router.put('/guide/:id', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  db.prepare('UPDATE guide_sections SET title=?, body_markdown=?, display_order=?, season_id=?, updated_at=? WHERE id=?')
    .run(body.title, body.body_markdown, body.display_order || 0, body.season_id || null, now, req.params.id);
  res.json({ ok: true });
});

router.delete('/guide/:id', requireAuth, requireAdmin, (req, res) => {
  db.prepare('DELETE FROM guide_sections WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

router.get('/factions', (req, res) => {
  const { seasonId, recruiting, tag } = req.query;
  let query = 'SELECT * FROM factions WHERE 1=1';
  const params: any[] = [];
  if (seasonId) {
    query += ' AND season_id = ?';
    params.push(seasonId);
  }
  if (recruiting) {
    query += ' AND recruiting = ?';
    params.push(recruiting === 'true' ? 1 : 0);
  }
  if (tag) {
    query += ' AND playstyle_tags LIKE ?';
    params.push(`%${tag}%`);
  }
  const rows = db.prepare(`${query} ORDER BY created_at DESC`).all(...params);
  res.json(rows);
});

router.post('/factions', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  const result = db
    .prepare('INSERT INTO factions (name, description, playstyle_tags, recruiting, territory, contact, emblem_url, season_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
    .run(body.name, body.description, body.playstyle_tags || null, body.recruiting ? 1 : 0, body.territory || null, body.contact || null, body.emblem_url || null, body.season_id || null, now, now);
  res.json({ id: result.lastInsertRowid });
});

router.put('/factions/:id', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  db.prepare('UPDATE factions SET name=?, description=?, playstyle_tags=?, recruiting=?, territory=?, contact=?, emblem_url=?, season_id=?, updated_at=? WHERE id=?')
    .run(body.name, body.description, body.playstyle_tags || null, body.recruiting ? 1 : 0, body.territory || null, body.contact || null, body.emblem_url || null, body.season_id || null, now, req.params.id);
  res.json({ ok: true });
});

router.delete('/factions/:id', requireAuth, requireAdmin, (req, res) => {
  db.prepare('DELETE FROM factions WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

router.get('/media', (req, res) => {
  const { seasonId, type, tag } = req.query;
  let query = 'SELECT * FROM media_items WHERE 1=1';
  const params: any[] = [];
  if (seasonId) {
    query += ' AND season_id = ?';
    params.push(seasonId);
  }
  if (type) {
    query += ' AND type = ?';
    params.push(type);
  }
  if (tag) {
    query += ' AND tags LIKE ?';
    params.push(`%${tag}%`);
  }
  const rows = db.prepare(`${query} ORDER BY display_order ASC`).all(...params);
  res.json(rows);
});

router.post('/media', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  const result = db
    .prepare('INSERT INTO media_items (type, title, description, url, thumbnail_url, season_id, tags, display_order, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)')
    .run(body.type, body.title, body.description || null, body.url, body.thumbnail_url || null, body.season_id || null, body.tags || null, body.display_order || 0, now);
  res.json({ id: result.lastInsertRowid });
});

router.put('/media/:id', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  db.prepare('UPDATE media_items SET type=?, title=?, description=?, url=?, thumbnail_url=?, season_id=?, tags=?, display_order=? WHERE id=?')
    .run(body.type, body.title, body.description || null, body.url, body.thumbnail_url || null, body.season_id || null, body.tags || null, body.display_order || 0, req.params.id);
  res.json({ ok: true });
});

router.delete('/media/:id', requireAuth, requireAdmin, (req, res) => {
  db.prepare('DELETE FROM media_items WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

router.get('/leaderboards', (req, res) => {
  const { seasonId, category } = req.query;
  let query = 'SELECT * FROM stats_entries WHERE 1=1';
  const params: any[] = [];
  if (seasonId) {
    query += ' AND season_id = ?';
    params.push(seasonId);
  }
  if (category) {
    query += ' AND category = ?';
    params.push(category);
  }
  const rows = db.prepare(`${query} ORDER BY value DESC`).all(...params);
  res.json(rows);
});

router.post('/leaderboards/import', text({ type: ['text/*', 'application/csv'] }), requireAuth, requireAdmin, (req, res) => {
  const contentType = req.header('content-type') || '';
  let entries: any[] = [];
  if (contentType.includes('application/json')) {
    entries = Array.isArray(req.body) ? req.body : req.body.entries || [];
  } else {
    const text = typeof req.body === 'string' ? req.body : '';
    entries = parse(text, { columns: true, skip_empty_lines: true });
  }
  const now = nowIso();
  const stmt = db.prepare('INSERT INTO stats_entries (season_id, player_name, category, value, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)');
  const insertMany = db.transaction((rows: any[]) => {
    rows.forEach((r) => stmt.run(r.season_id, r.player_name, r.category, Number(r.value), r.metadata_json || null, now));
  });
  insertMany(entries);
  res.json({ inserted: entries.length });
});

router.post('/map/marker-assets', requireAuth, upload.single('file'), async (req: FileUploadRequest, res) => {
  const file = req.file;
  if (!file) return res.status(400).json({ message: 'File missing' });
  try {
    const image = sharp(file.path);
    const meta = await image.metadata();
    await image.resize({ width: 512, height: 512, fit: 'inside' }).png({ force: true }).toFile(file.path);
    const resized = await sharp(file.path).metadata();
    const width = resized.width || meta.width || 0;
    const height = resized.height || meta.height || 0;
    const now = nowIso();
    const result = db
      .prepare('INSERT INTO marker_assets (uploader_user_id, original_filename, storage_path, width_px, height_px, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)')
      .run((req as any).user.id, file.originalname, file.path, width, height, 'uploaded', now);
    res.json({ id: result.lastInsertRowid, width, height, url: `/${toRelative(file.path)}` });
  } catch (err: any) {
    res.status(400).json({ message: err.message });
  }
});

router.post('/map/marker-placements', requireAuth, (req, res) => {
  const body = req.body;
  const asset = db.prepare('SELECT * FROM marker_assets WHERE id = ?').get(body.asset_id);
  if (!asset) return res.status(404).json({ message: 'Unknown asset' });
  const awaitingPath = path.join(APP_CONFIG.mapAssets.awaitingDir, path.basename(asset.storage_path));
  try {
    if (asset.storage_path !== awaitingPath) {
      ensureDir(APP_CONFIG.mapAssets.awaitingDir);
      fs.renameSync(asset.storage_path, awaitingPath);
    }
    db.prepare('UPDATE marker_assets SET storage_path = ?, status = ? WHERE id = ?').run(awaitingPath, 'pending', body.asset_id);
  } catch (err: any) {
    return res.status(400).json({ message: err.message });
  }
  const now = nowIso();
  const result = db
    .prepare(
      'INSERT INTO marker_placements (asset_id, map_id, season_id, x_norm, y_norm, scale, rotation_deg, label, description, created_by_user_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
    )
    .run(body.asset_id, body.map_id || null, body.season_id || null, body.x_norm, body.y_norm, body.scale, body.rotation_deg || 0, body.label || null, body.description || null, (req as any).user.id, 'pending', now);
  res.json({ id: result.lastInsertRowid, status: 'pending' });
});

router.get('/map/marker-placements', (req, res) => {
  const { mapId, status } = req.query;
  const rows = db
    .prepare('SELECT * FROM marker_placements WHERE (map_id = ? OR ? IS NULL) AND status = ?')
    .all(mapId || null, mapId || null, status || 'approved');
  res.json(rows);
});

router.get('/map/marker-placements/pending', requireAuth, requireAdmin, (_req, res) => {
  const rows = db.prepare('SELECT * FROM marker_placements WHERE status = ?').all('pending');
  res.json(rows);
});

router.patch('/map/marker-placements/:id', requireAuth, requireAdmin, (req, res) => {
  const body = req.body;
  const now = nowIso();
  db.prepare(
    'UPDATE marker_placements SET status=?, approved_at=?, approved_by_user_id=?, x_norm=?, y_norm=?, scale=?, rotation_deg=? WHERE id=?',
  ).run(body.status, now, (req as any).user.id, body.x_norm, body.y_norm, body.scale, body.rotation_deg || 0, req.params.id);
  res.json({ ok: true });
});

router.post('/map/export', requireAuth, requireAdmin, async (req, res) => {
  const { mapName, season_id } = req.body;
  const placements = db
    .prepare(
      'SELECT marker_placements.*, marker_assets.storage_path, marker_assets.width_px, marker_assets.height_px FROM marker_placements JOIN marker_assets ON marker_placements.asset_id = marker_assets.id WHERE marker_placements.status = "approved" AND (marker_placements.map_id = ? OR ? IS NULL)',
    )
    .all(mapName || null, mapName || null);
  const result = await composeMap(mapName, placements as any);
  const now = nowIso();
  const basePath = path.join(APP_CONFIG.mapAssets.templateDir, `${mapName}.png`);
  const relativeBase = `/${toRelative(basePath)}`;
  const relativeComposite = `/${toRelative(result.outputPath)}`;
  const layer = db
    .prepare('INSERT INTO map_layers (map_name, season_id, base_image_path, composite_image_path, version_number, created_at) VALUES (?, ?, ?, ?, ?, ?)')
    .run(mapName, season_id || null, relativeBase, relativeComposite, result.version, now);
  await notifyMapExport(`${mapName} v${result.version}`);
  res.json({ id: layer.lastInsertRowid, version: result.version, path: relativeComposite });
});

router.get('/map/latest', (_req, res) => {
  const row = db.prepare('SELECT * FROM map_layers ORDER BY created_at DESC LIMIT 1').get();
  const normalize = (p: string | null) => {
    if (!p) return p;
    return p.startsWith('/') ? p : `/${toRelative(p)}`;
  };
  if (row) {
    row.base_image_path = normalize(row.base_image_path);
    row.composite_image_path = normalize(row.composite_image_path);
  }
  res.json(row || null);
});

router.get('/map/assets', (_req, res) => {
  const findLatestPng = (dir: string) => {
    if (!fs.existsSync(dir)) return null;
    const pngs = fs
      .readdirSync(dir)
      .filter((f) => f.toLowerCase().endsWith('.png'))
      .map((file) => ({ file, mtime: fs.statSync(path.join(dir, file)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
    if (!pngs.length) return null;
    return `/${toRelative(path.join(dir, pngs[0].file))}`;
  };

  res.json({
    template: findLatestPng(APP_CONFIG.mapAssets.templateDir),
    current: findLatestPng(APP_CONFIG.mapAssets.currentDir),
  });
});

export default router;
