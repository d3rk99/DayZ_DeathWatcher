import os, sys
import aiohttp
import json
from email.mime import audio
import nextcord
from nextcord.ext import commands
from nextcord import Webhook
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from main import get_server_by_id, reset_death_counter
from services.file_utils import atomic_write_text


class ExtraCommands(commands.Cog):
    def __init__(self, client):
        self.client = client
        
    global config
    with open("config.json") as file:
        config = json.load(file)
    
    
    @nextcord.slash_command(name="userdata", description="Gets userdata from either discord id, or steam id.")
    @commands.has_role("Admin")
    async def get_userdata(self, interaction, ID:str=nextcord.SlashOption(name="id", description="ID can be either a discord ID, or a steam ID.", required=True), visibility:str=nextcord.SlashOption(name="visibility", choices=["public", "private"], default="private", required=False)):
        
        try:
            
            is_admin = False
            for role in interaction.user.roles:
                if (role.id == config["admin_role_id"]):
                    is_admin = True
                    break
            
            if (not is_admin):
                await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True, delete_after=20)
                return
            
            
            if (len(ID) != 17 and len(ID) != 18):
                # ID is invalid format
                await interaction.response.send_message(f"Passed ID ({ID}) does not match discord ID or steam ID formats.", ephemeral=True, delete_after=20)
                return
            
            userdata = None
            user_id = 0
            
            # Passed steam id
            if (len(ID) == 17):
                user_id, userdata = await self.get_userdata_from_steam_id(ID)
                if (userdata == None):
                    await interaction.response.send_message(f"Steam ID ({ID}) is not assigned to any user in the database.", ephemeral=True, delete_after=20)
                    return
            
            # Passed discord id
            elif (len(ID) == 18):
                userdata = await self.get_userdata_from_user_id(ID)
                user_id = ID
                if (userdata == None):
                    await interaction.response.send_message(f"Discord ID ({ID}) is not assigned to any user in the database.", ephemeral=True, delete_after=20)
                    return
            
            
            if user_id and userdata:
                normalize_userdata_fields(user_id, userdata)
            text = f"**Discord ID: `{user_id}`**"
            for (k, v) in userdata.items():
                text = f"{text}\n{k} : `{v}`"
            
            if (visibility == "public"):
                await interaction.response.send_message(text)
            else:
                await interaction.response.send_message(text, ephemeral=True, delete_after=20)
            
            
        except Exception as e:
            text = f"[UserIdToSteamId] \"{e}\"\n"
            print(text)
    
    
    
    
    @nextcord.slash_command(name="delete_user_from_database", description="Removes the user's entry from the database.")
    @commands.has_role("Admin")
    async def delete_user_entry(
        self,
        interaction,
        user_id:str=nextcord.SlashOption(name="user_id", description="User's discord id", required=True),
        confirm:bool=nextcord.SlashOption(name="confirm", description="Confirm deletion.", required=False, default=False),
    ):
        
        try:
            
            is_admin = False
            for role in interaction.user.roles:
                if (role.id == config["admin_role_id"]):
                    is_admin = True
                    break
            
            if (not is_admin):
                await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True, delete_after=15)
                return
            
            
            if not confirm:
                await interaction.response.send_message(
                    "Please confirm this action by setting `confirm: true`.",
                    ephemeral=True,
                    delete_after=20,
                )
                return

            if (len(user_id) != 18):
                # Discord ID is in an invalid format
                await interaction.response.send_message(f"Discord ID ({user_id}) does not match the correct format.", ephemeral=True, delete_after=20)
                return
            
            
            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            
            
            if (user_id in userdata_json["userdata"]):
                del userdata_json["userdata"][user_id]
                atomic_write_text(
                    config["userdata_db_path"], json.dumps(userdata_json, indent=4)
                )
                render_global_sync(userdata_json=userdata_json)
                await interaction.response.send_message(f"Successfully deleted user with ID ({user_id}) from the database.", ephemeral=True, delete_after=20)
                print(f"Successfully deleted user with ID ({user_id}) from the database.")
            
            else:
                await interaction.response.send_message(f"User with ID ({user_id}) does not exist in the database.", ephemeral=True, delete_after=20)
                return
            
            
        except Exception as e:
            text = f"[DeleteUserEntry] \"{e}\"\n"
            print(text)


    @nextcord.slash_command(name="reset_death_counter", description="Reset the tracked death counter and bot activity display.")
    @commands.has_role("Admin")
    async def reset_death_counter_command(self, interaction):
        try:
            is_admin = False
            for role in interaction.user.roles:
                if (role.id == config["admin_role_id"]):
                    is_admin = True
                    break

            if (not is_admin):
                await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True, delete_after=15)
                return

            await reset_death_counter()
            await interaction.response.send_message("Death counter reset to 0.", ephemeral=True, delete_after=20)

        except Exception as e:
            text = f"[ResetDeathCounterCommand] \"{e}\"\n"
            print(text)
            try:
                await interaction.response.send_message("Failed to reset the death counter.", ephemeral=True, delete_after=20)
            except Exception:
                pass

    @nextcord.slash_command(name="setserver", description="Set the active DayZ server for a user.")
    @commands.has_role("Admin")
    async def set_server(
        self,
        interaction,
        server_id: str = nextcord.SlashOption(
            name="server_id",
            description="Server ID to set as active.",
            required=True,
        ),
    ):
        try:
            is_admin = False
            for role in interaction.user.roles:
                if (role.id == config["admin_role_id"]):
                    is_admin = True
                    break

            if (not is_admin):
                await interaction.response.send_message(
                    "You are not authorized to use this command.",
                    ephemeral=True,
                    delete_after=15,
                )
                return

            server = get_server_by_id(server_id)
            if not server:
                await interaction.response.send_message(
                    f"Server ID ({server_id}) is not configured.",
                    ephemeral=True,
                    delete_after=20,
                )
                return

            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            user_entry = userdata_json["userdata"].get(str(interaction.user.id))
            if not user_entry:
                await interaction.response.send_message(
                    "You are not registered yet. Use /validatesteamid first.",
                    ephemeral=True,
                    delete_after=20,
                )
                return

            user_entry["active_server_id"] = str(server_id)
            userdata_json["userdata"][str(interaction.user.id)] = user_entry
            atomic_write_text(
                config["userdata_db_path"], json.dumps(userdata_json, indent=4)
            )

            await interaction.response.send_message(
                f"Active server set to {server.get('display_name')} ({server_id}).",
                ephemeral=True,
                delete_after=20,
            )

        except Exception as e:
            text = f"[SetServer] \"{e}\"\n"
            print(text)

    
    
    
    async def get_userdata_from_user_id(self, user_id : str):
        userdata = None
        try:
            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            userdata = userdata_json["userdata"][user_id]
        except:
            userdata = None
        
        return userdata
    
    
    
    async def get_userdata_from_steam_id(self, steam_id : str):
        userdata = None
        user_id = 0
        try:
            with open(config["userdata_db_path"], "r") as json_file:
                userdata_json = json.load(json_file)
            for ID, data in userdata_json["userdata"].items():
                if (steam_id == data["steam_id"]):
                    user_id = ID
                    userdata = data
                    break
        except:
            user_id = 0
            userdata = None
        
        return user_id, userdata
        
    
    
    async def dump_error_discord(self, error_message : str, prefix : str = "Error", force_mention_tag : str = ""):
        await dump_error_discord(error_message, prefix, force_mention_tag)
        
        
def setup(client):
    client.add_cog(ExtraCommands(client))
