import os
import platform
import sys
import datetime
import aiohttp
import asyncio
import json
import time

from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import tasks, commands
from nextcord.ext.commands import Bot
from nextcord.member import Member
import nextcord
from nextcord import Webhook
from dayz_dev_tools import guid as GUID
from death_watcher.new_dayz_death_watcher import DeathWatcher

death_watcher_instance = None

os.system("title " + "Life and Death Bot")

def main():
    global client
    global config
    global death_watcher_instance
    
    if (not os.path.isfile("config.json")):
        sys.exit("'config.json' not found!")
    else:
        print("Loading config...")
        with open("config.json") as file:
            config = json.load(file)
    
    # create userdata db (json) file if it does not exist
    if (not os.path.isfile(config["userdata_db_path"])):
        print(f"Userdata db file ({config['userdata_db_path']}) not found. Creating it now.")
        with open(config["userdata_db_path"], "w") as file:
            file.write("{\"userdata\": {}}")
    
    # verify whitelist file path is valid
    if (not os.path.isfile(config["whitelist_path"])):
        print(f"Whitelist file ({config['whitelist_path']}) not found. Please verify the path to the whitelist file in the config file.")
        input("Press enter to close this window.")
        sys.exit(0)
        
    # verify blacklist file path is valid
    if (not os.path.isfile(config["blacklist_path"])):
        print(f"Blacklist_path file ({config['blacklist_path']}) not found. Please verify the path to the blacklist file in the config file.")
        input("Press enter to close this window.")
        sys.exit(0)
    
    if (not os.path.isfile(config["steam_ids_to_unban_path"])):
        print(f"Steam ids to unban file ({config['steam_ids_to_unban_path']}) not found. Creating it now.")
        with open(config["steam_ids_to_unban_path"], "w") as file:
            file.write("")
    
    intents = nextcord.Intents.all()

    client = Bot(command_prefix=config["prefix"], intents=intents)

    client.remove_command("help")
    
    load_cogs()
    
    watch_death_watcher_bans = int(config["watch_death_watcher"]) > 0
    if (watch_death_watcher_bans and not os.path.isfile(config["death_watcher_death_path"])):
        print(f"Failed to find death watcher deaths file. ({config['death_watcher_death_path']}) Continuing without watching for deaths")
        watch_death_watcher_bans = False

    if (watch_death_watcher_bans):
        try:
            death_watcher_instance = DeathWatcher()
            death_watcher_instance.start_in_background()
            print("\nEmbedded death watcher started.")
        except Exception as e:
            print(f"Failed to start embedded death watcher. Continuing without log monitoring. Error: {e}")
            watch_death_watcher_bans = False
    
    vc_check.start()
    check_if_users_can_revive.start()
    
    if (watch_death_watcher_bans):
        print("\nWatching for new death watcher deaths")
        watch_for_new_deaths.start()
    print("Watching for users to unban")
    watch_for_users_to_unban.start()
    
    print()


def load_cogs():
    print("Loading cogs...")
    for fn in os.listdir("./cogs"):
        if (fn.endswith(".py")):
            print(f"\t{fn}...")
            client.load_extension(f"cogs.{fn[:-3]}")
            

