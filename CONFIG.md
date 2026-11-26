## VLC Configuration

**Configuration file:** `/home/greg/.config/vlc/vlcrc`

**VLC version:** 3.0.23 Vetinari

### Explicit settings

| Setting | Value | Description |
|---|---|---|
| `alsa-gain` | `0.592373` | ALSA gain configuration |
| `avcodec-hw` | `v4l2` | V4L2 hardware-accelerated decoding |

### Verified operation

- CLI executable: `/usr/bin/cvlc`
- Video output module: `drm_vout`
- Hardware decoder: `h264_v4l2m2m`
- Decoder device: `/dev/video10`
- Audio output: `hdmi:CARD=vc4hdmi,DEV=0`
- Portrait video: Working
- HDMI stereo audio: Working

### Known-good playback command

```bash
cvlc -vv \
  --vout=drm_vout \
  --drm-vout-no-modeset \
  --aout=alsa \
  --alsa-audio-device=hdmi:CARD=vc4hdmi,DEV=0 \
  --fullscreen \
  /home/greg/videos/charlie-brown-thanksgiving-portrait-rotated.mp4
```

### Notes

Preserve the original `vlcrc` file during configuration changes.

The VLC configuration contains numerous module sections, but only two active parameter assignments were identified in the initial inspection.

Hardware-assisted H.264 decoding and functional HDMI playback have been verified. Sustained playback performance remains to be tested.

 ### ModemManager Cleanup — 2026-11-22

- Disabled and stopped ModemManager.service.
- Removed and purged modemmanager 1.20.4-1.
- Removed seven orphaned MBIM/QMI/QRTR libraries.
- Recovered approximately 11.1 MB of disk space.
- Verified NetworkManager, SSH, and systemd-timesyncd remain active.
- Package removal emitted "Unknown option: runtime";
  subsequent purge and autoremove completed without errors.

### LIRC Cleanup — 2026-11-22

- Disabled lircd.service and lircd.socket.
- Verified both units inactive and disabled.
- Removed and purged lirc 0.10.1-7.2.
- Removed 10 orphaned dependencies using apt autoremove.
- Recovered approximately 10.2 MB of disk space.
- No errors reported during package removal.
- LIRC is unnecessary for the headless HDMI/VLC video player.

### Triggerhappy Cleanup — 2026-11-22

- Verified no active hotkey definitions were found in the checked paths.
- Disabled triggerhappy.service and triggerhappy.socket.
- Verified both units inactive and disabled.
- Removed and purged triggerhappy 0.5.0-1.1.
- Recovered approximately 94.2 KB.
- Confirmed apt autoremove reports no orphaned packages.
- Triggerhappy is unnecessary for the current headless VLC configuration.

### PipeWire Cleanup — 2026-11-22

- Removed pipewire, pipewire-pulse, pipewire-alsa,
  pipewire-audio, and wireplumber.
- Removed 12 orphaned dependencies with apt autoremove.
- Purged residual package configuration.
- Removed six obsolete user-level systemd masks.
- Verified no PipeWire, WirePlumber, or filter-chain
  unit files remain listed.
- Recovered approximately 13.4 MB of disk space.
- ALSA default output now selects the HDMI sound card.
- Verified left and right HDMI audio channels.
- Verified VLC portrait video and HDMI audio
  with PipeWire disabled.
- Removed obsolete ~/.asoundrc Bluetooth speaker configuration.
- VLC DRM "Failed to get xlease" warnings were observed,
  but playback appeared and sounded correct

### Bluetooth Auto-Connect Cleanup — 2026-11-22

- Identified custom service:
  /etc/systemd/system/bt-autoconnect.service
- Service attempted to connect to Bluetooth device
  68:CA:C4:F2:7A:0D during boot.
- Confirmed the service failed during boot on 2026-11-21.
- Disabled and stopped the service.
- Deleted its custom systemd unit file.
- Reloaded systemd and cleared the stale failure state.
- Verified systemd reports the unit could not be found.
- Bluetooth speaker connectivity will be handled by
  the Toshiba TV, not the Raspberry Pi.
.
### UDisks2 Cleanup — 2026-11-22

