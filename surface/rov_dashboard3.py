import socket, json, threading, subprocess, signal, logging, select, os
from inputs import get_gamepad
import tkinter as tk
from tkinter import ttk
import time
from rov_gui import setup_gui, draw_joystick, draw_claw, draw_thrusters, draw_current

VIDEO_ENABLED = True

PI5_IP = "192.168.2.204"
PI5_PORT = 9000

DEADZONE = 0.2
TRIGGER_DEADZONE = 0.05
CLAW_RATE = 0.30
controller_remap = False

MAX_CURRENT_PER_THRUSTER = 6.0

horizontal_speed = 0.3
vertical_speed = 0.4

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
axes = {"LX":0,"LY":0,"RX":0,"RY":0,"LT":0,"RT":0}
axes_raw = {"LX":0,"LY":0,"RX":0,"RY":0}
calibrate = False
recording = False
recording1 = False
recording2 = False
record_proc = None
record_proc1 = None
record_proc2 = None
video = None
video2 = None
rec_btn = None
claw_pos = 0.5
claw_last_update = time.time()
estimated_current = 0.0
thruster = [0.0] * 6
# Detection receiver
DETECTION_PORT = 9010
last_detections = []

def detection_listener(port=DETECTION_PORT):
    global last_detections
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('127.0.0.1', port))
    except Exception:
        try:
            sock.bind(('0.0.0.0', port))
        except Exception:
            return
    sock.settimeout(1.0)
    while True:
        try:
            data, _ = sock.recvfrom(65536)
            try:
                obj = json.loads(data.decode('utf-8'))
                last_detections = obj.get('detections', [])
            except Exception:
                continue
        except socket.timeout:
            continue
        except Exception:
            break
    sock.close()

def remap(value, code):
    if code not in ["ABS_X", "ABS_Y", "ABS_RX", "ABS_RY"]:
        return value
    return int(((value - 127) / 128) * 32767)

def estimate_current():
    global estimated_current, thruster
    speed = horizontal_speed
    surge = axes["LY"]
    sway = axes["LX"]
    yaw = axes["RX"]
    heave = axes["RY"]

    def clamp(v): return max(-1.0, min(1.0, v))

    thruster[0] = clamp((surge + yaw + sway) * speed)
    thruster[1] = clamp((surge - yaw + sway) * speed)
    thruster[2] = clamp((surge + yaw - sway) * speed)
    thruster[3] = clamp((surge - yaw - sway) * speed)
    thruster[4] = clamp(heave * vertical_speed)
    thruster[5] = clamp(heave * vertical_speed)

    estimated_current = sum(abs(val) for val in thruster) * MAX_CURRENT_PER_THRUSTER

def norm(v): return max(-1,min(1,v/32767))

def deadzone(v):
    if abs(v) <= DEADZONE:
        return 0
    return v

def process(e):
    global horizontal_speed, vertical_speed

    if e.ev_type=="Absolute":
        state = remap(e.state, e.code) if controller_remap else e.state

        if e.code=="ABS_X":
            normed = norm(state)
            axes_raw["LX"] = normed
            axes["LX"] = deadzone(normed)
        if e.code=="ABS_Y":
            normed = -norm(state)
            axes_raw["LY"] = normed
            axes["LY"] = deadzone(normed)
        if e.code=="ABS_RX":
            normed = norm(state)
            axes_raw["RX"] = normed
            axes["RX"] = deadzone(normed)
        if e.code=="ABS_RY":
            normed = -norm(state)
            axes_raw["RY"] = normed
            axes["RY"] = deadzone(normed)

        if e.code=="ABS_Z": axes["LT"]=e.state/255
        if e.code=="ABS_RZ": axes["RT"]=e.state/255

        if e.code == "ABS_HAT0Y" and e.state != 0:
            if e.state == -1:
                horizontal_speed = min(1.0, horizontal_speed + 0.1)
            elif e.state == 1:
                horizontal_speed = max(0.1, horizontal_speed - 0.1)

        if e.code == "ABS_HAT0X" and e.state != 0:
            if e.state == 1:
                vertical_speed = min(1.0, vertical_speed + 0.1)
            elif e.state == -1:
                vertical_speed = max(0.1, vertical_speed - 0.1)

    # Handle button/key events from the gamepad
    if e.ev_type == "Key":
        # Typical mapping: BTN_SOUTH=A, BTN_EAST=B, BTN_WEST=X, BTN_NORTH=Y
        # Only act on button press (state == 1)
        if e.state == 1:
            if e.code == "BTN_SOUTH":
                # A: toggle camera 1 recording
                toggle_record_cam1()
            elif e.code == "BTN_EAST":
                # B: camera 1 screenshot
                screenshot_cam1()
            elif e.code == "BTN_WEST":
                # X: toggle camera 2 recording
                toggle_record_cam2()
            elif e.code == "BTN_NORTH":
                # Y: camera 2 screenshot
                screenshot_cam2()

