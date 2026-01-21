# DayZ Death Watcher

Discord-first automation that enforces permadeath-style rules for DayZ servers. The bot tracks
Discord ↔ Steam64 validation in a shared userdata database, produces a single global whitelist and
ban list, and syncs those outputs to up to five DayZ servers. Deaths detected on any server ban the
player everywhere, while live players are only unbanned globally when they are inside their
private Discord voice channel.

## Features
- **Voice channel enforcement** – `main.py`'s `vc_check` loop ensures players are sitting in their
  correct private voice channel before they are globally unbanned. Leaving voice instantly re-adds
  the Steam64 ID to the global ban list.
- **Death-driven bans** – the `death_watcher/new_dayz_death_watcher.py` script tails the latest DayZ
  `.ljson` log in each configured `profiles/DetailedLogs` directory, looks for
  `event: "PLAYER_DEATH"` entries, and marks the Steam64 as dead globally. The bot updates the
  global ban list and syncs it to every server.
- **Global sync outputs** – a single `sync/ban.txt` and `sync/whitelist.txt` act as the source of
  truth and are copied to each server’s `ban.txt` and `whitelist.txt` atomically.
- **Discord slash commands** – administrators can inspect or delete entries with `/userdata` and
  `/delete_user_from_database`, while players self-register via `/validatesteamid` (restricted to the
  configured validation channel).
- **Automated reminders** – background tasks such as `watch_for_users_to_unban` and
  `check_if_users_can_revive` promote users out of the dead state once their timers expire and
  trigger a global sync.
- **GitHub Actions workflow** – `.github/workflows/codex.yml` provides a lightweight CI job that
  installs dependencies and byte-compiles the bot to catch syntax errors before deploying.

## Repository layout
```
main.py                  # Entrypoint for the Discord bot and background tasks
cogs/                    # Slash commands and event listeners (loaded dynamically)
death_watcher/           # Log parser that tails DetailedLogs for death events
userdata_db.json         # JSON document storing Discord ↔ Steam metadata
sync/                    # Global ban.txt + whitelist.txt outputs
steam_ids_to_unban.txt   # Queue of players that the bot should unban next
requirements.txt         # Python dependencies needed by both scripts
```

## Prerequisites
- Python 3.11 (matches the version used in CI)
- A Discord bot application with privileged intents enabled
- Access to the DayZ server's `.ljson` detailed logs, whitelist, and blacklist files
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
3. Review the DayZ whitelist (`path_to_whitelist`), ban list (`path_to_bans`), and
   `path_to_logs_directory` values under each `servers` entry and set `path_to_sync_dir` to a folder
   where the bot can write global `ban.txt` and `whitelist.txt` outputs.

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
| `servers` | Array of DayZ servers (1–5). Each entry supports `server_root_path` to auto-fill `path_to_logs_directory` (`profiles/DetailedLogs`), `path_to_bans` (`ban.txt`), and `path_to_whitelist` (`whitelist.txt`). Include `enable_death_scanning` if you want to disable log tailing for a specific server. |
| `path_to_sync_dir` | Folder where the bot writes the global `ban.txt` and `whitelist.txt` outputs before copying to each server. |
| `default_server_id` | Server ID used when a user has not selected an active server yet. |
| `max_active_servers` | Limits how many enabled servers the bot will watch at runtime (use `1` for a single-server setup). |
| `unban_scope` | Controls which server(s) are unbanned when a user joins/leaves private voice. Values: `active_server_only` (default), `all_servers`, `user_home_server`. |
| `validate_whitelist_scope` | Scope used by `/validatesteamid` when adding users to lists. Default: `all_servers`. |
| `enable_death_scanning` | Global toggle for Detailed Logs scanning. |
| `archive_old_ljson` | If enabled, moves older `.ljson` logs into an `archive/` folder when a new file appears. |
| `search_logs_interval` | Seconds between Detailed Logs scans. |
| `death_exceptions` | Controls which death logs should be ignored (for example maplink transfer suicides at origin). |
| `userdata_db_path` | Location of the JSON datastore the bot uses to correlate Discord users to Steam IDs. |
| `admin_role_id` | Discord role ID allowed to run admin-only slash commands. |
| `guild_id` | Discord server that the bot should operate in. |
| `join_vc_id` / `join_vc_category_id` | Voice channel & category IDs that gate players into private squad channels. |
| `validate_steam_id_channel` | Text channel where `/validatesteamid` requests are accepted. |
| `alive_role` / `dead_role` / `can_revive_role` / `season_pass_role` | Role IDs that the bot applies as users die or revive. |
| `watch_death_watcher` | Enables the embedded death watcher threads (legacy flag; the new scanner also respects `enable_death_scanning`). |
| `steam_ids_to_unban_path` | Text file that acts as a queue for Steam IDs waiting to be unbanned. |
| `error_dump_channel_id`, `error_dump_allow_mention`, `error_dump_mention_tag`, `error_dump_rate_limit_seconds`, `error_dump_include_traceback` | Controls for piping unexpected errors to a Discord channel. |
| `wait_time_new_life_seconds` / `_season_pass` | Cooldown timers before a dead player can return. |

