import { formatPlaytimeTag, getPlaytimeMinutes } from './playtime.js';

const MAX_NICKNAME_LENGTH = 32;
const SEPARATOR = ' ';

const buildNickname = (baseName, tag) => {
  const baseLimit = Math.max(1, MAX_NICKNAME_LENGTH - SEPARATOR.length - tag.length);
  const trimmedBase = baseName.length > baseLimit ? baseName.slice(0, baseLimit) : baseName;
  return `${trimmedBase}${SEPARATOR}${tag}`.slice(0, MAX_NICKNAME_LENGTH);
};

export const updateMemberNickname = async (member) => {
  if (!member) {
    throw new Error('No member provided to update nickname.');
  }

  const baseName = member?.user?.globalName || member?.user?.username;
  if (!baseName) {
    throw new Error('Unable to derive a base name for this member.');
  }

  const minutes = await getPlaytimeMinutes(member.id);
  const tag = formatPlaytimeTag(minutes);
  const desiredNickname = buildNickname(baseName, tag);
  const currentNickname = member.nickname ?? member.user.username;

  if (currentNickname === desiredNickname) {
    return { updated: false, nickname: desiredNickname, minutes, reason: 'unchanged' };
  }

  try {
    await member.setNickname(desiredNickname, 'Sync playtime with website leaderboard');
    return { updated: true, nickname: desiredNickname, minutes };
  } catch (error) {
    console.error(`[syncname] Failed to update nickname for ${member.id}:`, error);
    if (error.code === 50013) {
      return { updated: false, nickname: desiredNickname, minutes, reason: 'no-permission', error };
    }
    throw error;
  }
};
