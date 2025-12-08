# Memento Mori Architecture Plan

## Tech Stack
- **Backend:** Node.js + Express (TypeScript). Lightweight, easy to host on a VPS, and supports modular routing/middleware.
- **Database:** SQLite (via `better-sqlite3`) for a simple, file-based relational store that keeps schema clarity and portability. Can be swapped for another SQL database later with minimal changes to the data layer.
- **API Layer:** RESTful JSON endpoints with simple validation (Zod). Clear separation of routes/controllers/services for maintainability.
- **Frontend:** Static pages for now, progressively enhanced with modular JavaScript. Future-ready for a small React/Vite or vanilla TS setup that can consume the API.
- **Markdown Support:** Content fields (patch notes, stories, guides) are Markdown-friendly to keep authoring flexible.

## Folder Structure (proposed)
```
Memento-Mori-Site/
├── backend/
│   ├── src/
│   │   ├── server.ts          # Express bootstrap and router mounting
│   │   ├── config.ts          # Env + shared configuration
│   │   ├── db.ts              # SQLite connection + migrations
│   │   ├── middleware/
│   │   │   └── auth.ts        # Placeholder/simple auth guard
│   │   ├── models/            # Domain types & DB mappers
│   │   │   └── types.ts
│   │   ├── services/          # Business logic (one file per domain)
│   │   │   ├── seasonsService.ts
│   │   │   └── patchNotesService.ts
│   │   ├── routes/            # Express routers (one file per domain)
│   │   │   ├── seasons.ts
│   │   │   ├── patchNotes.ts
│   │   │   └── placeholders (whitelist, factions, etc.)
│   │   └── utils/
│   │       └── validation.ts  # Shared Zod schemas/helpers
│   ├── package.json
│   └── tsconfig.json
├── docs/
│   └── ARCHITECTURE.md        # This document
├── public/                    # (future) built frontend assets
├── Index.html, about.html, join.html, style.css  # current static site
└── Images/
```

## Data Models (TypeScript interfaces)
```ts
export interface Season {
  id: number;
  name: string;
  map: string;
  difficulty: 'casual' | 'hardcore' | 'custom';
  startDate: string; // ISO date
  endDate?: string;  // ISO date
  flags?: string[];  // e.g., harsh weather, low loot
  currentDay?: number;
  loreBlurb?: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface PatchNote {
  id: number;
  title: string;
  body: string; // Markdown
  tags: string[];
  seasonId?: number;
  createdAt: string;
  updatedAt: string;
}

export interface PlayerStory {
  id: number;
  title: string;
  author: string;
  seasonId?: number;
  body: string; // Markdown
  screenshotUrl?: string;
  status: 'pending' | 'approved' | 'published';
  isStoryOfTheWeek?: boolean;
  isHallOfFame?: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface WhitelistEntry {
  id: number;
  steam64Id: string;
  discordTag: string;
  region?: string;
  acceptedRules: boolean;
  status: 'pending' | 'approved' | 'rejected';
  adminNotes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ServerStatusSnapshot {
  id: number;
  isOnline: boolean;
  playerCount: number;
  maxPlayers: number;
  lastRestart: string; // ISO date
  createdAt: string;
}

export interface TimelineEvent {
  id: number;
  seasonId?: number;
  title: string;
  description: string;
  occurredAt: string; // ISO date
  type: 'wipe' | 'battle' | 'event' | 'system' | 'other';
  createdAt: string;
  updatedAt: string;
}

export interface GuideSection {
  id: number;
  seasonId?: number;
  title: string;
  body: string; // Markdown/HTML
  order: number;
  createdAt: string;
  updatedAt: string;
}

export interface Faction {
  id: number;
  name: string;
  description: string;
  playstyleTags: string[];
  recruiting: boolean;
  territory?: string;
  contact?: string;
  emblemUrl?: string;
  seasons?: number[];
  createdAt: string;
  updatedAt: string;
}

export interface MediaItem {
  id: number;
  type: 'image' | 'video';
  title: string;
  description?: string;
  url: string;
  seasonId?: number;
  tags?: string[];
  displayOrder?: number;
  createdAt: string;
  updatedAt: string;
}

export interface LeaderboardEntry {
  id: number;
  seasonId: number;
  playerName: string;
  category: string;
  value: number;
  metadata?: string;
  createdAt: string;
  updatedAt: string;
}
```

## API Surface (initial sketch)
- `GET /api/health` — heartbeat for uptime checks.
- **Seasons**
  - `GET /api/seasons` — list seasons (supports `active=true`, `includePast=true`).
  - `POST /api/seasons` — create season (admin).
  - `GET /api/seasons/:id` — season detail.
  - `PATCH /api/seasons/:id` — update season.
  - `POST /api/seasons/:id/activate` — mark active.
- **Patch Notes**
  - `GET /api/patch-notes` — list (filters: `tag`, `seasonId`).
  - `POST /api/patch-notes` — create (admin, optional Discord webhook dispatch placeholder).
  - `GET /api/patch-notes/:id` — detail.
- **Player Stories**
  - `GET /api/stories` — public list (filters: `seasonId`, `status=published`).
  - `POST /api/stories` — submit story (pending by default).
  - `PATCH /api/stories/:id` — admin approval/publish, mark Story of the Week or Hall of Fame.
- **Whitelist**
  - `POST /api/whitelist` — submit join request.
  - `GET /api/whitelist` — admin list/filter by status.
  - `PATCH /api/whitelist/:id` — admin approve/reject + optional Discord webhook placeholder.
- **Server Status**
  - `GET /api/status` — latest snapshot (pluggable adapter later).
- **Timeline Events**
  - `GET /api/timeline` — grouped view (optionally by season).
  - `POST /api/timeline` — admin create.
- **New Survivor Guide**
  - `GET /api/guide` — ordered sections (by optional season).
  - `POST /api/guide` — admin add/update sections.
- **Factions**
  - `GET /api/factions` — list/search/filter.
  - `POST /api/factions` — admin create/update.
- **Media Gallery**
  - `GET /api/media` — filter by type/season/tag.
  - `POST /api/media` — admin create/update.
- **Leaderboards**
  - `GET /api/leaderboards` — filter by season + category.
  - `POST /api/leaderboards/import` — admin upload CSV/JSON (placeholder).

## Implementation Notes
- **Validation:** Zod schemas per route for payload safety.
- **Discord Webhooks:** Helper stub that accepts payload + optional URL; disabled if URL missing.
- **Auth:** Minimal middleware placeholder (`X-Admin-Token` header) to guard admin endpoints; can be replaced with sessions later.
- **Status Adapter:** `services/statusAdapter.ts` can swap between mocked data and future DayZ query logic.
- **Frontend Consumption:** API returns JSON suitable for progressive enhancement or a future SPA.
```
