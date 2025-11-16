import os
import platform
import sys
import datetime
import aiohttp
import asyncio
import json
import time
import traceback
import threading
from typing import Callable, Optional

from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import tasks, commands
from nextcord.ext.commands import Bot
from nextcord.member import Member
import nextcord
from nextcord import Webhook
from dayz_dev_tools import guid as GUID

# Ensure the script runs relative to its own directory so double-click
# launches behave the same as running from a terminal.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

os.system("title " + "Life and Death Bot")

client: Optional[Bot] = None
config: dict = {}
death_counter_state: dict = {"count": 0, "last_reset": int(time.time())}
death_counter_lock: Optional[asyncio.Lock] = None


def main(*, interactive: bool = True, death_log_callback: Optional[Callable[[str], None]] = None):
    global client
    global config
    global death_counter_state

    if (not os.path.isfile("config.json")):
        message = "'config.json' not found!"
        if interactive:
            sys.exit(message)
        raise FileNotFoundError(message)

    print("Loading config...")
    with open("config.json") as file:
        config = json.load(file)

    load_death_counter_state()

    # create userdata db (json) file if it does not exist
    if (not os.path.isfile(config["userdata_db_path"])):
        print(f"Userdata db file ({config['userdata_db_path']}) not found. Creating it now.")
        with open(config["userdata_db_path"], "w") as file:
            file.write("{\"userdata\": {}}")

    # verify whitelist file path is valid
    if (not os.path.isfile(config["whitelist_path"])):
        message = f"Whitelist file ({config['whitelist_path']}) not found. Please verify the path to the whitelist file in the config file."
        print(message)
        if interactive:
            input("Press enter to close this window.")
            sys.exit(0)
        raise FileNotFoundError(message)

    # verify blacklist file path is valid
    if (not os.path.isfile(config["blacklist_path"])):
        message = f"Blacklist_path file ({config['blacklist_path']}) not found. Please verify the path to the blacklist file in the config file."
        print(message)
        if interactive:
            input("Press enter to close this window.")
            sys.exit(0)
        raise FileNotFoundError(message)

    if (not os.path.isfile(config["steam_ids_to_unban_path"])):
        print(f"Steam ids to unban file ({config['steam_ids_to_unban_path']}) not found. Creating it now.")
        with open(config["steam_ids_to_unban_path"], "w") as file:
            file.write("")
    
    intents = nextcord.Intents.all()

    client = Bot(command_prefix=config["prefix"], intents=intents)

    # expose config to cogs so optional components can read shared settings
    client.config = config
    client.death_watcher_logger = death_log_callback

    client.remove_command("help")
    
    load_cogs()
    
    watch_death_watcher_bans = int(config["watch_death_watcher"]) > 0
    if (watch_death_watcher_bans and not os.path.isfile(config["death_watcher_death_path"])):
        print(f"Failed to find death watcher deaths file. ({config['death_watcher_death_path']}) Continuing without watching for deaths")
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

    disabled_cogs = set()
    if int(config.get("run_death_watcher_cog", 0)) == 0:
        disabled_cogs.add("death_watcher")

    for fn in os.listdir("./cogs"):
        if (not fn.endswith(".py")):
            continue

        cog_name = fn[:-3]
        if cog_name in disabled_cogs:
            print(f"\t{fn}... (disabled via config)")
            continue

        print(f"\t{fn}...")
        client.load_extension(f"cogs.{cog_name}")


def get_death_counter_path() -> str:
    if not config:
        return "./death_counter.json"
    return config.get("death_counter_path", "./death_counter.json")


def load_death_counter_state() -> None:
    global death_counter_state

    path = get_death_counter_path()
    default_state = {"count": 0, "last_reset": int(time.time())}

    try:
        if os.path.isfile(path):
            with open(path, "r") as file:
                loaded_state = json.load(file)
            death_counter_state = {
                "count": int(loaded_state.get("count", 0)),
                "last_reset": int(loaded_state.get("last_reset", int(time.time()))),
            }
        else:
            death_counter_state = default_state
            save_death_counter_state()
    except Exception as exc:
        print(f"Failed to load death counter data ({path}). Using default state. Error: {exc}")
        death_counter_state = default_state
        save_death_counter_state()


def save_death_counter_state() -> None:
    path = get_death_counter_path()
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)

    with open(path, "w") as file:
        json.dump(death_counter_state, file, indent=4)


def get_death_counter_lock() -> asyncio.Lock:
    global death_counter_lock
    if death_counter_lock is None:
        death_counter_lock = asyncio.Lock()
    return death_counter_lock


def _format_day_suffix(day: int) -> str:
    if 10 <= day % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _format_since_timestamp(timestamp: Optional[int]) -> str:
    if not timestamp:
        return ""
    dt = datetime.datetime.fromtimestamp(timestamp)
    suffix = _format_day_suffix(dt.day)
    month = dt.strftime("%b")
    year_suffix = f", {dt.year}" if dt.year != datetime.datetime.now().year else ""
    return f"{month} {dt.day}{suffix}{year_suffix}"


