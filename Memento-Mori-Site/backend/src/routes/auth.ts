import { Router } from 'express';
import { APP_CONFIG } from '../config';
import { db, nowIso } from '../db';

const router = Router();

router.get('/discord', (_req, res) => {
  const params = new URLSearchParams({
    client_id: APP_CONFIG.discord.clientId,
    response_type: 'code',
    scope: 'identify guilds.members.read',
    redirect_uri: APP_CONFIG.discord.redirectUri,
  });
  res.redirect(`https://discord.com/api/oauth2/authorize?${params.toString()}`);
});

router.get('/discord/callback', async (req, res) => {
  const code = req.query.code as string;
  if (!code) {
    return res.status(400).send('Missing code');
  }
  const params = new URLSearchParams();
  params.append('client_id', APP_CONFIG.discord.clientId);
  params.append('client_secret', APP_CONFIG.discord.clientSecret);
  params.append('grant_type', 'authorization_code');
  params.append('code', code);
  params.append('redirect_uri', APP_CONFIG.discord.redirectUri);
  try {
    const tokenResp = await fetch('https://discord.com/api/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params,
    });
    const tokenJson: any = await tokenResp.json();
    const userResp = await fetch('https://discord.com/api/users/@me', {
      headers: { Authorization: `${tokenJson.token_type} ${tokenJson.access_token}` },
    });
    const discordUser: any = await userResp.json();
    let member: any = null;
    if (APP_CONFIG.discord.guildId) {
      const memberResp = await fetch(
        `https://discord.com/api/users/@me/guilds/${APP_CONFIG.discord.guildId}/member`,
        {
          headers: { Authorization: `${tokenJson.token_type} ${tokenJson.access_token}` },
        },
      );
      if (memberResp.ok) {
        member = await memberResp.json();
      } else {
        console.warn('Discord member lookup failed', memberResp.status);
      }
    }
    const existing = db.prepare('SELECT * FROM users WHERE discord_id = ?').get(discordUser.id);
    const now = nowIso();
    const hasAdminRole = Boolean(
      APP_CONFIG.discord.adminRoleId && member?.roles?.includes(APP_CONFIG.discord.adminRoleId),
    );
    const isAdminId = APP_CONFIG.discord.adminIds.includes(discordUser.id);
    const resolvedRole = hasAdminRole || isAdminId ? 'admin' : 'player';
    if (existing) {
      db.prepare('UPDATE users SET discord_username = ?, display_name = ?, role = ?, last_login_at = ? WHERE id = ?')
        .run(
          discordUser.username,
          discordUser.global_name || discordUser.username,
          resolvedRole,
          now,
          existing.id,
        );
      (req as any).session.userId = existing.id;
    } else {
      const result = db
        .prepare('INSERT INTO users (discord_id, discord_username, display_name, role, created_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?)')
        .run(discordUser.id, discordUser.username, discordUser.global_name || discordUser.username, resolvedRole, now, now);
      (req as any).session.userId = result.lastInsertRowid;
    }
    res.redirect('/');
  } catch (err) {
    console.error(err);
    res.status(500).send('Auth failed');
  }
});

router.get('/me', (req, res) => {
  const sessionUserId = (req as any).session?.userId;
  if (!sessionUserId) return res.json(null);
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(sessionUserId);
  res.json(user || null);
});

router.post('/logout', (req, res) => {
  if ((req as any).session) {
    (req as any).session.destroy(() => {});
  }
  res.json({ ok: true });
});

export default router;
