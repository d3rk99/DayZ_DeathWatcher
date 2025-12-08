import path from 'path';
import dotenv from 'dotenv';

dotenv.config();

export const APP_CONFIG = {
  port: Number(process.env.PORT) || 3001,
  databasePath: process.env.DB_PATH || path.join(process.cwd(), 'data', 'memento.db'),
  sessionSecret: process.env.SESSION_SECRET || 'dev-secret',
  discord: {
    clientId: process.env.DISCORD_CLIENT_ID || '',
    clientSecret: process.env.DISCORD_CLIENT_SECRET || '',
    redirectUri: process.env.DISCORD_REDIRECT_URI || 'http://localhost:3001/auth/discord/callback',
    adminIds: (process.env.DISCORD_ADMIN_IDS || '').split(',').filter(Boolean),
  },
  discordWebhook: {
    patchNotes: process.env.DISCORD_WEBHOOK_URL_patch_notes || '',
    map: process.env.DISCORD_WEBHOOK_URL_map || '',
    whitelist: process.env.DISCORD_WEBHOOK_URL_whitelist || '',
  },
  uploadsDir: process.env.UPLOADS_DIR || path.join(process.cwd(), 'uploads'),
  mapBaseDir: process.env.MAP_BASE_DIR || path.join(process.cwd(), 'maps'),
  generatedDir: process.env.GENERATED_DIR || path.join(process.cwd(), 'generated'),
  mapAssets: {
    templateDir: process.env.MAP_TEMPLATE_DIR || path.join(process.cwd(), 'maps', 'template'),
    currentDir: process.env.MAP_CURRENT_DIR || path.join(process.cwd(), 'maps', 'current'),
    overlaysDir: process.env.MAP_OVERLAYS_DIR || path.join(process.cwd(), 'maps', 'overlays'),
    awaitingDir: process.env.MAP_AWAITING_DIR || path.join(process.cwd(), 'maps', 'awaiting-approval'),
  },
};

export const ensureEnvReady = () => {
  if (!process.env.PORT) {
    console.warn('[config] Using default PORT 3001');
  }
};
