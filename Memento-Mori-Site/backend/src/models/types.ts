export type Difficulty = 'casual' | 'hardcore' | 'custom';

export interface Season {
  id: number;
  name: string;
  map: string;
  difficulty: Difficulty;
  startDate: string;
  endDate?: string;
  flags?: string[];
  currentDay?: number;
  loreBlurb?: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface PatchNote {
  id: number;
  title: string;
  body: string;
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
  body: string;
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
  lastRestart: string;
  createdAt: string;
}

export interface TimelineEvent {
  id: number;
  seasonId?: number;
  title: string;
  description: string;
  occurredAt: string;
  type: 'wipe' | 'battle' | 'event' | 'system' | 'other';
  createdAt: string;
  updatedAt: string;
}

export interface GuideSection {
  id: number;
  seasonId?: number;
  title: string;
  body: string;
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
