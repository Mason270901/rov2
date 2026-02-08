#!/bin/bash

# Start video streaming to ROV receiver
# Streams video from /dev/video0 to 10.0.0.13:5000 via RTP/H.264

# Raw at 640
# This has less artifacts, but lower res
# gst-launch-1.0 v4l2src device=/dev/video0 ! \
#     video/x-raw,width=640,height=480,framerate=30/1 ! \
#     videoconvert ! \
#     x264enc tune=zerolatency bitrate=1000 speed-preset=superfast ! \
#     rtph264pay config-interval=1 pt=96 ! \
#     udpsink host=10.0.0.13 port=5000 sync=false


# high quality at 1080p, but compressed with JPEG artifacts
gst-launch-1.0 v4l2src device=/dev/video0 ! \
    image/jpeg,width=1920,height=1080,framerate=30/1 ! \
    jpegdec ! \
    videoconvert ! \
    x264enc tune=zerolatency bitrate=1000 speed-preset=superfast ! \
    rtph264pay config-interval=1 pt=96 ! \
    udpsink host=192.168.2.13 port=5000 sync=false




# list formats
# v4l2-ctl --list-formats-ext -d /dev/video0 2>/dev/null | head -50