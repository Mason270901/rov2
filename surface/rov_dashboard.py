import socket, json, threading, subprocess, signal, logging, select, os
from inputs import get_gamepad
import tkinter as tk
from tkinter import ttk
import time
from rov_gui import setup_gui, draw_joystick, draw_claw

# Configurable Variables for this Script
###############################################################################
VIDEO_ENABLED = True  # Global flag to enable/disable video

PI5_IP = "192.168.2.204"
PI5_PORT = 9000

DEADZONE = 0.2    # Deadzone for the sticks
TRIGGER_DEADZONE = 0.05  # ignore triggers below this to prevent jitter
CLAW_RATE = 0.30  # claw open/close rate in units per second
controller_remap = False  # Set to True to remap Logitech controller values to Xbox ranges. Keep False for production


# State Variables updated as we run
###############################################################################
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
axes = {"LX":0,"LY":0,"RX":0,"RY":0,"LT":0,"RT":0} # This is the object that is updated, compute() operates on it
axes_raw = {"LX":0,"LY":0,"RX":0,"RY":0}  # Raw normalized values before deadzone, for GUI display
calibrate = False
recording = False
record_proc = None
video = None
rec_btn = None
claw_pos = 0.5
claw_last_update = time.time()



# Max raw controller values from the Xbox controller:
#   Joystick axes (LX, LY, RX, RY): ±32767 (16-bit signed integer)
#   Trigger axes (LT, RT): 0-255 (8-bit unsigned integer)

# Remap Logitech controller values (0-255, centered at 127) to Xbox ranges (±32767)
def remap(value, code):
    if code not in ["ABS_X", "ABS_Y", "ABS_RX", "ABS_RY"]:
        return value
    # Convert from 0-255 range (centered at 127) to -32767 to 32767 range (centered at 0)
    return int(((value - 127) / 128) * 32767)


# 16 bit normalize
def norm(v): return max(-1,min(1,v/32767))

# call this after norm
def deadzone(v):
    if(abs(v) <= DEADZONE):
        return 0
    else:
        return v

# handles each xbox input
def process(e):
    if e.ev_type=="Absolute":
        print(e.code, e.state)

        # Apply controller remapping if enabled
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

# takes the axes object, and converts it to a format to send over the wire
def compute():
    global claw_pos, claw_last_update
    now = time.time()
    dt = now - claw_last_update
    claw_last_update = now
    
    rt = axes["RT"]
    lt = axes["LT"]
    
    # Apply trigger deadzone to prevent jitter when triggers are idle
    if rt < TRIGGER_DEADZONE:
        rt = 0
    if lt < TRIGGER_DEADZONE:
        lt = 0
    
    # Move claw proportionally based on trigger deflection
    # RT increases claw_pos, LT decreases it, scaled by actual time delta
    claw_pos += (rt - lt) * CLAW_RATE * dt
    
    # Clamp between 0 and 1
    claw_pos = max(0, min(1, claw_pos))
    
    return {
        "surge": axes["LY"],
        "sway": axes["LX"],
        "yaw": axes["RX"],
        "heave": axes["RY"],
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
    last = time.time()
    while True:
        for e in get_gamepad():
            process(e)
        # now = time.time()
        # print(str(axes) + str(now-last))
        # last = now
        comp = compute()
        print(comp)
        sock.sendto(fmt(comp).encode(), (PI5_IP, PI5_PORT))

threading.Thread(target=sender, daemon=True).start()

def toggle_cal():
    global calibrate
    calibrate = not calibrate

def toggle_record():
    global recording, record_proc, rec_btn
    if not recording:
        cmd = [
            "gst-launch-1.0",
            "udpsrc", "port=5000",
            "!", "application/x-rtp, media=video, encoding-name=H264, payload=96",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "mp4mux",
            "!", "filesink", "location=rov_recording.mp4"
        ]
        record_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        recording = True
        if rec_btn:
            rec_btn.config(text="Stop Recording")
    else:
        try:
            record_proc.terminate()
        except Exception:
            pass
        recording = False
        if rec_btn:
            rec_btn.config(text="Start Recording")

def start_video_stream():
    """Start a local GStreamer pipeline that listens on UDP port 5000 and
    displays the incoming H.264 RTP stream. Returns the subprocess.Popen
    object so callers can terminate it when desired.
    """
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

    logging.info(f'Starting video display pipeline: {cmd}')
    # detach the child so it doesn't share the terminal/session and avoid
    # blocking when the child writes to stdout/stderr.
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return proc


def read_video_stream_output(video_proc):
    """Read available output from the video process without blocking."""
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
        # select may fail on some platforms; ignore and continue
        pass

def main():
    global video, rec_btn, recording, record_proc
    
    # Set up the GUI
    root, left_canvas, right_canvas, claw_canvas, status_label, rec_btn = setup_gui(toggle_cal, toggle_record)

    # Update function for controller visualizations
    def update_displays():
        # Update left joystick (LX, LY) - use raw values to show deadzone movement
        left_canvas.delete("all")
        draw_joystick(left_canvas, axes_raw["LX"], axes_raw["LY"], DEADZONE)
        
        # Update right joystick (RX, RY) - use raw values to show deadzone movement
        right_canvas.delete("all")
        draw_joystick(right_canvas, axes_raw["RX"], axes_raw["RY"], DEADZONE)
        
        # Update claw
        claw_canvas.delete("all")
        draw_claw(claw_canvas, claw_pos)
        
        # Update status label
        cal_status = "CAL" if calibrate else "---"
        rec_status = "REC" if recording else "---"
        status_label.config(text=f"Calibrate: {cal_status}  |  Recording: {rec_status}  |  LT: {axes['LT']:.2f}  RX: {axes['RX']:.2f}")
        
        root.after(50, update_displays)

    root.after(50, update_displays)

    # start the video display pipeline on app start if enabled
    global video
    if VIDEO_ENABLED:
        try:
            video = start_video_stream()
        except Exception as e:
            logging.error(f"Failed to start video stream: {e}")

        def poll_video():
            read_video_stream_output(video)
            root.after(200, poll_video)

        root.after(200, poll_video)

    # handle terminal Ctrl+C (SIGINT) so the Tk mainloop exits cleanly
    def _sigint_handler(signum, frame=None):
        print('caught ^C')
        on_close()

    def on_close():
        # terminate recording and video processes, then destroy UI
        global recording, record_proc, video
        try:
            if record_proc is not None and recording:
                record_proc.terminate()
        except Exception:
            pass
        try:
            if video is not None and video.poll() is None:
                video.terminate()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    def _check():
        # schedule another check so the signal gets processed while
        # the Tk event loop is running
        root.after(500, _check)

    # register the signal handler and start the periodic check
    signal.signal(signal.SIGINT, _sigint_handler)
    root.after(500, _check)
    root.bind_all('<Control-c>', lambda e: _sigint_handler(None, None))
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()

if __name__ == "__main__":
    print("Starting ROV dashboard...")
    main()

