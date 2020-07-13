import argparse
import multiprocessing
import os
import sys
from collections import namedtuple
from datetime import datetime
from os.path import join
from pathlib import Path
from urllib.parse import urlparse

import cv2
import pytz
import requests
import streamlink
import youtube_dl
from tqdm import tqdm


YOUTUBE_DL_OPTIONS = {
    "format": "bestvideo[ext=mp4][height<=1080]/best[ext=mp4][height<=1080]",
    "outtmpl": "%(uploader)s@%(id)s.%(ext)s",
}
SKIP = 3
TEMPLATE_MATCH_THRESHOLD = 0.2
DUPE_THRESHOLD = 0.1
DROP_TEXT_TEMPLATE = "drop_text.png"
Crop = namedtuple("Crop", ["top", "left", "bottom", "right"])


def recognize_drop_text(frame, template, name, crop_param):
    res = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
    # loc = np.where(res < THRESHOLD)
    min_val, _, _, _ = cv2.minMaxLoc(res, None)
    # loc is empty if the frame doesn't match
    # return loc[0].size > 0
    # print(name, min_val)
    if min_val < TEMPLATE_MATCH_THRESHOLD:
        # if loc[0].size > 0:
        if crop_param is None:
            cv2.imwrite(name, frame)
        else:
            # print(f"Writing {name}")
            cv2.imwrite(
                name,
                frame[
                    crop_param.top : crop_param.bottom,
                    crop_param.left : crop_param.right,
                ],
            )


def extract_drop_screen(
    file, local_file, ss, to, crop_param, output_folder, processes, template
):
    cap = cv2.VideoCapture(file)
    local_file = os.path.splitext(local_file)[0]
    template = cv2.imread(template)
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    if ss is None:
        ss_frame = 0
    else:
        ss_frame = int(ss) * fps
    if to is None:
        to_frame = total_frame_count
    else:
        to_frame = int(to) * fps
    # print(ss_frame, to_frame, fps)
    pool = multiprocessing.Pool(processes=processes)
    with tqdm(total=total_frame_count) as pbar:
        while cap.isOpened():
            ret, frame = cap.read()
            frame_id = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if ret:
                if (ss_frame <= frame_id <= to_frame) and (frame_id % SKIP == 0):
                    pool.apply_async(
                        recognize_drop_text,
                        (
                            frame.copy(),
                            template,
                            join(
                                output_folder, f"{local_file}@{frame_id/fps:.2f}@.png"
                            ),
                            crop_param,
                        ),
                    )
                pbar.update(1)
            else:
                break
    cap.release()
    pool.close()
    pool.join()


def remove_dupe_images(output_folder):
    files = sorted(os.listdir(output_folder))
    same_image = [files[0]]
    base_image = cv2.imread(join(output_folder, files[0]))
    for file in files[1:]:
        img = cv2.imread(join(output_folder, file))
        res = cv2.matchTemplate(base_image, img, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(res, None)
        if min_val < DUPE_THRESHOLD:
            same_image.append(file)
        else:
            same_image.pop(len(same_image) // 2)
            for dupe_img in same_image:
                os.remove(join(output_folder, dupe_img))
            same_image = [file]
            base_image = img
    same_image.pop(len(same_image) // 2)
    for dupe_img in same_image:
        os.remove(join(output_folder, dupe_img))


def remove_blank_drops(output_folder):
    files = sorted(os.listdir(output_folder))
    for file in files:
        img = cv2.imread(join(output_folder, file))
        height, width, _ = img.shape
        gray_image = cv2.cvtColor(
            img[
                int(height * 0.2) : int(height * 0.7),
                int(width * 0.1) : int(width * 0.85),
            ],
            cv2.COLOR_BGR2GRAY,
        )
        _, binary = cv2.threshold(gray_image, 225, 255, cv2.THRESH_BINARY)
        percentage_color = (binary.sum() / 255) / (
            (0.7 - 0.2) * height * (0.85 - 0.1) * width
        )
        if percentage_color < 0.005:
            os.remove(join(output_folder, file))


def run(
    link, live_stream, ss, to, crop_param, output_folder, processes, template,
):
    output_folder.mkdir(parents=True, exist_ok=True)
    if os.path.exists(link):
        file_name = link
        local_file = file_name.parent.name + "@" + file_name.name
    else:
        if live_stream:
            stream = streamlink.streams(link)["best"]
            file_name = stream.url
            streamer = file_name.split("/")[-1]
            current_pacific_time = datetime.now(pytz.timezone("US/Pacific"))
            local_file = f"{streamer}@live{current_pacific_time:%Y-%m-%d %H-%M:%S}.mp4"
        else:
            try:
                ydl = youtube_dl.YoutubeDL(YOUTUBE_DL_OPTIONS)
                ydl.add_default_info_extractors()
                info = ydl.extract_info(link, download=False)
                file_name = f"{info['uploader']}@{info['id']}.mp4"
                local_file = file_name
                if not os.path.exists(file_name):
                    ydl.download([link])
            except (youtube_dl.utils.UnsupportedError, youtube_dl.utils.DownloadError):
                print("Youtube-dl can't download the given link")
                sys.exit(0)

    if crop_param is not None:
        crop_param = Crop(*[int(c) for c in crop_param])

    if template.startswith("http"):
        response = requests.get(template)
        template = os.path.basename(urlparse(template).path)
        with open(join("template", template), "wb") as f:
            f.write(response.content)

    print(file_name)
    print(output_folder)

    extract_drop_screen(
        str(file_name), local_file, ss, to, crop_param, str(output_folder), processes, template
    )
    remove_dupe_images(output_folder)
    remove_blank_drops(output_folder)


if __name__ == "__main__":
    for work_folder in ["input", "template"]:
        if not os.path.exists(work_folder):
            os.makedirs(work_folder)
    parser = argparse.ArgumentParser(
        description="Get drop screenshots from Youtube link"
    )
    parser.add_argument("-i", "--input", help="File or Youtube link to download")
    parser.add_argument(
        "-t",
        "--template",
        help="Template image or URL for the drop screen",
        default=DROP_TEXT_TEMPLATE,
    )
    parser.add_argument("-ss", help="Start")
    parser.add_argument("-to", help="End")
    parser.add_argument(
        "-n",
        "--num-processes",
        help="Number of processes to run",
        default=cv2.getNumberOfCPUs(),
    )
    parser.add_argument("-c", "--crop", nargs=4, help="Crop: top, left, bottom, right")
    parser.add_argument("-l", "--live", action="store_true")
    args = parser.parse_args()
    input_path = Path(args.input).resolve()
    if input_path.is_dir():
        for video in input_path.iterdir():
            if video.name.endswith(".mp4"):
                run(
                    video,
                    args.live,
                    args.ss,
                    args.to,
                    args.crop,
                    input_path / "input" / "fp",
                    args.num_processes,
                    args.template,
                )