@tasks.loop(seconds = 2)
async def vc_check():
    await client.wait_until_ready()
    
    try:
        
        guild = client.get_guild(config["guild_id"])
        
        with open(config["userdata_db_path"], "r") as json_file:
            userdata_json = json.load(json_file)
        
        with open(config["whitelist_path"], "r") as file:
            whitelist_list = file.read().split('\n')
        with open(config["blacklist_path"], "r") as file:
            blacklist_list = file.read().split('\n')
        
        
        try:
            join_vc_category = nextcord.utils.get(guild.categories, id=config["join_vc_category_id"])
            category_voice_channels = None
            if (join_vc_category == None):
                print(f"Failed to find Category with id: {config['join_vc_category_id']}")
            else:
                category_voice_channels = join_vc_category.voice_channels
                for vc in category_voice_channels:
                    if (not len(vc.members)):
                        #print(f"Deleting VoiceChannel ({vc.name})")
                        await vc.delete()
        except Exception as e:
            category_voice_channels = None
            print(f"Error deleting empty Voice Channels: \"{e}\"")
        
        try:
            join_vc = nextcord.utils.get(guild.voice_channels, id=config["join_vc_id"])
            if (join_vc == None):
                print(f"Failed to find VoiceChannel with id: {config['join_vc_id']}")
            else:
                for member in join_vc.members:
                    #print(f"Creating VoiceChannel for user with id: {member.id}")
                    vc = await guild.create_voice_channel(name=str(member.id), category=join_vc_category, user_limit=5, reason=f"VoiceChannel created for user with id: {member.id}")
                    await member.move_to(vc)
        except Exception as e:
            print(f"Error creating a new Voice Channel: \"{e}\"")
        
        updated_users = 0
        for user_id, userdata in userdata_json["userdata"].items():
            
            try:
                member = guild.get_member(int(user_id))
            except:
                member = None
            
            if (member != None and (member.bot or (int(userdata["is_alive"]) == 0 and int(userdata["is_admin"]) == 0))):
                continue
            
            is_admin = int(userdata["is_admin"])
            
            try:
                category_id = int(member.voice.channel.category_id)
            except:
                category_id = 0
            
            if (is_admin != 0):
                if (userdata["steam_id"] in blacklist_list):
                    print(f"Removed admin's ({userdata['username']}) Steam ID from blacklist ({userdata['steam_id']})")
                    blacklist_list.remove(userdata["steam_id"])
                    updated_users += 1
            elif (member != None and userdata["steam_id"] in blacklist_list and category_id == int(config["join_vc_category_id"])):
                print(f"User ({userdata['username']}) joined channel. Removing Steam ID from blacklist ({userdata['steam_id']})")
                blacklist_list.remove(userdata["steam_id"])
                updated_users += 1
            elif ((not userdata["steam_id"] in blacklist_list) and (member == None or category_id != int(config["join_vc_category_id"]))):
                print(f"User ({userdata['username']}) left channel. Adding Steam ID to blacklist ({userdata['steam_id']})")
                blacklist_list.append(userdata["steam_id"])
                updated_users += 1
        
        if (updated_users > 0):
            with open(config["blacklist_path"], "w") as file:
                file.write('\n'.join(blacklist_list))
    
    except Exception as e:
        text = f"[VcCheck] \"{e}\"\nIt is advised to restart this script."
        print(text)
        await dump_error_discord(text, "Unexpected error")


@tasks.loop(seconds = 5)
async def check_if_users_can_revive():
    await client.wait_until_ready()
    
    try:
        
        guild = client.get_guild(config["guild_id"])
        #can_revive_role = nextcord.utils.get(guild.roles, id = config["can_revive_role"])
        #season_pass_role = nextcord.utils.get(guild.roles, id = config["season_pass_role"])
        
        with open(config["userdata_db_path"], "r") as json_file:
            userdata_json = json.load(json_file)
        
        updated_users = 0
        for user_id in userdata_json["season_deaths"]:
            
            try:
                userdata = userdata_json["userdata"][user_id]
            except:
                # user with user_id doesn't exist in db for some reason. Ignore
                continue
            
            #if (userdata["can_revive"] == 1):
                #continue
            
            if userdata["is_alive"] == 1:
                continue
            
            member = guild.get_member(int(user_id))
            if (member == None or member.bot):
                continue
            
            time_since_death = int(time.time()) - int(userdata["time_of_death"])
            if (time_since_death > float(config["wait_time_new_life_seconds"])):
                print(f"[MarkUserCanRevive] User ({user_id}) has been dead for {config['wait_time_new_life_seconds']/60} minutes. Reviving player.")
                #print(f"[MarkUserCanRevive] User ({user_id}) can now revive. Assigning them their role.")
                #userdata["can_revive"] = 1
                await unban_user(member.id)
                userdata["is_alive"] = 1
                updated_users += 1
                try:
                    await member.send(f"It has been {config['wait_time_new_life_seconds']/60} minutes since your last death. You have been revived.")
                except Exception as e:
                    text = f"[MarkUserCanRevive] Failed to send revive dm to user: {member.id}"
                    print(text)
                    await dump_error_discord(text, "Unexpected error")
                """
                if (not can_revive_role in member.roles):
                    await member.add_roles(can_revive_role)
                    try:
                        await member.send(f"It has been {config['wait_time_new_life_seconds']/60} minutes since your last death. Your ban has been lifted.")
                        #await member.send(f"Great news! You've been dead for {config['wait_time_new_life_seconds']/60} minutes, and are now elligible to purchase a new life if you choose to do so.")
                    except Exception as e:
                        pass
                """
            
            
        
        if (updated_users > 0):
            with open(config["userdata_db_path"], "w") as json_file:
                json.dump(userdata_json, json_file, indent = 4)
    
    except Exception as e:
        text = f"[MarkUserCanRevive] \"{e}\"\nIt is advised to restart this script."
        print(text)
        await dump_error_discord(text, "Unexpected error")


