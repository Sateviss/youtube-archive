#! /bin/env python3

import json
import logging
import os
import random
from datetime import date
import queue

from multiprocessing import Lock
from multiprocessing.pool import ThreadPool

import youtube_dl
from youtube_dl.utils import date_from_str

from config import *


logging.basicConfig(format="%(asctime)s [%(levelname)s] (%(name)s): %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=LOGLEVEL)

if __name__ == "__main__":
    # Load a list of channels for download from CHANNEL_LIST
    channels = {}
    logging.info("Loading playlist list...")
    with open(CHANNEL_LIST) as cl:
        for line in cl.readlines():
            # Remove leading whitespace
            line_l = line.split("#")[0].lstrip()
            # Skip all lines starting with "#"
            if len(line_l) == 0:
                continue
            line_s = line_l.split()
            # If the line is just one "word", i.e. no date given,
            #  download last 1000 years of content
            if len(line_s) == 1:
                channels.update({line_s[0]: {"url": line_s[0], "date_from": "now-1000years", "date_to": "now+1000years"}})
            elif len(line_s) == 2:
                channels.update({line_s[0]: {"url": line_s[0], "date_from": line_s[1], "date_to": "now+1000years"}})
            elif len(line_s) == 3:
                channels.update({line_s[0]: {"url": line_s[0], "date_from": line_s[1], "date_to": line_s[2]}})
            logging.debug("Added "+str(line_s[0]))
    logging.info("Loaded {} playlists".format(len(channels)))
    
    # Get a list of videos for each channel
    for _, channel in channels.items():
        videos = {}
        opts = {
            "quiet": True,
            "extract_flat": True
        }
        logging.info("Getting the list of videos in \"{}\"...".format(channel["url"]))
        with youtube_dl.YoutubeDL(opts) as ytd:
            # Get the URL of channle uploads playlist, instead of channel URL
            playlist = ytd.extract_info(channel["url"])["url"]
            data = ytd.extract_info(playlist)
            logging.info("Extracted IDs for {} videos in \"{}\"".format(len(data["entries"]), data["title"]))
            for video in data["entries"]:
                videos.update({video["id"]:{
                    "title": video["title"],
                    "url": video["url"]
                }})

            channel.update({"title": data["title"], "videos": videos})

    logging.info("Downloaded video list")
    dv = json.load(open(DOWNLOADED_VIDEOS)) if os.path.exists(DOWNLOADED_VIDEOS) else {}

    # List of videos with unknown info (like upload date)
    get_info_list = []
    # List of videos that should be downloaded
    download_list = []

    # Check the list of downloaded videos
    for url in channels.keys():

        # If this channel has some videos on the list...
        if url in dv.keys():

            # Update the title, just in case
            dv[url]["title"] = channels[url]["title"]
            # For each video in the CURRENT list
            for video_id in channels[url]["videos"].keys():

                # If it has a status of some kind
                if video_id in dv[url]["videos"].keys():
                    if dv[url]["videos"][video_id]["status"] == "downloaded":
                        # Skip downloaded videos
                        continue
                    elif dv[url]["videos"][video_id]["status"] == "downloading":
                        # Continue downloads for ANY video that hasn't finished
                        logging.debug("Resuming the download of \"{}\" from \"{}\"".format(dv[url]["videos"][video_id]["title"], channels[url]["title"]))
                        download_list.append((url, video_id))
                    elif dv[url]["videos"][video_id]["status"] == "checked":
                        # Put the video that fits parameters into the list
                        if date_from_str(channels[url]["date_from"]) < date_from_str(dv[url]["videos"][video_id]["date"]) < date_from_str(channels[url]["date_to"]):
                            logging.debug("Added \"{}\" from \"{}\" to download_list".format(dv[url]["videos"][video_id]["title"], channels[url]["title"]))
                            download_list.append((url, video_id))
                else:
                    get_info_list.append((url, video_id))

        else:
            dv.update({url: {
                "title": channels[url]["title"],
                "url": url,
                "videos": {}
            }})
            for video_id in channels[url]["videos"].keys():
                get_info_list.append((url, video_id))

    logging.info("Staged {} videos for download".format(len(download_list)))
    logging.info("Updating information about {} videos in {} threads...".format(len(get_info_list), DOWNLOAD_THREADS))

    lock = Lock()

    def get_info(info):
        url, video_id = info

        extracted = 1
        for code in BYPASS_CODES:
            opts = {"quiet": True, "geo_bypass": True, "geo_bypass_country": code}
            try:
                with youtube_dl.YoutubeDL(opts) as ytd:
                    extracted = ytd.extract_info(channels[url]["videos"][video_id]["url"], download=False)
                break
            except:
                logging.warning("\"{}\" from \"{}\" is blocked in {}".format(video_id, channels[url]["title"], code))
                continue
        if extracted == 1:
            logging.warning("\"{}\" from \"{}\" is blocked in all countries on the list".format(video_id, channels[url]["title"]))
            return
                 
        lock.acquire()
        if video_id in dv[url]["videos"].keys():
            dv[url]["videos"][video_id]["title"] = extracted["title"]
            dv[url]["videos"][video_id]["date"] = extracted["upload_date"]
            dv[url]["videos"][video_id]["url"] = extracted["webpage_url"]
        else:
            dv[url]["videos"].update({video_id: 
                {
                    "title": extracted["title"],
                    "date": extracted["upload_date"],
                    "url": extracted["webpage_url"],
                    "status": "checked"
                }
            })
        with open(DOWNLOADED_VIDEOS, "w") as dvf:
            json.dump(dv, dvf, indent=2)

        if date_from_str(channels[url]["date_from"]) < date_from_str(extracted["upload_date"]) < date_from_str(channels[url]["date_to"]):
            logging.debug("Added \"{}\" from \"{}\" to download_list".format(extracted["title"], channels[url]["title"]))
            download_list.append((url, video_id))
        else:
            logging.debug("\"{}\" from \"{}\" is not in date range, skipping".format(extracted["title"], channels[url]["title"]))
        lock.release()

    with ThreadPool(DOWNLOAD_THREADS) as p:
        p.map(get_info, get_info_list)

    logging.info("Downloading {} videos in {} threads...".format(len(download_list), DOWNLOAD_THREADS))

    def download(info):
        channel_url, video_id = info
        lock.acquire()
        dv[channel_url]["videos"][video_id]["status"] = "downloading"
        with open(DOWNLOADED_VIDEOS, "w") as dvf:
            json.dump(dv, dvf, indent=2)
        lock.release()
        try:

            extracted = 1
            for code in BYPASS_CODES:
                opts = {"quiet": True, "geo_bypass": True, "geo_bypass_country": code}
                try:
                    opts.update({"logger": logging, "geo_bypass_country": code})
                    with youtube_dl.YoutubeDL(DOWNLOAD_OPTIONS) as ytd:
                        extracted = ytd.download([dv[channel_url]["videos"][video_id]["url"]])
                    break
                except:
                    logging.warning("\"{}\" from \"{}\" is blocked in {}".format(video_id, channels[url]["title"], code))
                    continue
            if extracted == 1:
                logging.warning("\"{}\" from \"{}\" is blocked in all countries on the list".format(video_id, channels[url]["title"]))
                return

            lock.acquire()
            dv[channel_url]["videos"][video_id]["status"] = "downloaded"
            with open(DOWNLOADED_VIDEOS, "w") as dvf:
                json.dump(dv, dvf, indent=2)
            lock.release()
    
        except Exception as e:
            logging.error("An error occured while downloading {}".format(dv[channel_url]["videos"][video_id]["title"]))
            logging.error(e)

    with ThreadPool(DOWNLOAD_THREADS) as p:
        p.map(download, download_list)

    logging.info("Download finished, bye!")
