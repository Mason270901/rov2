#!/usr/bin/env python3
import socket, json, serial, subprocess, time, sys, signal
import logging
import select

LISTEN_IP   = "0.0.0.0"
LISTEN_PORT = 9000

SERIAL_PORT = "/dev/ttyACM0"
BAUD        = 115200

PI4_IP      = "192.168.2.13"

VIDEO_DEVICE_1 = "/dev/video0"
VIDEO_DEVICE_2 = "/dev/video2"


VIDEO_PORT_1 = 5000
VIDEO_PORT_2 = 5001

# runtime globals for graceful shutdown from SIGINT
running = True
video1 = None
video2 = None
ser = None
sock = None

###############################################################################
# Options
print_arduino = True
print_udp = True
###############################################################################

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _sigint_handler(signum, frame):
    global running, video1, video2, ser, sock
    print('caught ^C, shutting down')
    running = False
    try:
        if video1 is not None and video1.poll() is None:
            video1.terminate()
    except: pass
    try:
        if video2 is not None and video2.poll() is None:
            video2.terminate()
    except: pass
    try:
        if ser is not None and getattr(ser, 'is_open', False):
            ser.close()
    except: pass
    try:
        if sock is not None:
            sock.close()
    except: pass

def start_video_stream(device, port):
    cmd = [
        "/usr/bin/gst-launch-1.0",
        "v4l2src", f"device={device}",
        "!", "video/x-raw,width=640,height=480,framerate=30/1",
        "!", "videoconvert",
        "!", "x264enc", "tune=zerolatency", "bitrate=1000", "speed-preset=superfast",
        "!", "rtph264pay", "config-interval=1", "pt=96",
        "!", "udpsink", f"host={PI4_IP}", f"port={port}", "sync=false"
    ]
    logging.info(f"Starting camera stream: {cmd}")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def read_video_stream_output(video):
    """Read available output from video process streams without blocking."""
    if video is None or video.poll() is not None:
        return

    # Check if there's data available to read from stdout/stderr
    readable, _, _ = select.select([video.stdout, video.stderr], [], [], 0)

    for stream in readable:
        try:
            line = stream.readline()
            if line:
                if stream == video.stdout:
                    logging.info(line.rstrip())
                else:
                    logging.error(line.rstrip())
        except Exception as e:
            logging.error(f"Error reading video stream: {e}")

def main():
    global sock, ser, video1, video2, running

    print("binding socket...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.setblocking(False)  # make socket non-blocking

    print("opening serial with 2 second delay...")
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
    # prevent Arduino auto-reset on open (DTR toggle). Some launchers/debuggers
    # hold DTR differently which is why CLI vs debugger behaved differently.
    try: ser.dtr = False
    except: pass
    # give Arduino time to finish any auto-reset and start sending
    time.sleep(2)
    try: ser.reset_input_buffer()
    except: pass

    print("Arduino should be awake")

    print("starting video streams...")
    video1 = start_video_stream(VIDEO_DEVICE_1, VIDEO_PORT_1)
    video2 = start_video_stream(VIDEO_DEVICE_2, VIDEO_PORT_2)

    # ensure SIGINT triggers graceful shutdown
    signal.signal(signal.SIGINT, _sigint_handler)

    print("ROV receiver is up and running.")

    while running:
        try:
            data,_ = sock.recvfrom(1024)
            if print_udp:
                print("Received:", data)
            ser.write(data)
        except (BlockingIOError, socket.error):
            pass

        # read Arduino serial output if available
        if print_arduino and ser is not None and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    arduino_data = ser.read(ser.in_waiting)
                    if arduino_data:
                        print(arduino_data.decode('utf-8', errors='ignore'), end='')
            except Exception as e:
                print(f"Error reading Arduino serial: {e}")

        # read video stream output without blocking
        read_video_stream_output(video1)
        read_video_stream_output(video2)

    # final cleanup
    try:
        if video1 is not None and video1.poll() is None:
            video1.terminate()
    except: pass
    try:
        if video2 is not None and video2.poll() is None:
            video2.terminate()
    except: pass
    try:
        if ser is not None and ser.is_open:
            ser.close()
    except: pass
    try:
        if sock is not None:
            sock.close()
    except: pass

if __name__ == "__main__":
    print("Starting ROV receiver...")
    main()
