# **Playlist Controller — Requirements and Architecture**

**Project:** `vlc-main`\
**Host:** `vlc-00`\
**Hardware:** Raspberry Pi Zero 2 W\
**Operating system:** Raspberry Pi OS Bookworm, 32-bit ARM\
**Application:** `src/playlist_controller.py`

The goal is to build a **headless, configuration-driven VLC playback controller** that selects and plays videos according to a daily schedule, survives process failures, and starts the correct video after reboot.

The initial implementation targets one Raspberry Pi, but its architecture should support our future four-Pi synchronized playback system.

## **1. Functional requirements**

| ID    | Requirement                                                           | Priority |
| ----- | --------------------------------------------------------------------- | -------- |
| FR-01 | Load all application settings from `config.json`                      | Required |
| FR-02 | Support a configurable default video                                  | Required |
| FR-03 | Support multiple scheduled video entries                              | Required |
| FR-04 | Support fixed times such as `08:00` and `22:00`                       | Required |
| FR-05 | Support sunset-based schedule transitions                             | Required |
| FR-06 | Calculate sunset locally without internet access                      | Required |
| FR-07 | Support schedules spanning midnight                                   | Required |
| FR-08 | Determine the appropriate video based on current local time           | Required |
| FR-09 | Start the correct video immediately when the controller starts        | Required |
| FR-10 | Automatically change videos at scheduled transitions                  | Required |
| FR-11 | Loop the selected video continuously                                  | Required |
| FR-12 | Restart VLC if it crashes or exits unexpectedly                       | Required |
| FR-13 | Stop the existing VLC process cleanly when switching videos           | Required |
| FR-14 | Clean up VLC processes when the controller shuts down                 | Required |
| FR-15 | Provide a `--dry-run` mode that evaluates scheduling without playback | Required |
| FR-16 | Automatically start the controller when the Raspberry Pi boots        | Required |
| FR-17 | Support multiple different video files                                | Required |

### **Scheduling behavior**

For our initial configuration:

Illustrative daily playback schedule

The controller must not assume sunset occurs at a fixed clock time. It changes throughout the year and must account for the configured timezone and daylight saving time.

The default video is currently `charlie-brown-thanksgiving-portrait-rotated.mp4`. Our draft configuration also uses that file for the sunset window and `pumpkin_vertical.mp4` after 10 PM. Those choices should remain editable in JSON without modifying Python.

## **2. Configuration requirements**

**All deployment-specific values must live in&#x20;**`config.json`**, not in Python source code.**

| Configuration section | Settings                                                                   |
| --------------------- | -------------------------------------------------------------------------- |
| `player`              | Player name, video directory, default video, check interval, restart delay |
| `location`            | Latitude, longitude, IANA timezone                                         |
| `vlc`                 | Executable and command-line options                                        |
| `schedule`            | Video filename, start event/time, end event/time                           |

Additional configuration requirements:

- Validate the JSON structure at startup.
- Report missing video files and invalid schedule entries clearly.
- Reject invalid clock times, timezones, and geographic coordinates.
- Resolve relative video filenames against the configured video directory.
- Define deterministic behavior for overlapping schedule entries.
- Treat schedule intervals as start-inclusive and end-exclusive.
- Support intervals spanning midnight, including solar-event boundaries.
- Define a clear fallback when no schedule entry applies.
- Keep all timestamps timezone-aware.

The controller should receive an optional `--config` argument, with `~/vlc-main/config.json` as the default location.

## **3. Application architecture**

I recommend separating configuration, scheduling, process management, and orchestration into independent components.

Proposed application architecture

### **Component responsibilities**

**Configuration loader**

Reads and validates `config.json`. Provides the application with validated settings. It does not launch VLC or calculate schedules.

**Schedule engine**

A pure-Python component that accepts a timezone-aware `datetime` and returns the selected video. It handles calendar dates, clock-time boundaries, sunset calculations, overnight intervals, and schedule priority.

This separation makes scheduling logic easy to test without a Raspberry Pi or display.

**VLC process manager**

Owns the VLC subprocess, created using `subprocess.Popen()`.

It handles launching, monitoring, terminating, and restarting VLC. It should track the specific child process it launched, rather than indiscriminately killing every VLC process on the machine.

**Playlist controller**

Coordinates the other components. It checks the selected video, requests transitions when necessary, and handles shutdown signals.

## **4. Runtime behavior**

The main control loop should operate as follows:

