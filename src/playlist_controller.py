#!/usr/bin/env python3

import argparse
import logging
import math
import signal
import subprocess
import time

from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# Configuration
TIMEZONE = ZoneInfo("America/New_York")

# Approximate location: Midlothian, Virginia
LATITUDE = 37.50
LONGITUDE = -77.65

VIDEO_DIR = Path.home() / "videos"

DEFAULT_VIDEO = "pumpkin_vertical.mp4"
DUSK_VIDEO = "charlie-brown-thanksgiving-portrait-rotated.mp4"
AFTER_10PM_VIDEO = "pumpkin_vertical.mp4"

CUTOFF_TIME = clock_time(22, 0)

CHECK_INTERVAL = 5
RESTART_DELAY = 3

VLC_COMMAND = [
    "cvlc",
    "--vout=drm_vout",
    "--drm-vout-no-modeset",
    "--aout=alsa",
    "--alsa-audio-device=hdmi:CARD=vc4hdmi,DEV=0",
    "--fullscreen",
    "--loop",
]

running = True


def solar_event(day, latitude, longitude, zenith=90.833):
    """Calculate local sunset using a NOAA-style approximation."""

    day_of_year = day.timetuple().tm_yday
    longitude_hour = longitude / 15.0

    approximate_time = day_of_year + (
        (18 - longitude_hour) / 24
    )

    mean_anomaly = (0.9856 * approximate_time) - 3.289

    true_longitude = (
        mean_anomaly
        + 1.916 * math.sin(math.radians(mean_anomaly))
        + 0.020 * math.sin(math.radians(2 * mean_anomaly))
        + 282.634
    ) % 360

    right_ascension = math.degrees(
        math.atan(0.91764 * math.tan(math.radians(true_longitude)))
    ) % 360

    longitude_quadrant = math.floor(true_longitude / 90) * 90
    ascension_quadrant = math.floor(right_ascension / 90) * 90

    right_ascension += longitude_quadrant - ascension_quadrant
    right_ascension /= 15

    sin_declination = (
        0.39782 * math.sin(math.radians(true_longitude))
    )

    cos_declination = math.cos(
        math.asin(sin_declination)
    )

    cos_hour_angle = (
        math.cos(math.radians(zenith))
        - sin_declination * math.sin(math.radians(latitude))
    ) / (
        cos_declination * math.cos(math.radians(latitude))
    )

    if not -1 <= cos_hour_angle <= 1:
        raise ValueError("Sunset cannot be calculated for this date")

    hour_angle = math.degrees(math.acos(cos_hour_angle)) / 15

    local_mean_time = (
        hour_angle
        + right_ascension
        - 0.06571 * approximate_time
        - 6.622
    )

    utc_hour = (local_mean_time - longitude_hour) % 24

    utc_midnight = datetime(
        day.year, day.month, day.day,
        tzinfo=ZoneInfo("UTC")
    )

    sunset_utc = utc_midnight + timedelta(hours=utc_hour)

    return sunset_utc.astimezone(TIMEZONE)


def scheduled_video(now):
    sunset = solar_event(
        now.date(),
        LATITUDE,
        LONGITUDE
    )

    if now.time() >= CUTOFF_TIME:
        return AFTER_10PM_VIDEO, sunset

    if now >= sunset:
        return DUSK_VIDEO, sunset

    return DEFAULT_VIDEO, sunset


def stop_vlc(process):
    if process is None or process.poll() is not None:
        return

    logging.info("Stopping VLC PID %s", process.pid)

    process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def start_vlc(video):
    path = VIDEO_DIR / video

    if not path.is_file():
        raise FileNotFoundError(path)

    command = VLC_COMMAND + [str(path)]

    logging.info("Starting video: %s", path)

    return subprocess.Popen(command)


def handle_signal(signum, frame):
    global running
    running = False


def main():
    global running

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the scheduled video without launching VLC"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    now = datetime.now(TIMEZONE)
    video, sunset = scheduled_video(now)

    logging.info("Current time: %s", now.isoformat())
    logging.info("Today's sunset: %s", sunset.isoformat())
    logging.info("Scheduled video: %s", video)

    if args.dry_run:
        return

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    process = None
    active_video = None

    try:
        while running:
            now = datetime.now(TIMEZONE)
            video, sunset = scheduled_video(now)

            if video != active_video:
                stop_vlc(process)
                process = None

                process = start_vlc(video)
                active_video = video

            elif process is not None and process.poll() is not None:
                logging.warning(
                    "VLC exited with code %s; restarting",
                    process.returncode
                )

                time.sleep(RESTART_DELAY)

                if running:
                    process = start_vlc(video)

            time.sleep(CHECK_INTERVAL)

    finally:
        stop_vlc(process)
        logging.info("Playlist controller stopped")


if __name__ == "__main__":
    main()
