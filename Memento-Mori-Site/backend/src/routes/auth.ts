import { Router } from 'express';
import { APP_CONFIG } from '../config';
import { db, nowIso } from '../db';
import { SessionUser } from '../middleware/auth';

type DiscordUser = {
  id: string;
  username: string;
  global_name?: string | null;
  avatar?: string | null;
};

type DiscordMember = {
  roles?: string[];
} | null;

const getDiscordUser = async (accessToken: string): Promise<DiscordUser> => {
  const userResp = await fetch('https://discord.com/api/users/@me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!userResp.ok) {
    throw new Error(`Failed to fetch Discord user: ${userResp.status}`);
  }

  return (await userResp.json()) as DiscordUser;
};

const getDiscordGuildMember = async (accessToken: string, guildId: string): Promise<DiscordMember> => {
  if (!guildId) return null;

  const memberResp = await fetch(`https://discord.com/api/users/@me/guilds/${guildId}/member`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!memberResp.ok) {
    console.warn('Discord member lookup failed', memberResp.status);
    return null;
  }

  return (await memberResp.json()) as DiscordMember;
};

const userIsAdmin = (discordId: string, roles: string[] | undefined | null, adminRoleId: string) => {
  const allowlisted = APP_CONFIG.discord.adminIds.includes(discordId);
  if (allowlisted) return true;
  if (!roles || !adminRoleId) return false;
  return roles.includes(adminRoleId);
};

const deriveRedirectUriFromRequest = (req: any) => {
  const host = req?.get?.('host');
  const forwardedProto = (req?.headers?.['x-forwarded-proto'] as string) || '';
  const protocol = forwardedProto.split(',')[0]?.trim() || req?.protocol || 'http';
  if (!host) {
    console.warn('Missing host header when resolving Discord redirect URI');
    return 'http://localhost:3001/auth/discord/callback';
  }
  return `${protocol}://${host}/auth/discord/callback`;
};

const resolveRedirectUri = (req: any) => {
  const configured = APP_CONFIG.discord.redirectUri;
  const derived = deriveRedirectUriFromRequest(req);
  const isLocalConfigured = configured?.includes('localhost');
  const requestHost = req?.get?.('host') || '';

  if (configured && (!isLocalConfigured || requestHost.includes('localhost'))) {
    return configured;
  }

  return derived;
};

const router = Router();

router.get('/discord', (req, res) => {
  const redirectUri = resolveRedirectUri(req);
  const params = new URLSearchParams({
    client_id: APP_CONFIG.discord.clientId,
    response_type: 'code',
    scope: 'identify guilds.members.read',
    redirect_uri: redirectUri,
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
  params.append('redirect_uri', resolveRedirectUri(req));
  try {
    const tokenResp = await fetch('https://discord.com/api/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params,
    });
    if (!tokenResp.ok) {
      const errorBody = await tokenResp.text();
      console.error('Token exchange failed', tokenResp.status, errorBody);
      return res.status(400).send('Discord authorization failed');
    }

    const tokenJson: any = await tokenResp.json();
    const accessToken = tokenJson.access_token as string;

    const discordUser = await getDiscordUser(accessToken);
    const member = await getDiscordGuildMember(accessToken, APP_CONFIG.discord.guildId);

    const hasAdminRole = userIsAdmin(discordUser.id, member?.roles, APP_CONFIG.discord.adminRoleId);
    const resolvedRole = hasAdminRole ? 'admin' : 'player';
    const now = nowIso();
    const displayName = discordUser.global_name || discordUser.username;
    const avatarUrl = discordUser.avatar
      ? `https://cdn.discordapp.com/avatars/${discordUser.id}/${discordUser.avatar}.png?size=64`
      : null;

    const existing = db.prepare('SELECT * FROM users WHERE discord_id = ?').get(discordUser.id);

    if (existing) {
      db.prepare('UPDATE users SET discord_username = ?, display_name = ?, role = ?, last_login_at = ? WHERE id = ?').run(
        discordUser.username,
        displayName,
        resolvedRole,
        now,
        existing.id,
      );
    } else {
      db.prepare(
        'INSERT INTO users (discord_id, discord_username, display_name, role, created_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?)',
      ).run(discordUser.id, discordUser.username, displayName, resolvedRole, now, now);
    }

    const sessionUser: SessionUser = {
      discordId: discordUser.id,
      username: displayName,
      avatar: avatarUrl,
      isAdmin: hasAdminRole,
    };

    if ((req as any).session) {
      (req as any).session.user = sessionUser as any;
    }

    res.redirect('/');
  } catch (err) {
    console.error(err);
    res.status(500).send('Auth failed');
  }
});

router.get('/me', (req, res) => {
  const user = (req as any).session?.user as SessionUser | undefined;
  if (!user) return res.json({ user: null });
  res.json({ user });
});

router.get('/logout', (req, res) => {
  if ((req as any).session) {
    (req as any).session.destroy(() => {});
  }
  res.redirect('/');
});

export default router;
