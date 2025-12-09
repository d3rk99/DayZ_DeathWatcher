import { Request, Response, NextFunction } from 'express';
import { APP_CONFIG } from '../config';
import { db } from '../db';

export type SessionUser = {
  discordId: string;
  username: string;
  avatar: string | null;
  isAdmin: boolean;
  userId?: number;
};

export const requireAuth = (req: Request, res: Response, next: NextFunction) => {
  const sessionUser = (req as any).session?.user as SessionUser | undefined;
  if (!sessionUser) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  const user = db.prepare('SELECT * FROM users WHERE discord_id = ?').get(sessionUser.discordId);
  if (!user) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  sessionUser.userId = user.id;
  (req as any).user = user;
  return next();
};

export const requireAdmin = (req: Request, res: Response, next: NextFunction) => {
  const sessionUser = (req as any).session?.user as SessionUser | undefined;
  if (!sessionUser) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  if (!sessionUser.isAdmin) {
    return res.status(403).json({ message: 'Forbidden: admin only' });
  }

  const user = (req as any).user;
  if (!user && APP_CONFIG.discord.adminRoleId) {
    return res.status(403).json({ message: 'Forbidden: admin only' });
  }

  next();
};
