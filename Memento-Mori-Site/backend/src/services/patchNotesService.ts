import { db, deserializeArray, nowIso, serializeArray } from '../db';
import { PatchNote } from '../models/types';

const mapRowToPatchNote = (row: any): PatchNote => ({
  id: row.id,
  title: row.title,
  body: row.body,
  tags: deserializeArray(row.tags) ?? [],
  seasonId: row.seasonId ?? undefined,
  createdAt: row.createdAt,
  updatedAt: row.updatedAt,
});

export const createPatchNote = (payload: Omit<PatchNote, 'id' | 'createdAt' | 'updatedAt'>): PatchNote => {
  const timestamp = nowIso();
  const result = db.prepare(`
    INSERT INTO patch_notes (title, body, tags, seasonId, createdAt, updatedAt)
    VALUES (@title, @body, @tags, @seasonId, @createdAt, @updatedAt)
  `).run({
    ...payload,
    tags: serializeArray(payload.tags) ?? '[]',
    createdAt: timestamp,
    updatedAt: timestamp,
  });

  const created = getPatchNoteById(result.lastInsertRowid as number);
  if (!created) throw new Error('Failed to create patch note');
  return created;
};

export const listPatchNotes = (filters?: { tag?: string; seasonId?: number }): PatchNote[] => {
  let query = 'SELECT * FROM patch_notes';
  const clauses: string[] = [];
  const params: any[] = [];

  if (filters?.tag) {
    clauses.push('json_extract(tags, "$") LIKE ?');
    params.push(`%${filters.tag}%`);
  }
  if (filters?.seasonId) {
    clauses.push('seasonId = ?');
    params.push(filters.seasonId);
  }

  if (clauses.length) {
    query += ` WHERE ${clauses.join(' AND ')}`;
  }
  query += ' ORDER BY createdAt DESC';

  const rows = db.prepare(query).all(...params);
  return rows.map(mapRowToPatchNote);
};

export const getPatchNoteById = (id: number): PatchNote | null => {
  const row = db.prepare('SELECT * FROM patch_notes WHERE id = ?').get(id);
  return row ? mapRowToPatchNote(row) : null;
};
