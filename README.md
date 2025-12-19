# DayZ Death Watcher

Discord-first automation that enforces permadeath-style rules for a DayZ server. The bot keeps
Discord voice channels in sync with whitelist / blacklist files, tracks users' Steam64 IDs, and
coordinates temporary bans whenever the death watcher script detects a death event.

## Features
- **Voice channel enforcement** – `main.py`'s `vc_check` loop ensures players are sitting in an
  authorized voice channel before their Steam ID is whitelisted, and automatically re-adds IDs to
  the blacklist when they leave voice.
- **Death-driven bans** – the `death_watcher/new_dayz_death_watcher.py` script tails the latest DayZ
  `.ADM` log, looks for death cues, and adds the matching GUID to `death_watcher/deaths.txt`. The
  bot monitors that file and moves users to a "dead" state for `wait_time_new_life_seconds`.
- **Discord slash commands** – administrators can inspect or delete entries with `/userdata` and
  `/delete_user_from_database`, while players self-register via `/validatesteamid` (restricted to the
  configured validation channel).
- **Automated reminders** – background tasks such as `watch_for_users_to_unban` and
  `check_if_users_can_revive` promote users out of the dead state once their timers expire.
- **GitHub Actions workflow** – `.github/workflows/codex.yml` provides a lightweight CI job that
  installs dependencies and byte-compiles the bot to catch syntax errors before deploying.

## Repository layout
```
main.py                  # Entrypoint for the Discord bot and background tasks
cogs/                    # Slash commands and event listeners (loaded dynamically)
death_watcher/           # Stand-alone log parser that feeds the death list
userdata_db.json         # JSON document storing Discord ↔ Steam metadata
steam_ids_to_unban.txt   # Queue of players that the bot should unban next
requirements.txt         # Python dependencies needed by both scripts
```

## Prerequisites
- Python 3.11 (matches the version used in CI)
- A Discord bot application with privileged intents enabled
- Access to the DayZ server's `.ADM` logs, whitelist, and blacklist files
- A Windows host (optional) if you rely on `os.system("title …")` console titles for the provided scripts

## Local setup
1. Clone the repository and create a virtual environment:
   ```bash
   git clone <repo-url>
   cd DayZ_DeathWatcher
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Copy `config.json` to a safe location and replace any secrets (Discord token, role IDs, file paths)
   with the values that match your environment. **Never commit a real bot token.**
3. Review the DayZ whitelist (`whitelist_path`), blacklist (`blacklist_path`), and `death_watcher`
   paths to make sure the bot can read and write to them from the same machine where it runs.

### If Windows blocks `run_main.bat`
Windows Smart App Control sometimes flags unsigned batch files. You can still launch the bot by
running the same steps manually:

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If you prefer to keep using the batch file, right-click `run_main.bat` → **Properties** → check
**Unblock** (if available) and apply. Smart App Control does not support per-file exceptions, so you
may need to temporarily disable it in **Windows Security → App & browser control → Smart App Control**
to run the script.

### Configuration reference
All of the bot's knobs live in `config.json`:

| Key | Description |
| --- | --- |
| `prefix` | Legacy command prefix (the bot now primarily uses slash commands). |
| `token` | Discord bot token used by `main.py`. Prefer storing this securely (env var or secret file). |
| `whitelist_path` / `blacklist_path` | DayZ server files that the bot mutates whenever someone joins/leaves voice. |
| `userdata_db_path` | Location of the JSON datastore the bot uses to correlate Discord users to Steam IDs. |
| `admin_role_id` | Discord role ID allowed to run admin-only slash commands. |
| `guild_id` | Discord server that the bot should operate in. |
| `join_vc_id` / `join_vc_category_id` | Voice channel & category IDs that gate players into private squad channels. |
| `validate_steam_id_channel` | Text channel where `/validatesteamid` requests are accepted. |
| `alive_role` / `dead_role` / `can_revive_role` / `season_pass_role` | Role IDs that the bot applies as users die or revive. |
| `watch_death_watcher` / `death_watcher_death_path` | Toggles and file path for syncing with the `death_watcher` script. |
| `steam_ids_to_unban_path` | Text file that acts as a queue for Steam IDs waiting to be unbanned. |
| `error_dump_channel`, `error_dump_allow_mention`, `error_dump_mention_tag` | Controls for piping unexpected errors to a Discord channel. |
| `wait_time_new_life_seconds` / `_season_pass` | Cooldown timers before a dead player can return. |

### First-time GUI setup & missing paths
When you launch the GUI for the first time (or after deleting `config.json`), the app starts in a
"path setup" workflow. You'll be prompted to fill in every required file path (whitelist,
blacklist, DayZ log folder, etc.) before the Discord bot thread spins up. Those values are saved
back into `config.json`, so the next launch will run normally without prompting.

If a future change breaks one of the paths—for example you move the whitelist file and forget to
update the config—the worker thread raises a `MissingConfigPaths` error. The GUI catches that,
pauses startup, and shows the same path setup dialog so you can correct the paths inline. After you
click **Save & Continue**, the bot restarts automatically with the new values.

### Supporting data files
- `userdata_db.json` is auto-created with `{ "userdata": {} }` the first time the bot runs.
- `steam_ids_to_unban.txt` is created if missing and stores one Steam64 ID per line.
- `death_watcher/deaths.txt` is appended to by the log watcher; the bot reads it to enforce ban timers.

## Running the Discord bot
```bash
source .venv/bin/activate
python main.py
```
Ensure the machine can reach both the Discord API and the DayZ server's filesystem paths referenced in
`config.json`. The bot automatically loads every `cogs/*.py` module, so you can add features by
dropping new cogs in that folder.

## Running the death watcher
The `death_watcher/new_dayz_death_watcher.py` script can run on the same host as the DayZ server. It
continuously scans the newest `.ADM` log in `path_to_logs_directory`, detects death cues, and writes
matching GUIDs to `deaths.txt`. Start it in a dedicated console:
```bash
cd death_watcher
python new_dayz_death_watcher.py
```
Adjust `death_watcher/config.json` if your log folder or ban file lives elsewhere.

## Slash commands & roles
- `/validatesteamid <steam_id>` – validates that a Steam64 ID is unique, writes it to the whitelist,
  and assigns the "alive" role. Only works for alive users and inside `validate_steam_id_channel`.
- `/userdata <id> [visibility]` – Admin-only lookup by Discord ID or Steam64 ID.
- `/delete_user_from_database <user_id>` – Admin-only removal of a Discord user's entry from `userdata_db.json`.

Roles are central to the experience: alive players gain channel access, dead players lose it, and
admins bypass voice requirements. Keep role IDs in sync with Discord whenever you modify your server.

## Automation & CI
The repository ships with `.github/workflows/codex.yml`, a GitHub Actions workflow that installs
Python 3.11, caches pip packages, and byte-compiles the bot to surface syntax errors early. Extend it
with linting or unit tests as the codebase grows.

## Contributing & maintenance tips
- Treat config files with secrets as local-only and add `.example` templates if you need to share
  structure with collaborators.
- Use slash commands for all new functionality—legacy prefixed commands are disabled via
  `client.remove_command("help")` in `main.py`.
- Keep your DayZ server paths consistent between Windows and Linux hosts; the bot assumes it can
  read/write the configured files synchronously.
