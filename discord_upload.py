import os
from os.path import join
import discord

CHANNEL = "bots-la-soleil"
FOLDER = "input"

client = discord.Client()

with open("discord_api_token.txt") as f:
    discord_api_token = f.read().strip()
for work_folder in ["uploaded"]:
    if not os.path.exists(work_folder):
        os.makedirs(work_folder)


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))
    for quest_folder in os.listdir(FOLDER):
        if not os.path.exists(join("uploaded", quest_folder)):
            os.mkdir(join("uploaded", quest_folder))
        for channel in client.get_all_channels():
            if str(channel) == quest_folder:
                for screenshot in os.listdir(join(FOLDER, quest_folder)):
                    youtuber, video_id, timestamp, _ = screenshot.split("@")
                    timestamp = int(float(timestamp))
                    # print(f"{youtuber} https://youtu.be/{video_id}?t={timestamp}")
                    # print(join(FOLDER, quest_folder, screenshot))
                    to_upload_path = join(FOLDER, quest_folder, screenshot)
                    await channel.send(
                        f"{youtuber} <https://youtu.be/{video_id}?t={timestamp}>",
                        file=discord.File(to_upload_path, screenshot),
                    )
                    os.rename(
                        to_upload_path, join("uploaded", quest_folder, screenshot),
                    )


client.run(discord_api_token)
