# DeathWatcher

DeathWatcher is a Discord bot (discord.py 2.x) built to enforce a DayZ server's join rules using detailed log files and DayZ `ban.txt`/`whitelist.txt` files. The bot gates voice access to a private voice channel, bans dead players for a configurable time window, and keeps user metadata in simple JSON stores.

## Features
- Tails the latest DayZ Detailed Logs `dl_YYYYMMDD_HHMMSS.ljson` file and persists the cursor between restarts.
- Detects `PLAYER_DEATH` events, records lifetimes, bans the Steam64, kicks the user from voice, and swaps Alive/Dead roles.
- Automatically revives users once `deadUntil` expires or when an admin reapplies the Alive role.
- Voice join flow that creates a per-player private voice channel under an online category, moves the player there, and unbans them. Leaving the private channel re-adds the ban.
- Stores users and cache data in JSON for easy portability.

## Setup
1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `config.example.json` to `config.json` and fill in your values.
3. Create empty files for your DayZ lists and databases if they do not exist:
   ```bash
   touch ban.txt whitelist.txt userdata_db.json cache.json
   ```
4. Run the bot:
   ```bash
   python main.py --config config.json
   ```

### Required Discord intents and permissions
- Privileged intent: **Server Members Intent** (for role and voice enforcement).
- Privileged intent: **Presence Intent** is *not* required.
- Voice and role management permissions for the bot in the target guild.
- Permission to manage channels in the online category for creating/deleting private VCs.

## Configuration reference
See `config.example.json` for the full structure. Key sections include:
- `discord`: bot token, guild ID, Alive/Dead/Admin role IDs, the join lobby voice channel ID, the online category ID, and the bot spam text channel ID.
- `paths`: locations for DayZ logs, JSON user DB, cache, and the `ban.txt` / `whitelist.txt` files.
- `ban_duration_days`: number of days to keep a player dead after a death event.
- `verbose_logs`: enable DEBUG logging when true.

## Project layout
- `src/bot/`: bot orchestration and Discord event handlers.
- `src/watchers/`: log tailing utilities.
- `src/services/`: persistence helpers for ban/whitelist, cache, and user DB storage.
- `src/models/`: config and data models.
- `main.py`: entrypoint to load config and start the bot.

## Test plan (manual)
- [ ] Start the bot with valid config; observe the "Logged in" message in logs.
- [ ] Join the join lobby voice channel as a validated user; confirm a private VC is created and you are moved/unbanned.
- [ ] Leave the private VC; confirm the Steam64 is added back to `ban.txt` and the empty channel is deleted.
- [ ] Trigger a `PLAYER_DEATH` log line for a known Steam64; confirm the user is kicked from voice, ban is added, and roles are swapped.
- [ ] Wait for the revive timer or manually add the Alive role; confirm the ban is lifted and roles are updated.
