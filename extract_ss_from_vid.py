import os
from os.path import join
import argparse
from urllib.parse import urlparse
import multiprocessing
from collections import namedtuple
import cv2
from tqdm import tqdm
import youtube_dl
import requests


YOUTUBE_DL_OPTIONS = {
    "format": "bestvideo[ext=mp4][height<=1080]/best[ext=mp4][height<=1080]",
    "outtmpl": "%(uploader)s@%(id)s.%(ext)s",
}
SKIP = 10
TEMPLATE_MATCH_THRESHOLD = 0.2
DUPE_THRESHOLD = 0.001
DROP_TEXT_TEMPLATE = "drop_text.png"
Crop = namedtuple("Crop", ["top", "left", "bottom", "right"])


def recognize_drop_text(frame, template, name, crop_param):
    res = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
    # loc = np.where(res < THRESHOLD)
    min_val, _, _, _ = cv2.minMaxLoc(res, None)
    # loc is empty if the frame doesn't match
    # return loc[0].size > 0
    if min_val < TEMPLATE_MATCH_THRESHOLD:
        # if loc[0].size > 0:
        if crop_param is not None:
            cv2.imwrite(name, frame)
        else:
            # print(f"Writing {name}")
            # cv2.imwrite(name, frame[10:110, 10:210])
            cv2.imwrite(
                name,
                frame[
                    crop_param.top : crop_param.bottom,
                    crop_param.left : crop_param.right,
                ],
            )


def extract_drop_screen(file, ss, to, crop_param, output_folder, processes, template):
    cap = cv2.VideoCapture(file)
    file = os.path.splitext(file)[0]
    template = cv2.imread(join("template", template))
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
                            join(output_folder, f"{file}@{frame_id/fps:.2f}@.png"),
                            crop_param,
                        ),
                    )
                pbar.update(1)
            else:
                break
    cap.release()


def remove_dupe_images(output_folder):
    files = os.listdir(output_folder)
    files = sorted(files)
    base_image = cv2.imread(join(output_folder, files[0]))
    for file in files[1:]:
        full_path = join(output_folder, file)
        img = cv2.imread(full_path)
        res = cv2.matchTemplate(base_image, img, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(res, None)
        if min_val < DUPE_THRESHOLD:
            os.remove(full_path)
        else:
            base_image = img


def run(
    link, ss, to, crop_param, quest, processes, template,
):
    quest_folder = join("input", str(quest))
    if not os.path.isdir(quest_folder):
        os.mkdir(quest_folder)
    if os.path.exists(link):
        file_name = link
    else:
        try:
            ydl = youtube_dl.YoutubeDL(YOUTUBE_DL_OPTIONS)
            ydl.add_default_info_extractors()
            info = ydl.extract_info(link, download=False)
            file_name = f"{info['uploader']}@{info['id']}.mp4"
            if not os.path.exists(file_name):
                ydl.download(link)
        except (youtube_dl.utils.UnsupportedError, youtube_dl.utils.DownloadError):
            print("Youtube-dl can't download the given link")

    if crop_param is not None:
        crop_param = Crop(*[int(c) for c in crop_param])

    if template.startswith("http"):
        response = requests.get(template)
        template = os.path.basename(urlparse(template).path)
        with open(join("template", template), "wb") as f:
            f.write(response.content)

    extract_drop_screen(
        file_name, ss, to, crop_param, quest_folder, processes, template
    )
    remove_dupe_images(quest_folder)


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
    parser.add_argument(
        "-q",
        "--quest",
        help="Output quest folder in input folder",
        default="video_screenshot",
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
    args = parser.parse_args()
    run(
        args.input,
        args.ss,
        args.to,
        args.crop,
        args.quest,
        args.num_processes,
        args.template,
    )
