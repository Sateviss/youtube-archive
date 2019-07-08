import os
import logging

CHANNEL_LIST = "channel_list"
DOWNLOADED_VIDEOS = "video_list.json"

ARCHIVE_PATH = os.path.join(os.path.curdir, "Archive")
OUTPUT_FORMAT = os.path.join(ARCHIVE_PATH, "%(uploader)s/%(upload_date)s %(title)s/%(title)s.%(ext)s")

DOWNLOAD_OPTIONS = {
    "outtmpl": OUTPUT_FORMAT,
    "writethumbnail": True,
    "merge_output_format": "mp4",
    "geo_bypass": True,
    "prefer_ffmpeg": True,
    "format": "bestvideo+bestaudio[ext=m4a]/best",
    # "postprocessors": [
    #     {
    #         "key": "ExecAfterDownload",
    #         "exec_cmd": """echo {} | sed 's/\..\{0,4\}$/.mp3/' | tr -d '\\n' | xargs -0 ffmpeg -loglevel warning -y -i {}"""
    #     }
    # ],
    "writesubtitles": True,
    "allsubtitles": True,
    "writeinfojson": True,
    "continuedl": True
}

BYPASS_CODES = [
    "BY",
    "US",
    "GB",
    "RU",
    "NL",
    "NZ",
    "AU",
    "NE"

]

DOWNLOAD_THREADS = 2
LOGLEVEL = logging.DEBUG
