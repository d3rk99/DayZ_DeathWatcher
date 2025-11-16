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


def main(*, interactive: bool = True, death_log_callback: Optional[Callable[[str], None]] = None):
    global client
    global config

    if (not os.path.isfile("config.json")):
        message = "'config.json' not found!"
        if interactive:
            sys.exit(message)
        raise FileNotFoundError(message)

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
    import queue
    import tkinter as tk
    from tkinter import ttk

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

    class GuiApplication:
        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title("Life and Death Bot Console")
            self.root.minsize(960, 540)

            self.main_queue: "queue.Queue[str]" = queue.Queue()
            self.death_queue: "queue.Queue[str]" = queue.Queue()
            self.bot_thread: Optional[threading.Thread] = None
            self._style = ttk.Style(self.root)
            try:
                self._style.theme_use("clam")
            except tk.TclError:
                pass

            self._themes = {
                "light": {
                    "bg": "#f0f0f0",
                    "section_bg": "#ffffff",
                    "section_border": "#d9d9d9",
                    "title_fg": "#0f0f0f",
                    "text_bg": "#ffffff",
                    "text_fg": "#111111",
                    "desc_fg": "#3a3a3a",
                    "control_fg": "#111111",
                    "control_select": "#dcdcdc",
                    "scroll_trough": "#e6e6e6",
                    "scroll_thumb": "#c0c0c0",
                    "scroll_thumb_active": "#a0a0a0",
                    "scroll_arrow": "#111111",
                },
                "dark": {
                    "bg": "#1e1e1e",
                    "section_bg": "#2b2b2b",
                    "section_border": "#3f3f3f",
                    "title_fg": "#f5f5f5",
                    "text_bg": "#121212",
                    "text_fg": "#f5f5f5",
                    "desc_fg": "#d0d0d0",
                    "control_fg": "#f5f5f5",
                    "control_select": "#3c3c3c",
                    "scroll_trough": "#232323",
                    "scroll_thumb": "#3f3f3f",
                    "scroll_thumb_active": "#515151",
                    "scroll_arrow": "#f5f5f5",
                },
            }

            self._dark_mode = tk.BooleanVar(value=False)
            self._sections = []

            self._build_layout()
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            self._apply_theme()
            self._poll_logs()

        def _build_layout(self) -> None:
            self._container = tk.Frame(self.root, borderwidth=0)
            self._container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            self._controls = tk.Frame(self._container, borderwidth=0)
            self._controls.pack(fill=tk.X, side=tk.TOP)

            self._dark_toggle = tk.Checkbutton(
                self._controls,
                text="Enable dark mode",
                variable=self._dark_mode,
                command=self._apply_theme,
                anchor="e",
                justify="left",
                padx=10,
            )
            self._dark_toggle.pack(anchor="e")

            self._content = tk.Frame(self._container, borderwidth=0)
            self._content.pack(fill=tk.BOTH, expand=True)

            self._content.columnconfigure(0, weight=1)
            self._content.columnconfigure(1, weight=1)

            self._main_text = self._create_section(
                self._content,
                column=0,
                title="Life and Death Bot",
                description=(
                    "Shows everything the Discord bot is doing, including"
                    " cog startup, voice channel automation, revive checks,"
                    " and any unexpected errors."
                ),
            )
            self._death_text = self._create_section(
                self._content,
                column=1,
                title="DayZ Death Watcher",
                description=(
                    "Mirrors the watcher thread that scans DayZ server logs for"
                    " new deaths and queues bans. Use this to verify which"
                    " players were detected and when bans are written."
                ),
            )

        def _create_section(self, parent, *, column: int, title: str, description: str):
            frame = tk.Frame(parent, borderwidth=1, relief=tk.FLAT)
            frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0))
            parent.grid_rowconfigure(0, weight=1)

            title_label = tk.Label(frame, text=title, font=("Segoe UI", 12, "bold"), anchor="w")
            title_label.pack(anchor="w", padx=8, pady=(8, 0))
            desc_label = tk.Label(frame, text=description, wraplength=400, justify="left", anchor="w")
            desc_label.pack(anchor="w", padx=8, pady=(0, 6))

            text_container = tk.Frame(frame, borderwidth=0)
            text_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

            text_widget = tk.Text(
                text_container,
                wrap=tk.WORD,
                height=30,
                font=("Consolas", 10),
                borderwidth=0,
                relief=tk.FLAT,
            )
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            text_widget.configure(state="disabled")

            scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=text_widget.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget.configure(yscrollcommand=scrollbar.set)

            self._sections.append({
                "frame": frame,
                "title": title_label,
                "desc": desc_label,
                "text": text_widget,
                "text_container": text_container,
                "scrollbar": scrollbar,
            })

            return text_widget

        def _apply_theme(self) -> None:
            theme = self._themes["dark" if self._dark_mode.get() else "light"]

            self.root.configure(bg=theme["bg"])
            self._container.configure(bg=theme["bg"])
            self._controls.configure(bg=theme["bg"])
            self._content.configure(bg=theme["bg"])

            self._dark_toggle.configure(
                bg=theme["bg"],
                fg=theme["control_fg"],
                selectcolor=theme["control_select"],
                activebackground=theme["bg"],
                activeforeground=theme["control_fg"],
            )

            for section in self._sections:
                frame = section["frame"]
                title = section["title"]
                desc = section["desc"]
                text_widget = section["text"]
                text_container = section["text_container"]
                scrollbar = section["scrollbar"]

                frame.configure(bg=theme["section_bg"], highlightbackground=theme["section_border"], highlightcolor=theme["section_border"], highlightthickness=1)
                title.configure(bg=theme["section_bg"], fg=theme["title_fg"])
                desc.configure(bg=theme["section_bg"], fg=theme["desc_fg"])
                text_container.configure(bg=theme["section_bg"])
                text_widget.configure(
                    bg=theme["text_bg"],
                    fg=theme["text_fg"],
                    insertbackground=theme["text_fg"],
                    highlightbackground=theme["section_border"],
                    highlightcolor=theme["section_border"],
                )
                scrollbar.configure(style="Vertical.TScrollbar")

            self._style.configure(
                "Vertical.TScrollbar",
                troughcolor=theme["scroll_trough"],
                background=theme["scroll_thumb"],
                bordercolor=theme["section_border"],
                lightcolor=theme["scroll_thumb"],
                darkcolor=theme["scroll_thumb"],
                arrowcolor=theme["scroll_arrow"],
            )
            self._style.map(
                "Vertical.TScrollbar",
                background=[
                    ("active", theme["scroll_thumb_active"]),
                    ("pressed", theme["scroll_thumb_active"]),
                ],
                arrowcolor=[
                    ("active", theme["scroll_arrow"]),
                    ("pressed", theme["scroll_arrow"]),
                ],
            )

            self._apply_title_bar_theme(self._dark_mode.get())

        def _apply_title_bar_theme(self, dark: bool) -> None:
            if os.name != "nt":
                return
            try:
                import ctypes
                from ctypes import wintypes

                hwnd = wintypes.HWND(self.root.winfo_id())
                value = ctypes.c_int(1 if dark else 0)
                for attr in (20, 19):
                    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        attr,
                        ctypes.byref(value),
                        ctypes.sizeof(value),
                    )
                    if result == 0:
                        break
            except Exception:
                pass

        def append_main_log(self, message: str) -> None:
            self.main_queue.put(message)

        def append_death_log(self, message: str) -> None:
            self.death_queue.put(message)

        def _poll_logs(self) -> None:
            self._drain_queue(self.main_queue, self._main_text)
            self._drain_queue(self.death_queue, self._death_text)
            self.root.after(100, self._poll_logs)

        def _drain_queue(self, q: "queue.Queue[str]", widget) -> None:
            while not q.empty():
                message = q.get_nowait()
                if not isinstance(message, str):
                    message = str(message)
                widget.configure(state="normal")
                if not message.endswith("\n"):
                    message += "\n"
                widget.insert(tk.END, message)
                widget.see(tk.END)
                widget.configure(state="disabled")

        def _on_close(self) -> None:
            stop_bot()
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
            self.root.destroy()

        def run(self) -> None:
            self.root.mainloop()

    app = GuiApplication()

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
