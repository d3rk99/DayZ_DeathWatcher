import { db, nowIso } from '../db';

export type BotSyncStatus = 'pending' | 'processed' | 'failed';

export type BotSyncRecord = {
  id: number;
  discord_id: string;
  discord_username: string;
  steam64: string;
  region?: string | null;
  notes?: string | null;
  status: BotSyncStatus;
  error_message?: string | null;
  created_at: string;
  processed_at?: string | null;
};

type EnqueueOptions = {
  steam64Id: string;
  discordId: string;
  discordUsername: string;
  region?: string | null;
  notes?: string | null;
};

export const enqueueWhitelistSync = (options: EnqueueOptions) => {
  const now = nowIso();
  const result = db
    .prepare(
      'INSERT OR REPLACE INTO bot_sync_queue (discord_id, discord_username, steam64, region, notes, status, created_at, processed_at, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT processed_at FROM bot_sync_queue WHERE discord_id = ?), NULL), NULL)',
    )
    .run(
      options.discordId,
      options.discordUsername,
      options.steam64Id,
      options.region || null,
      options.notes || null,
      'pending',
      now,
      options.discordId,
    );
  return Number(result.lastInsertRowid);
};

export const getPendingSyncs = (): BotSyncRecord[] => {
  return db.prepare("SELECT * FROM bot_sync_queue WHERE status = 'pending' ORDER BY created_at ASC").all() as BotSyncRecord[];
};

export const updateSyncStatus = (id: number, status: BotSyncStatus, errorMessage?: string | null) => {
  const now = nowIso();
  db.prepare('UPDATE bot_sync_queue SET status = ?, processed_at = ?, error_message = ? WHERE id = ?')
    .run(status, status === 'pending' ? null : now, errorMessage || null, id);
};
