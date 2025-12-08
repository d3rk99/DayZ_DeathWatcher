import { Router } from 'express';
import { requireAdmin } from '../middleware/auth';
import { createSeason, getSeasonById, listSeasons, updateSeason, activateSeason } from '../services/seasonsService';
import { seasonSchema } from '../utils/validation';

const router = Router();

router.get('/', (req, res) => {
  const active = req.query.active === 'true';
  const includePast = req.query.includePast === 'true';
  const seasons = listSeasons({ active, includePast });
  res.json(seasons);
});

router.get('/:id', (req, res) => {
  const season = getSeasonById(Number(req.params.id));
  if (!season) return res.status(404).json({ message: 'Season not found' });
  res.json(season);
});

router.post('/', requireAdmin, (req, res) => {
  const parsed = seasonSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }
  const { name, map, difficulty, startDate, endDate, flags, currentDay, loreBlurb } = parsed.data;
  const season = createSeason({
    name,
    map,
    difficulty,
    startDate,
    endDate,
    flags,
    currentDay,
    loreBlurb,
    isActive: Boolean(parsed.data.isActive),
  });
  res.status(201).json(season);
});

router.patch('/:id', requireAdmin, (req, res) => {
  const parsed = seasonSchema.partial().safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }
  const updated = updateSeason(Number(req.params.id), parsed.data);
  if (!updated) return res.status(404).json({ message: 'Season not found' });
  res.json(updated);
});

router.post('/:id/activate', requireAdmin, (req, res) => {
  const season = activateSeason(Number(req.params.id));
  if (!season) return res.status(404).json({ message: 'Season not found' });
  res.json(season);
});

export default router;