def compute():
    global claw_pos, claw_last_update
    now = time.time()
    dt = now - claw_last_update
    claw_last_update = now

    rt = axes["RT"]
    lt = axes["LT"]

    if rt < TRIGGER_DEADZONE: rt = 0
    if lt < TRIGGER_DEADZONE: lt = 0

    claw_pos += (rt - lt) * CLAW_RATE * dt
    claw_pos = max(0, min(1, claw_pos))

    estimate_current()

    return {
        "surge": axes["LY"] * horizontal_speed,
        "sway": axes["LX"] * horizontal_speed,
        "yaw": axes["RX"] * horizontal_speed,
        "heave": axes["RY"] * vertical_speed,
        "claw_pos": claw_pos,
        "calibrate": calibrate
    }

def fmt(c):
    return (
        f"SURGE {c['surge']:.3f} "
        f"SWAY {c['sway']:.3f} "
        f"YAW {c['yaw']:.3f} "
        f"HEAVE {c['heave']:.3f} "
        f"CLAW_POS {c['claw_pos']:.3f} "
        f"CALIBRATE {int(c['calibrate'])}\n"
    )

def sender():
    while True:
        for e in get_gamepad():
            process(e)
        comp = compute()
        print(comp)
        sock.sendto(fmt(comp).encode(), (PI5_IP, PI5_PORT))

threading.Thread(target=sender, daemon=True).start()

def toggle_cal():
    global calibrate
    calibrate = not calibrate

def toggle_record_cam1():
    global recording1, record_proc1, rec_btn
    if not recording1:
        cmd = [
            "gst-launch-1.0",
            "udpsrc", "port=5000",
            "!", "application/x-rtp, media=video, encoding-name=H264, payload=96",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "mp4mux",
            "!", "filesink", "location=rov_recording_cam1.mp4"
        ]
        record_proc1 = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        recording1 = True
        if rec_btn:
            rec_btn.config(text="Stop Recording (Cam1)")
    else:
        try: record_proc1.terminate()
        except: pass
        recording1 = False
        if rec_btn:
            rec_btn.config(text="Start Recording (Cam1)")

def toggle_record_cam2():
    global recording2, record_proc2
    if not recording2:
        cmd = [
            "gst-launch-1.0",
            "udpsrc", "port=5001",
            "!", "application/x-rtp, media=video, encoding-name=H264, payload=96",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "mp4mux",
            "!", "filesink", "location=rov_recording_cam2.mp4"
        ]
        record_proc2 = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        recording2 = True
    else:
        try: record_proc2.terminate()
        except: pass
        recording2 = False

def screenshot_cam1():
    # capture a single frame to a timestamped JPEG using ffmpeg
    fn = f"screenshot_cam1_{int(time.time())}.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-i", "udp://127.0.0.1:5000",
        "-frames:v", "1",
        fn
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        logging.info(f"Saved screenshot: {fn}")
    except Exception as e:
        logging.error(f"Screenshot failed: {e}")

def screenshot_cam2():
    fn = f"screenshot_cam2_{int(time.time())}.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-i", "udp://127.0.0.1:5001",
        "-frames:v", "1",
        fn
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        logging.info(f"Saved screenshot: {fn}")
    except Exception as e:
        logging.error(f"Screenshot failed: {e}")

