import { z } from 'zod';
import { Difficulty } from '../models/types';

export const seasonSchema = z.object({
  name: z.string().min(1),
  map: z.string().min(1),
  difficulty: z.custom<Difficulty>((val) => val === 'casual' || val === 'hardcore' || val === 'custom'),
  startDate: z.string().min(1),
  endDate: z.string().optional(),
  flags: z.array(z.string()).optional(),
  currentDay: z.number().int().nonnegative().optional(),
  loreBlurb: z.string().optional(),
  isActive: z.boolean().optional(),
});

export const patchNoteSchema = z.object({
  title: z.string().min(1),
  body: z.string().min(1),
  tags: z.array(z.string()).default([]),
  seasonId: z.number().int().positive().optional(),
});

export const whitelistSchema = z.object({
  steam64Id: z.string().regex(/^\d{15,}$/),
  discordTag: z.string().min(2),
  region: z.string().optional(),
  acceptedRules: z.boolean(),
  notes: z.string().optional(),
});

export const adminWhitelistUpdateSchema = z.object({
  status: z.enum(['pending', 'approved', 'rejected']),
  adminNotes: z.string().optional(),
});

export const botSyncRequestSchema = z.object({
  steam64Id: z.string().regex(/^\d{15,}$/),
  region: z.string().optional(),
  notes: z.string().optional(),
});

export const botSyncStatusSchema = z.object({
  status: z.enum(['pending', 'processed', 'failed']),
  errorMessage: z.string().optional(),
});

export const playSessionSchema = z.object({
  playerGuid: z.string().min(1),
  playerName: z.string().optional().nullable(),
  steam64Id: z.string().regex(/^\d{15,}$/).optional().nullable(),
  loginAt: z.string().min(1),
  logoutAt: z.string().min(1),
  durationSeconds: z.number().nonnegative(),
});
