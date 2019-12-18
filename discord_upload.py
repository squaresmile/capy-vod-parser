import os
from os.path import join
import discord

CHANNEL = "bots-la-soleil"
FOLDER = "input"


def is_twitter_vod(video_id):
    return video_id[0] == "v" and video_id[1:].isnumeric()


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print("We have logged in as {0.user}".format(client))
        quests = [f for f in os.listdir(FOLDER) if f != "video_screenshot"]
        for quest_folder in quests:
            print(quest_folder)
            if not os.path.exists(join("uploaded", quest_folder)):
                os.mkdir(join("uploaded", quest_folder))
            for channel in client.get_all_channels():
                if str(channel) == quest_folder:
                    for screenshot in os.listdir(join(FOLDER, quest_folder)):
                        streamer, video_id, timestamp, _ = screenshot.split("@")
                        timestamp = int(float(timestamp))
                        to_upload_path = join(FOLDER, quest_folder, screenshot)
                        stream_url_timestamp = ""
                        if is_twitter_vod(video_id):
                            # https://www.twitch.tv/videos/523062473?t=0h5m51s
                            m, s = divmod(timestamp, 60)
                            h, m = divmod(m, 60)
                            stream_url_timestamp = f"https://www.twitch.tv/videos/{video_id}?t={h}h{m}m{s}s"
                        else:
                            stream_url_timestamp = (
                                f"https://youtu.be/{video_id}?t={timestamp}"
                            )
                        await channel.send(
                            f"{streamer} <{stream_url_timestamp}>",
                            file=discord.File(to_upload_path, screenshot),
                        )
                        os.rename(
                            to_upload_path, join("uploaded", quest_folder, screenshot),
                        )
        await self.close()


if __name__ == "__main__":
    with open("discord_api_token.txt") as f:
        discord_api_token = f.read().strip()
    for work_folder in ["uploaded"]:
        if not os.path.exists(work_folder):
            os.makedirs(work_folder)
    client = MyClient()
    client.run(discord_api_token)
