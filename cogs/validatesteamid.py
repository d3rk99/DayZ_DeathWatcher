import os, sys
import aiohttp
import json
from email.mime import audio
import nextcord
from nextcord.ext import commands
from nextcord import Webhook
from dayz_dev_tools import guid as GUID
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from main import *
from services.file_utils import atomic_write_text
import asyncio
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

            for existing_id, existing_user in userdata_json["userdata"].items():
                if str(existing_user.get("steam_id")) == steam_id or str(existing_user.get("steam64")) == steam_id:
                    if int(existing_user.get("is_alive", 1)) == 0 or bool(existing_user.get("isDead", False)):
                        embedVar = nextcord.Embed(
                            title=f"Steam ID is already marked dead! ({steam_id})",
                            color=0xFF0000,
                        )
                        await interaction.response.send_message(embed=embedVar)
                        return
            
            # try updating existing userdata
            if (str(user_id) in keys):
                userdata = userdata_json["userdata"][str(user_id)]

                if not userdata.get("active_server_id"):
                    userdata["active_server_id"] = get_default_server_id_value()
                
                userdata["steam_id"] = str(steam_id)
                userdata["steam64"] = str(steam_id)
                userdata["guid"] = str(guid)
                userdata["validated"] = True
                userdata["discordId"] = str(user_id)
                userdata.setdefault("isDead", False)
                userdata.setdefault("deadUntil", None)
                userdata.setdefault("lastAliveSec", None)
                userdata.setdefault("lastDeathAt", None)
                if "inCorrectVC" not in userdata:
                    try:
                        userdata["inCorrectVC"] = (
                            author.voice is not None
                            and author.voice.channel is not None
                            and author.voice.channel.category_id == int(config["join_vc_category_id"])
                            and str(author.voice.channel.name) == str(author.id)
                        )
                    except Exception:
                        userdata["inCorrectVC"] = False
                atomic_write_text(
                    config["userdata_db_path"], json.dumps(userdata_json, indent=4)
                )
                render_global_sync(userdata_json=userdata_json)
                print (f"Updated Steam ID ({steam_id}) for discord user: {userdata['username']}!")
                embedVar = nextcord.Embed(title=f"Updated your Steam ID ({steam_id})!", color=0x00FF00)
                await interaction.response.send_message(embed = embedVar)
                return
            
            # store discord user's data
            default_server_id = get_default_server_id_value()
            new_userdata = {
                'username' : author.name,
                'steam_id' : str(steam_id),
                'steam64' : str(steam_id),
                'guid' : str(guid),
                'is_alive' : 1,
                'isDead' : False,
                'time_of_death' : 0,
                'deadUntil': None,
                'lastAliveSec': None,
                'lastDeathAt': None,
                'inCorrectVC': False,
                'validated': True,
                'discordId': str(user_id),
                'can_revive' : 0,
                'is_admin' : 0,
                'active_server_id': default_server_id,
                'home_server_id': "",
            }

            try:
                new_userdata["inCorrectVC"] = (
                    author.voice is not None
                    and author.voice.channel is not None
                    and author.voice.channel.category_id == int(config["join_vc_category_id"])
                    and str(author.voice.channel.name) == str(author.id)
                )
            except Exception:
                new_userdata["inCorrectVC"] = False
            
            # store their userdata in db
            userdata_json["userdata"][str(user_id)] = new_userdata
            atomic_write_text(
                config["userdata_db_path"], json.dumps(userdata_json, indent=4)
            )
            
            # don't assign alive role if they already have it, or has the dead role
            alive_role = nextcord.utils.get(interaction.guild.roles, id = int(config["alive_role"]))
            dead_role = nextcord.utils.get(interaction.guild.roles, id = int(config["dead_role"]))
            if ((not alive_role in author.roles) and (not dead_role in author.roles)):
                await interaction.user.add_roles(alive_role)

            render_global_sync(userdata_json=userdata_json)
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
        await dump_error_discord(error_message, prefix, force_mention_tag)
        
        
        
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
