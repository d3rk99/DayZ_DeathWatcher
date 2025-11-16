import time
import sys
import os
import json
import glob


os.system("title " + "DayZ Death Watcher")

try:
    with open("./config.json", "r") as json_file:
        config = json.load(json_file)
except FileNotFoundError:
    print("Generating default config file: (config.json)")
    with open("./config.json", "w") as json_file:
        json_file.write("""{
    "path_to_logs" : "../profiles/DayZServer_x64.ADM",
    "path_to_bans" : "./deaths.txt",
    "path_to_cache" : "./death_watcher_cache.json",
    "death_cues" : ["killed by", "committed suicide", "bled out", "died.", "(DEAD)", "was brutally murdered by that psycho Timmy"],
    "ban_delay" : 5,
    "search_logs_interval" : 1,
    "verbose_logs" : 1
}""")

with open("./config.json", "r") as json_file:
    config = json.load(json_file)


# create last read log file if it doesn't exist
if (not os.path.isfile(config["path_to_cache"])):
    print(f"Failed to find cache file: {config['path_to_cache']}\nCreating it now.")
    with open(config["path_to_cache"], "w") as file:
        file.write("""{
	"prev_log_read" : {"line" : ""},
	"log_label" : "2022-01-01 at 00:00:00"
}""")

with open(config["path_to_cache"], "r") as json_file:
    current_cache = json.load(json_file)



try:
    #path_to_logs = config["path_to_logs"]
    path_to_bans = config["path_to_bans"]
    path_to_cache = config["path_to_cache"]
    death_cues = config["death_cues"]
    search_logs_interval = int(config["search_logs_interval"])
    verbose_logs = int(config["verbose_logs"])

except Exception as e:
    print(f"Ran into unexpected error loading variables from config:\n{e}")
    input("Press enter to close this window.")
    sys.exit(0)


players_to_ban = []


def try_to_ban_players():    
    current_seconds = time.time()
    
    for player in players_to_ban:
        if (current_seconds >= player[1]):
            ban_player(player[0])
            players_to_ban.remove(player)
        else:
            break


def ban_player(player_id):
    success = False
    tries = 0
    
    while not success and tries < 10:
        try:
            with open(path_to_bans, "a+") as file:
                file.seek(0)
                ids = [name.strip() for name in file]
                if not player_id in ids:
                    file.write(f'{player_id}\n')
            success = True
        except Exception as e:
            print(f"Failed to ban player: '{e}' Try: {tries + 1}")
            tries += 1
            time.sleep(0.25)
    
    if success:
        if (verbose_logs):
            print(f"Added player with id: {player_id} to ban file: {path_to_bans}")
    else:
        print(f"Player: {player_id} could not be added to the ban file: {path_to_bans}")
    

def get_latest_file():
    directory=config["path_to_logs_directory"]
    # Find all .adm files in the directory
    adm_files = glob.glob(os.path.join(directory, "*.adm"))

    if not adm_files:
        print("No .adm files found.")
        return

    # Get the latest file by modification time
    latest_file = max(adm_files, key=os.path.getmtime)
    return latest_file

def read_new_lines():
    try:
        latest_file=get_latest_file()
        with open(latest_file, "r") as file:
            lines = file.read().split("\n")
    except Exception as e:
        time.sleep(10)
        return []
    
    while ("" in lines):
        lines.remove("")
    
    lines.reverse()
    
    new_lines = []
    for line in lines:
        if (line == current_cache["prev_log_read"]["line"]):
            break
        new_lines.insert(0, line)
    
    return new_lines


def is_death_log(line):
    for death in death_cues:
        if (death in line and not f'"{death}' in line and not f"'{death}" in line):
            return True

    return False


def get_id_from_line(line):
    index = line.find("(id=")
    start_index = index + 4
    
    if (index == -1 or len(line) < (start_index + 44)):
        return ""
    
    player_id = ""
    player_id = line[start_index:start_index + 44]
    
    if ("Unknown" in player_id):
        return ""
    
    return player_id


