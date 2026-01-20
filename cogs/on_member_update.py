import os, sys
import aiohttp
import json
from email.mime import audio
import nextcord
from nextcord.ext import commands
from nextcord import Webhook
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from main import *
from services.file_utils import atomic_write_text



class OnMemberUpdate(commands.Cog):
    def __init__(self, client):
        self.client = client
        
    global config
    with open("config.json") as file:
        config = json.load(file)
    
    @commands.Cog.listener()
    async def on_member_update(self, member_before, member_after):
    
        try:
            
            user_id = int(member_before.id)
            
            # open userdata db file
            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            keys = list(userdata_json["userdata"].keys())
            
            # If they're not in the database, do nothing
            if (not str(user_id) in keys):
                return
            
            season_deaths = userdata_json["season_deaths"]
            
            userdata = userdata_json["userdata"][str(user_id)]
            alive_role = nextcord.utils.get(member_after.guild.roles, id = int(config["alive_role"]))
            dead_role = nextcord.utils.get(member_after.guild.roles, id = int(config["dead_role"]))
            can_revive_role = nextcord.utils.get(member_after.guild.roles, id = int(config["can_revive_role"]))
            new_role = None
            
            if (alive_role in member_after.roles and (not alive_role in member_before.roles) and str(userdata["is_alive"]) == "0"):
                if (dead_role in member_after.roles):
                    await member_after.remove_roles(dead_role)
                if (can_revive_role in member_after.roles):
                    await member_after.remove_roles(can_revive_role)
                userdata["is_alive"] = 1
                userdata["time_of_death"] = 0
                userdata["can_revive"] = 0
                
                # remove from season deaths if they're in there
                if (str(user_id) in season_deaths):
                    season_deaths.remove(str(user_id))
                
                print(f"[OnMemberUpdate] Alive role was given to user: {member_after.name}. Unbanning them.")
                
            elif (dead_role in member_after.roles and (not dead_role in member_before.roles) and (not str(userdata["is_alive"]) == "0")):
                if (alive_role in member_after.roles):
                    await member_after.remove_roles(alive_role)
                if (can_revive_role in member_after.roles):
                    await member_after.remove_roles(can_revive_role)
                userdata["is_alive"] = 0
                userdata["time_of_death"] = int(time.time())
                userdata["can_revive"] = 0
                
                # add them to season deaths if not already in there
                if (not str(user_id) in season_deaths):
                    season_deaths.append(str(user_id))
                
                print(f"[OnMemberUpdate] Dead role was given to user: {member_after.name}. Banning them.")
                
            else:
                return
            
            # store their userdata in db
            userdata_json["userdata"][str(user_id)] = userdata
            atomic_write_text(
                config["userdata_db_path"], json.dumps(userdata_json, indent=4)
            )
            
            
        except Exception as e:
            text = f"[OnMemberUpdate] \"{e}\"\nIt is advised to restart this script."
            print(text)
            await self.dump_error_discord(text, True, "Unexpected error")
        
        
        
    async def dump_error_discord(self, error_message : str, prefix : str = "Error", force_mention_tag : str = ""):
        prefix = "Error" if (prefix == "") else prefix
        channel_id = config["error_dump_channel"]
        if (channel_id != "-1"):
            channel = self.client.get_channel(int(channel_id))
            if (channel == None):
                print(f"Error: [OnMemberUpdate] Failed to find error_dump_channel with id: {channel_id}")
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
    client.add_cog(OnMemberUpdate(client))
