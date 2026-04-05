import socket
import threading
import subprocess
import signal
import logging
import time
import os

from inputs import get_gamepad
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

# ============================================================
# CONFIG
# ============================================================

PI5_IP = "192.168.2.204"
PI5_PORT = 9000

DEADZONE = 0.2
TRIGGER_DEADZONE = 0.05
CLAW_RATE = 0.30

MAX_CURRENT_PER_THRUSTER = 6.0

# 10% increment speeds
horizontal_speed = 0.3
vertical_speed = 0.4

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

axes = {"LX":0, "LY":0, "RX":0, "RY":0, "LT":0, "RT":0}
axes_raw = {"LX":0, "LY":0, "RX":0, "RY":0}

calibrate = False
recording = False
record_proc = None

claw_pos = 0.5
claw_last_update = time.time()

estimated_current = 0.0
thruster = [0.0] * 6

state_lock = threading.Lock()

# ============================================================
# NORMALIZATION / DEADZONE
# ============================================================

def remap(value, code):
    if code not in ["ABS_X", "ABS_Y", "ABS_RX", "ABS_RY"]:
        return value
    return int(((value - 127) / 128) * 32767)

def norm(v):
    return max(-1, min(1, v / 32767))

def deadzone(v):
    if abs(v) <= DEADZONE:
        return 0
    return v

# ============================================================
# THRUSTER MIXING + CURRENT ESTIMATION
# ============================================================

def estimate_current():
    global estimated_current, thruster
    global horizontal_speed, vertical_speed

    with state_lock:
        surge = axes["LY"]
        sway  = axes["LX"]
        yaw   = axes["RX"]
        heave = axes["RY"]

        h = horizontal_speed
        v = vertical_speed

    def clamp(x):
        return max(-1.0, min(1.0, x))

    t0 = clamp((surge + yaw + sway) * h)
    t1 = clamp((surge - yaw + sway) * h)
    t2 = clamp((surge + yaw - sway) * h)
    t3 = clamp((surge - yaw - sway) * h)
    t4 = clamp(heave * v)
    t5 = clamp(heave * v)

    with state_lock:
        thruster[0] = t0
        thruster[1] = t1
        thruster[2] = t2
        thruster[3] = t3
        thruster[4] = t4
        thruster[5] = t5

        estimated_current = (
            abs(t0) + abs(t1) + abs(t2) +
            abs(t3) + abs(t4) + abs(t5)
        ) * MAX_CURRENT_PER_THRUSTER

# ============================================================
# PROCESS CONTROLLER EVENTS
# ============================================================

def process_event(e):
    global horizontal_speed, vertical_speed

    if e.ev_type != "Absolute":
        return

    state = remap(e.state, e.code)

    with state_lock:

        if e.code == "ABS_X":
            n = norm(state)
            axes_raw["LX"] = n
            axes["LX"] = deadzone(n)

        if e.code == "ABS_Y":
            n = -norm(state)
            axes_raw["LY"] = n
            axes["LY"] = deadzone(n)

        if e.code == "ABS_RX":
            n = norm(state)
            axes_raw["RX"] = n
            axes["RX"] = deadzone(n)

        if e.code == "ABS_RY":
            n = -norm(state)
            axes_raw["RY"] = n
            axes["RY"] = deadzone(n)

        if e.code == "ABS_Z":
            axes["LT"] = e.state / 255

        if e.code == "ABS_RZ":
            axes["RT"] = e.state / 255

        # 10% increments
        if e.code == "ABS_HAT0Y" and e.state != 0:
            if e.state == -1:
                horizontal_speed = min(1.0, horizontal_speed + 0.1)
            if e.state == 1:
                horizontal_speed = max(0.1, horizontal_speed - 0.1)

        if e.code == "ABS_HAT0X" and e.state != 0:
            if e.state == 1:
                vertical_speed = min(1.0, vertical_speed + 0.1)
            if e.state == -1:
                vertical_speed = max(0.1, vertical_speed - 0.1)

# ============================================================
# COMPUTE OUTGOING PACKET
# ============================================================

def compute():
    global claw_pos, claw_last_update

    now = time.time()
    dt = now - claw_last_update
    claw_last_update = now

    with state_lock:
        rt = axes["RT"]
        lt = axes["LT"]

    if rt < TRIGGER_DEADZONE:
        rt = 0
    if lt < TRIGGER_DEADZONE:
        lt = 0

    with state_lock:
        claw_pos += (rt - lt) * CLAW_RATE * dt
        claw_pos = max(0, min(1, claw_pos))

    estimate_current()

    with state_lock:
        return {
            "surge": axes["LY"] * horizontal_speed,
            "sway":  axes["LX"] * horizontal_speed,
            "yaw":   axes["RX"] * horizontal_speed,
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

# ============================================================
# SENDER THREAD
# ============================================================

def sender_thread():
    print("Controller thread running...")
    while True:
        for e in get_gamepad():
            process_event(e)
        comp = compute()
        sock.sendto(fmt(comp).encode(), (PI5_IP, PI5_PORT))

# ============================================================
# RECORDING / CALIBRATION
# ============================================================

def toggle_cal():
    global calibrate
    with state_lock:
        calibrate = not calibrate

def toggle_record():
    global recording, record_proc

    with state_lock:
        rec = recording

    if not rec:
        cmd = [
            "gst-launch-1.0",
            "udpsrc", "port=5000",
            "!", "application/x-rtp, media=video, encoding-name=H264, payload=96",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "mp4mux",
            "!", "filesink", "location=rov_recording.mp4"
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        with state_lock:
            recording = True
            record_proc = proc

    else:
        with state_lock:
            proc = record_proc
        try:
            if proc:
                proc.terminate()
        except:
            pass
        with state_lock:
            recording = False
            record_proc = None

# ============================================================
# FLASK WEB SERVER
# ============================================================

app = Flask(__name__, static_folder="static")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

@app.route("/state")
def api_state():
    with state_lock:
        data = {
            "axes_raw": axes_raw,
            "axes": axes,
            "thruster": thruster,
            "estimated_current": estimated_current,
            "horizontal_speed": horizontal_speed,
            "vertical_speed": vertical_speed,
            "claw_pos": claw_pos,
            "calibrate": calibrate,
            "recording": recording
        }
    return jsonify(data)

@app.route("/toggle_cal", methods=["POST"])
def api_toggle_cal():
    toggle_cal()
    return jsonify({"ok": True})

@app.route("/toggle_record", methods=["POST"])
def api_toggle_record():
    toggle_record()
    return jsonify({"ok": True})

# ============================================================
# MAIN
# ============================================================

def run_flask():
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        use_reloader=False
    )

def main():
    print("Starting ROV Web Dashboard Backend...")

    t = threading.Thread(target=sender_thread, daemon=True)
    t.start()

    def handle_sigint(signum, frame):
        print("Shutting down...")
        with state_lock:
            proc = record_proc
        try:
            if proc:
                proc.terminate()
        except:
            pass
        os._exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    run_flask()

if __name__ == "__main__":
    main()
