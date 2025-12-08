import { db, deserializeArray, nowIso, serializeArray } from '../db';
import { Season } from '../models/types';

const mapRowToSeason = (row: any): Season => ({
  id: row.id,
  name: row.name,
  map: row.map,
  difficulty: row.difficulty,
  startDate: row.startDate,
  endDate: row.endDate ?? undefined,
  flags: deserializeArray(row.flags),
  currentDay: row.currentDay ?? undefined,
  loreBlurb: row.loreBlurb ?? undefined,
  isActive: Boolean(row.isActive),
  createdAt: row.createdAt,
  updatedAt: row.updatedAt,
});

export const listSeasons = (options?: { active?: boolean; includePast?: boolean }) => {
  if (options?.active) {
    const row = db.prepare('SELECT * FROM seasons WHERE isActive = 1 ORDER BY startDate DESC LIMIT 1').get();
    return row ? [mapRowToSeason(row)] : [];
  }

  const rows = db.prepare('SELECT * FROM seasons ORDER BY startDate DESC').all();
  return rows.map(mapRowToSeason);
};

export const getSeasonById = (id: number): Season | null => {
  const row = db.prepare('SELECT * FROM seasons WHERE id = ?').get(id);
  return row ? mapRowToSeason(row) : null;
};

export const createSeason = (payload: Omit<Season, 'id' | 'createdAt' | 'updatedAt'>): Season => {
  const timestamp = nowIso();
  const insert = db.prepare(`
    INSERT INTO seasons (name, map, difficulty, startDate, endDate, flags, currentDay, loreBlurb, isActive, createdAt, updatedAt)
    VALUES (@name, @map, @difficulty, @startDate, @endDate, @flags, @currentDay, @loreBlurb, @isActive, @createdAt, @updatedAt)
  `);

  const result = insert.run({
    ...payload,
    flags: serializeArray(payload.flags),
    isActive: payload.isActive ? 1 : 0,
    createdAt: timestamp,
    updatedAt: timestamp,
  });

  if (payload.isActive) {
    db.prepare('UPDATE seasons SET isActive = 0 WHERE id != ?').run(result.lastInsertRowid as number);
  }

  const created = getSeasonById(result.lastInsertRowid as number);
  if (!created) throw new Error('Failed to create season');
  return created;
};

export const updateSeason = (id: number, payload: Partial<Omit<Season, 'id' | 'createdAt' | 'updatedAt'>>) => {
  const existing = getSeasonById(id);
  if (!existing) return null;

  const updated = {
    ...existing,
    ...payload,
    flags: payload.flags ?? existing.flags,
    updatedAt: nowIso(),
  };

  db.prepare(`
    UPDATE seasons SET
      name = @name,
      map = @map,
      difficulty = @difficulty,
      startDate = @startDate,
      endDate = @endDate,
      flags = @flags,
      currentDay = @currentDay,
      loreBlurb = @loreBlurb,
      isActive = @isActive,
      updatedAt = @updatedAt
    WHERE id = @id
  `).run({
    ...updated,
    flags: serializeArray(updated.flags),
    isActive: updated.isActive ? 1 : 0,
    id,
  });

  if (updated.isActive) {
    db.prepare('UPDATE seasons SET isActive = 0 WHERE id != ?').run(id);
  }

  return getSeasonById(id);
};

export const activateSeason = (id: number) => {
  const existing = getSeasonById(id);
  if (!existing) return null;
  db.prepare('UPDATE seasons SET isActive = CASE WHEN id = ? THEN 1 ELSE 0 END, updatedAt = ?').run(id, nowIso());
  return getSeasonById(id);
};
