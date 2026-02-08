#!/usr/bin/bash


# gst-launch-1.0 udpsrc port=5000 caps="application/x-rtp, media=video, encoding-name=H264, payload=96" !   rtph264depay ! avdec_h264 ! videoconvert ! autovideosink sync=false


# Raw video (useless)
# gst-launch-1.0 udpsrc port=5000 \
#   caps="application/x-rtp, media=video, encoding-name=H264, payload=96" ! \
#   rtph264depay ! h264parse ! avdec_h264 ! \
#   videoconvert ! \
#   fakesink dump=true



gst-launch-1.0 udpsrc port=5000 \
  caps="application/x-rtp, media=video, encoding-name=H264, payload=96" ! \
  rtph264depay ! avdec_h264 ! \
  identity silent=false ! \
  videoconvert ! autovideosink
