import os, sys
import aiohttp
import json
from email.mime import audio
import nextcord
from nextcord.ext import commands
from nextcord import Webhook
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from main import *



class OnMemberJoin(commands.Cog):
    def __init__(self, client):
        self.client = client
        
    global config
    with open("config.json") as file:
        config = json.load(file)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
    
        try:
            
            user_id = int(member.id)
            
            # open userdata db file
            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            keys = list(userdata_json["userdata"].keys())
            
            # If they're not in the database, do nothing
            if (not str(user_id) in keys):
                return
            userdata = userdata_json["userdata"][str(user_id)]
            role = None
            
            # If they're alive in the database
            if (str(userdata["is_alive"]) != "0"):
                role = nextcord.utils.get(member.guild.roles, id = int(config["alive_role"]))
            # If they're dead in the database
            else:
                role = nextcord.utils.get(member.guild.roles, id = int(config["dead_role"]))
            
            # Give them the proper role
            await member.add_roles(role)
            print(f"[OnMemberJoin] Found new member with discord id: \"{user_id}\" in database. Assigned them the role: {role.name}.")
            
            
        except Exception as e:
            text = f"[OnMemberJoin] \"{e}\"\nIt is advised to restart this script."
            print(text)
            await self.dump_error_discord(text, True, "Unexpected error")
        
        
        
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
    client.add_cog(OnMemberJoin(client))
