import { Router } from 'express';
import { requireAdmin } from '../middleware/auth';
import { createPatchNote, getPatchNoteById, listPatchNotes } from '../services/patchNotesService';
import { patchNoteSchema } from '../utils/validation';

const router = Router();

router.get('/', (req, res) => {
  const tag = typeof req.query.tag === 'string' ? req.query.tag : undefined;
  const seasonId = req.query.seasonId ? Number(req.query.seasonId) : undefined;
  const notes = listPatchNotes({ tag, seasonId });
  res.json(notes);
});

router.get('/:id', (req, res) => {
  const note = getPatchNoteById(Number(req.params.id));
  if (!note) return res.status(404).json({ message: 'Patch note not found' });
  res.json(note);
});

router.post('/', requireAdmin, (req, res) => {
  const parsed = patchNoteSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }
  const { title, body, tags, seasonId } = parsed.data;
  const created = createPatchNote({ title, body, tags, seasonId });
  // Placeholder: trigger webhook if configured
  res.status(201).json(created);
});

export default router;
