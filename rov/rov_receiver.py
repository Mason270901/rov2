#!/usr/bin/env python3
import socket, json, serial, subprocess, time, sys, signal

LISTEN_IP   = "0.0.0.0"
LISTEN_PORT = 9000

SERIAL_PORT = "/dev/ttyACM0"
BAUD        = 115200

PI4_IP      = "192.168.2.13"
VIDEO_DEVICE = "/dev/video1"
VIDEO_PORT   = 5000

# runtime globals for graceful shutdown from SIGINT
running = True
video = None
ser = None
sock = None

###############################################################################
# Options
print_arduino = True  # set to True to print all Arduino serial output
print_udp = True
###############################################################################


def _sigint_handler(signum, frame):
    global running, video, ser, sock, print_arduino
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
    global sock, ser, video, running, print_arduino
    print("binding socket...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.setblocking(False)  # make socket non-blocking

    print("opening serial with 2 second delay...")
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
    print("serial open:", getattr(ser, 'is_open', False))
    # prevent Arduino auto-reset on open (DTR toggle). Some launchers/debuggers
    # hold DTR differently which is why CLI vs debugger behaved differently.
    try:
        ser.dtr = False
    except Exception:
        pass
    # give Arduino time to finish any auto-reset and start sending
    time.sleep(2)
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    
    print("Arduino should be awake")

    print("starting video stream...")
    video = start_video_stream()


    # ensure SIGINT triggers graceful shutdown
    print("setting up signal handler...")
    signal.signal(signal.SIGINT, _sigint_handler)

    print("ROV receiver is up and running.")

    last_check = time.time()
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
    print("Starting ROV receiver...")
    main()