@tasks.loop(seconds = 2)
async def watch_for_new_deaths():
    await client.wait_until_ready()
    
    try:
        with open(config["death_watcher_death_path"], "r") as file:
            death_list = file.read().split('\n')
        with open(config["userdata_db_path"], "r") as json_file:
            userdata_json = json.load(json_file)
        
        for guid in death_list:
            for user_id, userdata in userdata_json["userdata"].items():
                if (str(guid) == str(userdata["guid"]) and int(userdata["is_alive"]) != 0):
                    await set_user_as_dead(user_id)
        
        # clear file
        with open(config["death_watcher_death_path"], "w") as file:
            file.write("")
    
    except Exception as e:
        text = f"[WatchForNewDeaths] \"{e}\"\nIt is advised to restart this script."
        print(text)
        await dump_error_discord(text, "Unexpected error")


@tasks.loop(seconds = 2)
async def watch_for_users_to_unban():
    
    try:
        with open(config["steam_ids_to_unban_path"], "r") as file:
            steam_ids = file.read().split('\n')
        while('' in steam_ids):
            steam_ids.remove('')
        
        if (len(steam_ids) <= 1):
            return
        
        with open(config["userdata_db_path"], "r") as json_file:
            userdata_json = json.load(json_file)
        
        if (steam_ids[1] == "-1"):
            print(f"Unbanning all players")
            for user_id, userdata in userdata_json["userdata"].items():
                if (int(userdata["is_alive"]) == 0):
                    await unban_user(user_id)
            print(f"[WatchForUsersToUnban] Finished unbanning all players")
        
        else:
            for steam_id in steam_ids:
                if (not steam_id.isnumeric()):
                    continue
                    
                print(f"Attempting to unban steam id: {steam_id}\nSteam ids: {steam_ids}")
                for user_id, userdata in userdata_json["userdata"].items():
                    if (str(steam_id) in str(userdata["steam_id"])):
                        await unban_user(user_id)
                        break
    
        # clear file
        with open(config["steam_ids_to_unban_path"], "w") as file:
            file.write("Enter steam ids to unban below OR enter -1 to unban all users")
        
    except Exception as e:
        text = f"[WatchForUsersToUnban] \"{e}\"\nIt is advised to restart this script."
        print(text)
        await dump_error_discord(text, "Unexpected error")


async def set_user_as_dead(user_id):
    
    try:
    
        guild = client.get_guild(config["guild_id"])
        
        # update userdata (set user as dead)
        with open(config["userdata_db_path"], "r") as json_file:
            userdata_json = json.load(json_file)
        userdata = userdata_json["userdata"][user_id]
        season_deaths = userdata_json["season_deaths"]
        
        if (int(userdata["is_admin"]) == 1):
            text = f"[SetUserAsDead] An admin died. What a loser. User: {userdata['username']}"
            print(text)
            await dump_error_discord(text, "???")
            return
        
        print(f"Found new death. User: {userdata['username']}")
        userdata["is_alive"] = 0
        userdata["time_of_death"] = int(time.time())
        userdata["can_revive"] = 0
        
        if (not str(user_id) in season_deaths):
            season_deaths.append(str(user_id))
        
        with open(config["userdata_db_path"], "w") as json_file:
            json.dump(userdata_json, json_file, indent = 4)
        
        # add to blacklist
        with open(config["blacklist_path"], "r") as file:
            blacklist_list = file.read().split('\n')
        if (not str(userdata["steam_id"]) in blacklist_list):
            blacklist_list.append(str(userdata["steam_id"]))
            with open(config["blacklist_path"], "w") as file:
                file.write('\n'.join(blacklist_list))
        
        # update discord roles
        member = guild.get_member(int(user_id))
        if (member == None):
            return
        
        alive_role = nextcord.utils.get(guild.roles, id = config["alive_role"])
        dead_role = nextcord.utils.get(guild.roles, id = config["dead_role"])
        #can_revive_role = nextcord.utils.get(guild.roles, id = config["can_revive_role"])
        
        if (alive_role in member.roles):
            await member.remove_roles(alive_role)
        if (not dead_role in member.roles):
            await member.add_roles(dead_role)
        #if (can_revive_role in member.roles):
            #await member.remove_roles(can_revive_role)
        
        # kick user from voice channel
        try:
            channel = member.voice.channel
            channel_id = channel.id
            category_id = channel.category_id
        except:
            channel_id = -1
            category_id = -1
        if (channel_id == int(config["join_vc_id"]) or category_id == int(config["join_vc_category_id"])):
            await member.edit(voice_channel = None)
        
        print(f"Marked user ({userdata['username']}) as dead.")
        
    except Exception as e:
        text = f"[SetUserAsDead] \"{e}\"\nIt is advised to restart this script."
        print(text)
        await dump_error_discord(text, "Unexpected error")


