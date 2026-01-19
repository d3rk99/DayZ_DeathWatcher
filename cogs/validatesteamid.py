import os, sys
import aiohttp
import json
from email.mime import audio
import nextcord
from nextcord.ext import commands
from nextcord import Webhook
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from main import *
from services.file_utils import atomic_write_lines, atomic_write_text, read_lines
import asyncio
import time
import traceback


whitelist_id_length = 17

class ValidateSteamId(commands.Cog):
    def __init__(self, client):
        self.client = client
        
    global config
    with open("config.json") as file:
        config = json.load(file)
    
    @nextcord.slash_command(name = "validatesteamid", guild_ids = [config["guild_id"]])
    async def validatesteamid(self, interaction, steam_id : str): # int = nextcord.SlashOption(name="steam_id", description="Example steam id: 01234567890123456", required=True)
        
        try:
            
            try:
                channel_id = int(interaction.channel_id)
            except Exception as e:
                channel_id = -1
            
            # ignore if posted in wrong channel
            if (channel_id != int(config["validate_steam_id_channel"])):
                return
            
            author = interaction.user
            
            if (author == None):
                text = f"[WatchForUsersToUnban] Null user tried to validate their Steam ID???"
                print(text)
                await self.dump_error_discord(text, "Warning")
                return
            
            user_id = int(author.id)
            
            for role in author.roles:
                if (role.id == int(config["dead_role"])):
                    embedVar = nextcord.Embed(title="Dead users cannot update their Steam ID!", color=0xFF0000)
                    await interaction.response.send_message(embed = embedVar)
                    return
            
            # fix injections
            #steam_id = str(steam_id)
            steam_id = steam_id.replace("\n", "")
            
            valid = len(steam_id) == whitelist_id_length and steam_id.isnumeric()
            
            if (not valid):
                await self.dump_error_discord(f"[ValidateSteamId] Steam ID format is not valid! ({steam_id})", "TestError")
                embedVar = nextcord.Embed(title=f"Steam ID format is not valid! ({steam_id})", color=0xFF0000)
                await interaction.response.send_message(embed = embedVar)
                return
            
            # open userdata db file
            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            keys = list(userdata_json["userdata"].keys())
            
            # check if steam id is already registered
            steam_ids = []
            for key in keys:
                existing_steam_id = userdata_json["userdata"][key]["steam_id"]
                steam_ids.append(existing_steam_id)
            
            if (steam_id in steam_ids):
                embedVar = nextcord.Embed(title=f"Steam ID is already registered! ({steam_id})", color=0xFF0000)
                await interaction.response.send_message(embed = embedVar)
                return
            
            guid = GUID.guid_for_steamid64(steam_id)
            
            # prevent users from registering a steam_id/guid that had previously been banned
            enabled_servers = get_enabled_servers(get_servers())
            death_check_failed = False
            for server in enabled_servers:
                death_path = server.get("death_watcher_death_path", "")
                if not death_path:
                    continue
                success = False
                tries = 0
                while not success and tries < 10:
                    try:
                        deaths_list = read_lines(death_path)
                        success = True
                    except Exception as e:
                        print(
                            "[ValidateSteamId] Attempt "
                            f"{tries + 1} - Failed to open deaths list file: {death_path} '{e}'"
                        )
                        tries += 1
                        time.sleep(0.25)
                if not success:
                    death_check_failed = True
                    break
                if str(guid) in deaths_list:
                    embedVar = nextcord.Embed(
                        title=f"Steam ID is already dead on {server.get('display_name')}! ({steam_id})",
                        color=0xFF0000,
                    )
                    await interaction.response.send_message(embed=embedVar)
                    return

            if death_check_failed:
                print(f"Could not verify that user: {user_id} is in death list after 10 tries.")
                embedVar = nextcord.Embed(
                    title="Internal error. Please try again later.",
                    color=0xFF0000,
                )
                await interaction.response.send_message(embed=embedVar)
                await self.dump_error_discord(
                    f"Error validating user: `{user_id}`\nCould not verify death status in deaths file. "
                    "(likely file permission error?)",
                    "Unexpected error",
                )
                return
            
            # try updating existing userdata
            if (str(user_id) in keys):
                userdata = userdata_json["userdata"][str(user_id)]

                if not userdata.get("active_server_id"):
                    userdata["active_server_id"] = get_default_server_id_value()
                
                validate_scope = get_validate_scope(config)
                scope_servers = resolve_user_scope_servers(userdata, scope=validate_scope)

                # remove instances of old steam_id and guid per server
                for server_id in scope_servers:
                    server = get_server_by_id(server_id)
                    if not server:
                        continue
                    blacklist_path = server.get("path_to_bans", "")
                    whitelist_path = server.get("path_to_whitelist", "")
                    success = False
                    tries = 0
                    while not success and tries < 10:
                        try:
                            blacklist_list = read_lines(blacklist_path)
                            success = True
                        except Exception as e:
                            print(
                                "[ValidateSteamId] Attempt "
                                f"{tries + 1} - Failed to open blacklist file: {blacklist_path} '{e}'"
                            )
                            tries += 1
                            time.sleep(0.25)
                    if not success:
                        print(f"Could not open blacklist file: {blacklist_path} after 10 tries.")
                        embedVar = nextcord.Embed(
                            title="Internal error. Please try again later.",
                            color=0xFF0000,
                        )
                        await interaction.response.send_message(embed=embedVar)
                        await self.dump_error_discord(
                            f"Error validating user: `{user_id}`\nCould not open blacklist file. "
                            "(likely file permission error?)",
                            "Unexpected error",
                        )
                        return

                    blacklist_list = sanitize_steam_id_list(blacklist_list)
                    blacklist_list = remove_steam_id_occurrences(
                        blacklist_list, userdata["steam_id"]
                    )
                    blacklist_list = remove_steam_id_occurrences(blacklist_list, steam_id)
                    blacklist_list.append(str(steam_id))
                    atomic_write_lines(blacklist_path, blacklist_list)

                    whitelist_list = read_lines(whitelist_path)
                    whitelist_list = sanitize_steam_id_list(whitelist_list)
                    whitelist_list = remove_steam_id_occurrences(
                        whitelist_list, userdata["steam_id"]
                    )
                    whitelist_list = remove_steam_id_occurrences(whitelist_list, steam_id)
                    whitelist_list.append(str(steam_id))
                    atomic_write_lines(whitelist_path, whitelist_list)
                
                userdata["steam_id"] = str(steam_id)
                userdata["guid"] = str(guid)
                atomic_write_text(
                    config["userdata_db_path"], json.dumps(userdata_json, indent=4)
                )
                print (f"Updated Steam ID ({steam_id}) for discord user: {userdata['username']}!")
                embedVar = nextcord.Embed(title=f"Updated your Steam ID ({steam_id})!", color=0x00FF00)
                await interaction.response.send_message(embed = embedVar)
                return
            
            # store discord user's data
            default_server_id = get_default_server_id_value()
            new_userdata = {
                'username' : author.name,
                'steam_id' : str(steam_id),
                'guid' : str(guid),
                'is_alive' : 1,
                'time_of_death' : 0,
                'can_revive' : 0,
                'is_admin' : 0,
                'active_server_id': default_server_id,
                'home_server_id': "",
            }
            
            # store their userdata in db
            userdata_json["userdata"][str(user_id)] = new_userdata
            atomic_write_text(
                config["userdata_db_path"], json.dumps(userdata_json, indent=4)
            )
            
            validate_scope = get_validate_scope(config)
            scope_servers = resolve_user_scope_servers(new_userdata, scope=validate_scope)

            # add them to the server whitelist
            for server_id in scope_servers:
                server = get_server_by_id(server_id)
                if not server:
                    continue
                whitelist_path = server.get("path_to_whitelist", "")
                whitelist_list_raw = read_lines(whitelist_path)
                whitelist_list = sanitize_steam_id_list(whitelist_list_raw)
                whitelist_list = remove_steam_id_occurrences(whitelist_list, steam_id)
                whitelist_list.append(str(steam_id))
                atomic_write_lines(whitelist_path, whitelist_list)

            # don't assign alive role if they already have it, or has the dead role
            alive_role = nextcord.utils.get(interaction.guild.roles, id = int(config["alive_role"]))
            dead_role = nextcord.utils.get(interaction.guild.roles, id = int(config["dead_role"]))
            if ((not alive_role in author.roles) and (not dead_role in author.roles)):
                await interaction.user.add_roles(alive_role)
            
            for server_id in scope_servers:
                server = get_server_by_id(server_id)
                if not server:
                    continue
                blacklist_path = server.get("path_to_bans", "")
                success = False
                tries = 0
                while not success and tries < 10:
                    try:
                        blacklist_list_raw = read_lines(blacklist_path)
                        blacklist_list = sanitize_steam_id_list(blacklist_list_raw)
                        blacklist_list = remove_steam_id_occurrences(
                            blacklist_list, steam_id
                        )
                        blacklist_list.append(str(steam_id))
                        atomic_write_lines(blacklist_path, blacklist_list)
                        success = True

                    except Exception as e:
                        print(
                            "[UnbanUser] Attempt "
                            f"{tries + 1} - Failed to open deaths list file: {blacklist_path} '{e}'"
                        )
                        tries += 1
                        time.sleep(0.25)

                if not success:
                    print(f"Could not validate user: {user_id} after 10 tries.")
                    await dump_error_discord(
                        f"Could not validate user: `{user_id}` after 10 tries.\n"
                        "(likely file permission error?)",
                        "Unexpected error",
                    )
                    await interaction.send("An error occurred. Please try again.")
                    return
            
            print (f"Registered Steam ID ({steam_id}) for discord user: {new_userdata['username']}!")
            embedVar = nextcord.Embed(title=f"Registered your Steam ID ({steam_id})!", color=0x00FF00)
            await interaction.response.send_message(embed = embedVar)
            try:
                await author.send(f"Your Steam ID ({steam_id}) has successfully been validated.\nIn order to join the server, you will have to enter the https://discord.com/channels/749808733780967496/1369875969371930666 voice channel.")
            except Exception as e:
                pass
            
        except Exception as e:
            error_message = traceback.format_exc()
            text = f"[ValidateSteamId] \"{e}\"\n{error_message}\n**It is advised to restart this script.**"
            print(text)
            await self.dump_error_discord(text, "Unexpected error")
        
        
    
    # cleanup validate-steam-id channel
    @commands.Cog.listener()
    async def on_message(self, message):
        
        try:
            if (not message or not message.channel):
                return
            
            channel_id = message.channel.id
            if (channel_id != int(config["validate_steam_id_channel"])):
                return
            
            await asyncio.sleep(5)
            
            try:
                await message.delete()
            except Exception as e:
                # this is okay
                return
        
        except Exception as e:
            error_message = traceback.format_exc()
            text = f"[ValidateSteamId - Cleanup] \"{e}\"\n{error_message}\n**It is advised to restart this script.**"
            print(text)
            await self.dump_error_discord(text, "Unexpected error")
        
        
        
    async def dump_error_discord(self, error_message : str, prefix : str = "Error", force_mention_tag : str = ""):
        prefix = "Error" if (prefix == "") else prefix
        channel_id = config["error_dump_channel"]
        if (channel_id != "-1"):
            channel = self.client.get_channel(int(channel_id))
            if (channel == None):
                print(f"Error: [ValidateSteamId] Failed to find error_dump_channel with id: {channel_id}")
                return
            
            mention = ""
            if (force_mention_tag != ""):
                if (force_mention_tag == "everyone" or force_mention_tag == "here"):
                    mention = force_mention_tag
                else:
                    mention = await self.get_user_id_from_name(force_mention_tag)
            if (mention == "" and str(config["error_dump_allow_mention"]) != "0"):
                mention = config["error_dump_mention_tag"]
                if (mention != "" and mention != "everyone" and mention != "here"):
                    mention = await self.get_user_id_from_name(mention)
            mention = (f"@{mention} " if (mention == "everyone" or mention == "here") else f"<@{mention}> ") if (mention != "") else ""
            await channel.send(f"{mention}**{prefix}**\n{error_message}")
        
        
        
    async def get_user_id_from_name(self, username : str):
        ID = ""
        try:
            guild = self.client.get_guild(config["guild_id"])
            if (guild != None):
                mention_member = nextcord.utils.get(guild.members, name = username)
                ID = str(mention_member.id) if (mention_member != None) else ""
            else:
                ID = ""
        except:
            ID = ""
        
        return ID
        
        
        
def setup(client):
    client.add_cog(ValidateSteamId(client))
