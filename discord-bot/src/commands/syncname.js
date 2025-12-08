import { SlashCommandBuilder } from 'discord.js';
import { updateMemberNickname } from '../helpers/nickname.js';

export const data = new SlashCommandBuilder()
  .setName('syncname')
  .setDescription('Update your nickname with your in-game playtime tag');

export const execute = async (interaction) => {
  await interaction.deferReply({ ephemeral: true });

  try {
    const result = await updateMemberNickname(interaction.member);
    if (result.updated) {
      await interaction.editReply(`Updated your nickname to **${result.nickname}** based on ${result.minutes} minutes played.`);
    } else if (result.reason === 'no-permission') {
      await interaction.editReply('I could not change your nickname because I lack the Manage Nicknames permission.');
    } else {
      await interaction.editReply('Your nickname already reflects your current playtime.');
    }
  } catch (error) {
    console.error('[syncname] Error handling command:', error);
    const message = error?.message || 'An unexpected error occurred while syncing your nickname.';
    await interaction.editReply(`Failed to sync your nickname: ${message}`);
  }
};
