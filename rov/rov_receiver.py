#!/usr/bin/env python3
import socket, json, serial, subprocess, time, sys, signal

LISTEN_IP   = "0.0.0.0"
LISTEN_PORT = 9000

SERIAL_PORT = "/dev/ttyACM0"
BAUD        = 115200

PI4_IP      = "10.0.0.13"
VIDEO_DEVICE = "/dev/video1"
VIDEO_PORT   = 5000

# runtime globals for graceful shutdown from SIGINT
running = True
video = None
ser = None
sock = None

def _sigint_handler(signum, frame):
    global running, video, ser, sock
    print('caught ^C, shutting down')
    running = False
    try:
        if video is not None and video.poll() is None:
            video.terminate()
    except Exception:
        pass
    try:
        if ser is not None and getattr(ser, 'is_open', False):
            ser.close()
    except Exception:
        pass
    try:
        if sock is not None:
            sock.close()
    except Exception:
        pass

def start_video_stream():
    return subprocess.Popen([
        "/usr/bin/gst-launch-1.0",
        "v4l2src", f"device={VIDEO_DEVICE}",
        "!", "video/x-raw,width=1280,height=720,framerate=30/1",
        "!", "videoconvert",
        "!", "x264enc", "tune=zerolatency", "bitrate=2000", "speed-preset=superfast",
        "!", "rtph264pay", "config-interval=1", "pt=96",
        "!", "udpsink", f"host={PI4_IP}", f"port={VIDEO_PORT}", "sync=false"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)



def main():
    global sock, ser, video, running
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))

    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)

    video = start_video_stream()
    last_check = time.time()

    # ensure SIGINT triggers graceful shutdown
    signal.signal(signal.SIGINT, _sigint_handler)

    while running:
        try:

            data,_ = sock.recvfrom(1024)
            print("Received:", data)
            ser.write(data)
        except:
            pass

        if time.time() - last_check > 5:
            if video.poll() is not None:
                video = start_video_stream()
            last_check = time.time()

    # final cleanup
    try:
        if video is not None and video.poll() is None:
            video.terminate()
    except Exception:
        pass
    try:
        if ser is not None and getattr(ser, 'is_open', False):
            ser.close()
    except Exception:
        pass
    try:
        if sock is not None:
            sock.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()