async def unban_user(user_id):
    
    try:
    
        with open(config["userdata_db_path"], "r") as json_file:
            userdata_json = json.load(json_file)
        
        season_deaths = userdata_json["season_deaths"]
        
        try:
            userdata = userdata_json["userdata"][str(user_id)]
        except:
            text = f"[UnbanUser] Failed to find user in database with id: {user_id}"
            print(text)
            await dump_error_discord(text, "Warning")
            return
        
        if (userdata["is_alive"] != 0):
            text = f"[UnbanUser] User with id: {user_id} is not marked as dead!"
            print(text)
            await dump_error_discord(text, "Warning")
            return
        
        # set death status to alive and update db
        userdata["is_alive"] = 1
        userdata["time_of_death"] = 0
        userdata["can_revive"] = 0
        
        # remove from season deaths if user_id is in there
        if (str(user_id) in season_deaths):
            season_deaths.remove(str(user_id))
        
        with open(config["userdata_db_path"], "w") as json_file:
            json.dump(userdata_json, json_file, indent = 4)

        # remove from death list
        success = False
        tries = 0
        while not success and tries < 10:
            try:
                with open (config["death_watcher_death_path"], "r") as file:
                    deaths_list = file.read().split('\n')
                if (str(userdata["steam_id"]) in deaths_list):
                    deaths_list.remove(str(userdata["steam_id"]))
                with open (config["death_watcher_death_path"], "w") as file:
                    file.write('\n'.join(deaths_list))
                success = True
            except Exception as e:
                print(f"[UnbanUser] Attempt {tries + 1} - Failed to open deaths list file: {config['death_watcher_death_path']} '{e}'")
                tries += 1
                time.sleep(0.25)
        
        if not success:
            print(f"Could not write user id: {user_id} to ban list after 10 tries.")
            await dump_error_discord("Error unbanning user: `{user_id}`\nFailed to add user id to the ban list. (likely file permission error?)", "Unexpected error")
            return
            
        
        # update user's roles
        guild = client.get_guild(config["guild_id"])
        member = guild.get_member(int(user_id))
        if (member == None):
            text = f"[UnbanUser] Found user in database but not in server. ({user_id}) Maybe they left the server?"
            print(text)
            await dump_error_discord(text, "Warning")
            return
        
        alive_role = nextcord.utils.get(guild.roles, id = config["alive_role"])
        dead_role = nextcord.utils.get(guild.roles, id = config["dead_role"])
        #can_revive_role = nextcord.utils.get(guild.roles, id = config["can_revive_role"])
        
        if (dead_role in member.roles):
            await member.remove_roles(dead_role)
        #if (can_revive_role in member.roles):
            #await member.remove_roles(can_revive_role)
        if (not alive_role in member.roles):
            await member.add_roles(alive_role)
        
        print(f"Successfully unbanned: {userdata['username']}")
    
    except Exception as e:
        text = f"[UnbanUser] \"{e}\"\nIt is advised to restart this script."
        print(text)
        await dump_error_discord(text, "Unexpected error")
    
    

async def dump_error_discord(error_message : str, prefix : str = "Error", force_mention_tag : str = ""):
    prefix = "Error" if (prefix == "") else prefix
    channel_id = config["error_dump_channel"]
    if (channel_id != "-1"):
        channel = client.get_channel(int(channel_id))
        if (channel == None):
            print(f"Error: [Main] Failed to find error_dump_channel with id: {channel_id}")
            return
        
        mention = ""
        if (force_mention_tag != ""):
            if (force_mention_tag == "everyone" or force_mention_tag == "here"):
                mention = force_mention_tag
            else:
                mention = await get_user_id_from_name(force_mention_tag)
        if (mention == "" and str(config["error_dump_allow_mention"]) != "0"):
            mention = config["error_dump_mention_tag"]
            if (mention != "" and mention != "everyone" and mention != "here"):
                mention = await get_user_id_from_name(mention)
        mention = (f"@{mention} " if (mention == "everyone" or mention == "here") else f"<@{mention}> ") if (mention != "") else ""
        await channel.send(f"{mention}**{prefix}**\n{error_message}")
    
    
    
async def get_user_id_from_name(username : str):
    ID = ""
    try:
        guild = client.get_guild(config["guild_id"])
        if (guild != None):
            mention_member = nextcord.utils.get(guild.members, name=username)
            ID = str(mention_member.id) if (mention_member != None) else ""
        else:
            ID = ""
    except:
        ID = ""
    
    return ID
        



if __name__ == "__main__":
    print("Starting script...")
    main()
    client.run(config["token"])
