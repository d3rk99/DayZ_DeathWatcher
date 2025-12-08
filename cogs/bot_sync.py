import asyncio
import json
import time
from typing import Dict, List, Optional

import aiohttp
import nextcord
from dayz_dev_tools import guid as GUID
from nextcord.ext import commands, tasks


whitelist_id_length = 17


class BotSync(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.session: Optional[aiohttp.ClientSession] = None
        self.poll_queue.start()

    def cog_unload(self):
        self.poll_queue.cancel()
        if self.session is not None:
            asyncio.create_task(self.session.close())

    def _config(self) -> Dict:
        return getattr(self.client, "config", {})

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    @tasks.loop(seconds=30)
    async def poll_queue(self):
        await self.client.wait_until_ready()

        config = self._config()
        api_url = config.get("bot_sync_api_url")
        token = config.get("bot_sync_token")
        if not api_url or not token:
            return

        session = await self._get_session()
        try:
            async with session.get(f"{api_url}/queue", headers={"X-Bot-Bridge-Token": token}) as resp:
                if resp.status != 200:
                    print(f"[BotSync] Failed to fetch queue ({resp.status})")
                    return
                jobs = await resp.json()
        except Exception as exc:
            print(f"[BotSync] Error fetching queue: {exc}")
            return

        for job in jobs:
            await self._process_job(job, api_url, token)

    async def _process_job(self, job: Dict, api_url: str, token: str):
        steam_id = str(job.get("steam64", "")).strip()
        discord_id = job.get("discord_id")
        discord_username = job.get("discord_username")

        if len(steam_id) != whitelist_id_length or not steam_id.isnumeric():
            await self._mark_job(api_url, token, job["id"], "failed", f"Invalid steam64: {steam_id}")
            return

        config = self._config()
        guild = self.client.get_guild(int(config.get("guild_id", 0)))
        if guild is None:
            await self._mark_job(api_url, token, job["id"], "failed", "Guild not configured")
            return

        try:
            await self._register_steam_id(guild, discord_id, discord_username, steam_id)
        except Exception as exc:
            await self._mark_job(api_url, token, job["id"], "failed", str(exc))
            return

        await self._mark_job(api_url, token, job["id"], "processed")

    async def _mark_job(self, api_url: str, token: str, job_id: int, status: str, error_message: Optional[str] = None):
        session = await self._get_session()
        payload = {"status": status}
        if error_message:
            payload["errorMessage"] = error_message

        try:
            async with session.patch(
                f"{api_url}/queue/{job_id}",
                headers={"X-Bot-Bridge-Token": token},
                json=payload,
            ) as resp:
                if resp.status != 200:
                    print(f"[BotSync] Failed to update job {job_id}: {resp.status}")
        except Exception as exc:
            print(f"[BotSync] Error updating job status: {exc}")

    async def _register_steam_id(self, guild: nextcord.Guild, discord_id: str, username: str, steam_id: str):
        if not discord_id:
            raise RuntimeError("Missing Discord ID for sync job")

        config = self._config()
        user_id = int(discord_id)
        guid = GUID.guid_for_steamid64(steam_id)

        userdata_json = self._read_userdata(config["userdata_db_path"])
        keys = list(userdata_json["userdata"].keys())

        steam_ids = [userdata_json["userdata"][key]["steam_id"] for key in keys]
        if steam_id in steam_ids:
            raise RuntimeError(f"Steam ID already registered ({steam_id})")

        deaths_list = self._read_lines_with_retry(config["death_watcher_death_path"], "deaths list")
        if str(guid) in deaths_list:
            raise RuntimeError(f"Steam ID is already dead ({steam_id})")

        member = guild.get_member(user_id)
        existing_userdata = userdata_json["userdata"].get(str(user_id))

        if existing_userdata:
            await self._update_existing_user(existing_userdata, steam_id, guid, config)
        else:
            await self._create_userdata_entry(userdata_json, user_id, username or str(discord_id), steam_id, guid, config)

        with open(config["userdata_db_path"], "w") as json_file:
            json.dump(userdata_json, json_file, indent=4)

        if member:
            await self._assign_roles(member, config)

    async def _update_existing_user(self, userdata: Dict, steam_id: str, guid: str, config: Dict):
        blacklist_list = self._read_lines_with_retry(config["blacklist_path"], "blacklist")
        if userdata["steam_id"] in blacklist_list:
            blacklist_list.remove(userdata["steam_id"])
        blacklist_list.append(str(steam_id))
        self._write_lines_with_retry(config["blacklist_path"], blacklist_list, "blacklist")

        whitelist_contents = self._read_text_with_retry(config["whitelist_path"], "whitelist")
        whitelist_contents = whitelist_contents.replace(userdata["steam_id"], str(steam_id))
        self._write_text_with_retry(config["whitelist_path"], whitelist_contents, "whitelist")

        userdata["steam_id"] = str(steam_id)
        userdata["guid"] = str(guid)

    async def _create_userdata_entry(self, userdata_json: Dict, user_id: int, username: str, steam_id: str, guid: str, config: Dict):
        userdata_json["userdata"][str(user_id)] = {
            "username": username,
            "steam_id": str(steam_id),
            "guid": str(guid),
            "is_alive": 1,
            "time_of_death": 0,
            "can_revive": 0,
            "is_admin": 0,
        }

        with open(config["whitelist_path"], "a") as file:
            file.write('\n' + str(steam_id))

        blacklist_list = self._read_lines_with_retry(config["blacklist_path"], "blacklist")
        blacklist_list.append(str(steam_id))
        self._write_lines_with_retry(config["blacklist_path"], blacklist_list, "blacklist")

    async def _assign_roles(self, member: nextcord.Member, config: Dict):
        alive_role = nextcord.utils.get(member.guild.roles, id=int(config.get("alive_role", 0)))
        dead_role = nextcord.utils.get(member.guild.roles, id=int(config.get("dead_role", 0)))
        if alive_role and alive_role not in member.roles and (not dead_role or dead_role not in member.roles):
            try:
                await member.add_roles(alive_role)
            except Exception:
                pass

    def _read_lines_with_retry(self, path: str, label: str) -> List[str]:
        tries = 0
        while tries < 10:
            try:
                with open(path, "r") as file:
                    return file.read().split('\n')
            except Exception as exc:
                print(f"[BotSync] Attempt {tries + 1} - Failed to open {label} file: {path} '{exc}'")
                tries += 1
                time.sleep(0.25)
        raise RuntimeError(f"Could not access {label} file after 10 tries")

    def _write_lines_with_retry(self, path: str, lines: List[str], label: str):
        tries = 0
        while tries < 10:
            try:
                with open(path, "w") as file:
                    file.write('\n'.join(lines))
                return
            except Exception as exc:
                print(f"[BotSync] Attempt {tries + 1} - Failed to write {label} file: {path} '{exc}'")
                tries += 1
                time.sleep(0.25)
        raise RuntimeError(f"Could not write {label} file after 10 tries")

    def _read_text_with_retry(self, path: str, label: str) -> str:
        tries = 0
        while tries < 10:
            try:
                with open(path, "r") as file:
                    return file.read()
            except Exception as exc:
                print(f"[BotSync] Attempt {tries + 1} - Failed to read {label} file: {path} '{exc}'")
                tries += 1
                time.sleep(0.25)
        raise RuntimeError(f"Could not read {label} file after 10 tries")

    def _write_text_with_retry(self, path: str, contents: str, label: str):
        tries = 0
        while tries < 10:
            try:
                with open(path, "w") as file:
                    file.write(contents)
                return
            except Exception as exc:
                print(f"[BotSync] Attempt {tries + 1} - Failed to write {label} file: {path} '{exc}'")
                tries += 1
                time.sleep(0.25)
        raise RuntimeError(f"Could not write {label} file after 10 tries")

    def _read_userdata(self, path: str) -> Dict:
        with open(path, "r") as json_file:
            return json.load(json_file)


def setup(client):
    client.add_cog(BotSync(client))
