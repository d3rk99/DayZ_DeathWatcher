import { Request, Response, NextFunction } from 'express';
import { APP_CONFIG } from '../config';
import { db } from '../db';

export const requireAuth = (req: Request, res: Response, next: NextFunction) => {
  const sessionUserId = (req as any).session?.userId as number | undefined;
  if (!sessionUserId) {
    return res.status(401).json({ message: 'Unauthorized' });
  }
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(sessionUserId);
  if (!user) {
    return res.status(401).json({ message: 'Unauthorized' });
  }
  (req as any).user = user;
  return next();
};

export const requireAdmin = (req: Request, res: Response, next: NextFunction) => {
  const user = (req as any).user;
  if (!user) {
    return res.status(401).json({ message: 'Unauthorized' });
  }
  if (user.role !== 'admin' && !APP_CONFIG.discord.adminIds.includes(user.discord_id)) {
    return res.status(403).json({ message: 'Forbidden: admin only' });
  }
  next();
};
