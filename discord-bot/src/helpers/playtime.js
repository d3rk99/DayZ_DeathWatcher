import fetch from 'node-fetch';

export const formatPlaytimeTag = (totalMinutes = 0) => {
  const safeMinutes = Number.isFinite(totalMinutes) ? Math.max(0, Math.floor(totalMinutes)) : 0;
  const hours = Math.floor(safeMinutes / 60);
  const minutes = safeMinutes % 60;
  const paddedMinutes = String(minutes).padStart(2, '0');
  return `[${hours}h${paddedMinutes}m]`;
};

export const getPlaytimeMinutes = async (discordId) => {
  const apiBase = process.env.API_URL?.replace(/\/$/, '');
  if (!apiBase) {
    throw new Error('API_URL is not configured in the environment.');
  }

  const url = `${apiBase}/api/playtime/${discordId}`;
  const headers = {};
  if (process.env.BOT_API_KEY) {
    headers.Authorization = `Bearer ${process.env.BOT_API_KEY}`;
  }

  const response = await fetch(url, { headers });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Failed to fetch playtime for ${discordId}: ${response.status} ${response.statusText} - ${body}`);
  }

  const data = await response.json();
  return Number.isFinite(data?.minutes) ? data.minutes : 0;
};
