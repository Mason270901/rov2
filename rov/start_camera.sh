#!/bin/bash

# Start video streaming to ROV receiver
# Streams video from /dev/video0 to 10.0.0.13:5000 via RTP/H.264

gst-launch-1.0 v4l2src device=/dev/video0 ! \
    video/x-raw,width=640,height=480,framerate=30/1 ! \
    videoconvert ! \
    x264enc tune=zerolatency bitrate=1000 speed-preset=superfast ! \
    rtph264pay config-interval=1 pt=96 ! \
    udpsink host=10.0.0.13 port=5000 sync=false
