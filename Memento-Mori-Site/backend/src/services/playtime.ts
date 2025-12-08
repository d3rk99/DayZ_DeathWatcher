import fs from 'fs';
import path from 'path';
import { db, nowIso } from '../db';
import { playSessionSchema } from '../utils/validation';
import { z } from 'zod';

export type PlaySessionPayload = z.infer<typeof playSessionSchema>;

const USERDATA_PATH = path.join(process.cwd(), 'userdata_db.json');

type UserdataEntry = {
  username?: string;
  steam_id?: string;
  guid?: string;
  playtime_seconds?: number;
};

const coerceName = (value?: string | null, fallback?: string | null) => value?.trim() || fallback || null;

const getExistingByGuidOrSteam = (guid?: string, steam64?: string | null) => {
  if (guid) {
    const row = db.prepare('SELECT * FROM player_playtime WHERE player_guid = ?').get(guid);
    if (row) return row as any;
  }
  if (steam64) {
    const row = db.prepare('SELECT * FROM player_playtime WHERE steam64 = ?').get(steam64);
    if (row) return row as any;
  }
  return null;
};

const findUserdataKey = (entries: Record<string, UserdataEntry>, guid?: string, steam64?: string | null) => {
  return Object.keys(entries).find((key) => {
    const entry = entries[key];
    return (guid && entry.guid === guid) || (steam64 && entry.steam_id === steam64);
  });
};

const updateUserdataPlaytime = (payload: PlaySessionPayload, totalSeconds: number) => {
  try {
    if (!fs.existsSync(USERDATA_PATH)) return;
    const raw = fs.readFileSync(USERDATA_PATH, 'utf-8');
    const data = JSON.parse(raw);
    const entries: Record<string, UserdataEntry> | undefined = data?.userdata;
    if (!entries) return;

    const key = findUserdataKey(entries, payload.playerGuid, payload.steam64Id);
    if (!key) return;

    const entry = entries[key];
    entry.playtime_seconds = totalSeconds;
    if (payload.playerName) {
      entry.username = payload.playerName;
    }

    fs.writeFileSync(USERDATA_PATH, JSON.stringify(data, null, 4));
  } catch (err) {
    console.warn('[playtime] Failed to write playtime into userdata_db.json', err);
  }
};

export const recordPlaySession = (payload: PlaySessionPayload) => {
  const now = nowIso();
  const existing = getExistingByGuidOrSteam(payload.playerGuid, payload.steam64Id);

  const playerGuid = existing?.player_guid || payload.playerGuid;
  const steam64 = payload.steam64Id || existing?.steam64 || null;
  const playerName = coerceName(payload.playerName, existing?.player_name);
  const totalSeconds = Number(existing?.total_seconds || 0) + Number(payload.durationSeconds || 0);

  db.prepare(
    'INSERT INTO player_sessions (player_guid, steam64, player_name, login_at, logout_at, duration_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
  ).run(playerGuid, steam64, playerName, payload.loginAt, payload.logoutAt, Math.max(0, payload.durationSeconds), now);

  db.prepare(
    `INSERT INTO player_playtime (player_guid, steam64, player_name, total_seconds, updated_at, last_session_at)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(player_guid) DO UPDATE SET
       total_seconds = excluded.total_seconds,
       updated_at = excluded.updated_at,
       last_session_at = excluded.last_session_at,
       player_name = COALESCE(excluded.player_name, player_playtime.player_name),
       steam64 = COALESCE(excluded.steam64, player_playtime.steam64)`
  ).run(playerGuid, steam64, playerName, Math.max(0, totalSeconds), now, payload.logoutAt);

  updateUserdataPlaytime(payload, Math.max(0, totalSeconds));
};

export const getTopPlaytime = (limitInput?: number) => {
  const limit = Number.isFinite(limitInput) && Number(limitInput) > 0 ? Number(limitInput) : Number.MAX_SAFE_INTEGER;
  const rows = db
    .prepare('SELECT player_guid, steam64, player_name, total_seconds, last_session_at FROM player_playtime ORDER BY total_seconds DESC LIMIT ?')
    .all(limit);
  return rows.map((row: any) => ({
    playerGuid: row.player_guid,
    steam64Id: row.steam64,
    playerName: row.player_name,
    totalSeconds: Number(row.total_seconds || 0),
    lastSessionAt: row.last_session_at,
  }));
};

export const getPlaytimeForPlayer = (steam64?: string | null, guid?: string | null) => {
  if (!steam64 && !guid) return null;
  const row = db
    .prepare('SELECT player_guid, steam64, player_name, total_seconds, last_session_at FROM player_playtime WHERE player_guid = ? OR steam64 = ?')
    .get(guid || null, steam64 || null) as any;
  if (!row) return null;
  return {
    playerGuid: row.player_guid,
    steam64Id: row.steam64,
    playerName: row.player_name,
    totalSeconds: Number(row.total_seconds || 0),
    lastSessionAt: row.last_session_at,
  };
};

export const lookupSteamFromUserdata = (discordId: string) => {
  try {
    const raw = fs.readFileSync(USERDATA_PATH, 'utf-8');
    const data = JSON.parse(raw);
    const entry = data?.userdata?.[discordId];
    if (!entry) return null;
    return {
      steam64: entry.steam_id as string | undefined,
      guid: entry.guid as string | undefined,
      username: entry.username as string | undefined,
    };
  } catch (err) {
    console.warn('[playtime] Failed to read userdata_db.json', err);
    return null;
  }
};