### Global sync model
The bot now uses a single global whitelist and ban list:
- **GLOBAL_WHITELIST** = every validated Steam64 ID.
- **GLOBAL_BAN** = validated Steam64 IDs that are dead or not in their correct private voice channel.

The bot writes these lists to `path_to_sync_dir/whitelist.txt` and `path_to_sync_dir/ban.txt` and
then copies them to each server’s configured `path_to_whitelist` and `path_to_bans`. Server files are
treated as outputs only and are overwritten atomically whenever the global lists change.

### First-time GUI setup & missing paths
When you launch the GUI for the first time (or after deleting `config.json`), the app starts in a
"server roots" workflow. You'll be prompted for up to five server root folders; any blank entries are
treated as inactive. The bot derives `ban.txt`, `whitelist.txt`, and `profiles/DetailedLogs` from the
root folder automatically, then prompts for Discord IDs if they are missing. Those values are saved
back into `config.json`, so the next launch will run normally without prompting.

If a future change breaks one of the paths—for example you move the whitelist file and forget to
update the config—the worker thread raises a `MissingConfigPaths` error. The GUI pauses startup and
logs the issue so you can update the server root paths in the settings.

### Supporting data files
- `userdata_db.json` is auto-created with `{ "userdata": {} }` the first time the bot runs.
- `steam_ids_to_unban.txt` is created if missing and stores one Steam64 ID per line.
- `sync/ban.txt` and `sync/whitelist.txt` are the authoritative global outputs copied to each server.
- `death_watcher/death_watcher_cache.json` tracks per-server log cursors and status for restarts.

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
looks for the most recent `.ljson` file in `path_to_logs_directory` (for example
`E:/DayZ MM/servers/MementoMori/profiles/DetailedLogs`), reads each JSON log entry, and when it sees
`"event": "PLAYER_DEATH"` it emits the Steam64 ID to the bot for global banning. Start it in a
dedicated console:
```bash
cd death_watcher
python new_dayz_death_watcher.py
```
Adjust `death_watcher/config.json` if your log folder lives elsewhere. For multi-server setups, the
Discord bot embeds multiple watcher threads using the server definitions from `config.json`.
Use the `death_exceptions` block to ignore transfer-related suicide deaths at origin coordinates.

## Slash commands & roles
- `/validatesteamid <steam_id>` – validates that a Steam64 ID is unique, writes it to the whitelist
  based on `validate_whitelist_scope`, and assigns the "alive" role. Only works for alive users and
  inside `validate_steam_id_channel`.
- `/userdata <id> [visibility]` – Admin-only lookup by Discord ID or Steam64 ID.
- `/delete_user_from_database <user_id>` – Admin-only removal of a Discord user's entry from `userdata_db.json`.
- `/setserver <server_id>` – Admin-only update to set the invoking user's active server ID.

Roles are central to the experience: alive players gain channel access, dead players lose it, and
admins bypass voice requirements. Keep role IDs in sync with Discord whenever you modify your server.

## Multi-server behavior cheatsheet
- **Global travel**: a player alive and inside their correct private voice channel is unbanned
  globally and can move between servers without additional steps.
- **Death propagation**: a death on any server immediately marks the player dead everywhere and
  syncs the ban list to every configured server.
- **GUI server selector**: use the dropdown in the GUI header to filter the "Currently Dead" and
  "Death Counter" views by server. The "Server Activity" log view shows one panel per enabled
  server (up to five), while the Lists tab always shows the global outputs.
- **Server root shortcut**: set `server_root_path` (or use the GUI path setup) and leave the other
  per-server paths blank; the bot will derive `profiles/DetailedLogs`, `ban.txt`, and
  `whitelist.txt` automatically.

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