async def update_bot_activity(*, count: Optional[int] = None, last_reset: Optional[int] = None) -> None:
    if client is None:
        return

    if count is None or last_reset is None:
        lock = get_death_counter_lock()
        async with lock:
            if count is None:
                count = int(death_counter_state.get("count", 0))
            if last_reset is None:
                last_reset = int(death_counter_state.get("last_reset", int(time.time())))

    activity = nextcord.Activity(
        type=nextcord.ActivityType.watching,
        name=_build_activity_message(count=count, last_reset=last_reset),
    )
    try:
        await client.change_presence(activity=activity)
    except Exception as exc:
        print(f"Failed to update bot activity: {exc}")


def _build_activity_message(*, count: int, last_reset: Optional[int]) -> str:
    deaths = f"{count} death{'s' if count != 1 else ''}"
    since_text = _format_since_timestamp(last_reset)
    if since_text:
        return f"{deaths} since {since_text}"
    return deaths


async def increment_death_counter() -> None:
    await adjust_death_counter(delta=1)


async def reset_death_counter() -> tuple[int, int]:
    lock = get_death_counter_lock()
    async with lock:
        death_counter_state["count"] = 0
        death_counter_state["last_reset"] = int(time.time())
        save_death_counter_state()
        count = death_counter_state["count"]
        last_reset = death_counter_state["last_reset"]

    await update_bot_activity(count=count, last_reset=last_reset)
    return count, last_reset


async def get_death_counter_value() -> tuple[int, int]:
    lock = get_death_counter_lock()
    async with lock:
        return (
            int(death_counter_state.get("count", 0)),
            int(death_counter_state.get("last_reset", int(time.time()))),
        )


async def set_death_counter_value(count: int) -> tuple[int, int]:
    lock = get_death_counter_lock()
    async with lock:
        previous = int(death_counter_state.get("count", 0))
        death_counter_state["count"] = max(0, int(count))
        if death_counter_state["count"] == 0 and previous != 0:
            death_counter_state["last_reset"] = int(time.time())
        save_death_counter_state()
        current = death_counter_state["count"]
        last_reset = int(death_counter_state.get("last_reset", int(time.time())))

    await update_bot_activity(count=current, last_reset=last_reset)
    return current, last_reset


async def adjust_death_counter(delta: int) -> tuple[int, int]:
    lock = get_death_counter_lock()
    async with lock:
        previous = int(death_counter_state.get("count", 0))
        death_counter_state["count"] = max(
            0,
            previous + int(delta),
        )
        if death_counter_state["count"] == 0 and previous != 0:
            death_counter_state["last_reset"] = int(time.time())
        save_death_counter_state()
        current = death_counter_state["count"]
        last_reset = int(death_counter_state.get("last_reset", int(time.time())))

    await update_bot_activity(count=current, last_reset=last_reset)
    return current, last_reset
            

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

        await increment_death_counter()

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




def stop_bot() -> None:
    global client
    if client is None:
        return

    loop = getattr(client, "loop", None)
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(client.close(), loop)


def run_bot(*, interactive: bool = True, death_log_callback: Optional[Callable[[str], None]] = None) -> None:
    print("Starting script...")
    try:
        main(interactive=interactive, death_log_callback=death_log_callback)
        if client is None:
            raise RuntimeError("Failed to initialize Discord client.")
        client.run(config["token"])
    except KeyboardInterrupt:
        print("Closing program...")
    except Exception as exc:
        print("Encountered an unexpected error. Printing traceback below:\n")
        traceback.print_exc()
        print(f"\nError: {exc}")
        if interactive:
            input("Press enter to close this window.")
        else:
            raise


def launch_gui() -> None:
    from gui.app import GuiApplication

    class GuiConsoleWriter:
        def __init__(self, emit: Callable[[str], None], fallback):
            self.emit = emit
            self.fallback = fallback
            self._buffer = ""

        def write(self, data: str) -> None:
            text = str(data)
            if not text:
                return
            if self.fallback:
                self.fallback.write(text)
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self.emit(line + "\n")

        def flush(self) -> None:
            if self.fallback:
                self.fallback.flush()
            if self._buffer:
                self.emit(self._buffer)
                self._buffer = ""

    app: GuiApplication

    def shutdown() -> None:
        stop_bot()
        if app.bot_thread and app.bot_thread.is_alive():
            app.bot_thread.join(timeout=5)

    app = GuiApplication(on_close=shutdown)

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = GuiConsoleWriter(app.append_main_log, original_stdout)
    sys.stderr = GuiConsoleWriter(app.append_main_log, original_stderr)

    def bot_runner() -> None:
        try:
            run_bot(interactive=False, death_log_callback=app.append_death_log)
        except Exception:
            app.append_main_log("Life and Death Bot stopped due to an unexpected error:\n")
            app.append_main_log(traceback.format_exc())

    bot_thread = threading.Thread(target=bot_runner, daemon=True)
    bot_thread.start()
    app.bot_thread = bot_thread

    app.run()


if __name__ == "__main__":
    if "--no-gui" in sys.argv:
        run_bot()
    else:
        launch_gui()