def start_video_stream():
    cmd = [
        "gst-launch-1.0",
        "udpsrc", "port=5000",
        "caps=application/x-rtp, media=video, encoding-name=H264, payload=96",
        "!", "rtph264depay",
        "!", "avdec_h264",
        "!", "identity", "silent=false",
        "!", "videoconvert",
        "!", "autovideosink"
    ]
    logging.info(f"Starting video display pipeline: {cmd}")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def start_video_stream_cam2():
    cmd = [
        "gst-launch-1.0",
        "udpsrc", "port=5001",
        "caps=application/x-rtp, media=video, encoding-name=H264, payload=96",
        "!", "rtph264depay",
        "!", "avdec_h264",
        "!", "identity", "silent=false",
        "!", "videoconvert",
        "!", "autovideosink"
    ]
    logging.info(f"Starting second video display pipeline: {cmd}")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def read_video_stream_output(video_proc):
    if video_proc is None or video_proc.poll() is not None:
        return
    try:
        readable, _, _ = select.select([video_proc.stdout, video_proc.stderr], [], [], 0)
        for stream in readable:
            try:
                line = stream.readline()
                if line:
                    if stream == video_proc.stdout:
                        logging.info(line.rstrip())
                    else:
                        logging.error(line.rstrip())
            except Exception as e:
                logging.error(f"Error reading video stream: {e}")
    except Exception:
        pass

def main():
    global video, video2, rec_btn, recording, record_proc

    # setup GUI: use camera1 record as the main record button
    def _dummy_toggle_level():
        return
    root, left_canvas, right_canvas, claw_canvas, thruster_canvas, current_canvas, attitude_canvas, status_label, speed_label, rec_btn, level_btn = setup_gui(toggle_cal, toggle_record_cam1, _dummy_toggle_level)

    # start detection receiver thread
    threading.Thread(target=detection_listener, daemon=True).start()

    def update_displays():
        left_canvas.delete("all")
        draw_joystick(left_canvas, axes_raw["LX"], axes_raw["LY"], DEADZONE)

        right_canvas.delete("all")
        draw_joystick(right_canvas, axes_raw["RX"], axes_raw["RY"], DEADZONE)

        claw_canvas.delete("all")
        draw_claw(claw_canvas, claw_pos)

        thruster_canvas.delete("all")
        t2 = [thruster[1], thruster[0], thruster[3], thruster[2], thruster[4], thruster[5]]
        draw_thrusters(thruster_canvas, t2)

        current_canvas.delete("all")
        draw_current(current_canvas, estimated_current)

        cal_status = "CAL" if calibrate else "---"
        rec1_status = "REC1" if recording1 else "---"
        rec2_status = "REC2" if recording2 else "---"

        det_count = len(last_detections) if last_detections is not None else 0
        status_label.config(
            text=(f"Calibrate: {cal_status}  |  Cam1: {rec1_status}  Cam2: {rec2_status}  |  "
                f"LT: {axes['LT']:.2f}  RX: {axes['RX']:.2f}  |  Speed: "
                f"| Detections: {det_count}"),
            fg="black"
        )

        speed_label.config(
            text=f"H {int(horizontal_speed*100)}%  |  V {int(vertical_speed*100)}%",
            fg="black"
        )

        root.after(50, update_displays)

    root.after(50, update_displays)

    if VIDEO_ENABLED:
        try:
            video = start_video_stream()
            video2 = start_video_stream_cam2()
        except Exception as e:
            logging.error(f"Failed to start video streams: {e}")

        def poll_video():
            read_video_stream_output(video)
            root.after(200, poll_video)

        def poll_video2():
            read_video_stream_output(video2)
            root.after(200, poll_video2)

        root.after(200, poll_video)
        root.after(200, poll_video2)

    def _sigint_handler(signum, frame=None):
        print('caught ^C')
        on_close()

    def on_close():
        global recording, record_proc, video, video2, record_proc1, record_proc2, recording1, recording2
        try:
            if record_proc is not None and recording:
                record_proc.terminate()
        except: pass
        try:
            if record_proc1 is not None and recording1:
                record_proc1.terminate()
        except: pass
        try:
            if record_proc2 is not None and recording2:
                record_proc2.terminate()
        except: pass
        try:
            if video is not None and video.poll() is None:
                video.terminate()
        except: pass
        try:
            if video2 is not None and video2.poll() is None:
                video2.terminate()
        except: pass
        try:
            root.destroy()
        except: pass

    def _check():
        root.after(500, _check)

    signal.signal(signal.SIGINT, _sigint_handler)
    root.after(500, _check)
    root.bind_all('<Control-c>', lambda e: _sigint_handler(None, None))
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()

if __name__ == "__main__":
    print("Starting ROV dashboard...")
    main()
