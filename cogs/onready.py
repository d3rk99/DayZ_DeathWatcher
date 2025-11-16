import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import platform
import json
import nextcord
from nextcord.ext import commands
from main import *

class Onready(commands.Cog):
    
    def __init__(self, client):
        self.client = client

    global config
    with open("config.json") as file:
        config = json.load(file)

    @commands.Cog.listener()
    async def on_ready(self):
        print("-------------------")
        print(f"Logged in as: {self.client.user.name}")
        print(f"Nextcord API Version: {nextcord.__version__}")
        print(f"Python Version: {platform.python_version()}")
        print(f"OS: {platform.system()} {platform.release()} ({os.name})")
        print("-------------------")



def setup(client):
    client.add_cog(Onready(client))