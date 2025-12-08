import { Router } from 'express';
import { APP_CONFIG } from '../config';
import { requireAuth } from '../middleware/auth';
import { botSyncRequestSchema, botSyncStatusSchema } from '../utils/validation';
import { enqueueWhitelistSync, getPendingSyncs, updateSyncStatus } from '../services/botSync';

const router = Router();

const requireBridgeToken = (req: any, res: any, next: any) => {
  const token = (req.headers['x-bot-bridge-token'] as string) || '';
  if (!token || token !== APP_CONFIG.botSync.bridgeToken) {
    return res.status(401).json({ message: 'Unauthorized' });
  }
  next();
};

router.post('/whitelist', requireAuth, (req, res) => {
  const parsed = botSyncRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }

  const user = (req as any).user as { discord_id: string; discord_username: string };
  if (!user?.discord_id || !user.discord_username) {
    return res.status(400).json({ message: 'Missing Discord account information' });
  }

  const id = enqueueWhitelistSync({
    discordId: user.discord_id,
    discordUsername: user.discord_username,
    steam64Id: parsed.data.steam64Id,
    region: parsed.data.region || null,
    notes: parsed.data.notes || null,
  });

  res.json({ id, status: 'pending' });
});

router.get('/queue', requireBridgeToken, (_req, res) => {
  const pending = getPendingSyncs();
  res.json(pending);
});

router.patch('/queue/:id', requireBridgeToken, (req, res) => {
  const parsed = botSyncStatusSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: 'Invalid payload', issues: parsed.error.flatten() });
  }

  const id = Number(req.params.id);
  updateSyncStatus(id, parsed.data.status, parsed.data.errorMessage || null);
  res.json({ ok: true });
});

export default router;
