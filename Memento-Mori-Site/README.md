# Memento Mori Web App

This repository now includes a lightweight Express + SQLite backend that powers the static pages via JSON APIs.

## Getting started
1. Install dependencies
```bash
cd backend
npm install
```
2. Run dev server (TS)
```bash
npm run dev
```
The server serves static files from the repo root and exposes the API on `PORT` (default 3001).

## Configuration
Create a `.env` file under `backend/` (or set environment variables):
- `PORT` – server port
- `DB_PATH` – path to the SQLite database (defaults to `data/memento.db`)
- `SESSION_SECRET` – cookie/session secret
- `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI` – Discord OAuth2 details (if `DISCORD_REDIRECT_URI` is
  omitted, the server will derive the callback from the incoming request host; if it is set to a localhost placeholder but the
  site is accessed via another host, the server will prefer the request host to avoid Discord redirect errors and respects
  `X-Forwarded-Proto` when behind a proxy)
- `DISCORD_GUILD_ID`, `DISCORD_ADMIN_ROLE_ID` – Discord server + role used to grant admin access on login
- `DISCORD_ADMIN_IDS` – comma-separated Discord user IDs that should be treated as admins (legacy override when a role is not
  available)
- `DISCORD_WEBHOOK_URL_patch_notes`, `DISCORD_WEBHOOK_URL_map`, `DISCORD_WEBHOOK_URL_whitelist` – optional webhook URLs
- `BOT_SYNC_TOKEN` – shared secret token used by the Discord bot to poll `/bot-sync` bridge endpoints
- `MAP_BASE_DIR`, `GENERATED_DIR`, `UPLOADS_DIR` – legacy locations for base map PNGs, generated composites, and marker uploads
- `MAP_TEMPLATE_DIR`, `MAP_CURRENT_DIR`, `MAP_OVERLAYS_DIR`, `MAP_AWAITING_DIR` – optional overrides for the new map asset folders

## Map export
The `/api/map/export` admin endpoint composites approved marker placements over the base map for the requested map name. It stores the output in `maps/current` (or `MAP_CURRENT_DIR`) and records a new `map_layers` row; the latest export is available via `/api/map/latest`.

Map asset flow:
- Raw uploads land in `maps/overlays`.
- When a player submits a placement, the referenced PNG is moved into `maps/awaiting-approval` while the placement waits for moderation.
- Approved placements are composited on the base template found under `maps/template`.

## Auth & sessions
Use `/auth/discord` to start the login flow. After successful login, `/auth/me` returns `{ user: { discordId, username, avatar, isAdmin } }` or `{ user: null }` if not authenticated. Admin-only routes require the user to hold the configured Discord admin role in the configured guild; logout via `/auth/logout`.