1. Load and validate `config.json`.
2. Establish a trustworthy local clock and calculate today's schedule.
3. Determine the video that should be playing right now.
4. Launch VLC directly using `subprocess.Popen()`.
5. Monitor the clock, current selection, and VLC process.
6. When the schedule changes, stop the existing VLC process and launch the newly selected video.
7. If VLC exits unexpectedly, restart it with a configurable delay.
8. On SIGTERM or Ctrl+C, terminate VLC cleanly and exit.

The implementation should also avoid rapid restart loops if a video or VLC configuration repeatedly fails.

## **5. VLC and hardware requirements**

The controller must preserve the command-line settings we've already tested successfully:

```
cvlc \
    --vout=drm_vout \
    --drm-vout-no-modeset \
    --aout=alsa \
    --alsa-audio-device=hdmi:CARD=vc4hdmi,DEV=0 \
    --fullscreen \
    --loop \
    /home/greg/videos/VIDEO.mp4
```

The working system is headless and does not require X11, Wayland, PipeWire, or Bluetooth audio.

VLC-specific settings will be read from `config.json`, and the controller will **not** call `scripts/play.sh`.

## **6. Startup and reliability requirements**

The controller will eventually run as a systemd service.

| Requirement                 | Design                                              |
| --------------------------- | --------------------------------------------------- |
| Automatic boot startup      | systemd unit                                        |
| Correct video after restart | Evaluate schedule on startup                        |
| No display server           | Run directly through DRM/KMS                        |
| Reliable clock              | Use NTP synchronization; handle clock not yet ready |
| Logging                     | Python `logging`, visible through journald          |
| Process recovery            | Monitor VLC and restart after failures              |
| Graceful shutdown           | SIGTERM handling                                    |
| Network outages             | Continue local scheduling and playback              |
| No hardware RTC             | Handle potentially stale time at boot               |

We haven't installed this service yet. The initial implementation will run interactively so we can validate its behavior without impacting boot reliability.

## **7. Future multi-Pi architecture**

We should prepare the design for four synchronized Raspberry Pis without implementing distributed synchronization yet.

The parent controller will ultimately identify the three children in configuration and coordinate playback of four different but related videos.

For that future extension, we should keep scheduling decisions separate from actual playback commands. Eventually, the same schedule decision can trigger either local VLC playback or coordinated commands to multiple players.

**Important:** Synchronized video starts are not equivalent to synchronized frames. Tight synchronization will require additional design for clock offsets, playback position, startup latency, and drift correction.

## **8. Proposed project files**

```
vlc-main/
├── config.json
├── CONFIG.md
├── TODO.md
├── config_backup/
├── scripts/
│   ├── play.sh
│   └── github.sh
├── src/
│   ├── playlist_controller.py
│   ├── configuration.py
│   ├── scheduler.py
│   ├── solar.py
│   └── vlc_player.py
└── tests/
    ├── test_scheduler.py
    └── test_solar.py
```

We don't have to split the code into all these modules immediately. The important architectural boundary is that **schedule selection and VLC process management remain independent**.

## **9. Acceptance criteria**

We'll consider the first standalone version complete when it can:

- Start Charlie Brown or the configured default video based on the current schedule.
- Calculate the appropriate sunset transition for Midlothian.
- Switch to the scheduled video at exactly 10 PM, within the configured polling interval.
- Select the correct video after restarting the Python application at any time of day.
- Recover from an unexpected VLC process exit.
- Exit cleanly without leaving VLC running.
- Pass scheduling tests for midnight crossings, daylight saving time, and schedule overlaps.
- Run automatically as a systemd service after manual testing.

**Recommended implementation approach:** Build the configuration loader and pure scheduling engine first, test those using `--dry-run`, then integrate VLC process management and finally systemd startup. That gives us a reusable foundation for both `vlc-main` and `vlc-child`.

## Operations

### Server
* when clients register with the server on the tcp port, they are added to the client list
* whenever the server starts a new video, it sends "sync <video name> 0.0" to all clients. 
* then periodically (every self.config.schedule.sync_secs) the server sends "sync <video name> <ss.nn>" (sync, video-name timestamp) to all listening clients

### Client
* Clients gain the server information from self.config.server.tcp.host and .port from vlc-00.json.
* upon initialization clients attempt to connect to the server and listen for "sync" commands
* All the clients receive the same protocol over tcp/ip. specifically "sync <video-name> <secs.nn>" (sync, video-name timestamp). 
*  if the video-name is different from what is currently playing then 
    * client kills whatever video is currently playing 
    * starts the named video 
    * fast-forwards to the timestamp specified
* else if currently playing video is the same as the named video, then 
    * fast-forwards the currently playing video to the timestamp specified


