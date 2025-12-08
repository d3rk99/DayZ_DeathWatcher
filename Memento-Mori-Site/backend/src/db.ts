import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { APP_CONFIG } from './config';

const dataDir = path.dirname(APP_CONFIG.databasePath);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

export const db = new Database(APP_CONFIG.databasePath);

db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL UNIQUE,
    discord_username TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'player',
    created_at TEXT NOT NULL,
    last_login_at TEXT
  );

  CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    map_name TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    is_current INTEGER DEFAULT 0,
    flags TEXT,
    lore_blurb TEXT,
    created_at TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS patch_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER,
    title TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    tags TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );

  CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER,
    title TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_user_id INTEGER,
    body_markdown TEXT NOT NULL,
    screenshot_url TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    approved_by_user_id INTEGER,
    FOREIGN KEY (season_id) REFERENCES seasons(id),
    FOREIGN KEY (author_user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS whitelist_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    steam64 TEXT NOT NULL,
    discord_tag TEXT NOT NULL,
    region TEXT,
    notes TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    handled_by_user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );

  CREATE TABLE IF NOT EXISTS guide_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER,
    title TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );

  CREATE TABLE IF NOT EXISTS factions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    playstyle_tags TEXT,
    recruiting INTEGER NOT NULL DEFAULT 0,
    territory TEXT,
    contact TEXT,
    emblem_url TEXT,
    season_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );

  CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    thumbnail_url TEXT,
    season_id INTEGER,
    tags TEXT,
    display_order INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );

  CREATE TABLE IF NOT EXISTS stats_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    category TEXT NOT NULL,
    value REAL NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );

  CREATE TABLE IF NOT EXISTS marker_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uploader_user_id INTEGER,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    width_px INTEGER,
    height_px INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (uploader_user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS marker_placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    map_id TEXT,
    season_id INTEGER,
    x_norm REAL NOT NULL,
    y_norm REAL NOT NULL,
    scale REAL NOT NULL,
    rotation_deg REAL DEFAULT 0,
    label TEXT,
    description TEXT,
    created_by_user_id INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    approved_by_user_id INTEGER,
    FOREIGN KEY (asset_id) REFERENCES marker_assets(id),
    FOREIGN KEY (season_id) REFERENCES seasons(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS map_layers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_name TEXT NOT NULL,
    season_id INTEGER,
    base_image_path TEXT,
    composite_image_path TEXT,
    version_number INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id)
  );
`);

export const serializeArray = (value?: string[]) => (value ? JSON.stringify(value) : null);
export const deserializeArray = (raw?: string | null): string[] | undefined =>
  raw ? (JSON.parse(raw) as string[]) : undefined;

export const nowIso = () => new Date().toISOString();