- Disabled udisks2.service.
- Verified service inactive and disabled.
- Removed and purged udisks2 2.9.4-4+deb12u2.
- Removed 14 orphaned dependencies with apt autoremove.
- Recovered approximately 5.35 MB of disk space.
- Marked gdisk and exfatprogs as manually installed
  to preserve SD card and filesystem maintenance tools.
- No package removal errors reported.
- Normal root filesystem mounting does not require UDisks2.

### Hostname — 2026-11-22

- Previous hostname: rpi-offline-02
- Current hostname: vlc-00
- Changed using hostnamectl.
- Updated /etc/hosts to map 127.0.1.1 to vlc-00.
- Verified hostnamectl, hostname, and getent hosts.
- Role: Main Raspberry Pi (parent/controller).
- Default video:
  /home/greg/videos/charlie-brown-thanksgiving-portrait-rotated.mp4

Understood. We'll leave the old configuration files alone and document **only the configurations relevant to services we're keeping and using** on `vlc-00`.

### **Configuration inventory — vlc-00**

| Service / Function              | Configuration files                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| Raspberry Pi boot               | `/boot/firmware/config.txt`                                                          |
| Kernel boot parameters          | `/boot/firmware/cmdline.txt`                                                         |
| Hostname                        | `/etc/hostname`, `/etc/hosts`                                                        |
| NetworkManager (Wi-Fi)          | `/etc/NetworkManager/NetworkManager.conf`, `/etc/NetworkManager/system-connections/` |
| Wi-Fi authentication            | `/etc/wpa_supplicant/`                                                               |
| SSH                             | `/etc/ssh/sshd_config`, `/etc/ssh/sshd_config.d/`                                    |
| Time synchronization            | `/etc/systemd/timesyncd.conf`, `/etc/systemd/timesyncd.conf.d/`                      |
| Local network discovery (Avahi) | `/etc/avahi/avahi-daemon.conf`                                                       |
| Scheduled tasks (cron)          | `/etc/crontab`, `/etc/cron.d/`, `/var/spool/cron/crontabs/`                          |
| VLC                             | `/home/greg/.config/vlc/vlcrc`                                                       |
| HDMI audio (ALSA)               | `/etc/asound.conf` *(if present)*                                                    |
| Systemd services                | `/etc/systemd/system/`                                                               |

These are the **configuration paths to track**, not a claim that every optional file or directory exists on this Pi. The earlier inventory directly confirmed the boot files and VLC configuration; the other locations are standard paths we should verify.

### VLC Playback Script — 2026-11-22

- Script: /home/greg/vlc-main/play.sh
- Accepts one video filename or path as a CLI argument.
- Uses VLC DRM/KMS video output and ALSA HDMI audio.
- Supports filenames relative to /home/greg/videos/.
- Runs VLC in the foreground.
- Executable and playback tested successfully.
- No automatic startup configured yet.

### TCP Sync Protocol — 2026-11-25

Wire protocol: newline-terminated text lines over TCP.

- **Client → server:** `identify <client-id>` on connect. Clients are added
  to the server's client list.
- **Server → clients:** `sync <video-name> <secs.nn>` (video file base name,
  playback position in seconds, two decimals).
  - Sent as `sync <video-name> 0.0` whenever the server starts a new video.
  - Re-sent to all connected clients every `schedule.sync_secs` while a
    video is playing.

Configuration (`vlc-00.json` / `vlc-macos.json`):

| Key | Description |
|---|---|
| `server.tcp.host` | Host clients connect to (also used by `--client` mode) |
| `server.tcp.bind_host` | Optional local address the server binds to (default `0.0.0.0`) |
| `server.tcp.port` | TCP port clients connect to |
| `server.tcp.max_clients` | Maximum concurrent clients |
| `schedule.sync_secs` | Period, in seconds, between periodic sync broadcasts |

There is no separate `client` configuration section: `--client` mode reads
the server address from `server.tcp.host` and `server.tcp.port`.

Client behavior on receiving `sync <video-name> <secs.nn>`:

- If `<video-name>` differs from the video currently playing, the client
  stops the current video and starts the named video fast-forwarded to
  `<secs.nn>`.
- If the named video is the one currently playing, the client seeks the
  current video to `<secs.nn>` (implemented as a restart with
  `--start-time`, since VLC runs as an uncontrolled subprocess).
