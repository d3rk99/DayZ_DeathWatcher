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
- `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI` – Discord OAuth2 details
- `DISCORD_ADMIN_IDS` – comma-separated Discord user IDs that should be treated as admins
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
Use `/auth/discord` to start the login flow. After successful login, `/auth/me` returns the current user. Admin-only routes require the user role to be `admin` or listed in `DISCORD_ADMIN_IDS`.
