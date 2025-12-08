import dotenv from 'dotenv';
import {
  Client,
  Collection,
  Events,
  GatewayIntentBits,
  REST,
  Routes,
} from 'discord.js';
import { data as syncNameData, execute as syncNameExecute } from './commands/syncname.js';

dotenv.config();

const token = process.env.DISCORD_TOKEN;
const guildId = process.env.GUILD_ID || process.env.DISCORD_GUILD_ID;
let clientId =
  process.env.CLIENT_ID || process.env.DISCORD_CLIENT_ID || process.env.APPLICATION_ID;

if (!token) {
  console.error('DISCORD_TOKEN is required to run the bot.');
  process.exit(1);
}

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMembers],
});

client.commands = new Collection();
client.commands.set(syncNameData.name, { data: syncNameData, execute: syncNameExecute });

const registerCommands = async () => {
  if (!clientId && client.application?.id) {
    clientId = client.application.id;
  }

  if (!clientId) {
    console.warn('Client ID is missing; slash commands will not be registered.');
    return;
  }

  const rest = new REST({ version: '10' }).setToken(token);
  const commands = [syncNameData.toJSON()];

  try {
    if (guildId) {
      await rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commands });
      console.log('Registered /syncname command for the guild.');
    } else {
      await rest.put(Routes.applicationCommands(clientId), { body: commands });
      console.log('Registered /syncname command globally.');
    }
  } catch (error) {
    console.error('Failed to register slash commands:', error);
  }
};

client.once(Events.ClientReady, async () => {
  console.log(`Logged in as ${client.user.tag}`);
  // Ensure the application is fetched so we can derive the client ID if it was not provided.
  if (!client.application?.owner) {
    await client.application?.fetch().catch((error) => {
      console.warn('Unable to fetch application; command registration may fail:', error);
    });
  }
  await registerCommands();
});

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  const command = client.commands.get(interaction.commandName);
  if (!command) return;

  try {
    await command.execute(interaction);
  } catch (error) {
    console.error('Error executing command:', error);
    if (interaction.deferred || interaction.replied) {
      await interaction.editReply({ content: 'There was an error while executing this command.' });
    } else {
      await interaction.reply({ content: 'There was an error while executing this command.', ephemeral: true });
    }
  }
});

client.login(token).catch((error) => {
  console.error('Failed to log in to Discord:', error);
});
