#!/usr/bin/env python3
"""Crab detection service that reads the H264 UDP stream and sends detection
JSON over UDP to the dashboard.

Usage: python3 detect_crab.py --port 5000 --out-port 9010 --model best.pt
"""
import argparse
import json
import socket
import time
import cv2
from ultralytics import YOLO


def make_pipeline(port):
    return (
        f'udpsrc port={port} caps="application/x-rtp,media=video,encoding-name=H264,payload=96" '
        "! rtph264depay ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! appsink"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=5000, help='UDP port to read H264 stream from')
    p.add_argument('--out-port', type=int, default=9010, help='UDP port to send detection JSON to')
    p.add_argument('--model', type=str, default='best.pt', help='YOLO model path')
    p.add_argument('--conf', type=float, default=0.25, help='Confidence threshold')
    args = p.parse_args()

    pipeline = make_pipeline(args.port)
    print('Opening GStreamer pipeline:', pipeline)
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print('Failed to open video capture. Ensure GStreamer is installed and stream is active.')
        return

    print('Loading model:', args.model)
    model = YOLO(args.model)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dst = ('127.0.0.1', args.out_port)

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Run inference (ultralytics returns Results)
            try:
                results = model(frame, conf=args.conf, verbose=False)
            except Exception as e:
                print('Model inference error:', e)
                time.sleep(0.1)
                continue

            res0 = results[0]
            dets = []
            if hasattr(res0, 'boxes') and res0.boxes is not None:
                for box in res0.boxes:
                    # box.xyxy, box.conf, box.cls
                    xyxy = box.xyxy.cpu().numpy().tolist() if hasattr(box, 'xyxy') else []
                    conf = float(box.conf.cpu().numpy()) if hasattr(box, 'conf') else float(box.conf)
                    cls = int(box.cls.cpu().numpy()) if hasattr(box, 'cls') else int(box.cls)
                    dets.append({'bbox': xyxy, 'conf': conf, 'class': cls})

            payload = json.dumps({'ts': time.time(), 'detections': dets})
            try:
                sock.sendto(payload.encode('utf-8'), dst)
            except Exception as e:
                print('Failed to send detection:', e)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        sock.close()


if __name__ == '__main__':
    main()