def update_cache():
    with open(config["path_to_cache"], "w") as json_file:
        json.dump(current_cache, json_file, indent = 4)
    if (verbose_logs):
        print(f"Updated cache file:\n    {current_cache}")
    
    
def load_cache():
    with open(config["path_to_cache"], "r") as json_file:
        return json.load(json_file)


def player_is_queued_for_ban(player_id):
    for player in players_to_ban:
        if (player[0] == player_id):
            return True
    return False



def __main__():
    global current_cache
    print("Starting script...")
    
    # verify core files are found
    #if (not os.path.isfile(path_to_logs)):
       #print(f"Failed to find log file: \"{path_to_logs}\"")
        #input("Press enter to close this window.")
       # sys.exit(0)
    if (not os.path.isfile(path_to_bans)):
        print(f"Failed to find ban file: \"{path_to_bans}\"")
        input("Press enter to close this window.")
        sys.exit(0)
    
    
    current_cache = load_cache()
    if (current_cache["prev_log_read"]["line"] == "\n"):
        current_cache["prev_log_read"]["line"] = ""
    log_number = 0
    
    
    if (current_cache["prev_log_read"]["line"] != ""):
        print(f"Last log read: {current_cache['prev_log_read']['line']}")
    
    time.sleep(1)
    latest_file = get_latest_file()
    print(f"Started searching for new logs. ({latest_file})\n")
    time.sleep(1)
    
    
    while(True):
        
        try:
            latest_file=get_latest_file()
            with open(latest_file, "r") as log_file:
                logs = log_file.read().split('\n')
            while("" in logs) :
                logs.remove("")
        
            log_label = ' '.join(logs[1].split(' ')[3:])
            if (log_label != current_cache["log_label"]):
                pass
            current_cache["log_label"] = log_label
        
        except Exception as e:
            time.sleep(10)
            continue
        
        # Read new log messages
        new_lines = read_new_lines()
        if (verbose_logs and len(new_lines) > 0):
            print(f"Found {len(new_lines)} new logs")
            
        # Search each new log message for death messages
        for line in new_lines:
            if (verbose_logs):
                print(f"[{log_number}] {line}")
            
            # If current log message is a death message, get their id, and ban them
            if (is_death_log(line)):
                player_id = get_id_from_line(line)
                if (verbose_logs):
                    print(f"Found death log:\n    {line} Victim id: {player_id}")
                    
                if (player_id and not player_is_queued_for_ban(player_id)):
                    time_to_ban_player = time.time() + float(config["ban_delay"])
                    if (len(players_to_ban) > 0 and time_to_ban_player < players_to_ban[len(players_to_ban) - 1][1] + 2):
                        time_to_ban_player = players_to_ban[len(players_to_ban) - 1][1] + 2
                    players_to_ban.append((player_id, time_to_ban_player));
                    print(f"    Banning player with id: {player_id}.")
                    if (verbose_logs):
                        print(f"    This player will be banned in {time_to_ban_player - time.time()} seconds.")
                if (verbose_logs):
                    print()
                
            # Update last log message to know where we already searched for death messages
            current_cache["prev_log_read"]["line"] = line
            update_cache()
            
            log_number += 1
        
        if (verbose_logs and len(new_lines) > 0):
            print()
        try_to_ban_players()
        
        # time.sleep loop to cut out faster on interrupts
        sleep_amount = search_logs_interval
        while(sleep_amount > 0):
            sleep_inc = min(0.25, sleep_amount)
            time.sleep(sleep_inc)
            sleep_amount -= sleep_inc
    

try:
    __main__()
    
except KeyboardInterrupt:
    print("Closing program...")
    time.sleep(1.0)
    
except Exception as e:
    print(f"Ran into an unexpected exception. Error: {e}")
    input("Press enter to close this window.")