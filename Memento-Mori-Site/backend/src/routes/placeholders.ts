import { Router } from 'express';

const router = Router();

router.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'memento-mori-api' });
});

router.all(['/stories', '/stories/:id', '/whitelist', '/whitelist/:id', '/status', '/timeline', '/guide', '/factions', '/media', '/leaderboards'], (_req, res) => {
  res.status(501).json({ message: 'Not implemented yet - scaffold placeholder' });
});

export default router;
