# Raspberry Pi Portrait Video Player — TODO

Project: Raspberry Pi Zero 2 W portrait video playback, eventually deployed to a Toshiba 43-inch Smart TV, with up to four synchronized Raspberry Pis.

## Completed / verified

- [x] Identify OS, kernel, and architecture (Raspbian 12 Bookworm, 32-bit ARM; kernel 6.12.62+rpt-rpi-v7)
- [x] Inspect HDMI display modes on current display (1920x1080 at 60 Hz)
- [x] Inspect DRM/KMS configuration and boot parameters (`vc4-kms-v3d`; `video=HDMI-A-1:1080x1920,rotate=90`)
- [x] Verify portrait presentation on current display
- [x] Verify VLC CLI playback through DRM/KMS with prepared video
- [x] Verify H.264 hardware-assisted decoding (`h264_v4l2m2m`, `/dev/video10`)
- [x] Verify HDMI stereo audio on current display through ALSA and VLC
- [x] Confirm `greg` has DRM/render/audio permissions

## Pending — configuration and documentation

- [x] Change hostname (currently `rpi-offline-02`)
- [x] Collect configuration files for running services (backed up to ~/vlc-main/config_backup)
- [x] Remove old Raspberry Pi Bluetooth configuration (TV will handle Bluetooth speaker independently)
- [x] Keep `CONFIG.md` updated as settings are verified or changed
- [x] Test playback performance and stability (VLC verified; CPU, memory, temperature, and throttling checked; extended playback and dropped-frame testing deferred)

## Pending — playback scheduling

- [ ] Create time-ordered playlist for different videos at different times of day
  - [ ] Support dusk/sunset-based transitions (Charlie Brown video at dusk)
  - [ ] Stop Charlie Brown video at 10:00 PM and switch to another video
  - [ ] Determine correct scheduled video based on current time, including after reboot
- [ ] Automatically play the scheduled playlist when the Raspberry Pi starts

## Pending — multi-Pi synchronization

- [ ] Run up to 4 Raspberry Pis simultaneously (no configuration changes required for this item yet)
- [ ] Set up one **parent** Raspberry Pi with a configuration file identifying the other three Pis
- [ ] Have three **child** Raspberry Pis receive synchronization messages from the parent
- [ ] Have all 4 Pis play different but related videos, kept synchronized by the parent

## Pending — final hardware and delivery

- [ ] Test portrait video and HDMI audio on the final Toshiba 43-inch Smart TV
- [ ] Create final bootable microSD `.img` image (not ISO)

## Notes

- No automatic-playback service has been created or enabled as part of this project so far; scheduling design is deferred.
- The current known-good video is `~/videos/charlie-brown-thanksgiving-portrait-rotated.mp4`.
- Bluetooth speaker configuration on the Toshiba TV itself is outside project scope.
